"""Authorization and path validation shared by query and download routes."""
import re
from pathlib import Path

from tornado.web import HTTPError
from vx.gff.Settings import Settings
from vx.com.py.database.MongoDB import MongoDB


def dataset_path(dataset_id):
    if not isinstance(dataset_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", dataset_id):
        raise HTTPError(400, reason="Invalid dataset ID")
    root = Path(Settings.DATA_PATH).resolve()
    path = (root / dataset_id).resolve()
    if path.parent != root:
        raise HTTPError(400, reason="Dataset path escapes its directory")
    return path


def current_account(user_id):
    if not user_id:
        raise HTTPError(401, reason="Please log in")
    if isinstance(user_id, bytes):
        user_id = user_id.decode("utf-8")
    users = MongoDB.find(None, "user", {"_id": user_id})
    if len(users) != 1:
        raise HTTPError(401, reason="Please log in again")
    return users[0]


def authorize_dataset(user, dataset_id, write=False):
    dataset_path(dataset_id)
    rows = MongoDB.find(None, "data", {"_id": dataset_id})
    if not rows:
        raise HTTPError(404, reason="Dataset not found")
    row = rows[0]
    owner = str(row.get("_id_user")) == str(user["_id"])
    if not (owner or user.get("adminid") == 1 or (not write and row.get("isshare") == 1)):
        raise HTTPError(403, reason="Dataset access denied")
    return row
