#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math

import numpy as np
import pandas as pd


EPS = 1e-7


class DataMatrix:
    def __init__(self, filecsv="None", unselectedfeids=None):
        self._trueids = []
        self._feids = []
        self._featuresnames = {}
        self._featuresnames_index = []
        self._data = np.zeros((0, 0), dtype=float)

        if unselectedfeids is None:
            unselectedfeids = []

        if filecsv != "None":
            self._load_csv(filecsv, unselectedfeids)

    def _load_csv(self, filecsv, unselectedfeids):
        header = pd.read_csv(filecsv, nrows=0, encoding="utf-8-sig").columns
        all_features = [str(col).strip() for col in header]
        self._feids = list(range(len(all_features)))
        self._trueids = list(range(len(all_features)))

        if unselectedfeids:
            selected = [1 for _ in all_features]
            self._trueids = [-1 for _ in all_features]
            for index in unselectedfeids:
                selected[index] = 0

            self._feids = []
            self._featuresnames_index = []
            shifted = 0
            for index, keep in enumerate(selected):
                if keep:
                    self._feids.append(index)
                    self._featuresnames_index.append(all_features[index])
                    self._trueids[index] = shifted
                    shifted += 1
        else:
            self._featuresnames_index = all_features

        frame = pd.read_csv(
            filecsv,
            delimiter=",",
            encoding="utf-8-sig",
            usecols=self._feids,
        )
        self._data = frame.to_numpy(dtype=float, copy=True)
        self._featuresnames = {
            self._featuresnames_index[i].strip(): i
            for i in range(len(self._featuresnames_index))
        }

    def create(self, rows, cols):
        self._data = np.zeros((rows, cols), dtype=float)

    def trueids(self):
        return self._trueids

    def shifttrueids(self):
        return self._feids

    def columnsindexes(self):
        return self._featuresnames

    def columnindex(self, c):
        return self._featuresnames[c]

    def columns(self):
        return list(self._featuresnames.keys())

    def columns_index(self):
        return self._featuresnames_index

    def tolist(self):
        return self._data.tolist()

    def proximitymatrix_rows(self, ptn="Euclidean"):
        pm = ProximityMatrix(ptn=ptn)
        pm._mat = _pairwise_matrix(self._data, axis=0, pt=pm.pti)
        return pm

    def proximitymatrix_cols(self, ptn="Euclidean"):
        pm = ProximityMatrix(ptn=ptn)
        pm._mat = _pairwise_matrix(self._data, axis=1, pt=pm.pti)
        return pm

    def proximity_rows(self, i, j, pt):
        return _proximity(self._data[i, :], self._data[j, :], pt)

    def proximity_cols(self, i, j, pt):
        return _proximity(self._data[:, i], self._data[:, j], pt)

    def normalization_col(self, c, pt):
        self._data[:, c] = _normalize(self._data[:, c], pt)

    def normalization_row(self, r, pt):
        self._data[r, :] = _normalize(self._data[r, :], pt)

    def transpose(self):
        other = DataMatrix()
        other._data = self._data.T.copy()
        other._featuresnames_index = ["c" + str(i) for i in range(self.rows())]
        other._featuresnames = {
            other._featuresnames_index[i]: i
            for i in range(len(other._featuresnames_index))
        }
        other._feids = list(range(other.cols()))
        other._trueids = list(range(other.cols()))
        return other

    def selectcolumns(self, featurescols):
        indexes = [self._featuresnames[col] for col in featurescols]
        return self.selectcolumns_index(indexes)

    def selectcolumns_index(self, featurescols_index):
        indexes = list(featurescols_index)
        other = DataMatrix()
        other._data = self._data[:, indexes].copy()
        other._featuresnames_index = [self._featuresnames_index[i] for i in indexes]
        other._featuresnames = {
            other._featuresnames_index[i]: i
            for i in range(len(other._featuresnames_index))
        }
        other._feids = indexes
        other._trueids = list(range(len(indexes)))
        return other

    def selectrows(self, idrows):
        other = DataMatrix()
        other._data = self._data[list(idrows), :].copy()
        other._featuresnames = self._featuresnames.copy()
        other._featuresnames_index = list(self._featuresnames_index)
        other._feids = list(self._feids)
        other._trueids = list(self._trueids)
        return other

    def copyrow(self, rowi, densemat, rowj):
        self._data[rowi, :] = densemat._data[rowj, :]

    def fillrow(self, r, fill):
        self._data[r, :] = fill

    def fillcol(self, c, fill):
        self._data[:, c] = fill

    def getcolumn(self, ci):
        return self.getcolumn_index(self._featuresnames[ci])

    def getcolumn_index(self, c):
        values = self._data[:, c].tolist()
        return values, min(values), max(values)

    def setValue(self, i, j, v):
        self._data[i, j] = v

    def getValue(self, i, j):
        return float(self._data[i, j])

    def rows(self):
        return int(self._data.shape[0])

    def cols(self):
        return int(self._data.shape[1])

    def show(self):
        for row in self._data:
            print(" ".join(str(value) for value in row))

    def proximity_row(self, i, other, j, proxtype):
        return _proximity(self._data[i, :], other._data[j, :], proxtype)

    def proximity_row_ij(self, i, j, proxtype):
        return _proximity(self._data[i, :], self._data[j, :], proxtype)


class ProximityMatrix:
    POT = {
        "Euclidean": 0,
        "Manhattan": 1,
        "Camberra": 2,
        "Chebychev": 3,
        "Braycurtis": 4,
        "Cosine": 5,
        "Pearson": 6,
        "Gaussian": 7,
        "Correlation": 8,
        "DCosine": 9,
    }
    CEF = {
        "Euclidean": 1,
        "Manhattan": 1,
        "Camberra": 1,
        "Chebychev": 1,
        "Braycurtis": 1,
        "Cosine": -1,
        "Pearson": -1,
        "Gaussian": -1,
        "Correlation": -1,
        "DCosine": 1,
    }

    def __init__(self, N=None, init=0.0, isinit=0, ptn="Euclidean"):
        self.ptn = ptn
        self.pti = ProximityMatrix.POT[self.ptn]
        self.cei = ProximityMatrix.CEF[self.ptn]
        if N is None:
            self._mat = np.zeros((0, 0), dtype=float)
        else:
            fill = init if isinit else 0.0
            self._mat = np.full((N, N), fill, dtype=float)

    def getValue(self, i, j):
        return float(self._mat[i, j])

    def setValue(self, i, j, v):
        self._mat[i, j] = v
        self._mat[j, i] = v

    def getCoefficient(self):
        return self.cei


def _normalize(values, pt):
    values = np.asarray(values, dtype=float)
    if pt == 0:
        minv = values.min()
        maxv = values.max()
        denom = maxv - minv
        if abs(denom) < EPS:
            return np.zeros_like(values)
        return (values - minv) / denom
    if pt == 1:
        mean = values.mean()
        sigma = values.std(ddof=1) if values.size > 1 else 1.0
        if sigma < 1e-6:
            sigma = 1.0
        return (values - mean) / sigma
    return values


def _pairwise_matrix(data, axis, pt):
    vectors = data if axis == 0 else data.T
    n = vectors.shape[0]
    matrix = np.zeros((n, n), dtype=float)
    values = []

    for i in range(n):
        for j in range(i + 1, n):
            distance = _proximity(vectors[i], vectors[j], pt)
            matrix[i, j] = distance
            matrix[j, i] = distance
            values.append(distance)

    if not values:
        return matrix

    minv = min(values)
    maxv = max(values)
    denom = EPS + (maxv - minv)
    coeff = ProximityMatrix.CEF[_pt_name(pt)]
    for i in range(n):
        for j in range(i + 1, n):
            value = (matrix[i, j] - minv) / denom
            if coeff == -1:
                value = 1.0 - value
            matrix[i, j] = value
            matrix[j, i] = value
    return matrix


def _pt_name(pt):
    for name, value in ProximityMatrix.POT.items():
        if value == pt:
            return name
    return "Euclidean"


def _proximity(a, b, pt):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    diff = a - b

    if pt == 0:
        return float(np.sqrt(np.dot(diff, diff)))
    if pt == 1:
        return float(np.abs(diff).sum())
    if pt == 2:
        return float((np.abs(diff) / (EPS + np.abs(a) + np.abs(b))).sum())
    if pt == 3:
        return float(np.abs(diff).max())
    if pt == 4:
        return float(np.abs(diff).sum() / (EPS + (a + b).sum()))
    if pt == 5:
        return float(np.dot(a, b) / (EPS + math.sqrt(np.dot(a, a)) * math.sqrt(np.dot(b, b))))
    if pt == 6:
        ac = a - a.mean()
        bc = b - b.mean()
        return float(np.dot(ac, bc) / (EPS + math.sqrt(np.dot(ac, ac) * np.dot(bc, bc))))
    if pt == 7:
        euclidean = np.sqrt(np.dot(diff, diff))
        return float(math.exp((-1.0 * euclidean * euclidean) / (2.0 * (0.5 * 0.5))))
    if pt == 8:
        n = float(a.size)
        ai = float(np.dot(a, b))
        ax = float(a.sum())
        ay = float(b.sum())
        x2 = float(np.dot(a, a))
        y2 = float(np.dot(b, b))
        denom = EPS + math.sqrt(max(0.0, (n * x2) - (ax * ax)) * max(0.0, (n * y2) - (ay * ay)))
        return ((ai * n) - (ax * ay)) / denom
    if pt == 9:
        cosine = np.dot(a, b) / (EPS + math.sqrt(np.dot(a, a)) * math.sqrt(np.dot(b, b)))
        return float(1.0 - ((1.0 + cosine) / 2.0))
    return 0.0
