/*
# GFF+ bipartite feature-instance graph
*/

function chart_bipartite(idview, selft, vertexcolorf) {
    var self = this;

    self.width = selft.lwidth;
    self.height = selft.lwidth;
    self.graph = selft.datagff.layoutfeature["graph"];
    self.vertexcolorf = vertexcolorf;
    self.maxFeatures = 12;
    self.maxInstances = 45;
    self.maxScanRows = 3000;
    self.link = null;
    self.node = null;

    self.nodeColorMetric = function (node) {
        return selft.getFeatureNodeMetric ? selft.getFeatureNodeMetric(node, "color") : node.weight;
    };
    self.nodeSizeMetric = function (node) {
        return selft.getFeatureNodeMetric ? selft.getFeatureNodeMetric(node, "size") : node.weight;
    };

    d3.select(idview).selectAll("svg").remove();
    self.svg = d3.select(idview).append("svg")
        .attr("width", self.width)
        .attr("height", self.height);
    self.viewport = self.svg.append("g");
    self.zoom = d3.zoom()
        .scaleExtent([0.5, 12])
        .on("zoom", function () {
            self.viewport.attr("transform", d3.event.transform);
        });
    self.svg.call(self.zoom);

    self.featureCandidates = function () {
        var picked = {};
        var features = [];

        function addFeature(nodeId) {
            var node = self.graph.nodes[nodeId];
            if (!node || node.category != 0 || picked[nodeId]) {
                return;
            }
            picked[nodeId] = 1;
            features.push({
                "id": node.name,
                "name": selft.datagff.fenames[node.label],
                "weight": self.nodeColorMetric(node),
                "sizeWeight": self.nodeSizeMetric(node)
            });
        }

        for (var i = 0; i < selft.featureselected.length; ++i) {
            addFeature(selft.featureselected[i]);
        }

        if (features.length < 2) {
            var ranked = self.graph.nodes.filter(function (d) {
                return d.category == 0;
            }).sort(function (a, b) {
                return self.nodeColorMetric(b) - self.nodeColorMetric(a);
            });
            for (var j = 0; j < ranked.length && features.length < self.maxFeatures; ++j) {
                addFeature(ranked[j].name);
            }
        }

        return features.slice(0, self.maxFeatures);
    };

    self.sampleRows = function (rows) {
        if (rows.length <= self.maxScanRows) {
            return rows.map(function (row, index) {
                return {"row": row, "index": index};
            });
        }
        var step = Math.ceil(rows.length / self.maxScanRows);
        var sampled = [];
        for (var i = 0; i < rows.length; i += step) {
            sampled.push({"row": rows[i], "index": i});
        }
        return sampled;
    };

    self.thresholds = function (sampledRows, features) {
        var result = {};
        for (var i = 0; i < features.length; ++i) {
            var values = sampledRows.map(function (item) {
                return parseFloat(item.row[features[i].name]);
            }).filter(function (value) {
                return !isNaN(value);
            }).sort(function (a, b) {
                return a - b;
            });

            if (values.length == 0) {
                result[features[i].name] = 0;
                continue;
            }
            var minv = values[0];
            var maxv = values[values.length - 1];
            result[features[i].name] = minv >= 0 && maxv <= 1 ? 0 : values[Math.floor(values.length / 2)];
        }
        return result;
    };

    self.buildGraph = function (rows, features) {
        var sampledRows = self.sampleRows(rows);
        var thresholds = self.thresholds(sampledRows, features);
        var instances = [];
        var links = [];

        for (var r = 0; r < sampledRows.length; ++r) {
            var row = sampledRows[r].row;
            var originalIndex = sampledRows[r].index;
            var active = [];
            var score = 0;
            for (var f = 0; f < features.length; ++f) {
                var value = parseFloat(row[features[f].name]);
                if (!isNaN(value) && value > thresholds[features[f].name]) {
                    active.push({
                        "feature": features[f],
                        "value": value
                    });
                    score += value;
                }
            }
            if (active.length > 0) {
                instances.push({
                    "id": originalIndex,
                    "label": selft.getInstanceLabel(originalIndex),
                    "active": active,
                    "score": score
                });
            }
        }

        instances.sort(function (a, b) {
            return b.active.length - a.active.length || b.score - a.score;
        });
        instances = instances.slice(0, self.maxInstances);

        var instanceSet = {};
        for (var i = 0; i < instances.length; ++i) {
            instanceSet[instances[i].id] = 1;
        }

        for (var n = 0; n < instances.length; ++n) {
            for (var a = 0; a < instances[n].active.length; ++a) {
                links.push({
                    "source": "f" + instances[n].active[a].feature.id,
                    "target": "i" + instances[n].id,
                    "featureId": instances[n].active[a].feature.id,
                    "instanceId": instances[n].id,
                    "value": instances[n].active[a].value
                });
            }
        }

        return {
            "features": features.map(function (feature) {
                return {
                    "key": "f" + feature.id,
                    "type": "feature",
                    "featureId": feature.id,
                    "name": feature.name,
                    "weight": feature.weight,
                    "sizeWeight": feature.sizeWeight
                };
            }),
            "instances": instances.map(function (instance) {
                return {
                    "key": "i" + instance.id,
                    "type": "instance",
                    "instanceId": instance.id,
                    "name": String(instance.label),
                    "weight": instance.active.length / Math.max(1, features.length)
                };
            }),
            "links": links
        };
    };

    self.selectbythreshold = function (T1) {
        var ids = [];
        var taindex = selft.auxfeatureselectedf[selft.target];
        for (var i = 0; i < self.graph.nodes.length; ++i) {
            var node = self.graph.nodes[i];
            if (node.category == 0 && self.nodeColorMetric(node) >= T1 && node.name != taindex) {
                ids.push(node.name);
            }
        }
        selft.selectFeatureIds(ids, "replace");
        self.draw();
        selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
    };

    self.highlightforce = function (ids, options) {
        if (!self.node || !self.link) return;
        ids = ids || [];
        options = options || {};
        var selected = {};
        for (var i = 0; i < ids.length; ++i) {
            selected[ids[i]] = 1;
        }

        self.node.selectAll("circle")
            .style("stroke", function (d) {
                return d.type == "feature" && selected[d.featureId] ? "#ffffff" : "#263044";
            })
            .style("stroke-width", function (d) {
                return d.type == "feature" && selected[d.featureId] ? 2.25 : 1;
            });

        self.link.style("stroke-opacity", function (d) {
            return ids.length == 0 || selected[d.featureId] ? 0.45 : 0.08;
        });

        gelem("topleft1").innerHTML = "FEATURES: " + self.features.length + " / INSTANCES: " + self.instances.length;
        gelem("topright1").innerHTML = "/ SELECTED: " + ids.length;

        if (ids.length > 0) {
            var names = [];
            for (var j = 0; j < ids.length; ++j) {
                var node = self.graph.nodes[ids[j]];
                if (node && node.category == 0) {
                    names.push(selft.datagff.fenames[node.label]);
                }
            }
            gelem("fesenanetxt").value = names.join("&&");
        }

        if (!options.silent) {
            selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
        }
    };

    self.draw = function () {
        if (self.simulation) {
            self.simulation.stop();
        }
        self.viewport.selectAll("*").remove();

        var rows = selft.dataload || [];
        if (rows.length == 0 && selft.datafileselected != "") {
            self.viewport.append("text")
                .attr("x", self.width / 2)
                .attr("y", self.height / 2)
                .attr("text-anchor", "middle")
                .style("fill", "#ffffff")
                .style("font-size", "12px")
                .text("Loading feature-instance graph");
            selft.loadfilecsv(function () {
                self.draw();
            });
            return;
        }

        self.features = self.featureCandidates();
        if (rows.length == 0 || self.features.length < 2) {
            self.viewport.append("text")
                .attr("x", self.width / 2)
                .attr("y", self.height / 2)
                .attr("text-anchor", "middle")
                .style("fill", "#ffffff")
                .style("font-size", "12px")
                .text("Select at least two features");
            return;
        }

        var built = self.buildGraph(rows, self.features);
        self.instances = built.instances;
        var nodes = built.features.concat(built.instances);
        var nodeByKey = {};
        for (var i = 0; i < nodes.length; ++i) {
            nodeByKey[nodes[i].key] = nodes[i];
        }
        var links = built.links.filter(function (link) {
            return nodeByKey[link.source] && nodeByKey[link.target];
        });

        self.viewport.append("text")
            .attr("x", 12)
            .attr("y", 18)
            .style("fill", "#ffffff")
            .style("font-size", "12px")
            .text("Bipartite graph: " + self.instances.length + " representative active instances from " + rows.length + " rows");

        self.link = self.viewport.append("g")
            .selectAll(".bipartite-link")
            .data(links)
            .enter()
            .append("line")
            .attr("class", "bipartite-link")
            .style("stroke", "#9ca3af")
            .style("stroke-width", 0.8)
            .style("stroke-opacity", 0.35);

        self.node = self.viewport.append("g")
            .selectAll(".bipartite-node")
            .data(nodes)
            .enter()
            .append("g")
            .attr("class", "bipartite-node")
            .style("cursor", "pointer")
            .on("mouseover", function (d) {
                selft.setToolpiltex(
                    d3.event.pageX,
                    d3.event.pageY,
                    (d.type == "feature" ? "Feature: " : "Instance: ") + d.name
                );
            })
            .on("mouseout", function () {
                selft.hideToolpiltex();
            })
            .on("click", function (d) {
                if (d.type == "feature") {
                    var mode = selft.ispresskey == 1 ? "add" : (selft.ispresskey == 2 ? "remove" : "replace");
                    selft.selectFeatureIds([d.featureId], mode);
                    self.highlightforce(selft.featureselected, {"silent": true});
                    selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
                }
            });

        self.node.append("circle")
            .attr("r", function (d) {
                return d.type == "feature" ? 7 + ((d.sizeWeight || d.weight) * 5) : 3 + (d.weight * 5);
            })
            .style("fill", function (d) {
                return d.type == "feature" ? self.vertexcolorf(d.weight) : "#7dd3fc";
            })
            .style("stroke", "#263044")
            .style("stroke-width", 1)
            .style("opacity", 0.92);

        self.node.append("text")
            .attr("x", function (d) { return d.type == "feature" ? -8 : 8; })
            .attr("dy", 3)
            .attr("text-anchor", function (d) { return d.type == "feature" ? "end" : "start"; })
            .style("fill", "#d7dbea")
            .style("font-size", "9px")
            .style("pointer-events", "none")
            .text(function (d) {
                return d.name.length > 14 ? d.name.slice(0, 13) + "." : d.name;
            });

        self.simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(function (d) { return d.key; }).distance(55).strength(0.5))
            .force("charge", d3.forceManyBody().strength(-55))
            .force("y", d3.forceY(self.height / 2).strength(0.08))
            .force("x", d3.forceX(function (d) {
                return d.type == "feature" ? self.width * 0.25 : self.width * 0.75;
            }).strength(0.45))
            .force("collide", d3.forceCollide().radius(13))
            .on("tick", function () {
                self.link
                    .attr("x1", function (d) { return d.source.x; })
                    .attr("y1", function (d) { return d.source.y; })
                    .attr("x2", function (d) { return d.target.x; })
                    .attr("y2", function (d) { return d.target.y; });

                self.node.attr("transform", function (d) {
                    d.x = Math.max(35, Math.min(self.width - 35, d.x));
                    d.y = Math.max(35, Math.min(self.height - 25, d.y));
                    return "translate(" + d.x + "," + d.y + ")";
                });
            });

        self.highlightforce(selft.featureselected, {"silent": true});
    };

    self.updatelinkoption = function () {};
    self.showedges = function () {};
    self.updateedgestransparency = function () {
        if (!self.link) return;
        self.link.style("stroke-opacity", selft.edgetransparency);
    };
    self.updatesizecircle = function () {};
    self.applyNodeStyles = function () {
        self.draw();
    };

    self.draw();
}
