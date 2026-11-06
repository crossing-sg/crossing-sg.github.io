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
            if (f.geometry.type === 'Point') { return norm(minus(hit.point, project(f.geometry.coordinates, origin))) <= 3; }
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
    // Phase 1 selector. The legacy choose() contract above remains unchanged.
    // Enumerate first, then validate EVERY contact; a shallow/endpoint contact
    // must not quietly disappear while some other road is accepted.
    function contacts(a, b, features) {
        var end = project(b, a), length = norm(end), seen = {}, found = [], overlaps = [];
        features.forEach(function (f) {
            var id = f.properties.seg_id;
            if (!Number.isSafeInteger(id) || seen[id]) { return; }
            seen[id] = true;
            var local = [];
            parts(f.geometry).forEach(function (line) {
                for (var i = 1; i < line.length; i++) {
                    var c = project(line[i - 1], a), d = project(line[i], a), v = minus(d, c), den = cross(end, v);
                    if (!norm(v)) { continue; }
                    if (Math.abs(den) < 1e-8) {
                        if (Math.abs(cross(c, end)) / length < .01) {
                            var t0 = (c[0] * end[0] + c[1] * end[1]) / (length * length);
                            var t1 = (d[0] * end[0] + d[1] * end[1]) / (length * length);
                            if (Math.min(1, Math.max(t0, t1)) - Math.max(0, Math.min(t0, t1)) > 1e-7) { overlaps.push(id); }
                        }
                        continue;
                    }
                    var t = cross(c, v) / den, u = cross(c, end) / den;
                    if (t < -1e-7 || t > 1 + 1e-7 || u < -1e-7 || u > 1 + 1e-7) { continue; }
                    t = Math.max(0, Math.min(1, t));
                    var h = { feature: f, point: [end[0] * t, end[1] * t], vector: v, position_m: t * length,
                        sine: Math.abs(den) / (length * norm(v)), endpoint: (i === 1 && u < 1e-6) || (i === line.length - 1 && u > 1 - 1e-6), tangent: false };
                    // A bend merely touching A-B is not a confirmed traversal.
                    var vertex = u < 1e-6 ? i - 1 : u > 1 - 1e-6 ? i : -1;
                    if (vertex > 0 && vertex < line.length - 1) {
                        var before = cross(end, project(line[vertex - 1], a)), after = cross(end, project(line[vertex + 1], a));
                        h.tangent = before * after > 0;
                    }
                    var duplicate = local.find(function (x) { return norm(minus(x.point, h.point)) < .01; });
                    if (duplicate) { duplicate.sine = Math.min(duplicate.sine, h.sine); duplicate.tangent = duplicate.tangent || h.tangent; }
                    else { local.push(h); }
                }
            });
            found = found.concat(local);
        });
        found.sort(function (x, y) { return x.position_m - y.position_m || x.feature.properties.seg_id - y.feature.properties.seg_id; });
        return { contacts: found, overlaps: Array.from(new Set(overlaps)), length_m: length };
    }
    function select(a, b, features, validation) {
        function invalid(reason, length) { return { ok: false, status: 'invalid', reason: reason, segment_ids: [], crossings: [], features: [], length_m: length || 0 }; }
        if (!validPoint(a) || !validPoint(b)) { return invalid('location'); }
        var length = metres(a, b);
        if (length < 2 || length > 80) { return invalid('length', length); }
        var raw = contacts(a, b, features), list = raw.contacts;
        if (!list.length) { return invalid(raw.overlaps.length ? 'collinear' : 'unmatched', length); }
        var evidence = validation || {}, records = evidence.records || {}, reasons = [], groups = [];
        function flag(code, ids) {
            var sorted = ids.slice().sort(function (x, y) { return x - y; });
            if (!reasons.some(function (r) { return r.code === code && r.segment_ids.join(',') === sorted.join(','); })) { reasons.push({ code: code, segment_ids: sorted }); }
        }
        if (evidence.ready !== true) { flag('validation_unavailable', list.map(function (h) { return h.feature.properties.seg_id; })); }
        if (raw.overlaps.length) { flag('collinear_overlap', raw.overlaps); }
        list.forEach(function (h) {
            var id = h.feature.properties.seg_id, record = records[id];
            if (h.position_m < 1 || raw.length_m - h.position_m < 1) { flag('endpoint_clearance', [id]); }
            if (h.sine < .5) { flag('crossing_angle', [id]); }
            if (h.tangent) { flag('tangent_vertex', [id]); }
            if (!record || record.seg_id !== id) { flag('source_metadata_unavailable', [id]); }
            else {
                (record.reasons || []).forEach(function (code) { flag(code, [id]); });
                if (record.status !== 'valid' && !(record.reasons || []).length) { flag('unresolved_validation', [id]); }
                if (record.linked !== true) { flag('source_metadata_unavailable', [id]); }
                var tags = record.tags || {};
                if (tags.layer === undefined || tags.layer === null || String(tags.layer).trim() === '' || !isFinite(Number(tags.layer))) { flag('unknown_grade', [id]); }
                else if (Number(tags.layer) !== 0) { flag('non_reference_level', [id]); }
                ['bridge', 'tunnel'].forEach(function (key) {
                    if (tags[key] === undefined || tags[key] === null || String(tags[key]).trim() === '') { flag('unknown_grade', [id]); }
                    else if (['no', 'false', '0'].indexOf(String(tags[key])) < 0) { flag(key, [id]); }
                });
                if (['no', 'private', 'permit', 'use_sidepath'].indexOf(tags.foot) >= 0) { flag('pedestrian_restriction', [id]); }
                if (['motorway', 'motorway_link', 'bus_guideway'].indexOf(tags.highway) >= 0) { flag('controlled_access_carriageway', [id]); }
                if (['no', 'private', 'permit'].indexOf(tags.access) >= 0 && ['yes', 'designated', 'permissive'].indexOf(tags.foot) < 0) { flag('access_requires_review', [id]); }
            }
            (evidence.guards || []).forEach(function (guard) {
                if (nearbyGuard(h, [guard], a)) { flag('nearby_grade_or_access_guard', [id]); }
            });
            var group = groups.find(function (g) {
                return g.hits.every(function (other) {
                    var oid = other.feature.properties.seg_id, left = records[id], right = records[oid];
                    var gradeConflict = left && right && left.tags && right.tags && left.tags.layer !== undefined && right.tags.layer !== undefined && Number(left.tags.layer) !== Number(right.tags.layer);
                    ['bridge', 'tunnel'].forEach(function (key) {
                        var l = left && left.tags && left.tags[key], r = right && right.tags && right.tags[key];
                        if (l !== undefined && l !== null && r !== undefined && r !== null && String(l).trim() !== '' && String(r).trim() !== '') {
                            if ((['no', 'false', '0'].indexOf(String(l)) < 0) !== (['no', 'false', '0'].indexOf(String(r)) < 0)) { gradeConflict = true; }
                        }
                    });
                    return !gradeConflict && h.endpoint && other.endpoint && norm(minus(h.point, other.point)) <= .25 &&
                        Math.abs(cross(h.vector, other.vector)) / (norm(h.vector) * norm(other.vector)) <= Math.sin(10 * RAD);
                });
            });
            if (group) { group.hits.push(h); }
            else { groups.push({ hits: [h] }); }
        });
        var crossings = groups.map(function (g) {
            var ids = Array.from(new Set(g.hits.map(function (h) { return h.feature.properties.seg_id; }))).sort(function (x, y) { return x - y; });
            return { position_m: g.hits.reduce(function (n, h) { return n + h.position_m; }, 0) / g.hits.length, segment_ids: ids };
        }).sort(function (x, y) { return x.position_m - y.position_m || x.segment_ids[0] - y.segment_ids[0]; });
        var ids = [], byId = {};
        list.forEach(function (h) { byId[h.feature.properties.seg_id] = h.feature; });
        crossings.forEach(function (g) { g.segment_ids.forEach(function (id) { if (ids.indexOf(id) < 0) { ids.push(id); } }); });
        var result = { ok: true, status: reasons.length ? 'needs_review' : 'valid', segment_ids: ids, crossings: crossings,
            length_m: length, features: ids.map(function (id) { return byId[id]; }), review_reasons: reasons,
            validation_version: evidence.version || null };
        if (crossings.length === 1) { result.feature = byId[ids.reduce(function (x, y) { return Math.min(x, y); }, Infinity)]; }
        return result;
    }
    return { choose: choose, select: select, contacts: contacts, metres: metres, validPoint: validPoint, hits: hits };
}());
if (typeof module !== 'undefined' && module.exports) { module.exports = RoadGeometry; }
