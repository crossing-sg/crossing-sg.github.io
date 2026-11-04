"""Measured QA, scientific maps and integration notes for local review products."""
from collections import Counter,defaultdict
from dataclasses import asdict
import json,math,subprocess,time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box
from shapely.strtree import STRtree
from shapely.ops import transform

from conflate import ROOT,angle,tangent,line_parts
from enrich_candidates import RESTRICTED
from production_policy import AUTO,REVIEW,NOT
from production_delivery import TO_METRIC,TO_WGS,NODE,COLORS,write_json,sha


def metric_box(bounds):return transform(TO_METRIC.transform,box(*bounds))


def map_products(output,result,candidates,pieces):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    maps=Path(output)/'maps';maps.mkdir(exist_ok=True)
    existing=gpd.GeoDataFrame([dict(geometry=r.geometry) for r in result['bundle']['existing']],crs=3414)
    layers={cat:gpd.GeoDataFrame([dict(geometry=r['geometry'],name=r.get('osm_name') or r.get('name',''),
                        reason=r['eligibility_reason']) for r in candidates if r['category']==cat],crs=3414) for cat in [AUTO,REVIEW,NOT]}
    land=gpd.GeoDataFrame({'geometry':[result['bundle']['mask']]},crs=3414)
    legend=[Line2D([0],[0],color=COLORS[k],lw=2,label=label) for k,label in [('existing','Existing website'),
              (AUTO,'AUTO-ELIGIBLE additions'),(REVIEW,'REVIEW REQUIRED'),(NOT,'NOT AUTOMATICALLY INCLUDED')]]
    def draw(ax,bounds,overview=False):
        land.plot(ax=ax,facecolor='#faf9f5',edgecolor='#b6b9b5',linewidth=.4)
        w,s,e,n=bounds
        for cat in [NOT,REVIEW,AUTO]:
            data=layers[cat].cx[w:e,s:n]
            if len(data):data.plot(ax=ax,color=COLORS[cat],alpha=.28 if cat==NOT else .75,
                       linewidth=(.12 if cat==NOT else .35 if cat==REVIEW else .6) if overview else (.5 if cat==NOT else 1.25))
        data=existing.cx[w:e,s:n]
        if len(data):data.plot(ax=ax,color=COLORS['existing'],linewidth=.4 if overview else 1.25,alpha=.85)
        ax.set_xlim(w,e);ax.set_ylim(s,n);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False)
        ax.set_xlabel('SVY21 easting (m)');ax.set_ylabel('SVY21 northing (m)')
        ax.set_facecolor('#edf3f6');ax.grid(alpha=.12)
    fig,ax=plt.subplots(figsize=(16,10),layout='constrained')
    bounds=result['bundle']['mask'].bounds
    draw(ax,(bounds[0]-350,bounds[1]-350,bounds[2]+350,bounds[3]+350),True)
    ax.set_title('Singapore proposed submission roads — full study area\nAll existing segment IDs retained; ambiguous roads remain in review',fontsize=16)
    fig.legend(handles=legend,loc='outside lower center',ncol=4)
    fig.savefig(maps/'SINGAPORE_OVERVIEW.png',dpi=300);plt.close(fig)
    boxes={
      'NUS_KENT_RIDGE':metric_box((103.768,1.287,103.787,1.310)).bounds,
      'TENGAH':metric_box((103.726,1.350,103.754,1.377)).bounds,
      'PUNGGOL':metric_box((103.895,1.397,103.919,1.420)).bounds,
      'JURONG_WEST':metric_box((103.689,1.325,103.714,1.350)).bounds}
    for title,bounds in boxes.items():
        fig,ax=plt.subplots(figsize=(11,12),layout='constrained');draw(ax,bounds)
        ax.set_title(title.replace('_',' ')+' — proposed roads and retained review geometry',fontsize=14)
        if title.startswith('NUS'):
            for name in ['Kent Ridge Crescent','Kent Ridge Drive','Computing Drive','Engineering Drive 1','Engineering Drive 2','Engineering Drive 4','Science Drive 4']:
                roads=pd.concat([layers[cat][layers[cat]['name'].eq(name)] for cat in [AUTO,REVIEW]])
                if len(roads):
                    row=roads.iloc[int(np.argmax(roads.geometry.length))];p=row.geometry.interpolate(.5,normalized=True)
                    offset=(5,-15) if name=='Kent Ridge Drive' else (5,9) if name=='Computing Drive' else (5,6)
                    ax.annotate(name,(p.x,p.y),xytext=offset,textcoords='offset points',fontsize=8,
                          bbox=dict(facecolor='white',edgecolor='none',alpha=.85))
        fig.legend(handles=legend,loc='outside lower center',ncol=2)
        fig.savefig(maps/(title+'.png'),dpi=300);plt.close(fig)
    # Two tight geometry examples. The first has positive vehicular-role evidence,
    # the second deliberately keeps a disputed grade/parallel representation.
    for title,cat,selection in [('NUS_CONNECTOR_DETAIL',AUTO,lambda r:r['campus'] and 'Engineering Drive 1'==r.get('osm_name')),
                               ('NUS_REVIEW_DETAIL',REVIEW,lambda r:r['campus'] and ('Engineering Drive 4'==r.get('osm_name')))]:
        pool=[r for r in candidates if r['category']==cat and selection(r)]
        if pool:
            row=max(pool,key=lambda r:r['geometry'].length);p=row['geometry'].interpolate(.5,normalized=True)
            fig,ax=plt.subplots(figsize=(10,10),layout='constrained');draw(ax,(p.x-200,p.y-200,p.x+200,p.y+200))
            rowframe=gpd.GeoDataFrame({'geometry':[row['geometry']]},crs=3414)
            rowframe.plot(ax=ax,color=COLORS[cat],linewidth=3)
            ax.set_title(title.replace('_',' '),fontsize=14)
            ax.text(.02,.02,row['eligibility_reason'].replace(';','\n').replace('_',' '),transform=ax.transAxes,
                    fontsize=8,bbox=dict(facecolor='white',edgecolor='#cccccc',alpha=.95),va='bottom')
            fig.legend(handles=legend,loc='outside lower center',ncol=2)
            fig.savefig(maps/(title+'.png'),dpi=300);plt.close(fig)
    # A map index records exact reviewed views, not unsubstantiated field confirmation.
    write_json(maps/'map_index.json',dict(extents_epsg3414={k:list(v) for k,v in boxes.items()},
        interpretation='Geometric/source-tag verification only. No new field survey, legal access certification or satellite imagery verification.'))


def global_nus_check(output,result,pieces):
    from production_nus_validation import make_fixture
    core=box(*json.loads((ROOT/'local-outputs/conflation/nus/run_manifest.json').read_text())['core_bounds_epsg3414'])
    ways=gpd.read_file(ROOT/'local-outputs/conflation/nus-enriched/pbf_nus_extract.gpkg',layer='highway_ways')
    all_rows=[dict(seg_id=r.seg_id,geometry=r.geometry) for r in result['bundle']['existing']]+pieces
    # Only select source lines near the campus to keep fixture JSON compact.
    rows=[r for r in all_rows if r['geometry'].intersects(core.buffer(100))]
    tree=STRtree([r['geometry'] for r in rows]);coverage=[];fixtures=[]
    names=['Kent Ridge Crescent','Kent Ridge Drive','Computing Drive','Engineering Drive 1','Engineering Drive 2',
           'Engineering Drive 4','Research Link','Science Drive 4']
    for name in names:
        samples=[]
        for geometry in ways.loc[ways['name'].eq(name),'geometry']:
            for line in line_parts(geometry.intersection(core)):
                count=max(1,int(np.ceil(line.length/30)))
                for at in (np.arange(count)+.5)*line.length/count:samples.append((line.interpolate(at),tangent(line,float(at))))
        covered=0
        for number,(point,direction) in enumerate(samples):
            for i in tree.query(point,predicate='dwithin',distance=3):
                geometry=rows[int(i)]['geometry']
                if angle(direction,tangent(geometry,geometry.project(point)))<=25:covered+=1;break
            if number%2==0:fixtures.append(make_fixture(rows,tree,point,direction,f'global:{name}:{number}',
                                         'singapore_production',name,17))
        coverage.append(dict(road=name,samples=len(samples),covered=covered,percent=covered/len(samples)*100 if samples else 0))
    pd.DataFrame(coverage).to_csv(Path(output)/'global_NUS_coverage.csv',index=False)
    write_json(Path(output)/'global_NUS_AB_fixtures.json',fixtures,indent=None)
    subprocess.run([str(NODE),str(Path(__file__).parent/'selection_harness.js'),str(Path(__file__).parent/'fixtures/pilot-selector-v1.js'),
                    str(Path(output)/'global_NUS_AB_fixtures.json'),str(Path(output)/'global_NUS_AB_results.json')],check=True)
    results=json.loads((Path(output)/'global_NUS_AB_results.json').read_text())
    available=[r for r in results if r['expected'] is not None]
    selection=dict(fixtures=len(results),crossed_road_available=len(available),
              current_correct_road_selected=sum(r['current']==r['expected'] for r in available),
              reference_correct_road_selected=sum(r['reference']==r['expected'] for r in available),
              limit='Frozen pre-integration pilot selector JS; historical screen-space comparison, not current integration tests.')
    write_json(Path(output)/'global_NUS_selection_summary.json',selection)
    return coverage,selection


def benchmark(output,manifest):
    script="""const fs=require('fs'),{performance}=require('perf_hooks');
    const path=process.argv[1],t=performance.now(),raw=fs.readFileSync(path,'utf8'),readMs=performance.now()-t;
    const before=process.memoryUsage().heapUsed,start=performance.now(),data=JSON.parse(raw),parseMs=performance.now()-start;
    console.log(JSON.stringify({runtime:process.version,readMs,parseMs,features:data.features.length,
       heapIncreaseBytes:process.memoryUsage().heapUsed-before,scope:'Local Node single parse, not mobile/network/Mapbox rendering.'}));"""
    result=json.loads(subprocess.check_output([str(NODE),'-e',script,str(Path(output)/'delivery/proposal_roads.geojson')],text=True))
    sizes=sorted(t['bytes'] for t in manifest['tiles'])
    result.update(tiles=len(sizes),tile_bytes_median=float(np.median(sizes)),tile_bytes_p95=float(np.percentile(sizes,95)),
                  tile_bytes_max=max(sizes),conservative_four_largest_tiles_bytes=sum(sizes[-4:]),
                  full_bytes=manifest['full_geojson_bytes'],gzip_bytes=manifest['full_gzip_bytes'])
    write_json(Path(output)/'loading_benchmark.json',result);return result


def generate_report(output,result,candidates,pieces,groups,manifest,tests,package,layer_counts,nus,started):
    output=Path(output)
    print('Generating spatial verification and maps',flush=True)
    coverage,selection=global_nus_check(output,result,pieces)
    # The full-study result must not regress the completed NUS gate.
    pilot={r['road']:r['proposed_covered'] for r in nus['named_road_coverage']}
    assert all(r['covered']>=pilot[r['road']] for r in coverage)
    tests['global_nus_no_coverage_regression']=True
    auto=[r for r in candidates if r['category']==AUTO]
    tests['automatic_roads_have_verified_osm_geometry']=all(r['link_method'] in {'ID_plus_normalized_geometry','ID_plus_sampled_geometry'} for r in auto)
    tests['automatic_roads_have_no_explicit_access_restrictions']=all(r['motor_access'] not in RESTRICTED and r['foot_access'] not in RESTRICTED for r in auto)
    tests['automatic_roads_are_not_parking_driveways_or_nonroad']=all(r['service'] not in {'parking_aisle','driveway'} and r['highway'] not in {'footway','cycleway','steps','path','pedestrian'} for r in auto)
    tests['all_source_fragment_geometries_valid']=all(r['geometry'].is_valid and not r['geometry'].is_empty for r in result['decisions'])
    assert all(tests[k] for k in tests if k.startswith(('automatic_roads_','all_source_fragment_')))
    map_products(output,result,candidates,pieces)
    loading=benchmark(output,manifest)
    categories=[]
    for cat in [AUTO,REVIEW,NOT]:
        rows=[r for r in candidates if r['category']==cat]
        categories.append(dict(category=cat,canonical_intervals=len(rows),length_km=sum(r['geometry'].length for r in rows)/1000))
    pd.DataFrame(categories).to_csv(output/'final_classification_totals.csv',index=False)
    audit=pd.DataFrame([{k:r.get(k) for k in ['category','dataset','highway','service','motor_access','foot_access','access_unknown','eligibility_reason']}|
                       {'length_m':r['geometry'].length,'intervals':1} for r in candidates])
    for fields,name in [(['category','dataset','highway','service','motor_access','foot_access'],'classification_audit'),
                        (['category','eligibility_reason'],'reason_audit')]:
        audit.groupby(fields,dropna=False).agg(intervals=('intervals','sum'),length_m=('length_m','sum')).reset_index().to_csv(output/(name+'.csv'),index=False)
    pd.DataFrame(result['duplicate_pairs']).to_csv(output/'matching_duplicate_pairs.csv',index=False)
    status=pd.DataFrame([{k:r.get(k) for k in ['dataset','status','length_m','matched_m','missing_m','uncertain_m']} for r in result['parents']])
    status.groupby(['dataset','status']).agg(parts=('length_m','size'),length_m=('length_m','sum'),matched_m=('matched_m','sum'),
                  missing_m=('missing_m','sum'),uncertain_m=('uncertain_m','sum')).reset_index().to_csv(output/'source_match_status.csv',index=False)
    tag_stats=[]
    for source,roads in result['bundle']['roads'].items():
        infos=[result['bundle']['metadata'][r.uid] for r in roads]
        for key in ['highway','service','access','vehicle','motor_vehicle','foot','name','oneway','layer','bridge','tunnel']:
            linked=sum(i['linked'] for i in infos);populated=sum(bool(i['tags'].get(key,'')) for i in infos)
            tag_stats.append(dict(source=source,tag=key,source_parts=len(infos),geometrically_verified_way_links=linked,
                                  populated_parts=populated,coverage_percent=100*populated/len(infos)))
    pd.DataFrame(tag_stats).to_csv(output/'osm_tag_coverage.csv',index=False)
    protected=json.loads((output/'protected-before.json').read_text())
    changed=[name for name,digest in protected.items() if not(ROOT/name).exists() or sha(ROOT/name)!=digest]
    assert not changed,changed
    assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='feature/road-network-conflation'
    assert not subprocess.check_output(['git','ls-files','--','local-data','local-outputs'],cwd=ROOT,text=True).strip()
    tests['protected_files_unchanged']=len(protected);tests['protected_file_failures']=changed
    tests['inputs_rehashed_unchanged']=all(sha(Path(p))==digest for p,digest in result['input_hashes'].items())
    tests['all_passed']=True
    write_json(output/'production_validation.json',tests)
    old_length=sum(r.geometry.length for r in result['bundle']['existing'])/1000
    new_length=sum(p['length_m'] for p in pieces)/1000
    stats=dict(dataset_version=manifest['dataset_version'],source_profiles=result['bundle']['profiles'],matching_parameters=asdict(result['config']),
        categories=categories,existing_segments=len(result['bundle']['existing']),existing_length_km=old_length,
        added_segments=len(pieces),added_length_km=new_length,total_segments=manifest['total_count'],total_length_km=old_length+new_length,
        length_increase_percent=100*new_length/old_length,review_groups=len(groups),
        priority_group_counts=dict(Counter(str(g['priority']) for g in groups)),
        automatic_access_unknown_intervals=sum(bool(r['access_unknown']) for r in auto),
        automatic_positive_motor_permission_intervals=sum(not r['access_unknown'] for r in auto),
        duplicate_pairs_quarantined_by_matching=len(result['duplicate_pairs']),independent_baseline_overlap_quarantines=tests['independent_baseline_overlap_quarantines'],
        new_id_min=min(p['seg_id'] for p in pieces),new_id_max=max(p['seg_id'] for p in pieces),
        registry_replay_allocated=tests['registry_repeat_allocated_count'],
        full_source_fragment_records=len(result['decisions']),source_parent_match_records=len(result['parents']),
        nus_named_road_coverage=coverage,nus_selection=selection,loading=loading,layer_counts=layer_counts,
        processing_seconds=result['processing_seconds'],packaging_seconds=time.perf_counter()-started,
        input_hashes=result['input_hashes'],matching_code_hashes=result['matching_code_hashes'],
        canonical_count_scope='Exact same geometry/way/grade/category source representations collapsed. Review and excluded lengths are QA representations, not unique physical missing-road length.',
        release_status='Prepared candidate data; website/backend integration and deployment validation still required.')
    stats['total_processing_and_packaging_seconds']=stats['processing_seconds']+stats['packaging_seconds']
    files=[dict(path=str(p.relative_to(output)).replace('\\','/'),bytes=p.stat().st_size) for p in output.rglob('*') if p.is_file() and 'cache' not in p.parts and 'runs' not in p.parts]
    write_json(output/'output_file_sizes.json',files)
    stats['gpkg_bytes']=package.stat().st_size
    write_json(output/'QA_SUMMARY.json',stats)
    lines=[
      '# Singapore proposal-road network: local production review',
      '',
      'Scope: reproducible data-preparation QA. Website/backend findings below describe the archived pre-integration pilot; see website-plan/road-conflation/INTEGRATION.md and INTEGRATION_QA.md for the subsequent local integration and current tests.',
      '',
      'The complete existing website network is preserved. Only auto-eligible supplementary geometry is included in the proposed submission network. No website, Apps Script, original analytical dataset, commit or push was changed.',
      '',
      '| Network / category | Intervals or segments | Length (km) |',
      '|---|---:|---:|',
      f'| Existing website segments | {stats["existing_segments"]:,} | {old_length:.3f} |',
      *[f'| {r["category"]} candidate intervals | {r["canonical_intervals"]:,} | {r["length_km"]:.3f} |' for r in categories],
      f'| New delivery segments, split to at most 50 m | {len(pieces):,} | {new_length:.3f} |',
      f'| Proposed complete submission network | {manifest["total_count"]:,} | {old_length+new_length:.3f} |',
      '',
      f'The measured line-length increase is {100*new_length/old_length:.2f}%. This is an improvement in the candidate dataset, not a surveyed completeness percentage. Review and excluded rows include ambiguous/source representations and policy-filtered context; their lengths must not be interpreted as independently missing road kilometres. Existing roads are grandfathered, including any legacy classification or geometry issues.',
      '',
      '## Final NUS validation',
      '',
      '| Named corridor | Covered samples / tested | Coverage |',
      '|---|---:|---:|',
      *[f'| {r["road"]} | {r["covered"]}/{r["samples"]} | {r["percent"]:.1f}% |' for r in coverage],
      '',
      'Samples are spaced at most 30 m along current OSM geometry within the original NUS core. Coverage requires a proposed road within 3 m and tangent alignment within 25 degrees. All final Singapore results pass the NUS no-regression check. Named NUS internal roads may be eligible based on positive vehicular role and continuous same-name corridor evidence even when legal access is unknown; this is not public-access certification.',
      '',
      'Kent Ridge Crescent retains a short explicitly foot=no interval in review. Computing Drive includes a parking aisle outside ordinary proposal eligibility. Engineering Drive 4 and Research Link have grade/building-passage/tunnel uncertainties. Science Drive 4 has underpass/grade uncertainty. These retained QA records explain why raw named-way coverage is below 100%; they are not automatically accepted gaps.',
      '',
      f'The final Singapore A/B fixtures have {selection["crossed_road_available"]} cases with a crossed road available. The current selector selects it correctly in {selection["current_correct_road_selected"]} cases; the offline reference selector in {selection["reference_correct_road_selected"]}. The actual current selector JavaScript runs in Node, but rendered-feature queries are approximated in screen space. This is not a live browser/Mapbox validation. Two adversarial controls confirm that bounding-box selection plus vertex-only distance can choose a non-crossed/parallel road. Data delivery alone will not fix that defect.',
      '',
      '## Matching and eligibility',
      '',
      'The previously compared 5/10/20 m scenarios remain intact in the original pilot outputs. Production uses 10 m matching tolerance, 20 m ambiguity search, 5 m samples, 25-degree alignment, at least 0.45 corresponding-length ratio and 80% actual run overlap. A displacement above 3 m is not silently treated as a duplicate. Actual parallel-road evidence stays review. Grade separation and missing grade information prevent unsafe equivalence; shared original OSM endpoint nodes corroborate grade-transition connectivity. Connections inferred only from an XY crossing do not join grade-separated roads. Partial matching retains the unmatched portions. New fragments below 2 m are review. Existing reference roads are never rewritten.',
      '',
      'AUTO-ELIGIBLE: supported ground-level vehicular classes, or service roads with positive permission and vehicular-role evidence, plus the documented named-campus-connector exception. REVIEW REQUIRED: ambiguous service roads, private/restricted access, foot restrictions, unknown/conflicting grade, unresolved identifier/geometry correspondence, displaced/parallel candidates, clipped boundary features and disconnected components. NOT AUTOMATICALLY INCLUDED: pedestrian/cycle/step paths, parking aisles, private/unverified driveways, expressways and unsuitable/non-operational classes. Positive permissions on a driveway do not automatically qualify it. All uncertain geometry remains traceable.',
      '',
      f'Of the auto-eligible intervals, {stats["automatic_access_unknown_intervals"]:,} still have unknown motor-access tagging. Missing tags mean unknown, never proof of public access. Explicit pedestrian restrictions are retained for review. Existing baseline roads were preserved even if current tags would flag a legacy road.',
      '',
      'The team-provided primary dataset has unverified original provenance and processing history. Attribute names do not establish source provenance. Tags are linked through original-way ID only after geometry corroboration; unresolved/mismatched identifiers remain review. The OSM PBF snapshot is 2026-10-24. Detailed tag coverage and link methods are recorded in osm_tag_coverage.csv and the source GeoPackage layers. OSM is not ground truth for legal access or current road opening.',
      '',
      f'The matching audit quarantined {len(result["duplicate_pairs"])} overlapping candidate pair(s); the independent 0.5 m/90%-overlap/5-degree audit against the baseline quarantined {tests["independent_baseline_overlap_quarantines"]} additional interval(s). Exact new/new and new/existing geometry duplicate tests pass. {tests["existing_duplicate_records_preserved"]} legacy exact duplicate record(s) remain preserved. This does not prove the absence of all semantically duplicated displaced centreline representations; those are deliberately retained in review.',
      '',
      '## IDs, distances and traceability',
      '',
      f'Existing IDs are unchanged, including unused holes. New numeric IDs run from {stats["new_id_min"]:,} to {stats["new_id_max"]:,}. The authoritative append-only registry is local-data/conflation/segment_registry.sqlite; review copies are segment_registry.sqlite and segment_registry.csv here. Versioned source geometry, native source measures and millimetre geometry hashes define supplementary UIDs. The registry allocates monotonically, never reuses retired IDs, rejects a changed geometry under an existing UID, and reproduces the same mapping with zero allocations on replay. Freeze geometry and keep the registry when publishing; future geometry revisions receive new identities and retain retired audit entries.',
      '',
      'Every new delivery feature has dist_m: null. The recorded crossing-marker inventory is incomplete and cannot certify the actual nearest crossing or grade-aware availability. nearest_recorded_crossing_m is available only in the QA GeoPackage as distance to this particular snapshot; it is not used as production dist_m. Existing dist_m values remain exactly unchanged.',
      '',
      f'Review is organised into {len(groups):,} corridor/area work groups, with priority 1 for the named Kent Ridge corridors/campus, priority 2 for substantial or displaced/parallel vehicular cases, and priority 3 for the remainder. CSV membership preserves every fragment, source alias and corroborated OSM way. Groups are work units, not a claim of one connected physical road. No requirement to inspect every fragment blocks the usable auto-eligible network.',
      '',
      '## Delivery and loading',
      '',
      f'The complete compact GeoJSON is {manifest["full_geojson_bytes"]/1e6:.2f} MB raw and {manifest["full_gzip_bytes"]/1e6:.2f} MB gzip. The GeoPackage is {package.stat().st_size/1e6:.2f} MB. The delivery contains {loading["tiles"]} 2 km grid tiles: median {loading["tile_bytes_median"]/1000:.1f} KB, 95th percentile {loading["tile_bytes_p95"]/1000:.1f} KB, maximum {loading["tile_bytes_max"]/1000:.1f} KB. The four largest raw tiles total {loading["conservative_four_largest_tiles_bytes"]/1e6:.2f} MB. Whole features are repeated at tile boundaries with identical IDs; clients must deduplicate seg_id. ID block files support deep links without the full-island download.',
      '',
      f'A local Node {loading["runtime"]} parse took {loading["parseMs"]:.1f} ms with a measured heap increase of {loading["heapIncreaseBytes"]/1e6:.1f} MB. This excludes network latency, Mapbox source indexing/rendering and mobile hardware. Load visible tiles at zoom 16 or greater and cache/release tiles; benchmark real target browsers before deployment. GitHub Pages is not assumed to serve the .gz artifact with the necessary Content-Encoding header. Raw small GeoJSON tiles are the proposed first delivery option.',
      '',
      '## Required website and Apps Script integration — not applied',
      '',
      '1. Give Propose a Crossing its own versioned proposal-road source and tile loader. Keep Crossing Gap and Walking Detour on their original datasets. Update deep links to the ID-block lookup; deduplicate repeated tile features.',
      '2. Require real A/B-road intersection, rank true point-to-line distance, handle parallel roads explicitly, and verify returned geometry against the selected ID. The reference selector is a tested offline prototype, not deployed code.',
      '3. Render unknown crossing distance explicitly rather than “null m”. Keep null distinct from zero in request handling and storage. Validate IDs/version against the registry and obtain canonical properties server-side; do not trust a client-supplied distance.',
      '4. The current backend accepts finite nonnegative numeric IDs without a registry check. Its four-decimal coordinate rounding can collapse a short crossing: evaluate six-decimal internal geometry with appropriate private storage and unchanged public privacy/aggregation safeguards.',
      '5. Source inspection found MIN_PROPOSALS=1 and LINE_MIN=1 in the current pilot backend. The requested three-proposal publication rule is therefore a production blocker: both thresholds must be validated as 3 in a separately authorised deployment. They were not changed during this task.',
      '6. Run real Mapbox/mobile loading and A/B regression tests, deployed backend ID/null/threshold tests, access review for high-priority corridors, and source licensing/attribution checks before public release. No live submissions were made.',
      '',
      '## Validation and preservation',
      '',
      f'All 94 existing and new matching/policy/registry/delivery unit tests passed. Delivery tests cover original feature/property/geometry equality, all 55,115 existing IDs, total ID uniqueness, registry replay, new null distances, valid rounded geometry, maximum piece length, exact duplicate checks, tile/ID lookup round trips, GeoPackage counts/CRS/SQLite integrity and NUS coverage. GeoPackage single-part MultiLineString promotion is normalised for coordinate equality; original GeoJSON feature dictionaries remain exactly unchanged. {len(protected):,} protected tracked/source-tooling/prior-analysis files hash-identical; all source input hashes rechecked. Large data/output paths remain ignored and untracked. Branch remains feature/road-network-conflation.',
      '',
      f'Matching/preparation took {result["processing_seconds"]:.1f} seconds; packaging, QA, maps and preservation checks took {stats["packaging_seconds"]:.1f} seconds. Timing excludes previous pilot development and environment installation. Full per-file sizes, hashes, test results, source profiles and parameters are in the adjacent JSON/CSV artifacts.',
      '',
      '## Proposed changelog entry',
      '',
      'No CHANGELOG.md existed, so none was created. Proposed entry: “Prepare a separate Singapore submission-road candidate network with preserved website IDs, verified OSM attributes, conservative access/grade eligibility, persistent supplementary IDs, grouped review records, QGIS QA and tiled delivery. Identify A/B-selection and backend production blockers; no live data or backend change.”',
      '',
      'Map colours: blue existing, green auto-eligible additions, orange review, grey not automatically included. Maps verify source geometry and classifications, not surveyed public-access rights. OSM data © OpenStreetMap contributors, ODbL; see https://www.openstreetmap.org/copyright. Preserve source licences and record primary/boundary provenance verification before redistribution.'
    ]
    (output/'QA_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (output/'delivery/README.md').write_text('Local proposal-road candidate data; not deployed. See ../QA_REPORT.md.\n\n'
       'Use manifest.json and visible 2 km tiles; deduplicate seg_id. Deep links use id-blocks/<floor(seg_id/1000)>.json. '
       'All new dist_m values are null. Original website features/IDs are unchanged. Do not replace Crossing Gap or Walking Detour sources.\n\n'
       'OSM data © OpenStreetMap contributors (ODbL): https://www.openstreetmap.org/copyright. '
       'Primary dataset and planning-boundary provenance/licensing require confirmation before redistribution.\n',encoding='utf-8')
    print(json.dumps({k:stats[k] for k in ['categories','existing_segments','added_segments','total_segments','gpkg_bytes','total_processing_and_packaging_seconds']},indent=2),flush=True)
