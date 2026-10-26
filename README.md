# Pedestrian Crossing Proposal

**Where residents want to cross the road. Crowdsourced crossing proposals and pedestrian detours in Singapore.**

Final group project for DEP5118 Community Data Gathering and Visualization, Master of Urban Planning, National University of Singapore (2026).
Team: Gangsar Dwi Saputro, Xia Ruize, Yuan Zhiyi.

Website: https://crossing-sg.github.io/
Repository: https://github.com/crossing-sg/crossing-sg.github.io

## About the project

Residents propose where a pedestrian crossing should be by marking two points on opposite sides of a road, choosing a crossing type and giving a reason. Proposals are counted on 50 m road segments and compared with the distance to the nearest existing crossing and with the walking detours of nearby HDB blocks. The aim is evidence for planning, not enforcement.

## Repository structure

| Folder or file | Content |
|---|---|
| `website/` | The published website (HTML, CSS, JavaScript, processed data). See `website/README.md` |
| `website/mapbox/` | Home story, built on the Mapbox Storytelling template used in the course labs |
| `website/data/` | Processed GeoJSON used by the maps. `data/routes/<postal>.json` holds the walking routes of one block |
| `website-plan/` | Data processing scripts, story plan, wireframes (SVG, importable into Figma) and previews |
| `TEAM_OVERVIEW.md` | Current status, decisions and open questions for the team |
| `.github/workflows/pages.yml` | Publishes `website/` to GitHub Pages on every push to `main` |

## Running the website locally

1. Add a public Mapbox token and the map style URL in `website/js/site-config.js`.
2. Open `website/index.html` with the VS Code Live Server extension, as in the Week 7 lab. Opening the file directly does not work, because the maps load data with `fetch`.

## Rebuilding the data

Raw data is not stored in this repository. Download the files listed below into the repository root, then run the scripts in `website-plan/`.

| Script | Output |
|---|---|
| `make_site_data.py` | `website/data/` (crossing gap segments, detour blocks, reference points, routes per block) |
| `make_story_data.py` | `website-plan/story-data/`, copied to `website/data/story/` |
| `make_wireframes.py` | `website-plan/wireframes/` |
| `make_overview_docx.py` | `TEAM_OVERVIEW.docx` from `TEAM_OVERVIEW.md` |

## Data sources and attribution

- Land Transport Authority, LTA DataMall (September 2026). Road Section Line, Road Crossing, Pedestrian Overhead Bridge and Underpass, Bus Stop Location, Train Station Exit.
- Housing and Development Board, HDB Existing Building, data.gov.sg.
- Urban Redevelopment Authority, Master Plan 2019 Planning Area Boundary, data.gov.sg.
- OpenStreetMap contributors, road and footpath network used for walking routes. Data available under the Open Database Licence (ODbL).
- Singapore Land Authority, OneMap Search API, used for address search.
- Singapore Police Force, annual road traffic situation reports, used for summary statistics.
- Hero photo by Myznik Egor on Unsplash, used under the Unsplash License.
- Base maps by Mapbox. Story layout from the Mapbox Storytelling template.

## Work outside the course materials

The proposal form, the explore map and the Google Sheets backend are written for this project, because the course tools (Ushahidi, Weavely) do not support a two-point location per submission. The lecturer allowed exploration beyond the course materials.
