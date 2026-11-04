// Story chapters for the Home page. Layer names come from story-layers.js.
// Each chapter sets the opacity of every story layer when it is entered, so the result
// does not depend on the order in which scrollama fires enter and exit events.
var STORY_LAYERS = ['ctx-bus', 'ctx-crossings', 'ctx-mrt', 'area-fill', 'area-line', 'all-cases', 'cases',
    'ex-buffer-fill', 'ex-buffer-line', 'ex-gap', 'ex-markers', 'ex-case', 'detour-blocks', 'block', 'routes-other', 'route-walk', 'route-straight', 'stops', 'proposals'];
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
// The first three chapters share one camera, so only the data layers change between them.
// The lower 30% of the screen is kept for the infographic strip, and the left for the story card.
var PAD_SG = { top: 40, bottom: Math.round(window.innerHeight * 0.3), left: 20, right: 20 };
var LOC_SG = { center: [103.84, 1.38], zoom: 10.6, pitch: 0, bearing: 0, padding: PAD_SG };
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
    PAD_SG.left = wide ? PAD_LEFT.left : 0;
    PAD_SG.bottom = wide ? Math.round(window.innerHeight * 0.3) : 0;
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

// Horizontal bar chart drawn as inline SVG, one bar per area. avg adds a dashed line for the
// Singapore average.
function barChart(key, max, color, avg) {
    var rowH = 24, labelW = 92, barMax = 220, w = labelW + barMax + 36;
    var h = AREA_STATS.rows.length * rowH + (avg ? 18 : 2);
    var svg = '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" style="font-size:12px">';
    AREA_STATS.rows.forEach(function (r, i) {
        var y = i * rowH, v = r[key], bw = v / max * barMax, bold = r.name === 'Bukit Batok' ? ' font-weight="700"' : '';
        svg += '<text x="' + (labelW - 8) + '" y="' + (y + 15) + '" fill="#fafafa" text-anchor="end"' + bold + '>' + r.name + '</text>' +
            '<rect x="' + labelW + '" y="' + (y + 4) + '" width="' + bw + '" height="15" fill="' + color + '"/>' +
            '<text x="' + (labelW + bw + 5) + '" y="' + (y + 15) + '" fill="#fafafa">' + (key === 'cases' ? v : v.toFixed(1)) + '</text>';
    });
    if (avg) {
        var x = labelW + avg / max * barMax, yb = AREA_STATS.rows.length * rowH;
        svg += '<line x1="' + x + '" y1="0" x2="' + x + '" y2="' + yb + '" stroke="#fafafa" stroke-dasharray="4 3"/>' +
            '<text x="' + x + '" y="' + (yb + 14) + '" fill="#c9ced6" text-anchor="middle">Singapore ' + avg + '</text>';
    }
    return svg + '</svg>';
}

// News screenshots for the cases chapter, saved in ../img/news/. A missing file is hidden.
var NEWS = [
    { file: 'asiaone-river-valley.png', source: 'AsiaOne, 2024', url: 'https://www.asiaone.com/singapore/maid-jaywalked-4-year-old-girl-who-was-killed-river-valley-accident-traffic-police' },
    { file: 'malaymail-bukit-batok.png', source: 'Malay Mail, 2018', url: 'https://www.malaymail.com/news/world/2018/12/07/singaporean-jailed-six-weeks-for-causing-death-of-4-year-old-girl/1700941' },
    { file: 'mustsharenews-queensway.png', source: 'MustShareNews', url: 'https://mustsharenews.com/driver-jailed-jaywalker-queensway/' },
    { file: 'mothership-sims-ave.png', source: 'Mothership, 2023', url: 'https://mothership.sg/2023/04/cross-road-look-phone-death/' },
    { file: 'independent-bukit-batok.png', source: 'The Independent SG, 2020', url: 'https://theindependent.sg/elderly-man-dies-after-being-knocked-down-while-crossing-road-in-bukit-batok/' },
    { file: 'mothership-balestier.png', source: 'Mothership, 2025', url: 'https://mothership.sg/2025/08/woman-jaywalk-balestier-road/' }
];
function newsGallery() {
    return '<div class="news">' + NEWS.map(function (n) {
        return '<a href="' + n.url + '" target="_blank"><img src="../img/news/' + n.file + '" alt="' + n.source + '" onerror="this.parentNode.remove()"><span>' + n.source + '</span></a>';
    }).join('') + '</div>';
}

// Google Maps Street View at the bus stop opposite Blk 121. Paste the src of the embed code from Google Maps
// (Street View > Share > Embed a map). Leave empty to hide the view.
var STREETVIEW_BLK121 = 'https://www.google.com/maps/embed?pb=!4v1793753645399!6m8!1m7!1stRK7nQzHugoyyj7BWKnS0g!2m2!1d1.350669687478743!2d103.7480470536054!3f0!4f0!5f0.4000000000000002';
function streetView(src) {
    return src ? '<iframe class="streetview" src="' + src + '" loading="lazy" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>' : '';
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
                'This story looks at reported pedestrian deaths, at how well crossings are provided where they happen, at one case in Bukit Batok, and at the walking detours of HDB residents.<br><br>' +
                '<span class="dot" style="background:' + SITE.markerColors.crossing + '"></span> road crossing &nbsp; ' +
                '<span class="dot" style="background:' + SITE.markerColors.overhead_bridge + '"></span> overhead bridge &nbsp; ' +
                '<span class="dot" style="background:' + SITE.markerColors.underpass + '"></span> underpass<br>' +
                '<span class="dot" style="background:' + SITE.markerColors.bus + '"></span> bus stop &nbsp; ' +
                '<span class="dot" style="background:' + SITE.markerColors.mrt + '"></span> MRT exit',
            location: LOC_SG,
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
            title: 'Reported cases, 2017 to 2026',
            description:
                'News and court reports describe 32 cases in which a pedestrian was hit while crossing away from a crossing or against the signal. Seven were fatal (large points).<br><br>' +
                newsGallery() +
                '<small>Official statistics do not record where these cases happen, so news reports are the only public source of locations. Each point marks the road named in the report. Hollow points are approximate.</small>',
            location: LOC_SG,
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'ctx-crossings': 0.3, 'all-cases': 1 }),
            onChapterExit: []
        },
        {
            id: 'by-area',
            alignment: 'full',
            hidden: false,
            title: 'Fatal cases and crossing provision',
            description:
                '<p>Do the cases fall where crossings are few? Areas with a fatal case, compared.</p><div class="strip">' +
                '<div><h4>Reported cases</h4>' + barChart('cases', 5, SITE.caseColor) +
                '<p>Bukit Batok and Novena have the most cases in the news sample.</p></div>' +
                '<div><h4>Crossings per km of road</h4>' + barChart('crossings_per_km', 6, SITE.markerColors.crossing, AREA_STATS.national.crossings_per_km) +
                '<p>River Valley and Novena have the fewest, below the Singapore average.</p></div>' +
                '</div><small>Areas with a fatal case. Crossings include bridges and underpasses (LTA DataMall). News counts are small and not a measure of risk.</small>',
            location: LOC_SG,
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'area-fill': 0.75, 'area-line': 0.6, 'all-cases': 1, 'ctx-crossings': 0.25 }),
            onChapterExit: []
        },
        {
            id: 'bukit-batok-case',
            alignment: 'left',
            hidden: false,
            title: 'A fatal case in Bukit Batok',
            description:
                'In October 2017, a four-year-old girl was hit by a car while her caregiver crossed Bukit Batok Central with her. ' +
                'The court heard that they crossed the road instead of using the overhead bridge nearby.<br><br>' +
                'Within 300 m of the case (dashed circle) there are 6 road crossings and 2 overhead bridges or underpasses, 5.2 per km of road against 3.8 across Singapore. ' +
                'Crossings are provided here, so the question is whether they lie on the routes people walk. Roads are coloured by the distance to the nearest crossing.<br><br>' +
                '<span class="key" style="background:' + SITE.classColors[0] + '"></span> under 50 m &nbsp; <span class="key" style="background:' + SITE.classColors[1] + '"></span> 50 to 100 m &nbsp; ' +
                '<span class="key" style="background:' + SITE.classColors[2] + '"></span> 100 to 200 m &nbsp; <span class="key" style="background:' + SITE.classColors[3] + '"></span> over 200 m' +
                '<br><a href="https://www.malaymail.com/news/world/2018/12/07/singaporean-jailed-six-weeks-for-causing-death-of-4-year-old-girl/1700941" target="_blank">Source: Malay Mail, 7 December 2018</a>',
            location: { center: [103.7484, 1.3524], zoom: 16.2, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ 'ex-buffer-fill': 0.12, 'ex-buffer-line': 1, 'ex-gap': 1, 'ex-markers': 1, 'ex-case': 1 }),
            onChapterExit: []
        },
        {
            id: 'bukit-batok',
            alignment: 'left',
            hidden: false,
            title: 'More crossings, longer walks: Blk 121 Bukit Batok',
            description:
                'Bukit Batok has more crossings than the Singapore average but the most reported cases. One reason may be where the crossings are. ' +
                'Blk 121 (blue) is 84 m from the same case. The bus stop opposite is 96 m away in a straight line (dashed), but 548 m on foot (white line).<br><br>' +
                'The mean detour ratio of Blk 121 is 2.9, against 1.9 for all HDB blocks.<br><br>' +
                streetView(STREETVIEW_BLK121) + '<br>' +
                '<a href="../map.html?layer=detour&block=650121" target="_top">Look up another block</a>',
            location: { center: [103.7479, 1.3510], zoom: 16.8, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ block: 1, 'routes-other': 0.7, 'route-walk': 1, 'route-straight': 1, stops: 1, 'all-cases': 1, 'ctx-crossings': 0.6 }),
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
