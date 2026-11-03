/* Shared, dependency-free crossing validation. The identical file is exported to
 * Apps Script. Local tangent-plane metres are sufficient for an 80 m crossing;
 * the source conflation itself uses EPSG:3414. No rendered/tile-clipped geometry.
 */
var RoadGeometry = (function () {
    'use strict';
    var RAD = Math.PI / 180, R = 6371000;
    function validPoint(p) {
        return Array.isArray(p) && p.length === 2 && p.every(function (n) { return typeof n === 'number' && isFinite(n); }) &&
            p[0] > 103.48 && p[0] < 104.60 && p[1] > 1.10 && p[1] < 1.55;
    }
    function metres(a, b) {
        var h = Math.sin((b[1] - a[1]) * RAD / 2) ** 2 + Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) * Math.sin((b[0] - a[0]) * RAD / 2) ** 2;
        return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
    }
    function project(p, origin) { return [(p[0] - origin[0]) * RAD * R * Math.cos(origin[1] * RAD), (p[1] - origin[1]) * RAD * R]; }
    function minus(a, b) { return [a[0] - b[0], a[1] - b[1]]; }
    function cross(a, b) { return a[0] * b[1] - a[1] * b[0]; }
    function norm(a) { return Math.hypot(a[0], a[1]); }
    function parts(g) { return g.type === 'LineString' ? [g.coordinates] : g.type === 'MultiLineString' ? g.coordinates : []; }
    function pointDistance(p, a, b) {
        var v = minus(b, a), w = minus(p, a), d = v[0] ** 2 + v[1] ** 2;
        var t = d ? Math.max(0, Math.min(1, (w[0] * v[0] + w[1] * v[1]) / d)) : 0;
        return Math.hypot(p[0] - a[0] - t * v[0], p[1] - a[1] - t * v[1]);
    }
    function hits(a, b, geometry) {
        var end = project(b, a), length = norm(end), found = [];
        parts(geometry).forEach(function (line) {
            for (var i = 1; i < line.length; i++) {
                var c = project(line[i - 1], a), d = project(line[i], a), v = minus(d, c), den = cross(end, v);
                if (Math.abs(den) < 1e-8) { continue; } // collinear placement is not a crossing
                var t = cross(c, v) / den, u = cross(c, end) / den;
                if (t * length < 1 || (1 - t) * length < 1 || u < -1e-7 || u > 1 + 1e-7) { continue; }
                var sine = Math.abs(den) / (length * norm(v));
                if (sine < .5) { continue; } // at least 30 degrees across the centreline
                found.push({ point: [end[0] * t, end[1] * t], vector: v, distance: Math.abs(t - .5) * length });
            }
        });
        return found;
    }
    function nearbyGuard(hit, guards, origin) {
        return guards.some(function (f) {
            return parts(f.geometry).some(function (line) {
                for (var i = 1; i < line.length; i++) {
                    if (pointDistance(hit.point, project(line[i - 1], origin), project(line[i], origin)) <= 3) { return true; }
                }
                return false;
            });
        });
    }
    function choose(a, b, features, guards) {
        if (!validPoint(a) || !validPoint(b)) { return { ok: false, reason: 'location' }; }
        var length = metres(a, b);
        if (length > 80 || length < 2) { return { ok: false, reason: 'length', length: length }; }
        var byId = {}, crossed = [];
        features.forEach(function (f) {
            var id = f.properties.seg_id;
            if (!Number.isSafeInteger(id) || byId[id]) { return; }
            byId[id] = true;
            hits(a, b, f.geometry).forEach(function (h) { h.feature = f; crossed.push(h); });
        });
        if (!crossed.length) { return { ok: false, reason: 'unmatched' }; }
        crossed.sort(function (x, y) { return x.distance - y.distance || x.feature.properties.seg_id - y.feature.properties.seg_id; });
        var best = crossed[0];
        for (var i = 1; i < crossed.length; i++) {
            var other = crossed[i], separation = norm(minus(best.point, other.point));
            var sine = Math.abs(cross(best.vector, other.vector)) / (norm(best.vector) * norm(other.vector));
            // Adjacent collinear pieces may share an endpoint; all other multiple
            // centreline crossings (including parallel carriageways) need review.
            if (separation > .25 || sine > Math.sin(10 * RAD)) { return { ok: false, reason: 'ambiguous' }; }
        }
        if (nearbyGuard(best, guards || [], a)) { return { ok: false, reason: 'restricted_or_grade' }; }
        var ids = crossed.map(function (x) { return x.feature.properties.seg_id; });
        var chosenId = Math.min.apply(null, ids); // stable at a shared segmentation endpoint
        return { ok: true, feature: crossed.find(function (x) { return x.feature.properties.seg_id === chosenId; }).feature, length: length };
    }
    return { choose: choose, metres: metres, validPoint: validPoint, hits: hits };
}());
if (typeof module !== 'undefined' && module.exports) { module.exports = RoadGeometry; }
