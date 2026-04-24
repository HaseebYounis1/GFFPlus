#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
import json
import threading
import uuid
from pathlib import Path


def ObjectId(value=None):
    if value is None:
        return uuid.uuid4().hex
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


class MongoDB:
    """Small JSON-backed replacement for the previous MongoDB adapter.

    The rest of the app historically imports `MongoDB`, so this class keeps the
    old API shape while storing documents locally in data/gff/localdb.json.
    """

    DBACCESS = 0
    _lock = threading.RLock()
    _root = Path(__file__).resolve().parents[6]
    _dbfile = _root / "data" / "gff" / "localdb.json"

    @staticmethod
    def _empty():
        return {"user": [], "data": []}

    @staticmethod
    def _read():
        MongoDB._dbfile.parent.mkdir(parents=True, exist_ok=True)
        if not MongoDB._dbfile.exists():
            return MongoDB._empty()
        try:
            with MongoDB._dbfile.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
        except json.JSONDecodeError:
            data = MongoDB._empty()
        for collection in ("user", "data"):
            data.setdefault(collection, [])
        return data

    @staticmethod
    def _write(data):
        MongoDB._dbfile.parent.mkdir(parents=True, exist_ok=True)
        tmp = MongoDB._dbfile.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        tmp.replace(MongoDB._dbfile)

    @staticmethod
    def _match_value(document, key, value):
        return str(document.get(key)) == str(value)

    @staticmethod
    def _matches(document, query):
        if not query:
            return True
        for key, value in query.items():
            if key == "$or":
                return any(MongoDB._matches(document, option) for option in value)
            if not MongoDB._match_value(document, key, value):
                return False
        return True

    @staticmethod
    def find(arg, namecollection, query):
        with MongoDB._lock:
            data = MongoDB._read()
            rows = data.setdefault(namecollection, [])
            return [
                copy.deepcopy(row)
                for row in rows
                if MongoDB._matches(row, query)
            ]

    @staticmethod
    def aggregate(arg, namecollection, query):
        with MongoDB._lock:
            rows = MongoDB.find(arg, namecollection, {})
            for stage in query:
                if "$match" in stage:
                    rows = [row for row in rows if MongoDB._matches(row, stage["$match"])]
                elif "$sort" in stage:
                    key, direction = next(iter(stage["$sort"].items()))
                    rows.sort(key=lambda row: row.get(key, ""), reverse=direction < 0)
                elif "$lookup" in stage:
                    spec = stage["$lookup"]
                    foreign = MongoDB.find(arg, spec["from"], {})
                    for row in rows:
                        row[spec["as"]] = [
                            frow
                            for frow in foreign
                            if str(frow.get(spec["foreignField"])) == str(row.get(spec["localField"]))
                        ]
                elif "$project" in stage:
                    fields = {key for key, keep in stage["$project"].items() if keep and "." not in key}
                    rows = [
                        {key: value for key, value in row.items() if key in fields or key == "usersUnits"}
                        for row in rows
                    ]
            return rows

    @staticmethod
    def insert(arg, namecollection, query):
        with MongoDB._lock:
            data = MongoDB._read()
            rows = data.setdefault(namecollection, [])
            row = copy.deepcopy(query)
            row["_id"] = str(row.get("_id") or ObjectId())
            rows.append(row)
            MongoDB._write(data)
            return row["_id"]

    @staticmethod
    def delete(arg, namecollection, query):
        with MongoDB._lock:
            data = MongoDB._read()
            rows = data.setdefault(namecollection, [])
            for index, row in enumerate(rows):
                if MongoDB._matches(row, query):
                    del rows[index]
                    MongoDB._write(data)
                    return True
            return False

    @staticmethod
    def update(arg, namecollection, queryid, queryupdate):
        with MongoDB._lock:
            data = MongoDB._read()
            rows = data.setdefault(namecollection, [])
            changed = 0
            for row in rows:
                if MongoDB._matches(row, queryid):
                    row.update(copy.deepcopy(queryupdate))
                    changed += 1
            if changed:
                MongoDB._write(data)
            return changed
