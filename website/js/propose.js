// Proposal form: the resident clicks point A and point B across a road.
// The road segment is found with map.queryRenderedFeatures on the crossing gap layer,
// so only the segment id and the rounded points are sent to the Apps Script web app.

mapboxgl.accessToken = SITE.mapboxToken;
var MIN_ZOOM = 16;      // points must be marked close in, so the segment match is reliable
var MAX_LENGTH = 80;    // metres between A and B

var map = new mapboxgl.Map({
    container: 'map',
    style: SITE.mapStyle,
    center: [103.82, 1.355],
    zoom: 11
});
map.addControl(new mapboxgl.NavigationControl(), 'top-right');

var points = [];
var segment = null;
var empty = { type: 'FeatureCollection', features: [] };

map.on('load', function () {
    map.addSource('gap', { type: 'geojson', data: 'data/gap_segments.geojson' });
    map.addLayer({ id: 'gap', type: 'line', source: 'gap', paint: { 'line-color': SITE.routeStraight, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.6, 16, 6], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.2, 16, 0.45] } });
    map.addLayer({ id: 'gap-selected', type: 'line', source: 'gap', filter: ['==', ['get', 'seg_id'], -1], paint: { 'line-color': SITE.highlight, 'line-width': 8 } });
    map.addSource('draft', { type: 'geojson', data: empty });
    map.addLayer({ id: 'draft-line', type: 'line', source: 'draft', paint: { 'line-color': SITE.routeWalk, 'line-width': 4, 'line-dasharray': [1.5, 1.5] } });
    map.addLayer({
        id: 'draft-points', type: 'circle', source: 'draft', filter: ['==', ['geometry-type'], 'Point'],
        paint: { 'circle-radius': 9, 'circle-color': SITE.basemapDark, 'circle-stroke-color': SITE.routeWalk, 'circle-stroke-width': 3 }
    });
    map.addLayer({
        id: 'draft-labels', type: 'symbol', source: 'draft', filter: ['==', ['geometry-type'], 'Point'],
        layout: { 'text-field': ['get', 'label'], 'text-size': 11, 'text-font': ['DIN Pro Bold', 'Arial Unicode MS Bold'], 'text-allow-overlap': true },
        paint: { 'text-color': SITE.routeWalk }
    });

    // Opened from a segment card on the map page
    var seg = new URLSearchParams(window.location.search).get('seg');
    if (seg) {
        fetch('data/gap_segments.geojson').then(function (r) { return r.json(); }).then(function (gj) {
            var f = gj.features.find(function (x) { return String(x.properties.seg_id) === seg; });
            if (f) { map.flyTo({ center: f.geometry.coordinates[0], zoom: 17.5 }); }
        });
    }
});

// Address search (js/search.js): jump close enough to mark points straight away
addSearch(document.getElementById('search'), document.getElementById('results'), function (r) {
    map.flyTo({ center: [Number(r.LONGITUDE), Number(r.LATITUDE)], zoom: 18 });
});

map.on('click', function (e) {
    if (!map.getSource('draft')) { return; }   // map layers are still loading
    if (map.getZoom() < MIN_ZOOM) {
        showWhere('Zoom in further before marking points.');
        return;
    }
    if (points.length === 2) { resetPoints(); }
    points.push([e.lngLat.lng, e.lngLat.lat]);
    if (points.length === 2) { findSegment(); }
    drawDraft();
});

function drawDraft() {
    var feats = points.map(function (p, i) {
        return { type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: { label: i === 0 ? 'A' : 'B' } };
    });
    if (points.length === 2) { feats.unshift({ type: 'Feature', geometry: { type: 'LineString', coordinates: points }, properties: {} }); }
    map.getSource('draft').setData({ type: 'FeatureCollection', features: feats });
    if (points.length === 1) { showWhere('Point A marked. Now click the other side of the road.'); }
}

// The segment is the gap layer feature that the A to B line crosses, closest to its midpoint
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

function resetPoints() {
    points = [];
    segment = null;
    if (map.getSource('draft')) {
        map.getSource('draft').setData(empty);
        map.setFilter('gap-selected', ['==', ['get', 'seg_id'], -1]);
    }
    showWhere('Search or zoom in to a road, then click one side of the road and then the other.');
}

function showWhere(html) { document.getElementById('where').innerHTML = html; }

document.getElementById('story').addEventListener('input', function () {
    document.getElementById('chars').innerText = this.value.length;
});
document.querySelectorAll('input[type=radio]').forEach(function (r) {
    r.addEventListener('change', function () { document.getElementById('error').innerText = ''; });
});

function checked(name) {
    var el = document.querySelector('input[name=' + name + ']:checked');
    return el ? el.value : '';
}

function submitProposal() {
    var error = document.getElementById('error');
    var type = checked('type');
    var reason = checked('reason');
    if (!segment) { error.innerText = 'Mark point A and point B across a road first.'; return; }
    if (!type) { error.innerText = 'Choose a type of crossing.'; return; }
    if (!reason) { error.innerText = 'Choose the main reason.'; return; }
    if (!SITE.appsScriptUrl) { error.innerText = 'The form is not connected yet. Add the Apps Script URL in js/site-config.js.'; return; }

    var round4 = function (p) { return [Number(p[0].toFixed(4)), Number(p[1].toFixed(4))]; };
    var body = {
        kind: 'proposal',
        seg_id: segment.seg_id,
        dist_m: segment.dist_m,
        a: round4(points[0]),
        b: round4(points[1]),
        type: type,
        reason: reason,
        story: document.getElementById('story').value.trim(),
        website: document.getElementById('website').value
    };
    var btn = document.getElementById('submit');
    btn.disabled = true;
    btn.innerText = 'Sending...';
    fetch(SITE.appsScriptUrl, {
        method: 'POST',
        // text/plain avoids the CORS preflight that Apps Script does not answer
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify(body)
    })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (!res.ok) { throw new Error(res.error || 'error'); }
            showThanks(res.count, res.road);
        })
        .catch(function () {
            btn.disabled = false;
            btn.innerText = 'Submit proposal';
            error.innerText = 'Could not send the proposal. Check the connection and try again.';
        });
}

function showThanks(count, road) {
    document.getElementById('form-page').style.display = 'none';
    document.getElementById('thanks').style.display = 'block';
    document.getElementById('thanks-road').innerText = road || '';
    document.getElementById('thanks-count').innerText = 'This road segment now has ' + count + (count === 1 ? ' proposal' : ' proposals');
    document.getElementById('thanks-next').innerText = 'Your proposal is on the public map now. Share the link so neighbours can add theirs.';
}

function shareLink() {
    var url = window.location.origin + window.location.pathname;
    navigator.clipboard.writeText(url).then(function () {
        document.getElementById('share').innerText = 'Link copied';
    });
}
