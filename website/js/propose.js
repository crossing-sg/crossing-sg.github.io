// Proposal form: the resident clicks point A and point B across a road.
// Canonical proposal roads are loaded for the visible area. The server repeats
// intersection, ambiguity, grade/access and identifier checks before storing.

mapboxgl.accessToken = SITE.mapboxToken;
var MIN_ZOOM = 16;      // points must be marked close in, so the segment match is reliable
var MAX_LENGTH = 80;    // metres between A and B

var map = new mapboxgl.Map({
    container: 'map',
    style: SITE.proposeStyle,
    center: SITE.proposalInitialCenter || [103.82, 1.355],
    zoom: SITE.proposalInitialZoom || 11
});
map.addControl(new mapboxgl.NavigationControl(), 'top-right');
map.on('style.load', function () { ProposalBasemap.apply(map); });

var points = [];
var segment = null;
var empty = { type: 'FeatureCollection', features: [] };
var roads = new ProposalRoads.Store(SITE.proposalRoadsBase || 'data/proposal-roads');
var selectionGeneration = 0;
var submissionId = null;
var submissionBusy = false;
var selection = null;
var serviceCapabilities = null;
var capabilityRequest = null;
var validation = null;
if (SITE.proposalApiUrl) {
    document.getElementById('proposal-publication-note').textContent = 'Every proposal awaits validation and moderation. Public road summaries require at least three approved, validated proposals. Individual marked points and pending records are not published.';
}
function proposalCapabilities() {
    if (!SITE.proposalApiUrl) { return Promise.resolve(null); }
    if (!capabilityRequest) {
        capabilityRequest = ProposalRoads.requireService(SITE.proposalApiUrl).then(function (caps) {
            if (caps.multi_road === true) {
                if (caps.multi_schema_version !== 'proposal-multi-v1' || !caps.validation) { throw new Error('Multi-road service version mismatch'); }
                validation = new ProposalValidation.Store({ validationBase: SITE.proposalValidationBase || caps.validation.base,
                    validationVersion: caps.validation.version, validationManifestSha256: caps.validation.manifest_sha256,
                    networkManifestSha256: caps.validation.network_manifest_sha256, networkTotalCount: caps.validation.total_count });
            }
            serviceCapabilities = caps; return caps;
        }).catch(function (error) { capabilityRequest = null; serviceCapabilities = null; throw error; });
    }
    return capabilityRequest;
}

map.once('style.load', function () {
    map.addSource('gap', { type: 'geojson', data: empty,
        attribution: 'Proposal road data: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> (ODbL)' });
    map.addLayer({ id: 'gap', type: 'line', source: 'gap', paint: { 'line-color': SITE.routeStraight, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.6, 16, 6], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.2, 16, 0.45] } });
    map.addLayer({ id: 'gap-selected', type: 'line', source: 'gap', filter: ['==', ['get', 'seg_id'], -1], paint: { 'line-color': SITE.highlight, 'line-width': 8 } });
    map.addSource('draft', { type: 'geojson', data: empty });
    map.addLayer({ id: 'draft-line', type: 'line', source: 'draft', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': SITE.routeWalk, 'line-width': 4, 'line-dasharray': [1.5, 1.5] } });
    map.addLayer({
        id: 'draft-points', type: 'circle', source: 'draft', filter: ['==', ['geometry-type'], 'Point'],
        paint: { 'circle-radius': 9, 'circle-color': SITE.basemapDark, 'circle-stroke-color': SITE.routeWalk, 'circle-stroke-width': 3 }
    });
    map.addLayer({
        id: 'draft-labels', type: 'symbol', source: 'draft', filter: ['==', ['geometry-type'], 'Point'],
        layout: { 'text-field': ['get', 'label'], 'text-size': 11, 'text-font': ['DIN Pro Bold', 'Arial Unicode MS Bold'], 'text-allow-overlap': true },
        paint: { 'text-color': SITE.routeWalk }
    });

    roads.attach(map, 'gap', function (status) {
        if (!points.length && status === 'error') { showWhere('Road data could not load. Please try again after checking your connection.'); }
    });
    // Opened from a segment card on the map page, including supplementary IDs.
    var seg = new URLSearchParams(window.location.search).get('seg');
    if (seg !== null) {
        roads.feature(seg).then(function (f) {
            var coords = f.geometry.type === 'LineString' ? f.geometry.coordinates : f.geometry.coordinates[0];
            // An explicit deep link can warm its destination road tiles while the
            // camera animates. Guard checks remain mandatory when A/B is selected.
            var xs = coords.map(function (p) { return p[0]; }), ys = coords.map(function (p) { return p[1]; });
            roads.area([Math.min.apply(null, xs) - .00005, Math.min.apply(null, ys) - .00005,
                Math.max.apply(null, xs) + .00005, Math.max.apply(null, ys) + .00005], { displayOnly: true }).catch(function () {});
            map.flyTo({ center: coords[Math.floor(coords.length / 2)], zoom: 17.5 });
        }).catch(function () { showWhere('This road could not be found. Search for the location and mark points again.'); });
    }
});

// Address search (js/search.js): jump close enough to mark points straight away
addSearch(document.getElementById('search'), document.getElementById('results'), function (r) {
    map.flyTo({ center: [Number(r.LONGITUDE), Number(r.LATITUDE)], zoom: 18 });
});

map.on('click', function (e) {
    if (submissionBusy) { return; }
    if (!map.getSource('draft')) { return; }   // map layers are still loading
    if (map.getZoom() < MIN_ZOOM) {
        showWhere('Zoom in further before marking points.');
        return;
    }
    if (points.length === 2) { resetPoints(); }
    points.push([Number(e.lngLat.lng.toFixed(6)), Number(e.lngLat.lat.toFixed(6))]);
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

// Use full original geometry, not queryRenderedFeatures or nearest vertices.
function findSegment() {
    var token = ++selectionGeneration, marked = points.map(function (p) { return p.slice(); });
    var length = RoadGeometry.metres(marked[0], marked[1]);
    segment = null; selection = null; map.setFilter('gap-selected', ['==', ['get', 'seg_id'], -1]);
    if (length > MAX_LENGTH) {
        showWhere('The two points are ' + Math.round(length) + ' m apart. Mark them on opposite sides of one road, no more than ' + MAX_LENGTH + ' m apart.');
        return;
    }
    showWhere('Checking the road between A and B…');
    var pad = .00005;
    roads.area([Math.min(marked[0][0], marked[1][0]) - pad, Math.min(marked[0][1], marked[1][1]) - pad,
        Math.max(marked[0][0], marked[1][0]) + pad, Math.max(marked[0][1], marked[1][1]) + pad]).then(function (data) {
        if (token !== selectionGeneration) { return; }
        if (data.guardsReady !== true) { throw new Error('Road restrictions have not loaded'); }
        return proposalCapabilities().then(function (caps) {
            if (token !== selectionGeneration) { return; }
            if (caps && caps.multi_road === true) {
                return validation.context(marked[0], marked[1], data.features).then(function (evidence) {
                    if (token !== selectionGeneration) { return; }
                    showMultiSelection(RoadGeometry.select(marked[0], marked[1], data.features, evidence));
                });
            }
            applySingleSelection(marked, data);
        });
    }).catch(function () {
        if (token === selectionGeneration) { showWhere('Road data could not load. Your location has not been assigned. Please check your connection and mark again.'); }
    });
}

function applySingleSelection(marked, data) {
    var length = RoadGeometry.metres(marked[0], marked[1]);
    var result = RoadGeometry.choose(marked[0], marked[1], data.features, data.guards);
    if (!result.ok) {
        var messages = {
            unmatched: 'No mapped road or path crosses the marked line. Put A and B on opposite sides of one road or path.',
            ambiguous: 'This line crosses more than one road or an ambiguous intersection. Move A and B closer around one road. This location needs review if it still cannot be matched.',
            restricted_or_grade: 'This location has restricted pedestrian access or grade-separated geometry and needs review. It cannot be submitted automatically.',
            length: 'Mark two distinct points, at least 2 m and no more than 80 m apart, on opposite sides of one road.'
        };
        showWhere(messages[result.reason] || 'This location could not be matched reliably. Mark the points again.'); return;
    }
    segment = result.feature.properties;
    map.setFilter('gap-selected', ['==', ['get', 'seg_id'], segment.seg_id]);
    showWhere('Points A and B marked, ' + Math.round(length) + ' m apart.<br>Nearest existing crossing: ' + ProposalRoads.distance(segment.dist_m) + '.');
}

function resetPoints() {
    if (submissionBusy) { return; }
    selectionGeneration++;
    submissionId = null;
    points = [];
    segment = null;
    selection = null;
    document.getElementById('submit').innerText = 'Submit proposal';
    document.getElementById('error').innerText = '';
    if (map.getSource('draft')) {
        map.getSource('draft').setData(empty);
        map.setFilter('gap-selected', ['==', ['get', 'seg_id'], -1]);
    }
    showWhere('Search or zoom in to a road, then click one side of the road and then the other.');
}

function showMultiSelection(result) {
    selection = result;
    segment = result.feature ? result.feature.properties : null;
    if (!result.ok) {
        var invalid = { length: 'Mark two distinct points, at least 2 m and no more than 80 m apart.',
            unmatched: 'No road centreline crosses A–B. Mark opposite sides of the road.',
            collinear: 'A–B follows a road instead of crossing it. Mark opposite sides of the road.' };
        showWhere(invalid[result.reason] || 'This selection is invalid. Please mark the points again.');
        document.getElementById('submit').innerText = 'Submit proposal'; return;
    }
    map.setFilter('gap-selected', ['in', ['get', 'seg_id'], ['literal', result.segment_ids]]);
    var count = result.crossings.length, message = 'Points A and B marked, ' + Math.round(result.length_m) + ' m apart.<br>' +
        count + ' crossing group' + (count === 1 ? '' : 's') + ' · ' + result.segment_ids.length + ' road segment' + (result.segment_ids.length === 1 ? '' : 's') + '.';
    if (result.status === 'needs_review') {
        var labels = { unknown_grade: 'grade unknown', source_metadata_unavailable: 'source metadata unavailable', validation_unavailable: 'validation data unavailable',
            bridge: 'bridge', tunnel: 'tunnel', non_reference_level: 'non-reference road level', pedestrian_restriction: 'pedestrian restriction',
            controlled_access_carriageway: 'controlled-access carriageway', nearby_grade_or_access_guard: 'nearby grade/access guard', access_requires_review: 'access requires review' };
        var reasons = Array.from(new Set(result.review_reasons.map(function (r) { return labels[r.code] || r.code.replace(/_/g, ' '); })));
        message += '<br><strong>Needs review — unvalidated.</strong> ' + ProposalRoads.escape(reasons.join('; ')) + '.<br>Your proposal can enter review. It is not publicly counted until validation and approval.';
        document.getElementById('submit').innerText = 'Submit for review';
    } else {
        message += '<br>Validation checks passed. Your proposal still awaits moderation.';
        document.getElementById('submit').innerText = 'Submit proposal';
    }
    if (result.segment_ids.length === 1) { message += '<br>Nearest existing crossing: ' + ProposalRoads.distance(result.features[0].properties.dist_m) + '.'; }
    showWhere(message);
}

function showWhere(html) { document.getElementById('where').innerHTML = html; }

document.getElementById('story').addEventListener('input', function () {
    document.getElementById('chars').innerText = this.value.length;
    if (!submissionBusy) { submissionId = null; }
});
document.querySelectorAll('input[type=radio]').forEach(function (r) {
    r.addEventListener('change', function () { document.getElementById('error').innerText = ''; if (!submissionBusy) { submissionId = null; } });
});

function checked(name) {
    var el = document.querySelector('input[name=' + name + ']:checked');
    return el ? el.value : '';
}

function submitProposal() {
    if (submissionBusy) { return; }
    var error = document.getElementById('error');
    var type = checked('type');
    var reason = checked('reason');
    if (!segment && !(selection && selection.ok)) { error.innerText = 'Mark point A and point B across a road first.'; return; }
    if (!type) { error.innerText = 'Choose a type of crossing.'; return; }
    if (!reason) { error.innerText = 'Choose the main reason.'; return; }
    // Pilot mode (no v2 URL yet) sends to the pilot Apps Script without the v2 handshake
    var pilot = !SITE.proposalApiUrl, url = pilot ? SITE.appsScriptUrl : SITE.proposalApiUrl;

    var round6 = function (p) { return [Number(p[0].toFixed(6)), Number(p[1].toFixed(6))]; };
    if (!submissionId) { submissionId = crypto.randomUUID(); }
    var body = {
        kind: 'proposal',
        request_id: submissionId,
        seg_id: segment ? segment.seg_id : undefined,
        dist_m: segment ? segment.dist_m : null,
        registry_version: roads.manifest.version,
        a: round6(points[0]),
        b: round6(points[1]),
        type: type,
        reason: reason,
        story: document.getElementById('story').value.trim(),
        website: document.getElementById('website').value
    };
    if (selection) {
        if (pilot || !serviceCapabilities || serviceCapabilities.multi_road !== true) { error.innerText = 'The service has not advertised multi-road support. Please try again later.'; return; }
        body.schema_version = serviceCapabilities.multi_schema_version;
        body.validation_version = selection.validation_version;
        body.segment_ids = selection.segment_ids.slice(); body.crossings = selection.crossings;
        body.validation_status = selection.status; body.review_requested = selection.status === 'needs_review';
    }
    var btn = document.getElementById('submit');
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 30000);
    submissionBusy = true;
    btn.disabled = true;
    btn.innerText = 'Sending...';
    (pilot ? Promise.resolve() : ProposalRoads.requireService(url, controller.signal)).then(function (caps) { if (selection && (!caps || caps.multi_road !== true || caps.multi_schema_version !== body.schema_version)) { throw new Error('Multi-road capability unavailable'); } return fetch(url, {
        signal: controller.signal,
        method: 'POST',
        // text/plain avoids the CORS preflight that Apps Script does not answer
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify(body)
    }); })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (!res.ok) {
                var spatial = ['segment', 'segment_mismatch', 'ambiguous', 'unmatched', 'restricted_or_grade', 'length', 'location'];
                throw new Error(spatial.indexOf(res.error) >= 0 ? 'service_geometry' : 'service_unavailable');
            }
            if (!pilot && !ProposalRoads.compatible(res)) { throw new Error('Service version mismatch'); }
            showThanks(null, selection ? 'One proposal · ' + selection.segment_ids.length + ' associated road segment' + (selection.segment_ids.length === 1 ? '' : 's') : 'Road segment ' + segment.seg_id);
        })
        .catch(function (err) {
            btn.disabled = false;
            btn.innerText = 'Submit proposal';
            error.innerText = err && err.message === 'service_geometry' ?
                'The service could not confirm this road match. Mark the points again; this location may need review.' :
                'Could not record the proposal. Check the connection and try again. No public proposal has been created.';
        }).finally(function () { submissionBusy = false; clearTimeout(timeout); });
}

function showThanks(count, road) {
    document.getElementById('form-page').style.display = 'none';
    document.getElementById('thanks').style.display = 'block';
    document.getElementById('thanks-road').innerText = road || '';
    if (!SITE.proposalApiUrl) {
        document.getElementById('thanks-count').innerText = 'Your proposal has been recorded.';
        document.getElementById('thanks-next').innerText = 'During this pilot every proposal is shown on the map. Individual marked points are not published.';
        return;
    }
    document.getElementById('thanks-count').innerText = 'Your proposal is awaiting review.';
    document.getElementById('thanks-next').innerText = 'A road appears publicly only after at least three proposals have been approved. Individual marked points and unreviewed submissions are not published.';
}

function shareLink() {
    var url = window.location.origin + window.location.pathname + (segment ? '?seg=' + segment.seg_id : '');
    navigator.clipboard.writeText(url).then(function () {
        document.getElementById('share').innerText = 'Link copied';
    });
}
