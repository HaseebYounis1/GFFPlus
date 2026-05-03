#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math

import numpy as np
import pandas as pd


EPS = 1e-7
DEFAULT_DTYPE = np.float32


class DataMatrix:
    def __init__(self, filecsv="None", unselectedfeids=None, max_rows=None,
                 selectedfeids=None, dtype=DEFAULT_DTYPE):
        self._dtype = np.dtype(dtype)
        self._trueids = []
        self._feids = []
        self._featuresnames = {}
        self._featuresnames_index = []
        self._data = np.zeros((0, 0), dtype=self._dtype)

        if unselectedfeids is None:
            unselectedfeids = []

        if filecsv != "None":
            self._load_csv(filecsv, unselectedfeids, max_rows, selectedfeids)

    def _load_csv(self, filecsv, unselectedfeids, max_rows=None, selectedfeids=None):
        header = pd.read_csv(filecsv, nrows=0, encoding="utf-8-sig").columns
        all_features = [str(col).strip() for col in header]
        n_features = len(all_features)
        if selectedfeids is None:
            candidate_ids = list(range(n_features))
        else:
            candidate_ids = _clean_feature_ids(selectedfeids, n_features)

        dropped = set(_clean_feature_ids(unselectedfeids, n_features))
        self._feids = [index for index in candidate_ids if index not in dropped]
        self._trueids = [-1 for _ in all_features]
        for shifted, index in enumerate(self._feids):
            self._trueids[index] = shifted
        self._featuresnames_index = [all_features[index] for index in self._feids]

        if not self._feids:
            self._featuresnames = {}
            self._data = np.zeros((0, 0), dtype=self._dtype)
            return

        read_kw = {"delimiter": ",", "encoding": "utf-8-sig", "usecols": self._feids}
        if max_rows is not None:
            read_kw["nrows"] = max_rows
        frame = pd.read_csv(filecsv, **read_kw)

        # pandas reads integer usecols in file order; restore the caller's
        # requested order so original feature ids keep a stable local mapping.
        loaded_set = set(self._feids)
        loaded_ids = [index for index in range(n_features) if index in loaded_set]
        if loaded_ids != self._feids:
            reorder = {feature_id: pos for pos, feature_id in enumerate(loaded_ids)}
            frame = frame.iloc[:, [reorder[feature_id] for feature_id in self._feids]]

        self._data = frame.to_numpy(dtype=self._dtype, copy=True)
        self._featuresnames = {
            self._featuresnames_index[i].strip(): i
            for i in range(len(self._featuresnames_index))
        }

    def create(self, rows, cols):
        self._data = np.zeros((rows, cols), dtype=self._dtype)

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

    def proximitymatrix_cols(self, ptn="Euclidean", max_rows=5000):
        pm = ProximityMatrix(ptn=ptn)
        data = self._data
        if data.shape[0] > max_rows:
            idx = np.random.default_rng(42).choice(data.shape[0], max_rows, replace=False)
            data = data[idx, :]
        pm._mat = _pairwise_matrix(data, axis=1, pt=pm.pti)
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
        other._dtype = self._dtype
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
        indexes = [int(index) for index in featurescols_index]
        other = DataMatrix()
        other._dtype = self._dtype
        other._data = self._data[:, indexes].copy()
        other._featuresnames_index = [self._featuresnames_index[i] for i in indexes]
        other._featuresnames = {
            other._featuresnames_index[i]: i
            for i in range(len(other._featuresnames_index))
        }
        other._feids = [self._feids[i] for i in indexes]
        other._trueids = [-1 for _ in self._trueids]
        for shifted, index in enumerate(other._feids):
            if 0 <= index < len(other._trueids):
                other._trueids[index] = shifted
        return other

    def selectrows(self, idrows):
        other = DataMatrix()
        other._dtype = self._dtype
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

    def getcolumn_array(self, c, copy=True):
        column = self._data[:, c]
        return column.copy() if copy else column

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


def _clean_feature_ids(ids, n_features):
    clean = []
    seen = set()
    for raw in ids or []:
        try:
            index = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= index < n_features and index not in seen:
            clean.append(index)
            seen.add(index)
    return clean


def _pairwise_matrix(data, axis, pt):
    vectors = data if axis == 0 else data.T
    vectors = np.asarray(vectors, dtype=np.float64, order="C")
    n = vectors.shape[0]

    if n == 0:
        return np.zeros((0, 0), dtype=float)

    matrix = _compute_pairwise(vectors, pt)
    np.fill_diagonal(matrix, 0.0)

    upper = matrix[np.triu_indices(n, k=1)]
    if upper.size == 0:
        return matrix

    minv = float(upper.min())
    maxv = float(upper.max())
    denom = EPS + (maxv - minv)
    coeff = ProximityMatrix.CEF[_pt_name(pt)]
    matrix = (matrix - minv) / denom
    if coeff == -1:
        matrix = 1.0 - matrix
    np.fill_diagonal(matrix, 0.0)
    return matrix


def _compute_pairwise(vectors, pt):
    if pt == 0:  # Euclidean
        sq = (vectors ** 2).sum(axis=1)
        dots = vectors @ vectors.T
        return np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2.0 * dots, 0.0))

    if pt == 5:  # Cosine similarity
        norms = np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), EPS)
        n = vectors / norms
        return n @ n.T

    if pt == 6:  # Pearson correlation
        c = vectors - vectors.mean(axis=1, keepdims=True)
        norms = np.maximum(np.linalg.norm(c, axis=1, keepdims=True), EPS)
        n = c / norms
        return n @ n.T

    if pt == 7:  # Gaussian (RBF)
        sq = (vectors ** 2).sum(axis=1)
        dots = vectors @ vectors.T
        sq_dists = np.maximum(sq[:, None] + sq[None, :] - 2.0 * dots, 0.0)
        return np.exp(-sq_dists / 0.5)

    if pt == 8:  # Sample correlation
        d = float(vectors.shape[1])
        s = vectors.sum(axis=1, keepdims=True)
        s2 = (vectors ** 2).sum(axis=1, keepdims=True)
        dots = vectors @ vectors.T
        num = d * dots - s * s.T
        var = np.maximum(d * s2 - s ** 2, 0.0)
        return num / np.maximum(np.sqrt(var * var.T), EPS)

    if pt == 9:  # DCosine
        norms = np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), EPS)
        n = vectors / norms
        return 1.0 - (1.0 + n @ n.T) / 2.0

    # pt=1 (Manhattan), pt=2 (Canberra), pt=3 (Chebyshev), pt=4 (Braycurtis)
    try:
        from scipy.spatial.distance import cdist
        metric_map = {1: "cityblock", 2: "canberra", 3: "chebyshev", 4: "braycurtis"}
        if pt in metric_map:
            return cdist(vectors, vectors, metric=metric_map[pt])
    except ImportError:
        pass

    # Pure Python fallback for any unhandled metric
    nv = vectors.shape[0]
    matrix = np.zeros((nv, nv), dtype=float)
    for i in range(nv):
        for j in range(i + 1, nv):
            d = _proximity(vectors[i], vectors[j], pt)
            matrix[i, j] = d
            matrix[j, i] = d
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
