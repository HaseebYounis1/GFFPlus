/*
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br
*/


/* Adapted from: https://github.com/upphiminn/d3.ForceBundle
 */
function chart_force(vertexcolorf, edgecolorf, selft, idview, foncebi, argmsi) {
    var self = this;

    self.vertexcolorf = vertexcolorf;
    self.edgecolorf = edgecolorf;
    self.width = selft.lwidth;
    self.height = selft.lwidth;
    self.graph = selft.datagff.layoutfeature["graph"];
    self.ranking = selft.datagff.layoutfeature["ranking"];
    self.treehi = selft.datagff.layoutfeature["treehi"];
    self.graph["linkupdate"] = [];
    self.graph["linkupdate"] = self.graph.links.slice();
    self.graphmx = selft.datagff.layoutfeature["maxvalue"];
    self.graphmi = selft.datagff.layoutfeature["minvalue"];
    self.initv = selft.datagff.layoutfeature["initvertex1"];
    self.initv2 = selft.datagff.layoutfeature["initvertex2"];
    self.argms = argmsi;
    //    self.isplay = true;
    self.isplay = false;
    self.selectedIndexes = [];
    self.T1 = 0.0;
    //self.ispresskey = 0;
    self.sizecircleper = 0;
    self.sizecirclemax = 8;
    self.transform = d3.zoomIdentity;

    self.isupdatebundling = true;
    self.isshowedgesshift = true;
    self.iscoloslider = true;

    gelem(self.argms["infleft"]).innerHTML = "TOTAL: " + self.ranking.length;

    var R = Math.sqrt(self.graph.nodes.length / Math.PI);
    self.fonceb = foncebi;
    self.ratio = 3;

    self.nodeColorMetric = function (d) {
        return selft.getFeatureNodeMetric ? selft.getFeatureNodeMetric(d, "color") : d.weight;
    };
    self.nodeSizeMetric = function (d) {
        return selft.getFeatureNodeMetric ? selft.getFeatureNodeMetric(d, "size") : d.weight;
    };
    self.nodeRadius = function (d) {
        return (d.category == 1) ? 1.75 :
            ((self.nodeSizeMetric(d) * self.ratio) + 3) +
            (self.sizecirclemax * self.sizecircleper);
    };
    self.nodeTooltip = function (d) {
        if (selft && selft.getFeatureNodeTooltip) {
            return selft.getFeatureNodeTooltip(d, self.ranking);
        }
        var name = (selft && selft.datagff && selft.datagff.fenames && selft.datagff.fenames[d.label])
            ? selft.datagff.fenames[d.label] : (d.name || "Feature #" + d.label);
        var tip = name + ":" + (self.ranking ? self.ranking[d.name] : "");
        if (selft && selft.contrastiveData && selft.contrastiveData.by_feature_id) {
            var info = selft.contrastiveData.by_feature_id[String(d.label)];
            if (info) {
                var formatP = function (val) {
                    if (val === undefined || val === null) return "n/a";
                    var p = Number(val);
                    return p < 0.0001 ? p.toExponential(2) : p.toFixed(4);
                };
                var dVal = Number(info.effect_size || 0);
                var dirSign = dVal >= 0 ? "+" : "";
                var tVal = info.t_statistic !== undefined ? Number(info.t_statistic).toFixed(2) : "n/a";
                var pStr = formatP(info.p_value);
                var qStr = formatP(info.fdr_q_value);
                var sigStr = info.is_significant ? " [FDR Significant]" : "";
                tip += " | \u0394=" + dirSign + dVal.toFixed(2) + " (t=" + tVal + ", p=" + pStr + ", q=" + qStr + ")" + sigStr;
                if (info.is_top_counterfactual) {
                    tip += " [Top Counterfactual: gain=" + Number(info.counterfactual_gain || 0).toFixed(2) + "]";
                }
            }
        }
        return tip;
    };

    self.radiallayout = layout_radial(self.treehi, self.width);
    self.isradiallayout = true;

    self.simulation = d3.forceSimulation()
        .velocityDecay(0.1)
        .alphaTarget(0.1)
        .force("center", d3.forceCenter(0, 0));

    self.simulation
        .force(d3.forceLink());

    var lassoPolygon;
    var lassoPath;
    var closePath;
    self.drag = d3.drag()
        .on("start", function () {
            self.stopforce();

            lassoPolygon = [d3.mouse(this)];
            if (lassoPath) {
                lassoPath.remove();
            }
            lassoPath = self.svgw
                .append('path')
                .attr('fill', '#ff4e00')
                .attr('fill-opacity', 0.1)
                .attr('stroke', '#912c00')
                .attr('stroke-dasharray', '3, 3');

            closePath = self.svgw
                .append('line')
                .attr('x2', lassoPolygon[0][0])
                .attr('y2', lassoPolygon[0][1])
                .attr('stroke', '#0bb')
                .attr('stroke-dasharray', '3, 3')
                .attr('opacity', 0);
        })
        .on("drag", function () {
            var point = d3.mouse(this);
            lassoPolygon.push(point);
            lassoPath.attr('d', polygonToPath(lassoPolygon));

            closePath
                .attr('x1', point[0])
                .attr('y1', point[1])
                .attr('opacity', 1);
        })
        .on("end", function () {
            closePath.remove();
            closePath = null;
            lassoPath.attr('d', polygonToPath(lassoPolygon) + 'Z');
            var auxfeatureselected = [];
            var auxfeatureselected_vis = Array(self.graph.nodes.length).fill(0);
            if (selft.ispresskey == 1 || selft.ispresskey == 2) {
                for (var i in selft.featureselected) {
                    var e = selft.featureselected[i];
                    auxfeatureselected_vis[e] = 1;
                }
            }
            else {
                selft.featureselected = [];
            }
            var taindex = selft.auxfeatureselectedf[selft.target];


            self.svgw.selectAll(".node").each(function (d, i) {
                var xx = (parseFloat(d3.select(this).attr("cx")) * self.transform.k) + self.transform.x;
                var yy = (parseFloat(d3.select(this).attr("cy")) * self.transform.k) + self.transform.y;

                point = [xx, yy];
                if (pointInPolygon(point, lassoPolygon)) {
                    if (d.category == 0 && d.name != taindex) {
                        auxfeatureselected.push(d.name);
                    }
                }
            });
            // control key
            if (selft.ispresskey == 1) {
                for (var i in auxfeatureselected) {
                    var e = auxfeatureselected[i];
                    var ev = auxfeatureselected_vis[e];
                    if (ev == 0) {
                        selft.featureselected.push(e);
                    }
                }
            }
            // shift key
            else if (selft.ispresskey == 2) {
                var aux2featureselected = [];
                for (var i in auxfeatureselected) {
                    var e = auxfeatureselected[i];
                    auxfeatureselected_vis[e] = 2;
                }
                for (var i in selft.featureselected) {
                    var e = selft.featureselected[i];
                    if (auxfeatureselected_vis[e] != 2) {
                        aux2featureselected.push(e);
                    }
                }
                selft.featureselected = aux2featureselected;
            }
            else {
                selft.featureselected = auxfeatureselected;
            }

            if (selft.intarget && auxfeatureselected_vis[taindex] == 0 && selft.featureselected.length > 0) {
                selft.featureselected.push(taindex);
            }
            self.highlightforce(selft.featureselected, {"silent": true});
            selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            lassoPath.remove();
            lassoPath = null;
            lassoPolygon = null;

            //console.log("graggggggggggg.. featureselected",selft.featureselected);
        });


    self.zoom = d3.zoom()
        .scaleExtent([0.5, 15])
        .on("zoom", zoomed);

    function zoomed() {
        self.transform = d3.event.transform;
        self.container.attr("transform", self.transform);
    }



    //    self.svgw.call(drag);
    ///////////////////////////////////////////
    ///////////////////////////////////////////
    ///////////////////////////////////////////



    d3.select(idview).selectAll("svg").remove();
    self.svgw = d3.select(idview).append("svg")
        .attr("width", self.width)
        .attr("height", self.height)
        .call(self.drag)
        .call(self.zoom)
        .append("g");

    self.container = self.svgw.append("g")

    // elements for data join
    self.link = self.container.append("g").selectAll(".link");
    self.link2 = self.container.append("g").selectAll(".links");
    self.links = self.container.append("g").attr("class", "links");
    self.contrastRing = self.container.append("g").attr("class", "contrast-rings").selectAll(".node-contrast-ring");
    self.node = self.container.append("g").selectAll(".node");

    self.d3line = d3.line()
        .x(function (d) { return d.x; })
        .y(function (d) { return d.y; });


    self.showedges = function () {
        self.isshowedgesshift = true;
        self.iscoloslider = true;

        self.viewlayoutgraphtree_normal();

        self.link2.style("stroke-opacity", 0.0);
    };

    //draw nodes
    this.drawnodes = function () {
        self.contrastRing = self.contrastRing.data(self.graph.nodes);
        self.contrastRing.exit().remove();
        self.contrastRing = self.contrastRing.enter().append("circle")
            .attr("class", "node-contrast-ring")
            .attr("r", function (d) {
                return (d.category == 1) ? 0 : (self.nodeRadius(d) + 3.2);
            })
            .style("fill", "none")
            .style("stroke", "none")
            .style("stroke-width", 0)
            .style("pointer-events", "none");

        self.node = self.node.data(self.graph.nodes);
        self.node.exit().remove();
        self.node = self.node.enter().append("circle")
            .attr("class", "node")
            .attr("r", function (d) {
                return self.nodeRadius(d);
            })
            .style('stroke', 'white')
            .style('stroke-width', function (d) {
                return (d.category == 1) ? 0 : 0.75;
            })
            .style("fill", function (d) {
                return (d.category == 1) ? '#ccc' : self.vertexcolorf(self.nodeColorMetric(d));
            })
            .call(d3.drag()
                .on("start", function (d, i) {
                    self.showedges();
                })
                .on("drag", function (d, i) {
                    self.isupdatebundling = true;
                    d.px += d3.event.dx;
                    d.py += d3.event.dy;
                    d.x += d3.event.dx;
                    d.y += d3.event.dy;
                    self.tick();
                })
                .on("end", function (d, i) {
                    d.fixed = true;
                    self.tick();
                })
            )
            .on("mouseover", function (d) {
                mouseoveredx(d);

                if (d.category == 1){
                    selft.setToolpiltex(
                        d3.event.pageX,
                        d3.event.pageY,
                        "extra" 
                        );
                }
                else{
                    selft.setToolpiltex(
                        d3.event.pageX,
                        d3.event.pageY,
                        self.nodeTooltip(d)
                        );
                }

            })
            .on("mouseout", function (d) {
                mouseoutedx(null);
                selft.hideToolpiltex();
            })
            .on("click", function (d, i) {
                selft.keepselectvertex = i;
                mouseoveredx(d);
                if (d.category == 0) {
                    var mode = selft.ispresskey == 1 ? "add" : (selft.ispresskey == 2 ? "remove" : "replace");
                    selft.selectFeatureIds([d.name], mode);
                    self.highlightforce(selft.featureselected, {"silent": true});
                    selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
                    d3.event.stopPropagation();
                }
            });
        //.merge(self.node);

        function mouseoveredx(d) {
            self.viewlayoutgraphtree(d);
        };

        function mouseoutedx(d) {
            self.viewlayoutgraphtree(d);
        };

        //target node
        if (self.initv != -1) {
            var selectionBArray = self.svgw.selectAll(".node")["_groups"][0];
            if (selectionBArray[self.initv]) {
                selectionBArray[self.initv].style.fill = "#666";
            }
        }
        //target node
        if (self.initv2 != -1) {
            var selectionBArray = self.svgw.selectAll(".node")["_groups"][0];
            if (selectionBArray[self.initv2]) {
                selectionBArray[self.initv2].style.stroke = "#72ab41";
            }
        }

        // initial radial layout
        //self.stopforce();
    };
    
    this.updatecolors = function () {
        var selectionBArray = self.svgw.selectAll(".node").nodes();
        self.node
        .style("fill", function (d) {
            return (d.category == 1) ? '#ccc' : self.vertexcolorf(self.nodeColorMetric(d));
        })
        .style("stroke", function (d) {
            return (d.category == 1) ? '#ccc' : "#fff";
        });

        for (var i in selft.featureselected) {
            cir = selectionBArray[selft.featureselected[i]];
            if (!cir) {
                continue;
            }
            var fillCol = d3.color(cir.style.fill);
            cir.style.stroke = fillCol ? fillCol.darker() : "#333";
            cir.style.strokeWidth = 2.25;
            cir.style.opacity = "1.0";
        }
    };

    this.updatesizecircle = function (pct) {
        self.sizecircleper = pct;
        self.node
            .attr("r", function (d) {
                return self.nodeRadius(d);
            });
        if (self.contrastRing) {
            self.contrastRing
                .attr("r", function (d) {
                    return (d.category == 1) ? 0 : (self.nodeRadius(d) + 3.2);
                });
        }
    };

    this.applyContrastiveStyles = function () {
        if (!self.contrastRing) {
            return;
        }
        var cData = (selft && selft.contrastiveData && selft.contrastiveData.by_feature_id)
            ? selft.contrastiveData.by_feature_id : null;
        if (!cData) {
            self.contrastRing
                .style("stroke", "none")
                .style("stroke-width", 0)
                .style("stroke-dasharray", null);
            return;
        }
        self.contrastRing
            .attr("r", function (d) {
                if (d.category == 1) return 0;
                var info = cData[String(d.label)];
                if (info && info.is_top_counterfactual) {
                    return self.nodeRadius(d) + 4.2;
                }
                return self.nodeRadius(d) + 2.8;
            })
            .style("stroke", function (d) {
                if (d.category == 1) return "none";
                var info = cData[String(d.label)];
                if (!info) return "none";
                if (info.is_top_counterfactual) {
                    return "#00a676";
                }
                var cNorm = parseFloat(info.contrast_norm || 0.0);
                if (Math.abs(cNorm) < 0.12) return "none";
                return cNorm >= 0 ? "#b2182b" : "#2166ac";
            })
            .style("stroke-width", function (d) {
                if (d.category == 1) return 0;
                var info = cData[String(d.label)];
                if (!info) return 0;
                if (info.is_top_counterfactual) {
                    return 2.4;
                }
                var absNorm = Math.abs(parseFloat(info.contrast_norm || 0.0));
                var baseW = absNorm >= 0.12 ? (1.2 + 2.2 * absNorm) : 0;
                return (info.is_significant && baseW > 0) ? (baseW + 0.8) : baseW;
            })
            .style("stroke-dasharray", function (d) {
                if (d.category == 1) return null;
                var info = cData[String(d.label)];
                return (info && info.is_top_counterfactual) ? "3,2" : null;
            })
            .style("opacity", 0.92);

        if (self.node) {
            self.node.attr("title", function (d) {
                return self.nodeTooltip(d);
            });
        }
    };

    this.applyNodeStyles = function () {
        self.updatecolors();
        self.updatesizecircle(self.sizecircleper);
        self.applyContrastiveStyles();
    };

    this.drawedges = function () {
        self.linksForce = d3.forceLink(self.graph.linkupdate)
            .distance(function (d) {

                return ((self.ratio * 2) + (self.nodeSizeMetric(self.graph.nodes[d.source.index]) + d.weight +
                    self.nodeSizeMetric(self.graph.nodes[d.target.index]) + d.weight)) + 2.25 + (self.sizecirclemax * self.sizecircleper) * 2.0;
            });

        self.simulation
            .nodes(self.graph.nodes)
            .force("link", self.linksForce)
            .force("charge", d3.forceManyBody().strength(self.fonceb))
            .force("x", d3.forceX())
            .force("y", d3.forceY());



        self.link = self.link.data(self.graph.linkupdate);
        self.link.exit().remove();
        self.link = self.link.enter().append("line")
            .attr("class", "link")
            .merge(self.link);

        self.showedges();
    };



    this.initlocation = function () {
        var re = self.radiallayout;
        self.node.attr("cx", function (d, i) { return re[i].x; })
            .attr("cy", function (d, i) { return re[i].y })
            .attr("x", function (d, i) { return re[i].x })
            .attr("y", function (d, i) { return re[i].y });
        if (self.contrastRing) {
            self.contrastRing.attr("cx", function (d, i) { return re[i].x; })
                .attr("cy", function (d, i) { return re[i].y; });
        }

        self.link.attr("x1", function (d) { return re[d.source.index].x; })
            .attr("y1", function (d) { return re[d.source.index].y; })
            .attr("x2", function (d) { return re[d.target.index].x; })
            .attr("y2", function (d) { return re[d.target.index].y; });

        for (var i in self.graph.nodes) {
            self.graph.nodes[i]["x"] = re[i].x;
            self.graph.nodes[i]["y"] = re[i].y;
        }
    };

    this.selectbythreshold = function (T1) {
        self.T1 = T1;
        var i, d;
        var d;
        selft.featureselected = [];
        var taindex = selft.auxfeatureselectedf[selft.target];
        for (i = 0; i < self.graph.nodes.length; ++i) {
            d = self.graph.nodes[i];
            if (d.category == 0 && self.nodeColorMetric(d) >= self.T1 && d.name != taindex) {
                selft.featureselected.push(d.name);
            }
        }
        if (selft.intarget && selft.featureselected.length > 0) {
            selft.featureselected.push(taindex);
        }
        self.highlightforce(selft.featureselected, {"silent": true});
        selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
    };

    this.highlightforce = function (ids, options) {
        ids = ids || [];
        options = options || {};
        var selectionBArray = self.svgw.selectAll(".node").nodes();
        self.svgw.selectAll(".node")
            .style("stroke", "white")
            .style("stroke-width", function (d) {
                return (d.category == 1) ? 0.0 : 0.75;
            });

        var esel = gelem(self.argms["infright"]);
        esel.innerHTML = "/ SELECTED: " + ids.length;
        if (ids.length > 0) {

            if (self.iscoloslider) {
                self.iscoloslider = false;
                
                self.viewlayoutgraphtree();
            }

            self.svgw.selectAll(".node")
                .style("opacity", function (d) {
                    return (d.category == 1) ? 1.0 : 0.5;
                })
                .style("stroke-width", function (d) {
                    return (d.category == 1) ? 0.0 : 0.75;
                });

            var filterfe = [];
            //console.log("idsidsids", ids)
            for (var i of ids) {
                filterfe.push(selft.datagff.fenames[self.graph.nodes[i].label]);
            }
            gelem('fesenanetxt').value = filterfe.join("&&");
        }
        else {
            selft.keepselectvertex = -1;
            self.iscoloslider = true;
            
            self.viewlayoutgraphtree();

            self.svgw.selectAll(".node")
                .style("opacity", 1.0);


            esel.innerHTML = "/ SELECTED: " + 0;
        }
        
        for (var i in ids) {
            cir = selectionBArray[ids[i]];
            if (cir) {
                var fillCol = d3.color(cir.style.fill);
                cir.style.stroke = fillCol ? fillCol.darker() : "#333";
                cir.style.strokeWidth = 2.25;
                cir.style.opacity = "1.0";
            }
        }
        self.applyContrastiveStyles();
        if (!options.silent) {
            selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
        }
    };


    this.updatelinkoption = function (limi, type) {
        if (type == "percen") {
            self.updatelink(0.0, type);
            self.updatelink(limi, type);
        }
        else if (type == "array") {
            var ids = {};
            self.updatelink(ids, type);
            self.updatelink(limi, type);
        }
        else if (type == "limiar") {
            self.updatelink(-1.0, type);
            self.updatelink(limi, type);
        }
    };

    this.updatelink = function (limi, type) {
        self.stopforce();
        self.graph["linkupdate"] = [];
        self.graph["linkupdate"].length = 0;
        self.graph["linkupdate"] = self.graph.links.slice();

        if (type == "percen") {
            limi = (self.graph.whole.length) * (Math.pow(limi, 3.0) / 1000000000000.0);
            shiftv = selft.exchageslider == 180 ? self.graph.whole.length - 1 : 0;
            if (limi > 0) {
                if (selft.exchageslider == 180) {
                    for (var i = 0; i < self.graph.whole.length; ++i) {
                        if (i > limi) break;
                        self.graph["linkupdate"].push(self.graph.whole[shiftv - i]);
                    }
                }
                else {
                    for (var i = 0; i < self.graph.whole.length; ++i) {
                        if (i > limi) break;
                        self.graph["linkupdate"].push(self.graph.whole[i]);
                    }
                }
            }
        }
        else if (type == "array") {
            for (var i in limi) {
                self.graph["linkupdate"].push(self.graph.whole[limi[i]]);
            }
        }
        else if (type == "limiar") {
            for (var i = 0; i < self.graph.whole.length; ++i) {
                if (self.graph.whole[i].weight > limi) break;
                self.graph["linkupdate"].push(self.graph.whole[i]);
            }
        }

        if (self.isplay) {
            self.playforce();
            self.drawedges();
        }
        else {
            self.stopforce();
            self.drawedges();
            self.tick();
            self.stopforce();
        }
        self.isupdatebundling = true;
    };

    this.setSimilarityLinks = function (links) {
        var indexByFeatureId = {};
        for (var i = 0; i < self.graph.nodes.length; ++i) {
            indexByFeatureId[String(self.graph.nodes[i].label)] = i;
        }

        self.graph["linkupdate"] = [];
        for (var link of (links || [])) {
            var source = indexByFeatureId[String(link.source)];
            var target = indexByFeatureId[String(link.target)];
            if (source === undefined || target === undefined || source == target) {
                continue;
            }
            var similarity = parseFloat(link.weight || 0.0);
            self.graph["linkupdate"].push({
                "source": source,
                "target": target,
                "weight": Math.max(0.01, 1.0 - similarity),
                "xai_similarity": similarity
            });
        }

        self.stopforce();
        self.drawedges();
        self.tick();
        self.stopforce();
        self.isupdatebundling = true;
    };

    this.restoreGraphLinks = function () {
        self.graph["linkupdate"] = self.graph.links.slice();
        self.stopforce();
        self.drawedges();
        self.tick();
        self.stopforce();
        self.isupdatebundling = true;
    };

    this.tick = function () {
        if (self.isradiallayout) {
            self.initlocation();
            // self.graph.nodes
        }
        else {
            self.node.attr("cx", function (d) { return (self.width / 2) + d.x; })
                .attr("cy", function (d) { return (self.height / 2) + d.y; });
            if (self.contrastRing) {
                self.contrastRing.attr("cx", function (d) { return (self.width / 2) + d.x; })
                    .attr("cy", function (d) { return (self.height / 2) + d.y; });
            }

            self.link.attr("x1", function (d) { return (self.width / 2) + d.source.x; })
                .attr("y1", function (d) { return (self.height / 2) + d.source.y; })
                .attr("x2", function (d) { return (self.width / 2) + d.target.x; })
                .attr("y2", function (d) { return (self.height / 2) + d.target.y; });
        }
    };
    self.stopplayforce = function () {
        self.isradiallayout = false;
        if (self.isplay) {
            self.stopforce();
        }
        else {
            self.playforce();
        }
    };
    self.stopforce = function () {
        self.simulation.stop();
        self.tick();
        self.isplay = false;
    };
    self.playforce = function () {
        self.isupdatebundling = true;

        self.showedges();
        self.simulation.restart();
        self.simulation.on("tick", self.tick);
        self.isplay = true;
    };


    self.showedgebundling = function () {
        self.stopforce();
        if (self.isupdatebundling) {
            var fbundling = d3.ForceEdgeBundling()
                .nodes(self.simulation.nodes())
                .edges(self.simulation.force('link').links().map(function (edge) {
                    return {
                        source: self.simulation.nodes().indexOf(edge.source),
                        target: self.simulation.nodes().indexOf(edge.target)
                    }
                }));

            self.link2 = self.links.selectAll('path').data(fbundling());
            self.link2.exit().remove();
            self.link2 = self.link2.merge(self.link2.enter().append('path'))
                .attr('d', self.d3line);

            if (!self.isradiallayout) {
                self.link2
                    .attr("transform", "translate(" + self.width / 2 + "," + self.height / 2 + ")");
            }

            self.isupdatebundling = false;
        }
        
        self.link.style("stroke-opacity", 0.0);

        self.viewlayoutgraphtree_edgebundling();

        self.isshowedgesshift = false;
    };


    ////////////////////////////////////////
    ////////////////////////////////////////
    ////////////////////////////////////////
    // to selection nodes
    //    var container = svg.append("g");
    //    var svgw = svgw;

    //    selected = [];
    //    coords = [];
    //    line = d3.line();


    self.translatte = function (vx, vy) {
        cent = { "k": self.transform.k, "x": vx, "y": vy };

        self.transform.x += vx * self.transform.k;
        self.transform.y += vy * self.transform.k;

        self.container.attr("transform", self.transform);
    };

    self.viewlayoutgraphtree = function(d=null){
        if (self.isshowedgesshift) {
            self.viewlayoutgraphtree_normal(d);
        }
        else {
            self.viewlayoutgraphtree_edgebundling(d);
        }
    }

    self.viewlayoutgraphtree_normal = function(d=null){
            self.link
            .style('stroke', function (link_d, i) {
                return  link_d.source === d |
                        link_d.target === d |
                        link_d.source.index == selft.keepselectvertex |
                        link_d.target.index == selft.keepselectvertex ?
                        '#009eff' : self.edgecolorf(link_d.weight);
            })
            .style("stroke-opacity", function (link_d, i) {
                return  link_d.source === d |
                        link_d.target === d |
                        link_d.source.index === selft.keepselectvertex |
                        link_d.target.index === selft.keepselectvertex ?
                        1.0 : selft.edgetransparency;
            })
            .style("stroke-width", function (link_d, i) {
                return  i < self.graph.links.length ?
                        2.5 :
                        link_d.source === d |
                        link_d.target === d |
                        link_d.source.index === selft.keepselectvertex |
                        link_d.target.index === selft.keepselectvertex ?
                        2.0 : 1.0;
            });
    };

    self.viewlayoutgraphtree_edgebundling = function(d=null){
        self.link2
        .style('stroke', function (link_d, i) {
            return  self.graph.linkupdate[i].source === d |
                    self.graph.linkupdate[i].target === d |
                    self.graph.linkupdate[i].source.index === selft.keepselectvertex |
                    self.graph.linkupdate[i].target.index === selft.keepselectvertex ?
                    '#009eff' : self.edgecolorf(self.graph.linkupdate[i].weight);
        })
        .style("stroke-opacity",function (link_d, i) {
            return  self.graph.linkupdate[i].source === d |
                    self.graph.linkupdate[i].target === d |
                    self.graph.linkupdate[i].source.index === selft.keepselectvertex |
                    self.graph.linkupdate[i].target.index === selft.keepselectvertex ?
                    1.0 : selft.edgetransparency;
        })
        .style("stroke-width", function (link_d, i) {
            return  i < self.graph.links.length ?
                    2.5 :
                    self.graph.linkupdate[i].source === d |
                    self.graph.linkupdate[i].target === d |
                    self.graph.linkupdate[i].source.index === selft.keepselectvertex |
                    self.graph.linkupdate[i].target.index === selft.keepselectvertex ?
                    2.0 : 1.0;
        });
    };

        
    self.updateedgestransparency = function () {
        self.viewlayoutgraphtree();
    };
    ////////////////////////////////////////
    ////////////////////////////////////////
    ////////////////////////////////////////


    self.drawnodes();
    self.drawedges();

    //self.playforce();
    self.stopforce();
    //self.initlocation();
}
