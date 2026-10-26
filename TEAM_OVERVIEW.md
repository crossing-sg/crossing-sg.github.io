# Team overview for discussion (26 Oct 2026)

Project: Where residents want to cross the road. Final presentation due 10 Nov 2026.

## 1. What exists now

| Item | Location | Status |
|---|---|---|
| Website (5 pages) | `website/` | Built. Maps not yet tested because the Mapbox token is missing |
| Wireframes (13 desktop frames) | `website-plan/wireframes/` | Updated to the current design. Drag the SVG files into Figma |
| Story chapter plan | `website-plan/storymap_plan.md` | Updated to Bukit Batok |
| Story previews | `website-plan/story-previews/` | PNG previews of steps 1 to 3 |
| Incident data, corrected | `jaywalking_incidents_sg_v2.geojson` | V24 moved to its source location (about 550 m) |
| Data scripts | `website-plan/make_*.py` | Rebuild site data, story data and wireframes |

## 2. Site map

| Page | Content |
|---|---|
| Home | Hero photo, 3 summary cards, then a scrolling story in 5 steps |
| Map | One layer at a time (crossing gap, walking detour, resident proposals), reference points, address search with OneMap, block routes on click, proposal card with a support button |
| Propose | Two-point form (point A and point B across a road), crossing type, reason, optional experience text, thank-you screen with progress towards 3 proposals |
| Methodology | Data sources, methods, moderation and privacy, limits, downloads |
| About | Team, course, management plan |
| Review (team only) | Google Sheet with a status column |

## 3. Decisions made

1. Backend is Google Sheets with Google Apps Script. Proposals are counted at once (post-moderation). Experience texts appear only after approval (pre-moderation).
2. A road segment appears on the public map only after 3 proposals. Each segment shows one representative crossing line from the mean of the submitted points. Individual points are never published.
3. Support (one click) is counted separately and does not affect the 3-proposal threshold. One support per segment per browser.
4. The Home story uses Bukit Batok because it has the most reported cases in the news sample (5 of 32, of which 3 fatal). The story does not claim that crossings are missing there, because 4 of the 5 cases are within 20 m of a crossing. It shows that blocks next to existing crossings still face long walks.
5. Public text does not use the word "jaywalking".
6. Page structure and base CSS follow the Week 1, 3 and 5 lab examples. Additions are marked "Added for this project" in the code.

## 4. Checks done

| Check | Result |
|---|---|
| Blk 121 to bus stop Opp Blk 120 (story example) | Google Maps 550 m, OSM network 548 m. Confirmed |
| Blk 122 to Bt Batok Polyclinic (candidate) | Google Maps 270 m, OSM network 764 m. Rejected. Shows that some OSM detour ratios are overstated |
| Tengah Boulevard (first gap candidate) | 32 crossings in OSM but none in LTA. Rejected. Shows that LTA crossing data is incomplete in new towns |
| Incident locations against named roads | 31 of 32 consistent with the source text. V24 corrected |

## 5. Open questions

For the team
1. Is the Bukit Batok story acceptable, including the wording of step 1 and step 2?
2. Who prepares the hero photo credit, the README and the GitHub repository?
3. Who promotes the form (classmates, residents' networks, QR posters), and from which date?

For the lecturer
1. Is an external backend (Google Sheets and Apps Script) acceptable?
2. Are the changes from the proposal acceptable (Home story with reported cases and Bukit Batok, review queue in Google Sheets)?
3. Should the OSM detour ratios be validated against OneMap on a sample, given the polyclinic case?

## 6. Next steps

| Step | Who | Needed for |
|---|---|---|
| Create a Mapbox account and add the public token to `website/js/site-config.js` | | Testing all maps |
| Create a shared Google account and an empty Google Sheet | | Apps Script and the form |
| Write and deploy the Apps Script, connect the form | | Live proposals |
| Test all pages with Live Server | | Before publishing |
| Publish on GitHub Pages and write the README | | Course requirement |
| Collect proposals (at least 3 per segment to show) | | Proposal map and final presentation |
| Optional: validate a sample of detour pairs with OneMap (needs a new token) | | Methodology limits |
