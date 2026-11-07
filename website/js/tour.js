// Guided look at the Explore map. Four short steps, each with one area and one layer,
// so a first-time visitor knows where to look. Links from the story (?layer= or ?block=)
// skip the invitation and open the map as requested.

var TOUR = [
    {
        title: 'Few crossings',
        theme: 'gap',
        view: { center: [103.8355, 1.2935], zoom: 15 },
        text: 'River Valley has 2.2 crossings per km of road, against 3.8 for Singapore as a whole. ' +
            'Orange and red roads are far from the nearest crossing, bridge or underpass. Click a road to see the distance.'
    },
    {
        title: 'Long walking detours',
        theme: 'detour',
        block: '650121',
        view: { center: [103.7479, 1.3510], zoom: 16.5 },
        text: 'Blk 121 in Bukit Batok is 96 m from the bus stop opposite in a straight line, but the walk is 548 m. ' +
            'Each dot is an HDB block. Click another block to see its walking routes.'
    },
    {
        title: 'What residents ask for',
        theme: 'proposals',
        view: { center: [103.843, 1.2918], zoom: 17 },
        text: 'Each line marks a crossing that a resident proposed. This one, at the bus stop opposite UE Square, ' +
            'is 149 m from the nearest crossing. Click the line to see the type of crossing and the reason given.'
    },
    {
        title: 'Your own area',
        theme: 'gap',
        view: { center: [103.82, 1.355], zoom: 11 },
        text: 'Type a block number, road name or postal code in the search box to look at the roads and walks near you. ' +
            'All layers are available in the panel on the left.'
    }
];

var tourStep = -1;

function tourCard() {
    var card = document.getElementById('tour');
    if (!card) {
        card = document.createElement('div');
        card.id = 'tour';
        card.className = 'tour-card';
        document.querySelector('.map-area').appendChild(card);
    }
    return card;
}

function tourInvite() {
    tourStep = -1;
    var card = tourCard();
    card.hidden = false;
    card.innerHTML = '<b>New to this map?</b><p>A short guided look takes four steps and about a minute.</p>' +
        '<div class="tour-buttons"><button class="btn" onclick="tourGo(0)">Start</button>' +
        '<button class="btn btn-light" onclick="tourEnd()">Skip and explore freely</button></div>';
}

function tourGo(i) {
    tourStep = i;
    var s = TOUR[i];
    var radio = document.querySelector('input[name=layer][value=' + s.theme + ']');
    radio.checked = true;
    setTheme(s.theme);
    if (s.block) { openBlock(s.block, false); }
    map.flyTo(Object.assign({ duration: 2500 }, s.view));
    var card = tourCard();
    card.hidden = false;
    card.innerHTML = '<span class="tour-step">Step ' + (i + 1) + ' of ' + TOUR.length + '</span>' +
        '<b>' + s.title + '</b><p>' + s.text + '</p><div class="tour-buttons">' +
        (i > 0 ? '<button class="btn btn-light" onclick="tourGo(' + (i - 1) + ')">Back</button>' : '') +
        (i < TOUR.length - 1 ? '<button class="btn" onclick="tourGo(' + (i + 1) + ')">Next</button>' :
            '<button class="btn" onclick="tourEnd(true)">Start exploring</button>') +
        '<button class="tour-exit" onclick="tourEnd()">Exit tour</button></div>';
    if (i === TOUR.length - 1) { document.getElementById('search').focus(); }
}

function tourEnd(keepView) {
    tourStep = -1;
    tourCard().hidden = true;
    if (!keepView) { map.flyTo({ center: [103.82, 1.355], zoom: 11 }); }
}

document.getElementById('tour-open').addEventListener('click', tourInvite);
map.on('load', function () {
    if (!params.get('layer') && !params.get('block')) { tourInvite(); }
});
