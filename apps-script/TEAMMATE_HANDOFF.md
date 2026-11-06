# Multi-road Crossing handoff for the Apps Script owner

The GitHub integration stages the new code and the 242,112-segment road and validation assets. The site continues to use the existing pilot endpoint and BBBike registry until a separate cutover. This handoff covers the owner’s work for that cutover. See the [release runbook](RELEASE_MULTI_ROAD.md) for the full procedure and integrity hashes.

## What changes

A resident still marks A and B and submits one Proposal. The new backend recomputes which motorable roads were crossed, stores one request with a link to each road, and handles retries without duplicating those links. Unknown grade remains unvalidated and requires actual evidence before approval. Explore counts each Proposal once overall and once per associated road. A road needs three eligible approved Proposals to appear.

| Sheet tab | Existing pilot source | Successor schema |
| --- | --- | --- |
| `proposals` | 14 columns. Each row has one `seg_id`. | 26 columns. Each row is one Proposal with its original or new `request_id`, registry and schema versions, moderation and validation status, and crossing groups. A multi-road Proposal leaves the legacy scalar `seg_id` blank. |
| `proposal_segments` | Absent | 5 columns. One row per unique `(request_id, seg_id)`, with crossing group indexes and registry and schema versions. |
| `support` | 4 columns | Same 4 columns. Support votes remain separate from Proposals. |

## Prepare the successor

1. Use a **separate Apps Script project and private successor spreadsheet** for this rollout. The pilot writes by column position and its header order differs. Pointing it at a restructured live Sheet would risk putting new values in the wrong columns.
2. Back up the live Sheet, the pilot script source and deployment version, and the last working website commit. Inspect the actual Sheet headers on the backup. Use the successor for the import and keep the live Sheet as the source and rollback copy.
3. Upload these five files from the merged repository’s `apps-script/` directory: `Code.gs`, `MultiRoad.gs`, `RegistryConfig.gs`, `RoadGeometry.gs`, and `ValidationConfig.gs`. The `pilot/` directory and Phase 3A TEST helpers are separate.
4. In the new project, use V8 and the `Asia/Singapore` time zone. In **Project Settings**, show `appsscript.json` and set `oauthScopes` to `https://www.googleapis.com/auth/spreadsheets` and `https://www.googleapis.com/auth/script.external_request`. Under **Script Properties**, set the following values. The deploying owner needs edit access to the successor Sheet.

   | Property | Value |
   | --- | --- |
   | `PROPOSAL_SPREADSHEET_ID` | The approved successor Sheet ID, entered privately by the owner |
   | `PROPOSAL_DATA_BASE_URL` | `https://crossing-sg.github.io/data/pbf-motorable-v1/proposal-roads` |
   | `PROPOSAL_VALIDATION_BASE_URL` | `https://crossing-sg.github.io/data/pbf-motorable-v1/selection-validation` |
   | `ENABLE_MULTI_ROAD` | `false` during setup |

5. Verify the target Sheet, select `setup` in the Apps Script editor and click **Run**. Review and grant Sheets and external request permissions with the owner account. Confirm the three tabs and their column counts. Copy historical Proposal and support values by **matching header names**, preserving row order, IDs, versions, dates, coordinates and statuses. Import text as literal values and leave fields absent from the source blank. Check mapped values and row counts against the backup. Old pilot `status=ok` alone is insufficient for publication. Review retired and incompatible road references privately, retaining the original rows and IDs. Keep unresolved associations out of public totals.

## Coordinate deployment and cutover

1. Schedule an approved pilot write freeze and final data transfer. Have the owner prepare and review a pilot version that pauses POST while preserving GET, using the existing lock to drain in-flight writes. Record the previous version, transfer the final delta under the freeze and verify row counts and request IDs. The pilot and successor should serve separate Sheets throughout.
2. After approval for public access, choose **Deploy → New deployment → Web app**, set **Execute as Me** and **Who has access Anyone** including signed-out visitors, then deploy a version. Set `ENABLE_MULTI_ROAD=true` on the successor after its data and moderation gates pass. Confirm signed-out `?view=capabilities`, `?view=segments` and `?view=summary` from the intended website origin, including the pinned versions, `multi_road:true`, JSON after redirects, and exclusion of unvalidated records. Verify the browser’s cross-origin `text/plain` POST path against an approved isolated deployment with the same access settings. The earlier Google TEST used owner authorization.
3. Give the GitHub maintainer the approved new **public `/exec` URL**, deployment version, and confirmation of the history checks, asset pins, and signed-out GET and POST checks. Share backup references and cutover timing with the owner through the team’s private channel.
4. The GitHub maintainer updates `proposalApiUrl`, `proposalNetworkVersion`, `proposalRoadsBase`, and `proposalValidationBase` in one cutover commit and bumps the Proposal and Explore config cache keys. Keep `appsScriptUrl` for legacy reads. Merge the cutover commit, wait for Pages, then verify Proposal and Explore using the new endpoint. The exact values are in [section 4 of the release runbook](RELEASE_MULTI_ROAD.md#4-publish-the-site-configuration-together).

## Rollback

For an array-only fault, set `ENABLE_MULTI_ROAD=false` on the successor. For a full rollback, coordinate reverting the GitHub cutover commit with restoring the pilot’s recorded write-enabled version. Retain the successor Sheet, all rows and links, and both registry releases. Restrict successor access if cached clients keep writing after the switch, then reconcile writes during the rollback window by original request ID before resuming. [Detailed rollback procedure](RELEASE_MULTI_ROAD.md#rollback)
