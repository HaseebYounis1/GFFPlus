#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br

import tornado.ioloop
import tornado.web
import tornado.httpserver
import socket
import secrets
from pathlib import Path
from vx.gff.Security import current_account, authorize_dataset, dataset_path



from vx.com.py.database.MongoDB import *

#from ipy.dataio import *
#from ipy.db import *

from vx.gff.Settings import *
from vx.gff.BaseHandler import *
from vx.gff.Pages import *
from vx.gff.Query import *

MongoDB.DBACCESS = Settings.DBACCESS

class FaviconHandler(tornado.web.StaticFileHandler):
    """Serve icon.png directly when the browser requests /favicon.ico."""
    async def get(self, path=None, include_body=True):
        return await super().get("icon.png", include_body)


class DatasetDownloadHandler(tornado.web.StaticFileHandler):
    async def get(self, path, include_body=True):
        user = current_account(self.get_secure_cookie("user"))
        parts = path.split("/")
        if len(parts) != 2 or parts[1] not in {
            "sample.csv", "transform.csv", "original.csv", "working.csv", "row_ids.json", "sample_row_ids.json"
        }:
            raise tornado.web.HTTPError(404)
        authorize_dataset(user, parts[0])
        directory = dataset_path(parts[0])
        if (directory / parts[1]).resolve().parent != directory:
            raise tornado.web.HTTPError(403)
        self.set_header("Cache-Control", "private, no-store")
        return await super().get(path, include_body)


class Server(tornado.web.Application):
    def __init__(self):
        if Settings.COOKIE_SECRET is None:
            secret_path = Path(Settings.DATA_PATH) / ".session-secret"
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with secret_path.open("x", encoding="ascii") as secret_file:
                    secret_file.write(secrets.token_hex(32))
                secret_path.chmod(0o600)
            except FileExistsError:
                pass
            Settings.COOKIE_SECRET = secret_path.read_text(encoding="ascii").strip()
            if len(Settings.COOKIE_SECRET) < 32:
                raise RuntimeError("Invalid session secret file")
        from vx.gff.Upload import UploadHandler
        handlers = [
            (r"/", Index),
            (r"/login", Login),
            (r"/logout", Logout),
            (r"/query", Query),
            (r"/upload", UploadHandler),
            (r"/favicon\.ico", FaviconHandler, {"path": Settings.STATIC_PATH + "/img"}),

            (r"/lib/(.*)",tornado.web.StaticFileHandler, {"path": Settings.STATIC_PATH+"/lib"},),
            (r"/img/(.*)",tornado.web.StaticFileHandler, {"path": Settings.STATIC_PATH+"/img"},),
            (r"/data/(.*)", DatasetDownloadHandler, {"path": Settings.DATA_PATH},),
            # (r"/data/(.*)", DatasetDownloadHandler, {"path": "./static/data"},),
            # (r"/img/(.*)",tornado.web.StaticFileHandler, {"path": "./static/img"},)
        ]
        settings = {
            "template_path":Settings.TEMPLATE_PATH,
            "static_path":Settings.STATIC_PATH,
            "debug":Settings.DEBUG,
            "cookie_secret": Settings.COOKIE_SECRET,
            "xsrf_cookies": True,
        }
        tornado.web.Application.__init__(self, handlers, **settings)
        
    @staticmethod
    def execute():

        User.rootinit();

        server = tornado.httpserver.HTTPServer(Server(), max_buffer_size=2 * 1024 * 1024,
                                                     max_body_size=10 * 1024**3)
        requested_port = Settings.PORT
        Settings.PORT = Server._available_port(Settings.HOST, requested_port)
        Settings.PATHROOT = "http://{}:{}/".format(Settings.HOST, Settings.PORT)
        if Settings.PORT != requested_port:
            print(
                "Port {} is already in use; starting GFF on port {} instead.".format(
                    requested_port, Settings.PORT
                )
            )
        print ('The server is ready: http://'+Settings.HOST+':'+str(Settings.PORT)+'/')
        server.bind(Settings.PORT, address=Settings.HOST)
        processes = 1  # The JSON database lock is shared by threads, not processes.
        server.start(processes)
        tornado.ioloop.IOLoop.current().start()

    @staticmethod
    def _available_port(host, preferred, attempts=50):
        for port in range(int(preferred), int(preferred) + attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind((host, port))
                    return port
                except OSError:
                    continue
        raise OSError(
            "No free port found from {} to {}".format(
                preferred, int(preferred) + attempts - 1
            )
        )
