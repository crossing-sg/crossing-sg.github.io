// Adds the layers used by the story chapters. Every layer starts at opacity 0,
// then onChapterEnter / onChapterExit in config.js fade them in and out.
// Warning triangle with an exclamation mark, drawn on a canvas so no image file is needed.
// solid: red fill with a white mark (verified case). Otherwise a red outline (indicative case).
function warningIcon(solid) {
    var size = 64, c = document.createElement('canvas');
    c.width = c.height = size;
    var g = c.getContext('2d');
    g.lineJoin = 'round';
    g.beginPath();
    g.moveTo(32, 5); g.lineTo(60, 57); g.lineTo(4, 57); g.closePath();
    g.lineWidth = 7;
    g.strokeStyle = solid ? '#FFFFFF' : SITE.caseColor;
    g.stroke();
    g.fillStyle = solid ? SITE.caseColor : SITE.basemapDark;
    g.fill();
    g.fillStyle = solid ? '#FFFFFF' : SITE.caseColor;
    g.fillRect(29, 22, 6, 19);
    g.fillRect(29, 45, 6, 6);
    return g.getImageData(0, 0, size, size);
}

function addStoryLayers(map) {
    var data = '../data/story/';
    map.addImage('warn-solid', warningIcon(true), { pixelRatio: 2 });
    map.addImage('warn-outline', warningIcon(false), { pixelRatio: 2 });
    var warnLayout = {
        'icon-image': ['match', ['get', 'status'], 'indicative', 'warn-outline', 'warn-solid'],
        'icon-size': 1.1,
        'icon-allow-overlap': true,
        'icon-ignore-placement': true
    };

    // Island-wide context for the first chapters: every crossing, bridge, underpass, bus stop and MRT exit
    map.addSource('ctx-markers', { type: 'geojson', data: '../data/crossing_markers.geojson' });
    map.addSource('ctx-bus', { type: 'geojson', data: '../data/bus_stops.geojson' });
    map.addSource('ctx-mrt', { type: 'geojson', data: '../data/mrt_exits.geojson' });
    var dot = function (id, source, color, radius) {
        map.addLayer({
            id: id, type: 'circle', source: source,
            paint: {
                'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, radius, 14, radius * 2],
                'circle-color': color, 'circle-opacity': 0, 'circle-stroke-opacity': 0
            }
        });
    };
    dot('ctx-bus', 'ctx-bus', SITE.markerColors.bus, 1);
    dot('ctx-crossings', 'ctx-markers', ['match', ['get', 'kind'], 'overhead_bridge', SITE.markerColors.overhead_bridge,
        'underpass', SITE.markerColors.underpass, SITE.markerColors.crossing], 1.2);
    dot('ctx-mrt', 'ctx-mrt', SITE.markerColors.mrt, 1.8);

    // Transition chapter: planning areas shaded by the number of reported cases, and all 32 cases as dots
    map.addSource('area-stats', { type: 'geojson', data: data + 'step1b_area_stats.geojson' });
    map.addLayer({
        id: 'area-fill', type: 'fill', source: 'area-stats',
        paint: {
            'fill-color': ['step', ['get', 'cases'], 'rgba(0,0,0,0)', 1, '#5C2A2A', 2, '#8A3333', 4, '#C0392B'],
            'fill-opacity': 0
        }
    });
    map.addLayer({ id: 'area-line', type: 'line', source: 'area-stats', paint: { 'line-color': '#8A9099', 'line-width': 0.6, 'line-opacity': 0 } });
    map.addSource('all-cases', { type: 'geojson', data: data + 'step1b_all_cases.geojson' });
    map.addLayer({
        id: 'all-cases', type: 'circle', source: 'all-cases',
        paint: {
            'circle-radius': ['case', ['get', 'fatal'], 6, 4],
            'circle-color': ['match', ['get', 'status'], 'indicative', SITE.basemapDark, SITE.caseColor],
            'circle-stroke-color': ['match', ['get', 'status'], 'indicative', SITE.caseColor, '#FFFFFF'],
            'circle-stroke-width': 1.5, 'circle-opacity': 0, 'circle-stroke-opacity': 0
        }
    });

    map.addSource('cases', { type: 'geojson', data: data + 'step1_reported_cases.geojson' });
    map.addLayer({ id: 'cases', type: 'symbol', source: 'cases', layout: warnLayout, paint: { 'icon-opacity': 0 } });

    // Bukit Batok example (case V01): 300 m buffer, roads coloured by distance to the nearest crossing,
    // crossing markers and the case itself
    map.addSource('ex-buffer', { type: 'geojson', data: data + 'step2bb_buffer.geojson' });
    map.addLayer({ id: 'ex-buffer-fill', type: 'fill', source: 'ex-buffer', paint: { 'fill-color': '#FFFFFF', 'fill-opacity': 0 } });
    map.addLayer({ id: 'ex-buffer-line', type: 'line', source: 'ex-buffer', paint: { 'line-color': '#FFFFFF', 'line-width': 2, 'line-dasharray': [3, 2], 'line-opacity': 0 } });
    map.addSource('ex-gap', { type: 'geojson', data: data + 'step2bb_gap_segments.geojson' });
    map.addLayer({ id: 'ex-gap', type: 'line', source: 'ex-gap', paint: { 'line-color': SITE.gapColors, 'line-width': 5, 'line-opacity': 0 } });
    map.addSource('ex-markers', { type: 'geojson', data: data + 'step2bb_markers.geojson' });
    map.addLayer({
        id: 'ex-markers', type: 'circle', source: 'ex-markers',
        paint: {
            'circle-radius': 5,
            'circle-color': ['match', ['get', 'kind'], 'overhead_bridge', SITE.markerColors.overhead_bridge,
                'underpass', SITE.markerColors.underpass, SITE.markerColors.crossing],
            'circle-opacity': 0, 'circle-stroke-color': '#FFFFFF', 'circle-stroke-width': 1.5, 'circle-stroke-opacity': 0
        }
    });
    map.addSource('ex-case', { type: 'geojson', data: data + 'step2bb_case.geojson' });
    map.addLayer({ id: 'ex-case', type: 'symbol', source: 'ex-case', layout: warnLayout, paint: { 'icon-opacity': 0 } });

    // Island-wide walking detour: every HDB block coloured by its mean detour ratio
    map.addSource('detour-blocks', { type: 'geojson', data: '../data/detour_blocks.geojson' });
    map.addLayer({
        id: 'detour-blocks', type: 'circle', source: 'detour-blocks',
        paint: {
            'circle-color': SITE.detourColors,
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 1.5, 14, 5],
            'circle-opacity': 0, 'circle-stroke-opacity': 0
        }
    });

    // Case symbols stay on top of the road and marker layers
    map.addSource('block', { type: 'geojson', data: data + 'step3_block.geojson' });
    map.addLayer({ id: 'block', type: 'fill', source: 'block', paint: { 'fill-color': SITE.highlight, 'fill-opacity': 0 } });

    map.addSource('routes', { type: 'geojson', data: data + 'step3_routes.geojson' });
    map.addLayer({
        id: 'routes-other', type: 'line', source: 'routes',
        filter: ['all', ['==', ['get', 'kind'], 'walk'], ['!', ['get', 'highlight']]],
        paint: { 'line-color': '#9CA3AF', 'line-width': 2.5, 'line-opacity': 0 }
    });
    map.addLayer({
        id: 'route-walk', type: 'line', source: 'routes',
        filter: ['all', ['==', ['get', 'kind'], 'walk'], ['get', 'highlight']],
        paint: { 'line-color': SITE.routeWalk, 'line-width': 4, 'line-opacity': 0 }
    });
    map.addLayer({
        id: 'route-straight', type: 'line', source: 'routes',
        filter: ['all', ['==', ['get', 'kind'], 'straight'], ['get', 'highlight']],
        paint: { 'line-color': SITE.routeShortcut, 'line-width': 3, 'line-dasharray': [2, 2], 'line-opacity': 0 }
    });

    map.addSource('stops', { type: 'geojson', data: data + 'step3_destinations.geojson' });
    // Route destinations use the same bus and MRT pictograms as the Explore map (js/icons.js)
    var colors = {};
    colors['icon-bus'] = SITE.markerColors.bus;
    colors['icon-mrt'] = SITE.markerColors.mrt;
    addMapIcons(map, colors);
    var iconLayout = { 'icon-size': 0.9, 'icon-allow-overlap': true, 'icon-ignore-placement': true };
    map.addLayer({ id: 'stops', type: 'symbol', source: 'stops',
        layout: Object.assign({ 'icon-image': 'icon-bus' }, iconLayout), paint: { 'icon-opacity': 0 } });
    map.addLayer({ id: 'mrt-icons', type: 'symbol', source: 'ctx-mrt', minzoom: 13,
        layout: Object.assign({ 'icon-image': 'icon-mrt' }, iconLayout), paint: { 'icon-opacity': 0 } });

    map.moveLayer('ex-case');
    map.moveLayer('cases');

    // Steps 4 and 5 read live data from the Apps Script web app
    var empty = { type: 'FeatureCollection', features: [] };
    map.addSource('proposals', { type: 'geojson', data: empty });
    map.addLayer({
        id: 'proposals', type: 'circle', source: 'proposals',
        paint: {
            'circle-color': SITE.proposalColors, 'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 5, 10, 11],
            'circle-opacity': 0, 'circle-stroke-color': SITE.basemapDark, 'circle-stroke-width': 1, 'circle-stroke-opacity': 0
        }
    });
    // Match Explore: show only v2-reviewed, publicly visible road associations.
    // Multiple road dots may represent one distinct multi-road proposal.
    publishedProposalsForHome().then(function (publication) {
        map.getSource('proposals').setData({
            type: 'FeatureCollection',
            features: publication.segments.filter(function (s) {
                return Array.isArray(s.center) && s.center.length === 2 &&
                    s.center.every(Number.isFinite) && Number.isSafeInteger(s.count) && s.count >= 1;
            }).map(function (s) {
                return { type: 'Feature', geometry: { type: 'Point', coordinates: s.center },
                    properties: { count: s.count } };
            })
        });
    }).catch(function () {
        // On service errors do not fall back to the incompatible pilot dataset.
    });

    // Resident accounts for the "voices" chapter. HTML markers stay clickable while the
    // story map itself is not interactive. They show only when that chapter is active.
    var storiesApi = SITE.proposalApiUrl || '';
    if (storiesApi) {
        fetch(storiesApi + '?view=stories')
            .then(function (r) { return r.json(); })
            .then(function (res) { (res.stories || []).forEach(function (g) { addVoiceMarker(map, g); }); })
            .catch(function () { });
    }

}

// Reuse one version-checked v2 response for both Home map points and headline counts.
var homePublicationPromise = null;
function publishedProposalsForHome() {
    if (!SITE.proposalApiUrl || typeof ProposalRoads === 'undefined') {
        return Promise.reject(new Error('The v2 proposal service is unavailable'));
    }
    if (!homePublicationPromise) {
        homePublicationPromise = ProposalRoads.getPublic(SITE.proposalApiUrl, 'segments').then(function (response) {
            if (response.ok !== true || !response.summary || response.summary.ok !== true ||
                response.summary.scope !== 'published_only' ||
                !Number.isSafeInteger(response.summary.proposals) ||
                !Number.isSafeInteger(response.summary.segments) ||
                !Array.isArray(response.segments)) {
                throw new Error('Invalid published proposal summary');
            }
            var segments = ProposalRoads.publicSegments(response);
            if (segments.length !== response.summary.segments) {
                throw new Error('Published road counts do not match');
            }
            return { segments: segments, summary: response.summary };
        });
    }
    return homePublicationPromise;
}

window.addEventListener('DOMContentLoaded', fillSummaryCards);
function fillSummaryCards() {
    publishedProposalsForHome().then(function (publication) {
        var summary = publication.summary;
        document.getElementById('stat-proposals').innerText = summary.proposals;
        document.getElementById('stat-segments').innerText = 'accepted proposals, ' +
            summary.segments + ' road segments shown';
        document.getElementById('stat-updated').innerText = summary.lastUpdated || '-';
    }).catch(function () {
        // Failed requests are not evidence that the proposal total is zero.
        document.getElementById('stat-proposals').innerText = '–';
        document.getElementById('stat-segments').innerText = 'Accepted proposal data temporarily unavailable';
        document.getElementById('stat-updated').innerText = '–';
    });
}

function escapeHtml(t) {
    return String(t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
}

function addVoiceMarker(map, group) {
    var el = document.createElement('button');
    el.type = 'button';
    el.className = 'voice-marker';
    el.setAttribute('aria-label', 'Read the account from residents near this road');
    if (group.stories.length > 1) { el.textContent = group.stories.length; }
    var html = group.stories.map(function (s) {
        var meta = [s.type, s.reason, s.month].filter(Boolean).map(escapeHtml).join(', ');
        return '<blockquote>' + escapeHtml(s.text) + '</blockquote><small>' + meta + '</small>';
    }).join('<hr>');
    var popup = new mapboxgl.Popup({ offset: 14, maxWidth: '300px', className: 'voice-popup' }).setHTML(html);
    new mapboxgl.Marker({ element: el }).setLngLat(group.center).setPopup(popup).addTo(map);
}
