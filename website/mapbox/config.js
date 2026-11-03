// Story chapters for the Home page. Layer names come from story-layers.js.
// Each chapter sets the opacity of every story layer when it is entered, so the result
// does not depend on the order in which scrollama fires enter and exit events.
var STORY_LAYERS = ['ctx-bus', 'ctx-crossings', 'ctx-mrt', 'area-fill', 'area-line', 'all-cases', 'cases',
    'rv-buffer-fill', 'rv-buffer-line', 'rv-gap', 'rv-markers', 'rv-case', 'detour-blocks', 'proposals'];
var only = function (visible) {
    return STORY_LAYERS.map(function (l) {
        return { layer: l, opacity: visible[l] === undefined ? 0 : visible[l], duration: 800 };
    });
};

// Keeps the map content clear of the story card. Left-aligned cards cover about 38% of a
// wide screen, so the camera centres the data in the remaining area. On narrow screens the
// card sits in the middle and no padding is used.
var PAD_LEFT = { top: 40, bottom: 40, left: Math.round(window.innerWidth * 0.38), right: 40 };
var PAD_NONE = { top: 0, bottom: 0, left: 0, right: 0 };
var PAD_STRIP = { top: 20, bottom: Math.round(window.innerHeight * 0.42), left: 20, right: 20 };
// Measures the right edge of the story card and updates PAD_LEFT in place, so every chapter
// that refers to it uses the current screen size
function updateStoryPadding() {
    var card = document.querySelector('.step.lefty > div');
    var wide = window.innerWidth > 750;
    var right = card ? card.getBoundingClientRect().right : window.innerWidth * 0.38;
    PAD_LEFT.left = wide ? Math.round(right + 40) : 0;
    PAD_LEFT.top = PAD_LEFT.bottom = wide ? 40 : 0;
    PAD_LEFT.right = wide ? 40 : 0;
}
window.addEventListener('load', updateStoryPadding);
window.addEventListener('resize', updateStoryPadding);


// Cases and crossing provision for the planning areas with a fatal case in the news sample
// (from website-plan/make_area_stats.py). Crossings = road crossings, overhead bridges and underpasses.
var AREA_STATS = {
    national: { crossings_per_km: 3.8, pct_far: 33 },
    rows: [
        { name: 'Bukit Batok', cases: 5, crossings_per_km: 5.4, pct_far: 20 },
        { name: 'Queenstown', cases: 1, crossings_per_km: 5.3, pct_far: 19 },
        { name: 'Geylang', cases: 2, crossings_per_km: 3.2, pct_far: 13 },
        { name: 'River Valley', cases: 1, crossings_per_km: 2.2, pct_far: 17 },
        { name: 'Novena', cases: 4, crossings_per_km: 2.0, pct_far: 31 }
    ]
};

// Wide chart drawn as inline SVG for the centred panel. Areas run left to right. The upper row of
// columns shows reported cases, the lower row crossings per km of road, with a dashed line for the
// Singapore average. Each row has its own scale, so the two are read separately.
function areaChart() {
    var n = AREA_STATS.rows.length, labelW = 150, colW = 96, barW = 34, w = labelW + n * colW;
    var top1 = 20, h1 = 46, top2 = top1 + h1 + 30, h2 = 50, nameY = top2 + h2 + 18, h = nameY + 6;
    var avg = AREA_STATS.national.crossings_per_km, avgY = top2 + h2 - avg / 10 * h2;
    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" style="font-size:12px">' +
        '<text x="0" y="' + (top1 + h1 / 2) + '" fill="#c9ced6">Reported cases</text>' +
        '<text x="0" y="' + (top2 + h2 / 2 - 7) + '" fill="#c9ced6">Crossings per km</text>' +
        '<text x="0" y="' + (top2 + h2 / 2 + 9) + '" fill="#c9ced6">of road</text>' +
        '<line x1="' + labelW + '" y1="' + avgY + '" x2="' + w + '" y2="' + avgY + '" stroke="#fafafa" stroke-dasharray="4 3"/>' +
        '<line x1="0" y1="' + (top2 + h2 / 2 + 26) + '" x2="22" y2="' + (top2 + h2 / 2 + 26) + '" stroke="#fafafa" stroke-dasharray="4 3"/>' +
        '<text x="28" y="' + (top2 + h2 / 2 + 30) + '" fill="#fafafa">Singapore ' + avg + '</text>';
    AREA_STATS.rows.forEach(function (r, i) {
        var cx = labelW + i * colW + colW / 2, bold = r.name === 'River Valley' ? ' font-weight="700"' : '';
        var c1 = r.cases / 5 * h1, c2 = Math.min(r.crossings_per_km, 10) / 10 * h2;
        svg += '<rect x="' + (cx - barW / 2) + '" y="' + (top1 + h1 - c1) + '" width="' + barW + '" height="' + c1 + '" fill="' + SITE.caseColor + '"/>' +
            '<text x="' + cx + '" y="' + (top1 + h1 - c1 - 4) + '" fill="#fafafa" text-anchor="middle">' + r.cases + '</text>' +
            '<rect x="' + (cx - barW / 2) + '" y="' + (top2 + h2 - c2) + '" width="' + barW + '" height="' + c2 + '" fill="' + SITE.markerColors.crossing + '"/>' +
            '<text x="' + cx + '" y="' + (top2 + h2 - c2 - 4) + '" fill="#fafafa" text-anchor="middle">' + r.crossings_per_km.toFixed(1) + '</text>' +
            '<text x="' + cx + '" y="' + nameY + '" fill="#fafafa" text-anchor="middle"' + bold + '>' + r.name + '</text>';
    });
    return svg + '</svg>';
}

// Google Maps Street View at Institution Hill. Paste the src of the embed code from Google Maps
// (Street View > Share > Embed a map). Leave empty to hide the view.
var STREETVIEW_RIVER_VALLEY = '';
function streetView(src) {
    return src ? '<iframe class="streetview" src="' + src + '" loading="lazy" allowfullscreen referrerpolicy="no-referrer-when-downgrade"></iframe>' : '';
}

var config = {
    style: SITE.mapStyle,
    accessToken: SITE.mapboxToken,
    showMarkers: false,
    markerColor: '#3FB1CE',
    inset: false,
    theme: 'dark',
    use3dTerrain: false,
    auto: false,
    title: '',
    subtitle: '',
    byline: '',
    footer: 'DEP5118 Community Data Gathering and Visualization, National University of Singapore. Created using the <a href="https://github.com/mapbox/storytelling" target="_blank">Mapbox Storytelling</a> template.',
    chapters: [
        {
            id: 'crossings',
            alignment: 'left',
            hidden: false,
            title: 'Crossings in Singapore',
            description:
                'LTA records 9,702 road crossings and 771 overhead bridges and underpasses across Singapore. ' +
                'This story looks at reported pedestrian deaths, at how well crossings are provided where they happen, at one case in River Valley, and at the walking detours of HDB residents.<br><br>' +
                '<span class="dot" style="background:' + SITE.markerColors.crossing + '"></span> road crossing &nbsp; ' +
                '<span class="dot" style="background:' + SITE.markerColors.overhead_bridge + '"></span> overhead bridge &nbsp; ' +
                '<span class="dot" style="background:' + SITE.markerColors.underpass + '"></span> underpass<br>' +
                '<span class="dot" style="background:' + SITE.markerColors.bus + '"></span> bus stop &nbsp; ' +
                '<span class="dot" style="background:' + SITE.markerColors.mrt + '"></span> MRT exit',
            location: { center: [103.815, 1.352], zoom: 11.2, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'ctx-bus': 0.7, 'ctx-crossings': 0.9, 'ctx-mrt': 1 }),
            onChapterExit: []
        },
        {
            id: 'cases',
            alignment: 'left',
            hidden: false,
            title: 'Reported fatal cases, 2017 to 2024',
            description:
                'News and court reports describe five fatal cases in which a pedestrian was hit while crossing away from a crossing or against the signal. ' +
                'Official statistics count these cases but do not record where they happen, so news reports are the only public source of locations.<br><br>' +
                'Two of the five cases happened at signalised crossings. Each point marks the road or junction named in the report, not the exact spot.',
            location: { center: [103.815, 1.322], zoom: 11.2, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'ctx-bus': 0.25, 'ctx-crossings': 0.3, 'ctx-mrt': 0.35, cases: 1 }),
            onChapterExit: []
        },
        {
            id: 'by-area',
            alignment: 'full',
            hidden: false,
            title: 'Fatal cases and crossing provision',
            description:
                '<div class="strip"><div class="strip-text">' +
                'All 32 cases in the news sample are grouped by URA planning area (map). The chart shows the areas with a fatal case. ' +
                'Crossing provision is the number of road crossings, overhead bridges and underpasses per km of road, from LTA DataMall, with expressways excluded.<br><br>' +
                'Bukit Batok has the most cases but more crossings than the Singapore average. River Valley and Novena, each with a fatal case, have the fewest.' +
                '<br><small>News reports favour filmed and widely shared incidents, so the counts are small and not a measure of risk.</small>' +
                '</div><div class="strip-chart">' + areaChart() + '</div></div>',
            location: { center: [103.83, 1.35], zoom: 11.1, pitch: 0, bearing: 0, padding: PAD_STRIP },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'area-fill': 0.75, 'area-line': 0.6, 'all-cases': 1, 'ctx-crossings': 0.25 }),
            onChapterExit: []
        },
        {
            id: 'river-valley',
            alignment: 'left',
            hidden: false,
            title: 'A fatal case in River Valley',
            description:
                'In January 2024, a four-year-old girl was hit by a car while being walked across Institution Hill, a two-lane road off River Valley Road, ' +
                'between parked cars. A coroner\'s inquiry heard that the nearest pedestrian crossing was about 200 m away, and that crossing at this point ' +
                'was the usual route from the preschool.<br><br>' +
                'Within 300 m of the case (dashed circle) there are 7 road crossings and no overhead bridge or underpass, ' +
                '2.2 crossings per km of road against 3.8 across Singapore. Roads are coloured by the distance to the nearest crossing.<br><br>' +
                '<span class="key" style="background:' + SITE.classColors[0] + '"></span> under 50 m &nbsp; <span class="key" style="background:' + SITE.classColors[1] + '"></span> 50 to 100 m &nbsp; ' +
                '<span class="key" style="background:' + SITE.classColors[2] + '"></span> 100 to 200 m &nbsp; <span class="key" style="background:' + SITE.classColors[3] + '"></span> over 200 m' +
                streetView(STREETVIEW_RIVER_VALLEY) +
                '<br><a href="https://www.asiaone.com/singapore/maid-jaywalked-4-year-old-girl-who-was-killed-river-valley-accident-traffic-police" target="_blank">Source: AsiaOne, 26 June 2024</a>',
            location: { center: [103.8400, 1.2952], zoom: 16.2, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'rv-buffer-fill': 0.12, 'rv-buffer-line': 1, 'rv-gap': 1, 'rv-markers': 1, 'rv-case': 1 }),
            onChapterExit: []
        },
        {
            id: 'detour',
            alignment: 'left',
            hidden: false,
            title: 'Walking detours of HDB residents',
            description:
                'Where crossings are not on the way, walks get longer. Each dot is an HDB block, coloured by how much longer the walk to bus stops ' +
                'and MRT exits within 500 m is than the straight line. A ratio of 2.0 means twice as far.<br><br>' +
                '<span class="dot" style="background:' + SITE.classColors[0] + '"></span> under 1.5 &nbsp; <span class="dot" style="background:' + SITE.classColors[1] + '"></span> 1.5 to 2.0 &nbsp; ' +
                '<span class="dot" style="background:' + SITE.classColors[2] + '"></span> 2.0 to 2.5 &nbsp; <span class="dot" style="background:' + SITE.classColors[3] + '"></span> over 2.5' + '<br><br>' +
                'The mean ratio across all HDB blocks is 1.9. Walking distances are shortest paths on the OpenStreetMap network.<br><br>' +
                '<a href="../map.html?layer=detour" target="_top">Look up a block on the map</a>',
            location: { center: [103.815, 1.352], zoom: 11.2, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'detour-blocks': 1 }),
            onChapterExit: []
        },
        {
            id: 'voices',
            alignment: 'left',
            // Set to false once there are approved experiences to show
            hidden: true,
            title: 'Experiences from residents',
            description: 'Short accounts shared through the proposal form. Each one is reviewed by the team and placed on the nearest road segment, never at a home address.',
            location: { center: [103.82, 1.355], zoom: 11, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({}),
            onChapterExit: []
        },
        {
            id: 'propose',
            alignment: 'center',
            hidden: false,
            title: 'Propose a crossing',
            description:
                'Mark two points on opposite sides of a road and choose the type of crossing that would help. Each proposal appears on the map as soon as it is sent.' +
                '<p class="buttons"><a class="btn" href="../propose.html" target="_top">Propose a crossing</a> <a class="btn btn-light" href="../map.html" target="_top">Explore the map</a></p>',
            location: { center: [103.82, 1.355], zoom: 10.8, pitch: 0, bearing: 0, padding: PAD_NONE },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ proposals: 1 }),
            onChapterExit: []
        }
    ]
};
