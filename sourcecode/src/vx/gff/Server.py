#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br

import tornado.ioloop
import tornado.web
import tornado.httpserver
import datetime
import platform
import socket
from multiprocessing import cpu_count



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


class Server(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", Index),
            (r"/login", Login),
            (r"/logout", Logout),
            (r"/query", Query),
            (r"/favicon\.ico", FaviconHandler, {"path": Settings.STATIC_PATH + "/img"}),

            (r"/lib/(.*)",tornado.web.StaticFileHandler, {"path": Settings.STATIC_PATH+"/lib"},),
            (r"/img/(.*)",tornado.web.StaticFileHandler, {"path": Settings.STATIC_PATH+"/img"},),
            (r"/data/(.*)",tornado.web.StaticFileHandler, {"path": Settings.DATA_PATH},),
            # (r"/data/(.*)",tornado.web.StaticFileHandler, {"path": "./static/data"},),
            # (r"/img/(.*)",tornado.web.StaticFileHandler, {"path": "./static/img"},)
        ]
        settings = {
            "template_path":Settings.TEMPLATE_PATH,
            "static_path":Settings.STATIC_PATH,
            "debug":Settings.DEBUG,
            "cookie_secret": Settings.COOKIE_SECRET,
        }
        tornado.web.Application.__init__(self, handlers, **settings)
        
    @staticmethod
    def execute():

        User.rootinit();

        server = tornado.httpserver.HTTPServer(Server())
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
        server.bind(Settings.PORT)
        processes = 1 if platform.system() == "Windows" else max(1, cpu_count())
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



        
#if __name__ == "__main__":
#    print ('The server is ready: http://'+Settings.HOST+':'+str(Settings.PORT)+'/')
#    server = tornado.httpserver.HTTPServer(Server())
#    server.bind(Settings.PORT)
#    server.start(cpu_count())
##    tornado.ioloop.IOLoop.current().start()
#    tornado.ioloop.IOLoop.instance().start()






