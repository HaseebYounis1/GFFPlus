#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sourcecode" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vx.gff.Query import Query, DBFile
from vx.gff.Settings import Settings


class _DummyHandler:
    def __init__(self):
        self.headers = {}

    def set_header(self, key, value):
        self.headers[key] = value


class _DummyApp:
    def __init__(self, argms):
        self.argms = argms


class TestUIAndExportFixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.orig_data_path = Settings.DATA_PATH
        Settings.DATA_PATH = os.path.join(self.tmpdir.name, "")
        self.ds_id = "deadbeef0000000000000001"
        self.ds_dir = Path(Settings.DATA_PATH) / self.ds_id
        self.ds_dir.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame({
            "f1": [1.0, 2.0, 3.0],
            "f2": [4.0, 5.0, 6.0],
            "Category": [0, 1, 0],
        })
        df.to_csv(self.ds_dir / "transform.csv", index=False)

        # Simulate NJ graph with category==1 auxiliary nodes (label == -1)
        feature_obj = {
            "graph": {
                "nodes": [
                    {"name": 0, "label": 0, "category": 0, "weight": 0.9},
                    {"name": 1, "label": 1, "category": 0, "weight": 0.5},
                    {"name": 2, "label": 2, "category": 0, "weight": 1.0},
                    {"name": 3, "label": -1, "category": 1, "weight": 0.001},
                ],
                "links": [],
                "whole": [],
            }
        }
        DBFile.writeFile(str(self.ds_dir / "feature.obj"), feature_obj)

    def tearDown(self):
        Settings.DATA_PATH = self.orig_data_path
        self.tmpdir.cleanup()

    def test_exportfeat2datafile_excludes_nj_auxiliary_nodes(self):
        handler = _DummyHandler()
        app = _DummyApp({"file": self.ds_id})
        fake_row = [{"_id": self.ds_id, "name": "My Dataset Name", "fenames": ["f1", "f2", "Category"]}]

        with patch("vx.gff.Query.DBX.find", return_value=fake_row), \
             patch("vx.gff.Query.Query.converid", return_value=self.ds_id):
            exported = Query.exportfeat2datafile(app, handler)

        lines = [line for line in exported.splitlines() if line.strip() != ""]
        self.assertEqual(lines[0], "DY")
        # Must export 3 real feature nodes, NOT 4 (auxiliary category==1 node excluded)
        self.assertEqual(lines[1], "3")
        self.assertEqual(lines[2], "3")
        self.assertEqual(lines[3], "fe0;fe1;fe2")
        self.assertEqual(len(lines), 4 + 3)
        self.assertTrue(lines[4].startswith("f1;"))
        self.assertTrue(lines[5].startswith("f2;"))
        self.assertTrue(lines[6].startswith("Category;"))
        self.assertIn('filename="My_Dataset_Name.data"', handler.headers["Content-Disposition"])

    def test_frontend_assets_contain_required_fixes(self):
        static_dir = ROOT / "sourcecode" / "src" / "vx" / "gff" / "static" / "lib"
        index_html = (ROOT / "sourcecode" / "src" / "vx" / "gff" / "templates" / "index.html").read_text(encoding="utf-8")
        util_js = (static_dir / "Util.js").read_text(encoding="utf-8")
        palette_js = (static_dir / "chart_palettecolors.js").read_text(encoding="utf-8")
        force_js = (static_dir / "chart_force.js").read_text(encoding="utf-8")
        proj_js = (static_dir / "chart_projection.js").read_text(encoding="utf-8")
        libdata_js = (static_dir / "libdata.js").read_text(encoding="utf-8")
        unselected_js = (static_dir / "UnselectedFeatures.js").read_text(encoding="utf-8")

        # 1. Constant zoom helper & damped left bar
        self.assertIn("function createConstantZoom", util_js)
        self.assertIn("dragSensitivity", palette_js)
        self.assertIn("stepSize", palette_js)

        # 2. High-contrast selected features
        self.assertIn("node-selection-ring", force_js)
        self.assertIn("#d50000", force_js)

        # 3. Stable Flexbox layout + XAI summary in separate bottom dock + point files panel
        self.assertIn("gff-panels-row", index_html)
        self.assertIn('id="gffBottomDock"', index_html)
        self.assertIn("gff-canvas-box", index_html)
        self.assertIn('id="pointfilespanel"', index_html)
        self.assertIn('id="pointfilesinput"', index_html)
        self.assertIn('id="pointfolderinput"', index_html)

        # 4. Target excluded from dropdowns
        self.assertIn("String(item.id) === String(idt)", unselected_js)
        self.assertIn("populateInstanceIdDropdown", libdata_js)

        # 5. Selection count preserved on load / algorithm change
        self.assertIn("syncInTargetState", libdata_js)
        self.assertNotIn("self.changeintarget();\n                        }", libdata_js)

        # 6. VisPipeline .prj export with file names & Blob download
        self.assertIn("formatVisPipelinePrj", proj_js)
        self.assertIn("_whole.prj", proj_js)
        self.assertIn("getExportInstanceName", libdata_js)
        self.assertIn("loadPointFiles", libdata_js)
        self.assertIn("XMLSerializer", libdata_js)

    def test_all_projection_and_xai_scores_are_reproducible(self):
        import numpy as np
        from vx.gff.MakeProjection import MakeProjection
        from vx.gff.XAI import XAIPipeline

        rng = np.random.default_rng(123)
        n = 60
        df = pd.DataFrame({
            "a": np.concatenate([rng.normal(2.0, 0.3, 30), rng.normal(-2.0, 0.3, 30)]),
            "b": np.concatenate([rng.normal(-1.5, 0.3, 30), rng.normal(1.5, 0.3, 30)]),
            "c": rng.normal(0.0, 1.0, n),
            "d": rng.normal(0.5, 0.8, n),
            "Category": [0] * 30 + [1] * 30,
        })
        for fname in ("original.csv", "working.csv", "transform.csv"):
            df.to_csv(self.ds_dir / fname, index=False)

        # Verify PCA, t-SNE, MDS, UMAP, and LSP produce identical scores across repeated runs
        # AND regardless of feature selection order ([3, 0, 1] vs [1, 3, 0])
        for method in ("pca", "tsne", "mds", "umap", "lsptsne"):
            p1 = MakeProjection()
            p1.execute({
                "file": self.ds_id,
                "projection": method,
                "instanceproximity": "Euclidean",
                "target": 4,
                "featureselected": [3, 0, 1],
            })
            p2 = MakeProjection()
            p2.execute({
                "file": self.ds_id,
                "projection": method,
                "instanceproximity": "Euclidean",
                "target": 4,
                "featureselected": [1, 3, 0],
            })
            self.assertEqual(p1.data["quality"], p2.data["quality"], f"Quality mismatch for {method}")
            self.assertEqual(
                [(round(pt["x"], 6), round(pt["y"], 6)) for pt in p1.data["points"]],
                [(round(pt["x"], 6), round(pt["y"], 6)) for pt in p2.data["points"]],
                f"Coordinates mismatch for {method}",
            )

        # Verify XAIPipeline produces identical importance & permutation scores across repeated runs
        xai = XAIPipeline()
        r1 = xai.execute(Settings.DATA_PATH, {"file": self.ds_id, "target": 4, "xai_enable_shap": False})
        r2 = xai.execute(Settings.DATA_PATH, {"file": self.ds_id, "target": 4, "xai_enable_shap": False})
        self.assertEqual(r1["importance"], r2["importance"])
        self.assertEqual(r1["permutation"]["values"], r2["permutation"]["values"])


if __name__ == "__main__":
    unittest.main()
