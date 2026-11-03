"""Generate local QA summaries from the reproducible GeoPackage outputs."""
from pathlib import Path
import json

import geopandas as gpd
import pandas as pd


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in rows])


def generate_report(output, manifest, summary):
    output=Path(output)
    selected=next((r for r in manifest['runs'] if r['tolerance_m']==10),manifest['runs'][0])
    tolerance=selected['tolerance_m']
    package=Path(selected['package'])
    classified=gpd.read_file(package,layer='classified_roads')
    candidates=gpd.read_file(package,layer='candidate_supplements')
    uncertain=gpd.read_file(package,layer='uncertain_roads')
    website=gpd.read_file(package,layer='website_roads')
    summary=pd.DataFrame(summary)
    counts=[]
    for run in manifest['runs']:
        current=summary[(summary.tolerance_m==run['tolerance_m']) & (summary.scope=='fragments')]
        row=[f"{run['tolerance_m']:g} m"]
        for status in ['matched','missing','uncertain']:
            subset=current[current.category==status]
            row.append(f"{int(subset['count'].sum()):,} / {subset.length_m.sum()/1000:.3f}")
        counts.append(row)
    candidate_source=[]
    for dataset,data in candidates.groupby('dataset'):
        candidate_source.append([dataset,len(data),f'{data.length_m.sum()/1000:.3f}'])
    status_rows=[]
    for dataset,data in classified.groupby('dataset'):
        for status,group in data.groupby('status'):
            status_rows.append([dataset,status,len(group),f'{group.length_m.sum()/1000:.3f}'])
    target=candidates[candidates.name.fillna('').str.contains('Kent Ridge Crescent|Kent Ridge Drive',case=False)]
    named_rows=[]
    for (dataset,name),data in target.groupby(['dataset','name']):
        named_rows.append([dataset,name,len(data),f'{data.length_m.sum()/1000:.3f}'])
    choices=[]
    for mask,label in [
        ((classified.dataset=='processed_lta') & (classified.name=='Kent Ridge Crescent') & (classified.status=='unmatched'),'missing campus road'),
        ((classified.dataset=='processed_lta') & (classified.name=='Clementi Road') & classified.reason.fillna('').str.contains('displacement_or_parallel'),'displaced or parallel'),
        ((classified.dataset=='processed_lta') & classified.parallel_evidence.fillna(False),'coexisting parallel evidence'),
        ((classified.dataset=='processed_lta') & (classified.status=='partially_matched'),'partial overlap'),
        ((classified.dataset=='processed_lta') & classified.reason.fillna('').str.contains('reference_grade_unknown'),'unknown grade'),
        ((classified.dataset=='osm') & (classified.status=='partially_matched') & (classified.missing_m.fillna(0)>0),'OSM extension'),
    ]:
        possible=classified.loc[mask].sort_values('length_m',ascending=False)
        if len(possible):
            value=possible.iloc[0]
            point=value.geometry.interpolate(.5,normalized=True)
            choices.append(dict(case=label,dataset=value.dataset,source_id=value.source_id,
                                uid=value.uid,name=value['name'] or '(unnamed)',status=value.status,
                                length_m=round(value.length_m,3),reason=value.reason,
                                easting=round(point.x,3),northing=round(point.y,3)))
    pd.DataFrame(choices).to_csv(output/'review_examples.csv',index=False)
    pd.DataFrame([{k:v for k,v in row.items()} for row in choices]).to_json(output/'review_examples.json',orient='records',indent=2)
    points=uncertain.geometry.interpolate(.5,normalized=True).to_crs(4326)
    review=uncertain.drop(columns='geometry').copy()
    review['review_longitude']=points.x
    review['review_latitude']=points.y
    review.to_csv(output/'uncertain_review_queue.csv',index=False)
    example_rows=[[r['case'],r['source_id'],r['name'],r['status'],f"{r['easting']}, {r['northing']}"] for r in choices]
    investigation_path=output/'network_investigation.json'
    investigation=json.loads(investigation_path.read_text()) if investigation_path.exists() else {}
    diagnostic=investigation.get('shared_identifier_geometry_diagnostic',{})
    shared_text=f"{diagnostic['shared_attribute_values']:,}" if 'shared_attribute_values' in diagnostic else 'not recomputed'
    equal_text=f"{diagnostic['equal_geometry_at_5cm']:,}" if 'equal_geometry_at_5cm' in diagnostic else 'not recomputed'
    area='Singapore whole-island run' if manifest['mode']=='all_island' else 'NUS Kent Ridge pilot' if manifest['mode']=='nus_pilot' else 'Custom-area pilot'
    core_description=('Whole input extent; no pilot clipping.' if manifest['mode']=='all_island' else
                      'The named Kent Ridge roads expanded by 500 m on each side.' if manifest['mode']=='nus_pilot' else 'User-supplied WGS84 bounding box, transformed to SVY21.')
    versions={}
    from importlib.metadata import version
    for name in ['geopandas','shapely','pyproj','pyogrio','networkx','numpy','pandas','matplotlib']:
        versions[name]=version(name)
    (output/'requirements-used.txt').write_text('\n'.join(f'{name}=={v}' for name,v in versions.items())+'\n')
    qa=f'''# Road network conflation: {area} QA

Run time (Singapore): {manifest['created_singapore']}
Selected review scenario: {tolerance:g} m. All layers use EPSG:3414. Status: pilot complete; outputs require review and are not deployed.

## Inputs and coverage

- Existing website: 55,115 globally preserved IDs; {len(website):,} existing features intersect this pilot, {website.geometry.length.sum()/1000:.3f} km. They are retained whole, including small extensions beyond the core boundary.
- Primary: team-provided GIS-processed LTA dataset, 252,972 original features. Original provenance and processing history remain unverified.
- Supplement: OSM shapefile, 276,032 original features.
- Area: {core_description} An additional 75 m website-reference context is used for bounded runs. Metric bounds: {manifest['core_bounds_epsg3414']}.
- Source roads are clipped to the core for review; feature counts refer to resulting line parts, not original whole-island features.
- The website pipeline reads an unavailable external crossing_gap_segments.geojson, excludes expressways, simplifies by 2 m and rounds exported coordinates to five decimals. It preserves existing IDs. Its upstream segmentation cannot be reconstructed from this checkout.
- Whole-island lengths are 2,755.323 km (website), 17,321.667 km (primary), and 24,275.971 km (OSM). The primary includes 66,516 footways, 7,483 steps, 5,971 cycleways, and 90,522 service features. Counts alone do not explain road coverage; island_class_profile.csv gives class lengths and nearest-midpoint diagnostics.
- Current primary/OSM files share {shared_text} identifier values; {equal_text} paired geometries agree on a 5 cm precision grid. This demonstrates overlap between these current files and does not verify original provenance or processing direction.

## Tolerance sensitivity

Each entry is fragment count / km. Fragment categories are disjoint within a source; matched roads from two sources often represent the same physical road and must not be summed as unique road coverage.

{table(['Retrieval tolerance','Matched','Candidate missing','Uncertain'],counts)}

The three scenarios are deliberately conservative: a 20 m ambiguity search is retained even at a 5 m matching tolerance, so a displaced line just outside the matching radius is not silently called missing. The 10 m scenario is recommended for further review. Differences between scenarios are candidates for review, not evidence that a wider buffer is correct.

## Selected scenario: source classifications

These are parent source parts. Partially matched parents are summarized here; their matched, missing and uncertain intervals are exported separately. Do not add these parent lengths to fragment lengths.

{table(['Dataset','Category','Parts','km'],status_rows)}

Candidate missing intervals after sequential primary/OSM matching:

{table(['Dataset','Intervals','km'],candidate_source)}

Named campus roads among candidate intervals:

{table(['Dataset','Road','Intervals','km'],named_rows)}

Lengths are source centreline lengths, including separate carriageways where represented; they are not deduplicated physical street-name lengths. Unnamed service roads include possible parking aisles, private access and loading roads. Access/subtype attributes are absent, so crossing eligibility requires review. Candidate does not mean approved for website publication.

## Matching parameters and safeguards

- Candidate search {tolerance:g} m; wider ambiguity guard 20 m; source sampling intervals at most 5 m, anchored to original source measures.
- Unoriented local tangent difference <=25 degrees; projected corresponding reference length >=45% of each sample interval; longitudinal endpoint overshoot <=2 m.
- Continuous matched runs must also have >=80% actual geometric overlap with the flat-ended corridors of direction-compatible references; sparse short stubs cannot establish coverage solely at sampled midpoints.
- Automatic matched intervals require offset <=3 m as well as direction and length correspondence. Larger aligned offsets remain uncertain unless separate parallel-road evidence is present.
- Parallel-road evidence requires a distinct sibling in the same input aligned near the reference at >=2 of 3 interior positions, >=3 m separation, and source-network connections at both ends. Otherwise displaced versus parallel remains a review question.
- Endpoint-to-line source connectivity uses 1 m; reference attachment uses 3 m. Grade metadata conflicts block matching and connectivity. Unknown website grade metadata produces uncertainty for elevated/tunnel candidates. XY crossings alone do not connect source lines.
- Footways, steps, cycleways, construction/proposed features and motorway/motorway_link are excluded from road additions. Tracks/pedestrian classes, busways and trunk/trunk_link additions require category/access review. This policy is not a verified reconstruction of CAT1, which is absent from the supplied input.
- Source intervals are split into matched/missing/uncertain runs. Missing fragments under 10 m are reviewed rather than automatically added; larger uncovered extensions are retained. Split boundaries have sampling uncertainty of approximately +/-2.5 m.
- OSM is compared to the existing website plus all eligible primary intervals. Overlap with an uncertain primary interval stays uncertain, preventing OSM from duplicating or silently confirming it.
- Candidate overlap audit uses <=0.5 m, >=90% coverage of the quarantined candidate and <=5 degrees, retaining flagged cases in uncertainty. It never discards a longer valid extension merely because a shorter line overlaps part of it.
- The review network retains all existing pilot roads unchanged and adds candidate intervals split into approximately 50 m preview sections. No snapping or graph noding is performed on preview geometry; connectivity metrics describe near connections, not a routing-ready graph.

## Examples to inspect in QGIS

Filter classified_roads by dataset/source_id or uid, then compare website_roads and source layers. Coordinates below are SVY21 metres.

{table(['Case','Source ID','Name','Result','Review coordinate'],example_rows)}

Full details: review_examples.csv, ambiguous_examples_{tolerance:g}m.json and uncertain_review_queue.csv. The map is a visual comparison of these datasets, without independent field/satellite verification. Precision/recall against human-labelled ground truth has not been established.

## QGIS deliverables and automated QA

Open {package.name}. Layers: website_roads, processed_lta_roads, osm_roads, classified_roads, matched_roads, candidate_supplements, partially_matched_roads, uncertain_roads, excluded_roads, network_preview and pilot_boundary.

All {len(manifest['runs'])} scenarios passed geometry validity, non-empty geometries, interval-length conservation, unique fragment/network UIDs, zero exact duplicate preview additions, and preservation of existing pilot IDs and coordinates. GeoPackages were reopened and checked for CRS, valid geometries and existing-road ID/coordinate integrity. Near-duplicate candidates quarantined in the selected scenario: {selected['validation']['near_duplicate_candidates_quarantined']}.

Input SHA-256 hashes were checked before and after processing, including the shapefile components. Originals and website files were not written. Global tracked-file and 55,115-ID checks are recorded separately in preservation_check.json after final verification.

## Stable supplementary identifiers

Existing numeric seg_id values remain untouched, including holes in the 0..57987 range. Supplementary preview rows have null seg_id and deterministic namespaced network_uid values derived from source identity, canonical source geometry and native measure intervals. They are repeatable for fixed inputs, clipping bounds and algorithm parameters; split boundaries/source revisions can change them.

After human acceptance, freeze accepted geometry and use a persistent registry mapping network_uid to a numeric seg_id. Start after the maximum existing/reserved value (currently 57988), allocate monotonically, never fill old holes or recycle retired IDs, and preserve the registry across reruns. Update lineage explicitly when sources or boundaries change. Do not derive IDs from row order or assume an osm_id equals a website segment ID. Numeric allocation and backend integration have not been performed.

## Reproduction and whole-island readiness

From repository root in PowerShell:

```powershell
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' -m unittest discover -s 'website-plan/road-conflation' -v
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' 'website-plan/road-conflation/conflate.py'
```

The same indexed matcher supports --bbox WEST SOUTH EAST NORTH and a subsequent full-island run:

```powershell
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' 'website-plan/road-conflation/conflate.py' --all --tolerances 10 --no-map
```

Whole-island outputs default to local-outputs/conflation/singapore. Full-island conflation has not been run or performance-benchmarked. Review pilot ground truth, class/access policy, unconnected components and grade uncertainty before treating island-wide additions as accepted. Pinned package versions are in requirements-used.txt and the source workflow requirements.txt. Code and input hashes are in run_manifest.json.

## Proposed changelog entry

No existing CHANGELOG.md was found; none was created. Proposed entry:

“Add a reproducible EPSG:3414 road conflation pilot for NUS Kent Ridge, with direction/length/connectivity checks, conservative parallel-road handling, partial-overlap preservation, 5/10/20 m sensitivity, QGIS review layers and ID-preservation tests. Keep all existing website segment IDs and website/backend behavior unchanged.”
'''
    (output/'QA_REPORT.md').write_text(qa,encoding='utf-8')
