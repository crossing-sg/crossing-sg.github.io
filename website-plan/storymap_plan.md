# Home story: chapter plan (draft for team discussion)

Built on the Mapbox Storytelling template from the Week 3 and Week 4 labs (`mapbox/index.html` + `mapbox/config.js`).
Data files are in `story-data/` (copied to `website/data/story/`), previews in `story-previews/`.

## Why Bukit Batok

The example location follows the accident data. Bukit Batok has the most reported cases in the news sample (5 of 32, of which 3 fatal). Novena has more verified cases (4 against 3), but Novena has few HDB blocks, and the detour data covers HDB blocks only.

The data does not show Bukit Batok as a crossing gap hotspot. Four of its five cases are within 20 m of an existing crossing, 20% of its road length is more than 200 m from a crossing (33% for Singapore), and its mean detour ratio is 1.86 (1.92 for Singapore). The story therefore does not claim that crossings are missing there. It shows that crossings exist at junctions while blocks next to them still face long walks, which matches the form reasons "existing crossing is not on the way" and "stairs at the overhead bridge".

## Chapters

| Step | Title (public text) | Map content | Camera (lon, lat, zoom) |
|---|---|---|---|
| Hero | Where residents want to cross the road | Photo, title, buttons, 3 summary cards | none |
| 0 | Crossings in Singapore | Island, no data layer | 103.82, 1.355, 10.6 |
| 1 | Reported fatal cases, 2017 to 2024 | 5 fatal cases island-wide (`step1_reported_cases`) | 103.815, 1.322, 11.3 |
| 2 | Reported cases in Bukit Batok | 5 Bukit Batok cases (filled verified, outlined indicative), distance to nearest crossing, crossing markers (`step2_*`) | 103.7478, 1.3575, 13.9 |
| 3 | Walking distance from Blk 121 Bukit Batok Central | Blk 121, walking route and straight line to bus stop 43399, other routes faint (`step3_*`) | 103.7479, 1.3510, 16.4 |
| 4 | Experiences from residents | Hidden until approved experiences exist | 103.82, 1.355, 11 |
| 5 | Propose a crossing | Proposal segments with 3 or more proposals (live) | 103.82, 1.355, 10.8 |

## Figures used in the text

- 9,702 road crossings and 771 overhead bridges and underpasses (LTA DataMall, September 2026).
- Fatal cases V01 (2017), V10 (2020), V13 (2022), V15 (2024), V17 (2024). V10 and V13 happened at signalised crossings.
- Bukit Batok cases V01, V26, V27 (verified) and I01, I02 (indicative). Distance from each case to the nearest crossing is 16, 5, 14, 90 and 14 m. Cases are placed at the junction named in the report, so these distances partly reflect how the points were placed.
- Blk 121 (postal 650121) is 84 m from V01. Bus stop 43399 "Opp Blk 120" on Bukit Batok Central is 96 m away in a straight line and 548 m on foot (ratio 5.73). Mean ratio of Blk 121 is 2.90 over 13 bus stops and 4 MRT exits.

## Writing style for the story text

Titles describe the content and avoid hook phrasing. Sentences state what the data shows, with the number and its source. No figurative language, no first-person pronouns, no em dashes, and no use of the word "jaywalking".

## Items to verify before publishing

1. Checked 26 Oct 2026. Google Maps gives 550 m (7 min) from Blk 121 to bus stop 43399, crossing Bukit Batok Central at the signalised junction. This matches the 548 m from the OSM network.
2. Rejected 26 Oct 2026. Blk 122 to bus stop 43401 "Bt Batok Polyclinic" is 764 m on the OSM network but 270 m in Google Maps. The OSM network misses a path here, which shows that some detour ratios are overstated. This supports listing the OSM network as a limit and validating a sample of pairs against OneMap.
3. Incident V24 sits about 550 m from the location given by its source and should be moved to bus stop 50251 before any use. It is outside Bukit Batok and not fatal, so it does not affect the story.

## Files

- `make_story_data.py` rebuilds `story-data/` and `story-previews/`.
- `make_wireframes.py` rebuilds `wireframes/` (desktop frames, SVG, importable into Figma). The wireframe text still describes the earlier Boon Lay Way example.
