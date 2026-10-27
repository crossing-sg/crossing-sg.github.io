// Story chapters for the Home page. Layer names come from story-layers.js.
// Each chapter sets the opacity of every story layer when it is entered, so the result
// does not depend on the order in which scrollama fires enter and exit events.
var STORY_LAYERS = ['cases', 'area-cases', 'gap', 'markers', 'block', 'routes-other', 'route-walk', 'route-straight', 'stops', 'proposals'];
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
                'This story looks at reported pedestrian deaths, then at one town, Bukit Batok, and at the walk from one block to its nearest bus stop.',
            location: { center: [103.82, 1.355], zoom: 10.6, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({}),
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
            onChapterEnter: only({ cases: 1 }),
            onChapterExit: []
        },
        {
            id: 'bukit-batok',
            alignment: 'left',
            hidden: false,
            title: 'Reported cases in Bukit Batok',
            description:
                'Bukit Batok has the most reported cases in the news sample, five in total, of which three were fatal. ' +
                'Solid red triangles are cases confirmed by the source. Outlined triangles are cases where the source does not confirm how the pedestrian crossed.<br><br>' +
                'Four of the five cases are within 20 m of an existing crossing. Roads are coloured by the distance to the nearest crossing, overhead bridge or underpass.<br><br>' +
                '<span class="key" style="background:' + SITE.classColors[0] + '"></span> under 50 m &nbsp; <span class="key" style="background:' + SITE.classColors[1] + '"></span> 50 to 100 m &nbsp; ' +
                '<span class="key" style="background:' + SITE.classColors[2] + '"></span> 100 to 200 m &nbsp; <span class="key" style="background:' + SITE.classColors[3] + '"></span> over 200 m<br><br>' +
                'In Bukit Batok, 20% of road length is more than 200 m from a crossing, compared with 33% across Singapore.<br><br>' +
                '<a href="../map.html?layer=gap" target="_top">See all roads on the map</a>',
            location: { center: [103.7478, 1.3575], zoom: 13.9, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ gap: 1, markers: 1, 'area-cases': 1 }),
            onChapterExit: []
        },
        {
            id: 'detour',
            alignment: 'left',
            hidden: false,
            title: 'Walking distance from Blk 121 Bukit Batok Central',
            description:
                'Blk 121 (blue) is 84 m from case V01 on Bukit Batok Central. The bus stop opposite Blk 120 is 96 m from the block in a straight line (grey dashed line). ' +
                'The shortest walking route on the pedestrian network (white line) is 548 m, 5.7 times the straight distance.<br><br>' +
                'Across the 17 bus stops and MRT exits within 500 m, the mean detour ratio of Blk 121 is 2.9. The mean for all HDB blocks in Singapore is 1.9.<br><br>' +
                '<a href="../map.html?layer=detour&block=650121" target="_top">Look up another block</a>',
            location: { center: [103.7479, 1.3510], zoom: 16.8, pitch: 0, bearing: 0, padding: PAD_LEFT },
            mapAnimation: 'flyTo',
            rotateAnimation: false,
            callback: '',
            onChapterEnter: only({ gap: 0.25, block: 1, 'routes-other': 0.3, 'route-walk': 1, 'route-straight': 1, stops: 1, 'area-cases': 1 }),
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
                'Mark two points on opposite sides of a road and choose the type of crossing that would help. A road segment is shown on the map once it has three proposals.' +
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
