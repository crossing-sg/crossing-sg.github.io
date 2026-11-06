> For the 242,112-segment PBF and Multi-road Crossing release, follow the [production cutover and rollback runbook](RELEASE_MULTI_ROAD.md). The older single-road guide below describes the earlier integration.

# Apps Script v2: isolated review and deployment guide

The source in this branch is a proposed public-launch backend. It is not deployed. Do not paste it into the current production project or run tests on the production Sheet.

Read [the integration guide](../website-plan/road-conflation/INTEGRATION.md) for complete data, test and release instructions.

## Files and configuration

Copy all three files into a **separate test project**: `Code.gs`, generated `RegistryConfig.gs`, and generated `RoadGeometry.gs`. Set Script Property `PROPOSAL_DATA_BASE_URL` to the HTTPS URL of this exact reviewed static release, ending in `proposal-roads/`. No URL from a client request is used for registry fetches. The version and SHA-256 manifest digest are generated and pinned; fetched tiles and canonical registry blocks are checked against it.

`MIN_PROPOSALS = 1` and `LINE_MIN = 1` for the November demo. Zero, negative and non-integer thresholds fail closed. The public API is `proposal-api-v2`; the frontend rejects incompatible pilot responses. The feature branch leaves its API URL disabled pending a separately authorised, tested deployment.

## Sheet migration and moderation

Back up the private Sheet, copy it into the isolated environment, then run `setup()` there. Setup validates existing header names and appends columns; it preserves all existing rows. New proposal columns are `schema_version`, `registry_version`, `request_id` and `review_status`. Support adds `request_id`.

New proposals have `status=pending` and `review_status=pending`. To approve a reviewed proposal, set **both** `status=ok` and `review_status=approved`. To reject it, set `status=rejected` or `review_status=rejected`. Blank review state is not approval. Pilot imports with `status=ok` and blank `schema_version`/`review_status` are eligible without another manual approval. Rejected/pending pilot rows remain excluded. New-schema submissions still require explicit moderation; no bulk edits or deletions are performed. Legacy IDs and rows remain compatible, and approved legacy rows can contribute to counts. Their old individually rounded geometry does not enter current-schema representative lines.

Free-text stories remain private, with a separate `story_status`; the public API currently returns no free text. Keep the Sheet private. Six-decimal A/B coordinates are needed for private geometry validation; public lines are aggregated from at least one accepted current-schema submission and rounded to about 10 m. Invalid/degenerate aggregates remain null.

## Request validation

Proposals require an actual registry member, matching network version, UUID request token, allowed choices, finite Singapore A/B coordinates, 2–80 m distance, a unique geometric road crossing and no relevant grade/access guard conflict. The server reloads canonical geometry and ignores client distance. Null remains null; a real zero distance remains zero. Identical retries do not add another row. Submitted moderation status is ignored; the server always writes pending.

Support is accepted only for a published segment, is idempotent for a retry token and cannot count as a proposal. Browser storage limits casual repeat support, not determined repeat users. Anonymous submissions cannot establish distinct residents; the demo threshold is one accepted submission, not a verified unique person. A single rounded line may approximately reveal the original crossing location.

## Public views

- `?view=capabilities`: read-only protocol/network/publication/moderation policy, without proposal activity. Clients must accept this handshake before any POST, preventing an accidental write to the incompatible pilot backend.
- `?view=segments`: segments with at least one accepted proposal, with reviewed aggregates, canonical nullable distance and a representative line only when separately supported by at least one eligible current-schema proposal.
- `?view=summary`: totals and last-updated date for the **published-only** population. Pending and below-threshold activity contributes nothing.
- `?view=csv`: the same published segment population; null distance is blank rather than an invented zero.
- POST acknowledgements: receipt/review state, with no public or hidden segment count.

Rejecting an accepted row removes its contribution. A segment dropping below one disappears from segment/CSV/summary responses and from the next Explore/Home refresh. No individual A/B coordinates or stories are returned. Home uses canonical road locations rounded to about 100 m.

## Isolated verification

`npm test` executes the actual `.gs` files with in-memory Sheets, local static registry fetches and no network credentials. `npm run serve:integration` serves the local website with this mock at `http://127.0.0.1:8765`; test controls are outside the published `website/` folder. Browser tests block all live backend requests.

Before production, use a separately deployed test Apps Script and test Sheet to verify real Google authorisation, HTTPS static hosting, redirect/CORS behaviour, cache/UrlFetch quotas and performance. The implementation skips caching payloads above 90 KB because individual Apps Script cache values are limited to 100 KB ([Google Cache reference](https://developers.google.com/apps-script/reference/cache/cache)); cache misses always revalidate static content. This mock does not certify Google service permissions or production throughput.

Only after explicit approval should a compatible website/API release be committed, pushed or deployed. Preserve the registry snapshot and legacy records, set both thresholds to 1, reconcile legacy road IDs before making imported `ok` records public, and enable the matching v2 URL. The existing live pilot remains untouched until that authorised change.
