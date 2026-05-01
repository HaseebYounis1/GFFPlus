/*
# Author: Ivar Vargas Belizario
# Extension: UpSet-style feature intersections
*/

function chart_upset(idview, selft, vertexcolorf) {
    var self = this;

    self.width = selft.lwidth;
    self.height = selft.lwidth;
    self.graph = selft.datagff.layoutfeature["graph"];
    self.vertexcolorf = vertexcolorf;
    self.maxSets = 12;
    self.selectedIndexes = [];

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

    self.selectbythreshold = function (T1) {
        var ids = [];
        var taindex = selft.auxfeatureselectedf[selft.target];
        for (var i = 0; i < self.graph.nodes.length; ++i) {
            var node = self.graph.nodes[i];
            if (node.category == 0 && node.weight >= T1 && node.name != taindex) {
                ids.push(node.name);
            }
        }
        selft.selectFeatureIds(ids, "replace");
        self.highlightforce(selft.featureselected, {"silent": true});
        selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
    };

    self.highlightforce = function (ids, options) {
        ids = ids || [];
        options = options || {};
        var selected = {};
        for (var i = 0; i < ids.length; ++i) {
            selected[ids[i]] = 1;
        }

        self.svg.selectAll(".upset-set-label")
            .style("font-weight", function (d) {
                return selected[d.nodeId] ? "bold" : "normal";
            })
            .style("fill", function (d) {
                return selected[d.nodeId] ? "#ffffff" : "#d9dbe7";
            });

        self.svg.selectAll(".upset-set-dot")
            .style("stroke", function (d) {
                return selected[d.nodeId] ? "#ffffff" : "none";
            })
            .style("stroke-width", function (d) {
                return selected[d.nodeId] ? 2 : 0;
            });

        gelem("topleft1").innerHTML = "TOTAL: " + self.graph.nodes.filter(function (d) {
            return d.category == 0;
        }).length;
        gelem("topright1").innerHTML = "/ SELECTED: " + ids.length;

        if (ids.length > 0) {
            var names = [];
            for (var j = 0; j < ids.length; ++j) {
                var n = self.graph.nodes[ids[j]];
                if (n && n.category == 0) {
                    names.push(selft.datagff.fenames[n.label]);
                }
            }
            gelem("fesenanetxt").value = names.join("&&");
        }

        if (!options.silent) {
            selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
        }
    };

    self.updatelinkoption = function () {};
    self.showedges = function () {};
    self.updateedgestransparency = function () {};
    self.updatesizecircle = function () {};

    self.getCandidateSets = function () {
        var picked = {};
        var sets = [];

        function addNode(nodeId) {
            var node = self.graph.nodes[nodeId];
            if (!node || node.category != 0 || picked[nodeId]) {
                return;
            }
            var featureName = selft.datagff.fenames[node.label];
            if (featureName === undefined || featureName === null) {
                return;
            }
            picked[nodeId] = 1;
            sets.push({
                "nodeId": nodeId,
                "featureId": node.label,
                "name": featureName,
                "weight": node.weight
            });
        }

        for (var i = 0; i < selft.featureselected.length; ++i) {
            addNode(selft.featureselected[i]);
        }

        if (sets.length < 2) {
            var ranked = self.graph.nodes.filter(function (d) {
                return d.category == 0;
            }).sort(function (a, b) {
                return b.weight - a.weight;
            });
            for (var j = 0; j < ranked.length && sets.length < 8; ++j) {
                addNode(ranked[j].name);
            }
        }

        return sets.slice(0, self.maxSets);
    };

    self.thresholds = function (rows, sets) {
        var result = {};
        for (var i = 0; i < sets.length; ++i) {
            var values = rows.map(function (row) {
                return parseFloat(row[sets[i].name]);
            }).filter(function (v) {
                return !isNaN(v);
            }).sort(function (a, b) {
                return a - b;
            });

            if (values.length == 0) {
                result[sets[i].name] = 0;
                continue;
            }

            var minv = values[0];
            var maxv = values[values.length - 1];
            if (minv >= 0 && maxv <= 1) {
                result[sets[i].name] = 0;
            }
            else {
                result[sets[i].name] = values[Math.floor(values.length / 2)];
            }
        }
        return result;
    };

    self.buildIntersections = function (rows, sets) {
        var thresholds = self.thresholds(rows, sets);
        var counts = {};

        for (var r = 0; r < rows.length; ++r) {
            var active = [];
            for (var s = 0; s < sets.length; ++s) {
                var value = parseFloat(rows[r][sets[s].name]);
                if (!isNaN(value) && value > thresholds[sets[s].name]) {
                    active.push(s);
                }
            }
            if (active.length > 0) {
                var key = active.join(",");
                counts[key] = (counts[key] || 0) + 1;
            }
        }

        var intersections = Object.keys(counts).map(function (key) {
            return {
                "key": key,
                "active": key.split(",").map(function (d) { return parseInt(d, 10); }),
                "count": counts[key]
            };
        }).sort(function (a, b) {
            return b.count - a.count || a.active.length - b.active.length;
        });

        return intersections.slice(0, 24);
    };

    self.draw = function () {
        self.viewport.selectAll("*").remove();

        var rows = selft.dataload || [];
        if (rows.length == 0 && selft.datafileselected != "") {
            self.viewport.append("text")
                .attr("x", self.width / 2)
                .attr("y", self.height / 2)
                .attr("text-anchor", "middle")
                .style("fill", "#ffffff")
                .style("font-size", "12px")
                .text("Loading intersections");
            selft.loadfilecsv(function () {
                self.draw();
            });
            return;
        }

        var sets = self.getCandidateSets();
        if (rows.length == 0 || sets.length < 2) {
            self.viewport.append("text")
                .attr("x", self.width / 2)
                .attr("y", self.height / 2)
                .attr("text-anchor", "middle")
                .style("fill", "#ffffff")
                .style("font-size", "12px")
                .text("Select at least two features");
            return;
        }

        var intersections = self.buildIntersections(rows, sets);
        var margin = {"top": 24, "right": 16, "bottom": 22, "left": 150};
        var matrixTop = Math.max(135, self.height * 0.36);
        var barHeight = matrixTop - margin.top - 28;
        var rowStep = Math.min(24, Math.max(16, (self.height - matrixTop - margin.bottom) / sets.length));
        var colStep = Math.max(16, (self.width - margin.left - margin.right) / Math.max(1, intersections.length));
        var barWidth = Math.max(5, Math.min(18, colStep * 0.65));
        var maxCount = d3.max(intersections, function (d) { return d.count; }) || 1;
        var yBar = d3.scaleLinear().domain([0, maxCount]).range([barHeight, 0]);

        self.viewport.append("text")
            .attr("x", margin.left)
            .attr("y", 14)
            .style("fill", "#ffffff")
            .style("font-size", "12px")
            .text("Top intersections from selected or highest-ranked features");

        var bars = self.viewport.append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

        bars.selectAll("rect")
            .data(intersections)
            .enter()
            .append("rect")
            .attr("x", function (d, i) { return (i * colStep) + ((colStep - barWidth) / 2); })
            .attr("y", function (d) { return yBar(d.count); })
            .attr("width", barWidth)
            .attr("height", function (d) { return barHeight - yBar(d.count); })
            .style("fill", "#7dd3fc")
            .style("cursor", "pointer")
            .on("click", function (d) {
                var ids = d.active.map(function (setIndex) {
                    return sets[setIndex].nodeId;
                });
                selft.selectFeatureIds(ids, "replace");
                self.highlightforce(selft.featureselected, {"silent": true});
                selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            });

        bars.selectAll("text")
            .data(intersections)
            .enter()
            .append("text")
            .attr("x", function (d, i) { return (i * colStep) + (colStep / 2); })
            .attr("y", function (d) { return Math.max(10, yBar(d.count) - 4); })
            .attr("text-anchor", "middle")
            .style("fill", "#ffffff")
            .style("font-size", "9px")
            .text(function (d) { return d.count; });

        var matrix = self.viewport.append("g")
            .attr("transform", "translate(" + margin.left + "," + matrixTop + ")");

        var setRows = self.viewport.append("g")
            .attr("transform", "translate(8," + matrixTop + ")");

        setRows.selectAll("text")
            .data(sets)
            .enter()
            .append("text")
            .attr("class", "upset-set-label")
            .attr("x", 0)
            .attr("y", function (d, i) { return (i * rowStep) + 4; })
            .style("fill", "#d9dbe7")
            .style("font-size", "10px")
            .style("cursor", "pointer")
            .text(function (d) {
                return d.name.length > 22 ? d.name.slice(0, 21) + "." : d.name;
            })
            .on("click", function (d) {
                selft.selectFeatureIds([d.nodeId], selft.ispresskey == 1 ? "add" : "replace");
                self.highlightforce(selft.featureselected, {"silent": true});
                selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            });

        for (var i = 0; i < sets.length; ++i) {
            matrix.append("line")
                .attr("x1", 0)
                .attr("x2", self.width - margin.left - margin.right)
                .attr("y1", i * rowStep)
                .attr("y2", i * rowStep)
                .style("stroke", "#455064")
                .style("stroke-width", 1);
        }

        var cols = matrix.selectAll(".upset-column")
            .data(intersections)
            .enter()
            .append("g")
            .attr("class", "upset-column")
            .attr("transform", function (d, i) {
                return "translate(" + ((i * colStep) + (colStep / 2)) + ",0)";
            })
            .style("cursor", "pointer")
            .on("click", function (d) {
                var ids = d.active.map(function (setIndex) {
                    return sets[setIndex].nodeId;
                });
                selft.selectFeatureIds(ids, "replace");
                self.highlightforce(selft.featureselected, {"silent": true});
                selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
            });

        cols.each(function (d) {
            var g = d3.select(this);
            if (d.active.length > 1) {
                g.append("line")
                    .attr("x1", 0)
                    .attr("x2", 0)
                    .attr("y1", d3.min(d.active) * rowStep)
                    .attr("y2", d3.max(d.active) * rowStep)
                    .style("stroke", "#9ca3af")
                    .style("stroke-width", 2);
            }
        });

        cols.selectAll("circle")
            .data(function (d) {
                var active = {};
                for (var i = 0; i < d.active.length; ++i) {
                    active[d.active[i]] = 1;
                }
                return sets.map(function (setInfo, index) {
                    return {
                        "set": setInfo,
                        "setIndex": index,
                        "active": active[index] == 1
                    };
                });
            })
            .enter()
            .append("circle")
            .attr("class", "upset-set-dot")
            .attr("cy", function (d) { return d.setIndex * rowStep; })
            .attr("r", function (d) { return d.active ? 4.5 : 3; })
            .style("fill", function (d) {
                return d.active ? self.vertexcolorf(d.set.weight) : "#293244";
            })
            .style("opacity", function (d) { return d.active ? 1.0 : 0.45; });

        self.highlightforce(selft.featureselected, {"silent": true});
    };

    self.draw();
}
