import sys
import unittest
from shutil import rmtree
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sourcecode" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vx.com.py.database.MongoDB import MongoDB
from vx.gff.MakeProjection import MakeProjection
from vx.gff.Query import DBFile, Query
from vx.gff.Settings import Settings


class RuntimeSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_path = ROOT / "data" / "gff" / f"__test_runtime_smoke_{uuid4().hex}"
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        self.old_data_path = Settings.DATA_PATH
        self.old_dbfile = MongoDB._dbfile

        Settings.DATA_PATH = str(self.tmp_path) + "/"
        MongoDB._dbfile = self.tmp_path / "localdb.json"
        Path(Settings.DATA_PATH).mkdir(parents=True, exist_ok=True)

        self.dataset_id = "dataset_smoke"
        dataset_dir = Path(Settings.DATA_PATH) / self.dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)
        csv_text = "\n".join(
            [
                "a,b,c,target",
                "1.0,2.0,3.0,0",
                "2.0,1.0,4.0,1",
                "3.0,4.0,1.0,0",
                "4.0,3.0,2.0,1",
            ]
        )
        (dataset_dir / "transform.csv").write_text(csv_text, encoding="utf-8")
        (dataset_dir / "original.csv").write_text(csv_text, encoding="utf-8")

    def tearDown(self):
        Settings.DATA_PATH = self.old_data_path
        MongoDB._dbfile = self.old_dbfile
        rmtree(self.tmp_path, ignore_errors=True)

    def _projection_args(self, projection="simple"):
        return {
            "file": self.dataset_id,
            "projection": projection,
            "instanceproximity": "Euclidean",
            "featureselected": [0, 1],
            "target": 3,
            "isfeature": 0,
        }

    def test_pair_projection_outputs_one_point_per_row(self):
        projection = MakeProjection()
        projection.execute(self._projection_args("simple"))

        self.assertEqual(len(projection.data["points"]), 4)
        self.assertEqual(projection.data["points"][0]["x"], 1.0)
        self.assertEqual(projection.data["points"][0]["y"], 2.0)

    def test_tsne_projection_outputs_one_point_per_row(self):
        projection = MakeProjection()
        projection.execute(self._projection_args("tsne"))

        self.assertEqual(len(projection.data["points"]), 4)
        self.assertIn("x", projection.data["points"][0])
        self.assertIn("y", projection.data["points"][0])

    def test_dbfile_missing_layout_returns_empty_dict(self):
        missing = Path(Settings.DATA_PATH) / self.dataset_id / "missing.obj"
        self.assertEqual(DBFile.openFile(str(missing)), {})

    def test_status_can_transition_from_working_to_ready(self):
        MongoDB.insert(
            None,
            "data",
            {
                "_id": self.dataset_id,
                "name": "Smoke",
                "statusopt": 0,
                "statusval": "",
            },
        )
        app = SimpleNamespace(argms={"file": self.dataset_id, "statusval": "working"})

        Query.setStatus(app, 1)
        self.assertEqual(Query.getStatus(app)["statusopt"], 1)

        Query.setStatus(SimpleNamespace(argms={"file": self.dataset_id}), 0)
        status = Query.getStatus(app)
        self.assertEqual(status["statusopt"], 0)
        self.assertEqual(status["statusval"], "")


if __name__ == "__main__":
    unittest.main()
