#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br

import tornado.ioloop
import tornado.web
import tornado.httpserver

import uuid


from vx.gff.Settings import *


class BaseHandler(tornado.web.RequestHandler):   
    def set_default_headers(self):
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("Cache-Control", "no-store")

    def get_current_user(self):
        """ if Settings.MULIUSER == 0:
            return "localuser"
        elif Settings.MULIUSER == 1:
            return self.get_secure_cookie("user") """
        return self.get_secure_cookie("user")
    
    def get_current_email(self):
        """ 
        if Settings.MULIUSER == 0:
            return "localuser"
        elif Settings.MULIUSER == 1:
            return self.get_secure_cookie("email") """
        return self.get_secure_cookie("email")

    def get_current_adminid(self):
        """ 
        if Settings.MULIUSER == 0:
            return "localuser"
        elif Settings.MULIUSER == 1:
            return self.get_secure_cookie("adminid") """
        return self.get_secure_cookie("adminid")

