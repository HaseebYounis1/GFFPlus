/*
# Author: Ivar Vargas Belizario
# Copyright (c) 2020
# E-mail: ivar@usp.br
*/


function chart_palettecolors(functionT, id, w, h, colorf) {
    gelem(id).setAttribute("width", w + "px");
    gelem(id).setAttribute("height", h + "px");

    var n = 100;
    var data = Array.from(Array(n).keys());
    var handleHeight = 10;
    var usableH = Math.max(1, h - handleHeight);
    var currentY = h; // starts at bottom (threshold = 0)
    var lastCommittedT = -1;
    var dragStartY = 0;
    var dragStartHandleY = h;
    var dragSensitivity = 0.45; // damped drag sensitivity for fine control
    var stepSize = 0.02; // 2% threshold quantization to prevent jitter

    var xScale = d3.scaleLinear()
        .domain([0, n - 1])
        .range([0, h]);

    var idview = "#" + id;

    function clampY(y) {
        if (y < handleHeight) return handleHeight;
        if (y > h) return h;
        return y;
    }

    function yToThreshold(y) {
        var raw = (h - clampY(y)) / usableH;
        var quantized = Math.round(raw / stepSize) * stepSize;
        return Math.max(0.0, Math.min(1.0, quantized));
    }

    function thresholdToY(t) {
        return clampY(h - (t * usableH));
    }

    function showThresholdTooltip(t) {
        var evt = d3.event && d3.event.sourceEvent ? d3.event.sourceEvent : d3.event;
        if (evt && typeof GFFOBJ !== "undefined" && GFFOBJ && GFFOBJ.setToolpiltex) {
            GFFOBJ.setToolpiltex(evt.pageX + 12, evt.pageY, "Threshold: " + Math.round(t * 100) + "%");
        }
    }

    function hideThresholdTooltip() {
        if (typeof GFFOBJ !== "undefined" && GFFOBJ && GFFOBJ.hideToolpiltex) {
            GFFOBJ.hideToolpiltex();
        }
    }

    function applyHandleVisual(y) {
        currentY = clampY(y);
        bars.attr("transform", "translate(0, " + (currentY - h) + ")");
    }

    function commitThreshold(y, force) {
        var t = yToThreshold(y);
        var snappedY = thresholdToY(t);
        applyHandleVisual(snappedY);
        showThresholdTooltip(t);
        if (force || Math.abs(t - lastCommittedT) >= stepSize - 1e-6) {
            lastCommittedT = t;
            functionT(t);
        }
    }

    var dragg = d3.drag()
        .on("start", function () {
            dragStartY = d3.mouse(this)[1];
            dragStartHandleY = currentY;
            showThresholdTooltip(yToThreshold(currentY));
        })
        .on("drag", function () {
            var pointerY = d3.mouse(this)[1];
            var deltaY = (pointerY - dragStartY) * dragSensitivity;
            var nextY = clampY(dragStartHandleY + deltaY);
            applyHandleVisual(nextY);
            showThresholdTooltip(yToThreshold(nextY));
        })
        .on("end", function () {
            commitThreshold(currentY, true);
            hideThresholdTooltip();
        });

    d3.select(idview).selectAll("svg").remove();
    var svgmain = d3.select(idview).append("svg")
        .attr("width", w)
        .attr("height", h)
        .style("cursor", "ns-resize")
        .call(dragg)
        .on("click", function () {
            if (d3.event.defaultPrevented) {
                return;
            }
            var coords = d3.mouse(this);
            commitThreshold(coords[1], true);
        })
        .on("mouseout", function () {
            hideThresholdTooltip();
        })
        .append("g");

    var palette = svgmain.append("g").selectAll(".rectclass");
    var bars = svgmain.append("g");

    palette = palette.data(data);
    palette.exit().remove();
    palette = palette.enter().append("rect")
        .attr("class", "rectclass")
        .attr("x", 0)
        .attr("y", function (d) { return Math.floor(xScale(d)); })
        .attr("width", w)
        .attr("height", function (d) {
            if (d == n - 1) {
                return 6;
            }
            return Math.floor(xScale(d + 1)) - Math.floor(xScale(d)) + 1;
        })
        .attr("fill", function (d) { return colorf(1 - (d / (n - 1))); });

    bars.selectAll(".splitermove").remove();
    bars
        .append("rect")
        .attr("class", "splitermove")
        .attr("x", 0)
        .attr("y", h - handleHeight)
        .attr("width", w)
        .attr("height", handleHeight)
        .attr("fill", "#222")
        .attr("stroke", "#fff")
        .style("stroke-width", 1.2);
}

