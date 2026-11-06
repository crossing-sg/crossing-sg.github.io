# Production cutover for the PBF network and Multi-road Crossing

The release branch stages the website, Apps Script source and frozen assets. The active site configuration already selects the PBF registry assets but still reads the existing pilot endpoint; the successor v2 API URL remains disabled. GitHub Pages publishes `website/` after a push to `main`. Merge the staging change only when authorized. Schedule activation separately so a new-registry request cannot reach the pilot.

## 1. Stage and verify the assets

After review, merge the staging branch and wait for the **Deploy website to GitHub Pages** workflow for that commit. The expected paths below are relative to the Pages origin. The `.gz` bodies must arrive as raw gzip bytes after any HTTP transport decoding. Verify representative registry blocks, road tiles and validation blocks, and compare the fetched manifest SHA-256 values with these pins. Keep both releases available. [GitHub Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

| Item | Release value |
| --- | --- |
| Network directory | `/data/pbf-motorable-v1/proposal-roads` |
| Network version | `proposal-pbf-france-experimental-3d1457efd477ae74` |
| Network manifest SHA-256 | `ca47962548593fc62f6b9e4157368d00b405f9575319ae9b185f257a3a2fc742` |
| Evidence directory | `/data/pbf-motorable-v1/selection-validation` |
| Evidence version | `multi-road-clean-pbf-validation-v2-324e096056c72f1f` |
| Evidence manifest SHA-256 | `3f057c690653a670e29b62d6d80e8000e96b0c7a9fe04b9a4a4685c94a127e1d` |

The immutable release combines the original LTA network with Singapore motorable roads from the original OSM France PBF snapshot of 2026-11-03 00:15:04 UTC. Supplementary OSM data is attributed to [OpenStreetMap contributors under ODbL](https://www.openstreetmap.org/copyright).

## 2. Prepare the private successor Sheet and migration

1. Save restricted backups of the pilot spreadsheet, its Apps Script source and deployment details, and the last published website SHA. Use a separate private successor Sheet and a separate Apps Script project for the new backend. The old pilot appends by position and is unsafe as a writer to the new schema.
2. Inspect the actual backup headers. The checked-in pilot uses 14 proposal columns, ending with `registry_version, request_id`. The new format expects `schema_version, registry_version, request_id, review_status` after `status`, then the ten validation and membership fields declared in `Code.gs`. Initialize the successor headers with `setup()` as described below. Copy historical values into the successor by matching **header names**, including `support`. Import stored text as literal values and preserve coordinates, dates, IDs, registry versions, review statuses and source row order. Keep columns absent from the old schema blank. Compare the mapped records and counts to the backup before proceeding. Unexpected headers require a reviewed mapping.
3. Keep any legacy status and request ID exactly as stored. Pilot rows with `status=ok` and blank schema/review fields are eligible for publication as previously accepted without another moderation step. New-schema rows still require explicit approval, and rejected or pending pilot records remain excluded. Check historical registry versions and resolve references on a private audit. The candidate preserves 198,104 existing IDs by geometry and retires 88,109 BBBike supplement IDs. Retain unresolved rows in the successor with their original IDs and withhold incompatible associations from public output. Where an older registry used an ID differently, withhold that row pending a reviewed reconciliation. Never infer a replacement ID from name or proximity.
4. Arrange a short, separately approved pilot write freeze for the final transfer. Use a reviewed read-only pilot version that refuses POST after acquiring its existing script lock while continuing to serve GET at the same URL. Record the prior pilot version. Confirm the freeze, capture and compare the final snapshot, transfer the final delta and verify exact rows before routing writes to the successor. Keep the old project and Sheet available for rollback. The pilot GET views continue to serve legacy consumers such as Storytelling. The new Explore page uses the new API after cutover.

## 3. Prepare and activate the new Apps Script deployment

1. In the new project, upload only `Code.gs`, `RegistryConfig.gs`, `RoadGeometry.gs`, `ValidationConfig.gs` and `MultiRoad.gs` from the reviewed commit. Use V8, Asia/Singapore, and the `https://www.googleapis.com/auth/spreadsheets` and `https://www.googleapis.com/auth/script.external_request` scopes. The owner needs edit access to the successor Sheet. Exclude the `pilot/` subdirectory, TEST bootstrap/runner/fixtures, fault injection and local adapters.
2. Under **Project Settings → Script Properties**, set `PROPOSAL_SPREADSHEET_ID` to the private successor Sheet ID, `PROPOSAL_DATA_BASE_URL` and `PROPOSAL_VALIDATION_BASE_URL` to the absolute HTTPS directories in the table, and `ENABLE_MULTI_ROAD` to `false`. Verify the target ID against the approved successor. Run `setup()` from the editor and grant the runtime scopes. Confirm 26 `proposals` columns, 5 `proposal_segments` columns and 4 `support` columns. Finish and verify the history transfer before exposing the new endpoint. The Sheet ID and credentials belong only in private configuration.
3. When public deployment is authorized, use **Deploy → New deployment → Web app**, **Execute as Me**, **Who has access Anyone** including signed-out residents (`USER_DEPLOYING` and `ANYONE_ANONYMOUS` in the manifest). Record the new version and `/exec` URL privately for cutover review. If the account restricts anonymous web apps, stop. Keep the existing pilot deployment and endpoint separate. [Google web app and deployment settings](https://developers.google.com/apps-script/guides/web)
4. Set `ENABLE_MULTI_ROAD=true` on the new project for final capability verification. From a signed-out browser on the intended site origin, verify `?view=capabilities` returns `ok`, the pinned versions/hashes, `multi_road:true` and `multi_schema_version:"proposal-multi-v1"`. Verify `?view=segments` and `?view=summary` return JSON after redirects and exclude unapproved/unvalidated records. Verify the actual cross-origin `text/plain` JSON POST and response from the same browser origin using an approved isolated deployment with the same access settings. The TEST results used owner OAuth and do not establish anonymous cross-origin access. The signed-out production endpoint can also verify transport without storing a row using the existing `website` honeypot with a nonempty value. A human moderator must supply actual grade/access evidence to approve an eligible unknown-grade record. Hard grade/access failures remain blocked.

## 4. Publish the site configuration together

Once the asset, private history and signed-out browser gates pass, make one reviewed config commit. Update these four settings in `website/js/site-config.js` together, and change the `site-config.js?v=...` cache keys in `propose.html` and `map.html` for the cutover:

```js
proposalApiUrl: '<approved new public Apps Script /exec URL>',
proposalNetworkVersion: 'proposal-pbf-france-experimental-3d1457efd477ae74',
proposalRoadsBase: 'data/pbf-motorable-v1/proposal-roads',
proposalValidationBase: 'data/pbf-motorable-v1/selection-validation',
```

Keep `appsScriptUrl` for the existing legacy readers. Merge the config commit to `main` and wait for the Pages workflow for that SHA. Confirm the live Proposal loads the new manifests and capability handshake and selects the two-carriageway fixture. Confirm Explore reads the new API and reports distinct Proposals separately from road associations. Watch first approved live traffic for submission errors and timeouts. Keep incoming proposals pending until reviewed. Record the exact website SHA, deployment version and backup reference.

## Rollback

1. For an array-ingestion problem, set `ENABLE_MULTI_ROAD=false` in the new project. The new reader still understands already stored memberships. Candidate scalar submissions continue through grade/access checks. Record the incident window and preserve retries and incomplete records.
2. For a site/API rollback, revert **only the cutover config commit** on `main` so the previous registry, endpoint and cache keys ship together. Wait for the Pages workflow for the revert. Restore pilot write access using its recorded pre-freeze version in the coordinated rollback window. If the successor must stop accepting writes from cached clients, restrict its web app access after the site switches. Keep its data and compatible reader for private recovery.
3. For a backend-only rollback, use **Deploy → Manage deployments** to pin a previously reviewed version compatible with the new schema and literal-text writes. If no such version exists, pause successor writes and use the site/API rollback. Preserve both Sheets, all rows, memberships and registry releases. Reconcile any writes on either side of the rollback window by original request ID before resuming. [Google versioned deployment controls](https://developers.google.com/apps-script/concepts/deployments)
