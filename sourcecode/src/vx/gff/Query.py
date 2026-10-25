#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br

import sys
sys.setrecursionlimit(100000)


import tornado
import tornado.ioloop
import tornado.web
import tornado.httpserver

import threading
import asyncio
import tempfile
from pathlib import Path
from vx.gff.Security import dataset_path, current_account, authorize_dataset
from vx.gff.Jobs import submit
from vx.gff.Ingestion import source_ids
from vx.com.py.sampling.CSVSample import sample_csv, read_rows


import json as ujson
import glob
import os

import pandas as pd
import numpy as np
import os.path
import math

import bcrypt
import uuid

import zipfile
import io
import shutil
from io import BytesIO
from datetime import datetime, timedelta
from vx.gff.Settings import *
from vx.gff.BaseHandler import *
from vx.gff.MakeProjection import *
from vx.gff.XAI import XAIPipeline
from vx.gff.graphtree.graphtree_pure import *
from vx.gff.User import *


from vx.com.py.matrix.MData import *
from vx.com.py.database.MongoDB import *


class Query(BaseHandler):
    STALE_WORKING_TIMEOUT_SECONDS = 15 * 60

    READ_TYPES = {2, 4, 5, 12, 17, 18, 22, 24}
    _xai_running = set()

    def _request(self):
        user = current_account(self.current_user)
        try:
            app = DataTransfer(self.get_argument("data"))
            kind = app.argms["type"]
            if not isinstance(kind, int) or kind not in set(range(27)) - {3, 14, 15, 16}:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise tornado.web.HTTPError(400, reason="Invalid query")
        if self.request.method == "GET" and kind not in self.READ_TYPES:
            raise tornado.web.HTTPError(405, reason="Use POST for changes")
        if kind in {18, 19, 20} and user.get("adminid") != 1:
            raise tornado.web.HTTPError(403, reason="Administrator access required")
        if kind not in {2, 11, 18, 19, 20}:
            write = kind not in self.READ_TYPES | {7, 25}
            record = authorize_dataset(user, app.argms.get("file"), write=write)
            if write and kind not in {0, 1} and (
                app.argms["file"] in self._xai_running or record.get("statusopt") == 1
            ):
                raise tornado.web.HTTPError(409, reason="Wait for this dataset's current analysis to finish")
            if write and app.argms["file"] in self._xai_running:
                raise tornado.web.HTTPError(409, reason="Wait for this dataset's XAI analysis to finish")
        if kind == 20:
            app.argms["data"]["email0"] = user["email"]
        return app

    async def get(self):
        app = self._request()
        if app.argms["type"] == 12:
            await self._download(app)
        else:
            self._dispatch(app)

    async def post(self):
        app = self._request()
        kind = app.argms["type"]
        if kind == 12:
            await self._download(app)
            return
        workers = {7: Query.clonedataset, 13: Query.silhouette, 21: Query.makeInstancesLabels, 25: Query.ensureSampleCsv}
        if kind in workers:
            args = (app, self.current_user) if kind == 7 else (app,)
            self.write(ujson.dumps(await asyncio.wrap_future(submit(workers[kind], *args))))
            return
        if kind != 26:
            self._dispatch(app)
            return
        dataset = app.argms["file"]
        if dataset in self._xai_running:
            raise tornado.web.HTTPError(409, reason="XAI is already running for this dataset")
        self._xai_running.add(dataset)
        try:
            self.write(await asyncio.wrap_future(submit(Query.runXAI, app)))
        finally:
            self._xai_running.discard(dataset)

    def _dispatch(self, app):
        obj = ""
        
        #try:
        if True:    

            if app.argms["type"]==0:
                #print("app.argms", app.argms)
                if app.argms["algorithm"]=="mst" or app.argms["algorithm"]=="nj":
                    # 0:ok; 1:working; 2:error
                    # lock dataset
                    status = Query.getStatus(app)
                    if status["statusopt"] in (0, 2):
                        Query.setStatus(app, 1);
                        try:
                            submit(Query.processFeatures, app)
                        except Exception:
                            Query.setStatus(app, 0)
                            raise
                        status = Query.getStatus(app)

                    obj = ujson.dumps(status);

            elif app.argms["type"]==1:
                # 0:ok; 1:working; 2:error
                # lock dataset
                status = Query.getStatus(app)
                if status["statusopt"] in (0, 2) and not Query.isprojectioncurrent(app):
                    Query.setStatus(app, 1);
                    try:
                        submit(Query.processInstances, app)
                    except Exception:
                        Query.setStatus(app, 0)
                        raise
                    status = Query.getStatus(app)
                
                obj = ujson.dumps(status);

            elif app.argms["type"]==2:
                obj = ujson.dumps(Query.listdatasets(self.current_user));

                """
                elif app.argms["type"]==2:
                    obj = ujson.dumps(Query.loadatributenames(app));
                """

            elif app.argms["type"]==4:
                obj = ujson.dumps(Query.getdatasetname(app));

            elif app.argms["type"]==5:
                obj = ujson.dumps(Query.opencsv(app));

            elif app.argms["type"]==6:
                obj = ujson.dumps(Query.updatedatasetname(app));
            elif app.argms["type"]==7:
                obj = ujson.dumps(Query.clonedataset(app, self.current_user));
            elif app.argms["type"]==8:
                obj = ujson.dumps(Query.sharedataset(app));
            elif app.argms["type"]==9:
                obj = ujson.dumps(Query.unsharedataset(app));
            elif app.argms["type"]==10:
                obj = ujson.dumps(Query.dropdataset(app.argms["file"]));

            elif app.argms["type"]==11:
                obj = ujson.dumps(User.changePassword(app, self.current_user));


            elif app.argms["type"]==13:
                obj = ujson.dumps(Query.silhouette(app));

                #elif app.argms["type"]==14:
                #    obj = Query.openfeature(app)
                #    obj = ujson.dumps(obj);
                #    
                #elif app.argms["type"]==15:
                #    obj = Query.openinstance(app)
                #    obj = ujson.dumps(obj);

            #elif app.argms["type"]==16:
            #    obj = Query.export2dproj(app, self);

            elif app.argms["type"]==17:
                obj = Query.exportfeat2datafile(app, self);

            elif app.argms["type"]==18:
                obj = User.getUsers();
                obj = ujson.dumps(obj);

            elif app.argms["type"]==19:
                obj = User.newUser(app.argms["data"]);
                obj = ujson.dumps(obj);

            elif app.argms["type"]==20:
                obj = User.setAdmin(app.argms["data"]);
                obj = ujson.dumps(obj);

            elif app.argms["type"]==21:
                obj = ujson.dumps(Query.makeInstancesLabels(app));

            elif app.argms["type"]==22: 
                obj = ujson.dumps(Query.getUnselecteFeatures(app)); 

            elif app.argms["type"]==23: 
                status = Query.getStatus(app)
                #if status["statusopt"]==0: """
                status = Query.setListFeaturesChecks(app); 
                
                obj = ujson.dumps(status);
                
            elif app.argms["type"]==24:
                obj = ujson.dumps(Query.opendataset(app));

            elif app.argms["type"]==25:
                obj = ujson.dumps(Query.ensureSampleCsv(app));


        #except Exception as e:
        #    print("Error: " + str(e))

        
        # self.write(ujson.dumps(obj))
        self.write(obj)
        self.finish()
        #self.write(obj)


    @staticmethod
    def converid(idin):
        """ 
        #idin = file
        if Settings.MULIUSER == 1:
            #idin = idin.decode("utf-8");
            idin = ObjectId(idin) """
        idin = ObjectId(idin)
        return idin

    @staticmethod
    def processFeatures(app):
        try:
            #Query.setStatus(app, 0)
            ufe = Query.getUnselecteFeatures(app)
            g = Graph()
            g.make_graph(Settings.DATA_PATH, ufe, app.argms)

            app.argms["nodes"] = g.data["graph"]["nodes"];
            app.argms["ranking"] = g.data["ranking"];
            app.argms["rankingmin"] = g.data["rankingmin"];
            app.argms["rankingmax"] = g.data["rankingmax"];

            Query.savegraph(app,g.data);
            Query.setStatus(app, 0);
         
        except Exception as e:
            # error dataset
            print("error in save graph", e)
            Query.setStatus(app, 2);
        
        #Query.setStatus(app, 0)


    @staticmethod
    def processInstances(app):
        try:
            dap = MakeProjection()
            dap.execute(app.argms);
            Query.saveprojection(app,dap.data);
            Query.setStatus(app, 0);
        except Exception as e:
            # error dataset
            print("error save projection", e)
            Query.setStatus(app, 2);

    @staticmethod
    def isprojectioncurrent(app):
        if "file" not in app.argms or app.argms["file"] == "":
            return False

        idin = Query.converid(app.argms["file"])
        filen = Settings.DATA_PATH+str(idin)+"/instance.obj"
        if not os.path.exists(filen):
            return False
        if DBFile.openFile(filen).get("targettype") not in ("classification", "regression"):
            return False

        keys = [
            "projection",
            "instanceproximity",
            "target",
            "intarget",
            "featureselected",
            "idinstanceslabels",
            "submodular_size",
            "targettype",
        ]
        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        for row in re:
            config = row.get("configinstance", {})
            for key in keys:
                if str(config.get(key, "")) != str(app.argms.get(key, "")):
                    return False
            return True
        return False




    @staticmethod
    def makedir(ndir):
        if not os.path.exists(ndir):
            os.makedirs(ndir, mode=0o777)

    # static query methods
    @staticmethod
    def listfiles(outdir, ext):
        dires = []
        fileso = []
        for name in os.listdir(outdir):
            dires.append(os.path.join(outdir, name))
            if name.endswith(ext):
#                fileso.append(str(os.path.join(outdir, str(name))))
                fileso.append({"name":str(name)})
        return fileso

    @staticmethod
    def listdirs(folder):
        if os.path.exists(folder):
            # listd =  [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]
            # for d in listd:
            #     if os.path.isdir(os.path.join(folder, d)):
            return [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]
        else:
            return []

    @staticmethod
    def listdatasets(iduser):
        rs = []
        """         
        if Settings.MULIUSER == 0:
            dir_list = Query.listdirs(Settings.DATA_PATH)
            for di in dir_list:
                ro = DBX.find(DBS.DBGFF, "data",{"_id": di})
                if len(ro)>0:
                    for row in ro:
                        #if len(row)>0 and "_id" in row:
                        if len(row)>0:
                            rs.append( {"_id":row["_id"], 
                                "_id_user": "localuser",
                                "owner":"localuser",
                                "name":row["name"],
                                "dateupdate":row["dateupdate"],
                                "isshare":row["isshare"],
                                } ) 

        elif Settings.MULIUSER == 1:"""

        iduser = iduser.decode("utf-8") if isinstance(iduser, bytes) else str(iduser)
        datasets = [
            row for row in DBX.find(DBS.DBGFF, "data", {})
            if str(row.get("_id_user")) == str(iduser) or row.get("isshare") == 1
        ]
        users = {str(row["_id"]): row for row in DBX.find(DBS.DBGFF, "user", {})}
        datasets.sort(key=lambda row: row.get("dateupdate", ""), reverse=True)

        for row in datasets:
            owner = users.get(str(row.get("_id_user")), {}).get("name", "localuser")
            rs.append( {"_id":str(row["_id"]), 
                            "_id_user_query": str(iduser),
                            "_id_user": str(row["_id_user"]),
                            "owner":owner,
                            "name":row["name"],
                            "dateupdate":row["dateupdate"],
                            "isshare":row["isshare"],
                            } )
        return rs

    @staticmethod
    def loadatributenames(app):
        idin = Query.converid(app.argms["file"])
        columns = []
        da = list(DBX.find(DBS.DBGFF, "data", {"_id": idin}))
        for d in da:
            if "fenames" in d and len(d["fenames"]) > 0:
                columns = d["fenames"]
            else:
                with open(Settings.DATA_PATH + app.argms["file"] + "/transform.csv",
                          encoding="utf-8-sig") as f:
                    columns = [x.strip() for x in f.readline().split(",")]
                DBX.update(DBS.DBGFF, "data", {"_id": idin}, {"fenames": columns})
        return columns

    @staticmethod
    def getdatasetname(app):
        idin = Query.converid(app.argms["file"])

        re = ""
        da = list(DBX.find(DBS.DBGFF, "data", {"_id": idin}))
        for d in da:
            re = d["name"];

        return re

    @staticmethod
    def setListFeaturesChecks(app):
        idin = Query.converid(app.argms["file"])
        feidlist = app.argms["data"]
           
        da = list(DBX.find(DBS.DBGFF, "data", {"_id": idin}))
        for d in da:
            featurecheck = []
            if "featurecheck" in d and len(d["featurecheck"])>0:
                featurecheck = d["featurecheck"]
            else:
                cols = Query.loadatributenames(app)
                if len(cols)>0:
                    featurecheck = [1 for i in range(len(cols))]

            for i, v in feidlist:
                featurecheck[i] = v
            
            DBX.update( DBS.DBGFF,"data",
                        {'_id': idin},
                        {'featurecheck':featurecheck})

        rs = {"statusopt":0, "statusval":"", "response":{}}
        return rs

    @staticmethod
    def getUnselecteFeatures(app):
        result = []
        idin = Query.converid(app.argms["file"])

        da = list(DBX.find(DBS.DBGFF, "data", {"_id": idin}))
        for d in da:
            if "featurecheck" in d and len(d["featurecheck"])>0:
                featurecheck = d["featurecheck"]
                for i in range(len(featurecheck)):
                    if featurecheck[i] == 0:
                        result.append(i);
            else:
                cols = Query.loadatributenames(app)
                if len(cols)>0:
                    featurecheck = [1 for i in range(len(cols))]
                    DBX.update( DBS.DBGFF,"data",
                                {'_id': idin},
                                {'featurecheck':featurecheck})

        return result;

    @staticmethod
    def ensureSampleCsv(app):
        directory = dataset_path(app.argms["file"])
        sample_path = directory / "sample.csv"
        ids_path = directory / "sample_row_ids.json"
        if not sample_path.exists() or not ids_path.exists():
            frame, local_ids, _ = sample_csv(directory / "transform.csv", 5000)
            frame.to_csv(sample_path, index=False)
            ids_path.write_text(ujson.dumps(source_ids(directory, local_ids).tolist()), encoding="utf-8")
        return {"ok": 1}

    @staticmethod
    def runXAI(app):
        """Run local CPU-first feature attribution and persist xai.obj."""
        try:
            feature_names = Query.loadatributenames(app)
            unselected = Query.getUnselecteFeatures(app)
            result = XAIPipeline().execute(
                Settings.DATA_PATH,
                app.argms,
                feature_names=feature_names,
                unselectedfeids=unselected,
            )
            result["created"] = Query.now()
            Query.saveXAI(app, result)
            return result
        except Exception as e:
            print("error running xai", e)
            return {
                "status": "error",
                "message": str(e),
                "target": {
                    "id": int(app.argms.get("target", -1))
                    if str(app.argms.get("target", "")).lstrip("-").isdigit()
                    else -1,
                    "name": "",
                    "type": "",
                },
                "model": {},
                "features": [],
                "importance": [],
                "permutation": {"values": [], "values_norm": [], "status": "error"},
                "shap": {
                    "available": False,
                    "reason": "not computed",
                    "values": [],
                    "values_norm": [],
                    "summary": [],
                    "similarity": {"available": False, "links": []},
                },
                "settings": {"local_only": True},
            }

    @staticmethod
    def opencsv(app):
        filefe = Settings.DATA_PATH+app.argms["file"]+"/transform.csv"
        pd.read_csv(filefe, nrows=1)

        return {"response":1};

    @staticmethod
    def updatedatasetname(app):
        idin = Query.converid(app.argms["file"])

        nname = app.argms["newname"]
        DBX.update( DBS.DBGFF,"data", {'_id': idin}, {'name':nname})

        return {"response":1};

    @staticmethod
    def clonedataset(app, iduser):
        idin = Query.converid(app.argms["file"])
        """ 
        if Settings.MULIUSER == 1:
            iduser = iduser.decode("utf-8") """
        iduser = iduser.decode("utf-8") if isinstance(iduser, bytes) else str(iduser)
        iduser = Query.converid(iduser)
        
        dat = list(DBX.find(DBS.DBGFF,"data", {"_id": idin}))
        datc = {}
        for row in dat:
            for k, v in row.items():
                if k != "_id":
                    datc[k] = v

        dt_string = Query.now();
        datc["name"] += " (clone)";
        datc["datecreate"] = dt_string;
        datc["dateupdate"] = dt_string;
        datc["_id_user"] = iduser;
        #datc["_id"] = DBFile.uid();

        idinsert = DBX.insert(DBS.DBGFF, "data", datc)
        idinsert = str(idinsert)

        ndir = Settings.DATA_PATH+idinsert
        Query.makedir(ndir)
        srcdir = os.path.join(Settings.DATA_PATH, str(idin))
        for name in os.listdir(srcdir):
            if name == "data.obj":
                continue
            source = os.path.join(srcdir, name)
            target = os.path.join(ndir, name)
            if os.path.isdir(source):
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target)

        return {"response":1};

    @staticmethod
    def _make_download(dataset_id):
        directory = dataset_path(dataset_id)
        output = tempfile.TemporaryFile()
        try:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in directory.iterdir():
                    if path.is_file() and not path.is_symlink() and not path.name.startswith("."):
                        archive.write(path, path.name)
            output.seek(0)
            return output
        except BaseException:
            output.close()
            raise

    async def _download(self, app):
        output = await asyncio.wrap_future(submit(Query._make_download, app.argms["file"]))
        try:
            self.set_header("Content-Type", "application/zip")
            self.set_header("Content-Disposition", 'attachment; filename="dataset.zip"')
            while block := output.read(1024 * 1024):
                self.write(block)
                await self.flush()
        finally:
            output.close()

    @staticmethod
    def setStatus(app, k):
        if "file" in app.argms and app.argms["file"]!="":
            idin = Query.converid(app.argms["file"])
            statusval = app.argms.get("statusval", "")
            statusdate = Query.now()
            if k == 0:
                statusval = ""
                statusdate = ""
            
            DBX.update(DBS.DBGFF, "data",
                                    {'_id': idin},
                                    {
                                        'statusopt': k,
                                        'statusval': statusval,
                                        'statusdate': statusdate,
                                    })

    @staticmethod
    def getStatus(app):
        idin = Query.converid(app.argms["file"])
        status = {"statusopt":0, "statusval":"", "response":{}}

        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        for r in re:
            if not "statusopt" in r or  not "statusval" in r:
                DBX.update(DBS.DBGFF, "data",
                                        {'_id': idin},
                                        {'statusopt':0, 'statusval':'', 'statusdate':''})
            else:
                status["statusopt"] = r["statusopt"];
                status["statusval"] = r["statusval"];
                if Query.isStaleWorkingStatus(r):
                    status["statusopt"] = 0
                    status["statusval"] = ""
                    DBX.update(DBS.DBGFF, "data",
                               {'_id': idin},
                               {'statusopt': 0, 'statusval': '', 'statusdate': ''})

        return status

    @staticmethod
    def isStaleWorkingStatus(row):
        if int(row.get("statusopt", 0)) != 1:
            return False
        raw_date = row.get("statusdate") or row.get("dateupdate") or row.get("datecreate")
        try:
            started = datetime.strptime(str(raw_date), '%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError):
            return True
        return datetime.now() - started > timedelta(
            seconds=Query.STALE_WORKING_TIMEOUT_SECONDS
        )

    @staticmethod
    def sharedataset(app):
        idin = app.argms["file"]
        MongoDB.update(   DBS.DBGFF, "data",
                                    {"_id": ObjectId(idin)},
                                    {"isshare":1 }
                                )

        return {"response":1};

    @staticmethod
    def unsharedataset(app):
        idin = app.argms["file"]
        MongoDB.update(   DBS.DBGFF, "data",
                                    {"_id": ObjectId(idin)},
                                    {"isshare":0 }
                                )

        return {"response":1};

    @staticmethod
    def dropdataset(idin):
        filefe = dataset_path(idin)
        if filefe.exists():
            shutil.rmtree(filefe)
        """ 
        if Settings.MULIUSER == 1:
            MongoDB.delete(DBS.DBGFF, "data", {"_id": ObjectId(idin)}) """
        MongoDB.delete(DBS.DBGFF, "data", {"_id": ObjectId(idin)})

        r = "<script>parent.opendatsetparser();</script>"
        return {"response":r};

    @staticmethod
    def savegraph(app,db):
        idin = Query.converid(app.argms["file"])

        dataup =    {
                            'versionfeature':Settings.VERSION,
                            'typefeature':'graph',
                            'configfeature':app.argms,
                            'layoutfeature':'feature.obj',
                            'dateupdate': Query.now(),
                        }

        DBX.update(DBS.DBGFF, "data", {'_id':idin}, dataup)

        DBFile.writeFile(Settings.DATA_PATH+str(idin)+"/feature.obj", db)

    @staticmethod
    def saveprojection(app,db):
        idin = Query.converid(app.argms["file"])

        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        for r in re:

            if "configfeature" in r:
                config = r["configfeature"]
                config["projection"] = app.argms["projection"]
                config["instanceproximity"] = app.argms["instanceproximity"]
                
                config["target"] = app.argms["target"]
                config["intarget"] = app.argms["intarget"]
                config["featureselected"] = app.argms["featureselected"]
                config["idinstanceslabels"] = app.argms["idinstanceslabels"];
                #config["ranking"] = app.argms["ranking"]

                dataup = {"configfeature":config};
                
                DBX.update(DBS.DBGFF, "data", {'_id':idin}, dataup)

                app.argms["ranking"] = r["configfeature"].get("ranking", [])
                app.argms["nodes"] = r["configfeature"].get("nodes", [])

            dataup = {
                        "versioninstance":Settings.VERSION,
                        "typeinstance":"projection",
                        "configinstance":app.argms,
                        "layoutinstance":"instance.obj",
                        "dateupdate": Query.now(),
                    }
            DBX.update(DBS.DBGFF, "data", {'_id':idin}, dataup)

        DBFile.writeFile(Settings.DATA_PATH+str(idin)+"/instance.obj", db)

    @staticmethod
    def saveXAI(app, db):
        idin = Query.converid(app.argms["file"])
        dataup = {
            'versionxai': Settings.VERSION,
            'typexai': 'xai',
            'configxai': {
                'target': db.get('target', {}).get('id', app.argms.get('target', '')),
                'model': db.get('model', {}),
                'settings': db.get('settings', {}),
            },
            'layoutxai': 'xai.obj',
            'dateupdate': Query.now(),
        }
        DBX.update(DBS.DBGFF, "data", {'_id': idin}, dataup)
        DBFile.writeFile(Settings.DATA_PATH+str(idin)+"/xai.obj", db)


    @staticmethod
    def silhouette(app):
        idin = Query.converid(app.argms["file"])        

        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        si = 0.0
        for r in re:
            if "typeinstance" in r and r["typeinstance"]=="projection":
                filen = Settings.DATA_PATH+str(idin)+"/instance.obj"
                if os.path.exists(filen):
                    data = {}
                    try:
                        infil = open(filen, mode="r", encoding='utf-8-sig')
                        data = ujson.load(infil)
                        infil.close()
                    except:
                        print("Something went wrong")
                        data = {}
                    # finally:
                    #     data = {}
                
                    if "points" in data:
                        config = {}
                        if "configinstance" in r:
                            config =r["configinstance"]

                        pp = data["points"]
                        if data.get("targettype") == "regression" or not 2 <= len({p["t"] for p in pp}) < len(pp):
                            DBX.update(DBS.DBGFF, "data", {"_id": idin},
                                       {"configinstance": dict(config, silhouette=None)})
                            return None
                        X, y, z = [],[],{}
                        for p in pp:
                            X.append([p["x"], p["y"]])    
                            y.append(p["t"])
                            z[p["t"]]=1
                        
                        it = 0
                        for zkey, zval in z.items():
                            z[zkey] = it
                            it += 1

                        si = Metrics.compute_silhoute(X,y,z);
                        config["silhouette"] = si;
                        DBX.update(DBS.DBGFF, "data", {'_id':idin}, {'configinstance':config})

        return si;

    @staticmethod
    def makeInstancesLabels(app):
        idin = Query.converid(app.argms["file"])
        colid = int(app.argms["idinstanceslabels"])
        try:
            maxlabels = int(app.argms.get("maxlabels", 5000))
        except (TypeError, ValueError):
            maxlabels = 5000
        #print("WWWWWWWWWWWWWWWWWWWWWWW")
        #print("colid", colid)

        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))

        for r in re:
            config_i = {}
            if "configinstance" in r:
                config_i = r["configinstance"]
            config_i["idinstanceslabels"] = colid;

            config_f = {}
            if "configfeature" in r:
                config_f = r["configfeature"]
            config_f["idinstanceslabels"] = colid;

            dataup = {'configfeature':config_f, 'configinstance':config_i};
            DBX.update(DBS.DBGFF, "data", {'_id':idin}, dataup)

                    
        directory = dataset_path(idin)
        header = pd.read_csv(directory / "original.csv", nrows=0).columns
        if not 0 <= colid < len(header):
            raise ValueError("Invalid label column")
        if (directory / "working.csv").exists():
            frame = pd.read_csv(directory / "working.csv", usecols=[colid], dtype=str)
            ids = source_ids(directory, np.arange(len(frame)))
            return {str(int(i)): str(value) for i, value in zip(ids, frame.iloc[:, 0])}
        Query.ensureSampleCsv(app)
        ids = set(ujson.loads((directory / "sample_row_ids.json").read_text(encoding="utf-8")))
        projection = DBFile.openFile(str(directory / "instance.obj"))
        ids.update(int(point["id"]) for point in projection.get("points", []))
        ordered = sorted(ids)[:10000]
        labels = read_rows(directory / "original.csv", ordered, usecols=[colid])
        return {str(i): str(label[0]) for i, label in zip(ordered, labels)}



    """ 
    @staticmethod
    def export2dproj(app,selft):
        idin = Query.converid(app.argms["file"])

        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        export = ""
        name = ""
        for r in re:
            name = r["name"]
            if "typeinstance" in r and r["typeinstance"]=="projection":
                filen = Settings.DATA_PATH+str(idin)+"/instance.obj"
                if os.path.exists(filen):
                    data = {}
                    try:
                        infil = open(filen, "r")
                        data = ujson.load(infil)
                        infil.close()
                    except:
                        print("Something went wrong")
                        data = {}
                    # finally:
                    #     data = {}
                
                    if "points" in data:
                        pp = data["points"]
                        export = "DY\n" 
                        export += str(len(pp))+"\n" 
                        export += "2\n"
                        export += "x;y\n"
                        for p in pp:
                            export += "{};{:.6f};{:.6f};{:.1f}\n".format(p["id"],p["x"], p["y"], p["t"])

        selft.set_header('Content-Type', 'text/plain')
        selft.set_header("Content-Disposition", "attachment; filename=%s" % name+".prj")

        return export;
    """


    @staticmethod
    def opendataset(app):
        idin = Query.converid(app.argms["file"])
        colle = app.argms["data"]["collect"]
        query = app.argms["data"]["query"]

        rf = []
        rs = {};
        status = Query.getStatus(app)
        status_warning = ""
        if status["statusopt"] == 2:
            # Opening cached dataset artifacts is read-only. A previous feature or
            # projection job may have failed, but existing feature.obj/instance.obj
            # files should still render instead of leaving the browser loader stuck.
            status_warning = status.get("statusval", "")
            status["statusopt"] = 0
            status["statusval"] = ""

        if status["statusopt"]==0:
            re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
            #print()
            for r in re:
                #print("re", re)
                r["_id"] = str(r["_id"])
                """ making projection from features selected """
                r["_id_user"] = str(r["_id_user"])            
                rs = r

                rs["fenames"] = Query.loadatributenames(app)
                rs["lastversion"] = Settings.VERSION
                if colle=="features":                
                    # open features
                    filen = Settings.DATA_PATH+str(idin)+"/feature.obj" 
                    rs["layoutfeature"] = DBFile.openFile(filen)

                    filen = Settings.DATA_PATH+str(idin)+"/xai.obj"
                    rs["layoutxai"] = DBFile.openFile(filen)


                elif colle=="instances":
                    # open instances
                    filen = Settings.DATA_PATH+str(idin)+"/instance.obj"
                    rs["layoutinstance"] = DBFile.openFile(filen)

                #filter
                for qrow in query:
                    aux = rs
                    for k in qrow:
                        if k in aux:
                            aux = aux[k]
                        else:
                            aux = {}
                            break;
                    rf.append({"query":qrow, "response":aux})

        status["response"] = rf
        if status_warning:
            status["statuswarning"] = status_warning
        return status




    """ 
    @staticmethod
    def openfeature(app):
        idin = app.argms["file"]
        cols = Query.loadatributenames(app.argms)

        if Settings.MULIUSER == 1:
            idin = ObjectId(idin)

        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        rs = {};
        for r in re:
            r["_id"] = str(r["_id"])
            r["_id_user"] = str(r["_id_user"])
            rs = r

            rs["fenames"] = cols
            rs["lastversion"] = Settings.VERSION


            filen = Settings.DATA_PATH+str(idin)+"/feature.obj" 
            dfile = {}
            if os.path.exists(filen):
                try:
                    infil = open(filen, "r")
                    dfile = ujson.load(infil)
                    infil.close()
                except:
                    print("Something went wrong")
                    dfile = {}
            rs["layoutfeature"] = dfile

        return rs;

    @staticmethod
    def openinstance(app):
        idin = app.argms["file"]
        #cols = Query.loadatributenames(app.argms)
        if Settings.MULIUSER == 1:
            idin = ObjectId(idin)

        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        rs = {};
        for r in re:
            r["_id"] = str(r["_id"])
            r["_id_user"] = str(r["_id_user"])
            rs = r

            #rs["fenames"] = cols
            rs["lastversion"] = Settings.VERSION

            filen = Settings.DATA_PATH+str(idin)+"/instance.obj"
            dfile = {}
            if os.path.exists(filen):
                try:
                    infil = open(filen, "r")
                    dfile = ujson.load(infil)
                    infil.close()
                except:
                    print("Something went wrong")
                    dfile = {}

            rs["layoutinstance"] = dfile

        return rs;
     """
    
    @staticmethod
    def exportfeat2datafile(app, selft):
        idin = Query.converid(app.argms["file"])
        
        filename =  Settings.DATA_PATH+str(idin)+"/transform.csv"    
        re = list(DBX.find(DBS.DBGFF, "data", {"_id":idin}))
        export = ""
        name = ""
        for r in re:
            name = r["name"]
            
            fnames = Query.loadatributenames(app);
            fnamesindex ={ str(fnames[i]):i for i in range(len(fnames))}

            layoutfeature = DBFile.openFile(Settings.DATA_PATH+str(idin)+"/feature.obj")
            nodes = layoutfeature["graph"]["nodes"]

            X = DataMatrix(filename, max_rows=5000)
            columns = X.columns()
            colsindexes = X.columnsindexes()
            
            XT = X.transpose()
            del X

            export = "DY\n" 
            export += str(len(nodes))+"\n" 
            export += str(XT.cols())+"\n" 
            nfecol = ["fe"+str(i) for i in range(XT.cols()) ]
            export += ";".join(nfecol)+"\n" 
            for nod in nodes:
                #i = fnamesindex[nod["label"]]
                i = nod["label"]
                row = [str(columns[i])]
                for j in range(XT.cols()):
                    row.append(str(XT.getValue(i,j)))

                export += ";".join(row)
                export += ";"+str(0.0)+"\n"
                
            del XT
            del fnamesindex
            del layoutfeature
            del nodes
            #target_id = X.columnindex(target)

        selft.set_header('Content-Type', 'text/plain')
        selft.set_header("Content-Disposition", "attachment; filename=%s" % name+".data")

        return export;
    
    @staticmethod
    def now():
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')




class DataTransfer:
    def __init__(self, data):
        self.argms = {}
        self.load(ujson.loads(data))

    def load(self, data):
        for k in self.__dict__:
            if k in data:
                setattr( self, k, (data[k]) )


"""
Database X
"""

class DBX:
    @staticmethod
    def find(dbs, collect, rdata):
        """ 
        rest = []
        if Settings.MULIUSER == 0:
            rest = DBFile.find(dbs, collect, rdata)
        elif Settings.MULIUSER == 1:
            rest = MongoDB.find(dbs, collect, rdata) """
        rest = MongoDB.find(dbs, collect, rdata)
        return rest
    @staticmethod
    def insert(dbs, collect, rdata):
        """ 
        rest = []
        if Settings.MULIUSER == 0:
            rest = DBFile.insert(dbs, collect, rdata)
        elif Settings.MULIUSER == 1:
            rest = MongoDB.insert(dbs, collect, rdata) """
        rest = MongoDB.insert(dbs, collect, rdata)
        return rest
    
    @staticmethod
    def update(dbs, collect, queryid, rdata):
        """ 
        if Settings.MULIUSER == 0:
            DBFile.update(dbs, collect, queryid, rdata)
        elif Settings.MULIUSER == 1:
            MongoDB.update(dbs, collect, queryid, rdata) """
        MongoDB.update(dbs, collect, queryid, rdata)

    @staticmethod
    def delete(dbs, collect, queryid):
        """ 
        if Settings.MULIUSER == 0:
            DBFile.delete(dbs, collect, queryid)
        elif Settings.MULIUSER == 1:
            MongoDB.delete(dbs, collect, queryid) """
        MongoDB.delete(dbs, collect, queryid)

"""
Database from file
"""
class DBFile:    
    global_lock = threading.Lock()

    """ multithreadiung read file """
    @staticmethod
    def openFile(pathf):
        dfile = {}
        if not os.path.isfile(pathf):
            return dfile
        try:
            with DBFile.global_lock:
                with open(pathf, mode="r", encoding='utf-8-sig') as fp:
                    dfile = ujson.load(fp)
                    
        except Exception as e:
            print("Error opening file", e, pathf)
            dfile = {}

        return dfile

    """ @staticmethod
    def openFile(pathf):
        t = threading.Thread(target=DBFile.openFile_t, args=[pathf,])
        t.start() """




    """ write JSON atomically so large layouts are never read half-written """
    @staticmethod
    def writeFile_t(pathf, rdata):
        tmpf = None
        try:
            with DBFile.global_lock:
                os.makedirs(os.path.dirname(pathf), exist_ok=True)
                tmpf = "{}.{}.tmp".format(pathf, uuid.uuid4().hex)
                with open(tmpf, mode="w", encoding='utf-8-sig') as fp:
                    ujson.dump(rdata, fp, ensure_ascii=False)
                    fp.flush()
                    os.fsync(fp.fileno())
                os.replace(tmpf, pathf)

        except Exception as e:
            print("Error writing file", e, pathf)
            if tmpf and os.path.exists(tmpf):
                try:
                    os.remove(tmpf)
                except OSError:
                    pass

    @staticmethod
    def writeFile(pathf, rdata):
        DBFile.writeFile_t(pathf, rdata)



    @staticmethod
    def find(dbs, collect, rdata):
        rdata["_id"] = str(rdata["_id"])
        rest = []
        f = Settings.DATA_PATH+rdata["_id"]+"/"+collect+".obj"            
        if os.path.isfile(f):
            rest = [DBFile.openFile(f)]
        return rest

    @staticmethod
    def insert(dbs, collect, rdata):
        idud = DBFile.uid()
        rdata["_id"] = idud

        ndir = Settings.DATA_PATH+idud

        Query.makedir(ndir)

        DBFile.writeFile(ndir+"/"+collect+".obj", rdata)
        return idud
    
    @staticmethod
    def update(dbs, collect, queryid, rdata):
        queryid["_id"] = str(queryid["_id"])
        #db = DBFile.openFile(Settings.DATA_PATH+queryid["_id"]+"/"+collect+".obj")
        #for k, v in rdata.items():
        #    db[k] = v

        # read and copy
        dat = list(DBX.find(DBS.DBGFF,collect,{"_id": queryid["_id"]}))
        db = {}
        for row in dat:
            for k, v in row.items():
                db[k] = v
        
        #print()
        #print("DB update1", db)

        # update
        for k, v in rdata.items():
            db[k] = v

        #print("DB update2", db)

        # write
        DBFile.writeFile(Settings.DATA_PATH+queryid["_id"]+"/"+collect+".obj", db)

    @staticmethod
    def uid():
        return uuid.uuid4().hex
