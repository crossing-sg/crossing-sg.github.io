// Explore map: one thematic layer at a time, reference points on request,
// OneMap search, block routes on click and proposal cards with a support button.

mapboxgl.accessToken = SITE.mapboxToken;
var params = new URLSearchParams(window.location.search);

var map = new mapboxgl.Map({
    container: 'map',
    style: SITE.mapStyle,
    center: [103.82, 1.355],
    zoom: 11
});
map.addControl(new mapboxgl.NavigationControl(), 'top-right');

var NOTES = {
    gap: 'Each 50 m piece of road is coloured by the straight-line distance to the nearest crossing, overhead bridge or underpass. Expressways are not shown. Click a piece of road to see its distance.',
    detour: 'Each point is an HDB block, coloured by how much longer the walk to nearby bus stops and MRT exits is than the straight distance. 2.0 means twice as far. Click a block to see its routes.',
    proposals: 'Road pieces coloured by the number of crossing proposals from residents. Pieces with fewer than three proposals are not shown. Click a piece of road to read the summary and add your support.'
};
var LEGENDS = {
    gap: [[SITE.classColors[0], 'Under 50 m'], [SITE.classColors[1], '50 to 100 m'], [SITE.classColors[2], '100 to 200 m'], [SITE.classColors[3], 'Over 200 m']],
    detour: [[SITE.classColors[0], 'Under 1.5'], [SITE.classColors[1], '1.5 to 2.0'], [SITE.classColors[2], '2.0 to 2.5'], [SITE.classColors[3], 'Over 2.5']],
    proposals: [[SITE.proposalRamp[0], '3 to 4 proposals'], [SITE.proposalRamp[1], '5 to 9'], [SITE.proposalRamp[2], '10 or more']]
};
var THEME_LAYERS = { gap: ['gap'], detour: ['blocks'], proposals: ['proposals', 'proposal-line'] };
var empty = { type: 'FeatureCollection', features: [] };

// Block names and mean ratios by postal code, used for the block panel title
var blockInfo = {};
var blocksReady = fetch('data/detour_blocks.geojson')
    .then(function (r) { return r.json(); })
    .then(function (gj) { gj.features.forEach(function (f) { blockInfo[f.properties.postal] = f.properties; }); });

map.on('load', function () {
    map.addSource('gap', { type: 'geojson', data: 'data/gap_segments.geojson' });
    map.addLayer({ id: 'gap', type: 'line', source: 'gap', paint: { 'line-color': SITE.gapColors, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 1.2, 16, 6] } });

    map.addSource('blocks', { type: 'geojson', data: 'data/detour_blocks.geojson' });
    map.addLayer({
        id: 'blocks', type: 'circle', source: 'blocks',
        paint: {
            'circle-color': SITE.detourColors,
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 2, 16, 8],
            'circle-stroke-color': SITE.basemapDark, 'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 13, 0, 16, 1.5]
        }
    });

    map.addSource('routes', { type: 'geojson', data: empty });
    map.addLayer({ id: 'route-walk', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'walk'], paint: { 'line-color': SITE.routeWalk, 'line-width': 3 } });
    map.addLayer({ id: 'route-straight', type: 'line', source: 'routes', filter: ['==', ['get', 'kind'], 'straight'], paint: { 'line-color': SITE.routeStraight, 'line-width': 1.5, 'line-dasharray': [2, 2] } });

    map.addSource('proposals', { type: 'geojson', data: empty });
    map.addLayer({ id: 'proposals', type: 'line', source: 'proposals', paint: { 'line-color': SITE.proposalColors, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 3, 16, 9] } });
    map.addSource('proposal-line', { type: 'geojson', data: empty });
    map.addLayer({ id: 'proposal-line', type: 'line', source: 'proposal-line', paint: { 'line-color': SITE.routeWalk, 'line-width': 6, 'line-opacity': 0.9 }, layout: { 'line-cap': 'round' } });

    // Reference points are shown as pictogram icons from zoom 15, so the island view stays readable.
    // Each entry: layer id, data file, kind filter, icon name, icon colour.
    var refs = [
        ['ref-bus', 'data/bus_stops.geojson', null, 'icon-bus', SITE.markerColors.bus],
        ['ref-mrt', 'data/mrt_exits.geojson', null, 'icon-mrt', SITE.markerColors.mrt],
        ['ref-crossing', 'data/crossing_markers.geojson', 'crossing', 'icon-crossing', SITE.markerColors.crossing],
        ['ref-bridge', 'data/crossing_markers.geojson', 'overhead_bridge', 'icon-bridge', SITE.markerColors.overhead_bridge],
        ['ref-underpass', 'data/crossing_markers.geojson', 'underpass', 'icon-underpass', SITE.markerColors.underpass]
    ];
    var iconColors = {};
    refs.forEach(function (r) { iconColors[r[3]] = r[4]; });
    addMapIcons(map, iconColors).then(function () {
        refs.forEach(function (r) {
            if (!map.getSource(r[1])) { map.addSource(r[1], { type: 'geojson', data: r[1] }); }
            var layer = {
                id: r[0], type: 'symbol', source: r[1], minzoom: 15,
                layout: {
                    'icon-image': r[3],
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 15, 0.75, 18, 1.1],
                    'icon-allow-overlap': true
                }
            };
            if (r[2]) { layer.filter = ['==', ['get', 'kind'], r[2]]; }
            map.addLayer(layer);
        });
        document.querySelectorAll('.ref').forEach(function (box) {
            box.addEventListener('change', updateRefs);
            // Show the same icon next to the checkbox in the side panel
            var r = refs.find(function (x) { return x[0] === box.value; });
            var img = document.createElement('img');
            img.src = iconUrl(r[3], r[4]);
            img.className = 'ref-icon';
            img.alt = '';
            box.insertAdjacentElement('afterend', img);
        });
        updateRefs();
    });

    document.querySelectorAll('input[name=layer]').forEach(function (radio) {
        radio.addEventListener('change', function () { setTheme(this.value); });
    });
    var start = params.get('layer') || 'gap';
    document.querySelector('input[name=layer][value=' + start + ']').checked = true;
    setTheme(start);

    loadProposals();
    if (params.get('block')) { openBlock(params.get('block'), true); }

    map.on('click', 'gap', function (e) {
        var p = e.features[0].properties;
        new mapboxgl.Popup().setLngLat(e.lngLat)
            .setHTML('<b>' + p.dist_m + ' m</b> to the nearest crossing, bridge or underpass')
            .addTo(map);
    });
    map.on('click', 'blocks', function (e) { openBlock(e.features[0].properties.postal, false); });
    map.on('click', 'proposals', function (e) { openSegment(e.features[0].properties); });
    ['gap', 'blocks', 'proposals'].forEach(function (id) {
        map.on('mouseenter', id, function () { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', id, function () { map.getCanvas().style.cursor = ''; });
    });
});

function setTheme(theme) {
    Object.keys(THEME_LAYERS).forEach(function (t) {
        THEME_LAYERS[t].forEach(function (id) {
            map.setLayoutProperty(id, 'visibility', t === theme ? 'visible' : 'none');
        });
    });
    var routesOn = theme === 'detour' ? 'visible' : 'none';
    map.setLayoutProperty('route-walk', 'visibility', routesOn);
    map.setLayoutProperty('route-straight', 'visibility', routesOn);
    document.getElementById('layer-note').innerText = NOTES[theme];
    document.getElementById('legend').innerHTML = LEGENDS[theme].map(function (row) {
        return '<div style="margin:6px 0"><span class="key" style="background:' + row[0] + '"></span>' + row[1] + '</div>';
    }).join('');
    closeCard();
}

function updateRefs() {
    document.querySelectorAll('.ref').forEach(function (box) {
        map.setLayoutProperty(box.value, 'visibility', box.checked ? 'visible' : 'none');
    });
}

// Detour: load the routes of one block from data/routes/<postal>.json
function openBlock(postal, fly) {
    blocksReady
        .then(function () { return fetch('data/routes/' + postal + '.json'); })
        .then(function (r) { return r.json(); })
        .then(function (gj) {
            map.getSource('routes').setData(gj);
            var walks = gj.features.filter(function (f) { return f.properties.kind === 'walk'; })
                .sort(function (a, b) { return b.properties.detour - a.properties.detour; });
            var block = blockInfo[Number(postal)];
            var title = block ? 'Blk ' + block.BLK_NO : 'Postal ' + postal;
            var mean = block ? block.mean_detour : '';
            var html = '<span class="close" onclick="closeCard()">x</span><b style="font-size:16px">' + title + '</b>' +
                '<div class="small">Postal ' + postal + (mean ? ' | mean detour ratio ' + mean : '') + ' | ' + walks.length + ' destinations</div><hr>';
            var maxRoute = Math.max.apply(null, walks.map(function (w) { return w.properties.route_m; }));
            walks.slice(0, 6).forEach(function (w) {
                var p = w.properties;
                var name = p.dest_type === 'bus_stop' ? 'Bus stop ' + p.dest_id : p.dest_id.replace('MRT STATION ', '');
                html += '<div><b>' + name + '</b><br><span class="small">Straight ' + p.straight_m + ' m | Walk ' + p.route_m +
                    ' m | ratio ' + p.detour + '</span><div class="bar"><div style="width:' + Math.round(p.route_m / maxRoute * 100) + '%"></div></div></div>';
            });
            if (walks.length > 6) { html += '<div class="small">Showing the 6 longest detours.</div>'; }
            showCard(html);
            if (fly && walks.length) {
                map.flyTo({ center: walks[0].geometry.coordinates[0], zoom: 16 });
            }
        })
        .catch(function () { showCard('<span class="close" onclick="closeCard()">x</span>No routes found for this block.'); });
}

// Proposals come from the Apps Script web app as one summary per road segment (no geometry).
// The road geometry is taken from the crossing gap file, matched on seg_id.
function loadProposals() {
    if (!SITE.appsScriptUrl) { return; }
    Promise.all([
        fetch(SITE.appsScriptUrl + '?view=segments').then(function (r) { return r.json(); }),
        fetch('data/gap_segments.geojson').then(function (r) { return r.json(); })
    ]).then(function (res) {
        var bySeg = {};
        res[0].segments.forEach(function (s) { bySeg[s.seg_id] = s; });
        var features = res[1].features.filter(function (f) { return bySeg[f.properties.seg_id]; }).map(function (f) {
            var s = bySeg[f.properties.seg_id];
            return { type: 'Feature', geometry: f.geometry, properties: Object.assign({}, s, { line: JSON.stringify(s.line) }) };
        });
        map.getSource('proposals').setData({ type: 'FeatureCollection', features: features });
    }).catch(function () { });
}

function openSegment(p) {
    var line = typeof p.line === 'string' ? JSON.parse(p.line) : p.line;
    map.getSource('proposal-line').setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: line }, properties: {} });
    var supported = hasSupported(p.seg_id);
    showCard('<span class="close" onclick="closeCard()">x</span><b style="font-size:16px">' + p.road + '</b>' +
        '<div class="nums"><div><span class="small">PROPOSALS</span><b>' + p.count + '</b></div>' +
        '<div><span class="small">SUPPORT</span><b id="support-count">' + p.support + '</b></div>' +
        '<div><span class="small">NEAREST CROSSING</span><b>' + p.dist_m + ' m</b></div></div>' +
        '<div class="small">Most requested type</div><b>' + p.top_type + '</b><br><br>' +
        '<div class="small">Most common reason</div><b>' + p.top_reason + '</b><br><br>' +
        '<button class="btn" id="support-btn" ' + (supported ? 'disabled' : '') + ' onclick="support(' + p.seg_id + ')">' +
        (supported ? 'Support added' : 'I need a crossing here too') + '</button> ' +
        '<a class="btn btn-light" href="propose.html?seg=' + p.seg_id + '">Propose here</a>');
}

// One support per segment per browser. A determined person can get around this,
// which the methodology page states as a limit.
function hasSupported(segId) {
    try { return JSON.parse(localStorage.getItem('supported') || '[]').indexOf(segId) >= 0; } catch (e) { return false; }
}

function support(segId) {
    if (!SITE.appsScriptUrl || hasSupported(segId)) { return; }
    var btn = document.getElementById('support-btn');
    btn.disabled = true;
    fetch(SITE.appsScriptUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },
        body: JSON.stringify({ kind: 'support', seg_id: segId })
    }).then(function () {
        try {
            var list = JSON.parse(localStorage.getItem('supported') || '[]');
            list.push(segId);
            localStorage.setItem('supported', JSON.stringify(list));
        } catch (e) { }
        var c = document.getElementById('support-count');
        c.innerText = Number(c.innerText) + 1;
        btn.innerText = 'Support added';
    }).catch(function () {
        btn.disabled = false;
        btn.innerText = 'Could not send. Try again';
    });
}

function showCard(html) {
    var card = document.getElementById('info');
    card.innerHTML = html;
    card.style.display = 'block';
}

function closeCard() {
    document.getElementById('info').style.display = 'none';
    if (map.getSource('proposal-line')) { map.getSource('proposal-line').setData(empty); }
}

// Address search (js/search.js). In the detour layer, picking an HDB address also opens its routes.
addSearch(document.getElementById('search'), document.getElementById('results'), function (r) {
    map.flyTo({ center: [Number(r.LONGITUDE), Number(r.LATITUDE)], zoom: 16.5 });
    var theme = document.querySelector('input[name=layer]:checked').value;
    if (theme === 'detour' && r.POSTAL && r.POSTAL !== 'NIL') { openBlock(r.POSTAL, false); }
});
