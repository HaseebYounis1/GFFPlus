#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Production-readiness audit tests for GFF+:
1. Static UI, DOM, CSS clipping, z-index hierarchy, handler guards, and JS syntax checks.
2. Live Tornado HTTP end-to-end integration tests (auth, upload, feature graph,
   projection, silhouette, .data export, XAI, multimodal media upload/serve, path safety).
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import zipfile
from http.cookies import SimpleCookie
from pathlib import Path

from tornado.testing import AsyncHTTPTestCase

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sourcecode" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vx.com.py.database.MongoDB import MongoDB
from vx.gff.Server import Server
from vx.gff.Settings import Settings
from vx.gff.User import User

STATIC_LIB = ROOT / "sourcecode" / "src" / "vx" / "gff" / "static" / "lib"
TEMPLATES = ROOT / "sourcecode" / "src" / "vx" / "gff" / "templates"


def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _extract_css_block(css_text: str, selector: str) -> str:
    pattern = re.escape(selector) + r"\s*\{([^}]*)\}"
    matches = re.findall(pattern, css_text, flags=re.S)
    return "\n".join(matches)


def _encode_multipart(fields: dict, files: list):
    """Build multipart/form-data body and Content-Type header."""
    boundary = "----GFFTestBoundary7MA4YWxkTrZu0gW"
    lines = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        lines.append(f"{value}\r\n".encode("utf-8"))
    for field_name, filename, content_type, data in files:
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        lines.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        lines.append(data)
        lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(lines), f"multipart/form-data; boundary={boundary}"


class TestStaticUIAndDOMIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index_html = (TEMPLATES / "index.html").read_text(encoding="utf-8", errors="ignore")
        cls.index_active = _strip_html_comments(cls.index_html)
        cls.libdata_js = (STATIC_LIB / "libdata.js").read_text(encoding="utf-8", errors="ignore")
        cls.style_css = (STATIC_LIB / "style.css").read_text(encoding="utf-8", errors="ignore")
        cls.all_custom_js = sorted(
            p for p in STATIC_LIB.glob("*.js")
            if not p.name.startswith(("d3", "jquery", "FileSaver"))
        )
        # Active scripts actually loaded by index.html (excluding third-party vendor libs)
        loaded_names = re.findall(r'<script[^>]+src=["\']\.?/?lib/([^"\'?#]+\.js)', cls.index_active)
        cls.loaded_custom_js = sorted({
            STATIC_LIB / name
            for name in loaded_names
            if "/" not in name and not name.startswith(("d3", "jquery", "FileSaver"))
        })

    def test_all_custom_js_files_pass_node_syntax_check(self):
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node is not installed on PATH")
        self.assertGreater(len(self.loaded_custom_js), 10)
        failures = []
        for js_file in self.loaded_custom_js:
            self.assertTrue(js_file.is_file(), f"Missing script referenced in index.html: {js_file.name}")
            proc = subprocess.run(
                [node_bin, "--check", str(js_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                failures.append(f"{js_file.name}: {proc.stderr.strip()}")
        self.assertEqual(failures, [], "JS syntax errors found:\n" + "\n".join(failures))

    def test_all_gffobj_methods_called_in_index_exist(self):
        called = set(re.findall(r"GFFOBJ\.([A-Za-z0-9_]+)\s*\(", self.index_active))
        defined = set(re.findall(r"(?:this|self)\.([A-Za-z0-9_]+)\s*=", self.libdata_js))
        missing = sorted(called - defined)
        self.assertEqual(missing, [], f"index.html calls undefined GFFOBJ methods: {missing}")

    def test_all_gelem_ids_in_index_exist(self):
        html_ids = set(re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', self.index_active))
        js_ids = set()
        for js_file in self.all_custom_js:
            txt = js_file.read_text(encoding="utf-8", errors="ignore")
            js_ids.update(re.findall(r'setAttribute\(["\']id["\']\s*,\s*["\'`]([^"\'`$]+)["\'`]', txt))
            js_ids.update(re.findall(r'id=["\']([A-Za-z0-9_-]+)["\']', txt))
        all_known_ids = html_ids | js_ids
        referenced = set(re.findall(r"gelem\(['\"]([^'\"]+)['\"]\)", self.index_active))
        missing = sorted(referenced - all_known_ids)
        self.assertEqual(missing, [], f"index.html references missing DOM IDs via gelem(): {missing}")

    def test_no_unguarded_layout_method_calls_in_index_html(self):
        """Every GFFOBJ.layoutfeatures.<fn>( or GFFOBJ.layoutinstance.<fn>( call in
        index.html must be guarded so switching layouts or clicking before load
        never throws TypeError."""
        for obj_name in ("layoutfeatures", "layoutinstance"):
            pattern = re.compile(rf"GFFOBJ\.{obj_name}\.([A-Za-z0-9_]+)\s*\(")
            for match in pattern.finditer(self.index_active):
                method = match.group(1)
                start = max(0, match.start() - 180)
                context = self.index_active[start:match.start()]
                has_guard = (
                    f"GFFOBJ.{obj_name}.{method}" in context
                    or (obj_name == "layoutinstance" and "GFFOBJ.layoutinstance!=null" in context)
                )
                self.assertTrue(
                    has_guard,
                    f"Unguarded GFFOBJ.{obj_name}.{method}() call in index.html",
                )

    def test_dropdown_containers_do_not_clip_overflow(self):
        for selector in (".gff-canvas-box", ".gff-canvas-strip-right"):
            block = _extract_css_block(self.style_css, selector)
            self.assertTrue(block, f"Missing CSS rule for {selector}")
            self.assertIn("overflow: visible", block, f"{selector} must allow dropdown overflow")
            self.assertNotIn("overflow: hidden", block, f"{selector} must not clip dropdowns")
            self.assertNotIn("overflow-x: hidden", block, f"{selector} must not clip dropdowns")

    def test_z_index_layering_hierarchy(self):
        modal_js = (STATIC_LIB / "Modal.js").read_text(encoding="utf-8", errors="ignore")
        util_js = (STATIC_LIB / "Util.js").read_text(encoding="utf-8", errors="ignore")
        colors_js = (STATIC_LIB / "Colors.js").read_text(encoding="utf-8", errors="ignore")
        unsel_js = (STATIC_LIB / "UnselectedFeatures.js").read_text(encoding="utf-8", errors="ignore")

        # Modal.js: #idwinmodal container must have z-index >= 10000 and no duplicate lower z-index
        m_modal = re.search(r'id="idwinmodal"[^>]*style="([^"]+)"', modal_js, flags=re.S)
        self.assertIsNotNone(m_modal, "Missing #idwinmodal in Modal.js")
        modal_z = [int(z) for z in re.findall(r"z-index:\s*(\d+)", m_modal.group(1))]
        self.assertEqual(len(modal_z), 1, f"#idwinmodal should have exactly one z-index, got {modal_z}")
        self.assertGreaterEqual(modal_z[0], 10000, f"#idwinmodal z-index too low: {modal_z[0]}")

        # Util.js: outer loading overlays (#idloading / #idloadingMP) >= 10000
        util_z = [int(z) for z in re.findall(r"z-index:\s*(\d+)", util_js)]
        self.assertTrue(util_z, "Util.js missing z-index")
        self.assertGreaterEqual(max(util_z), 10000, f"Util.js outer overlay z-index too low: {util_z}")

        # Colors.js: color palette modal >= 2000
        colors_z = [int(z) for z in re.findall(r"z-index:\s*(\d+)", colors_js)]
        self.assertTrue(colors_z, "Colors.js missing z-index")
        self.assertGreaterEqual(max(colors_z), 2000, f"Colors.js z-index too low: {colors_z}")

        # UnselectedFeatures.js: Sel/Unsel dropdown >= 1000
        unsel_z = [int(z) for z in re.findall(r"z-index:\s*(\d+)", unsel_js)]
        self.assertTrue(unsel_z, "UnselectedFeatures.js missing z-index")
        self.assertGreaterEqual(max(unsel_z), 1000, f"UnselectedFeatures.js z-index too low: {unsel_z}")

        # style.css: #pointdatamodal >= 9000
        pm_block = _extract_css_block(self.style_css, "#pointdatamodal")
        self.assertTrue(pm_block, "Missing #pointdatamodal in style.css")
        pm_z = re.search(r"z-index:\s*(\d+)", pm_block)
        self.assertIsNotNone(pm_z, "#pointdatamodal missing z-index")
        self.assertGreaterEqual(int(pm_z.group(1)), 9000)

        # index.html: #featselectfeature & #featselectinstance >= 10
        for elem_id, min_z in (
            ("featselectfeature", 10),
            ("featselectinstance", 10),
        ):
            m = re.search(rf'id="{elem_id}"[^>]*style="([^"]+)"', self.index_active, flags=re.S)
            self.assertIsNotNone(m, f"Missing styled element #{elem_id} in index.html")
            zm = re.search(r"z-index:\s*(\d+)", m.group(1))
            self.assertIsNotNone(zm, f"Element #{elem_id} missing z-index")
            self.assertGreaterEqual(int(zm.group(1)), min_z, f"#{elem_id} z-index below {min_z}")

    def test_view_features_selected_and_filter_guards_present(self):
        self.assertIn("viewFeaturesSelected = function", self.libdata_js)
        self.assertIn("Array.isArray(self.datagff.configfeature.nodes)", self.libdata_js)
        self.assertIn("if (!self.layoutfeatures)", self.libdata_js)
        self.assertIn("No matching feature names found", self.libdata_js)

    def test_target_selection_reads_dropdown_first(self):
        """Ensure changing #target is never snapped back to an older self.target."""
        idx = self.libdata_js.find("this.getTargetId = function")
        self.assertNotEqual(idx, -1)
        body = self.libdata_js[idx:idx + 600]
        pos_el = body.find("targetElement.value")
        pos_self = body.find("parseInt(self.target")
        self.assertNotEqual(pos_el, -1, "getTargetId must read targetElement.value")
        self.assertNotEqual(pos_self, -1, "getTargetId must fall back to self.target")
        self.assertLess(
            pos_el,
            pos_self,
            "getTargetId must read #target dropdown BEFORE falling back to cached self.target",
        )
        self.assertIn('ob.in.argms["target"] = self.getTargetId();', self.libdata_js)
        self.assertNotIn('ob.in.argms["target"] = self.target;', self.libdata_js)

    def test_responsive_fullscreen_layout_contract(self):
        """Ensure panels scale to full viewport width/height with resize handling and no 720px cap."""
        self.assertIn("computeResponsivePanelDimensions", self.libdata_js)
        self.assertIn("applyPanelDimensions", self.libdata_js)
        self.assertIn("handleViewportResize", self.libdata_js)
        self.assertIn('window.addEventListener("resize"', self.libdata_js)
        self.assertNotIn("Math.min(720", self.libdata_js)
        for chart_name in (
            "chart_force.js",
            "chart_projection.js",
            "chart_bipartite.js",
            "chart_circularbundle.js",
            "chart_feature_community.js",
            "chart_feature_heatmap.js",
            "chart_upset.js",
            "chart_circlepack.js",
            "chart_sunburst.js",
        ):
            txt = (STATIC_LIB / chart_name).read_text(encoding="utf-8", errors="ignore")
            self.assertIn("lheight", txt, f"{chart_name} must support responsive lheight")


class TestLiveServerEndToEnd(AsyncHTTPTestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_data_path = Settings.DATA_PATH
        self.orig_cookie_secret = Settings.COOKIE_SECRET
        self.orig_dbfile = MongoDB._dbfile
        self.orig_multiuser = Settings.MULIUSER

        Settings.DATA_PATH = os.path.join(self.tmpdir.name, "data", "")
        Settings.COOKIE_SECRET = "test-secret-" + ("a" * 48)
        Settings.MULIUSER = 1
        MongoDB._dbfile = Path(self.tmpdir.name) / "localdb.json"

        # Seed a test admin user in isolated JSON DB
        self.test_email = "e2e@test.local"
        self.test_pass = "StrongPass123!"
        uid = User.newUser({
            "name": "E2E Tester",
            "fono": "",
            "addres": "",
            "email": self.test_email,
            "password": self.test_pass,
            "adminid": 1,
        })
        self.assertTrue(uid)
        self.cookies = {}
        super().setUp()

    def tearDown(self):
        super().tearDown()
        Settings.DATA_PATH = self.orig_data_path
        Settings.COOKIE_SECRET = self.orig_cookie_secret
        Settings.MULIUSER = self.orig_multiuser
        MongoDB._dbfile = self.orig_dbfile
        self.tmpdir.cleanup()

    def get_app(self):
        return Server()

    def _update_cookies(self, response):
        for header in response.headers.get_list("Set-Cookie"):
            c = SimpleCookie()
            c.load(header)
            for k, morsel in c.items():
                self.cookies[k] = morsel.value

    def _cookie_header(self):
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _login(self):
        # 1. GET /login to obtain _xsrf cookie
        r_get = self.fetch("/login", method="GET")
        self.assertEqual(r_get.code, 200)
        self._update_cookies(r_get)
        xsrf = self.cookies.get("_xsrf")
        self.assertTrue(xsrf, "Missing _xsrf cookie on GET /login")

        # 2. POST /login with credentials
        body = urllib.parse.urlencode({
            "_xsrf": xsrf,
            "user": self.test_email,
            "password": self.test_pass,
            "option": "1",
        })
        r_post = self.fetch(
            "/login",
            method="POST",
            body=body,
            headers={
                "Cookie": self._cookie_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            follow_redirects=False,
        )
        self.assertEqual(r_post.code, 302)
        self._update_cookies(r_post)
        self.assertIn("user", self.cookies, "Login did not set user cookie")
        return xsrf

    def _post_query(self, payload: dict):
        xsrf = self.cookies["_xsrf"]
        body = urllib.parse.urlencode({
            "_xsrf": xsrf,
            "data": json.dumps({"argms": payload}),
        })
        return self.fetch(
            "/query",
            method="POST",
            body=body,
            headers={
                "Cookie": self._cookie_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

    def test_full_end_to_end_user_workflow(self):
        xsrf = self._login()

        # 1. GET / renders main page with all critical UI containers
        r_idx = self.fetch("/", method="GET", headers={"Cookie": self._cookie_header()})
        self.assertEqual(r_idx.code, 200)
        html = r_idx.body.decode("utf-8")
        for elem_id in (
            "gffPanelsRow",
            "gffBottomDock",
            "fesenanetxt",
            "pointdatamodal",
            "featselectfeature",
            "featselectinstance",
        ):
            self.assertIn(f'id="{elem_id}"', html, f"Rendered index.html missing #{elem_id}")

        # 2. POST /upload with raw streaming CSV (12 rows, 4 features + Category + file)
        csv_lines = ["file,f1,f2,f3,f4,Category"]
        for i in range(12):
            cls = 0 if i < 6 else 1
            base = 1.0 if cls == 0 else 10.0
            csv_lines.append(
                f"item_{i}.png,{base + i*0.1:.2f},{base + i*0.2:.2f},{base*0.5 + i*0.05:.2f},{i*0.3:.2f},{cls}"
            )
        csv_bytes = ("\n".join(csv_lines) + "\n").encode("utf-8")
        r_up = self.fetch(
            "/upload",
            method="POST",
            body=csv_bytes,
            headers={
                "Cookie": self._cookie_header(),
                "Content-Type": "application/octet-stream",
                "X-Filename": "smoke.csv",
                "X-Xsrftoken": xsrf,
            },
        )
        self.assertEqual(r_up.code, 200, f"/upload failed: {r_up.body}")
        up_json = json.loads(r_up.body.decode("utf-8"))
        ds_id = up_json.get("file") or up_json.get("_id") or up_json.get("id")
        self.assertTrue(ds_id, f"Unexpected /upload response: {up_json}")

        # 2b. Open dataset via Query type 24 to get feature names & Category index
        def _wait_ready(dataset_id, collect="init", query_paths=None, timeout_s=15.0):
            import time
            if query_paths is None:
                query_paths = [["fenames"]]
            deadline = time.time() + timeout_s
            last = None
            while time.time() < deadline:
                r = self._post_query({
                    "type": 24,
                    "file": dataset_id,
                    "data": {"collect": collect, "query": query_paths},
                })
                self.assertEqual(r.code, 200, f"opendataset failed: {r.body}")
                last = json.loads(r.body.decode("utf-8"))
                if last.get("statusopt") == 0:
                    out = {}
                    for item in last.get("response", []):
                        key = item["query"][0]
                        out[key] = item["response"]
                    return out
                time.sleep(0.05)
            self.fail(f"Dataset job did not finish within {timeout_s}s; last={last}")

        ds_info = _wait_ready(ds_id, collect="init", query_paths=[["fenames"]])
        fenames = ds_info.get("fenames", [])
        self.assertIn("Category", fenames, f"Category missing from fenames: {fenames}")
        cat_idx = fenames.index("Category")
        feat_indices = [i for i, name in enumerate(fenames) if name not in ("Category", "file")]
        self.assertGreaterEqual(len(feat_indices), 4)

        # 3. Feature Graph (MST and NJ)
        for alg in ("mst", "nj"):
            r_fg = self._post_query({
                "type": 0,
                "file": ds_id,
                "target": cat_idx,
                "intarget": False,
                "proximity": "Cosine",
                "instanceproximity": "Euclidean",
                "submodular_size": 3000,
                "relevance": "Pearson",
                "algorithm": alg,
                "layout": "fo",
                "isfeature": 1,
                "featureselected": feat_indices,
                "ranking": [],
                "idinstanceslabels": -1,
                "statusval": f"e2e-{alg}",
            })
            self.assertEqual(r_fg.code, 200, f"Feature graph ({alg}) failed: {r_fg.body}")
            ds_after = _wait_ready(ds_id, collect="features", query_paths=[["layoutfeature"]])
            graph = ds_after.get("layoutfeature", {}).get("graph", {})
            self.assertGreaterEqual(len(graph.get("nodes", [])), 4, f"Missing graph nodes for {alg}")

        # 4. Projection (PCA) + Reproducibility check
        proj_args = {
            "type": 1,
            "file": ds_id,
            "threshold": 0.78,
            "target": cat_idx,
            "intarget": False,
            "proximity": "Cosine",
            "instanceproximity": "Euclidean",
            "submodular_size": 3000,
            "relevance": "Pearson",
            "algorithm": "mst",
            "layout": "fo",
            "projection": "PCA",
            "isfeature": 0,
            "featureselected": feat_indices,
            "ranking": [],
            "idinstanceslabels": -1,
            "statusval": "e2e-pca",
        }
        r_p1 = self._post_query(proj_args)
        self.assertEqual(r_p1.code, 200, f"PCA projection failed: {r_p1.body}")
        p1 = _wait_ready(ds_id, collect="instances", query_paths=[["layoutinstance"]]).get("layoutinstance", {})
        self.assertTrue(p1.get("points"), f"PCA projection returned no points: {p1}")

        r_p2 = self._post_query(proj_args)
        self.assertEqual(r_p2.code, 200)
        p2 = _wait_ready(ds_id, collect="instances", query_paths=[["layoutinstance"]]).get("layoutinstance", {})
        self.assertEqual(p1["points"], p2["points"], "PCA projection must be deterministic")

        # 5. Silhouette score reproducibility
        sil_args = {
            "type": 13,
            "file": ds_id,
            "statusval": "e2e-silhouette",
        }
        r_s1 = self._post_query(sil_args)
        r_s2 = self._post_query(sil_args)
        self.assertEqual(r_s1.code, 200, f"Silhouette query failed: {r_s1.body}")
        self.assertEqual(r_s1.body, r_s2.body, "Silhouette score must be reproducible")
        self.assertIsInstance(json.loads(r_s1.body.decode("utf-8")), (int, float))

        # 6. .data export (VisPipeline format, excluding NJ auxiliary nodes)
        r_exp = self._post_query({"type": 17, "file": ds_id})
        self.assertEqual(r_exp.code, 200, f".data export failed: {r_exp.body}")
        exp_lines = [ln for ln in r_exp.body.decode("utf-8").splitlines() if ln.strip()]
        self.assertEqual(exp_lines[0], "DY")

        # 7. Upload multimodal media ZIP (raw streaming body) and serve files safely
        zip_buf = io.BytesIO()
        png_stub = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("item_0.png", png_stub)
            zf.writestr("notes.txt", b"hello multimodal")
        r_mu = self.fetch(
            "/upload_media",
            method="POST",
            body=zip_buf.getvalue(),
            headers={
                "Cookie": self._cookie_header(),
                "Content-Type": "application/octet-stream",
                "X-Dataset-Id": ds_id,
                "X-Filename": "media.zip",
                "X-Xsrftoken": xsrf,
            },
        )
        self.assertEqual(r_mu.code, 200, f"/upload_media failed: {r_mu.body}")
        mu_json = json.loads(r_mu.body.decode("utf-8"))
        self.assertGreaterEqual(mu_json.get("saved", 0), 2)

        # List media via Query type 29
        r_ml = self._post_query({"type": 29, "file": ds_id})
        self.assertEqual(r_ml.code, 200)
        ml_json = json.loads(r_ml.body.decode("utf-8"))
        media_names = [f["name"] for f in ml_json.get("files", [])]
        self.assertIn("item_0.png", media_names)
        self.assertIn("notes.txt", media_names)

        # Serve uploaded media file
        r_img = self.fetch(
            f"/data/{ds_id}/media/item_0.png",
            method="GET",
            headers={"Cookie": self._cookie_header()},
        )
        self.assertEqual(r_img.code, 200)
        self.assertEqual(r_img.body, png_stub)

        # Path traversal attempt must be rejected (403 or 404)
        r_trav = self.fetch(
            f"/data/{ds_id}/media/..%2Ftransform.csv",
            method="GET",
            headers={"Cookie": self._cookie_header()},
        )
        self.assertIn(r_trav.code, (400, 403, 404))

    def test_switching_between_multiple_target_variables_end_to_end(self):
        """Users must be able to pick ANY column (string health labels, cluster IDs,
        or standard class) as the target variable and re-project / re-score cleanly."""
        xsrf = self._login()

        csv_lines = ["f1,f2,f3,f4,health_condition,cluster_k,Category"]
        conditions = ["healthy", "diabetic", "hypertensive"]
        for i in range(18):
            cond = conditions[i % 3]
            clust = i % 3
            cat = 0 if i < 9 else 1
            base = (clust + 1) * 3.0
            csv_lines.append(
                f"{base + i*0.05:.2f},{base*1.2 + i*0.03:.2f},{cat*5.0 + i*0.1:.2f},{i*0.2:.2f},{cond},{clust},{cat}"
            )
        csv_bytes = ("\n".join(csv_lines) + "\n").encode("utf-8")
        r_up = self.fetch(
            "/upload",
            method="POST",
            body=csv_bytes,
            headers={
                "Cookie": self._cookie_header(),
                "Content-Type": "application/octet-stream",
                "X-Filename": "multi_target.csv",
                "X-Xsrftoken": xsrf,
            },
        )
        self.assertEqual(r_up.code, 200, f"/upload failed: {r_up.body}")
        ds_id = json.loads(r_up.body.decode("utf-8"))["file"]

        def _wait_ready(collect, query_paths, timeout_s=15.0):
            import time
            deadline = time.time() + timeout_s
            last = None
            while time.time() < deadline:
                r = self._post_query({
                    "type": 24,
                    "file": ds_id,
                    "data": {"collect": collect, "query": query_paths},
                })
                self.assertEqual(r.code, 200)
                last = json.loads(r.body.decode("utf-8"))
                if last.get("statusopt") == 0:
                    return {item["query"][0]: item["response"] for item in last.get("response", [])}
                time.sleep(0.05)
            self.fail(f"Timed out waiting for {collect}: {last}")

        fenames = _wait_ready("init", [["fenames"]])["fenames"]
        feat_indices = [fenames.index(c) for c in ("f1", "f2", "f3", "f4")]

        for target_col, expected_labels in (
            ("health_condition", {"healthy", "diabetic", "hypertensive"}),
            ("cluster_k", {"0", "1", "2"}),
            ("Category", {"0", "1"}),
        ):
            t_idx = fenames.index(target_col)
            r_fg = self._post_query({
                "type": 0,
                "file": ds_id,
                "target": t_idx,
                "intarget": False,
                "proximity": "Cosine",
                "instanceproximity": "Euclidean",
                "submodular_size": 3000,
                "relevance": "Pearson",
                "algorithm": "mst",
                "layout": "fo",
                "isfeature": 1,
                "featureselected": feat_indices,
                "ranking": [],
                "idinstanceslabels": -1,
                "statusval": f"fg-{target_col}",
            })
            self.assertEqual(r_fg.code, 200)
            fg = _wait_ready("features", [["layoutfeature"]])["layoutfeature"]
            self.assertGreaterEqual(len(fg.get("graph", {}).get("nodes", [])), 4)

            r_pr = self._post_query({
                "type": 1,
                "file": ds_id,
                "threshold": 0.78,
                "target": t_idx,
                "intarget": False,
                "proximity": "Cosine",
                "instanceproximity": "Euclidean",
                "submodular_size": 3000,
                "relevance": "Pearson",
                "algorithm": "mst",
                "layout": "fo",
                "projection": "PCA",
                "isfeature": 0,
                "featureselected": feat_indices,
                "ranking": [],
                "idinstanceslabels": -1,
                "statusval": f"proj-{target_col}",
            })
            self.assertEqual(r_pr.code, 200)
            inst = _wait_ready("instances", [["layoutinstance"]])["layoutinstance"]
            self.assertEqual(len(inst.get("points", [])), 18)
            label_values = {str(v) for v in inst.get("tartegsnames", {}).values()}
            self.assertEqual(label_values, expected_labels, f"Unexpected labels for target {target_col}")

            r_sil = self._post_query({"type": 13, "file": ds_id, "statusval": f"sil-{target_col}"})
            self.assertEqual(r_sil.code, 200)
            self.assertIsInstance(json.loads(r_sil.body.decode("utf-8")), (int, float))


if __name__ == "__main__":
    unittest.main()
