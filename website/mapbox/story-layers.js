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

    map.addSource('cases', { type: 'geojson', data: data + 'step1_reported_cases.geojson' });
    map.addLayer({ id: 'cases', type: 'symbol', source: 'cases', layout: warnLayout, paint: { 'icon-opacity': 0 } });

    // Bukit Batok cases. Verified cases are solid, indicative cases are outlined.
    map.addSource('area-cases', { type: 'geojson', data: data + 'step2_area_cases.geojson' });
    map.addLayer({ id: 'area-cases', type: 'symbol', source: 'area-cases', layout: warnLayout, paint: { 'icon-opacity': 0 } });

    map.addSource('gap', { type: 'geojson', data: data + 'step2_gap_segments.geojson' });
    map.addLayer({
        id: 'gap', type: 'line', source: 'gap',
        paint: { 'line-color': SITE.gapColors, 'line-width': 5, 'line-opacity': 0 }
    });

    map.addSource('markers', { type: 'geojson', data: data + 'step2_crossing_markers.geojson' });
    map.addLayer({
        id: 'markers', type: 'circle', source: 'markers',
        paint: {
            'circle-radius': 3.5,
            'circle-color': ['match', ['get', 'kind'], 'overhead_bridge', SITE.markerColors.overhead_bridge,
                'underpass', SITE.markerColors.underpass, SITE.markerColors.crossing],
            'circle-opacity': 0, 'circle-stroke-color': SITE.basemapDark, 'circle-stroke-width': 1, 'circle-stroke-opacity': 0
        }
    });

    map.addSource('block', { type: 'geojson', data: data + 'step3_block.geojson' });
    map.addLayer({ id: 'block', type: 'fill', source: 'block', paint: { 'fill-color': SITE.highlight, 'fill-opacity': 0 } });

    map.addSource('routes', { type: 'geojson', data: data + 'step3_routes.geojson' });
    map.addLayer({
        id: 'routes-other', type: 'line', source: 'routes',
        filter: ['all', ['==', ['get', 'kind'], 'walk'], ['!', ['get', 'highlight']]],
        paint: { 'line-color': SITE.routeWalk, 'line-width': 1.5, 'line-opacity': 0 }
    });
    map.addLayer({
        id: 'route-walk', type: 'line', source: 'routes',
        filter: ['all', ['==', ['get', 'kind'], 'walk'], ['get', 'highlight']],
        paint: { 'line-color': SITE.routeWalk, 'line-width': 4, 'line-opacity': 0 }
    });
    map.addLayer({
        id: 'route-straight', type: 'line', source: 'routes',
        filter: ['all', ['==', ['get', 'kind'], 'straight'], ['get', 'highlight']],
        paint: { 'line-color': SITE.routeStraight, 'line-width': 3, 'line-dasharray': [2, 2], 'line-opacity': 0 }
    });

    map.addSource('stops', { type: 'geojson', data: data + 'step3_destinations.geojson' });
    map.addLayer({
        id: 'stops', type: 'circle', source: 'stops',
        paint: {
            'circle-radius': 5, 'circle-color': SITE.basemapDark, 'circle-opacity': 0,
            'circle-stroke-color': SITE.routeWalk, 'circle-stroke-width': 2, 'circle-stroke-opacity': 0
        }
    });

    // Case points stay on top of the road and marker layers
    map.moveLayer('area-cases');
    map.moveLayer('cases');

    // Steps 4 and 5 read live data from the Apps Script web app
    var empty = { type: 'FeatureCollection', features: [] };
    map.addSource('proposals', { type: 'geojson', data: empty });
    map.addLayer({
        id: 'proposals', type: 'line', source: 'proposals',
        paint: { 'line-color': SITE.proposalColors, 'line-width': 6, 'line-opacity': 0 }
    });
    if (SITE.appsScriptUrl) {
        fetch(SITE.appsScriptUrl + '?view=segments')
            .then(function (r) { return r.json(); })
            .then(function (gj) { map.getSource('proposals').setData(gj); })
            .catch(function () { });
    }

    // Summary cards in the intro chapter
    fillSummaryCards();
}

function fillSummaryCards() {
    if (!SITE.appsScriptUrl) { return; }
    fetch(SITE.appsScriptUrl + '?view=summary')
        .then(function (r) { return r.json(); })
        .then(function (s) {
            document.getElementById('stat-proposals').innerText = s.proposals;
            document.getElementById('stat-segments').innerText = s.segments + ' road segments shown';
            document.getElementById('stat-updated').innerText = s.lastUpdated;
        })
        .catch(function () { });
}
