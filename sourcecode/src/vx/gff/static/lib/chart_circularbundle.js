/*
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br
*/

/* Adapted from: https://github.com/upphiminn/d3.ForceBundle
 */
function chart_circularbundle(idview,datai,diameteri){
    var self = this;
    self.data = datai;

    self.diameter = diameteri,
        self.radius = self.diameter / 2;
//    var perimeter = (2*Math.PI*radius);
//    var r = Math.floor((perimeter/datai.nodes.children.length)/5);
    self.r = 3;
    
    self.color = d3.scaleOrdinal(d3.schemeCategory10);
//    var instances = datai.nodes;
//    var arestas = datai.edges;

    d3.select(idview).selectAll("svg").remove();
    self.svg = d3.select(idview)
        .append("svg")
        .attr("width", self.diameter)
        .attr("height", self.diameter)
        .append("g")
        .attr("transform", "translate(" + self.radius + "," + self.radius + ")");
    self.link = self.svg.append("g").selectAll(".link");
    self.node = self.svg.append("g").selectAll(".node");


    self.line = d3.radialLine()
        .curve(d3.curveBundle.beta(0.85))
        .radius(function (d) {
            return d.y;
        })
        .angle(function (d) {
            return d.x / 180 * Math.PI;
        });
        
//    self.line = d3.line()
//      .x(xAccessor)
//      .y(yAccessor)
//      .curve(d3.curveBundle.beta(0.7));


    self.cluster = d3.cluster()
//        .size([360, (diameter/2) - 100]);
        .size([360, (self.diameter/2) - (2*self.r+5 )]);
//        .size([360, (diameter/2) - (2*r+5 )]);


    
    self.nodes = self.cluster(d3.hierarchy({name: "",children:self.data.graph.nodes})).leaves();
    console.log("XXXXXXX",self.nodes);
    self.links = mapx(self.nodes, self.data.graph.links);

    self.drawedges = function(){
        self.link = self.link
            .data(self.links)
            .enter()
            .append("path")
            .attr("class", "link")
            .attr("d", self.line);
    };
    self.drawedges();

    self.drawnodes = function(){
        self.node = self.node
            .data(self.nodes.filter(function (d) {
                return !d.children;
            }));
            
        self.node.exit().remove();
                
        self.node = self.node
            .enter()
            .append("g")
            .attr("class", "node")
            .attr("transform", function (d) {
                return "rotate(" + (d.x - 90) + ")translate(" + (d.y+self.r+2) + ")"
                + "rotate(" + (90 - d.x) + ")";
            })
            .on("mouseover", mouseoveredx)
            .on("mouseout", mouseoutedx);

        self.node.append("circle")
            .attr("r", self.r)
            .style("fill", function (d, i) {
//                return self.color(i);
                return d.data.color;
            });

        self.node.append("title")
            .text(function(d) { return d.data.label; });

    //    node.append('text')
    //        .attr('dy', '0.32em')
    //        .attr('x', function (d) { return d.x < 180 ? (r+2) : -1*(r+2); })
    //        .style('text-anchor', function (d) { return d.x < 180 ? 'start' : 'end'; })
    //        .attr('transform', function (d) { return 'rotate(' + (d.x < 180 ? d.x - 90 : d.x + 90) + ')'; })
    //        .text(function (d) { return d.data.name+"ABCXXXX1245678"; });
    };
    self.drawnodes();        


    function mouseoveredx(d){
        self.link
          .style('stroke-opacity', function (link_d) {
            return link_d[0] === d | link_d[link_d.length - 1] === d ? 1 : null;
          })
          .style('stroke', function (link_d) {
            return link_d[0] === d | link_d[link_d.length - 1] === d ? '#d62333' : null;
          });
    };
    function mouseoutedx(d){
        self.link
            .style('stroke-opacity', null)
            .style('stroke', null);    
    };
    

    function mapx(nodes, links) {
        var hash = [];
        for (var i = 0; i < nodes.length; i++) {
            hash[nodes[i].data.name] = nodes[i];
        }
        var resultLinks = [];
        for (var i = 0; i < links.length; i++) {
            //d3 v4后用node.path(target)来计算两个点的距离
            //返回一个从node->parent->target的数组路径
            resultLinks.push(hash[links[i].source].path(hash[links[i].target]));
        }
        return resultLinks;
    };


    function xAccessor (d) {
        var angle = (d.x - 90) / 180 * Math.PI, radius = d.y;
        return radius * Math.cos(angle);
    }

    function yAccessor (d) {
        var angle = (d.x - 90) / 180 * Math.PI, radius = d.y;
        return radius * Math.sin(angle);
    }
}

function chart_circularbundle_gff(idview, selft, vertexcolorf, edgecolorf) {
    var self = this;

    self.width = selft.lwidth;
    self.height = selft.lwidth;
    self.graph = selft.datagff.layoutfeature["graph"];
    self.vertexcolorf = vertexcolorf;
    self.edgecolorf = edgecolorf;
    self.radius = self.width / 2;
    self.r = 4;

    d3.select(idview).selectAll("svg").remove();
    self.svgRoot = d3.select(idview).append("svg")
        .attr("width", self.width)
        .attr("height", self.height);
    self.svg = self.svgRoot.append("g")
        .attr("transform", "translate(" + self.radius + "," + self.radius + ")");
    self.zoom = d3.zoom()
        .scaleExtent([0.5, 12])
        .on("zoom", function () {
            self.svg.attr(
                "transform",
                "translate(" + self.radius + "," + self.radius + ") " + d3.event.transform
            );
        });
    self.svgRoot.call(self.zoom);

    self.cluster = d3.cluster()
        .size([360, (self.width / 2) - 24]);

    self.line = d3.radialLine()
        .curve(d3.curveBundle.beta(0.82))
        .radius(function (d) { return d.y; })
        .angle(function (d) { return d.x / 180 * Math.PI; });

    self.root = d3.hierarchy({
        "name": "root",
        "children": self.graph.nodes.map(function (node) {
            return {
                "name": node.name,
                "node": node
            };
        })
    });

    self.nodes = self.cluster(self.root).leaves();
    self.nodeById = {};
    for (var i = 0; i < self.nodes.length; ++i) {
        self.nodeById[self.nodes[i].data.name] = self.nodes[i];
    }

    self.linksData = self.graph.links.filter(function (link) {
        return self.nodeById[link.source] && self.nodeById[link.target];
    });

    self.links = self.svg.append("g")
        .selectAll(".bundle-link")
        .data(self.linksData)
        .enter()
        .append("path")
        .attr("class", "bundle-link")
        .attr("d", function (d) {
            return self.line(self.nodeById[d.source].path(self.nodeById[d.target]));
        })
        .style("fill", "none")
        .style("stroke", function (d) { return self.edgecolorf(d.weight); })
        .style("stroke-opacity", 0.35)
        .style("stroke-width", 1.1);

    self.node = self.svg.append("g")
        .selectAll(".bundle-node")
        .data(self.nodes)
        .enter()
        .append("g")
        .attr("class", "bundle-node")
        .attr("transform", function (d) {
            return "rotate(" + (d.x - 90) + ")translate(" + (d.y + self.r + 2) + ")rotate(" + (90 - d.x) + ")";
        })
        .style("cursor", "pointer")
        .on("mouseover", function (d) {
            self.showRelated(d.data.name);
            var node = d.data.node;
            if (node.category == 0) {
                selft.setToolpiltex(
                    d3.event.pageX,
                    d3.event.pageY,
                    selft.datagff.fenames[node.label] + ":" + selft.datagff.layoutfeature.ranking[node.name]
                );
            }
        })
        .on("mouseout", function () {
            self.showRelated(null);
            selft.hideToolpiltex();
        })
        .on("click", function (d) {
            var node = d.data.node;
            if (node.category == 0) {
                var mode = selft.ispresskey == 1 ? "add" : (selft.ispresskey == 2 ? "remove" : "replace");
                selft.selectFeatureIds([node.name], mode);
                self.highlightforce(selft.featureselected, {"silent": true});
                selft.onFeatureSelectionChanged({"skipFeatureHighlight": true});
                d3.event.stopPropagation();
            }
        });

    self.node.append("circle")
        .attr("r", function (d) {
            return d.data.node.category == 1 ? 2 : self.r + (d.data.node.weight * 2);
        })
        .style("fill", function (d) {
            return d.data.node.category == 1 ? "#c7c7c7" : self.vertexcolorf(d.data.node.weight);
        })
        .style("stroke", "#ffffff")
        .style("stroke-width", 0.75);

    self.node.append("title")
        .text(function (d) {
            var node = d.data.node;
            return node.category == 1 ? "extra" : selft.datagff.fenames[node.label];
        });

    self.showRelated = function (nodeId) {
        self.links
            .style("stroke-opacity", function (d) {
                return nodeId === null || d.source == nodeId || d.target == nodeId ? 0.85 : 0.08;
            })
            .style("stroke", function (d) {
                return d.source == nodeId || d.target == nodeId ? "#7dd3fc" : self.edgecolorf(d.weight);
            });
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
        ids = ids || [];
        options = options || {};
        var selected = {};
        for (var i = 0; i < ids.length; ++i) {
            selected[ids[i]] = 1;
        }

        self.node.selectAll("circle")
            .style("opacity", function (d) {
                return ids.length > 0 && d.data.node.category == 0 && !selected[d.data.node.name] ? 0.35 : 1.0;
            })
            .style("stroke-width", function (d) {
                return selected[d.data.node.name] ? 2.25 : 0.75;
            })
            .style("stroke", function (d) {
                return selected[d.data.node.name] ? d3.color(this.style.fill).darker() : "#ffffff";
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

    self.updatelinkoption = function () {};
    self.showedges = function () {};
    self.updateedgestransparency = function () {
        self.links.style("stroke-opacity", selft.edgetransparency);
    };
    self.updatesizecircle = function () {};

    self.highlightforce(selft.featureselected, {"silent": true});
}
