Integrate the complete Singapore OSM proposal network on top of the shared main's Satellite Streets v12 update. Residents can match and submit OSM-only roads, and Explore resolves those proposals from the versioned geometry registry while retaining the teammate's thin white crossing lines and highlight outline.

- Preserve all 55,115 LTA segments and the earlier supplementary IDs, with 602,199 unified segments across all 32 highway categories. Analytical inputs, Walking Detour routes, Storytelling, and planning-area charts remain unchanged.
- Apply Proposal-only satellite raster saturation -0.25, hue +40°, contrast -0.30, brightness min 0 / max 0.5, using the reviewed preview's conversion. Preserve all vector road and label styles.
- Keep the legacy API URL for existing Home/Story reads. New proposal functionality has a separate `proposalApiUrl`, to be enabled after the compatible Google Apps Script is separately deployed and validated.
- Retain desktop styles and scope narrow-screen map/form fixes to Proposal and Explore.

Validation: 24 legacy tests, six all-highway/API tests, three basemap/integration tests, four processing tests, isolated desktop/mobile end-to-end checks, complete dataset/hash checks against main `785b7533`, and real Mapbox raster/vector-style verification. All proposal tests use in-memory Sheets; no production records are submitted. See `website-plan/shared-integration/README.md` and the checked-in JSON results.

Google Apps Script deployment and the coordinated `proposalApiUrl` switch remain separate operational steps. This PR does not deploy the backend or alter production data.
