/*
# GFF+ feature community graph
*/

function chart_feature_community(idview, selft, vertexcolorf, edgecolorf) {
    var self = this;

    self.width = selft.lwidth;
    self.height = selft.lwidth;
    self.graph = selft.datagff.layoutfeature["graph"];
    self.vertexcolorf = vertexcolorf;
    self.edgecolorf = edgecolorf;
    self.maxMembersPerCommunity = 30;
    self.link = null;
    self.node = null;

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

    self.pickCommunityEdges = function () {
        var featureEdges = self.graph.links.filter(function (edge) {
            return self.graph.nodes[edge.source] &&
                self.graph.nodes[edge.target] &&
                self.graph.nodes[edge.source].category == 0 &&
                self.graph.nodes[edge.target].category == 0;
        });

        if (featureEdges.length == 0) {
            return [];
        }

        var weights = featureEdges.map(function (d) { return d.weight; })
            .sort(function (a, b) { return a - b; });
        var threshold = weights[Math.floor(weights.length * 0.65)];
        return featureEdges.filter(function (edge) {
            return edge.weight <= threshold;
        });
    };

    self.buildCommunities = function () {
        var featureNodes = self.graph.nodes.filter(function (node) {
            return node.category == 0;
        });
        var adjacency = {};
        for (var i = 0; i < featureNodes.length; ++i) {
            adjacency[featureNodes[i].name] = [];
        }

        var communityEdges = self.pickCommunityEdges();
        for (var e = 0; e < communityEdges.length; ++e) {
            adjacency[communityEdges[e].source].push(communityEdges[e].target);
            adjacency[communityEdges[e].target].push(communityEdges[e].source);
        }

        var visited = {};
        var communities = [];
        for (var n = 0; n < featureNodes.length; ++n) {
            var start = featureNodes[n].name;
            if (visited[start]) {
                continue;
            }
            var queue = [start];
            var members = [];
            visited[start] = 1;
            while (queue.length > 0) {
                var current = queue.shift();
                members.push(current);
                var neighbors = adjacency[current] || [];
                for (var j = 0; j < neighbors.length; ++j) {
                    if (!visited[neighbors[j]]) {
                        visited[neighbors[j]] = 1;
                        queue.push(neighbors[j]);
                    }
                }
            }
            communities.push({
                "id": communities.length,
                "members": members,
                "size": members.length,
                "weight": d3.mean(members, function (id) {
                    return self.graph.nodes[id].weight || 0;
                }) || 0
            });
        }

        communities.sort(function (a, b) {
            return b.size - a.size || b.weight - a.weight;
        });
        for (var c = 0; c < communities.length; ++c) {
            communities[c].id = c;
        }
        return communities;
    };

    self.buildCommunityLinks = function (communities) {
        var communityByFeature = {};
        for (var c = 0; c < communities.length; ++c) {
            for (var m = 0; m < communities[c].members.length; ++m) {
                communityByFeature[communities[c].members[m]] = communities[c].id;
            }
        }

        var aggregate = {};
        var edges = self.graph.whole.concat(self.graph.links);
        for (var e = 0; e < edges.length; ++e) {
            var source = communityByFeature[edges[e].source];
            var target = communityByFeature[edges[e].target];
            if (source === undefined || target === undefined || source == target) {
                continue;
            }
            var a = Math.min(source, target);
            var b = Math.max(source, target);
            var key = a + ":" + b;
            if (!aggregate[key]) {
                aggregate[key] = {"source": a, "target": b, "count": 0, "weight": 0};
            }
            aggregate[key].count += 1;
            aggregate[key].weight += edges[e].weight;
        }

        return Object.keys(aggregate).map(function (key) {
            var item = aggregate[key];
            item.weight = item.weight / item.count;
            return item;
        }).sort(function (a, b) {
            return b.count - a.count;
        }).slice(0, 80);
    };

    self.memberNames = function (community) {
        return community.members.slice(0, self.maxMembersPerCommunity).map(function (id) {
            return selft.datagff.fenames[self.graph.nodes[id].label];
        });
    };

    self.selectCommunity = function (community, mode) {
        var ids = community.members.slice(0, self.maxMembersPerCommunity);
        selft.selectFeatureIds(ids, mode || "replace");
        self.highlightforce(selft.featureselected, {"silent": true});
        selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
    };

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
        if (!self.node || !self.link) return;
        ids = ids || [];
        options = options || {};
        var selected = {};
        for (var i = 0; i < ids.length; ++i) {
            selected[ids[i]] = 1;
        }

        self.node.selectAll("circle")
            .style("stroke", function (d) {
                var hit = d.members.some(function (id) { return selected[id]; });
                return hit ? "#ffffff" : "#293244";
            })
            .style("stroke-width", function (d) {
                var hit = d.members.some(function (id) { return selected[id]; });
                return hit ? 2.5 : 1;
            });

        gelem("topleft1").innerHTML = "COMMUNITIES: " + self.communities.length;
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
        self.communities = self.buildCommunities();
        self.communityLinks = self.buildCommunityLinks(self.communities);

        self.viewport.append("text")
            .attr("x", 12)
            .attr("y", 18)
            .style("fill", "#ffffff")
            .style("font-size", "12px")
            .text("Feature communities from strong graph relationships");

        self.link = self.viewport.append("g")
            .selectAll(".community-link")
            .data(self.communityLinks)
            .enter()
            .append("line")
            .attr("class", "community-link")
            .style("stroke", function (d) { return self.edgecolorf(d.weight); })
            .style("stroke-opacity", 0.35)
            .style("stroke-width", function (d) { return Math.min(5, 1 + Math.sqrt(d.count)); });

        self.node = self.viewport.append("g")
            .selectAll(".community-node")
            .data(self.communities)
            .enter()
            .append("g")
            .attr("class", "community-node")
            .style("cursor", "pointer")
            .on("mouseover", function (d) {
                selft.setToolpiltex(
                    d3.event.pageX,
                    d3.event.pageY,
                    "Community " + (d.id + 1) + " (" + d.size + "): " + self.memberNames(d).join(", ")
                );
            })
            .on("mouseout", function () {
                selft.hideToolpiltex();
            })
            .on("click", function (d) {
                var mode = selft.ispresskey == 1 ? "add" : (selft.ispresskey == 2 ? "remove" : "replace");
                self.selectCommunity(d, mode);
            });

        self.node.append("circle")
            .attr("r", function (d) {
                return Math.min(38, 8 + Math.sqrt(d.size) * 5);
            })
            .style("fill", function (d) { return self.vertexcolorf(d.weight); })
            .style("stroke", "#293244")
            .style("stroke-width", 1)
            .style("opacity", 0.9);

        self.node.append("text")
            .attr("text-anchor", "middle")
            .attr("dy", 4)
            .style("fill", "#ffffff")
            .style("font-size", "10px")
            .style("pointer-events", "none")
            .text(function (d) { return d.size; });

        self.simulation = d3.forceSimulation(self.communities)
            .force("link", d3.forceLink(self.communityLinks).id(function (d) { return d.id; }).distance(80))
            .force("charge", d3.forceManyBody().strength(-180))
            .force("center", d3.forceCenter(self.width / 2, self.height / 2))
            .force("collide", d3.forceCollide().radius(function (d) {
                return Math.min(42, 12 + Math.sqrt(d.size) * 5);
            }))
            .on("tick", function () {
                self.link
                    .attr("x1", function (d) { return d.source.x; })
                    .attr("y1", function (d) { return d.source.y; })
                    .attr("x2", function (d) { return d.target.x; })
                    .attr("y2", function (d) { return d.target.y; });

                self.node.attr("transform", function (d) {
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

    self.draw();
}
