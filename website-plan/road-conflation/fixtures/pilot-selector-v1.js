// Historical pre-integration selector from Git a4dc7558, for reproducible data-phase QA only.
function findSegment() {
    var a = map.project(points[0]);
    var b = map.project(points[1]);
    var box = [[Math.min(a.x, b.x) - 4, Math.min(a.y, b.y) - 4], [Math.max(a.x, b.x) + 4, Math.max(a.y, b.y) + 4]];
    var mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    var found = map.queryRenderedFeatures(box, { layers: ['gap'] });
    var length = metres(points[0], points[1]);
    segment = null;
    if (length > MAX_LENGTH) {
        showWhere('The two points are ' + Math.round(length) + ' m apart. Mark them on opposite sides of one road, no more than ' + MAX_LENGTH + ' m apart.');
        return;
    }
    if (!found.length) {
        showWhere('No road found between the two points. Mark one point on each side of a road.');
        return;
    }
    found.sort(function (f, g) { return pixelDist(f, mid) - pixelDist(g, mid); });
    segment = found[0].properties;
    map.setFilter('gap-selected', ['==', ['get', 'seg_id'], segment.seg_id]);
    showWhere('Points A and B marked, ' + Math.round(length) + ' m apart.<br>Nearest existing crossing: ' + segment.dist_m + ' m.');
}

function pixelDist(feature, p) {
    var coords = feature.geometry.type === 'LineString' ? feature.geometry.coordinates : feature.geometry.coordinates[0];
    return Math.min.apply(null, coords.map(function (c) {
        var q = map.project(c);
        return Math.hypot(q.x - p.x, q.y - p.y);
    }));
}

function metres(p, q) {
    var R = 6371000, rad = Math.PI / 180;
    var dLat = (q[1] - p[1]) * rad, dLng = (q[0] - p[0]) * rad;
    var h = Math.sin(dLat / 2) ** 2 + Math.cos(p[1] * rad) * Math.cos(q[1] * rad) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
}

function resetPoints() {}
