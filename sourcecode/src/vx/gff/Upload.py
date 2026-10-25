"""Stream uploads to disk before any CSV analysis starts."""
import asyncio
from datetime import datetime
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote
import uuid
import zipfile

from tornado.web import HTTPError, stream_request_body
from vx.gff.BaseHandler import BaseHandler
from vx.gff.Security import current_account, dataset_path
from vx.gff.Settings import Settings
from vx.gff.Ingestion import ingest_csv
from vx.gff.Jobs import submit
from vx.com.py.database.MongoDB import MongoDB

MAX_UPLOAD_BYTES = 10 * 1024**3


def import_upload(path, filename, user_id):
    dataset_id = uuid.uuid4().hex
    directory = dataset_path(dataset_id)
    directory.mkdir()
    try:
        destination = directory / "original.csv"
        if filename.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as archive:
                entries = [entry for entry in archive.infolist() if not entry.is_dir()]
                if len(entries) != 1 or not entries[0].filename.lower().endswith(".csv"):
                    raise ValueError("ZIP must contain exactly one CSV file")
                if entries[0].file_size > MAX_UPLOAD_BYTES:
                    raise ValueError("Uncompressed CSV exceeds the 10 GiB upload limit")
                with archive.open(entries[0]) as source, destination.open("wb") as output:
                    copied = 0
                    while block := source.read(1024 * 1024):
                        copied += len(block)
                        if copied > MAX_UPLOAD_BYTES:
                            raise ValueError("Uncompressed CSV exceeds the upload limit")
                        output.write(block)
        else:
            shutil.copyfile(path, destination)
        metadata = ingest_csv(directory)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        MongoDB.insert(None, "data", {
            "_id": dataset_id, "_id_user": user_id, "name": Path(filename).stem,
            "type": ".csv", "fenames": [], "featurecheck": [],
            "configfeature": {}, "configinstance": {},
            "typefeature": "", "typeinstance": "", "layoutfeature": "", "layoutinstance": "",
            "versionfeature": Settings.VERSION, "versioninstance": Settings.VERSION,
            "datecreate": now, "dateupdate": now, "hasupdate": 0, "isshare": 0,
            "statusopt": 0, "statusval": "", "sampling": metadata,
        })
        return dict(metadata, file=dataset_id)
    except BaseException:
        # directory is a newly created, validated UUID child; never a request path.
        shutil.rmtree(directory)
        raise
    finally:
        Path(path).unlink(missing_ok=True)


@stream_request_body
class UploadHandler(BaseHandler):
    def initialize(self):
        self.upload = None
        self.upload_path = None
        self.worker_owns_file = False
        self.received = 0

    def prepare(self):
        if self.request.method != "POST":
            raise HTTPError(405)
        self.account = current_account(self.current_user)
        self.filename = unquote(self.request.headers.get("X-Filename", ""))
        if not self.filename.lower().endswith((".csv", ".zip")):
            raise HTTPError(400, reason="Upload a CSV or ZIP file")
        Path(Settings.DATA_PATH).mkdir(parents=True, exist_ok=True)
        self.upload = tempfile.NamedTemporaryFile(prefix=".upload-", dir=Settings.DATA_PATH, delete=False)
        self.upload_path = self.upload.name

    def data_received(self, chunk):
        self.received += len(chunk)
        if self.received > MAX_UPLOAD_BYTES:
            self._cleanup()
            raise HTTPError(413, reason="Upload exceeds 10 GiB")
        self.upload.write(chunk)

    async def post(self):
        self.upload.close()
        try:
            future = submit(import_upload, self.upload_path, self.filename, str(self.account["_id"]))
            self.worker_owns_file = True
            result = await asyncio.shield(asyncio.wrap_future(future))
            self.write(result)
        except (ValueError, zipfile.BadZipFile) as exc:
            raise HTTPError(400, reason=str(exc))
        finally:
            self._cleanup()

    def _cleanup(self):
        if self.upload is not None:
            self.upload.close()
        if self.upload_path and not self.worker_owns_file:
            Path(self.upload_path).unlink(missing_ok=True)

    def on_connection_close(self):
        self._cleanup()

    def on_finish(self):
        self._cleanup()
