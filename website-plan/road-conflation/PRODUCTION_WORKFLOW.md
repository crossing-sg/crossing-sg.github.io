# Local Singapore proposal-road preparation

These tools produce review artifacts only. They do not write website data, Apps Script, the original inputs, Crossing Gap or Walking Detour analysis files. Run from the repository root on `feature/road-network-conflation` using the existing ignored Python environment.

```powershell
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' -m unittest discover -s website-plan/road-conflation -p 'test_*.py'
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' 'website-plan/road-conflation/production_pipeline.py' --stage nus --workers 2
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' 'website-plan/road-conflation/production_pipeline.py' --stage singapore --workers 4
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' 'website-plan/road-conflation/production_pipeline.py' --stage package
& '.\local-outputs\road-conflation-venv\Scripts\python.exe' 'website-plan/road-conflation/production_source_audit.py'
```

Outputs are in `local-outputs/conflation/singapore-production/`. Start with `QA_REPORT.md`, `QA_SUMMARY.json`, `maps/`, and `singapore_proposal_network.gpkg`. `delivery/manifest.json` describes the complete GeoJSON, visible-area tiles and deep-link ID lookup. Files stay local and ignored; copying any artifact into the website is a separate deployment task.

The original `nus`, `nus-refined`, and `nus-enriched` outputs are read-only. `nus-final` adds the final policy/selection gate. The full run masks supplementary sources to the local Master Plan 2025 land boundary plus 20 m; all existing website roads are preserved irrespective of the mask. Current PBF attributes are recovered from the previously downloaded 2026-10-24 snapshot. No third-party service is called during processing.

The matcher checkpoints 400-source-road batches and uses global source connectivity rather than isolated tile graphs. Input and matching-code hashes determine the checkpoint namespace. Do not manually mix checkpoints from different fingerprints. The final NUS and full-study matching-code hashes must agree before packaging. Packaging is repeatable, replacing its generated GeoPackage and delivery products; the authoritative registry is never reset.

`local-data/conflation/segment_registry.sqlite` is the persistent append-only identity registry. Keep a backup with every release. Existing holes are reserved; all supplementary numeric IDs begin above the maximum existing ID. Millimetre source measures and geometry hashes create stable supplementary UIDs. Changed geometry receives a new UID/ID, and retired records remain in the registry. Never regenerate a published registry from a subset of inputs or reassign its IDs.

The final policy is in `production_policy.py`. It explicitly separates missing access tags from permission. It retains uncertain geometry for review and never uses a buffer alone as proof of duplication. The named-NUS-corridor exception is evidence of vehicular function, not certification of public ownership/access. The processed primary dataset's original provenance and processing history remain unverified.

Every new production distance is null. The QA-only `nearest_recorded_crossing_m` measures distance to an incomplete, unverified crossing-marker snapshot. It must not be substituted into `dist_m`.

The selector comparison in this data-phase workflow is historical: `selection_harness.js` runs the frozen pre-integration selector in `fixtures/pilot-selector-v1.js` against the original prototype. This preserves reproducibility after the frontend became asynchronous. The archived data-phase reports' selector defects and pilot thresholds of 1 describe that earlier source, not the subsequent integration. See `INTEGRATION.md` and `INTEGRATION_QA.md` for the current shared selector, local source thresholds of 3, real Chromium tests and remaining isolated Google-deployment checks. Previously generated analytical outputs are preserved.

Review CSVs identify work groups and every source member; GeoPackage source-fragment classifications retain matched, partially matched, uncertain and policy-filtered records. Review/excluded lengths count QA representations and must not be interpreted as unique missing physical-road kilometres. OSM source attribution and primary/boundary licensing verification remain necessary before redistribution.

The final visual follow-up found coordinate jumps in some supplied Shapefile ways. The source-audit command independently re-reads selected raw PBF ways, verifies that the local Shapefile matches the ZIP, and records every in-study source part without a corroborated way mapping. It adds review layers/maps without changing proposal delivery or the registry. Unverified geometries were already blocked from automatic eligibility; an unusually long edge alone is not enough to discard a corroborated road.
