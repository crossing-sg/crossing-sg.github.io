// Settings shared by every page. Fill these two values in before publishing.
var SITE = {
    // Public Mapbox token (starts with pk.). Restrict it to the GitHub Pages URL in your Mapbox account.
    mapboxToken: 'YOUR_MAPBOX_PUBLIC_TOKEN',
    // Web app URL of the Google Apps Script deployment (ends with /exec). Leave empty until the script is deployed.
    appsScriptUrl: '',
    // Replace with your own Monochrome Dark style from Mapbox Studio (classic template, works with GL JS v2)
    mapStyle: 'mapbox://styles/mapbox/dark-v11',

    // Colours for a dark basemap. Crossing gap and walking detour share one ramp: grey, yellow, orange, red (worse).
    classColors: ['#5C6370', '#F2C94C', '#F2994A', '#EB5757'],
    proposalRamp: ['#6D5BA8', '#9B7FE0', '#D2C3FF'],
    routeWalk: '#FFFFFF',
    routeStraight: '#9CA3AF',
    caseColor: '#E879F9',
    highlight: '#38BDF8',
    basemapDark: '#1B1E23',
    markerColors: { crossing: '#38BDF8', overhead_bridge: '#A78BFA', underpass: '#4ADE80', bus: '#9CA3AF', mrt: '#FFFFFF' }
};
SITE.gapColors = ['step', ['get', 'dist_m'], SITE.classColors[0], 50.0001, SITE.classColors[1], 100.0001, SITE.classColors[2], 200.0001, SITE.classColors[3]];
SITE.detourColors = ['step', ['get', 'mean_detour'], SITE.classColors[0], 1.5, SITE.classColors[1], 2, SITE.classColors[2], 2.5, SITE.classColors[3]];
SITE.proposalColors = ['step', ['get', 'count'], SITE.proposalRamp[0], 5, SITE.proposalRamp[1], 10, SITE.proposalRamp[2]];
