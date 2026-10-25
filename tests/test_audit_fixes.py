import asyncio
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import zipfile

import numpy as np
import pandas as pd
from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import create_signed_value, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sourcecode" / "src"))
from vx.com.py.database.MongoDB import MongoDB
from vx.com.py.sampling.CSVSample import sample_csv
from vx.com.px.dataset.dataio_pure import DataMatrix
from vx.gff.Ingestion import ingest_csv
from vx.gff.MakeProjection import MakeProjection
from vx.gff.Query import Query
from vx.gff.Security import dataset_path
from vx.gff.Server import Server
from vx.gff.Settings import Settings
from vx.gff.Upload import import_upload
from vx.gff.XAI import XAIPipeline


class TemporaryData:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(Settings, "DATA_PATH", self.temp.name + "/"),
                        patch.object(Settings, "COOKIE_SECRET", "test-secret-not-for-production"),
                        patch.object(Settings, "DEBUG", False),
                        patch.object(MongoDB, "_dbfile", self.root / "localdb.json")]
        for item in self.patches:
            item.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()


class DataFixTests(TemporaryData, unittest.TestCase):
    def test_corrupt_database_is_never_replaced(self):
        MongoDB._dbfile.write_text('{"data": broken', encoding="utf-8")
        before = MongoDB._dbfile.read_bytes()
        for operation in (lambda: MongoDB.insert(None, "data", {}),
                          lambda: MongoDB.update(None, "data", {}, {}),
                          lambda: MongoDB.delete(None, "data", {})):
            with self.assertRaises(RuntimeError):
                operation()
            self.assertEqual(MongoDB._dbfile.read_bytes(), before)
        for invalid in ('{}', '[]', '{"user": [], "data": {}}'):
            MongoDB._dbfile.write_text(invalid)
            with self.assertRaises(RuntimeError):
                MongoDB.insert(None, "data", {})
            self.assertEqual(MongoDB._dbfile.read_text(), invalid)

    def test_old_projection_cache_is_recomputed(self):
        ds = self.root / "ds"
        ds.mkdir()
        cache = ds / "instance.obj"
        cache.write_text('{"points": []}')
        args = {"file": "ds", "projection": "pca"}
        MongoDB.insert(None, "data", {"_id": "ds", "configinstance": args})
        self.assertFalse(Query.isprojectioncurrent(SimpleNamespace(argms=args)))
        cache.write_text('{"points": [], "targettype": "regression"}')
        self.assertTrue(Query.isprojectioncurrent(SimpleNamespace(argms=args)))

    def test_continuous_targets_do_not_get_a_class_silhouette(self):
        ds = self.root / "ds"
        ds.mkdir()
        (ds / "instance.obj").write_text(json.dumps({"targettype": "regression", "points": [
            {"x": 0, "y": 0, "t": 0.2}, {"x": 1, "y": 1, "t": 0.8}]}))
        MongoDB.insert(None, "data", {"_id": "ds", "typeinstance": "projection"})
        self.assertIsNone(Query.silhouette(SimpleNamespace(argms={"file": "ds"})))

    def test_delete_rejects_parent_and_absolute_paths(self):
        outside = self.root / "keep.txt"
        outside.write_text("keep")
        for value in ("..", "../keep.txt", str(self.root), "x/y", "x\\y", ""):
            with self.assertRaises(HTTPError):
                Query.dropdataset(value)
        self.assertEqual(outside.read_text(), "keep")

    def test_stream_sample_covers_file_and_preserves_rare_class(self):
        path = self.root / "sorted.csv"
        pd.DataFrame({"x": range(12000), "target": [0] * 11999 + [1]}).to_csv(path, index=False)
        frame, ids, total = sample_csv(path, 128, protect_column="target")
        self.assertEqual(total, 12000)
        self.assertEqual(len(frame), 128)
        self.assertIn(11999, ids)
        self.assertTrue((ids < 4000).any() and (ids > 8000).any())
        np.testing.assert_array_equal(ids, sample_csv(path, 128, protect_column="target")[1])
        sampled = DataMatrix(str(path), max_rows=128)
        self.assertGreater(sampled._row_ids.max(), 5000)

    def test_ingestion_keeps_source_and_aligns_projection_ids(self):
        ds = self.root / "ds"
        ds.mkdir()
        frame = pd.DataFrame({"x": range(1000), "y": np.arange(1000) * 2,
                              "label": ["common"] * 999 + ["rare"]})
        source = ds / "original.csv"
        frame.to_csv(source, index=False)
        before = source.read_bytes()
        result = ingest_csv(ds, budget=40)
        self.assertEqual(result["selected_rows"], 40)
        self.assertEqual(result["original_rows"], 1000)
        self.assertEqual(source.read_bytes(), before)
        ids = json.loads((ds / "row_ids.json").read_text())
        self.assertIn(999, ids)
        selected = pd.read_csv(ds / "working.csv")
        self.assertEqual(selected.x.tolist(), ids)
        projection = MakeProjection()
        projection.execute(dict(file="ds", target=2, featureselected=[0, 1],
                                projection="simple", instanceproximity="Euclidean"))
        for point in projection.data["points"]:
            self.assertEqual(point["x"], point["id"])
            expected = "rare" if point["id"] == 999 else "common"
            self.assertEqual(projection.data["tartegsnames"][point["t"]], expected)

    def test_decimal_targets_do_not_collapse(self):
        ds = self.root / "ds"
        ds.mkdir()
        (ds / "transform.csv").write_text("x,y,target\n1,2,0.2\n2,3,0.8\n3,4,1.1\n")
        projection = MakeProjection()
        projection.execute(dict(file="ds", target=2, featureselected=[0, 1],
                                projection="simple", instanceproximity="Euclidean"))
        self.assertEqual(projection.data["targettype"], "regression")
        self.assertEqual([point["t"] for point in projection.data["points"]], [0.2, 0.8, 1.1])

    def test_xai_train_and_permutation_rows_are_disjoint(self):
        ds = self.root / "ds"
        ds.mkdir()
        pd.DataFrame({"x": np.arange(80), "y": np.arange(80) * 2, "target": [0, 1] * 40}).to_csv(
            ds / "transform.csv", index=False)
        pipeline = XAIPipeline()
        fit = pipeline._fit_model
        captured = {}
        def fit_model(X, y, *args):
            captured["train"] = set(X[:, 0])
            return fit(X, y, *args)
        def permutation(model, X, y, plan):
            captured["test"] = set(X[:, 0])
            return np.zeros(2), np.zeros(2), "ok"
        with patch.object(pipeline, "_fit_model", side_effect=fit_model), \
             patch.object(pipeline, "_compute_permutation", side_effect=permutation):
            result = pipeline.execute(str(self.root), dict(file="ds", target=2,
                                      xai_enable_shap=False, xai_estimators=4, xai_n_jobs=1))
        self.assertTrue(captured["test"])
        self.assertFalse(captured["train"] & captured["test"])
        self.assertEqual(result["settings"]["sampling"]["evaluation_rows"], 20)
        _, tiny_test = pipeline._evaluation_split(np.array([0, 1, 0, 1]), "classification")
        self.assertEqual(len(tiny_test), 0)

    def test_invalid_archive_leaves_no_dataset_or_upload(self):
        upload = self.root / "bad.zip"
        with zipfile.ZipFile(upload, "w") as archive:
            archive.writestr("a.csv", "x,y\n1,2")
            archive.writestr("b.csv", "x,y\n3,4")
        with self.assertRaises(ValueError):
            import_upload(upload, "bad.zip", "owner")
        self.assertFalse(upload.exists())
        self.assertFalse(any(p.is_dir() for p in self.root.iterdir()))

    def test_worker_queue_has_a_limit(self):
        from vx.gff.Jobs import submit
        release = threading.Event()
        futures = []
        try:
            for _ in range(4):
                futures.append(submit(release.wait))
            with self.assertRaises(HTTPError) as error:
                submit(lambda: None)
            self.assertEqual(error.exception.status_code, 503)
        finally:
            release.set()
            for future in futures:
                future.result(timeout=3)


class HTTPFixTests(TemporaryData, AsyncHTTPTestCase):
    def get_httpserver_options(self):
        return {"max_buffer_size": 128 * 1024, "max_body_size": 10 * 1024**3}

    def get_app(self):
        for uid, admin in (("owner", 0), ("other", 0), ("admin", 1)):
            MongoDB.insert(None, "user", {"_id": uid, "email": uid, "name": uid, "adminid": admin})
        MongoDB.insert(None, "data", {"_id": "ds", "_id_user": "owner", "name": "Test",
                                     "isshare": 0, "statusopt": 0, "statusval": ""})
        ds = self.root / "ds"
        ds.mkdir()
        (ds / "original.csv").write_text("x,y,label\n1,2,0\n3,4,1\n")
        (ds / "transform.csv").write_text("x,y,label\n1,2,0\n3,4,1\n")
        return Server()

    def headers(self, user="owner", xsrf=True):
        token = "test-xsrf-token"
        cookies = "_xsrf=" + token
        if user:
            signed = create_signed_value(Settings.COOKIE_SECRET, "user", user).decode()
            cookies += "; user=" + signed
        headers = {"Cookie": cookies, "Content-Type": "application/x-www-form-urlencoded"}
        if xsrf:
            headers["X-XSRFToken"] = token
        return headers

    def query(self, kind, *, user="owner", method="POST", xsrf=True, **args):
        payload = urlencode({"data": json.dumps({"argms": dict(type=kind, **args)})})
        url = "/query" + ("?" + payload if method == "GET" else "")
        return self.fetch(url, method=method, headers=self.headers(user, xsrf),
                          body=payload if method == "POST" else None)

    def test_anonymous_and_cross_owner_operations_are_denied(self):
        with patch.object(Query, "dropdataset") as deletion:
            self.assertEqual(self.query(10, user=None, file="ds").code, 401)
            self.assertEqual(self.query(10, user="other", file="ds").code, 403)
            self.assertEqual(self.query(10, method="GET", file="ds").code, 405)
            self.assertEqual(self.query(10, xsrf=False, file="ds").code, 403)
            deletion.assert_not_called()
        self.assertEqual(self.query(20, user="other", data={"email0": "admin", "email1": "other", "adminid": 1}).code, 403)

    def test_authorized_mutation_and_shared_read(self):
        self.assertEqual(self.query(6, file="ds", newname="Renamed").code, 200)
        MongoDB.update(None, "data", {"_id": "ds"}, {"isshare": 1})
        self.assertEqual(self.query(4, method="GET", user="other", file="ds").code, 200)
        self.assertEqual(self.query(6, user="other", file="ds", newname="No").code, 403)

    def test_private_downloads_and_database_file_are_protected(self):
        self.assertEqual(self.fetch("/data/ds/original.csv").code, 401)
        self.assertEqual(self.fetch("/data/ds/original.csv", headers=self.headers("other")).code, 403)
        self.assertEqual(self.fetch("/data/ds/original.csv", headers=self.headers()).code, 200)
        self.assertEqual(self.fetch("/data/localdb.json", headers=self.headers()).code, 404)

    def test_templates_render_csrf_tokens(self):
        login = self.fetch("/login")
        self.assertEqual(login.code, 200)
        self.assertIn(b'name="_xsrf"', login.body)
        index = self.fetch("/", headers=self.headers())
        self.assertEqual(index.code, 200)
        self.assertIn(b'name="xsrf-token"', index.body)

    def test_streamed_upload_creates_representative_dataset(self):
        headers = self.headers()
        headers.update({"Content-Type": "application/octet-stream", "X-Filename": "sample.csv"})
        response = self.fetch("/upload", method="POST", headers=headers,
                              body=b"x,y,label\n1,2,cat\n3,4,dog\n")
        self.assertEqual(response.code, 200, response.body)
        result = json.loads(response.body)
        directory = dataset_path(result["file"])
        self.assertEqual(result["original_rows"], 2)
        self.assertTrue((directory / "working.csv").exists())
        self.assertFalse(list(self.root.glob(".upload-*")))

    def test_upload_requires_login_and_csrf(self):
        for user, xsrf, code in ((None, True, 401), ("owner", False, 403)):
            headers = self.headers(user, xsrf)
            headers["X-Filename"] = "sample.csv"
            response = self.fetch("/upload", method="POST", headers=headers, body=b"x,y\n1,2\n")
            self.assertEqual(response.code, code)
        self.assertFalse(list(self.root.glob(".upload-*")))

    def test_archive_download_streams_valid_zip(self):
        response = self.query(12, method="GET", file="ds")
        self.assertEqual(response.code, 200)
        with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
            self.assertEqual(archive.read("original.csv"), (self.root / "ds" / "original.csv").read_bytes())

    def test_server_binds_locally_and_uses_one_worker(self):
        with patch("vx.gff.Server.User.rootinit"), \
             patch("vx.gff.Server.tornado.httpserver.HTTPServer") as http, \
             patch("vx.gff.Server.tornado.ioloop.IOLoop.current") as loop, \
             patch.object(Server, "_available_port", return_value=8000):
            Server.execute()
            http.return_value.bind.assert_called_once_with(8000, address="localhost")
            http.return_value.start.assert_called_once_with(1)
            loop.return_value.start.assert_called_once()

    @gen_test(timeout=30)
    async def test_upload_larger_than_server_buffer_is_streamed(self):
        async def producer(write):
            await write(b"x,y,label\n")
            for _ in range(64):
                await write(b"1,2,cat\n" * 8192)
        headers = self.headers()
        headers.update({"Content-Type": "application/octet-stream", "X-Filename": "large.csv"})
        request = HTTPRequest(self.get_url("/upload"), method="POST", headers=headers,
                              body_producer=producer, request_timeout=25)
        response = await self.http_client.fetch(request)
        result = json.loads(response.body)
        self.assertEqual(result["original_rows"], 64 * 8192)
        self.assertLessEqual(result["selected_rows"], 3000)
        directory = dataset_path(result["file"])
        self.assertGreater((directory / "original.csv").stat().st_size, 128 * 1024)
        self.assertLessEqual(len(pd.read_csv(directory / "transform.csv")), 3000)

    @gen_test(timeout=10)
    async def test_xai_does_not_block_other_requests(self):
        entered, release = threading.Event(), threading.Event()
        def slow_xai(app):
            entered.set()
            release.wait(5)
            return {"status": "ok"}
        body = urlencode({"data": json.dumps({"argms": {"type": 26, "file": "ds"}})})
        request = HTTPRequest(self.get_url("/query"), method="POST", headers=self.headers(), body=body)
        with patch.object(Query, "runXAI", side_effect=slow_xai):
            pending = self.http_client.fetch(request)
            try:
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(entered.is_set())
                # This must finish while the analysis worker is still blocked.
                response = await asyncio.wait_for(self.http_client.fetch(self.get_url("/favicon.ico")), 1)
                self.assertEqual(response.code, 200)
            finally:
                release.set()
                await pending


if __name__ == "__main__":
    unittest.main()
