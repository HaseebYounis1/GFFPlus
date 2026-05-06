/*
# GFF+ feature similarity heatmap
*/

function chart_feature_heatmap(idview, selft, vertexcolorf, edgecolorf) {
    var self = this;

    self.width = selft.lwidth;
    self.height = selft.lwidth;
    self.graph = selft.datagff.layoutfeature["graph"];
    self.treehi = selft.datagff.layoutfeature["treehi"] || [];
    self.vertexcolorf = vertexcolorf;
    self.edgecolorf = edgecolorf;
    self.maxFeatures = 80;

    self.nodeColorMetric = function (node) {
        return selft.getFeatureNodeMetric ? selft.getFeatureNodeMetric(node, "color") : node.weight;
    };

    d3.select(idview).selectAll("svg").remove();
    self.svg = d3.select(idview).append("svg")
        .attr("width", self.width)
        .attr("height", self.height);
    self.viewport = self.svg.append("g");
    self.zoom = d3.zoom()
        .scaleExtent([0.5, 14])
        .on("zoom", function () {
            self.viewport.attr("transform", d3.event.transform);
        });
    self.svg.call(self.zoom);

    self.getFeatureOrder = function () {
        var added = {};
        var ordered = [];

        function addNode(nodeId) {
            var node = self.graph.nodes[nodeId];
            if (!node || node.category != 0 || added[nodeId]) {
                return;
            }
            added[nodeId] = 1;
            ordered.push(node);
        }

        if (selft.featureselected.length >= 2) {
            for (var i = 0; i < selft.featureselected.length; ++i) {
                addNode(selft.featureselected[i]);
            }
        }

        for (var t = 0; t < self.treehi.length && ordered.length < self.maxFeatures; ++t) {
            addNode(self.treehi[t].id);
        }

        if (ordered.length < 2) {
            var ranked = self.graph.nodes.filter(function (d) {
                return d.category == 0;
            }).sort(function (a, b) {
                return self.nodeColorMetric(b) - self.nodeColorMetric(a);
            });
            for (var r = 0; r < ranked.length && ordered.length < self.maxFeatures; ++r) {
                addNode(ranked[r].name);
            }
        }

        return ordered.slice(0, self.maxFeatures);
    };

    self.edgeLookup = function () {
        var lookup = {};
        function add(link) {
            lookup[link.source + ":" + link.target] = link.weight;
            lookup[link.target + ":" + link.source] = link.weight;
        }
        for (var i = 0; i < self.graph.links.length; ++i) {
            add(self.graph.links[i]);
        }
        for (var j = 0; j < self.graph.whole.length; ++j) {
            add(self.graph.whole[j]);
        }
        return lookup;
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
        ids = ids || [];
        options = options || {};
        var selected = {};
        for (var i = 0; i < ids.length; ++i) {
            selected[ids[i]] = 1;
        }

        self.svg.selectAll(".heatmap-label")
            .style("fill", function (d) {
                return selected[d.name] ? "#ffffff" : "#d7dbea";
            })
            .style("font-weight", function (d) {
                return selected[d.name] ? "bold" : "normal";
            });

        self.svg.selectAll(".heatmap-cell")
            .style("stroke", function (d) {
                return selected[d.source] || selected[d.target] ? "#ffffff" : "#202638";
            })
            .style("stroke-width", function (d) {
                return selected[d.source] || selected[d.target] ? 0.9 : 0.35;
            });

        gelem("topleft1").innerHTML = "TOTAL: " + self.graph.nodes.filter(function (d) {
            return d.category == 0;
        }).length;
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
        self.viewport.selectAll("*").remove();
        var nodes = self.getFeatureOrder();
        if (nodes.length < 2) {
            self.viewport.append("text")
                .attr("x", self.width / 2)
                .attr("y", self.height / 2)
                .attr("text-anchor", "middle")
                .style("fill", "#ffffff")
                .style("font-size", "12px")
                .text("Select or compute at least two features");
            return;
        }

        var margin = {"top": 108, "right": 12, "bottom": 12, "left": 108};
        var gridSize = Math.min(
            self.width - margin.left - margin.right,
            self.height - margin.top - margin.bottom
        );
        var cell = Math.max(3, gridSize / nodes.length);
        gridSize = cell * nodes.length;
        var lookup = self.edgeLookup();
        var rows = [];

        for (var i = 0; i < nodes.length; ++i) {
            for (var j = 0; j < nodes.length; ++j) {
                var source = nodes[i].name;
                var target = nodes[j].name;
                var value = source == target ? 0 : lookup[source + ":" + target];
                rows.push({
                    "source": source,
                    "target": target,
                    "row": i,
                    "col": j,
                    "value": value === undefined ? null : value
                });
            }
        }

        self.viewport.append("text")
            .attr("x", margin.left)
            .attr("y", 16)
            .style("fill", "#ffffff")
            .style("font-size", "12px")
            .text("Feature similarity matrix ordered by the GFF tree");

        var heat = self.viewport.append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

        heat.selectAll("rect")
            .data(rows)
            .enter()
            .append("rect")
            .attr("class", "heatmap-cell")
            .attr("x", function (d) { return d.col * cell; })
            .attr("y", function (d) { return d.row * cell; })
            .attr("width", cell)
            .attr("height", cell)
            .style("fill", function (d) {
                if (d.source == d.target) {
                    return "#ffffff";
                }
                if (d.value === null) {
                    return "#151a28";
                }
                return self.edgecolorf(d.value);
            })
            .style("opacity", function (d) {
                return d.value === null && d.source != d.target ? 0.25 : 0.95;
            })
            .style("stroke", "#202638")
            .style("stroke-width", 0.35)
            .style("cursor", "pointer")
            .on("mouseover", function (d) {
                var sourceName = selft.datagff.fenames[self.graph.nodes[d.source].label];
                var targetName = selft.datagff.fenames[self.graph.nodes[d.target].label];
                var value = d.value === null ? "not stored" : d.value.toFixed(4);
                selft.setToolpiltex(
                    d3.event.pageX,
                    d3.event.pageY,
                    sourceName + " / " + targetName + ": " + value
                );
            })
            .on("mouseout", function () {
                selft.hideToolpiltex();
            })
            .on("click", function (d) {
                var mode = selft.ispresskey == 1 ? "add" : (selft.ispresskey == 2 ? "remove" : "replace");
                selft.selectFeatureIds([d.source, d.target], mode);
                self.highlightforce(selft.featureselected, {"silent": true});
                selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            });

        var labels = self.viewport.append("g");

        labels.selectAll(".heatmap-row-label")
            .data(nodes)
            .enter()
            .append("text")
            .attr("class", "heatmap-label")
            .attr("x", margin.left - 6)
            .attr("y", function (d, i) { return margin.top + (i * cell) + (cell / 2) + 3; })
            .attr("text-anchor", "end")
            .style("fill", "#d7dbea")
            .style("font-size", cell < 8 ? "7px" : "9px")
            .style("cursor", "pointer")
            .text(function (d) {
                var name = selft.datagff.fenames[d.label];
                return name.length > 16 ? name.slice(0, 15) + "." : name;
            })
            .on("click", function (d) {
                selft.selectFeatureIds([d.name], selft.ispresskey == 1 ? "add" : "replace");
                self.highlightforce(selft.featureselected, {"silent": true});
                selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            });

        labels.selectAll(".heatmap-col-label")
            .data(nodes)
            .enter()
            .append("text")
            .attr("class", "heatmap-label")
            .attr("transform", function (d, i) {
                return "translate(" + (margin.left + (i * cell) + (cell / 2) + 3) + "," + (margin.top - 6) + ")rotate(-65)";
            })
            .attr("text-anchor", "start")
            .style("fill", "#d7dbea")
            .style("font-size", cell < 8 ? "7px" : "9px")
            .style("cursor", "pointer")
            .text(function (d) {
                var name = selft.datagff.fenames[d.label];
                return name.length > 16 ? name.slice(0, 15) + "." : name;
            })
            .on("click", function (d) {
                selft.selectFeatureIds([d.name], selft.ispresskey == 1 ? "add" : "replace");
                self.highlightforce(selft.featureselected, {"silent": true});
                selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            });

        self.highlightforce(selft.featureselected, {"silent": true});
    };

    self.updatelinkoption = function () {};
    self.showedges = function () {};
    self.updateedgestransparency = function () {};
    self.updatesizecircle = function () {};
    self.applyNodeStyles = function () {
        self.draw();
    };

    self.draw();
}
