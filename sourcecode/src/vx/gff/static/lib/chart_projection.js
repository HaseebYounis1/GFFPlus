/*
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br
*/


function hidewindowinfo() {
    //    gelem('idinfosoundfile').style.display = "none";
    //    mySoundSC.pause();
}



// from https://github.com/substack/point-in-polygon
function pointInPolygon(point, vs) {
    var xi, xj, i, intersect,
        x = point[0],
        y = point[1],
        inside = false;
    for (var i = 0, j = vs.length - 1; i < vs.length; j = i++) {
        xi = vs[i][0],
            yi = vs[i][1],
            xj = vs[j][0],
            yj = vs[j][1],
            intersect = ((yi > y) != (yj > y))
            && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

function polygonToPath(polygon) {
    return ("M" + (polygon.map(function (d) { return d.join(','); }).join('L')));
}



function plotProjection(projectioncolorf, idview, selfgff, argms) {
    var self = this;

    this.projectioncolorf = projectioncolorf;
    //console.log("dat",dat);
    //console.log("argms",argms);

    var layoutinstance = selfgff.datagff.layoutinstance || {};
    var data = Array.isArray(layoutinstance.points) ? layoutinstance.points : [];
    var targetNames = layoutinstance.tartegsnames || {};
    var targetsize = Math.max(1, Object.keys(targetNames).length);
    function targetColor(value) {
        if (layoutinstance.targettype === "regression") {
            var range = layoutinstance.targetrange || [0, 1];
            return self.projectioncolorf(range[1] > range[0] ?
                (value - range[0]) / (range[1] - range[0]) : 0.5);
        }
        return self.projectioncolorf(value / targetsize);
    }

    d3.select(idview).selectAll("svg").remove();
    gelem(argms["infleft"]).innerHTML = "TOTAL: " + data.length;
    if (data.length === 0) {
        gelem(argms["infright"]).innerHTML = " / SELECTED: 0";
        return;
    }
    
    //var colors = dat.tartegscolors;
    var issel = 1;

    var margin = { top: 0, right: 0, bottom: 0, left: 0 },
        width = selfgff.lwidth,
        height = selfgff.lwidth;

    // setup x
    var xValue = function (d) { return d.x; }, // data -> value
        xScale = d3.scaleLinear().range([0, width]), // value -> display
        xMap = function (d) { return xScale(xValue(d)); }, // data -> display
        //        xAxis = d3.svg.axis().scale(xScale).orient("bottom");
        xAxis = d3.axisBottom(xScale);

    // setup y
    var yValue = function (d) { return d.y; }, // data -> value
        yScale = d3.scaleLinear().range([height, 0]), // value -> display
        yMap = function (d) { return yScale(yValue(d)); }, // data -> display
        yAxis = d3.axisLeft(yScale);


    // don't want dots overlapping axis, so add in buffer to data domain
    xScale.domain([d3.min(data, xValue) - 5, d3.max(data, xValue) + 5]);
    yScale.domain([d3.min(data, yValue) - 5, d3.max(data, yValue) + 5]);


    //console.log("colors", colors);
    //var cValue = function (t) { return colors[t]; };

    /////////////////////////////////////////////////////////    
    /////////////////////////////////////////////////////////    
    /////////////////////////////////////////////////////////    
    /////////////////////////////////////////////////////////    
    this.selected = [];
    this.selectedB = [];
    this.showFidelityHalo = !!selfgff.showFidelityHalo;
    this.transform = d3.zoomIdentity;
    //this.coords = [],
    //this.line = d3.line();

    //this.svg;
    //var container;
    //var savedTranslation = [0, 0];
    //var savedScale = 1;

    var lassoPolygon;
    var lassoPath;
    var closePath;
    var isGroupBDrag = false;

    var drag = d3.drag()
        .on("start", function () {
            var srcEvt = d3.event && d3.event.sourceEvent ? d3.event.sourceEvent : null;
            isGroupBDrag = !!(srcEvt && srcEvt.shiftKey) || (selfgff.ispresskey == 2);
            var strokeColor = isGroupBDrag ? '#ff7043' : '#00acc1';
            lassoPolygon = [d3.mouse(this)];
            if (lassoPath) {
                lassoPath.remove();
            }
            lassoPath = self.svg
                .append('path')
                .attr('fill', strokeColor)
                .attr('fill-opacity', 0.12)
                .attr('stroke', strokeColor)
                .attr('stroke-width', 1.5)
                .attr('stroke-dasharray', '3, 3');
            closePath = self.svg
                .append('line')
                .attr('x2', lassoPolygon[0][0])
                .attr('y2', lassoPolygon[0][1])
                .attr('stroke', strokeColor)
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
            var brushedIds = [];
            self.container.selectAll(".dot").each(function (d, i) {
                var xx = (parseFloat(d3.select(this).attr("cx")) * self.transform.k) + self.transform.x;
                var yy = (parseFloat(d3.select(this).attr("cy")) * self.transform.k) + self.transform.y;

                point = [xx, yy];
                if (pointInPolygon(point, lassoPolygon)) {
                    brushedIds.push(d.id);
                }
            });
            if (isGroupBDrag && self.selected.length > 0) {
                var setA = new Set(self.selected);
                self.selectedB = brushedIds.filter(function (id) { return !setA.has(id); });
            } else {
                self.selected = brushedIds;
                self.selectedB = [];
            }
            self.highlight(this, self.selected, self.selectedB);
            var rightLabel = " / SELECTED A: " + self.selected.length;
            if (self.selectedB.length > 0) {
                rightLabel += " | B: " + self.selectedB.length;
            }
            gelem(argms["infright"]).innerHTML = rightLabel;
            lassoPath.remove();
            lassoPath = null;
            lassoPolygon = null;
            if (selfgff.onInstanceSelectionChanged) {
                selfgff.onInstanceSelectionChanged(self.selected, self.selectedB);
            }
        });

    var zoom = d3.zoom()
        .scaleExtent([0.5, 50])
        .on("zoom", function () {
            self.transform = d3.event.transform;
            self.container.attr("transform", self.transform);
        });

    this.svg = d3.select(idview)
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .call(drag)
        .call(zoom)
        .append("g");
    //.attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    // Define arrowhead marker for Ghost Trail displacement vectors
    var defs = this.svg.append("defs");
    defs.append("marker")
        .attr("id", "ghost-trail-arrow")
        .attr("viewBox", "0 -4 8 8")
        .attr("refX", 6)
        .attr("refY", 0)
        .attr("markerWidth", 5)
        .attr("markerHeight", 5)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-3.5L7,0L0,3.5")
        .attr("fill", "#6a3d9a");

    this.container = this.svg.append("g");
    this.haloLayer = this.container.append("g").attr("class", "fidelity-halo-layer");
    this.trailLayer = this.container.append("g").attr("class", "ghost-trail-layer");
    this.dotLayer = this.container.append("g").attr("class", "dot-layer");


    /////////////////////////////////////////////////////////    
    /////////////////////////////////////////////////////////    
    /////////////////////////////////////////////////////////    
    /////////////////////////////////////////////////////////    

    var opxy = 0.5;
    var sizexy = selfgff.instvertexratio;
    var sizebr = 1.75;

    self.halos = self.haloLayer.selectAll(".fidelity-halo")
        .data(data)
        .enter()
        .append("circle")
        .attr("class", "fidelity-halo")
        .attr("cx", xMap)
        .attr("cy", yMap)
        .attr("r", function (d) {
            var fid = d.fidelity !== undefined ? parseFloat(d.fidelity) : 1.0;
            var distortion = Math.max(0.0, 1.0 - fid);
            return parseFloat(sizexy) + 2.0 + distortion * 5.0;
        })
        .style("fill", "none")
        .style("stroke", "#d95f02")
        .style("stroke-width", function (d) {
            var fid = d.fidelity !== undefined ? parseFloat(d.fidelity) : 1.0;
            return fid < 0.65 ? 1.4 : 0.0;
        })
        .style("stroke-dasharray", "2,1.5")
        .style("opacity", function (d) {
            if (!self.showFidelityHalo) return 0.0;
            var fid = d.fidelity !== undefined ? parseFloat(d.fidelity) : 1.0;
            return fid < 0.65 ? Math.min(0.85, (0.75 - fid) * 1.3) : 0.0;
        })
        .style("pointer-events", "none");

    self.nodesc = self.dotLayer.selectAll(".dot");

    self.nodesc = self.nodesc.data(data);
    self.nodesc.exit().remove();
    self.nodesc = self.nodesc.enter().append("circle")
        .attr("class", "dot")
        .attr("r", sizexy)
        .attr("cx", xMap)
        .attr("cy", yMap)
        .style("opacity", selfgff.instvertexoacity)
        .style('stroke', 'white')
        .style('stroke-width', sizebr)
        .style("fill", function (d) {
            return targetColor(d.t);
            })
        .on("mouseover", function (d) {
            var fidText = d.fidelity !== undefined ? (" | Fidelity: " + Math.round(parseFloat(d.fidelity) * 100) + "%") : "";
            var tLabel = targetNames[d.t] !== undefined ? (" | Class: " + targetNames[d.t]) : "";
            selfgff.setToolpiltex(
                d3.event.pageX,
                d3.event.pageY,
                "ID: " + selfgff.getInstanceLabel(d.id) + tLabel + fidText
                );

        })
        .on("mouseout", function (d) {
            selfgff.hideToolpiltex();
        })
        .merge(self.nodesc);

    this.highlight = function (view, ids, idsB) {
        var setA = new Set((ids || []).map(function (x) { return parseInt(x, 10); }));
        var setB = new Set((idsB || []).map(function (x) { return parseInt(x, 10); }));
        var hasSelection = setA.size > 0 || setB.size > 0;

        self.nodesc
            .attr("r", function (d) {
                var baseR = parseFloat(selfgff.instvertexratio);
                return (setA.has(d.id) || setB.has(d.id)) ? (baseR + 1.25) : baseR;
            })
            .style("opacity", function (d) {
                if (!hasSelection) return selfgff.instvertexoacity;
                return (setA.has(d.id) || setB.has(d.id)) ? 1.0 : Math.max(0.22, selfgff.instvertexoacity * 0.45);
            })
            .style("stroke", function (d) {
                if (setA.has(d.id)) return "#00838f";
                if (setB.has(d.id)) return "#e64a19";
                return "white";
            })
            .style("stroke-width", function (d) {
                return (setA.has(d.id) || setB.has(d.id)) ? 2.4 : sizebr;
            });
    };

    this.clearSelection = function () {
        self.selected = [];
        self.selectedB = [];
        self.highlight(idview, [], []);
        gelem(argms["infright"]).innerHTML = " / SELECTED: 0";
    };

    this.toggleFidelityHalo = function (forceState) {
        self.showFidelityHalo = forceState !== undefined ? !!forceState : !self.showFidelityHalo;
        self.halos.style("opacity", function (d) {
            if (!self.showFidelityHalo) return 0.0;
            var fid = d.fidelity !== undefined ? parseFloat(d.fidelity) : 1.0;
            return fid < 0.65 ? Math.min(0.85, (0.75 - fid) * 1.3) : 0.0;
        });
        return self.showFidelityHalo;
    };

    this.renderGhostTrails = function (trails) {
        self.trailLayer.selectAll("*").remove();
        if (!Array.isArray(trails) || trails.length === 0) {
            return;
        }
        var pointById = {};
        for (var i = 0; i < data.length; i++) {
            pointById[data[i].id] = data[i];
        }
        var xDom = xScale.domain();
        var yDom = yScale.domain();
        var xSpan = Math.max(1e-6, (xDom[1] - 5) - (xDom[0] + 5));
        var ySpan = Math.max(1e-6, (yDom[1] - 5) - (yDom[0] + 5));

        var activeSet = new Set(self.selected.concat(self.selectedB));
        var filtered = trails.filter(function (t) {
            return pointById[t.id] !== undefined && t.displacement > 0.015;
        });
        // Sort by displacement descending and cap to top 250 vectors for visual legibility
        filtered.sort(function (a, b) {
            var aBrushed = activeSet.has(a.id) ? 1 : 0;
            var bBrushed = activeSet.has(b.id) ? 1 : 0;
            if (aBrushed !== bBrushed) return bBrushed - aBrushed;
            return b.displacement - a.displacement;
        });
        filtered = filtered.slice(0, 220);

        self.trailLayer.selectAll(".ghost-trail-line")
            .data(filtered)
            .enter()
            .append("line")
            .attr("class", "ghost-trail-line")
            .attr("x1", function (t) { return xMap(pointById[t.id]); })
            .attr("y1", function (t) { return yMap(pointById[t.id]); })
            .attr("x2", function (t) {
                var p = pointById[t.id];
                var targetX = p.x + t.dx * xSpan * 0.65;
                return xScale(targetX);
            })
            .attr("y2", function (t) {
                var p = pointById[t.id];
                var targetY = p.y + t.dy * ySpan * 0.65;
                return yScale(targetY);
            })
            .style("stroke", function (t) {
                return activeSet.has(t.id) ? "#00838f" : "#6a3d9a";
            })
            .style("stroke-width", function (t) {
                return activeSet.has(t.id) ? 1.8 : 1.15;
            })
            .style("stroke-opacity", function (t) {
                return activeSet.has(t.id) ? 0.85 : 0.48;
            })
            .attr("marker-end", "url(#ghost-trail-arrow)")
            .style("pointer-events", "none");
    };

    this.clearGhostTrails = function () {
        self.trailLayer.selectAll("*").remove();
    };

    this.updatesizeandopacity = function () {
        self.highlight(idview, self.selected, self.selectedB);
        self.halos.attr("r", function (d) {
            var fid = d.fidelity !== undefined ? parseFloat(d.fidelity) : 1.0;
            var distortion = Math.max(0.0, 1.0 - fid);
            return parseFloat(selfgff.instvertexratio) + 2.0 + distortion * 5.0;
        });
    };

    this.updatecolors = function () {
        self.nodesc
        .style("fill", function (d) {
            return targetColor(d.t);
        });
        self.highlight(idview, self.selected, self.selectedB);
    };

    this.exwholeinstancesprj = function() {
        var txtex = "DY\n"+data.length+"\n2\nx;y\n";
        for (var i in data){
            txtex += selfgff.getInstanceLabel(data[i].id)+";"+data[i].x+";"+data[i].y+";"+data[i].t+"\n";
        }
        var hiddenElement = document.createElement('a');
        hiddenElement.href = 'data:text/txt;charset=utf-8,' + encodeURI(txtex);
        hiddenElement.target = '_blank';
        hiddenElement.download = selfgff.datafileselectedname+'_selected.prj';
        hiddenElement.click();

/*         gelem("idaddhide").appendChild(hiddenElement);
        var olddata=gelem("idaddhide").lastChild;
        gelem("idaddhide").removeChild(olddata); */
    };

    this.exselectedinstancesprj = function() {
        if (self.selected.length>0){        
            var ids = new Set(self.selected);
            var selectedPoints = data.filter(function (point) { return ids.has(point.id); });
            var txtex = "DY\n"+selectedPoints.length+"\n2\nx;y\n";
            for (var point of selectedPoints) {
                txtex += selfgff.getInstanceLabel(point.id)+";"+point.x+";"+point.y+";"+point.t+"\n";
            }
            var hiddenElement = document.createElement('a');
            hiddenElement.href = 'data:text/txt;charset=utf-8,' + encodeURI(txtex);
            hiddenElement.target = '_blank';
            hiddenElement.download = selfgff.datafileselectedname+'_selected.prj';
            hiddenElement.click();

    /*         gelem("idaddhide").appendChild(hiddenElement);
            var olddata=gelem("idaddhide").lastChild;
            gelem("idaddhide").removeChild(olddata); */
        }
    };

    this.exidsinstancesprj = function() {
        if (self.selected.length>0){
            var txtex = "";
            for (var i of self.selected){
                txtex += selfgff.getInstanceLabel(i)+"\n";
            }
            var hiddenElement = document.createElement('a');
            hiddenElement.href = 'data:text/txt;charset=utf-8,' + encodeURI(txtex);
            hiddenElement.target = '_blank';
            hiddenElement.download = selfgff.datafileselectedname+'_ids.txt';
            hiddenElement.click();

    /*         gelem("idaddhide").appendChild(hiddenElement);
            var olddata=gelem("idaddhide").lastChild;
            gelem("idaddhide").removeChild(olddata); */
        }
    };

}
