// Pictogram icons for the reference points: a white symbol on a coloured circle.
// The same SVG is used as a map icon (map.addImage) and as an image in the legend.
var ICON_GLYPHS = {
    'icon-bus': '<rect x="7" y="6" width="10" height="10" rx="2"/><path d="M7 11h10"/><circle cx="9.5" cy="17.5" r="1" fill="#fff"/><circle cx="14.5" cy="17.5" r="1" fill="#fff"/>',
    'icon-mrt': '<rect x="8" y="5" width="8" height="10" rx="2.5"/><path d="M8 10h8"/><path d="M10 15l-2 4M14 15l2 4"/>',
    'icon-crossing': '<path d="M7 7v10M10.3 7v10M13.6 7v10M17 7v10" stroke-width="2.2"/>',
    'icon-bridge': '<path d="M5 10h14M8 10v8M16 10v8M5 14h3M16 14h3"/>',
    'icon-underpass': '<path d="M4 18h16"/><path d="M7 18v-5a5 5 0 0 1 10 0v5"/>'
};

function iconSvg(name, color) {
    return '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24">' +
        '<circle cx="12" cy="12" r="11" fill="' + color + '" stroke="#1B1E23" stroke-width="1"/>' +
        '<g fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
        ICON_GLYPHS[name] + '</g></svg>';
}

function iconUrl(name, color) {
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(iconSvg(name, color));
}

// Adds every icon to the map. Resolves when all images are ready.
function addMapIcons(map, colors) {
    return Promise.all(Object.keys(colors).map(function (name) {
        return new Promise(function (resolve) {
            var img = new Image(48, 48);
            img.onload = function () {
                if (!map.hasImage(name)) { map.addImage(name, img, { pixelRatio: 2 }); }
                resolve();
            };
            img.src = iconUrl(name, colors[name]);
        });
    }));
}
