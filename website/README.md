# Where residents want to cross the road

DEP5118 Community Data Gathering and Visualization, NUS (Gangsar Dwi Saputro, Xia Ruize, Yuan Zhiyi).

## Structure (follows the Week 5 lab website)

| File | Page |
|---|---|
| `index.html` | Home. Embeds the story in `mapbox/` with an iframe |
| `mapbox/index.html`, `mapbox/config.js` | Mapbox Storytelling template. Chapters are in `config.js`, layers in `story-layers.js` |
| `map.html`, `js/explore.js` | Explore map (crossing gap, walking detour, resident proposals) |
| `propose.html`, `js/propose.js` | Proposal form and thank-you screen |
| `methodology.html`, `about.html` | Text pages |
| `css/style.css` | Shared style |
| `js/site-config.js` | Mapbox token, Apps Script URL and colours |
| `data/` | Processed GeoJSON. `data/routes/<postal>.json` holds the routes of one block |

## Before it works

1. Put a public Mapbox token (`pk.`) in `js/site-config.js`.
2. Deploy the Google Apps Script web app and put its `/exec` URL in `js/site-config.js`. Until then the form shows a "not connected" message and the proposal layer is empty.
3. Open with VS Code Live Server (as in the Week 7 lab), not by double-clicking the file, because the maps load GeoJSON with `fetch`.

## Rebuilding the data

Scripts in `../website-plan/`: `make_site_data.py` builds `data/`, `make_story_data.py` builds `data/story/` (copy from `website-plan/story-data`).
