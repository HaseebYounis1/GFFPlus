#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br


import pandas as pd
import numpy as np

class MData:
    def __init__(self, X=[], columns=[], columnsi={}):
        self.X = X
        self.columns = columns
        self.columns_i = columnsi
        # add columns adn columnsi when are null

    def getData(self):
        return self.X
    
    def getColumns(self):
        return self.columns 

    def sample(self, smp_rows=None, smp_cols=None):
        X = []

        cols_i = None
        if smp_cols != None:
            cols_i = []
            for c in smp_cols:
                cols_i.append(self.columns_i[c])

        X = MData.samplex(self.X, smp_rows, cols_i)

        if smp_cols != None:
            colsi = {str(smp_cols[i]):i for i in range(len(smp_cols))}
            
        md = MData(X, smp_cols, colsi)
        return md;

    @staticmethod
    def samplex(X, smp_r=None, smp_c=None):
        if smp_r is None and smp_c is None:
            return X
        arr = np.asarray(X, dtype=float)
        if smp_r is not None and smp_c is None:
            return arr[smp_r].tolist()
        if smp_r is None and smp_c is not None:
            return arr[:, smp_c].tolist()
        return arr[np.ix_(smp_r, smp_c)].tolist()

    # output: id of poin of controls
    @staticmethod
    def openfilecsv(filename):
        df = pd.read_csv(filename, delimiter=",")
        columns = [c for c in df.columns.tolist() if c != "INDEXIDUID_"]
        df = df[columns]

        cat_columns = df.select_dtypes(["object"]).columns
        if len(cat_columns):
            df[cat_columns] = df[cat_columns].apply(
                lambda col: col.astype("category").cat.codes
            )

        X = df.to_numpy(dtype=float).tolist()
        columns_i = {str(columns[i]): i for i in range(len(columns))}
        return MData(X, columns, columns_i)

    # input: smpsize, fematrix, prox
    # output: id of poin of controls
    @staticmethod
    def openfiledata(file):
        X = []
        featurenames = []
        ids = []
        targets = []
        
        f = open(file, "r")
        dtype = (f.readline()).strip()

        if dtype=="SY":
            rows = int(f.readline().strip())
            cols = int(f.readline().strip())

            X = [[0.0 for j in range(cols)] for i in range(rows)];
            ids = [["" for j in range(cols)] for i in range(rows)];
            targets = [ 0.0 for i in range(rows)];
            featurenames = f.readline().strip()
            featurenames = featurenames.split(";")
            featurenames = [x.strip() for x in featurenames]
            ir = 0
            while True:
                line = f.readline().strip()
                if not line:
                    break;
                line = line.strip()
                words = line.split(";")
                ids[ir] = str(words[0])
                targets[ir] = float(words[len(words)-1])
                for i in range(1,len(words)-1):
                    j,v = words[i].split(":");
                    X[ir][int(j)] = float(v)
                ir += 1
        elif dtype=="DY":
            rows = f.readline()
            cols = f.readline()
            X = [[0.0 for j in range(cols)] for i in range(rows)];
            ids = [["" for j in range(cols)] for i in range(rows)];
            targets = [ "" for i in range(rows)];
            featurenames = f.readline()
            featurenames = featurenames.split(";")
            featurenames = [x.strip() for x in featurenames]
            ir = 0
            while True:
                line = f.readline()
                if not line:
                    break;
                line = line.strip()
                words = line.split(";")
                ids[ir] = str(words[0])
                targets[ir] = float(words[len(words)-1])
                for j in range(1,len(words)-1):
                    X[ir][j-1] = float(words[i])
                ir += 1
        else:
            pass
        f.close()
        return X, featurenames, ids, targets
        
    # input: smpsize, fematrix, prox
    # output: id of poin of controls
    @staticmethod
    def converdata2csv(filedata,filecsv):
        X, featurenames, ids, targets = MData.openfiledata(filedata)
        lines = "INDEXIDUID_,"
        lines += ",".join(featurenames)
        lines += ",TARGETDUID_\n";
        for i in range(len(X)):
            lines += str(ids[i])+","
            row = [str(x) for x in X[i]]
            lines += ",".join(row)
            lines += ","+str(targets[i])+"\n";
        ofile = open(filecsv, 'w')
        ofile.write(lines)
        ofile.close()

        
    # /mnt/sda1/software/desktop/java/pex-1.6.3_src/ProjectionExplorer/test/data/cbrilpirson.data
        
    

