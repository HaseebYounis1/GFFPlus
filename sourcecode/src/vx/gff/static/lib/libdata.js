/*
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br
*/


/**
 * Making initial objects
 */


/**
 * Auxiliar methods
 */
function DataIO() {
    var data = {
        "argms": {}
    };
    return data;
}

/* 
function showloading(text) {
    gelem("idloading").style.display = "block";
    gelem("idloadingtxt").innerHTML = text+" ...";
}
function showstatus(load) {
    gelem("idloadingload").style.width = load+"%";
    //gelem("idloadingload").innerHTML = size;
}
function hideloading() {
    gelem('idloading').style.display = "none";
}
 */


/**
 * Claass: SevcieData
 */
function ServiceData(pname) {
    var self = this;
    this.in = new DataIO();
    this.ou = '';

    this.event = function () { };
    
    this.start = function () {
        var ps = MOPRO.pushprocess(pname);
        try {
            fetch("./query", {
                method: "POST",
                credentials: "same-origin",
                headers: {"Content-Type": "application/x-www-form-urlencoded",
                          "X-XSRFToken": document.querySelector('meta[name="xsrf-token"]').content},
                body: new URLSearchParams({data: JSON.stringify(self.in)}).toString()
            }).then(function (response) {
                if (!response.ok) throw new Error("Request failed: " + response.status + " " + response.statusText);
                return response.json();
            }).then(function (data) {
                self.ou = data;
                self.event();
            }).catch(function (err) {
                self.ou = {status: "error", statusopt: 2, message: err.message};
                console.error(pname, err);
                try { self.event(); } catch (eventError) { console.error(eventError); }
            }).finally(function () { MOPRO.popprocess(ps); });
        }
        catch (err) {
            MOPRO.popprocess(ps);
            console.log(err);
        }
    };
}


/**
 * Claass: Graph From Features
 */
function GraphFromFeatures() {
    let self = this;
    this.datax = {}

    this.listinstances = [
        {
            "collect":"instances",
            "query":    [
                            ["configinstance"],
                            ["typeinstance"],
                            ["layoutinstance"],
                            ["versioninstance"],
                        ]
        }
    ];

    
    this.listfeatures = [
        {
            "collect":"features",
            "query":    [
                            ["configfeature"],
                            ["typefeature"],
                            ["versionfeature"],
                            ["featurecheck"],

                            ["layoutfeature","root"],
                            ["layoutfeature","ranking"],
                            ["layoutfeature","rankingmin"],
                            ["layoutfeature","rankingmax"],
                            ["layoutfeature","initvertex1"],
                            ["layoutfeature","initvertex2"],
                            ["layoutfeature","tree"],
                            ["layoutfeature","treehi"],
                            ["layoutfeature","edgehist"],
                            ["typexai"],
                            ["versionxai"],
                            ["layoutxai"]
                        ]
        },

        {
            "collect":"features",
            "query":    [
                            ["layoutfeature","graph","nodes"]
                        ]
        },

        {
            "collect":"features",
            "query":    [
                            ["layoutfeature","graph","links"]
                        ]
        },

        {
            "collect":"features",
            "query":    [
                            ["layoutfeature","graph","whole"]
                        ]
        },

    ];
    

    this.listbase = [
                            {
                                "collect":"features",
                                "query":    [

                                                ["fenames"],
                                                ["lastversion"],
                                                    
                                                ["_id"],
                                                ["name"],
                                                ["type"],

                                                /* features */
                                                /* instances */

                                                ["datecreate"],
                                                ["dateupdate"],
                                                ["hasupdate"],
                                                ["isshare"],
                                                ["sampling"],
                                                
                                                ["statusopt"],
                                                ["statusval"],
                                                
                                                ["_id_user"]
                                            ]
                            },

                        ];

    this.listdataset = this.listbase.concat(this.listfeatures, this.listinstances);
    this.listdataset_count = 0;
    this.datagff = {};

    //console.log("this.listdataset", this.listdataset);



    this.mw = new ModalWindow();
    this.USFOBJ = new UnselectedFeatures("idselectedfebt","idunselectedfecont",self);
        
    this.adminid = 0;
    this.email = "";
    this.multiuser = 0;

    this.layoutfeatures = null;
    this.layoutinstance = null;

    this.dataload = [];
    this.dataloadfile = "";
    this.dataloadcallbacks = [];
    this.isloadingcsv = false;
    this.datafiles = [];
    this.featureselected = [];
    //this.ranking = [];
    this.datafileselected = "";
    this.datafileselectedname = "";
    this.computeResponsivePanelDimensions = function () {
        var vw = document.documentElement.clientWidth || window.innerWidth || 1280;
        var vh = window.innerHeight || document.documentElement.clientHeight || 800;
        var wsCell = gelem("gffWorkspaceCell");
        var availW = vw - 64;
        var topOffset = 46;
        if (wsCell) {
            var rect = wsCell.getBoundingClientRect();
            if (wsCell.clientWidth > 200) {
                availW = wsCell.clientWidth - 16; // 8px left + 8px right padding
            } else if (rect.left > 0) {
                availW = vw - rect.left - 16;
            }
            if (rect.top > 0) {
                topOffset = Math.ceil(rect.top);
            }
        }
        // Per panel horizontal chrome: 20px left strip + 26px right strip + 6px border + 6px padding = 58px (2x = 116px)
        // Plus 8px flex gap between panels + 4px safety margin = 128px
        var width = Math.max(320, Math.floor((availW - 128) / 2));

        // Vertical fit: keep BOTH panels AND the bottom dock (Contrastive & Counterfactual Subspace Inspector)
        // 100% visible inside the viewport without scrolling down.
        var availH = Math.max(460, vh - topOffset - 12); // 6px top + 6px bottom cell padding
        var dockHeight = Math.max(135, Math.min(185, Math.floor(availH * 0.22)));
        // Panel vertical chrome: 18px header + 36px controls + 6px padding + 6px border + 30px bottom bar + 8px dock margin = 104px
        var height = Math.max(280, Math.floor(availH - 104 - dockHeight));
        return { width: width, height: height, dockHeight: dockHeight };
    };
    this.computeStablePanelSize = function () {
        return self.computeResponsivePanelDimensions().width;
    };
    var _initialDims = this.computeResponsivePanelDimensions();
    this.lwidth = _initialDims.width;
    this.lheight = _initialDims.height;
    this.ldockheight = _initialDims.dockHeight;
    this._resizeTimer = null;

    this.isnamedbedited = false;
    this.intarget = false;
    this.exchageslider = 0;
    this.intargetaction = false;
    this.target = "";
    this.lfenamesindex = {};
    //this.lfenames = []
    //this.dataoutfeature = null;
    //this.dataoutinstance = null;
    this.edgetransparency = 0.75;

    this.instvertexratio = 4;
    this.instvertexoacity = 0.75;


    this.ispresskey = 3;
    this.keepselectvertex = -1;

    this.colorstableshitttype = -1;

    
    // new attributes
    this.unselectedfeids = [];
    this.idinstancelabel = {};
    this.csvFileLabels = {};
    this.csvFileColumnName = "";
    this._spacePanActive = false;
    this._ctrlPanActive = false;
    this.pointFiles = {};
    this.pointFileList = [];
    this.activePointId = null;
    
    this.auxfeatureselectedf = {};
    this.auxfeatureselectedi = {};


    this.featuresChecks = [];
    this.featuresChecks_count = 0;
    this.featureSelectionTimer = null;
    this.xaiColorMode = "graph";
    this.xaiSizeMode = "graph";
    this.xaiThreshold = 0.0;
    this.contrastiveData = null;
    this.perturbationPreview = null;
    this.showFidelityHalo = false;

/*     this.featuresChecks = [];
    this.featuresChecks_count = 0; */

    this.makeFeatureAux = function(nodes){
        var rest = {};
        for(var e of nodes){
            if (e.category == 1 || e.label === undefined || e.label === null || e.label < 0) {
                continue;
            }
            rest[e.label] = e.name;
        }
        return rest;
    };

    this.normalizeFeatureSelection = function () {
        var seen = {};
        var clean = [];
        for (var id of self.featureselected) {
            id = parseInt(id, 10);
            if (!isNaN(id) && !seen[id]) {
                seen[id] = 1;
                clean.push(id);
            }
        }
        self.featureselected = clean;
    };

    this.selectFeatureIds = function (ids, mode) {
        ids = (ids || []).map(function (id) {
            return parseInt(id, 10);
        }).filter(function (id) {
            return !isNaN(id);
        });
        if (ids.length == 0) {
            return;
        }

        var selected = {};
        for (var id of self.featureselected) {
            selected[parseInt(id, 10)] = 1;
        }

        if (mode == "add") {
            for (var id of ids) {
                selected[id] = 1;
            }
        }
        else if (mode == "remove") {
            for (var id of ids) {
                delete selected[id];
            }
        }
        else {
            selected = {};
            for (var id of ids) {
                selected[id] = 1;
            }
        }

        var taindex = self.auxfeatureselectedf[self.target];
        if (taindex !== undefined) {
            var nonTargetCount = Object.keys(selected).filter(function (id) {
                return parseInt(id, 10) != taindex;
            }).length;
            if (self.intarget && nonTargetCount > 0) {
                selected[taindex] = 1;
            }
            else if (nonTargetCount == 0) {
                delete selected[taindex];
            }
        }

        self.featureselected = Object.keys(selected).map(function (id) {
            return parseInt(id, 10);
        });
        self.normalizeFeatureSelection();
    };

    this.onFeatureSelectionChanged = function (options) {
        options = options || {};
        self.normalizeFeatureSelection();
        self.renderXAISelectedSummary();

        if (self.layoutfeatures != null && !options.skipFeatureHighlight) {
            self.layoutfeatures.highlightforce(self.featureselected, {"silent": true});
                            self.applyPanModeState("features");
        }

        if (gvalue('projection') == "simple" && !gvalue("submodular_size")) {
            if (self.dataload && self.dataload.length > 0) {
                self.plotpaiercorrelate();
            }
            else if (self.datafileselected != "") {
                self.loadfilecsv(function () {
                    self.plotpaiercorrelate();
                });
            }
            return;
        }

        if (self.datafileselected == "" || self.featureselected.length < 2) {
            self.setProjectionPanelStatus(
                "Projection unavailable",
                "Select at least two features from any feature graph"
            );
            return;
        }

        var projection = gvalue('projection');
        if (projection != "pca") {
            gelem("topleft2").innerHTML = "Projection ready";
            gelem("topright2").innerHTML = "Press execute to update " + projection.toUpperCase();
            return;
        }

        if (self.featureSelectionTimer) {
            clearTimeout(self.featureSelectionTimer);
        }
        self.featureSelectionTimer = setTimeout(function () {
            self.featureSelectionTimer = null;
            self.visInstnaces();
        }, 700);
    };

    this.makeInstancesLabels = function(colname){
        if (colname === "" || colname === null || colname === undefined) {
            self.idinstancelabel = {};
            if (self.pointFileList.length > 0) {
                self.rebindPointFilesToCurrentPoints();
            }
            return;
        }
        if (self.datafileselected != ""){
            var ob = new ServiceData("compute instances labels");
            ob.in.argms["type"] = 21;
            ob.in.argms["file"] = self.datafileselected;
            ob.in.argms["idinstanceslabels"] = parseInt(colname, 10);
            ob.in.argms["maxlabels"] = 5000;

            ob.event = function () {
                self.idinstancelabel = this.ou || {};
                if (self.pointFileList.length > 0) {
                    self.rebindPointFilesToCurrentPoints();
                }
            };
            ob.start();
        }
    };

    this.getPointFile = function(id){
        if (self.pointFiles && Object.prototype.hasOwnProperty.call(self.pointFiles, String(id))) {
            return self.pointFiles[String(id)];
        }
        return null;
    };

    this.getInstanceLabel = function(id){
        var pf = self.getPointFile(id);
        if (pf && pf.name) {
            return pf.name;
        }
        if (self.idinstancelabel && self.idinstancelabel[String(id)] !== undefined && self.idinstancelabel[String(id)] !== "") {
            return self.idinstancelabel[String(id)];
        }
        return id;
    };

    this.autoLoadCsvFileLabels = function () {
        self.csvFileLabels = {};
        self.csvFileColumnName = "";
        var names = (self.datagff && Array.isArray(self.datagff.fenames)) ? self.datagff.fenames : [];
        if (!self.datafileselected || names.length === 0) return;
        var fileColIdx = -1;
        var strictRe = /^(file|filename|file_name|filepath|file_path|media_file|image_file|audio_file|doc_file)$/i;
        var softRe = /^(image|img|audio|sound|video|document|doc|media|path)$/i;
        for (var i = 0; i < names.length; ++i) {
            if (strictRe.test(String(names[i] || "").trim())) {
                fileColIdx = i;
                break;
            }
        }
        if (fileColIdx < 0) {
            for (var j = 0; j < names.length; ++j) {
                if (softRe.test(String(names[j] || "").trim())) {
                    fileColIdx = j;
                    break;
                }
            }
        }
        if (fileColIdx < 0) return;
        self.csvFileColumnName = String(names[fileColIdx]);
        var ob = new ServiceData("loading file column");
        ob.in.argms["type"] = 21;
        ob.in.argms["file"] = self.datafileselected;
        ob.in.argms["idinstanceslabels"] = String(fileColIdx);
        ob.event = function () {
            if (this.ou && typeof this.ou === "object") {
                self.csvFileLabels = this.ou;
                if (self.pointFileList && self.pointFileList.length > 0) {
                    self.rebindPointFilesToCurrentPoints();
                }
            }
        };
        ob.start();
    };

    this.getExportInstanceName = function(id){
        var sid = String(id);
        if (self.csvFileLabels && self.csvFileLabels[sid] !== undefined && String(self.csvFileLabels[sid]).trim() !== "") {
            return String(self.csvFileLabels[sid]).replace(/[;\r\n]+/g, "_").trim();
        }
        var pf = self.getPointFile(id);
        if (pf && pf.name) {
            return String(pf.name).replace(/[;\r\n]+/g, "_").trim();
        }
        if (self.csvFileColumnName && Array.isArray(self.dataload) && self.dataload.length > 0) {
            var rIdx = Array.isArray(self.dataloadids) ? self.dataloadids.indexOf(parseInt(id, 10)) : parseInt(id, 10);
            var row = (rIdx >= 0 && self.dataload[rIdx]) ? self.dataload[rIdx] : self.dataload[parseInt(id, 10)];
            if (row && row[self.csvFileColumnName] !== undefined && String(row[self.csvFileColumnName]).trim() !== "") {
                return String(row[self.csvFileColumnName]).replace(/[;\r\n]+/g, "_").trim();
            }
        }
        if (self.idinstancelabel && self.idinstancelabel[sid] !== undefined && String(self.idinstancelabel[sid]).trim() !== "") {
            return String(self.idinstancelabel[sid]).replace(/[;\r\n]+/g, "_").trim();
        }
        var prefix = sanitizeExportFilename(self.datafileselectedname, "instance");
        return prefix + "_" + id;
    };

    this.panModeFeatures = false;
    this.panModeInstances = false;

    this.applyPanModeState = function (which) {
        var featActive = !!(self.panModeFeatures || self._spacePanActive || self._ctrlPanActive);
        var instActive = !!(self.panModeInstances || self._spacePanActive || self._ctrlPanActive);
        if (which === "features" || !which) {
            var btnF = gelem("btnPanFeatures");
            if (btnF) {
                btnF.classList.toggle("btn-primary", featActive);
                btnF.classList.toggle("btn-light", !featActive);
            }
            if (self.layoutfeatures && self.layoutfeatures.zoomController && self.layoutfeatures.zoomController.setPanMode) {
                self.layoutfeatures.zoomController.setPanMode(featActive);
            }
        }
        if (which === "instances" || !which) {
            var btnI = gelem("btnPanInstances");
            if (btnI) {
                btnI.classList.toggle("btn-primary", instActive);
                btnI.classList.toggle("btn-light", !instActive);
            }
            if (self.layoutinstance && self.layoutinstance.zoomController && self.layoutinstance.zoomController.setPanMode) {
                self.layoutinstance.zoomController.setPanMode(instActive);
            }
        }
    };

    this.togglePanFeatures = function () {
        self.panModeFeatures = !self.panModeFeatures;
        self.applyPanModeState("features");
    };

    this.togglePanInstances = function () {
        self.panModeInstances = !self.panModeInstances;
        self.applyPanModeState("instances");
    };

    this.zoomFeatures = function (direction) {
        if (!self.layoutfeatures) return;
        if (direction === "in" && self.layoutfeatures.zoomIn) {
            self.layoutfeatures.zoomIn();
        } else if (direction === "out" && self.layoutfeatures.zoomOut) {
            self.layoutfeatures.zoomOut();
        } else if (direction === "reset" && self.layoutfeatures.resetZoom) {
            self.layoutfeatures.resetZoom();
        }
    };

    this.zoomInstances = function (direction) {
        if (!self.layoutinstance) return;
        if (direction === "in" && self.layoutinstance.zoomIn) {
            self.layoutinstance.zoomIn();
        } else if (direction === "out" && self.layoutinstance.zoomOut) {
            self.layoutinstance.zoomOut();
        } else if (direction === "reset" && self.layoutinstance.resetZoom) {
            self.layoutinstance.resetZoom();
        }
    };

    this.clearPointFiles = function () {
        for (var i = 0; i < self.pointFileList.length; ++i) {
            if (self.pointFileList[i] && self.pointFileList[i].isObjectUrl && self.pointFileList[i].url) {
                try { URL.revokeObjectURL(self.pointFileList[i].url); } catch (e) {}
            }
        }
        self.pointFiles = {};
        self.pointFileList = [];
        self.activePointId = null;
        var st = gelem("pointfilesstatus");
        if (st) st.textContent = "";
        var clr = gelem("pointfilesclearbtn");
        if (clr) clr.style.display = "none";
        var panel = gelem("pointfilespanel");
        if (panel) {
            panel.style.display = "none";
            panel.innerHTML = "";
        }
    };

    this._classifyMediaEntry = function (name, url, opts) {
        opts = opts || {};
        var mime = String(opts.type || "").toLowerCase();
        var lower = String(name || "").toLowerCase();
        var stem = String(name || "").replace(/\.[^/.]+$/, "");
        return {
            file: opts.file || null,
            name: name,
            stem: stem,
            lowerName: lower,
            lowerStem: stem.toLowerCase(),
            url: url,
            isObjectUrl: !!opts.isObjectUrl,
            type: mime,
            size: opts.size || 0,
            isImage: mime.indexOf("image/") === 0 || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(lower),
            isAudio: mime.indexOf("audio/") === 0 || /\.(wav|mp3|ogg|flac|m4a)$/i.test(lower),
            isVideo: mime.indexOf("video/") === 0 || /\.(mp4|webm|ogv|mov)$/i.test(lower),
            isPdf: mime === "application/pdf" || /\.pdf$/i.test(lower),
            isText: mime.indexOf("text/") === 0 || mime === "application/json" || /\.(txt|csv|tsv|json|md|xml|log|yaml|yml|html?|rst|tex|srt|vtt)$/i.test(lower),
            textPreview: null
        };
    };

    this.loadPointFiles = function (fileList) {
        if (!fileList || fileList.length === 0) {
            return;
        }
        self.clearPointFiles();
        var entries = [];
        for (var i = 0; i < fileList.length; ++i) {
            var f = fileList[i];
            if (!f || !f.name) continue;
            entries.push(self._classifyMediaEntry(f.name, URL.createObjectURL(f), {
                file: f,
                type: f.type,
                size: f.size,
                isObjectUrl: true
            }));
        }
        entries.sort(function (a, b) {
            return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
        });
        self.pointFileList = entries;
        self.rebindPointFilesToCurrentPoints();
    };

    this.loadServerPointMedia = function () {
        if (!self.datafileselected) return;
        var ob = new ServiceData("loading dataset point media");
        ob.in.argms["type"] = 29;
        ob.in.argms["file"] = self.datafileselected;
        ob.event = function () {
            if (!this.ou || this.ou.status !== "ok" || !Array.isArray(this.ou.files) || this.ou.files.length === 0) {
                return;
            }
            self.clearPointFiles();
            var entries = this.ou.files.map(function (item) {
                return self._classifyMediaEntry(item.name, item.url, {
                    size: item.size || 0,
                    isObjectUrl: false
                });
            });
            entries.sort(function (a, b) {
                return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
            });
            self.pointFileList = entries;
            self.rebindPointFilesToCurrentPoints();
        };
        ob.start();
    };

    this.uploadPointMediaZip = function (file) {
        if (!file || !self.datafileselected) {
            self.mw.alert("Media Upload", "Open a dataset before uploading point media.");
            return;
        }
        MOPRO.show("Uploading point media files");
        fetch("./upload_media", {
            method: "POST",
            credentials: "same-origin",
            body: file,
            headers: {
                "Content-Type": "application/octet-stream",
                "X-Dataset-Id": self.datafileselected,
                "X-Filename": encodeURIComponent(file.name),
                "X-XSRFToken": document.querySelector('meta[name="xsrf-token"]').content
            }
        }).then(function (response) {
            if (!response.ok) throw new Error("Media upload failed: " + response.status + " " + response.statusText);
            return response.json();
        }).then(function (result) {
            self.loadServerPointMedia();
            self.mw.alert("Media Loaded", "Saved " + (result.saved || 0) + " media file(s) to this dataset.");
        }).catch(function (err) {
            self.mw.alert("Media Upload Error", err.message);
        }).finally(function () {
            MOPRO.hide();
        });
    };

    this.renderAudioWaveform = function (canvasId, url) {
        var canvas = gelem(canvasId);
        if (!canvas || !url || !(window.AudioContext || window.webkitAudioContext)) return;
        fetch(url, { credentials: "same-origin" })
            .then(function (res) { return res.arrayBuffer(); })
            .then(function (buf) {
                var AudioCtx = window.AudioContext || window.webkitAudioContext;
                var ctx = new AudioCtx();
                return ctx.decodeAudioData(buf).then(function (audioBuffer) {
                    try { ctx.close(); } catch (e) {}
                    return audioBuffer;
                });
            })
            .then(function (audioBuffer) {
                var el = gelem(canvasId);
                if (!el) return;
                var c = el.getContext("2d");
                var w = el.width;
                var h = el.height;
                c.fillStyle = "#0f172a";
                c.fillRect(0, 0, w, h);
                var data = audioBuffer.getChannelData(0);
                var step = Math.max(1, Math.floor(data.length / w));
                var mid = h / 2;
                c.strokeStyle = "#38bdf8";
                c.lineWidth = 1.2;
                c.beginPath();
                for (var x = 0; x < w; ++x) {
                    var minV = 1.0, maxV = -1.0;
                    var start = x * step;
                    for (var j = 0; j < step && (start + j) < data.length; ++j) {
                        var v = data[start + j];
                        if (v < minV) minV = v;
                        if (v > maxV) maxV = v;
                    }
                    c.moveTo(x, mid + minV * (mid - 4));
                    c.lineTo(x, mid + maxV * (mid - 4));
                }
                c.stroke();
            })
            .catch(function () {});
    };

    this.closePointDataModal = function () {
        var modal = gelem("pointdatamodal");
        if (!modal) return;
        var mediaEls = modal.querySelectorAll("audio, video");
        for (var i = 0; i < mediaEls.length; ++i) {
            try { mediaEls[i].pause(); } catch (e) {}
        }
        modal.classList.remove("open");
    };

    this.stepPointDataModal = function (delta) {
        var points = (self.datagff && self.datagff.layoutinstance && Array.isArray(self.datagff.layoutinstance.points))
            ? self.datagff.layoutinstance.points : [];
        if (points.length === 0) return;
        var idx = 0;
        for (var i = 0; i < points.length; ++i) {
            if (String(points[i].id) === String(self.activePointId)) {
                idx = i;
                break;
            }
        }
        var nextIdx = (idx + delta + points.length) % points.length;
        self.openPointDataModal(points[nextIdx].id);
    };

    this._activeModalTextRaw = "";

    this._activeInstanceRow = null;

    this._buildOriginalInstanceStageHtml = function (pointId, displayName, pt, targetNames) {
        var clsText = pt ? (targetNames[pt.t] !== undefined ? targetNames[pt.t] : pt.t) : "n/a";
        return "<div style='width:100%; display:flex; flex-direction:column; height:58vh; background:#0f172a; border:1px solid #334155; border-radius:5px; overflow:hidden;'>" +
            "<div style='display:flex; align-items:center; gap:6px; padding:7px 10px; background:#1e293b; border-bottom:1px solid #334155; flex-wrap:wrap;'>" +
                "<span style='font-size:11px; font-weight:700; color:#f8fafc;'><i class='fa fa-table' style='color:#38bdf8; margin-right:5px;'></i>Original Instance #" + self.escapeHTML(pointId) + "</span>" +
                "<span style='font-size:10px; color:#93c5fd;'>" + self.escapeHTML(displayName) + " · Target: " + self.escapeHTML(clsText) + "</span>" +
                "<input id='pdmFeatureFilter' type='text' placeholder='Filter features...' oninput='GFFOBJ.filterOriginalInstanceFeatures(this.value);' style='margin-left:auto; width:130px; height:22px; font-size:10px; padding:2px 6px; border-radius:3px; border:1px solid #475569; background:#0f172a; color:#f8fafc;'>" +
                "<button type='button' class='btn btn-outline-info btn-sm' style='padding:1px 6px; font-size:10px;' onclick='gelem(\"pointfilesinput\").click();' title='Attach files'><i class='fa fa-file-upload'></i></button>" +
                "<button type='button' class='btn btn-outline-warning btn-sm' style='padding:1px 6px; font-size:10px;' onclick='gelem(\"pointmediazipinput\").click();' title='Upload media ZIP'><i class='fa fa-file-archive'></i></button>" +
            "</div>" +
            "<div id='pdmOriginalFeatureTable' style='flex:1 1 auto; overflow:auto; padding:8px 10px; text-align:left;'>" +
                "<div style='color:#94a3b8; font-size:11px; padding:12px;'>Loading original instance values...</div>" +
            "</div>" +
        "</div>";
    };

    this._findFeatureRowForPoint = function (pointId) {
        if (!Array.isArray(self.dataload) || self.dataload.length === 0) return null;
        if (Array.isArray(self.dataloadids)) {
            var pos = self.dataloadids.indexOf(parseInt(pointId, 10));
            if (pos >= 0 && self.dataload[pos]) return self.dataload[pos];
        }
        var idx = parseInt(pointId, 10);
        if (!isNaN(idx) && self.dataload[idx]) return self.dataload[idx];
        return null;
    };

    this._renderOriginalInstanceTable = function (pointId, filterQuery) {
        var container = gelem("pdmOriginalFeatureTable");
        if (!container) return;
        var row = self._findFeatureRowForPoint(pointId);
        self._activeInstanceRow = row;
        if (!row) {
            container.innerHTML = "<div style='color:#94a3b8; font-size:11px; padding:12px;'>Original CSV row is not available for this point.</div>";
            return;
        }
        var selectedNames = {};
        var selIds = self.getfeatureselected();
        var feNames = (self.datagff && Array.isArray(self.datagff.fenames)) ? self.datagff.fenames : [];
        for (var s = 0; s < selIds.length; ++s) {
            if (feNames[selIds[s]] !== undefined) selectedNames[feNames[selIds[s]]] = true;
        }
        var q = String(filterQuery || "").trim().toLowerCase();
        var cols = Object.keys(row);
        var html = "<table style='width:100%; border-collapse:collapse; font-size:11px; color:#e2e8f0;'>" +
            "<thead><tr style='border-bottom:1px solid #334155; color:#94a3b8; text-align:left;'>" +
            "<th style='padding:4px 6px;'>Feature Name</th><th style='padding:4px 6px; text-align:right;'>Original Value</th></tr></thead><tbody>";
        var shown = 0;
        for (var i = 0; i < cols.length; ++i) {
            var col = cols[i];
            var val = row[col];
            if (q && col.toLowerCase().indexOf(q) < 0 && String(val).toLowerCase().indexOf(q) < 0) {
                continue;
            }
            var isSel = !!selectedNames[col];
            var bg = isSel ? "rgba(56,189,248,0.12)" : (shown % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent");
            var badge = isSel ? " <span style='background:#0284c7; color:#fff; font-size:9px; padding:0 4px; border-radius:2px; margin-left:4px;'>selected</span>" : "";
            html += "<tr style='background:" + bg + "; border-bottom:1px solid #1e293b;'>" +
                "<td style='padding:4px 6px; font-weight:" + (isSel ? "600" : "400") + "; color:" + (isSel ? "#f8fafc" : "#cbd5e1") + ";'>" + self.escapeHTML(col) + badge + "</td>" +
                "<td style='padding:4px 6px; text-align:right; font-family:monospace; color:#fde68a;'>" + self.escapeHTML(val) + "</td></tr>";
            shown++;
        }
        html += "</tbody></table>";
        if (shown === 0) {
            html = "<div style='color:#94a3b8; font-size:11px; padding:12px;'>No matching features found.</div>";
        }
        container.innerHTML = html;
    };

    this.filterOriginalInstanceFeatures = function (query) {
        if (self.activePointId !== null && self.activePointId !== undefined) {
            self._renderOriginalInstanceTable(self.activePointId, query);
        }
    };

    this.getInlineTextForPoint = function (pointId, featureRow) {
        var candidates = [];
        var rawLbl = String(self.getInstanceLabel(pointId) || "").trim();
        if (rawLbl.length >= 24 && !/^(https?:\/\/|data:)/i.test(rawLbl) && rawLbl.indexOf(" ") >= 0) {
            candidates.push({ label: "Selected Label Column", text: rawLbl });
        }
        if (featureRow && typeof featureRow === "object") {
            var preferred = /^(text|document|doc|abstract|review|content|body|article|message|description|snippet|comment|title|headline|notes?|summary|transcript)$/i;
            var keys = Object.keys(featureRow);
            for (var i = 0; i < keys.length; ++i) {
                var k = keys[i];
                var v = String(featureRow[k] === undefined || featureRow[k] === null ? "" : featureRow[k]).trim();
                if (!v) continue;
                if (preferred.test(k) && v.length >= 8 && isNaN(Number(v))) {
                    candidates.unshift({ label: k, text: v });
                } else if (v.length >= 40 && isNaN(Number(v)) && v.indexOf(" ") >= 0) {
                    candidates.push({ label: k, text: v });
                }
            }
        }
        return candidates.length > 0 ? candidates[0] : null;
    };

    this.renderPointTextDocument = function (rawText, fileName, sourceLabel) {
        var textStr = String(rawText === undefined || rawText === null ? "" : rawText);
        if (fileName && /\.json$/i.test(fileName)) {
            try {
                textStr = JSON.stringify(JSON.parse(textStr), null, 2);
            } catch (e) {}
        }
        self._activeModalTextRaw = textStr;
        var pre = gelem("pdmTextContent");
        var statsEl = gelem("pdmTextStats");
        var matchEl = gelem("pdmTextMatchCount");
        if (statsEl) {
            var trimmed = textStr.trim();
            var words = trimmed ? trimmed.split(/\s+/).length : 0;
            var lines = textStr ? textStr.split(/\r?\n/).length : 0;
            var badge = sourceLabel ? (sourceLabel + " · ") : "";
            statsEl.textContent = badge + words + " words · " + textStr.length + " chars · " + lines + " lines";
        }
        if (matchEl) {
            matchEl.textContent = "";
        }
        if (pre) {
            pre.textContent = textStr;
        }
    };

    this.filterPointTextSearch = function (query) {
        var pre = gelem("pdmTextContent");
        var matchEl = gelem("pdmTextMatchCount");
        if (!pre) return;
        var raw = self._activeModalTextRaw || "";
        var q = String(query || "").trim();
        if (!q) {
            pre.textContent = raw;
            if (matchEl) matchEl.textContent = "";
            return;
        }
        var escapedQ = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        var re = new RegExp(escapedQ, "gi");
        var count = 0;
        var parts = [];
        var lastIdx = 0;
        var m;
        while ((m = re.exec(raw)) !== null) {
            if (m.index > lastIdx) {
                parts.push(self.escapeHTML(raw.slice(lastIdx, m.index)));
            }
            parts.push("<mark style='background:#facc15; color:#0f172a; padding:0 2px; border-radius:2px;'>" + self.escapeHTML(m[0]) + "</mark>");
            count++;
            lastIdx = m.index + m[0].length;
            if (m[0].length === 0) {
                re.lastIndex++;
            }
        }
        if (lastIdx < raw.length) {
            parts.push(self.escapeHTML(raw.slice(lastIdx)));
        }
        pre.innerHTML = parts.join("");
        if (matchEl) {
            matchEl.textContent = count + (count === 1 ? " match" : " matches");
        }
    };

    this.togglePointTextWrap = function () {
        var pre = gelem("pdmTextContent");
        if (!pre) return;
        var isWrapped = pre.style.whiteSpace !== "pre";
        pre.style.whiteSpace = isWrapped ? "pre" : "pre-wrap";
    };

    this.copyPointTextContent = function () {
        var raw = self._activeModalTextRaw || "";
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(raw).catch(function () {});
        }
    };

    this._buildTextReaderHtml = function (headerLabel) {
        return "<div style='width:100%; display:flex; flex-direction:column; height:58vh; background:#0f172a; border:1px solid #334155; border-radius:5px; overflow:hidden;'>" +
            "<div style='display:flex; align-items:center; gap:6px; padding:6px 8px; background:#1e293b; border-bottom:1px solid #334155; flex-wrap:wrap;'>" +
                "<span style='font-size:11px; font-weight:600; color:#e2e8f0;'><i class='fa fa-file-alt' style='color:#38bdf8; margin-right:4px;'></i>" + self.escapeHTML(headerLabel || "Document") + "</span>" +
                "<span id='pdmTextStats' style='font-size:10px; color:#94a3b8; margin-right:auto;'></span>" +
                "<input id='pdmTextSearch' type='text' placeholder='Search text...' oninput='GFFOBJ.filterPointTextSearch(this.value);' style='width:130px; height:22px; font-size:10px; padding:2px 6px; border-radius:3px; border:1px solid #475569; background:#0f172a; color:#f8fafc;'>" +
                "<span id='pdmTextMatchCount' style='font-size:10px; color:#facc15;'></span>" +
                "<button type='button' class='btn btn-outline-light btn-sm' style='padding:1px 6px; font-size:10px;' onclick='GFFOBJ.togglePointTextWrap();' title='Toggle word wrap'>Wrap</button>" +
                "<button type='button' class='btn btn-outline-info btn-sm' style='padding:1px 6px; font-size:10px;' onclick='GFFOBJ.copyPointTextContent();' title='Copy document text'><i class='fa fa-copy'></i></button>" +
            "</div>" +
            "<pre id='pdmTextContent' style='flex:1 1 auto; width:100%; overflow:auto; text-align:left; background:#0f172a; color:#e2e8f0; padding:12px 14px; font-size:12px; line-height:1.55; white-space:pre-wrap; word-break:break-word; margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;'>Loading document...</pre>" +
        "</div>";
    };

    this.openPointDataModal = function (pointId) {
        self.activePointId = pointId;
        if (self.layoutinstance && self.layoutinstance.focusPoint) {
            self.layoutinstance.focusPoint(pointId);
        }
        var modal = gelem("pointdatamodal");
        var stage = gelem("pdmMediaStage");
        var sidebar = gelem("pdmSidebar");
        var titleEl = gelem("pdmTitle");
        var openLink = gelem("pdmOpenLink");
        if (!modal || !stage || !sidebar) return;

        var points = (self.datagff && self.datagff.layoutinstance && Array.isArray(self.datagff.layoutinstance.points))
            ? self.datagff.layoutinstance.points : [];
        var targetNames = (self.datagff && self.datagff.layoutinstance && self.datagff.layoutinstance.tartegsnames)
            ? self.datagff.layoutinstance.tartegsnames : {};
        var pt = null;
        for (var i = 0; i < points.length; ++i) {
            if (String(points[i].id) === String(pointId)) {
                pt = points[i];
                break;
            }
        }

        var pf = self.getPointFile(pointId);
        if (!pf) {
            var rawLbl = String(self.getInstanceLabel(pointId) || "").trim();
            if (/^(https?:\/\/|data:image\/|data:audio\/|data:video\/)/i.test(rawLbl)) {
                pf = self._classifyMediaEntry(rawLbl.split("/").pop() || ("point_" + pointId), rawLbl, { isObjectUrl: false });
            }
        }

        var displayName = pf ? pf.name : self.getExportInstanceName(pointId);
        if (titleEl) {
            titleEl.textContent = displayName + "  (Point #" + pointId + ")";
        }
        if (openLink) {
            if (pf && pf.url) {
                openLink.href = pf.url;
                openLink.style.display = "inline-block";
            } else {
                openLink.style.display = "none";
            }
        }

        var stageHtml = "";
        if (pf && pf.url) {
            if (pf.isImage) {
                stageHtml = "<img src='" + pf.url + "' alt='" + self.escapeHTML(pf.name) + "' onclick='this.classList.toggle(\"zoomed\");' title='Click to toggle zoom'>" +
                    "<div style='margin-top:6px; font-size:10px; color:#94a3b8;'>" + self.escapeHTML(pf.name) + " (click image to zoom)</div>";
            } else if (pf.isAudio) {
                stageHtml = "<canvas id='pdmWaveformCanvas' width='420' height='120' style='width:100%; max-width:440px; height:120px; border:1px solid #334155; border-radius:4px; margin-bottom:10px;'></canvas>" +
                    "<audio controls autoplay src='" + pf.url + "' style='width:100%; max-width:440px;'></audio>" +
                    "<div style='margin-top:6px; font-size:11px; color:#cbd5e1;'>" + self.escapeHTML(pf.name) + "</div>";
            } else if (pf.isVideo) {
                stageHtml = "<video controls autoplay src='" + pf.url + "' style='max-width:100%; max-height:60vh; border-radius:4px;'></video>" +
                    "<div style='margin-top:6px; font-size:11px; color:#cbd5e1;'>" + self.escapeHTML(pf.name) + "</div>";
            } else if (pf.isPdf) {
                stageHtml = "<iframe src='" + pf.url + "' style='width:100%; height:58vh; border:none; background:#fff; border-radius:3px;'></iframe>";
            } else if (pf.isText) {
                stageHtml = self._buildTextReaderHtml(pf.name);
            } else {
                stageHtml = "<div style='text-align:center; padding:24px;'>" +
                    "<i class='fa fa-file fa-4x' style='color:#64748b; margin-bottom:10px;'></i>" +
                    "<div style='font-size:13px; font-weight:600;'>" + self.escapeHTML(pf.name) + "</div>" +
                    "<a href='" + pf.url + "' target='_blank' rel='noopener' class='btn btn-info btn-sm' style='margin-top:10px;'>Open / Download File</a></div>";
            }
        } else {
            var fallbackRow = null;
            if (Array.isArray(self.dataload) && self.dataload.length > 0) {
                if (Array.isArray(self.dataloadids)) {
                    var fPos = self.dataloadids.indexOf(parseInt(pointId, 10));
                    if (fPos >= 0 && self.dataload[fPos]) fallbackRow = self.dataload[fPos];
                }
                if (!fallbackRow && self.dataload[parseInt(pointId, 10)]) {
                    fallbackRow = self.dataload[parseInt(pointId, 10)];
                }
            }
            var inlineDoc = self.getInlineTextForPoint(pointId, fallbackRow);
            if (inlineDoc) {
                stageHtml = self._buildTextReaderHtml(inlineDoc.label);
            } else {
                stageHtml = self._buildOriginalInstanceStageHtml(pointId, displayName, pt, targetNames);
            }
        }
        stage.innerHTML = stageHtml;

        var sideHtml = "";
        var clsText = pt ? (targetNames[pt.t] !== undefined ? targetNames[pt.t] : pt.t) : "n/a";
        var fidText = (pt && pt.fidelity !== undefined) ? (Math.round(parseFloat(pt.fidelity) * 100) + "%") : "n/a";
        sideHtml += "<div class='pdm-section'><h6>Point Metadata</h6>" +
            "<div><b>Point ID:</b> " + self.escapeHTML(pointId) + "</div>" +
            "<div><b>File / Label:</b> " + self.escapeHTML(displayName) + "</div>" +
            "<div><b>Class / Target:</b> " + self.escapeHTML(clsText) + "</div>" +
            (pt ? ("<div><b>2D Projection:</b> (" + Number(pt.x).toFixed(4) + ", " + Number(pt.y).toFixed(4) + ")</div>") : "") +
            "<div><b>k-NN Fidelity:</b> " + self.escapeHTML(fidText) + "</div>" +
            "</div>";

        if (pt && points.length > 1) {
            var neighbors = [];
            for (var n = 0; n < points.length; ++n) {
                var other = points[n];
                if (String(other.id) === String(pointId)) continue;
                var d2 = Math.hypot(other.x - pt.x, other.y - pt.y);
                neighbors.push({ pt: other, dist: d2 });
            }
            neighbors.sort(function (a, b) { return a.dist - b.dist; });
            neighbors = neighbors.slice(0, 8);
            sideHtml += "<div class='pdm-section'><h6>Nearest Projected Neighbors</h6>";
            for (var k = 0; k < neighbors.length; ++k) {
                var nb = neighbors[k].pt;
                var nbName = self.getInstanceLabel(nb.id);
                var nbCls = targetNames[nb.t] !== undefined ? targetNames[nb.t] : nb.t;
                sideHtml += "<div class='pdm-neighbor-row' onclick='GFFOBJ.openPointDataModal(" + JSON.stringify(nb.id) + ");'>" +
                    "<span style='overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:180px;' title='" + self.escapeHTML(nbName) + "'>" + self.escapeHTML(nbName) + "</span>" +
                    "<span style='color:#475569; font-size:10px;'>" + self.escapeHTML(nbCls) + " · d=" + neighbors[k].dist.toFixed(2) + "</span>" +
                    "</div>";
            }
            sideHtml += "</div>";
        }

        var featureRow = null;
        if (Array.isArray(self.dataload) && self.dataload.length > 0) {
            if (Array.isArray(self.dataloadids)) {
                var pos = self.dataloadids.indexOf(parseInt(pointId, 10));
                if (pos >= 0 && self.dataload[pos]) {
                    featureRow = self.dataload[pos];
                }
            }
            if (!featureRow && self.dataload[parseInt(pointId, 10)]) {
                featureRow = self.dataload[parseInt(pointId, 10)];
            }
        }
        if (featureRow) {
            var selectedIds = self.getfeatureselected();
            var namesToShow = selectedIds.length > 0
                ? selectedIds.slice(0, 8).map(function (fid) { return self.datagff.fenames[fid]; }).filter(Boolean)
                : Object.keys(featureRow).slice(0, 8);
            sideHtml += "<div class='pdm-section'><h6>Feature Values (Active / Sample)</h6><table style='width:100%; font-size:10px;'>";
            for (var fi = 0; fi < namesToShow.length; ++fi) {
                var colName = namesToShow[fi];
                if (featureRow[colName] === undefined) continue;
                sideHtml += "<tr><td style='color:#334155; padding:1px 4px 1px 0;'>" + self.escapeHTML(colName) + "</td>" +
                    "<td style='text-align:right; font-weight:600;'>" + self.escapeHTML(featureRow[colName]) + "</td></tr>";
            }
            sideHtml += "</table></div>";
        }

        sidebar.innerHTML = sideHtml;
        modal.classList.add("open");

        if (pf && pf.isAudio && pf.url) {
            self.renderAudioWaveform("pdmWaveformCanvas", pf.url);
        }
        if (pf && pf.isText) {
            if (pf.textPreview !== null) {
                self.renderPointTextDocument(pf.textPreview, pf.name, "File");
            } else if (pf.file) {
                var reader = new FileReader();
                reader.onload = function (ev) {
                    var fullTxt = String(ev.target.result || "");
                    pf.textPreview = fullTxt.length > 65536
                        ? (fullTxt.slice(0, 65536) + "\n\n... [truncated at 64 KB — click Open to view full file]")
                        : fullTxt;
                    self.renderPointTextDocument(pf.textPreview, pf.name, "Local File");
                };
                reader.readAsText(pf.file.slice(0, 65536));
            } else if (pf.url) {
                fetch(pf.url, { credentials: "same-origin" })
                    .then(function (r) { return r.text(); })
                    .then(function (txt) {
                        pf.textPreview = txt.length > 65536
                            ? (txt.slice(0, 65536) + "\n\n... [truncated at 64 KB — click Open to view full file]")
                            : txt;
                        self.renderPointTextDocument(pf.textPreview, pf.name, "Server Media");
                    }).catch(function () {
                        self.renderPointTextDocument("Could not load text file.", pf.name, "Error");
                    });
            }
        } else if (!pf && typeof inlineDoc !== "undefined" && inlineDoc) {
            self.renderPointTextDocument(inlineDoc.text, inlineDoc.label, "Inline CSV Text");
        } else if (!pf) {
            var existingRow = self._findFeatureRowForPoint(pointId);
            if (existingRow) {
                self._renderOriginalInstanceTable(pointId, "");
            } else {
                self.loadfilecsv(function () {
                    if (String(self.activePointId) === String(pointId)) {
                        var loadedRow = self._findFeatureRowForPoint(pointId);
                        var lateInline = self.getInlineTextForPoint(pointId, loadedRow);
                        if (lateInline && gelem("pdmMediaStage")) {
                            gelem("pdmMediaStage").innerHTML = self._buildTextReaderHtml(lateInline.label);
                            self.renderPointTextDocument(lateInline.text, lateInline.label, "Inline CSV Text");
                        } else {
                            self._renderOriginalInstanceTable(pointId, "");
                        }
                    }
                });
            }
        }
        self.renderPointFilesPanel(
            (self.layoutinstance && self.layoutinstance.selected && self.layoutinstance.selected.length > 0)
                ? self.layoutinstance.selected
                : [pointId]
        );
    };

    this.rebindPointFilesToCurrentPoints = function () {
        self.pointFiles = {};
        var points = (self.datagff && self.datagff.layoutinstance && Array.isArray(self.datagff.layoutinstance.points))
            ? self.datagff.layoutinstance.points : [];
        var entries = self.pointFileList || [];
        if (entries.length === 0) {
            return;
        }

        var byLowerName = {};
        var byLowerStem = {};
        var byNumericId = {};
        for (var i = 0; i < entries.length; ++i) {
            var e = entries[i];
            byLowerName[e.lowerName] = e;
            if (!byLowerStem[e.lowerStem]) {
                byLowerStem[e.lowerStem] = e;
            }
            var m = e.stem.match(/(\d+)/);
            if (m && byNumericId[String(parseInt(m[1], 10))] === undefined) {
                byNumericId[String(parseInt(m[1], 10))] = e;
            }
        }

        // Determine if this dataset has explicit filename/label metadata (CSV file column or SELECT ID)
        var hasExplicitLabels = (self.csvFileLabels && Object.keys(self.csvFileLabels).length > 0)
            || (self.idinstancelabel && Object.keys(self.idinstancelabel).length > 0);

        var matched = 0;
        var unmatchedPoints = [];
        var usedEntries = new Set();
        for (var p = 0; p < points.length; ++p) {
            var pt = points[p];
            var sid = String(pt.id);
            var rawLabel = "";
            if (self.idinstancelabel && self.idinstancelabel[sid] !== undefined && String(self.idinstancelabel[sid]).trim() !== "") {
                rawLabel = String(self.idinstancelabel[sid]).trim();
            } else if (self.csvFileLabels && self.csvFileLabels[sid] !== undefined && String(self.csvFileLabels[sid]).trim() !== "") {
                rawLabel = String(self.csvFileLabels[sid]).trim();
            }
            var lowerLabel = rawLabel.toLowerCase();
            var lowerLabelStem = lowerLabel.replace(/\.[^/.]+$/, "");
            var found = null;
            if (lowerLabel && byLowerName[lowerLabel]) {
                found = byLowerName[lowerLabel];
            } else if (lowerLabelStem && byLowerStem[lowerLabelStem]) {
                found = byLowerStem[lowerLabelStem];
            } else if (!hasExplicitLabels && byNumericId[sid]) {
                found = byNumericId[sid];
            }
            if (found) {
                self.pointFiles[sid] = found;
                usedEntries.add(found);
                matched++;
            } else {
                unmatchedPoints.push(pt);
            }
        }

        // Only use positional natural-order fallback when the dataset has NO explicit filename/ID labels.
        // If a dataset has a file column (e.g. text_80.csv -> doc_*.txt), mismatched media (e.g. digit_*.png)
        // must NOT be force-attached to unrelated points.
        if (!hasExplicitLabels && unmatchedPoints.length > 0) {
            var remaining = entries.filter(function (e) { return !usedEntries.has(e); });
            var n = Math.min(unmatchedPoints.length, remaining.length);
            for (var r = 0; r < n; ++r) {
                self.pointFiles[String(unmatchedPoints[r].id)] = remaining[r];
                matched++;
            }
        }

        var st = gelem("pointfilesstatus");
        if (st) {
            st.textContent = points.length > 0
                ? (matched + "/" + points.length)
                : (entries.length + " files");
        }
        var clr = gelem("pointfilesclearbtn");
        if (clr) clr.style.display = "inline-block";

        var activeIds = (self.layoutinstance && Array.isArray(self.layoutinstance.selected) && self.layoutinstance.selected.length > 0)
            ? self.layoutinstance.selected
            : points.slice(0, 36).map(function (pt) { return pt.id; });
        self.renderPointFilesPanel(activeIds);
    };

    this.showPointFileDetails = function (pointId) {
        self.activePointId = pointId;
        var ids = (self.layoutinstance && Array.isArray(self.layoutinstance.selected) && self.layoutinstance.selected.length > 0)
            ? self.layoutinstance.selected.slice()
            : [pointId];
        if (ids.indexOf(pointId) === -1) {
            ids.unshift(pointId);
        }
        self.renderPointFilesPanel(ids);
    };

    this.renderPointFilesPanel = function (pointIds) {
        var panel = gelem("pointfilespanel");
        if (!panel) return;
        var hasLoadedFiles = self.pointFileList && self.pointFileList.length > 0;
        var points = (self.datagff && self.datagff.layoutinstance && Array.isArray(self.datagff.layoutinstance.points))
            ? self.datagff.layoutinstance.points : [];
        var targetNames = (self.datagff && self.datagff.layoutinstance && self.datagff.layoutinstance.tartegsnames)
            ? self.datagff.layoutinstance.tartegsnames : {};

        if (!hasLoadedFiles && self.activePointId === null) {
            panel.style.display = "none";
            panel.innerHTML = "";
            return;
        }

        var pointById = {};
        for (var i = 0; i < points.length; ++i) {
            pointById[String(points[i].id)] = points[i];
        }

        var ids = Array.isArray(pointIds) && pointIds.length > 0
            ? pointIds
            : points.slice(0, 36).map(function (pt) { return pt.id; });

        var headerCount = hasLoadedFiles
            ? (Object.keys(self.pointFiles).length + " / " + points.length + " points matched")
            : ("Point inspector");

        var html = "<div style='display:flex; align-items:center; justify-content:space-between; gap:8px; border-bottom:1px solid #cbd5e1; padding-bottom:4px;'>" +
            "<div><strong>Associated Point Files</strong> <span style='color:#475569;'>(" + self.escapeHTML(headerCount) + " &mdash; showing " + Math.min(ids.length, 48) + " of " + ids.length + ")</span></div>" +
            "<div style='display:flex; gap:4px;'>" +
                "<button type='button' class='btn btn-info btn-sm' style='padding:0 6px; font-size:10px;' onclick='GFFOBJ.captureHtmlPanelScreenshot(\"pointfilespanel\", \"point_files\");' title='Download PNG screenshot of Associated Point Files'><i class='fas fa-image'></i> Screenshot</button>" +
                "<button type='button' class='btn btn-outline-secondary btn-sm' style='padding:0 6px; font-size:10px;' onclick='gelem(\"pointfilesinput\").click();'>Load Files</button>" +
                "<button type='button' class='btn btn-outline-secondary btn-sm' style='padding:0 6px; font-size:10px;' onclick='gelem(\"pointfolderinput\").click();'>Load Folder</button>" +
                (hasLoadedFiles ? "<button type='button' class='btn btn-outline-danger btn-sm' style='padding:0 6px; font-size:10px;' onclick='GFFOBJ.clearPointFiles();'>Clear</button>" : "") +
            "</div></div>";

        // Active clicked point detailed preview
        if (self.activePointId !== null && pointById[String(self.activePointId)]) {
            var activePt = pointById[String(self.activePointId)];
            var activeFile = self.getPointFile(self.activePointId);
            var clsName = targetNames[activePt.t] !== undefined ? targetNames[activePt.t] : activePt.t;
            html += "<div style='display:flex; gap:10px; align-items:flex-start; background:#ffffff; border:1px solid #bfdbfe; padding:6px; margin-top:6px; border-radius:3px;'>";
            if (activeFile && activeFile.isImage) {
                html += "<img src='" + activeFile.url + "' style='max-width:160px; max-height:110px; object-fit:contain; border:1px solid #cbd5e1;'>";
            } else if (activeFile && activeFile.isAudio) {
                html += "<audio controls src='" + activeFile.url + "' style='height:32px;'></audio>";
            } else if (activeFile && activeFile.isVideo) {
                html += "<video controls src='" + activeFile.url + "' style='max-width:180px; max-height:110px;'></video>";
            }
            html += "<div style='text-align:left; font-size:11px;'>" +
                "<div><strong>Point ID:</strong> " + self.escapeHTML(activePt.id) +
                " &nbsp;|&nbsp; <strong>Class:</strong> " + self.escapeHTML(clsName) +
                " &nbsp;|&nbsp; <strong>Coords:</strong> (" + Number(activePt.x).toFixed(3) + ", " + Number(activePt.y).toFixed(3) + ")</div>" +
                "<div><strong>Associated File:</strong> " + self.escapeHTML(activeFile ? activeFile.name : self.getExportInstanceName(activePt.id)) +
                (activeFile ? (" <a href='" + activeFile.url + "' target='_blank' rel='noopener'>Open</a>") : "") + "</div>" +
                (activeFile && activeFile.isText ? "<pre id='activepointtextpreview' style='max-height:70px; overflow:auto; margin:4px 0 0 0; padding:4px; background:#f1f5f9; font-size:10px;'>Loading text preview...</pre>" : "") +
                "</div></div>";
        }

        // Grid of associated files for shown/selected points
        var displayIds = ids.slice(0, 48);
        html += "<div class='point-files-grid'>";
        for (var j = 0; j < displayIds.length; ++j) {
            var pid = displayIds[j];
            var pt = pointById[String(pid)];
            var pf = self.getPointFile(pid);
            var fname = pf ? pf.name : self.getInstanceLabel(pid);
            var cls = pt ? (targetNames[pt.t] !== undefined ? targetNames[pt.t] : pt.t) : "";
            var activeCls = (String(pid) === String(self.activePointId)) ? " active" : "";
            html += "<div class='point-file-card" + activeCls + "' onclick='GFFOBJ.openPointDataModal(" + JSON.stringify(pid) + ");' title='" + self.escapeHTML(fname) + "'>";
            if (pf && pf.isImage) {
                html += "<img class='point-file-thumb' src='" + pf.url + "' alt='" + self.escapeHTML(fname) + "'>";
            } else {
                var icon = pf && pf.isAudio ? "fa-file-audio" : (pf && pf.isVideo ? "fa-file-video" : (pf && pf.isText ? "fa-file-alt" : "fa-file"));
                html += "<div class='point-file-thumb' style='display:flex; align-items:center; justify-content:center; color:#475569;'><i class='fa " + icon + " fa-2x'></i></div>";
            }
            html += "<div class='point-file-name'>" + self.escapeHTML(fname) + "</div>" +
                "<div class='point-file-meta'>ID " + self.escapeHTML(pid) + (cls !== "" ? (" · " + self.escapeHTML(cls)) : "") + "</div>" +
                "</div>";
        }
        html += "</div>";

        panel.innerHTML = html;
        panel.style.display = "block";

        // Async load text preview if active point is a text file
        if (self.activePointId !== null) {
            var af = self.getPointFile(self.activePointId);
            if (af && af.isText && af.file) {
                var pre = gelem("activepointtextpreview");
                if (af.textPreview !== null) {
                    if (pre) pre.textContent = af.textPreview;
                } else {
                    var reader = new FileReader();
                    reader.onload = function (ev) {
                        af.textPreview = String(ev.target.result || "").slice(0, 1000);
                        var el = gelem("activepointtextpreview");
                        if (el) el.textContent = af.textPreview;
                    };
                    reader.readAsText(af.file.slice(0, 2048));
                }
            }
        }
    };


    this.getfeatureselected = function (){
        var featureselectedTrueIds = [];
        self.normalizeFeatureSelection();
        var nodes = (self.datagff.layoutfeature && self.datagff.layoutfeature["graph"])
                    ? self.datagff.layoutfeature["graph"].nodes : [];
        for(var i of self.featureselected){
            var node = nodes[i];
            if (!node || node.category == 1) continue;
            var tid = node.label;
            var entry = self.USFOBJ.at(tid);
            if (!entry || entry.value == 0){
                featureselectedTrueIds.push(tid);
            }
        }
        return featureselectedTrueIds;
    };

    this.setfeatureselected = function (featureselected){
        rest = [];
        for(var i of featureselected){
            //nam = self.datagff.fenames[i];
            //rest.push(self.auxfeatureselectedf[nam]);
            
            //nam = self.datagff.fenames[i];
            if (i in self.auxfeatureselectedf) {
                rest.push(self.auxfeatureselectedf[i]);
            }
        }
        //console.log("WSDself.auxfeatureselectedf", self.auxfeatureselectedf);
        return rest;
    };

    this.hasXAI = function () {
        return self.datagff && self.datagff.layoutxai &&
            Array.isArray(self.datagff.layoutxai.features) &&
            self.datagff.layoutxai.features.length > 0;
    };

    this.getTargetId = function () {
        var targetElement = gelem("target");
        var target = NaN;
        if (targetElement && targetElement.options && targetElement.options.length > 0) {
            target = parseInt(targetElement.value, 10);
            if (isNaN(target)) {
                target = parseInt(targetElement.selectedIndex, 10);
            }
        }
        if (isNaN(target) || target < 0) {
            target = parseInt(self.target, 10);
        }
        if (isNaN(target) || target < 0) {
            var names = (self.datagff && Array.isArray(self.datagff.fenames)) ? self.datagff.fenames : [];
            target = names.length > 0 ? names.length - 1 : 0;
        }
        self.target = target;
        if (targetElement && target >= 0 && target < targetElement.options.length) {
            targetElement.selectedIndex = target;
            targetElement.title = targetElement.options[target].text || "";
        }
        return target;
    };

    this.escapeHTML = function (value) {
        var map = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };
        return String(value === undefined || value === null ? "" : value)
            .replace(/[&<>"']/g, function (chr) {
                return map[chr];
            });
    };

    this.formatScore = function (value) {
        value = parseFloat(value || 0.0);
        if (!isFinite(value)) {
            value = 0.0;
        }
        if (value == 0.0) {
            return "0.0000";
        }
        if (Math.abs(value) >= 1.0) {
            return value.toFixed(3);
        }
        if (Math.abs(value) >= 0.001) {
            return value.toFixed(4);
        }
        return value.toExponential(2);
    };

    this.formatPValue = function (value) {
        if (value === undefined || value === null) {
            return "n/a";
        }
        var p = parseFloat(value);
        if (!isFinite(p)) {
            return "n/a";
        }
        if (p < 0.0001) {
            return p.toExponential(2);
        }
        return p.toFixed(4);
    };

    this.renderXAISelectedSummary = function () {
        var panel = gelem("xaiselectedsummary");
        if (!panel) {
            return;
        }
        self.normalizeFeatureSelection();
        var graph = self.datagff && self.datagff.layoutfeature && self.datagff.layoutfeature.graph
            ? self.datagff.layoutfeature.graph : {};
        var nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
        var names = self.datagff && Array.isArray(self.datagff.fenames) ? self.datagff.fenames : [];
        var rows = [];
        var targetCount = 0;

        for (var selectedId of self.featureselected) {
            var node = nodes[selectedId];
            if (!node) {
                continue;
            }
            if (node.category == 1) {
                targetCount += 1;
                continue;
            }
            var featureName = names[node.label] !== undefined ? names[node.label] : node.label;
            rows.push({
                "id": node.label,
                "name": featureName,
                "importance": parseFloat(node.xai_importance || 0.0),
                "importanceNorm": parseFloat(node.xai_importance_norm || 0.0),
                "permutation": parseFloat(node.xai_permutation || 0.0),
                "permutationNorm": parseFloat(node.xai_permutation_norm || 0.0),
                "shap": parseFloat(node.xai_shap || 0.0),
                "shapNorm": parseFloat(node.xai_shap_norm || 0.0)
            });
        }

        var quality = (self.datagff && self.datagff.layoutinstance && self.datagff.layoutinstance.quality)
            ? self.datagff.layoutinstance.quality : null;
        var hasContrastive = !!(self.contrastiveData && self.contrastiveData.status === "ok");

        if (rows.length == 0 && targetCount == 0 && !hasContrastive && !quality) {
            panel.style.display = "none";
            panel.innerHTML = "";
            return;
        }

        var hasXai = self.hasXAI();
        var shap = hasXai && self.datagff.layoutxai ? (self.datagff.layoutxai.shap || {}) : {};
        var shapAvailable = !!shap.available;
        var xaiTarget = hasXai && self.datagff.layoutxai.target ? self.datagff.layoutxai.target : {};
        var model = hasXai && self.datagff.layoutxai.model ? self.datagff.layoutxai.model : {};
        var targetName = xaiTarget.name || names[parseInt(self.target, 10)] || "";
        var selectedLabel = rows.length + (targetCount > 0 ? " + target" : "");
        var html = "";

        if (quality) {
            var haloActiveStyle = self.showFidelityHalo
                ? "background:#d95f02; color:#fff; border:1px solid #b34800;"
                : "background:#fff; color:#172033; border:1px solid #9fb3cd;";
            html += "<div style='display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:4px; padding-bottom:3px; border-bottom:1px solid #cddbf0;'>" +
                "<strong style='color:#0d3b66;'>Projection Fidelity</strong>" +
                "<span title='Venna & Kaski k-NN Trustworthiness (false-neighbor resistance)'>T: <b>" + Number(quality.trustworthiness).toFixed(3) + "</b></span>" +
                "<span title='Venna & Kaski k-NN Continuity (missing-neighbor resistance)'>C: <b>" + Number(quality.continuity).toFixed(3) + "</b></span>" +
                "<span title='Shepard pairwise distance correlation'>R: <b>" + Number(quality.shepard_corr).toFixed(3) + "</b></span>" +
                "<span title='Mean local k-NN neighborhood preservation'>Fidelity: <b>" + Math.round(Number(quality.mean_fidelity) * 100) + "%</b></span>";
            if (quality.silhouette !== null && quality.silhouette !== undefined) {
                html += "<span title='Class Silhouette coefficient in 2D'>Sil: <b>" + Number(quality.silhouette).toFixed(3) + "</b></span>";
            }
            html += "<span style='margin-left:auto; display:flex; gap:4px;'>" +
                "<button type='button' onclick='GFFOBJ.toggleProjectionFidelityHalo();' style='padding:1px 5px; font-size:9px; border-radius:2px; cursor:pointer; " + haloActiveStyle + "' title='Highlight projected points with low k-NN neighborhood fidelity'>" +
                    (self.showFidelityHalo ? "Hide Distortion Halos" : "Distortion Halos") +
                "</button>" +
                "<button type='button' onclick='GFFOBJ.clearInstanceBrush();' style='padding:1px 5px; font-size:9px; border-radius:2px; cursor:pointer; background:#fff; color:#172033; border:1px solid #9fb3cd;' title='Clear brushed instance groups and Ghost Trails'>Clear Brush</button>" +
                "</span></div>";
        }

        if (hasContrastive) {
            var cd = self.contrastiveData;
            var modeBadge = cd.comparison_mode === "a_vs_b"
                ? ("Group A (" + cd.group_a_count + ") vs. Group B (" + cd.group_b_count + ")")
                : ("Group A (" + cd.group_a_count + ") vs. Rest (" + cd.group_b_count + ")");
            html += "<div style='background:#f7faff; border:1px solid #b8cae6; padding:4px 6px; margin-bottom:4px; border-radius:2px;'>" +
                "<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom:2px;'>" +
                "<span><strong style='color:#006064;'>Contrastive &amp; Counterfactual Subspace Inspector</strong> &mdash; <b>" + self.escapeHTML(modeBadge) + "</b> (Purity: " + Math.round((cd.group_a_purity || 1) * 100) + "%)</span>" +
                "<span style='display:flex; align-items:center; gap:6px;'>" +
                    "<span style='font-size:9px; color:#4b5d73;'>Tip: Shift+Lasso in projection to brush Group B</span>" +
                    "<button type='button' class='btn btn-info btn-sm' style='padding:0 6px; font-size:9px;' onclick='GFFOBJ.captureHtmlPanelScreenshot(\"xaiselectedsummary\", \"contrastive_inspector\");' title='Download PNG screenshot of Contrastive & Counterfactual Subspace Inspector'><i class='fas fa-image'></i> Screenshot</button>" +
                "</span>" +
                "</div>";

            if (self.perturbationPreview && self.perturbationPreview.status === "ok") {
                var pp = self.perturbationPreview;
                var qd = pp.quality_delta || {};
                var cNames = (pp.candidate_names || []).join(", ") || ("Feature #" + (pp.candidates || []).join(","));
                var fmtDelta = function (v) {
                    if (v === null || v === undefined) return "n/a";
                    var num = Number(v);
                    return (num >= 0 ? "+" : "") + num.toFixed(3);
                };
                html += "<div style='background:#ede7f6; border:1px solid #b39ddb; padding:2px 5px; margin-bottom:3px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;'>" +
                    "<strong style='color:#4a148c;'>Ghost Trail Preview (" + self.escapeHTML(pp.action.toUpperCase() + " " + cNames) + "):</strong>" +
                    "<span>&Delta;T: <b>" + fmtDelta(qd.trustworthiness) + "</b></span>" +
                    "<span>&Delta;C: <b>" + fmtDelta(qd.continuity) + "</b></span>" +
                    "<span>&Delta;Fidelity: <b>" + fmtDelta(qd.mean_fidelity) + "</b></span>" +
                    (qd.silhouette !== null && qd.silhouette !== undefined ? ("<span>&Delta;Sil: <b>" + fmtDelta(qd.silhouette) + "</b></span>") : "") +
                    "<button type='button' onclick='GFFOBJ.clearGhostTrailPreview();' style='margin-left:auto; padding:0 4px; font-size:9px; background:#fff; border:1px solid #9575cd; cursor:pointer;'>Clear Trails</button>" +
                    "</div>";
            }

            html += "<div style='display:flex; gap:8px; flex-wrap:wrap;'>";
            // Left column: Top Contrastive Drivers (Delta_f)
            var topCon = Array.isArray(cd.top_contrastive) ? cd.top_contrastive.slice(0, 4) : [];
            html += "<div style='flex:1; min-width:210px;'>" +
                "<div style='font-weight:600; color:#1f2d3d; margin-bottom:2px;'>Local Contrastive Drivers (&Delta;<sub>f</sub> Cohen's d)</div>" +
                "<table style='width:100%; border-collapse:collapse; font-size:9.5px;'>";
            for (var ci = 0; ci < topCon.length; ci++) {
                var cf = topCon[ci];
                var dVal = Number(cf.effect_size || 0);
                var cNorm = Math.min(1.0, Math.abs(Number(cf.contrast_norm || 0)));
                var barColor = dVal >= 0 ? "#b2182b" : "#2166ac";
                var dirSign = dVal >= 0 ? "+" : "";
                var pFormatted = self.formatPValue(cf.p_value);
                var qFormatted = self.formatPValue(cf.fdr_q_value);
                var tVal = cf.t_statistic !== undefined ? Number(cf.t_statistic).toFixed(2) : "n/a";
                var sigLabel = cf.is_significant ? " [FDR Significant]" : "";
                var titleText = cf.name + " (Cohen's d: " + dirSign + dVal.toFixed(2) + ", Welch t: " + tVal + ", p: " + pFormatted + ", FDR q: " + qFormatted + sigLabel + ")";
                html += "<tr>" +
                    "<td title='" + self.escapeHTML(titleText) + "' style='max-width:95px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>" +
                        self.escapeHTML(cf.name) + (cf.is_significant ? " <span style='color:#b2182b; font-weight:bold;' title='FDR significant (q &lt; 0.05)'>*</span>" : "") +
                    "</td>" +
                    "<td style='text-align:right; width:44px; font-weight:600; color:" + barColor + ";' title='Welch t=" + tVal + ", p=" + pFormatted + ", FDR q=" + qFormatted + "'>" + dirSign + dVal.toFixed(2) + "</td>" +
                    "<td style='width:60px; padding-left:4px;' title='Welch p=" + pFormatted + ", FDR q=" + qFormatted + "'>" +
                        "<div style='height:6px; width:100%; background:#dce4f0;'><div style='height:6px; width:" + Math.round(cNorm * 100) + "%; background:" + barColor + ";'></div></div>" +
                        "<div style='font-size:7.5px; color:#556; line-height:9px; text-align:right;'>q=" + qFormatted + "</div>" +
                    "</td>" +
                    "<td style='width:38px; text-align:right; vertical-align:top;'>" +
                        "<button type='button' onclick='GFFOBJ.previewCandidateFeature(" + cf.id + ", \"toggle\");' style='padding:0 3px; font-size:8.5px; cursor:pointer; background:#fff; border:1px solid #b0bec5;' title='Preview Ghost Trails when toggling this feature'>&Delta; Trail</button>" +
                    "</td>" +
                    "</tr>";
            }
            html += "</table></div>";

            // Right column: Top Counterfactual Unselected Features (G_f)
            var topCF = Array.isArray(cd.top_counterfactual) ? cd.top_counterfactual.slice(0, 4) : [];
            html += "<div style='flex:1; min-width:220px;'>" +
                "<div style='font-weight:600; color:#00695c; margin-bottom:2px;'>Counterfactual Subspace Additions (G<sub>f</sub> Gain)</div>" +
                "<table style='width:100%; border-collapse:collapse; font-size:9.5px;'>";
            for (var cfi = 0; cfi < topCF.length; cfi++) {
                var rec = topCF[cfi];
                var gainPct = Math.round(Math.min(1.0, Math.max(0.0, Number(rec.counterfactual_gain || 0))) * 100);
                html += "<tr>" +
                    "<td title='" + self.escapeHTML(rec.name) + " (Redundancy: " + Math.round(Number(rec.redundancy || 0) * 100) + "%)' style='max-width:105px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>" + self.escapeHTML(rec.name) + "</td>" +
                    "<td style='text-align:right; width:36px; color:#00695c; font-weight:600;'>" + Number(rec.counterfactual_gain || 0).toFixed(2) + "</td>" +
                    "<td style='width:50px; padding-left:4px;'>" +
                        "<div style='height:6px; width:100%; background:#d0ece7;'><div style='height:6px; width:" + gainPct + "%; background:#00a676;'></div></div>" +
                    "</td>" +
                    "<td style='width:78px; text-align:right; white-space:nowrap;'>" +
                        "<button type='button' onclick='GFFOBJ.previewCandidateFeature(" + rec.id + ", \"add\");' style='padding:0 3px; font-size:8.5px; cursor:pointer; background:#fff; border:1px solid #80cbc4; margin-right:2px;' title='Preview Ghost Trails if this feature is added'>&Delta; Trail</button>" +
                        (!rec.is_selected ? ("<button type='button' onclick='GFFOBJ.addCounterfactualFeature(" + rec.id + ");' style='padding:0 4px; font-size:8.5px; cursor:pointer; background:#00a676; color:#fff; border:1px solid #00897b;' title='Add feature to active subspace and reproject'>+ Add</button>") : "<span style='color:#666; font-size:8px;'>Active</span>") +
                    "</td>" +
                    "</tr>";
            }
            html += "</table></div></div></div>";
        }

        if (rows.length == 0 && targetCount == 0) {
            panel.innerHTML = html;
            panel.style.display = html ? "block" : "none";
            return;
        }

        html += "<div style='display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:3px;'>" +
            "<strong>XAI selected features</strong>" +
            "<span>Selected: " + self.escapeHTML(selectedLabel) + "</span>";

        if (targetName !== "") {
            html += "<span>Target: " + self.escapeHTML(targetName) + "</span>";
        }
        if (hasXai && model.type) {
            html += "<span>Model: " + self.escapeHTML(model.type) + "</span>";
        }
        if (hasXai && self.xaiThreshold > 0.0) {
            html += "<span>Threshold: " + self.formatScore(self.xaiThreshold) + "</span>";
        }
        html += "</div>";

        if (rows.length == 0) {
            html += "<div>Only the target is selected; XAI feature scores are shown for input features.</div>";
            panel.innerHTML = html;
            panel.style.display = "block";
            return;
        }

        if (hasXai) {
            rows.sort(function (a, b) {
                return (b.importanceNorm - a.importanceNorm) ||
                    (b.permutationNorm - a.permutationNorm) ||
                    String(a.name).localeCompare(String(b.name));
            });
        }
        else {
            rows.sort(function (a, b) {
                return String(a.name).localeCompare(String(b.name));
            });
        }

        var limit = Math.min(rows.length, 10);
        if (!hasXai) {
            var chips = [];
            for (var chipIndex = 0; chipIndex < Math.min(rows.length, 16); chipIndex++) {
                chips.push("<span style='display:inline-block; margin:1px 3px 1px 0; padding:2px 5px; background:#fff; border:1px solid #c7d3e5;'>" +
                    self.escapeHTML(rows[chipIndex].name) + "</span>");
            }
            if (rows.length > 16) {
                chips.push("<span>+" + (rows.length - 16) + " more</span>");
            }
            html += "<div>XAI scores unavailable for this selection.</div><div>" + chips.join("") + "</div>";
            panel.innerHTML = html;
            panel.style.display = "block";
            return;
        }

        html += "<table style='width:100%; border-collapse:collapse; table-layout:fixed;'>" +
            "<tr>" +
            "<th style='text-align:left; width:34%; font-weight:600;'>Feature</th>" +
            "<th style='text-align:right; width:13%; font-weight:600;'>Imp.</th>" +
            "<th style='text-align:right; width:13%; font-weight:600;'>Perm.</th>";
        if (shapAvailable) {
            html += "<th style='text-align:right; width:13%; font-weight:600;'>SHAP</th>";
        }
        html += "<th style='text-align:left; font-weight:600;'>Rank</th></tr>";

        for (var rowIndex = 0; rowIndex < limit; rowIndex++) {
            var row = rows[rowIndex];
            var norm = Math.max(0.0, Math.min(1.0, row.importanceNorm || 0.0));
            var pct = Math.round(norm * 100);
            var muted = self.xaiThreshold > 0.0 && norm < self.xaiThreshold;
            var fill = muted ? "#8f99a8" : "#0b78d0";
            html += "<tr>" +
                "<td title='" + self.escapeHTML(row.name) + "' style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding-right:6px;'>" +
                    self.escapeHTML(row.name) +
                "</td>" +
                "<td style='text-align:right;'>" + self.formatScore(row.importance) + "</td>" +
                "<td style='text-align:right;'>" + self.formatScore(row.permutation) + "</td>";
            if (shapAvailable) {
                html += "<td style='text-align:right;'>" + self.formatScore(row.shap) + "</td>";
            }
            html += "<td style='padding-left:6px;'>" +
                    "<div style='height:8px; width:100%; background:#d7e1ef; overflow:hidden;'>" +
                        "<div style='height:8px; width:" + pct + "%; background:" + fill + ";'></div>" +
                    "</div>" +
                "</td>" +
            "</tr>";
        }
        html += "</table>";
        if (rows.length > limit) {
            html += "<div style='margin-top:2px;'>Showing top " + limit + " of " + rows.length + " selected features.</div>";
        }
        if (!shapAvailable && shap.reason) {
            html += "<div style='margin-top:2px;'>SHAP: " + self.escapeHTML(shap.reason) + "</div>";
        }
        panel.innerHTML = html;
        panel.style.display = "block";
    };

    this.setProjectionPanelStatus = function (left, right) {
        var leftElem = gelem("topleft2");
        var rightElem = gelem("topright2");
        if (leftElem) {
            leftElem.textContent = left || "";
        }
        if (rightElem) {
            rightElem.textContent = right || "";
        }
    };

    this.wrapPanelText = function (value, maxChars, maxLines) {
        var words = String(value || "").split(/\s+/);
        var lines = [];
        var current = "";
        for (var word of words) {
            if (current.length > 0 && (current.length + word.length + 1) > maxChars) {
                lines.push(current);
                current = word;
                if (lines.length >= maxLines) {
                    break;
                }
            }
            else {
                current = current.length > 0 ? current + " " + word : word;
            }
        }
        if (lines.length < maxLines && current.length > 0) {
            lines.push(current);
        }
        return lines.slice(0, maxLines);
    };

    this.showProjectionPanelMessage = function (left, right) {
        self.setProjectionPanelStatus(left, right);
        var width = Math.max(300, parseInt(self.lwidth, 10) || 500);
        var height = Math.max(300, parseInt(self.lheight, 10) || width);
        d3.select("#visp").selectAll("svg").remove();
        d3.select("#seq2").selectAll("svg").remove();
        var infLeft = gelem("infleft2");
        var infRight = gelem("infright2");
        if (infLeft) {
            infLeft.innerHTML = "";
        }
        if (infRight) {
            infRight.innerHTML = "";
        }
        var svg = d3.select("#visp").append("svg")
            .attr("width", width)
            .attr("height", height);
        svg.append("rect")
            .attr("width", width)
            .attr("height", height)
            .attr("fill", "#f7f9fc");
        svg.append("text")
            .attr("x", width / 2)
            .attr("y", height / 2 - 20)
            .attr("text-anchor", "middle")
            .attr("font-size", "15px")
            .attr("font-weight", "600")
            .attr("fill", "#1a2d45")
            .text(left || "Projection unavailable");
        var lines = self.wrapPanelText(right || "", 64, 3);
        for (var i = 0; i < lines.length; i++) {
            svg.append("text")
                .attr("x", width / 2)
                .attr("y", height / 2 + 8 + (i * 16))
                .attr("text-anchor", "middle")
                .attr("font-size", "12px")
                .attr("fill", "#465a72")
                .text(lines[i]);
        }
    };

    this.updateProjectionFallbackStatus = function (ds) {
        ds = ds || self.datagff || {};
        var layout = ds.layoutinstance || {};
        var requested = layout.projectionrequested || "";
        var used = layout.projectionused || "";
        if (layout.sampling) {
            self.setProjectionPanelStatus("Projection: " + used.toUpperCase(),
                "Submodular shortlist: " + layout.sampling.selected_rows + " of " +
                layout.sampling.original_rows + " rows. " + (layout.projectionfallback || ""));
            return true;
        }
        if (requested && used && requested != used) {
            var reason = layout.projectionfallback ||
                (requested.toUpperCase() + " was replaced by " + used.toUpperCase() + " for this dataset");
            self.setProjectionPanelStatus("Projection: " + used.toUpperCase(), reason);
            return true;
        }
        return false;
    };

    this.applyXAIAttributesToGraph = function (ds) {
        ds = ds || self.datagff || {};
        ds.layoutxai = ds.layoutxai || {};
        if (!ds.layoutfeature || !ds.layoutfeature.graph || !Array.isArray(ds.layoutfeature.graph.nodes)) {
            return;
        }

        var scores = {};
        var features = Array.isArray(ds.layoutxai.features) ? ds.layoutxai.features : [];
        for (var item of features) {
            scores[String(item.id)] = item;
        }

        for (var node of ds.layoutfeature.graph.nodes) {
            if (node.category != 0) {
                continue;
            }
            var xai = scores[String(node.label)] || {};
            node.xai_importance = parseFloat(xai.importance || 0.0);
            node.xai_importance_norm = parseFloat(xai.importance_norm || 0.0);
            node.xai_permutation = parseFloat(xai.permutation || 0.0);
            node.xai_permutation_norm = parseFloat(xai.permutation_norm || 0.0);
            node.xai_shap = parseFloat(xai.shap || 0.0);
            node.xai_shap_norm = parseFloat(xai.shap_norm || 0.0);
        }
    };

    this.getFeatureNodeMetric = function (node, channel) {
        if (!node) {
            return 0.0;
        }
        if (node.category == 1) {
            return parseFloat(node.weight || 0.0);
        }
        var mode = channel == "size" ? self.xaiSizeMode : self.xaiColorMode;
        if (mode == "xai_importance") {
            return parseFloat(node.xai_importance_norm || 0.0);
        }
        return parseFloat(node.weight || 0.0);
    };

    this.getFeatureNodeTooltip = function (node, ranking) {
        if (!node || node.category == 1) {
            return "extra";
        }
        var name = (self.datagff && self.datagff.fenames && self.datagff.fenames[node.label])
            ? self.datagff.fenames[node.label] : (node.name || "Feature #" + node.label);
        var baseTip = "";
        if (self.xaiColorMode == "xai_importance" || self.xaiSizeMode == "xai_importance") {
            var xaiScore = parseFloat(node.xai_importance || 0.0).toFixed(6);
            baseTip = name + ": XAI " + xaiScore;
        } else if (ranking && ranking[node.name] !== undefined) {
            baseTip = name + ":" + ranking[node.name];
        } else {
            baseTip = name;
        }

        if (self.contrastiveData && self.contrastiveData.by_feature_id) {
            var cInfo = self.contrastiveData.by_feature_id[String(node.label)];
            if (cInfo) {
                var dVal = Number(cInfo.effect_size || 0);
                var dirSign = dVal >= 0 ? "+" : "";
                var pStr = self.formatPValue(cInfo.p_value);
                var qStr = self.formatPValue(cInfo.fdr_q_value);
                var tVal = cInfo.t_statistic !== undefined ? Number(cInfo.t_statistic).toFixed(2) : "n/a";
                var sigStr = cInfo.is_significant ? " [FDR Significant]" : "";
                baseTip += " | \u0394=" + dirSign + dVal.toFixed(2) + " (t=" + tVal + ", p=" + pStr + ", q=" + qStr + ")" + sigStr;
                if (cInfo.is_top_counterfactual) {
                    baseTip += " [Top Counterfactual: gain=" + Number(cInfo.counterfactual_gain || 0).toFixed(2) + "]";
                }
            }
        }
        return baseTip;
    };

    this.refreshFeatureNodeStyles = function () {
        if (self.layoutfeatures != null && self.layoutfeatures.applyNodeStyles) {
            self.layoutfeatures.applyNodeStyles();
        }
    };

    this.onInstanceSelectionChanged = function (groupA, groupB) {
        groupA = Array.isArray(groupA) ? groupA : [];
        groupB = Array.isArray(groupB) ? groupB : [];
        if (self.pointFileList.length > 0) {
            var combinedIds = groupA.concat(groupB);
            if (combinedIds.length > 0) {
                self.renderPointFilesPanel(combinedIds);
            } else {
                var pts = (self.datagff && self.datagff.layoutinstance && Array.isArray(self.datagff.layoutinstance.points))
                    ? self.datagff.layoutinstance.points : [];
                self.renderPointFilesPanel(pts.slice(0, 36).map(function (pt) { return pt.id; }));
            }
        }
        if (self.datafileselected == "" || groupA.length === 0) {
            self.contrastiveData = null;
            self.refreshFeatureNodeStyles();
            self.renderXAISelectedSummary();
            return;
        }
        var ob = new ServiceData("computing contrastive subspace explanation");
        ob.in.argms["type"] = 27;
        ob.in.argms["file"] = self.datafileselected;
        ob.in.argms["target"] = self.getTargetId();
        ob.in.argms["featureselected"] = self.getfeatureselected();
        ob.in.argms["group_a_ids"] = groupA;
        ob.in.argms["group_b_ids"] = groupB;
        ob.event = function () {
            if (this.ou && this.ou.status === "ok") {
                self.contrastiveData = this.ou;
            } else {
                self.contrastiveData = null;
            }
            self.refreshFeatureNodeStyles();
            self.renderXAISelectedSummary();
        };
        ob.start();
    };

    this.previewCandidateFeature = function (featureOrigId, action) {
        if (self.datafileselected == "") {
            return;
        }
        var ob = new ServiceData("computing Ghost Trail subspace perturbation preview");
        ob.in.argms["type"] = 28;
        ob.in.argms["file"] = self.datafileselected;
        ob.in.argms["target"] = self.getTargetId();
        ob.in.argms["instanceproximity"] = gvalue("instanceproximity");
        ob.in.argms["featureselected"] = self.getfeatureselected();
        ob.in.argms["candidate_feature"] = parseInt(featureOrigId, 10);
        ob.in.argms["action"] = action || "toggle";
        ob.event = function () {
            if (this.ou && this.ou.status === "ok") {
                self.perturbationPreview = this.ou;
                if (self.layoutinstance != null && self.layoutinstance.renderGhostTrails) {
                    self.layoutinstance.renderGhostTrails(this.ou.trails || []);
                }
                self.renderXAISelectedSummary();
            }
        };
        ob.start();
    };

    this.clearGhostTrailPreview = function () {
        self.perturbationPreview = null;
        if (self.layoutinstance != null && self.layoutinstance.clearGhostTrails) {
            self.layoutinstance.clearGhostTrails();
        }
        self.renderXAISelectedSummary();
    };

    this.addCounterfactualFeature = function (featureOrigId) {
        var nodeIndex = self.auxfeatureselectedf[parseInt(featureOrigId, 10)];
        if (nodeIndex === undefined) {
            return;
        }
        self.selectFeatureIds([nodeIndex], "add");
        self.perturbationPreview = null;
        if (self.layoutinstance != null && self.layoutinstance.clearGhostTrails) {
            self.layoutinstance.clearGhostTrails();
        }
        self.onFeatureSelectionChanged();
    };

    this.toggleProjectionFidelityHalo = function () {
        self.showFidelityHalo = !self.showFidelityHalo;
        if (self.layoutinstance != null && self.layoutinstance.toggleFidelityHalo) {
            self.layoutinstance.toggleFidelityHalo(self.showFidelityHalo);
        }
        self.renderXAISelectedSummary();
    };

    this.clearInstanceBrush = function () {
        self.contrastiveData = null;
        self.perturbationPreview = null;
        if (self.layoutinstance != null) {
            if (self.layoutinstance.clearSelection) {
                self.layoutinstance.clearSelection();
            }
            if (self.layoutinstance.clearGhostTrails) {
                self.layoutinstance.clearGhostTrails();
            }
        }
        self.refreshFeatureNodeStyles();
        self.renderXAISelectedSummary();
    };

    this.setFeatureLayoutMode = function (layout) {
        var layoutElement = gelem("layout");
        if (layoutElement) {
            layoutElement.value = layout;
        }
        self.datagff.configfeature = self.datagff.configfeature || {};
        self.datagff.configfeature.layout = layout;
    };

    this.featureGraphHasNodes = function () {
        var graph = self.datagff && self.datagff.layoutfeature && self.datagff.layoutfeature.graph
            ? self.datagff.layoutfeature.graph : {};
        return Array.isArray(graph.nodes) && graph.nodes.length > 0;
    };

    this.ensureXAICompatibleFeatureLayout = function () {
        if (!self.featureGraphHasNodes()) {
            self.visFeatures();
            return false;
        }
        if (self.layoutfeatures != null && self.layoutfeatures.applyNodeStyles) {
            return true;
        }
        self.setFeatureLayoutMode("fo");
        self.processFeaturesResults(self.datagff);
        return self.layoutfeatures != null && self.layoutfeatures.applyNodeStyles;
    };

    this.ensureSHAPCompatibleFeatureLayout = function () {
        if (!self.featureGraphHasNodes()) {
            self.visFeatures();
            return false;
        }
        if (self.layoutfeatures != null && self.layoutfeatures.setSimilarityLinks) {
            return true;
        }
        self.setFeatureLayoutMode("fo");
        self.processFeaturesResults(self.datagff);
        return self.layoutfeatures != null && self.layoutfeatures.setSimilarityLinks;
    };

    this.ensureFeatureGraphVisibleAfterXAI = function (preferXAIStyleLayout) {
        if (preferXAIStyleLayout && self.ensureXAICompatibleFeatureLayout()) {
            self.refreshFeatureNodeStyles();
        }
        else if (self.layoutfeatures != null) {
            self.refreshFeatureNodeStyles();
        }
        else if (self.featureGraphHasNodes()) {
            self.processFeaturesResults(self.datagff);
        }
        else {
            self.visFeatures();
        }
    };

    this.runXAI = function () {
        if (self.datafileselected == "") {
            return;
        }
        var ob = new ServiceData("running local XAI");
        ob.in.argms["type"] = 26;
        ob.in.argms["file"] = self.datafileselected;
        ob.in.argms["target"] = self.getTargetId();
        ob.in.argms["xai_enable_shap"] = true;
        ob.event = function () {
            if (this.ou && (this.ou.status == "ok" || this.ou.status == "partial")) {
                self.datagff.layoutxai = this.ou;
                self.applyXAIAttributesToGraph(self.datagff);
                self.renderXAISelectedSummary();
                var needsXAIStyleLayout = self.xaiColorMode == "xai_importance" ||
                    self.xaiSizeMode == "xai_importance" ||
                    self.xaiThreshold > 0.0;
                self.ensureFeatureGraphVisibleAfterXAI(needsXAIStyleLayout);
                if (self.xaiThreshold > 0.0 &&
                        self.layoutfeatures != null &&
                        self.layoutfeatures.selectbythreshold) {
                    self.layoutfeatures.selectbythreshold(self.xaiThreshold);
                }
                gelem("topleft1").innerHTML = "XAI: " + this.ou.model.type;
                gelem("topright1").innerHTML = "Target: " + this.ou.target.name;
            }
            else {
                var msg = this.ou && this.ou.message ? this.ou.message : "XAI failed";
                gelem("topleft1").innerHTML = "XAI error";
                gelem("topright1").innerHTML = msg;
                console.error("xai error:", this.ou);
            }
        };
        ob.start();
    };

    this.setXAIImportanceColorMode = function () {
        if (!self.hasXAI()) {
            self.xaiColorMode = "xai_importance";
            self.runXAI();
            return;
        }
        self.xaiColorMode = self.xaiColorMode == "xai_importance" ? "graph" : "xai_importance";
        if (self.xaiColorMode == "xai_importance") {
            self.ensureXAICompatibleFeatureLayout();
        }
        self.refreshFeatureNodeStyles();
        self.renderXAISelectedSummary();
    };

    this.setXAIImportanceSizeMode = function () {
        if (!self.hasXAI()) {
            self.xaiSizeMode = "xai_importance";
            self.runXAI();
            return;
        }
        self.xaiSizeMode = self.xaiSizeMode == "xai_importance" ? "graph" : "xai_importance";
        if (self.xaiSizeMode == "xai_importance") {
            self.ensureXAICompatibleFeatureLayout();
        }
        self.refreshFeatureNodeStyles();
        self.renderXAISelectedSummary();
    };

    this.selectXAIThreshold = function (threshold) {
        self.xaiThreshold = parseFloat(threshold || 0.0);
        if (!self.hasXAI()) {
            self.xaiColorMode = "xai_importance";
            self.runXAI();
            return;
        }
        self.xaiColorMode = "xai_importance";
        self.ensureXAICompatibleFeatureLayout();
        if (self.layoutfeatures != null && self.layoutfeatures.selectbythreshold) {
            self.layoutfeatures.selectbythreshold(self.xaiThreshold);
        }
        self.renderXAISelectedSummary();
    };

    this.showSHAPSimilarityGraph = function () {
        if (!self.hasXAI()) {
            self.runXAI();
            return;
        }
        var shap = self.datagff.layoutxai.shap || {};
        var similarity = shap.similarity || {};
        if (!similarity.available || !Array.isArray(similarity.links) || similarity.links.length == 0) {
            gelem("topleft1").innerHTML = "SHAP graph unavailable";
            gelem("topright1").innerHTML = shap.reason || "No SHAP similarity links";
            return;
        }
        self.ensureSHAPCompatibleFeatureLayout();
        if (self.layoutfeatures != null && self.layoutfeatures.setSimilarityLinks) {
            self.layoutfeatures.setSimilarityLinks(similarity.links);
            gelem("topleft1").innerHTML = "SHAP similarity";
            gelem("topright1").innerHTML = similarity.links.length + " links";
        }
        else {
            gelem("topleft1").innerHTML = "SHAP graph unavailable";
            gelem("topright1").innerHTML = "Force layout could not be opened";
        }
    };

    this.visFeatures = function () {
        self.cleanfeatures();
        //self.setfullScreen();
        self.unselectedfeids = self.USFOBJ.getUnselected();        
        
        if (self.datafileselected != "" && self.unselectedfeids.length<(self.datagff.fenames.length-1)) {
            self.cleanfeatures();
            var status = "making feature graph";
            
            var ob = new ServiceData(status);
            ob.in.argms["type"] = 0;
            ob.in.argms["file"] = self.datafileselected;
            ob.in.argms["target"] = self.getTargetId();
            ob.in.argms["intarget"] = self.intarget;
            ob.in.argms["proximity"] = gvalue('proximity');
            ob.in.argms["instanceproximity"] = gvalue('instanceproximity');
            ob.in.argms["submodular_size"] = gvalue("submodular_size");
            ob.in.argms["relevance"] = gvalue('relevance');
            ob.in.argms["algorithm"] = gvalue('algorithm');
            ob.in.argms["layout"] = gvalue('layout');
            ob.in.argms["isfeature"] = 1;
            ob.in.argms["featureselected"] = self.getfeatureselected();
            ob.in.argms["ranking"] = [];

            ob.in.argms["idinstanceslabels"] = gvalue("idinstanceslabels");

            ob.in.argms["statusval"] = status;
            //console.log("ob.in", ob.in);
            ob.event = function () {
                if(this.ou["statusopt"]==0){
                    self.dequeLoadFeatures();
                }
                else if(this.ou["statusopt"]==1){
                    self.dequeLoadFeatures();
                }
                else if(this.ou["statusopt"]==2){
                    gelem("topleft1").innerHTML = "Error building feature graph";
                    gelem("topright1").innerHTML = "Check server log";
                    console.error("feature graph error:", this.ou);
                }
            };
            ob.start();
        }
    };


    this.visInstnaces = function () {
        self.cleaninstances();
        //self.setfullScreen();
        if (self.datafileselected == "") {
            self.showProjectionPanelMessage(
                "Projection unavailable",
                "Open a dataset before running PCA, UMAP, t-SNE, or MDS"
            );
            return;
        }
        if (self.featureselected.length < 2) {
            self.showProjectionPanelMessage(
                "Projection unavailable",
                "PCA, UMAP, t-SNE, and MDS use selected features from any feature graph; select at least two features"
            );
            return;
        }
        if (self.featureselected.length >= 2) {
            var status = "making projection from features selected";
            var ob = new ServiceData(status);
            ob.in.argms["type"] = 1;
            ob.in.argms["threshold"] = 0.78;
            ob.in.argms["target"] = self.getTargetId();
            ob.in.argms["intarget"] = self.intarget;
            ob.in.argms["proximity"] = gvalue('proximity');
            ob.in.argms["instanceproximity"] = gvalue('instanceproximity');
            ob.in.argms["submodular_size"] = gvalue("submodular_size");
            ob.in.argms["relevance"] = gvalue('relevance');
            ob.in.argms["algorithm"] = gvalue('algorithm');
            ob.in.argms["layout"] = gvalue('layout');
            ob.in.argms["projection"] = gvalue('projection');
            ob.in.argms["topleft"] = 'topleft2';
            ob.in.argms["topfright"] = 'topright2';
            ob.in.argms["infleft"] = 'infleft2';
            ob.in.argms["infright"] = 'infright2';
            ob.in.argms["file"] = self.datafileselected;
            ob.in.argms["isfeature"] = 0;
            ob.in.argms["featureselected"] = self.getfeatureselected();
            ob.in.argms["ranking"] = [];

            ob.in.argms["idinstanceslabels"] = gvalue("idinstanceslabels");

            ob.in.argms["statusval"] = status;

            //self.unselectedfeids
            if (ob.in.argms["projection"] == "mst") {

            }
            else if (ob.in.argms["projection"] == "simple" && !ob.in.argms["submodular_size"]) {
                MOPRO.show("simple projection");
                self.loadfilecsv(function () {
                    self.plotpaiercorrelate();
                    MOPRO.hide();
                });
            }
            else {
                ob.event = function () {
                    if(this.ou["statusopt"]==0){
                        self.dequeLoadInstances();
                    }
                    else if(this.ou["statusopt"]==1){
                        self.dequeLoadInstances();
                    }
                    else if(this.ou["statusopt"]==2){
                        gelem("topleft2").innerHTML = "Error building projection";
                        gelem("topright2").innerHTML = "Check server log";
                        console.error("projection error:", this.ou);
                    }
                };
                ob.start();
            }
        }
    };
    

   


    /**
     * Load one dataset
     */
    this.dequeLoadDataset = function(datasetid){
        var obj = {};
        var count = 0;
        var pname ="loading dataset";
        loadObject(pname, obj, self.listdataset, count, datasetid,
            //process function
            function (obj, ou) {
                for(let q of ou["response"]){
                    setDict(obj, q["query"], q["response"]);
                }
            },
            //end function
            function (obj) {       
                self.datagff = {};
                self.datagff = obj;
                
                self.processFeaturesResults(self.datagff);
                self.processInstancesResults(self.datagff);
            },
            //busy function
            function (ou) {
                var ps = MOPRO.pushprocess(pname);
                setTimeout(function(){
                    MOPRO.popprocess(ps);
                    self.dequeLoadDataset(datasetid);
                }, 5000);
            },
            24
        );
    };


    /**
     * Load one dataset-features
     */
     this.dequeLoadFeatures = function(){
        var count = 0;
        var obj = {};
        var pname = "loading dataset (features)";
        loadObject(pname, obj, self.listfeatures, count, self.datafileselected, 
            //process function
            function (obj, ou) {
                for(let q of ou["response"]){
                    setDict(obj, q["query"], q["response"]);
                }
            }, 
            //end function
            function(obj) {
                self.datagff["configfeature"] = {};
                self.datagff["typefeature"] = {};
                self.datagff["layoutfeature"] = {};
                self.datagff["versionfeature"] = {};
                self.datagff["featurecheck"] = {};
                
                for (var k in obj){
                    self.datagff[k] = {};
                    self.datagff[k] = obj[k];
                }

                self.processFeaturesResults(self.datagff);
            },
            //busy function
            function (ou) {
                var ps = MOPRO.pushprocess(pname);
                setTimeout(function(){
                    MOPRO.popprocess(ps);
                    self.dequeLoadFeatures();
                }, 5000);
            },
            24
        );
    };


    /**
     * Load one dataset-features
     */
     this.dequeLoadInstances = function(){
        var count = 0;
        var obj = {};
        var pname = "loading dataset (instances)";
        loadObject(pname, obj, self.listinstances, count, self.datafileselected, 
            //process function
            function (obj, ou) {
                for(let q of ou["response"]){
                    setDict(obj, q["query"], q["response"]);
                }
            }, 
            //end function
            function(obj) {
                self.datagff["configinstance"] = {};
                self.datagff["typeinstance"] = {};
                self.datagff["layoutinstance"] = {};
                self.datagff["versioninstance"] = {};

                for (var k in obj){
                    self.datagff[k] = {};
                    self.datagff[k] = obj[k];
                }
                self.processInstancesResults(self.datagff);
            },
            //busy function
            function (ou) {
                var ps = MOPRO.pushprocess(pname);
                setTimeout(function(){
                    MOPRO.popprocess(ps);
                    self.dequeLoadInstances();
                }, 5000);
            },
            24
        );
    };

    /**
     * Send select and unselect features
     */
    this.dequeSendFeaturesChecks = function () {
        self.unselectedfeids = self.USFOBJ.getUnselected();                
        if (self.datafileselected != "" && self.unselectedfeids.length<(self.datagff.fenames.length-1)) {
            var list = [];
            for (var e of self.USFOBJ.unselectedfeatures){
                var v = e.value==1 ? 0 : 1;
                list.push([e.id, v]);
            }
            //self.featuresChecks = chunk(self.USFOBJ.unselectedfeatures,5);
            self.featuresChecks = chunk(list,100);
            
            var count = 0;
            var obj = {};
            var pname = "sending features selected and unselected";
            loadObject(pname,
                obj, self.featuresChecks, count, self.datafileselected,
                // process function
                function (obj, ou) {
    
                },
                // end function
                function (obj) {
                    //MOPRO.auto = true;
                    self.visFeatures();
                },
                // busy function
                function () {
                    var ps = MOPRO.pushprocess(pname);
                    setTimeout(function(){
                        MOPRO.popprocess(ps);
                        self.dequeSendFeaturesChecks();
                    }, 5000);
                },
                23
            );
        }
    };

    this.processFeaturesResults = function(ds){
        self.shifflayoutcontrols("mainlayout");
        self.lfenamesindex = {};
        ds.layoutfeature = ds.layoutfeature || {};
        ds.layoutfeature.graph = ds.layoutfeature.graph || {};
        ds.layoutfeature.graph.nodes = ds.layoutfeature.graph.nodes || [];
        ds.layoutfeature.graph.links = ds.layoutfeature.graph.links || [];
        ds.layoutfeature.graph.whole = ds.layoutfeature.graph.whole || [];
        ds.layoutfeature.root = ds.layoutfeature.root || [];
        ds.layoutfeature.treehi = ds.layoutfeature.treehi || [];
        ds.layoutfeature.edgehist = ds.layoutfeature.edgehist || [];
        ds.layoutfeature.ranking = ds.layoutfeature.ranking || [];
        ds.layoutxai = ds.layoutxai || {};
        self.applyXAIAttributesToGraph(ds);

        if ("fenames" in ds) {
            var strs = "";
            var i = 0;
            for (var item of ds["fenames"]) {
                self.lfenamesindex[item] = i;
                strs += "<option value='" + i + "'>" + self.escapeHTML(item) + "</option>";
                i++;
            }
            gelem("target").innerHTML = strs;
            gelem("target").selectedIndex = Object.keys(self.lfenamesindex).length - 1;
            self.target = self.getTargetId();

            self.populateInstanceIdDropdown();
            self.autoLoadCsvFileLabels();
            self.getUnselecteFeatures();
        }
        if ("lastversion" in ds && "versionfeature" in ds && ds["lastversion"] == ds["versionfeature"]) {
           
            if ("configfeature" in ds) {
                conf = ds["configfeature"];
                if ("target" in conf) {
                    var configTarget = parseInt(conf["target"], 10);
                    self.target = isNaN(configTarget) ? self.getTargetId() : configTarget;
                    if (self.target >= 0 && self.target < gelem("target").options.length) {
                        gelem("target").selectedIndex = self.target;
                    }
                    self.populateInstanceIdDropdown();
                }
                var confins = ds["configinstance"] || {};
                if ("idinstanceslabels" in confins && String(confins["idinstanceslabels"]).trim() !== "") {
                    var savedIdVal = String(confins["idinstanceslabels"]).trim();
                    if (savedIdVal !== String(self.target)) {
                        gelem('idinstanceslabels').value = savedIdVal;
                        self.makeInstancesLabels(savedIdVal);
                    } else {
                        gelem('idinstanceslabels').value = "";
                    }
                }
                else {
                    gelem('idinstanceslabels').value = "";
                }

                if ("proximity" in conf) {
                    gelem('proximity').value = conf["proximity"];
                }
                if ("relevance" in conf) {
                    gelem('relevance').value = conf["relevance"];
                }
                if ("algorithm" in conf) {
                    gelem('algorithm').value = conf["algorithm"];
                }
                if ("layout" in conf) {
                    gelem('layout').value = conf["layout"];
                }


                // Restore include-target state without mutating the saved feature selection count
                if ("intarget" in conf) {
                    self.syncInTargetState(!!conf["intarget"]);
                } else {
                    self.syncInTargetState(false);
                }
                if (Object.keys(ds.layoutfeature.graph.nodes).length > 0 ) {
                    self.auxfeatureselectedf = self.makeFeatureAux(ds.layoutfeature.graph.nodes);
                }
                if ("featureselected" in conf) {
                    self.featureselected = self.setfeatureselected(conf["featureselected"]);
                    self.normalizeFeatureSelection();
                }

                /* 
                self.USFOBJ.init();
                if ("unselectedfeids" in conf) {
                    self.unselectedfeids = conf["unselectedfeids"];
                    self.USFOBJ.load();
                }
                self.USFOBJ.print();
                */
                //end new code

                if (    "typefeature" in ds &&
                        "layoutfeature" in ds &&
                        ds["layoutfeature"] != "" &&
                        "layout" in conf
                ){
                    if (ds["typefeature"] == "graph") {
                        inargms = {};
                        inargms["infleft"] = 'topleft1';
                        inargms["infright"] = 'topright1';
                        self.layoutfeatures = null;
                        //var data = ds["layoutfeature"];
                        //console.log("self.datagff.layoutfeature", self.datagff.layoutfeature);
                        if (conf["layout"] == "fo" && Object.keys(ds["layoutfeature"]).length > 0) {
                            self.layoutfeatures = new chart_force(VertexColorF, EdgeColorF, self, "#vis", -10, inargms);
                        }
                        else if (conf["layout"] == "cb" && Object.keys(ds["layoutfeature"]).length > 0) {
                            self.layoutfeatures = new chart_circularbundle_gff("#vis", self, VertexColorF, EdgeColorF);
                        }
                        else if (conf["layout"] == "sb" && Object.keys(ds["layoutfeature"]).length > 0) {
                            self.layoutfeatures = new chart_sunburst("#vis", VertexColorF, self, inargms);
                        }
                        else if (conf["layout"] == "pk") {
                            self.layoutfeatures = new chart_circlepack("#vis", self, VertexColorF);
                        }
                        else if (conf["layout"] == "hm") {
                            self.layoutfeatures = new chart_feature_heatmap("#vis", self, VertexColorF, EdgeColorF);
                        }
                        else if (conf["layout"] == "cm") {
                            self.layoutfeatures = new chart_feature_community("#vis", self, VertexColorF, EdgeColorF);
                        }
                        else if (conf["layout"] == "bp") {
                            self.layoutfeatures = new chart_bipartite("#vis", self, VertexColorF);
                        }
                        else if (conf["layout"] == "up") {
                            self.layoutfeatures = new chart_upset("#vis", self, VertexColorF);
                        }
                        if (self.layoutfeatures != null) {
                            gelem('edgeslider').value = 0;
                            self.edgeslider = 0;

                            if (self.layoutfeatures.selectbythreshold) {
                                chart_palettecolors(self.layoutfeatures.selectbythreshold,
                                    "seq1", 20, Math.max(200, (self.lheight || self.lwidth) - 20), VertexColorF);
                            }
                            else {
                                d3.select("#seq1").selectAll("svg").remove();
                            }

                            if (self.layoutfeatures.updatelinkoption) {
                                chart_histogram(self.setToolpiltex,
                                    self.hideToolpiltex,
                                    self.layoutfeatures.updatelinkoption,
                                    "seqedgehist", self.lwidth, EdgeColorF, self.datagff.layoutfeature["edgehist"]);
                            }
                            else {
                                d3.select("#seqedgehist").selectAll("svg").remove();
                            }

                            // Highlight restored selection without toggling intarget or changing feature count
                            self.layoutfeatures.highlightforce(self.featureselected, {"silent": true});
                        }
                        else {
                            gelem("topleft1").innerHTML = "Feature layout unavailable";
                            gelem("topright1").innerHTML = "Choose another layout";
                        }
                        self.renderXAISelectedSummary();
                    }
                    else if (ds["typefeature"] == "otherss") {
                        if ("layoutfeature" in ds && ds["layoutfeature"] != "" && "layout" in conf) {

                        }
                    }
                }
            }
        }
            
    };


    this.processInstancesResults = function(ds){
        self.shifflayoutcontrols("mainlayout");
        ds.layoutinstance = ds.layoutinstance || {};
        if ("lastversion" in ds && "versioninstance" in ds && ds["lastversion"] == ds["versioninstance"]) {
            //self.dataoutinstance = ds;
            if ("configinstance" in ds) {
                conf = ds["configinstance"];
                if ("projection" in conf) {
                    gelem('projection').value = conf["projection"];
                }
                gelem("submodular_size").value = conf.submodular_size || "";
                if ("instanceproximity" in conf) {
                    gelem('instanceproximity').value = conf["instanceproximity"];
                }

                if ("idinstanceslabels" in conf && String(conf["idinstanceslabels"]).trim() !== "") {
                    var savedCol = String(conf["idinstanceslabels"]).trim();
                    if (savedCol !== String(self.target)) {
                        gelem('idinstanceslabels').value = savedCol;
                        self.makeInstancesLabels(savedCol);
                    } else {
                        gelem('idinstanceslabels').value = "";
                    }
                }
                else{
                    gelem('idinstanceslabels').value = "";
                }


                if ("silhouette" in conf) {
                    gelem("topleft2").innerHTML = "SILHOUETTE: " + conf["silhouette"];
                }

            }
            if ("typeinstance" in ds) {
                if (ds["typeinstance"] == "projection") {
                    if (ds.layoutinstance && Array.isArray(ds.layoutinstance.points) && ds.layoutinstance.points.length > 0) {
                        //var data = ds["layoutinstance"];
                        argms = {"infleft": 'infleft2',"infright": 'infright2'};
                        self.layoutinstance = new plotProjection(ProjectionColorF, "#visp", self, argms);
                        self.applyPanModeState("instances");
                        if (!self.updateProjectionFallbackStatus(ds)) {
                            var q = ds.layoutinstance.quality;
                            if (q) {
                                var silStr = (q.silhouette !== null && q.silhouette !== undefined) ? (" | SIL: " + Number(q.silhouette).toFixed(3)) : "";
                                gelem("topleft2").innerHTML = "T: " + Number(q.trustworthiness).toFixed(3) + " | C: " + Number(q.continuity).toFixed(3) + silStr;
                                gelem("topright2").innerHTML = "FIDELITY: " + Math.round(Number(q.mean_fidelity) * 100) + "% (R=" + Number(q.shepard_corr).toFixed(2) + ")";
                            }
                        }
                        self.renderXAISelectedSummary();

                        if (self.datagff.configinstance && self.datagff.configinstance.nodes) {
                            self.auxfeatureselectedi = self.makeFeatureAux(self.datagff.configinstance.nodes);
                        }
                        if (self.pointFileList.length > 0) {
                            self.rebindPointFilesToCurrentPoints();
                        }
                    }
                    else {
                        var fallback = ds.layoutinstance && ds.layoutinstance.projectionfallback
                            ? ds.layoutinstance.projectionfallback
                            : "No projection points were returned for the selected features";
                        self.showProjectionPanelMessage("Projection unavailable", fallback);
                    }
                }
                else if (ds["typeinstance"] == "graph") {
                    if ("layoutinstance" in ds) {
                        //
                    }
                }
            }
        }
    };

    this.loaddatasets = function () {
        var ob = new ServiceData("load datasets");
        ob.in.argms["type"] = 2;

        ob.event = function () {
            self.datafiles = this.ou;
            self.searchdataset('');
        };
        ob.start();
    };

    this.loadlayoutdbs = function () {
        //MPRO.clean();

        gelem('layoutchangenametxtdb').style.display = 'none';
        gelem('iddatasettitle').style.display = 'none';

        
/*         gelem('iddatasettitle').innerHTML = "";
        gelem("iddatasettitle").style.display = "none"
        gelem("layoutchangenametxtdb").style.display = "none" */
        
        self.loaddatasets();
        self.shifflayoutcontrols('iddatasetlayout');
    };

    this.listusers = function () {
        USERC.listUsers();
        if(self.adminid==1){
            gelem("idformnewuser").innerHTML = USERC.newUserForm();
        }
        self.shifflayoutcontrols('iduserlayout');
    };

    this.cleanfeatures = function () {
        // clear all layouts
        d3.select("#seq1").selectAll("svg").remove();
        d3.select("#vis").selectAll("svg").remove();
        d3.select("#seqedgehist").selectAll("svg").remove();
        self.hideFeaturesSelected("feature");
        self.renderXAISelectedSummary();
        gelem("infleft1").innerHTML = "";
        gelem("infright1").innerHTML = "";
        gelem("topleft1").innerHTML = "";
        gelem("topright1").innerHTML = "";

        self.exchageslider = 0;
        gelem('edgeslider').style.transform = 'rotate('+self.exchageslider+'deg)';
        self.keepselectvertex = -1;
    }

    this.cleaninstances = function () {
        d3.select("#visp").selectAll("svg").remove();
        d3.select("#seq2").selectAll("svg").remove();
        self.hideFeaturesSelected("instance");
        gelem("infleft2").innerHTML = "";
        gelem("infright2").innerHTML = "";
        gelem("topleft2").innerHTML = "";
        gelem("topright2").innerHTML = "";
    }

    this.opendataset = function (filename, usersame) {
        //console.log("filename, usersame", filename, usersame);

        self.isnamedbedited = usersame;
        
        self.USFOBJ.close();

        self.clearPointFiles();
        self.idinstancelabel = {};
        self.cleanfeatures();
        self.cleaninstances();

        self.featureselected = [];
        self.renderXAISelectedSummary();
        //self.ranking = [];
        self.intargetaction = false;
        self.intarget = false;
        self.target = "";
        self.exchageslider = 0;

        self.layoutfeatures = null;
        self.layoutinstance = null;

        self.datafileselected = filename;
        self.dataload = [];
        self.dataloadfile = "";
        self.dataloadcallbacks = [];
        self.isloadingcsv = false;
        self.getdatasetname();

        /*
        self.openfeature();
        self.openinstance();
        */
        self.shifflayoutcontrols('mainlayout');

        self.dequeLoadDataset(self.datafileselected);
        self.loadServerPointMedia();


    };

    this.searchdataset = function (txti) {
        let txt = trim(txti);
        gelem("idtabledatasets").innerHTML = "";
        let b = [];
        if (txt != "") {
            b = self.datafiles.filter(item => item.name.toLowerCase().indexOf(txt) > -1);
        }
        else {
            b = self.datafiles;
        }
        var stringhtml = "";
        var txtshare = "";

        if(self.multiuser==1){
            txtshare =  `<th>
                            <div style="width: 70px">
                                Is shared?
                            </div>
                        </th>
                        <th>
                            <div style="width: 60px">
                                Owner
                            </div>
                        </th>
                        `;
        }
        stringhtml = `<table class="table table-striped table-sm btn-table" style="margin: 0 auto">
                    <thead>
                        <tr>
                            <th style="width: 100%">
                                Name
                            </th>
                            `+txtshare+`
                            <th>
                                <div style="width: 150px">
                                    Last Modified
                                </div>
                            </th>
                            <th>
                                <div style="width: 150px">
                                    Actions
                                </div>
                            </th>
                        </tr>
                    <thead>
                    <tbody>`;

        isnoshare = `<i  class="fa fa-link fa-lg"
                            title="Shared"
                            style="color: #48ad09;"
                        ></i>`;
        //console.log("d",b);
        for (var i = 0; i < b.length; ++i) {
            var usersame = false;
            if (b[i]._id_user_query == b[i]._id_user) {
                usersame = true;
            }
    
            stringhtml += `<tr class="trover"
                                style="z-index:9">`;
            stringhtml += `<td
                                onclick="
                                    GFFOBJ.opendataset('`+ b[i]._id + `', `+usersame+`);
                                "
                                title="Open dataset"
                            >`+ b[i].name + `</td>`;

            issh = ""
            if (b[i].isshare == 1)
                issh = isnoshare;

            if (self.multiuser==1){
            stringhtml += `<td
                                onclick="
                                    GFFOBJ.opendataset('`+ b[i]._id + `', `+usersame+`);
                                "
                                title="Open dataset"
                            >`+ issh + `</td>`;
            }
            
            if (self.multiuser==1){
            stringhtml += `<td
                                onclick="
                                    GFFOBJ.opendataset('`+ b[i]._id + `', `+usersame+ `);
                                "
                                title="Open dataset"
                            >
                                <div
                                    style=" width: 45px;
                                            white-space: nowrap;
                                            overflow: hidden;
                                            text-overflow: ellipsis
                                    "
                                >`+ b[i].owner+ `</div></td>`;
            }

            ownclt_share = `
                            <a href="#" class="btn btn-light"
                                style="padding: 2px;"
                                title="Share dataset"
                                onclick="
                                    GFFOBJ.sharedataset('`+ b[i]._id + `');
                                "
                            >
                                <i  class="fa fa-link fa-lg"
                                    style="color: #48ad09;"
                                ></i>
                            </a>
                            <a href="#" class="btn btn-light"
                                style="padding: 2px;"
                                title="Unshare dataset"
                                onclick="
                                    GFFOBJ.unsharedataset('`+ b[i]._id + `');
                                "
                            >
                                <i class="fa fa-link fa-lg"
                                ></i>
                            </a>
                            `;
            ownclt_drop = `
                            <a href="#" class="btn btn-light"
                                style="padding: 2px;"
                                title="Drop dataset"
                                onclick="
                                    GFFOBJ.mw.option('',
                                    'Are you sure to delete the dataset?',
                                    GFFOBJ.dropdataset,
                                    ['`+b[i]._id+`']);
                                "
                            >
                                <i class="fa fa-trash fa-lg"
                                    style="color: #ff0000;"
                                ></i>
                            </a>`;

            ownclt = "";
            if (usersame) {
                if(self.multiuser==1){
                    ownclt += ownclt_share;
                    ownclt += ownclt_drop;
                }    
            }
        
            if(self.multiuser==0){
                ownclt += ownclt_drop;
            }

            stringhtml += `<td
                                onclick="
                                    GFFOBJ.opendataset('`+ b[i]._id + `', `+usersame+`);
                                "
                                title="Open dashboard"
                            >`+ b[i].dateupdate + `</td>`;
            stringhtml += `<td>
                                <div style="z-index:10">
                                    <a href="#" class="btn btn-light"
                                        style="padding: 2px;"
                                        title="Clone dataset"
                                        onclick="
                                        GFFOBJ.mw.option('',
                                            'Are you sure to clone the dataset?',
                                            GFFOBJ.clonedataset,
                                            ['`+b[i]._id+`']);
                                        "
                                    >
                                        <i  class="fa fa-clone fa-lg"
                                            style="color: #1479d9;"
                                        ></i>
                                    </a>
                                    <a href="#" class="btn btn-light"
                                        style="padding: 2px;"
                                        title="Download dataset"
                                        onclick="
                                            GFFOBJ.downloaddataset('`+ b[i]._id + `');
                                        "
                                    >
                                        <i class="fa fa-download fa-lg"
                                            style="color: #f5a742;"
                                        ></i>
                                    </a>
                                    `+ ownclt + `
                                </div>
                        </td>`;
            stringhtml += '</tr>';
        }
        stringhtml += '</tbody></table>';

        gelem("idtabledatasets").innerHTML = stringhtml;
    };

    this.getdatasetname = function () {
        var ob = new ServiceData("get data set name");
        ob.in.argms["type"] = 4;
        ob.in.argms["file"] = self.datafileselected;
        ob.event = function () {
            var txtnamedb = this.ou;
            if (self.isnamedbedited || self.multiuser==0){
                txtnamedb += `&nbsp;<i class="fas fa-edit fa-sm"></i>`;
            }
            gelem('iddatasettitle').innerHTML = txtnamedb;
            gelem('iddatasettitle').setAttribute("title","Change name");

            gelem('idtxtsearch').value = this.ou;
            gelem('idtextdbname').value = this.ou;
            self.datafileselectedname = this.ou;

            gelem('layoutchangenametxtdb').style.display = 'none';
            gelem('iddatasettitle').style.display = 'block';
        };
        ob.start();
    };

    this.uploadfiledata = function () {
        var fi = document.getElementById('fileu');
        var file = fi.files[0];
        if (!file || !/\.(csv|zip)$/i.test(file.name)) {
            self.mw.alert("", "Please use a CSV or ZIP containing one CSV");
            return;
        }
        MOPRO.show("Uploading and selecting representative rows");
        fetch("./upload", {
            method: "POST", credentials: "same-origin", body: file,
            headers: {"Content-Type": "application/octet-stream",
                      "X-Filename": encodeURIComponent(file.name),
                      "X-XSRFToken": document.querySelector('meta[name="xsrf-token"]').content}
        }).then(function (response) {
            if (!response.ok) throw new Error("Upload failed: " + response.status + " " + response.statusText);
            return response.json();
        }).then(function (result) {
            self.loaddatasets();
            self.mw.alert("", "Loaded " + result.selected_rows + " representative rows from " +
                          result.original_rows + " rows. The full CSV is retained on disk.");
        }).catch(function (error) { self.mw.alert("", error.message); })
          .finally(function () { MOPRO.hide(); fi.value = ""; });
    };

    this.loadfilecsv = function (callback) {
        if (self.dataloadfile == self.datafileselected && self.dataload && self.dataload.length > 0) {
            if (callback) {
                callback(self.dataload);
            }
            return;
        }

        if (callback) {
            self.dataloadcallbacks.push(callback);
        }

        if (self.isloadingcsv) {
            return;
        }

        self.isloadingcsv = true;

        function _commitLoad(rows) {
            self.dataload = rows || [];
            self.dataloadfile = self.datafileselected;
            self.isloadingcsv = false;
            var cbs = self.dataloadcallbacks.slice();
            self.dataloadcallbacks = [];
            for (var i = 0; i < cbs.length; ++i) { cbs[i](self.dataload); }
        }

        var datasetId = self.datafileselected;
        var base = "./data/" + datasetId + "/";
        var ob = new ServiceData("preparing representative preview");
        ob.in.argms = {type: 25, file: datasetId};
        ob.event = function () {
            if (!this.ou || !this.ou.ok) { _commitLoad([]); return; }
            fetch(base + "sample_row_ids.json", {credentials: "same-origin"})
                .then(function (response) {
                    if (!response.ok) throw new Error("Preview row IDs unavailable");
                    return response.json();
                }).then(function (ids) {
                    self.dataloadids = ids;
                    d3.csv(base + "sample.csv", function (rows) { _commitLoad(rows); });
                }).catch(function (error) { console.error(error); _commitLoad([]); });
        };
        ob.start();
    };

    this.padmove = function (wwwd) {
        var idviewpad = "#idpadmover";
        d3.select(idviewpad).selectAll("svg").remove();

        var xx = 0;
        var yy = 0;
        var dragpad = d3.drag()
            .on("start", function () {
                xx = d3.event.x;
                yy = d3.event.y;
            })
            .on("drag", function (d, i) {
                coordination(d3.event.x, d3.event.y);
            })
            .on("end", function () {

            });

        var svgpad = d3.select(idviewpad).append("svg")
            .attr("x", 0)
            .attr("y", 0)
            .attr("width", wwwd)
            .attr("height", wwwd)
            .append("rect")
            .attr("width", wwwd + "px")
            .attr("height", wwwd + "px")
            .attr("fill", "#ffdb56")
            .call(dragpad)
            .on("click", function () {

            });

        svgpad.append("g");

        function coordination(x, y) {
            if (x >= 0 && y >= 0 && x < wwwd && y < wwwd) {
                var xi = x - xx;
                var yi = y - yy;

                cx = (xi / wwwd) * 17.0;
                cy = (yi / wwwd) * 17.0;
                if (self.layoutfeatures && self.layoutfeatures.translatte) {
                    self.layoutfeatures.translatte(cx, cy);
                }
            }
        }
    };

    this.plotpaiercorrelate = function () {
        if (self.featureselected.length >= 2) {
            d3.select("#visp").selectAll("svg").remove();
            var featureids = self.getfeatureselected();
            var featurenames = featureids.map(function (id) {
                return self.datagff.fenames[id];
            }).filter(function (name) {
                return name !== undefined && name !== null;
            });
            var targetname = self.datagff.fenames[self.getTargetId()];
            var pairSize = Math.min(self.lwidth, self.lheight || self.lwidth);
            chart_correlation("#visp", self.dataload || [], featurenames, targetname, pairSize);
        }
        else {
            self.showProjectionPanelMessage(
                "Pair projection unavailable",
                "Select at least two features from any feature graph"
            );
        }
        //MOPRO.hide();
    };
    
/*     this.featureCheck = function (feid, feva) {
        var ob = new ServiceData("unselected feature");
        ob.in.argms["type"] = 22;
        ob.in.argms["file"] = self.datafileselected;
        ob.in.argms["feid"] = feid;
        ob.in.argms["feva"] = feva;
        ob.event = function () {
            response = this.ou;
            if (response["response"] != 0) {

            }
        };
        ob.start();
    }; */


    this.getUnselecteFeatures = function () {
        var ob = new ServiceData("get unselected features");
        ob.in.argms["type"] = 22;
        ob.in.argms["file"] = self.datafileselected;
        ob.event = function () {
            self.unselectedfeids = Array.isArray(this.ou) ? this.ou : [];
            self.USFOBJ.init();
            self.USFOBJ.load();
            self.USFOBJ.print();
        };
        ob.start();
    };





    this.dropdataset = function (iddb) {
        var ob = new ServiceData("drop dataset");
        ob.in.argms["type"] = 10;
        ob.in.argms["file"] = iddb;
        ob.event = function () {
            response = this.ou;
            self.loadlayoutdbs();
        };
        ob.start();
    };

    this.sharedataset = function (iddb) {
        var ob = new ServiceData("share dataset");
        ob.in.argms["type"] = 8;
        ob.in.argms["file"] = iddb;
        ob.event = function () {
            response = this.ou;
            self.loadlayoutdbs();
        };
        ob.start();
    };

    this.unsharedataset = function (iddb) {
        var ob = new ServiceData("unshare dataset");
        ob.in.argms["type"] = 9;
        ob.in.argms["file"] = iddb;
        ob.event = function () {
            response = this.ou;
            self.loadlayoutdbs();
        };
        ob.start();
    };

    this.clonedataset = function (iddb) {
        var ob = new ServiceData("clone dataset");
        ob.in.argms["type"] = 7;
        ob.in.argms["file"] = iddb;
        ob.event = function () {
            response = this.ou;
            self.loadlayoutdbs();
        };
        ob.start();
    };

    this.downloaddataset = function (iddb) {
        datin = new DataIO();
        datin.argms["type"] = 12;
        datin.argms["file"] = iddb;
        var url = "./query?data=" + encodeURIComponent(JSON.stringify(datin));
        window.location.href = url;
    };

    this.export2dprojwhole = function () {
        if (self.layoutinstance != null && self.layoutinstance.exwholeinstancesprj) {
            self.layoutinstance.exwholeinstancesprj();
        }
    };

    this.export2dprojselected = function () {
        if (self.layoutinstance != null && self.layoutinstance.exselectedinstancesprj) {
            self.layoutinstance.exselectedinstancesprj();
        }
    };

    this.exportfeat2datafile = function () {   
        if (self.datagff && self.datagff.layoutfeature && self.datagff.layoutfeature.graph &&
            Array.isArray(self.datagff.layoutfeature.graph.nodes) &&
            self.datagff.layoutfeature.graph.nodes.length > 0) {
            datin = new DataIO();
            datin.argms["type"] = 17;
            datin.argms["file"] = self.datafileselected;
            var url = "./query?data=" + encodeURIComponent(JSON.stringify(datin));
            window.location.href = url;
        }
    };

    this.updatedatasetname = function (e, newname) {
        newname = trim(newname);
        if (e.keyCode === 13) {
            if (self.datafileselected != "" && newname != "") {
                var ob = new ServiceData("update dataset name");
                ob.in.argms["type"] = 6;
                ob.in.argms["file"] = self.datafileselected;
                ob.in.argms["newname"] = newname;
                ob.event = function () {
                    response = this.ou;
                    self.getdatasetname();
                };
                ob.start();
            }
        }
    };

    this.logout = function () {
        window.location.href = "./logout";
    };

    this.changepassword = function () {
        pass = gelem("ipassword").value;
        npass = gelem("inpassword").value;
        rpass = gelem("inpasswordr").value;
        if (pass != "" && npass != "" && rpass != "") {
            if (npass == rpass) {
                var ob = new ServiceData("change password");
                ob.in.argms["type"] = 11;
                ob.in.argms["password"] = pass;
                ob.in.argms["newpassword"] = npass;
                ob.event = function () {
                    response = this.ou;
                    if (response["response"] == 1) {
                        self.mw.alert("","The new password was saved!", self.logout);
                    }
                };
                ob.start();
            }
        }
    };

    this.silhouette = function () {
        var status = "compute silhouette";
        var ob = new ServiceData(status);
        ob.in.argms["type"] = 13;
        ob.in.argms["file"] = self.datafileselected;
        ob.in.argms["statusval"] = status;
        ob.event = function () {
            response = this.ou;
            gelem("topleft2").textContent = typeof response === "number"
                ? "SILHOUETTE: " + response : "Silhouette needs at least two nontrivial target classes";
        };
        ob.start();
    };


    this.syncInTargetState = function (includeTarget) {
        self.intarget = !!includeTarget;
        self.intargetaction = !self.intarget;
        self.changeintargetbtn();
    };

    this.populateInstanceIdDropdown = function () {
        var selectEl = gelem("idinstanceslabels");
        if (!selectEl) return;
        var prevVal = selectEl.value;
        var names = (self.datagff && Array.isArray(self.datagff.fenames)) ? self.datagff.fenames : [];
        var targetId = String(self.target);
        var html = "<option value=''>None</option>";
        for (var i = 0; i < names.length; ++i) {
            // Exclude the target column (e.g. Category) from SELECT ID dropdown
            if (String(i) === targetId) {
                continue;
            }
            html += "<option value='" + i + "'>" + self.escapeHTML(names[i]) + "</option>";
        }
        selectEl.innerHTML = html;
        if (prevVal && prevVal !== targetId) {
            selectEl.value = prevVal;
        } else {
            selectEl.value = "";
        }
    };

    this.changeintarget = function () {
        //console.log("self.featureselectedWWWWWWWWWW::", self.featureselected);
        if (self.intargetaction) {
            self.intarget = true;
            self.intargetaction = false;
            if (self.featureselected.length > 0) {
                var istargetinclude = false;
                var taindex = self.auxfeatureselectedf[self.target];
                for (var e of self.featureselected) {
                    if (e == taindex) {
                        istargetinclude = true;
                        break;
                    }
                }
                if (istargetinclude == false) {
                    self.featureselected.push(taindex);
                }
                if (self.layoutfeatures != null) {
                    self.layoutfeatures.highlightforce(self.featureselected, {"silent": true});
                }
                self.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            }
        }
        else {
            self.intarget = false;
            self.intargetaction = true;
            ref = [];
            taindex = self.auxfeatureselectedf[self.target];
            for (var i in self.featureselected) {
                e = self.featureselected[i];
                if (e != taindex) {
                    ref.push(e);
                }
            }
            self.featureselected = ref;
            //console.log("self.featureselected", self.auxfeatureselectedf, self.featureselected);
            if (self.layoutfeatures != null) {
                self.layoutfeatures.highlightforce(self.featureselected, {"silent": true});
            }
            self.onFeatureSelectionChanged({"skipFeatureHighlight": true});
        }
        self.changeintargetbtn();
    };
    
    this.changeintargetbtn = function () {
        var el = gelem("btnintarget");
        if (self.intargetaction) {
            el.style.backgroundColor = '#f1f1f1';
        }
        else{
            el.style.backgroundColor = '#ffd70f';
        }
    };

    this.getNode = function(i){
        //return this.dataoutfeature.layoutfeature["graph"].nodes[i];
        return self.datagff.layoutfeature["graph"].nodes[i];
    };

    /* 
    //listfeatures
    this.showstatuspanel = function(ou){
        self.loadingverification();
        //self.shifflayoutcontrols("idstatedataset");
        //gelem("idstatusval").innerHTML = ou["statusval"];
        
    };
    */


    this.shifflayoutcontrols = function (el) {
        gelem('layoutchangenametxtdb').style.display = 'none';
        gelem('iddatasettitle').style.display = 'none';

        //fullScreen();
        gelem("idchangepasswordlayout").style.display = "none";
        gelem("iduserlayout").style.display = "none";
        gelem("iddatasetlayout").style.display = "none";
        gelem("idaboutlayout").style.display = "none";
        gelem("mainlayout").style.display = "none";
        //gelem("idstatedataset").style.display = "none";
        
        gelem(el).style.display = "block";

        if (gelem("idscreenshotallnav")) {
            gelem("idscreenshotallnav").style.display = (el == "mainlayout") ? "block" : "none";
        }
        if (el=="mainlayout"){
            gelem('layoutchangenametxtdb').style.display = 'none';
            gelem('iddatasettitle').style.display = 'block';
            var liveDims = self.computeResponsivePanelDimensions();
            self.lwidth = liveDims.width;
            self.lheight = liveDims.height;
            self.ldockheight = liveDims.dockHeight;
            self.applyPanelDimensions();
        }
    };

    this.showedgebundlingX = function () {
        if (!self.layoutfeatures || !self.layoutfeatures.showedgebundling) {
            return;
        }
        if (self.layoutfeatures.isupdatebundling) {
            setTimeout( function () {
                            MOPRO.show("making edge bundling");
                        }
                        , 1);
        }
        setTimeout(self.layoutfeatures.showedgebundling, 500);
    };

    this.applyPanelDimensions = function () {
        var panelIds = ["idlayout1", "idlayout2", "vis", "visp"];
        for (var pi = 0; pi < panelIds.length; ++pi) {
            var pEl = gelem(panelIds[pi]);
            if (pEl) {
                pEl.style.width = self.lwidth + "px";
                pEl.style.height = self.lheight + "px";
                pEl.style.minHeight = self.lheight + "px";
                pEl.style.minWidth = self.lwidth + "px";
                pEl.style.maxHeight = self.lheight + "px";
                pEl.style.maxWidth = self.lwidth + "px";
            }
        }

        // Lock outer panel columns (20px left strip + lwidth canvas + 26px right strip + 6px border + 6px padding = +58px)
        var panelTotalWidth = self.lwidth + 58;
        var outerPanels = ["gffPanelLeft", "gffPanelRight"];
        for (var op = 0; op < outerPanels.length; ++op) {
            var oEl = gelem(outerPanels[op]);
            if (oEl) {
                oEl.style.width = panelTotalWidth + "px";
                oEl.style.minWidth = panelTotalWidth + "px";
                oEl.style.maxWidth = panelTotalWidth + "px";
            }
        }
        var bottomDock = gelem("gffBottomDock");
        var dockMaxH = Math.max(120, (self.ldockheight || 160) - 6);
        if (bottomDock) {
            var dockWidth = (panelTotalWidth * 2) + 8;
            bottomDock.style.width = dockWidth + "px";
            bottomDock.style.maxWidth = dockWidth + "px";
        }
        var xaiSummary = gelem("xaiselectedsummary");
        if (xaiSummary) {
            xaiSummary.style.maxHeight = dockMaxH + "px";
        }
        var pfPanel = gelem("pointfilespanel");
        if (pfPanel) {
            pfPanel.style.maxHeight = dockMaxH + "px";
        }

        if (gelem("idlayout1bar")) {
            gelem("idlayout1bar").style.maxHeight = self.lheight + "px";
            gelem("idlayout1bar").style.minHeight = self.lheight + "px";
        }
        if (gelem("idlayout2bar")) {
            gelem("idlayout2bar").style.maxHeight = self.lheight + "px";
            gelem("idlayout2bar").style.minHeight = self.lheight + "px";
        }
    };

    this.handleViewportResize = function () {
        var dims = self.computeResponsivePanelDimensions();
        if (Math.abs(dims.width - self.lwidth) < 6 && Math.abs(dims.height - self.lheight) < 6) {
            return;
        }
        self.lwidth = dims.width;
        self.lheight = dims.height;
        self.ldockheight = dims.dockHeight;
        self.applyPanelDimensions();

        // Redraw active layouts smoothly to fit the new screen dimensions
        var mainEl = gelem("mainlayout");
        if (mainEl && mainEl.style.display !== "none" && self.datagff) {
            if (self.datagff.layoutfeature && self.datagff.configfeature) {
                var savedTarget = self.getTargetId();
                var savedSelected = Array.isArray(self.featureselected) ? self.featureselected.slice() : [];
                self.processFeaturesResults(self.datagff);
                if (savedTarget >= 0 && gelem("target") && savedTarget < gelem("target").options.length) {
                    gelem("target").selectedIndex = savedTarget;
                    self.target = savedTarget;
                }
                if (savedSelected.length > 0 && self.layoutfeatures && self.layoutfeatures.highlightforce) {
                    self.featureselected = savedSelected;
                    self.layoutfeatures.highlightforce(self.featureselected, {"silent": true});
                }
            }
            if (self.datagff.layoutinstance && Array.isArray(self.datagff.layoutinstance.points) && self.datagff.layoutinstance.points.length > 0) {
                self.processInstancesResults(self.datagff);
            }
        }
    };

    this.main = function () {
        //setInterval(self.loadingverification, 3000);
        

        MOPRO.main();
        self.mw.main();
        
        self.loaddatasets();
        
        self.shifflayoutcontrols("iddatasetlayout");
        // Legacy yellow padmover removed in favor of Hand pan tool and Hold-Space pan

        self.applyPanelDimensions();

        var scheduleResize = function () {
            if (self._resizeTimer) {
                clearTimeout(self._resizeTimer);
            }
            self._resizeTimer = setTimeout(function () {
                self.handleViewportResize();
            }, 180);
        };
        window.addEventListener("resize", scheduleResize);
        document.addEventListener("fullscreenchange", scheduleResize);

        if (self.adminid==1 && self.multiuser==1){
            gelem("iduserlistop").style.display = "block";
        }
        

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                self.closePointDataModal();
            }
            var tag = event.target && event.target.tagName ? event.target.tagName.toUpperCase() : "";
            var isTyping = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (event.target && event.target.isContentEditable);
            var modalOpen = gelem("pointdatamodal") && gelem("pointdatamodal").classList.contains("open");
            if ((event.key === "Control" || event.ctrlKey) && !isTyping && !modalOpen) {
                if (!self._ctrlPanActive) {
                    self._ctrlPanActive = true;
                    self.applyPanModeState();
                }
            }
            if ((event.code === "Space" || event.key === " ") && !isTyping && !modalOpen) {
                event.preventDefault();
                if (!self._spacePanActive) {
                    self._spacePanActive = true;
                    self.applyPanModeState();
                }
                return;
            }
            self.setkey(event);
        });
        document.addEventListener('keyup', (event) => {
            if ((event.key === "Control" || !event.ctrlKey) && self._ctrlPanActive) {
                self._ctrlPanActive = false;
                self.applyPanModeState();
            }
            if ((event.code === "Space" || event.key === " ") && self._spacePanActive) {
                self._spacePanActive = false;
                self.applyPanModeState();
            }
            self.hidekey();
        });
        window.addEventListener('blur', () => {
            if (self._ctrlPanActive || self._spacePanActive) {
                self._ctrlPanActive = false;
                self._spacePanActive = false;
                self.applyPanModeState();
            }
            self.hidekey();
        });
        self.hidekey();

        CCTT.main();

    };

    this.fullScreen = function () {
        var isInFullScreen = (document.fullscreenElement && document.fullscreenElement !== null) ||
        (document.webkitFullscreenElement && document.webkitFullscreenElement !== null) ||
        (document.mozFullScreenElement && document.mozFullScreenElement !== null) ||
        (document.msFullscreenElement && document.msFullscreenElement !== null);

        if (!isInFullScreen) {
            self.setfullScreen();
        } else {
            self.exitfullScreen();
        }
    };

    this.setfullScreen = function () {
        var docElm = document.documentElement;
        if (docElm.requestFullscreen) {
            docElm.requestFullscreen();
        } else if (docElm.mozRequestFullScreen) {
            docElm.mozRequestFullScreen();
        } else if (docElm.webkitRequestFullScreen) {
            docElm.webkitRequestFullScreen();
        } else if (docElm.msRequestFullscreen) {
            docElm.msRequestFullscreen();
        }
    };

    this.exitfullScreen = function () {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    };
    
    this._serializeFittedSvg = function (svgNode, cssContent, pad) {
        pad = pad !== undefined ? pad : 20;
        var clone = svgNode.cloneNode(true);
        clone.setAttribute("version", "1.1");
        clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
        clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");

        // Compute tight bounding box across all rendered graphics so nothing is clipped
        var bbox = null;
        try {
            bbox = svgNode.getBBox();
        } catch (e) {}
        var rect = svgNode.getBoundingClientRect ? svgNode.getBoundingClientRect() : null;
        var fallbackW = parseFloat(svgNode.getAttribute("width")) || (rect && rect.width) || 600;
        var fallbackH = parseFloat(svgNode.getAttribute("height")) || (rect && rect.height) || 600;

        var vx = 0, vy = 0, vw = fallbackW, vh = fallbackH;
        if (bbox && isFinite(bbox.width) && isFinite(bbox.height) && bbox.width > 1 && bbox.height > 1) {
            vx = bbox.x - pad;
            vy = bbox.y - pad;
            vw = bbox.width + pad * 2;
            vh = bbox.height + pad * 2;
        }
        clone.setAttribute("viewBox", vx + " " + vy + " " + vw + " " + vh);
        clone.setAttribute("width", Math.ceil(vw));
        clone.setAttribute("height", Math.ceil(vh));

        // White background rect so PNG/SVG exports are crisp and readable
        var bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        bg.setAttribute("x", vx);
        bg.setAttribute("y", vy);
        bg.setAttribute("width", vw);
        bg.setAttribute("height", vh);
        bg.setAttribute("fill", "#ffffff");
        clone.insertBefore(bg, clone.firstChild);

        var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        var style = document.createElementNS("http://www.w3.org/2000/svg", "style");
        style.setAttribute("type", "text/css");
        style.textContent = cssContent || "";
        defs.appendChild(style);
        clone.insertBefore(defs, clone.firstChild);

        var xml = new XMLSerializer().serializeToString(clone);
        return { xml: xml, width: Math.ceil(vw), height: Math.ceil(vh) };
    };

    this._svgXmlToImage = function (xml) {
        return new Promise(function (resolve, reject) {
            var blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
            var url = URL.createObjectURL(blob);
            var img = new Image();
            img.onload = function () {
                URL.revokeObjectURL(url);
                resolve(img);
            };
            img.onerror = function (err) {
                URL.revokeObjectURL(url);
                reject(err);
            };
            img.src = url;
        });
    };

    this.captureCanvasScreenshot = function (idp, title) {
        var svgNode = d3.select(idp).select("svg").node();
        if (!svgNode) {
            self.mw.alert("Screenshot", "No visualization is currently rendered in this canvas.");
            return;
        }
        $.get("./lib/style.css", function (cssContent) {
            var fitted = self._serializeFittedSvg(svgNode, cssContent, 24);
            var scale = 2;
            var maxDim = 2400;
            var outW = Math.min(maxDim, Math.max(400, fitted.width * scale));
            var outH = Math.round(outW * (fitted.height / Math.max(1, fitted.width)));
            self._svgXmlToImage(fitted.xml).then(function (img) {
                var canvas = document.createElement("canvas");
                canvas.width = outW;
                canvas.height = outH;
                var ctx = canvas.getContext("2d");
                ctx.fillStyle = "#ffffff";
                ctx.fillRect(0, 0, outW, outH);
                ctx.drawImage(img, 0, 0, outW, outH);
                canvas.toBlob(function (pngBlob) {
                    if (!pngBlob) return;
                    var safeName = sanitizeExportFilename(self.datafileselectedname, "gff");
                    var safeTitle = sanitizeExportFilename(title, "canvas");
                    var url = URL.createObjectURL(pngBlob);
                    var a = document.createElement("a");
                    a.href = url;
                    a.download = safeName + "_" + safeTitle + ".png";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
                }, "image/png");
            }).catch(function () {
                self.mw.alert("Screenshot", "Could not render PNG screenshot; try SVG export instead.");
            });
        });
    };

    this._wrapCanvasText = function (ctx, str, maxWidth) {
        var words = String(str || "").split(/\s+/);
        var lines = [];
        var line = "";
        for (var i = 0; i < words.length; ++i) {
            var test = line ? (line + " " + words[i]) : words[i];
            if (ctx.measureText(test).width > maxWidth && line) {
                lines.push(line);
                line = words[i];
            } else {
                line = test;
            }
        }
        if (line) lines.push(line);
        return lines.length ? lines : [""];
    };

    this._renderHtmlPanelToImage = function (panelEl, cssContent, targetWidth) {
        return new Promise(function (resolve) {
            var w = Math.max(820, targetWidth || panelEl.clientWidth || 960);
            var pad = 16;

            // Specialized crisp Canvas 2D renderer for Associated Point Files grid
            if (panelEl.id === "pointfilespanel") {
                var cards = panelEl.querySelectorAll(".point-file-card");
                var cardW = 148;
                var cardH = 112;
                var gap = 10;
                var cols = Math.max(2, Math.floor((w - pad * 2 + gap) / (cardW + gap)));
                var shown = Math.min(cards.length, 48);
                var rows = Math.max(1, Math.ceil(shown / cols));
                var headerH = 34;
                var totalH = pad * 2 + headerH + rows * (cardH + gap);

                var c = document.createElement("canvas");
                c.width = w;
                c.height = totalH;
                var ctx = c.getContext("2d");
                ctx.fillStyle = "#f8fafc";
                ctx.fillRect(0, 0, w, totalH);
                ctx.strokeStyle = "#cbd5e1";
                ctx.strokeRect(1, 1, w - 2, totalH - 2);

                ctx.fillStyle = "#0f172a";
                ctx.font = "bold 14px Sans-serif";
                ctx.fillText("Associated Point Files (" + shown + " items)", pad, pad + 18);

                for (var idx = 0; idx < shown; ++idx) {
                    var card = cards[idx];
                    var col = idx % cols;
                    var row = Math.floor(idx / cols);
                    var x = pad + col * (cardW + gap);
                    var y = pad + headerH + row * (cardH + gap);

                    ctx.fillStyle = "#ffffff";
                    ctx.fillRect(x, y, cardW, cardH);
                    ctx.strokeStyle = card.classList.contains("active") ? "#029ff1" : "#cbd5e1";
                    ctx.lineWidth = card.classList.contains("active") ? 2 : 1;
                    ctx.strokeRect(x, y, cardW, cardH);

                    var imgEl = card.querySelector("img");
                    if (imgEl && imgEl.complete && imgEl.naturalWidth > 0) {
                        try {
                            ctx.drawImage(imgEl, x + 6, y + 6, cardW - 12, 66);
                        } catch (e) {
                            ctx.fillStyle = "#e2e8f0";
                            ctx.fillRect(x + 6, y + 6, cardW - 12, 66);
                        }
                    } else {
                        ctx.fillStyle = "#e2e8f0";
                        ctx.fillRect(x + 6, y + 6, cardW - 12, 66);
                        ctx.fillStyle = "#475569";
                        ctx.font = "bold 12px Sans-serif";
                        var iconLabel = card.querySelector(".fa-volume-up") ? "AUDIO"
                            : (card.querySelector(".fa-video") ? "VIDEO"
                            : (card.querySelector(".fa-file-alt") ? "TEXT" : "DATA"));
                        ctx.fillText(iconLabel, x + 48, y + 44);
                    }

                    var nameEl = card.querySelector(".point-file-name");
                    var metaEl = card.querySelector(".point-file-meta");
                    ctx.fillStyle = "#1e293b";
                    ctx.font = "bold 11px Sans-serif";
                    var fname = (nameEl ? nameEl.textContent : "").trim();
                    if (fname.length > 20) fname = fname.slice(0, 19) + "...";
                    ctx.fillText(fname, x + 6, y + 88);

                    ctx.fillStyle = "#64748b";
                    ctx.font = "10px Sans-serif";
                    var fmeta = (metaEl ? metaEl.textContent : "").trim();
                    if (fmeta.length > 22) fmeta = fmeta.slice(0, 21) + "...";
                    ctx.fillText(fmeta, x + 6, y + 103);
                }
                resolve({ img: c, w: w, h: totalH });
                return;
            }

            // Pure Canvas 2D renderer for Contrastive & Counterfactual Subspace Inspector / XAI Summary
            var tmpC = document.createElement("canvas");
            var tmpCtx = tmpC.getContext("2d");
            tmpCtx.font = "12px Sans-serif";
            var rawLines = String(panelEl.innerText || "").split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean);
            // Strip button label noise like "Screenshot"
            rawLines = rawLines.filter(function (ln) { return ln !== "Screenshot"; });

            var wrapped = [];
            for (var li = 0; li < rawLines.length; ++li) {
                var ln = rawLines[li];
                var isHeading = li === 0 || /Contrastive|Projection Quality|Local Contrastive|Counterfactual|Top Selected/i.test(ln);
                tmpCtx.font = isHeading ? "bold 13px Sans-serif" : "12px Sans-serif";
                var parts = self._wrapCanvasText(tmpCtx, ln, w - pad * 2);
                for (var pi = 0; pi < parts.length; ++pi) {
                    wrapped.push({ text: parts[pi], bold: isHeading && pi === 0 });
                }
            }

            // If structured contrastive drivers exist, render visual Cohen's d bars too
            var drivers = (self.contrastiveData && self.contrastiveData.status === "ok" && Array.isArray(self.contrastiveData.drivers))
                ? self.contrastiveData.drivers.slice(0, 8) : [];
            var lineH = 19;
            var barsH = drivers.length > 0 ? (32 + drivers.length * 22) : 0;
            var textH = Math.max(40, wrapped.length * lineH);
            var totalH = pad * 2 + barsH + textH + 12;

            var c2 = document.createElement("canvas");
            c2.width = w;
            c2.height = totalH;
            var ctx2 = c2.getContext("2d");
            ctx2.fillStyle = "#eef4ff";
            ctx2.fillRect(0, 0, w, totalH);
            ctx2.strokeStyle = "#b8cae6";
            ctx2.strokeRect(1, 1, w - 2, totalH - 2);

            var curY = pad + 14;
            if (drivers.length > 0) {
                ctx2.fillStyle = "#006064";
                ctx2.font = "bold 14px Sans-serif";
                var modeLbl = self.contrastiveData.mode === "group_vs_group" ? "Group A vs Group B" : "Group A vs Rest";
                ctx2.fillText("Contrastive & Counterfactual Subspace Inspector — " + modeLbl + " (Top Drivers)", pad, curY);
                curY += 18;
                var maxAbsD = 0.01;
                for (var d1 = 0; d1 < drivers.length; ++d1) {
                    maxAbsD = Math.max(maxAbsD, Math.abs(Number(drivers[d1].cohens_d || 0)));
                }
                var labelW = 200;
                var barMaxW = Math.max(180, w - pad * 2 - labelW - 140);
                for (var d2 = 0; d2 < drivers.length; ++d2) {
                    var dr = drivers[d2];
                    var dVal = Number(dr.cohens_d || 0);
                    var frac = Math.min(1, Math.abs(dVal) / maxAbsD);
                    ctx2.fillStyle = "#1e293b";
                    ctx2.font = "bold 11px Sans-serif";
                    var dName = String(dr.name || dr.feature || ("f" + d2));
                    if (dName.length > 26) dName = dName.slice(0, 25) + "...";
                    ctx2.fillText(dName, pad, curY + 12);

                    ctx2.fillStyle = "#dbeafe";
                    ctx2.fillRect(pad + labelW, curY + 2, barMaxW, 13);
                    ctx2.fillStyle = dVal >= 0 ? "#0284c7" : "#dc2626";
                    ctx2.fillRect(pad + labelW, curY + 2, Math.max(3, Math.round(barMaxW * frac)), 13);

                    ctx2.fillStyle = "#334155";
                    ctx2.font = "11px monospace";
                    ctx2.fillText("d=" + dVal.toFixed(2) + (dr.fdr !== undefined ? ("  q=" + Number(dr.fdr).toExponential(1)) : ""), pad + labelW + barMaxW + 8, curY + 12);
                    curY += 22;
                }
                curY += 10;
            }

            for (var wi = 0; wi < wrapped.length; ++wi) {
                ctx2.fillStyle = wrapped[wi].bold ? "#0f172a" : "#334155";
                ctx2.font = wrapped[wi].bold ? "bold 13px Sans-serif" : "12px Sans-serif";
                ctx2.fillText(wrapped[wi].text, pad, curY);
                curY += lineH;
            }

            resolve({ img: c2, w: w, h: totalH });
        });
    };

    this.captureHtmlPanelScreenshot = function (panelId, title) {
        var el = gelem(panelId);
        if (!el || el.style.display === "none" || !el.innerHTML.trim()) {
            self.mw.alert("Screenshot", "This panel is currently empty or hidden.");
            return;
        }
        var targetW = Math.max(900, el.clientWidth || 1000);
        self._renderHtmlPanelToImage(el, "", targetW).then(function (res) {
            res.img.toBlob(function (pngBlob) {
                if (!pngBlob) return;
                var safeName = sanitizeExportFilename(self.datafileselectedname, "gff");
                var safeTitle = sanitizeExportFilename(title, panelId);
                var url = URL.createObjectURL(pngBlob);
                var a = document.createElement("a");
                a.href = url;
                a.download = safeName + "_" + safeTitle + ".png";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
            }, "image/png");
        }).catch(function (err) {
            console.error("Panel screenshot error:", err);
            self.mw.alert("Screenshot", "Could not render PNG screenshot for this panel.");
        });
    };

    this.captureAllCanvasesScreenshot = function () {
        var specs = [
            { sel: "#vis", title: "Feature Graph", sub: (gelem("topleft1") ? gelem("topleft1").textContent : "") + " " + (gelem("topright1") ? gelem("topright1").textContent : "") },
            { sel: "#visp", title: "Instance Projection", sub: (gelem("topleft2") ? gelem("topleft2").textContent : "") + " " + (gelem("topright2") ? gelem("topright2").textContent : "") },
            { sel: "#featselectfeaturecontent", title: "Selected Features", sub: gelem("featselectfeaturetitle") ? gelem("featselectfeaturetitle").textContent : "", requireVisibleId: "featselectfeature" },
            { sel: "#featselectinstancecontent", title: "Selected Instances", sub: gelem("featselectinstancetitle") ? gelem("featselectinstancetitle").textContent : "", requireVisibleId: "featselectinstance" }
        ];
        var active = [];
        for (var i = 0; i < specs.length; ++i) {
            var sp = specs[i];
            if (sp.requireVisibleId) {
                var host = gelem(sp.requireVisibleId);
                if (!host || host.style.display === "none") continue;
            }
            var node = d3.select(sp.sel).select("svg").node();
            if (node) {
                active.push({ spec: sp, node: node });
            }
        }
        if (active.length === 0) {
            self.mw.alert("Screenshot All", "No active visualizations to capture yet.");
            return;
        }
        $.get("./lib/style.css", function (cssContent) {
            var cols = active.length === 1 ? 1 : 2;
            var cellW = 1000;
            var cellH = 820;
            var headerH = 54;
            var cellHeaderH = 38;
            var gap = 20;
            var pad = 20;
            var fullDockW = cols * cellW + (cols - 1) * gap;

            var jobs = active.map(function (item) {
                var fitted = self._serializeFittedSvg(item.node, cssContent, 24);
                return self._svgXmlToImage(fitted.xml).then(function (img) {
                    return { kind: "svg", spec: item.spec, img: img, w: fitted.width, h: fitted.height };
                });
            });

            var dockSpecs = [
                { id: "xaiselectedsummary", title: "Contrastive & Counterfactual Subspace Inspector / XAI Summary" },
                { id: "pointfilespanel", title: "Associated Point Files Viewer" }
            ];
            var dockJobs = [];
            for (var di = 0; di < dockSpecs.length; ++di) {
                (function (dsp) {
                    var el = gelem(dsp.id);
                    if (el && el.style.display !== "none" && el.innerHTML.trim() !== "") {
                        dockJobs.push(
                            self._renderHtmlPanelToImage(el, cssContent, fullDockW - 24).then(function (res) {
                                return { kind: "dock", title: dsp.title, img: res.img, w: res.w, h: res.h };
                            }).catch(function () { return null; })
                        );
                    }
                })(dockSpecs[di]);
            }

            Promise.all([Promise.all(jobs), Promise.all(dockJobs)]).then(function (both) {
                var rendered = both[0];
                var docks = both[1].filter(Boolean);
                var rows = Math.ceil(rendered.length / cols);
                var totalW = pad * 2 + fullDockW;
                var gridBottomY = pad + headerH + rows * (cellH + cellHeaderH) + Math.max(0, rows - 1) * gap;
                var dockExtraH = 0;
                for (var dk = 0; dk < docks.length; ++dk) {
                    dockExtraH += gap + cellHeaderH + docks[dk].h + 24;
                }
                var totalH = gridBottomY + dockExtraH + pad;

                var canvas = document.createElement("canvas");
                canvas.width = totalW;
                canvas.height = totalH;
                var ctx = canvas.getContext("2d");
                ctx.fillStyle = "#f1f5f9";
                ctx.fillRect(0, 0, totalW, totalH);

                // Top banner
                ctx.fillStyle = "#120c36";
                ctx.fillRect(0, 0, totalW, headerH);
                ctx.fillStyle = "#ffffff";
                ctx.font = "bold 20px Sans-serif";
                var dsLabel = self.datafileselectedname || "GFF+ Workspace";
                ctx.fillText("GFF+ Snapshot — " + dsLabel, pad, 34);

                for (var idx = 0; idx < rendered.length; ++idx) {
                    var r = rendered[idx];
                    var colIdx = idx % cols;
                    var rowIdx = Math.floor(idx / cols);
                    var x0 = pad + colIdx * (cellW + gap);
                    var y0 = pad + headerH + rowIdx * (cellH + cellHeaderH + gap);

                    ctx.fillStyle = "#ffffff";
                    ctx.fillRect(x0, y0, cellW, cellH + cellHeaderH);
                    ctx.strokeStyle = "#cbd5e1";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(x0, y0, cellW, cellH + cellHeaderH);

                    ctx.fillStyle = "#1e293b";
                    ctx.font = "bold 15px Sans-serif";
                    ctx.fillText(r.spec.title, x0 + 12, y0 + 24);
                    if (r.spec.sub && r.spec.sub.trim()) {
                        ctx.fillStyle = "#475569";
                        ctx.font = "12px Sans-serif";
                        ctx.fillText(r.spec.sub.trim().slice(0, 85), x0 + 210, y0 + 24);
                    }

                    // Preserve aspect ratio and fit 100% inside the cell
                    var innerPad = 14;
                    var availW = cellW - innerPad * 2;
                    var availH = cellH - innerPad * 2;
                    var ratio = Math.min(availW / Math.max(1, r.w), availH / Math.max(1, r.h));
                    var drawW = r.w * ratio;
                    var drawH = r.h * ratio;
                    var dx = x0 + innerPad + (availW - drawW) / 2;
                    var dy = y0 + cellHeaderH + innerPad + (availH - drawH) / 2;
                    ctx.drawImage(r.img, dx, dy, drawW, drawH);
                }

                // Render visible bottom dock panels (Contrastive Inspector & Associated Point Files)
                var curY = gridBottomY + gap;
                for (var dIdx = 0; dIdx < docks.length; ++dIdx) {
                    var dkObj = docks[dIdx];
                    var boxH = cellHeaderH + dkObj.h + 24;
                    ctx.fillStyle = "#ffffff";
                    ctx.fillRect(pad, curY, fullDockW, boxH);
                    ctx.strokeStyle = "#cbd5e1";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(pad, curY, fullDockW, boxH);

                    ctx.fillStyle = "#1e293b";
                    ctx.font = "bold 15px Sans-serif";
                    ctx.fillText(dkObj.title, pad + 12, curY + 24);
                    ctx.drawImage(dkObj.img, pad + 12, curY + cellHeaderH + 8, dkObj.w, dkObj.h);
                    curY += boxH + gap;
                }

                canvas.toBlob(function (pngBlob) {
                    if (!pngBlob) return;
                    var safeName = sanitizeExportFilename(self.datafileselectedname, "gff");
                    var url = URL.createObjectURL(pngBlob);
                    var a = document.createElement("a");
                    a.href = url;
                    a.download = safeName + "_all_canvases.png";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
                }, "image/png");
            }).catch(function () {
                self.mw.alert("Screenshot All", "Could not generate combined PNG screenshot.");
            });
        });
    };

    this.save_as_svg = function (idp, title) {
        var svgNode = d3.select(idp).select("svg").node();
        if (!svgNode) {
            self.mw.alert("Export SVG", "No visualization is currently rendered to export.");
            return;
        }
        $.get("./lib/style.css", function (cssContent) {
            var clone = svgNode.cloneNode(true);
            clone.setAttribute("version", "1.1");
            clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
            clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
            var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
            var style = document.createElementNS("http://www.w3.org/2000/svg", "style");
            style.setAttribute("type", "text/css");
            style.textContent = cssContent || "";
            defs.appendChild(style);
            clone.insertBefore(defs, clone.firstChild);

            var serialized = new XMLSerializer().serializeToString(clone);
            var fname = sanitizeExportFilename(self.datafileselectedname, "chart") + "_" +
                sanitizeExportFilename(title, "view") + ".svg";
            downloadBlobFile(serialized, fname, "image/svg+xml;charset=utf-8");
        });
    };

    this.featureselectionbyfiltername = function (txt2filter) {
        var featsel = [];
        var txtfilter = String(txt2filter || "").split('&&');
        var lowerLookup = {};
        for (var fname in self.lfenamesindex) {
            if (Object.prototype.hasOwnProperty.call(self.lfenamesindex, fname)) {
                lowerLookup[fname.toLowerCase()] = self.lfenamesindex[fname];
            }
        }

        var nfilter = [];
        for (var wd of txtfilter) {
            wd = trim(wd);
            if (!wd) continue;
            var fid = self.lfenamesindex[wd];
            if (fid === undefined) {
                fid = lowerLookup[wd.toLowerCase()];
            }
            if (fid !== undefined && (fid in self.auxfeatureselectedf)) {
                var index = self.auxfeatureselectedf[fid];
                featsel.push(index);
                nfilter.push(self.datagff.fenames[fid]);
            }
        }
        if (featsel.length > 0) {
            self.featureselected = featsel;
            self.normalizeFeatureSelection();
            if (self.layoutfeatures && self.layoutfeatures.highlightforce) {
                self.layoutfeatures.highlightforce(self.featureselected, {"silent": true});
            }
            gelem("fesenanetxt").value = nfilter.join('&&');
            self.onFeatureSelectionChanged({"skipFeatureHighlight": true});
        } else {
            self.mw.alert("Filter", "No matching feature names found. Separate multiple feature names with &&.");
        }
    };

    this.setToolpiltex = function (ex, ey, txt) {
        gelem("floatdiv").innerHTML = "";
        gelem('floatdiv').style.left = (ex + 2) + "px";
        gelem('floatdiv').style.top = (ey - 23) + "px";
        gelem('floatdiv').style.display = "block";
        gelem("floatdiv").innerHTML = txt;
    };

    this.hideToolpiltex = function () {
        gelem("floatdiv").style.display = "none";
        gelem("floatdiv").innerHTML = "";
    };

    this.setkey = function (event) {
        if (event.ctrlKey || event.altKey ) {
            self.ispresskey = 1;
            //console.log("event.ctrlKey || event.altKey");
        }
        else if (event.shiftKey) {
            self.ispresskey = 2;
            //console.log(event.shiftKey);
        }

    };
    this.hidekey = function () {
        self.ispresskey = 0;
        //console.log("self.ispresskey", self.ispresskey);
    };

    this.viewFeaturesSelected = function (opt) {
        let datfe = [];
        let maxv = 0;
        let title = "";
        var chartSize = Math.max(360, Math.min(480, (parseInt(self.lwidth, 10) || 500) - 16));
        if (opt == "feature") {
            title = (self.datagff && self.datagff.configfeature && self.datagff.configfeature.relevance)
                ? self.datagff.configfeature.relevance : "Selected Features";
            var cfgNodes = (self.datagff && self.datagff.configfeature && Array.isArray(self.datagff.configfeature.nodes))
                ? self.datagff.configfeature.nodes : [];
            self.normalizeFeatureSelection();
            for (var i of self.featureselected) {
                var item = self.getNode(i);
                if (!item || item.category == 1) continue;
                var rawScore = (item.weight !== undefined && item.weight !== null)
                    ? parseFloat(item.weight)
                    : ((cfgNodes[item.name] && cfgNodes[item.name].weight !== undefined)
                        ? parseFloat(cfgNodes[item.name].weight) : 0.0);
                if (!isFinite(rawScore)) rawScore = 0.0;
                datfe.push({
                    "label": item.label,
                    "color": VertexColorF(rawScore),
                    "score": rawScore,
                    "scorenorm": rawScore,
                });
                if (rawScore > maxv) {
                    maxv = rawScore;
                }
            }

            var denom = maxv > 0 ? maxv : 1.0;
            for (var k = 0; k < datfe.length; ++k) {
                datfe[k]["scorenorm"] = maxv > 0 ? (datfe[k]["scorenorm"] / denom) : 1.0;
            }
            gelem("featselectfeaturetitle").innerHTML = title + " (" + datfe.length + ")";
            if (datfe.length > 0) {
                gelem("featselectfeaturecontent").innerHTML = "";
                chart_circularhist(self, datfe, "#featselectfeaturecontent", chartSize, chartSize);
            } else {
                gelem("featselectfeaturecontent").innerHTML =
                    "<div style='padding: 40px 16px; color: #475569; text-align: center;'>No features selected. Select features from the feature graph first.</div>";
            }
        }
        else if (opt == "instance") {
            title = (self.datagff && self.datagff.configinstance && self.datagff.configinstance.relevance)
                ? self.datagff.configinstance.relevance : "Instance Features";
            var featt = (self.datagff && self.datagff.configinstance && Array.isArray(self.datagff.configinstance.featureselected))
                ? self.datagff.configinstance.featureselected : [];
            var insNodes = (self.datagff && self.datagff.configinstance && Array.isArray(self.datagff.configinstance.nodes))
                ? self.datagff.configinstance.nodes : [];
            for (var e of featt) {
                var idx = self.auxfeatureselectedi[e];
                var item = insNodes[idx];
                if (!item || item.category == 1) continue;
                var rawScore = parseFloat(item.weight || 0.0);
                if (!isFinite(rawScore)) rawScore = 0.0;
                datfe.push({
                    "label": item.label,
                    "color": VertexColorF(rawScore),
                    "score": rawScore,
                    "scorenorm": rawScore,
                });
                if (rawScore > maxv) {
                    maxv = rawScore;
                }
            }
            var denomI = maxv > 0 ? maxv : 1.0;
            for (var m = 0; m < datfe.length; ++m) {
                datfe[m]["scorenorm"] = maxv > 0 ? (datfe[m]["scorenorm"] / denomI) : 1.0;
            }
            gelem("featselectinstancetitle").innerHTML = title + " (" + datfe.length + ")";
            if (datfe.length > 0) {
                gelem("featselectinstancecontent").innerHTML = "";
                chart_circularhist(self, datfe, "#featselectinstancecontent", chartSize, chartSize);
            } else {
                gelem("featselectinstancecontent").innerHTML =
                    "<div style='padding: 40px 16px; color: #475569; text-align: center;'>No features recorded for the current projection.</div>";
            }
        }
    };

    this.hideFeaturesSelected = function (opt) {
        if (opt == "feature") {
            gelem('featselectfeature').style.display = 'none';
        }
        else if (opt == "instance") {
            gelem('featselectinstance').style.display = 'none';
        }
    };

    this.initradiallayout = function () {
        self.layoutfeatures.initradiallayout();
    };

    this.changecolorstable = function (c) {
        if(self.colorstableshitttype==1){
            CCTT.id = c;
            VertexColorF = CCTT.interpolate();

            if (self.layoutfeatures && self.layoutfeatures.selectbythreshold) {
                chart_palettecolors(self.layoutfeatures.selectbythreshold,
                    "seq1", 20, Math.max(200, (self.lheight || self.lwidth) - 20), VertexColorF);
            }

            if (self.layoutfeatures) {
                self.layoutfeatures.vertexcolorf = VertexColorF;
                if (self.layoutfeatures.updatecolors) {
                    self.layoutfeatures.updatecolors();
                }
                else if (self.layoutfeatures.applyNodeStyles) {
                    self.layoutfeatures.applyNodeStyles();
                }
            }
        }
        else if(self.colorstableshitttype==2){
            CCTT.id = c;
            EdgeColorF = CCTT.interpolate();
            if (self.layoutfeatures && self.layoutfeatures.updatelinkoption) {
                chart_histogram(self.setToolpiltex,
                    self.hideToolpiltex,
                    self.layoutfeatures.updatelinkoption,
                    "seqedgehist", self.lwidth, EdgeColorF, self.datagff.layoutfeature["edgehist"]);
            }

            if (self.layoutfeatures) {
                self.layoutfeatures.edgecolorf = EdgeColorF;
                if (self.layoutfeatures.drawedges) {
                    self.layoutfeatures.drawedges();
                }
            }
        }
        else if(self.colorstableshitttype==3){
            CCTT.id = c;
            ProjectionColorF = CCTT.interpolate();

            if (self.layoutinstance) {
                self.layoutinstance.projectioncolorf = ProjectionColorF;
                if (self.layoutinstance.updatecolors) {
                    self.layoutinstance.updatecolors();
                }
            }
        }
    };

    this.settarget = function () {
        var targetElement = gelem("target");
        if (targetElement && targetElement.options && targetElement.options.length > 0) {
            var parsed = parseInt(targetElement.value, 10);
            if (isNaN(parsed)) {
                parsed = parseInt(targetElement.selectedIndex, 10);
            }
            if (!isNaN(parsed) && parsed >= 0) {
                self.target = parsed;
            }
        }
        self.target = self.getTargetId();
        self.normalizeFeatureSelection();
        self.populateInstanceIdDropdown();
        if (self.USFOBJ && self.USFOBJ.print) {
            self.USFOBJ.print();
        }
    };

/*     this.loadselectfeatureid = function () {
        loadselectfeatureid
        for (var item of selfgff.datagff.fenames) {
            self.unselectedfeatures.push({
                                            "name": item,
                                            "id": i,
                                            "value": 0,
                                        });
            i++;
        }
    };

    gelem("idselectedfebt").onclick = function(){
        if(gelem("idselectedfebt").value==1){
            gelem("idselectidcont").style.display = "block";
            gelem("idselectedfebt").value = 0;
        }
        else{
            gelem("idselectidcont").style.display = "none";
            gelem("idselectedfebt").value = 1;
        }    
    }; */


}


/**
 * Others auxiliar methods
 */
/* $(document).ready(function () {
    $('#idtextdbname').focusout(function () {
        GFFOBJ.getdatasetname();
        GFFOBJ.fullScreen();
    });
}); */
function opendatsetparser() {
    //self.fullScreen();
    GFFOBJ.loadlayoutdbs();
}
function mwalert(title, txtbody) {
    //self.fullScreen();
    GFFOBJ.mw.alert(title, txtbody);
}
/* function showloading(title, txtbody) {
    //self.fullScreen();
    MOPRO.show(title);
} */


/***
* function: Load Object recursively
*/
function loadObject(work, obj, list, count, dataset, functpro, functend, functbusy, type) {
    if(count<list.length){
        //MOPRO.status((count*100.0)/list.length);
        let ob = new ServiceData(work+" ("+(count+1)+" of "+list.length+")");
        ob.in.argms["type"] = type;
        ob.in.argms["file"] = dataset;
        ob.in.argms["data"] = list[count];
        ob.event = function () {
            /* console.log("error loadataset", this); */
            switch (this.ou["statusopt"]) {
                // ok, free, ready
                case 0:
                    //console.log("out", out, this.in.argms["data"]);
                    //update obj
                    functpro.apply(this, [obj, this.ou]);

                    /* var timer = setTimeout(
                        function(){
                        },1000); */
                    count++;
                    loadObject(work, obj, list, count, dataset, functpro, functend, functbusy, type);
                    break;
                // working/busy
                case 1:
                    functbusy.apply(this,[this.ou]);
                    break;
                // error
                case 2:
    
                    break;
                //default:
                    
            };
        };
        ob.start();
    }
    else{
        //execute function when end
        functend.apply(this, [obj]);
    }
};
