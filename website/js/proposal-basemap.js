/* Proposal-only imagery adjustment. Never filter the map canvas or vector labels.
 * Matches satellite_color_preview.html: n = brightness / 100;
 * brightness min = Math.max(0, n); max = Math.min(1, 1 + n).
 */
var ProposalBasemap = (function () {
    'use strict';
    var brightness = -50 / 100;
    var paint = {
        'raster-saturation': -0.25,
        'raster-hue-rotate': 40,
        'raster-contrast': -0.30,
        'raster-brightness-min': Math.max(0, brightness),
        'raster-brightness-max': Math.min(1, 1 + brightness)
    };
    function apply(map) {
        var style = map.getStyle();
        if (!style) { return; }
        (style.layers || []).filter(function (layer) { return layer.type === 'raster'; }).forEach(function (layer) {
            Object.keys(paint).forEach(function (property) { map.setPaintProperty(layer.id, property, paint[property]); });
        });
    }
    return { apply: apply };
}());
if (typeof module !== 'undefined' && module.exports) { module.exports = ProposalBasemap; }
