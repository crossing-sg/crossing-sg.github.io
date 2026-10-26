// Adds the layers used by the story chapters. Every layer starts at opacity 0,
// then onChapterEnter / onChapterExit in config.js fade them in and out.
function addStoryLayers(map) {
    var data = '../data/story/';

    map.addSource('cases', { type: 'geojson', data: data + 'step1_reported_cases.geojson' });
    map.addLayer({
        id: 'cases', type: 'circle', source: 'cases',
        paint: {
            'circle-radius': 8, 'circle-color': SITE.caseColor, 'circle-opacity': 0,
            'circle-stroke-color': SITE.basemapDark, 'circle-stroke-width': 2, 'circle-stroke-opacity': 0
        }
    });

    // Bukit Batok cases. Verified cases are filled, indicative cases are outlined.
    map.addSource('area-cases', { type: 'geojson', data: data + 'step2_area_cases.geojson' });
    map.addLayer({
        id: 'area-cases', type: 'circle', source: 'area-cases',
        paint: {
            'circle-radius': 8,
            'circle-color': ['match', ['get', 'status'], 'verified', SITE.caseColor, SITE.basemapDark],
            'circle-opacity': 0,
            'circle-stroke-color': ['match', ['get', 'status'], 'verified', SITE.basemapDark, SITE.caseColor],
            'circle-stroke-width': 2, 'circle-stroke-opacity': 0
        }
    });

    map.addSource('gap', { type: 'geojson', data: data + 'step2_gap_segments.geojson' });
    map.addLayer({
        id: 'gap', type: 'line', source: 'gap',
        paint: { 'line-color': SITE.gapColors, 'line-width': 5, 'line-opacity': 0 }
    });

    map.addSource('markers', { type: 'geojson', data: data + 'step2_crossing_markers.geojson' });
    map.addLayer({
        id: 'markers', type: 'circle', source: 'markers',
        paint: {
            'circle-radius': 5,
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
        paint: { 'line-color': SITE.routeStraight, 'line-width': 2.5, 'line-dasharray': [2, 2], 'line-opacity': 0 }
    });

    map.addSource('stops', { type: 'geojson', data: data + 'step3_destinations.geojson' });
    map.addLayer({
        id: 'stops', type: 'circle', source: 'stops',
        paint: {
            'circle-radius': 5, 'circle-color': SITE.basemapDark, 'circle-opacity': 0,
            'circle-stroke-color': SITE.routeWalk, 'circle-stroke-width': 2, 'circle-stroke-opacity': 0
        }
    });

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
