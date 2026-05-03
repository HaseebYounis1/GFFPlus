# distutils: language = c
# Author: Ivar Vargas Belizario and Liz M. Huancapaza Hilasaca
# Copyright (c) 2020
# All Rights Reserved
# E-mail: ivar@usp.br, lizhh@usp.br 

import glob
import os
#import soundfile as sf
#import librosa
import numpy as np
import os.path
import math

import sys
sys.setrecursionlimit(100000)




from sklearn.ensemble import ExtraTreesClassifier

#from xgboost import XGBClassifier

from collections import defaultdict 
import queue
from collections import deque
import pandas as pd

import os
from typing import List
import numpy as np


import random
import time
import math
import sys



from vx.com.px.dataset.dataio_pure import *


# ---------------------------------------------------------------------------
# Fast helpers (replace Python loops with single numpy operations)
# ---------------------------------------------------------------------------

def _target_correlations(data, target_id, corr_type):
    """Return correlation of every column in *data* with column *target_id*.

    *data* must be z-score normalised already.
    corr_type = 6 → Pearson,  corr_type = 8 → sample correlation.
    Returns a 1-D array of length data.shape[1].
    """
    _EPS = 1e-7
    tgt = data[:, target_id]

    if corr_type == 6:                          # Pearson
        dots  = data.T @ tgt                    # (n_cols,)
        norms = np.sqrt((data ** 2).sum(axis=0))
        return dots / np.maximum(norms * float(norms[target_id]), _EPS)

    else:                                       # Sample correlation (pt=8)
        n      = float(data.shape[0])
        cross  = data.T @ tgt                   # (n_cols,)
        sums   = data.sum(axis=0)               # (n_cols,)
        sq     = (data ** 2).sum(axis=0)        # (n_cols,)
        s_t    = float(sums[target_id])
        sq_t   = float(sq[target_id])
        num    = n * cross - sums * s_t
        var_c  = np.maximum(n * sq  - sums ** 2, 0.0)
        var_t  = max(n * sq_t - s_t ** 2, 0.0)
        return num / np.maximum(np.sqrt(var_c * var_t), _EPS)


def _kruskal_mst(N, ww, src, dst,
                 tree_edges, whole_edges, root, hist, max_whole_edges):
    """Kruskal's MST on a *pre-sorted* edge list.

    ww / src / dst are plain Python lists (already sorted by weight).
    Modifies tree_edges, whole_edges, root, hist in-place.
    Path-halving union-find; no recursion.
    """
    parent = list(range(N))
    rank   = [0] * N
    n_hist = len(hist) - 1

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]      # path halving
            i = parent[i]
        return i

    tree_count = 0
    cc         = 0

    for w, u, v in zip(ww, src, dst):
        ru, rv = find(u), find(v)

        if ru != rv and tree_count < N - 1:     # tree edge
            tree_count += 1
            if rank[ru] < rank[rv]:
                ru, rv = rv, ru
            parent[rv] = ru
            if rank[ru] == rank[rv]:
                rank[ru] += 1
            tree_edges.append({"source": u, "target": v, "weight": w})
            root[u][str(v)] = w
            root[v][str(u)] = w
        else:                                   # non-tree (whole) edge
            stored = len(whole_edges) < max_whole_edges
            if stored:
                whole_edges.append({"source": u, "target": v, "weight": w})
            idx = int(w * n_hist)
            hist[idx]["co"] += 1.0
            if stored:
                hist[idx]["id"].append(cc)
            cc += 1

    postprocessinghist(hist)


########################################
## Graph
########################################
class Graph:
    MAX_WHOLE_EDGES = 8000

    def __init__(self):
        self.data = {
                        "root":[],
                        "graph":{},

                        "ranking":[],
                        "rankingmin":-1,
                        "rankingmax":-1,

                        #"rankingreal":[],
                        #"rankingrealmin":-1,
                        #"rankingrealmax":-1,

                        "initvertex1":-1,
                        "initvertex2":-1,
                        "tree":{},
                        "treehi":[],
                        "edgehist":[]
                    }


    def load(self, data):
        for k in self.__dict__:
            if k in data:
                setattr( self, k, (data[k]) )            
    def toDict(self):
        return self.__dict__;

    def make_graph(self, datapath, unselectedfeids, argms):
        pmetric = argms["proximity"]
        #inv1 = int(argms["p1"])
        #inv2 = int(argms["p2"])
        targeti = int(argms["target"])
        #target_id = argms["target"]
        algorithm = argms["algorithm"]
        importance = argms["relevance"]
        filefe = datapath+argms["file"]+"/transform.csv"
        isfeature = True if int(argms["isfeature"])==1 else False
        #unselectedfeids = argms["unselectedfeids"]


        #ff = "/mnt/sda1/academic/doutorado/projects/sourcecode/data/input/"+argms["file"]+"/transform.csv"
        #f = open(ff, "r")
        #self._featuresnames_index = f.readline().split(",");
        #print("self._featuresnames_index", self._featuresnames_index)
        #f.close()

        #print("featureselected",featureselected, importance)
        #print("unselectedfeids",unselectedfeids)
        unselectedfeids = [
            int(index) for index in unselectedfeids
            if str(index).lstrip("-").isdigit() and int(index) != targeti
        ]

        # Load at most 5000 rows — sufficient for feature distances and
        # target correlations; avoids reading 100+ MB CSVs in full.
        X = DataMatrix(filefe, unselectedfeids, max_rows=5000)
        
        trueids = X.trueids()
        shifttrueids = X.shifttrueids()

        columns = X.columns()
        colsindexes = X.columnsindexes()
        #target_id = X.columnindex(targeti)
        
        target_id = trueids[targeti] if 0 <= targeti < len(trueids) else -1
        if target_id < 0:
            raise ValueError("Target column {} is not available in {}".format(targeti, filefe))
        #print("target_id, targeti", target_id, targeti)
        
        #target_id = X.columnindex(target)
        N = X.cols()
        max_whole_edges = int(argms.get("maxwholeedges", Graph.MAX_WHOLE_EDGES))
        # NJ is O(n³): cap to prevent multi-minute hangs on wide datasets
        if algorithm == "nj" and N > 300:
            algorithm = "mst"
        pm_t = X.proximitymatrix_cols(pmetric)
        prox_types = ProximityMatrix.POT
        coeffx = pm_t.getCoefficient()
        # define to graph json format to send D3.js
        graph = { "nodes": [], "links": [], "whole": [] }
        root = [ {} for i in range(N) ] 
        self.data["ranking"] = []
        #self.data["rankingreal"] = []
        idmx = -1

        if isfeature == True:
            for i in range(N):
                graph["nodes"].append({ "name": i,
                                        "label": "",
                                        #"type": 1,
                                        "category": 0,
                                        #"color": "",
                                        "weight": 0,
                                        #"ranking": -1,
                                        #"ratio": 0
                                        })
                self.data["ranking"].append(-1.0);
                #self.data["rankingreal"].append(-1.0);

            idmx = target_id
            if importance == "Pearson" or importance == "Correlation" :
                # Z-score all columns in one broadcast pass
                mu    = X._data.mean(axis=0, keepdims=True)
                sigma = X._data.std(axis=0, ddof=1, keepdims=True)
                sigma = np.where(sigma < 1e-6, 1.0, sigma)
                X._data = (X._data - mu) / sigma

                corrmeasure = prox_types["Pearson"] if importance == "Pearson" \
                              else prox_types["Correlation"]

                # Single matrix operation: correlations of all columns with target
                all_corr = _target_correlations(X._data, target_id, corrmeasure)

                minf_, maxf_ = float("inf"), -float("inf")
                minfr_, maxfr_ = float("inf"), -float("inf")

                for name, i in colsindexes.items():
                    if i != target_id:
                        dr = float(all_corr[i])
                        d  = abs(dr)
                        if d  < minf_:  minf_  = d
                        if d  > maxf_:  maxf_  = d
                        if dr < minfr_: minfr_ = dr
                        if dr > maxfr_: maxfr_ = dr
                        node = graph["nodes"][i]
                        node["label"]  = shifttrueids[i]
                        node["weight"] = d
                        self.data["ranking"][node["name"]] = dr

                self.data["rankingmin"] = minfr_
                self.data["rankingmax"] = maxfr_

                minmax = float(0.0000001 + (maxf_ - minf_))
                for g in graph["nodes"]:
                    g["weight"] = (g["weight"] - minf_) / minmax
                    
                    #self.data["ranking"][g["name"]] = d

                    #d = (rkg - self.data["ranking"][g["name"]]-minf_)/(minmax)
                    #self.data["ranking"][g["name"]] = d


            elif importance == "Extratrees":
                xidcols = []
                for name, i in colsindexes.items():
                    if i != target_id:
                        xidcols.append(i)

                yt, ymint, ymaxt = X.getcolumn_index(target_id)
                XR = X.selectcolumns_index(xidcols)

                xt = XR._data
                yt = np.array(yt)
                modelt = ExtraTreesClassifier(n_estimators=50, random_state=7, n_jobs=-1)
                n_rows = xt.shape[0]
                if n_rows > 5000:
                    rng = np.random.default_rng(42)
                    idx = rng.choice(n_rows, 5000, replace=False)
                    modelt.fit(xt[idx], yt[idx])
                else:
                    modelt.fit(xt, yt)

                # Access feature_importances_ ONCE — it spawns a parallel
                # worker pool on every call; calling it inside a loop would
                # create/teardown that pool N times (14+ s on Windows).
                importances = modelt.feature_importances_
                vls      = importances.tolist()
                impmi    = float(importances.min())
                impmx    = float(importances.max())

                self.data["rankingmin"] = impmi
                self.data["rankingmax"] = impmx

                #self.data["rankingrealmin"] = impmi
                #self.data["rankingrealmax"] = impmx

                #for i in range(len(xcols)):
                for i in range(len(xidcols)):
                    
                    #name = xcols[i]
                    name = shifttrueids[xidcols[i]]
                    ix = xidcols[i]
                    d = (vls[i]-impmi)/(0.0000001+(impmx-impmi));
                    node = graph["nodes"][ix]
                    node["label"] = name;
                    node["weight"] = d;
                    #node["ranking"] = vls[i];
                    self.data["ranking"][node["name"]] = vls[i]
                    #self.data["rankingreal"][node["name"]] = vls[i]

                del XR
#                print(graph["nodes"])

            g = graph["nodes"][target_id]
            #g["label"] = target
            g["label"] = shifttrueids[target_id]
            g["weight"] = 1.0
            #g["ranking"] = 1.0
            self.data["ranking"][target_id] = 1.0
            
            #self.data["rankingreal"][target_id] = 1.0

        hist = [{"hi":0.0, "co":0.0, "id":[]} for i in range(400)]
        if algorithm == "mst":
            self.data["initvertex2"] = 0

            # Extract all upper-triangle weights in one numpy operation,
            # sort once — avoids N*(N-1)/2 Python getValue() calls.
            ii, jj = np.triu_indices(N, k=1)
            ww     = pm_t._mat[ii, jj]
            ord_   = np.argsort(ww, kind="stable")

            _kruskal_mst(
                N,
                ww[ord_].tolist(),
                ii[ord_].tolist(),
                jj[ord_].tolist(),
                graph["links"], graph["whole"], root, hist, max_whole_edges,
            )


        elif algorithm=="nj":
            # add auxiliar nodes
            for i in range(N,(N+(N-2))):
                root.append({});
                graph["nodes"].append({ 
                                        "name": i,
                                        #"label": "ExtraNode"+str(i),
                                        "label": -1,
                                        #"type": 0,
#                                        "indexcol": i,
                                        "category": 1,
                                        #"color": "#ccc",
                                        "weight": 0.001,
                                        #"ratio": 0.1
                                        })

            #print("Calculating Neighbor-Joining...");
            nj = NeighborJoining()
            self.data["initvertex2"] = nj.execute(pm_t, N, root, graph) 

            # Whole edges for NJ: non-tree pairs sorted by weight (numpy)
            ii_nj, jj_nj = np.triu_indices(N, k=1)
            ww_nj  = pm_t._mat[ii_nj, jj_nj]
            ord_nj = np.argsort(ww_nj, kind="stable")
            cc = 0
            n_hist = len(hist) - 1
            for eidx in ord_nj:
                u_nj, v_nj = int(ii_nj[eidx]), int(jj_nj[eidx])
                if str(v_nj) in root[u_nj]:
                    continue
                w_nj  = float(ww_nj[eidx])
                stored = len(graph["whole"]) < max_whole_edges
                if stored:
                    graph["whole"].append({"source": u_nj, "target": v_nj, "weight": w_nj})
                hid = int(w_nj * n_hist)
                hist[hid]["co"] += 1.0
                if stored:
                    hist[hid]["id"].append(cc)
                cc += 1

            postprocessinghist(hist)
        #add tree childs
        if algorithm=="mst" or algorithm=="nj":
            self.data["tree"] = newtree(root, graph["nodes"], self.data["initvertex2"])
            #print("22222222222222222222222222")
            #self.data["tree"] = maingettree(root, graph["nodes"], self.data["initvertex2"])
            #print("TREEEEEEEEE",self.data["tree"])
            self.data["treehi"] = buildtreehierarquical(root, self.data["initvertex2"])
            #print("333333333333333333333333333333")
        del(X)
        del(pm_t)

        self.data["root"] = root
        self.data["graph"] = graph
        #self.data["ranking"] = ranking
        self.data["initvertex1"] = idmx
        self.data["edgehist"] = hist
        
#        self.initvertex2 = idmx2
#        self.tree = trees
       
      
        
        
########################################
## Kruskal's algorithm - MST
########################################
#Class to represent a graph 

class GraphMST: 
  
    def __init__(self,vertices): 
        self.V= vertices #No. of vertices 
        self.graph = []

   
    # function to add an edge to graph 
    def addEdge(self,w,u,v): 
        self.graph.append((w, u, v))
  
    # A utility function to find set of an element i 
    # (uses path compression technique) 
    def find(self, parent, i): 
        if parent[i] == i: 
            return i 
        return self.find(parent, parent[i]) 
  
    # A function that does union of two sets of x and y 
    # (uses union by rank) 
    def union(self, parent, rank, x, y): 
        xroot = self.find(parent, x) 
        yroot = self.find(parent, y) 
  
        # Attach smaller rank tree under root of  
        # high rank tree (Union by Rank) 
        if rank[xroot] < rank[yroot]: 
            parent[xroot] = yroot 
        elif rank[xroot] > rank[yroot]: 
            parent[yroot] = xroot 
  
        # If ranks are same, then make one as root  
        # and increment its rank by one 
        else : 
            parent[yroot] = xroot 
            rank[xroot] += 1
  
    # The main function to construct MST using Kruskal's  
        # algorithm 
    def KruskalMST(self, graph1, graph2, root, hist):
        #print("hist", hist)
        #hist = [0.0 for i in range(400)]
        # result =[] #This will store the resultant MST 
  
        i = 0 # An index variable, used for sorted edges 
        e = 0 # An index variable, used for result[] 
        cc = 0
            # Step 1:  Sort all the edges in non-decreasing  
                # order of their 
                # weight.  If we are not allowed to change the  
                # given graph, we can create a copy of graph 
#        self.graph =  sorted(self.graph,key=lambda item: item[2]) 
  
        parent = [];
        rank = [] 
  
        # Create V subsets with single elements 
        for node in range(self.V): 
            parent.append(node) 
            rank.append(0) 


        edges = sorted(self.graph, key=lambda item: item[0])
        max_whole_edges = Graph.MAX_WHOLE_EDGES

        # Number of edges to be taken is equal to V-1 
        for w, u, v in edges:
            if e >= self.V - 1:
                break
  
            # Step 2: Pick the smallest edge and increment  
                    # the index for next iteration 
            #print("size: ",len(self.graph.queue))
            i = i + 1
            x = self.find(parent, u) 
            y = self.find(parent ,v) 
  
            # If including this edge does't cause cycle,  
                        # include it in result and increment the index 
                        # of result for next edge 
            if x != y: 
                e = e + 1     
                # result.append([u,v,w]) 
                self.union(parent, rank, x, y)
                graph1.append({ "source": u,
                                "target": v,
                                "weight": w,
                                #"category": 0
                                })

                root[u][str(v)] = w
                root[v][str(u)] = w
                
                #hist[int(w*(len(hist)-1))]["co"] += 1 
                #print("w",w)
            # Else discard the edge 
            else:
                stored_edge = len(graph2) < max_whole_edges
                if stored_edge:
                    graph2.append({ "source": u,
                                    "target": v,
                                    "weight": w,
                                    #"category": 1
                                    })
                idx = int(w*(len(hist)-1))
                hist[idx]["co"] += 1.0
                if stored_edge:
                    hist[idx]["id"].append(cc)
                cc += 1 

        for w, u, v in edges[i:]:
            stored_edge = len(graph2) < max_whole_edges
            if stored_edge:
                graph2.append({ "source": u,
                                "target": v,
                                "weight": w,
                                #"category": 1
                                })
            idx = int(w*(len(hist)-1))
            hist[idx]["co"] += 1.0 
            if stored_edge:
                hist[idx]["id"].append(cc)
            cc += 1

        postprocessinghist(hist)
        #minh = float("inf")
        #maxh = float("-inf")
        #for i in range(len(hist)):
        #    if hist[i]["co"]>=1:
        #        hist[i]["hi"] = math.log(hist[i]["co"]) 
        #
        #    if hist[i]["hi"]<minh:
        #        minh = hist[i]["hi"]
        #    if hist[i]["hi"]>maxh:
        #        maxh = hist[i]["hi"]
        #
        #conden = 0.0000001+(maxh-minh)
        #for i in range(len(hist)):
        #    hist[i]["hi"] = (hist[i]["hi"]-minh)/(conden)
        #    co = hist[i]["co"]
        #    if co >= 1 and co <= 5:
        #        hist[i]["hi"] = 0.04+(1/(co*100));



###############################    
## NeighborJoining
###############################    
class NeighborJoining:
    def __init__(self):
        pass

    def execute(self, dm, N, root, graph):
#        nodetmp ={  "label":"", "category":"",
#                    "color":"#00ffff", "weight": 1.0,
#                    "ratio": 1.0, "xpos":-1.0, "ypos":-1.0}
#
#        linktmp ={"source":-1,"target":-1,"weight":0}
        vs = N+(N-2)
#        self.graph = { k:{"node":[], "link":[] } for k in range(vs) }
        clusters = { k:k for k in range(N)}
        ud = [0.0 for k in range(vs)]
        u = N
        repetir = True
        while repetir:
#            idmx = u
            self.nj(dm, clusters, graph, root, u, ud);
            u+=1
            repetir = (len(clusters)>2);

#        ab = clusters.items();
#        a = ab[0][0]
#        b = ab[1][0]
#        self.addEdge(graph, root, a, b, u, awu, bwu)        
#        idmx = vs-1
#        print("idmx", idmx)
        return vs-1

    def nj(self, dm, clusters, graph, root, u, ud):
        n = len(clusters)
        for a,va in clusters.items():
            ud[a] = 0.0
            for b,va2 in clusters.items():
#                if a!=b:
                ud[a] += dm.getValue(a, b)

        ai, bi, minp = -1, -1, float("inf")

        # Q matrix
        for a,va in clusters.items():
            for b,va2 in clusters.items():
                if a!=b:
                    v = (n-2.0)*dm.getValue(a, b)-ud[a]-ud[b];
                    if v<minp:
                        minp = v
                        ai = a
                        bi = b

        # ai u, bi u, edges values
        aiu = ((0.5)*dm.getValue(ai, bi))+((1.0/(2.0*(n-2.0)))*(ud[ai]-ud[bi]));
        biu = dm.getValue(ai, bi)-aiu;
        
#        print(ai, bi, u, aiu, biu)

        # insert 2 edges in the graph
#        print("WW",clusters[ai], clusters[bi], u, awu, bwu)
#        print("len(clusters)",len(clusters), clusters[ai], clusters[bi], u)
#        self.addEdge(graph, root, clusters[ai], clusters[bi], u, aiu, ubi)

        # add two edges from ai and bi vertex to new u vertex
        self.addEdge(graph, root, clusters[ai], u, aiu)
        self.addEdge(graph, root, clusters[bi], u, biu)
        # delete one cluster
        
        # to comple the last edge
        if len(clusters)==3:
            ci = -1
            for k, v in clusters.items():
                if k!= ai and k!= bi:
                    ci = k
            uci = dm.getValue(ai, ci)-aiu;
            self.addEdge(graph, root, clusters[ci], u, uci) 
            
        del clusters[bi]
#        print(clusters)


        # update distance matrix
        for i,v2 in clusters.items():
            v = (0.5)*(dm.getValue(ai,i)+dm.getValue(bi,i)-dm.getValue(ai,bi))
            dm.setValue(ai, i, v)

        clusters[ai] = u
        # update index matrix with new vertex


    def addEdge(self, graph, root, a, b, w):
        graph["links"].append({"source":a,"target":b,"weight":w})

        root[a][str(b)] = w
        root[b][str(a)] = w





class DistanceMatrix:
    def __init__(self, X):
        n = len(X)
        self.dist = [ [] for i in range(n)]
        for i in range(n):
            self.dist[i] = [ 0.0 for j in range(n)];
            for j in range(i,n):
                if i!=j:
                    d = DistanceMatrix.proximity(X[i], X[j], 1);
                    self.dist[i][j] = d
                    
    def get(self, i, j):
        mi = i
        mj = j
        if j<i:
            mi = j
            mj = i

        return self.dist[mi][mj]

    @staticmethod
    def proximity(a,b,t):
        p = 0.0;
        if t==1:
            for i in range(len(a)):
                c = a[i]-b[i]
                c = c**2
                p+=c
            p = math.sqrt(p)
        return p






class Metrics:
    @staticmethod
    def average_silhouette(dm, clus, i):
        d = 0.0;
        n = 0.0;
        for j in clus:
            if i != j:
                d += dm.get(i, j)
                n += 1.0
        d/=n;
        return d;

    """
    * @silhoute function
    * @X vector matrix
    * @y vector classes
    * @z clusters ids
    """
    @staticmethod
    def compute_silhoute(X, y, z):
        nz = len(z)
        print("Compute silhoute...")
        s = 0.0        
        n = len(X)
        S = [0.0 for i in range(n)]
        clusters = [ [] for i in range(nz)]
       
        #lesval = 1
        #havzero = False
        #for i in y:
        #    if i==0:
        #        havzero = True
        #        lesval = 0
        #        break
        #if havzero==False:
        #    for i in range(len(y)):
        #        y[i] = y[i]-lesval

        for i in range(n):
            clusters[z[y[i]]].append(i);

        d2 = DistanceMatrix(X)
        #pm_t = X.proximitymatrix_cols(pmetric)


        for i in range(n):
            if len(clusters[z[y[i]]])>1:#is not singleton
                a = Metrics.average_silhouette(d2, clusters[z[y[i]]], i);
                b = float("inf");
                for j in range(nz):
                    if len(clusters[j]) > 0:
                        if j == z[y[i]]:
                            continue
                        b = min(b, Metrics.average_silhouette(d2, clusters[j], i))

                S[i] = (b - a)/max(a, b)
                if b==a:
                    S[i] = 0.0;

            else:
                S[i] = 0.0;
        del d2
        for i in range(n):
            s += S[i]

        s = s/n;
        print("silhoute complete")

        return s;
        





def gettreefromgraph(graph, nodes, root, visi):
    visi[root] = True 
    rest = {}
    rest["name"] = nodes[root]["label"]
    rest["id"] = root
    aux = []
    for i in graph[root]:
        i = int(i)
        if visi[i] == False:
            ch = gettreefromgraph(graph, nodes, i, visi)
#            if (len(ch)>0):
            aux.append(ch)
               
    if len(aux)>0:
        rest["children"] = aux
    else:
        rest["size"] = nodes[root]["weight"]
    return rest

def maingettree(graph, nodes, root):
    visi = [False for i in range(len(graph))]
    rest = gettreefromgraph(graph, nodes, root, visi)
    return rest




def postprocessinghist(hist):
    minh = float("inf")
    maxh = float("-inf")
    for i in range(len(hist)):
        if hist[i]["co"]>=1:
            hist[i]["hi"] = math.log(hist[i]["co"]) 

        if hist[i]["hi"]<minh:
            minh = hist[i]["hi"]
        if hist[i]["hi"]>maxh:
            maxh = hist[i]["hi"]

    conden = 0.0000001+(maxh-minh)
    for i in range(len(hist)):
        hist[i]["hi"] = (hist[i]["hi"]-minh)/(conden)
        co = hist[i]["co"]
        if co >= 1 and co <= 5:
            hist[i]["hi"] = 0.04+(1/(co*100));




def buildtreehierarquical(graph, root):
    visi = [False for i in range(len(graph))];
    hi = [{"id":int(root), "parentId": "null" }]
    #visi[root] = True
    de = deque([int(root)]) 
    while de:
        p = de.popleft()
        for i in graph[p]:
            i = int(i)
            if visi[i]==False:
                hi.append({"id":i, "parentId": p})

                de.append(i)
        visi[p]=True

    #print(hi)
    return hi


def newtree(graph, nodes, root):

    #print(">>>>>>>>>1")
    visi = [False for i in range(len(graph))]
    i = int(root)
    XX = {"id":i, "name":nodes[i]["label"], "size":nodes[i]["weight"]+0.01}
    de = deque()
    de.append(XX)
    while de:
        ei = de.popleft()
        i = ei["id"]
        if len(graph[i])>0:
            ei["children"] = []

        c = 0
        for j in graph[i]:
            j = int(j)
            if visi[j]==False:
                ei["children"].append({"id":j, "name":nodes[j]["label"], "size":nodes[j]["weight"]+0.01})
                de.append(ei["children"][c])
                c+=1
        visi[i]=True

    #print(">>>>>>>>>2")
    #visi = [False for i in range(len(graph))]
    de = deque()
    de.append(XX)
    while de:
        ei = de.popleft()
        i = ei["id"]
        if "children" in ei:
            if len(ei["children"])>0:
                for e in ei["children"]:
                    de.append(e)
            else:
                del ei["children"]
    
    #print(">>>>>>>>>3")
    #print("XXXX222",XX)


    return XX


