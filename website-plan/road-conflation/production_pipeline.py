"""Final NUS validation, then resumable Singapore proposal-road preparation.

No website/backend writes. Large products and the persistent registry are local.
"""
import argparse
from dataclasses import replace
import hashlib,json,time
from pathlib import Path
import subprocess

import geopandas as gpd
import shapely
from shapely.ops import substring

from conflate import ROOT,Config,frame,row_for,candidate_duplicate_review
from production_policy import AUTO,REVIEW,NOT,VERSION,eligibility
from production_prepare import prepare_bundle,dump,load,sha
from production_match import run_stage


def classify_row(row,road,info):
    links=int(bool(row.get('source_connections_start')))+int(bool(row.get('source_connections_end')))
    category,reason,evidence=eligibility(road.road_class,info['tags'],info['linked'],campus=info['campus'],
                                        connected=bool(row.get('component_connected')),endpoint_links=links,
                                        match_kind=row['fragment_kind'],match_reason=row['reason'],boundary=road.boundary,
                                        grade_conflict=info['grade_conflict'],barrier_restriction=info['barrier_restriction'],
                                        corridor_supported=info['corridor_supported'])
    if row['length_m']<2 and category==AUTO:category=REVIEW;reason='below_2m_proposal_geometry'
    tags=info['tags']
    row.update(category=category,eligibility_reason=reason,osm_way_id=info['matched_way_id'],
               link_method=info['link_method'],link_max_offset_m=info['link_max_offset_m'],campus=info['campus'],
               source_geometry_key=road.source_geometry_key,tags_json=json.dumps(tags,sort_keys=True),
               inclusion_action='represented_by_reference' if row['fragment_kind']=='matched' else 'candidate')
    row.update({f'osm_{key}':tags.get(key,'') for key in ['highway','service','access','vehicle','motor_vehicle','foot','name','oneway','layer','bridge','tunnel','lanes','sidewalk']})
    row.update(evidence)
    return row


def policy_record(road,info):
    row=row_for(road,fragment_uid='policy-'+hashlib.sha256(road.uid.encode()).hexdigest()[:24],parent_uid=road.uid,
                fragment_kind='not_evaluated_policy',reason=info['preliminary_reason'],from_m=road.original_offset_m,
                to_m=road.original_offset_m+road.length,component_connected=False,parallel_evidence=False,
                source_connections_start=0,source_connections_end=0)
    row=classify_row(row,road,info)
    row['category']=NOT;row['eligibility_reason']=info['preliminary_reason'];row['inclusion_action']='not_automatically_included'
    return row


def canonical_candidates(rows):
    """Collapse identical same-grade QA representations; retain full source audit."""
    chosen={}
    for row in sorted(rows,key=lambda r:(r['dataset']!='processed_lta',r['fragment_uid'])):
        if row['inclusion_action']=='represented_by_reference':continue
        key=(hashlib.sha256(shapely.to_wkb(shapely.normalize(shapely.set_precision(row['geometry'],.05)))).hexdigest(),
             row['category'],row.get('osm_way_id'),row.get('osm_layer'),row.get('osm_bridge'),row.get('osm_tunnel'))
        if key not in chosen:
            item=row.copy();item['source_record_uids_json']=json.dumps([row['fragment_uid']]);item['supporting_sources']=row['dataset']
            chosen[key]=item
        else:
            item=chosen[key];members=json.loads(item['source_record_uids_json']);members.append(row['fragment_uid'])
            item['source_record_uids_json']=json.dumps(members);item['supporting_sources']=';'.join(sorted(set(item['supporting_sources'].split(';')+[row['dataset']])))
    return list(chosen.values())


def process(output,*,nus=False,workers=4):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    source_files=[ROOT/'website/data/gap_segments.geojson',ROOT/'local-data/lta/road singapore.geojson',
                  ROOT/'local-data/osm/pbf/Singapore.osm.pbf',ROOT/'local-data/boundaries/MasterPlan2025PlanningAreaBoundaryNoSea.geojson']
    source_files+=sorted((ROOT/'local-data/osm/Singapore-shp/shape').glob('roads.*'))
    input_hashes={str(path):sha(path) for path in source_files}
    code_hashes={name:sha(Path(__file__).parent/name) for name in ['production_policy.py','production_prepare.py','production_match.py','production_pipeline.py']}
    fingerprint=hashlib.sha256(json.dumps(dict(inputs=input_hashes,code=code_hashes,nus=nus,minimum_fragment_m=2),sort_keys=True).encode()).hexdigest()[:16]
    prepared=output/'cache/prepared.pkl';prepared_meta=output/'cache/prepared-code.txt'
    if prepared.exists() and prepared_meta.exists() and prepared_meta.read_text()==fingerprint:
        bundle=load(prepared);print('Reusing immutable prepared inputs.',flush=True)
    else:
        bundle=prepare_bundle(output,nus=nus);prepared_meta.write_text(fingerprint)
    run_dir=output/'runs'/fingerprint
    config=Config(min_fragment_m=2)
    all_parents=[];decisions=[];references=list(bundle['reference'])
    for label in ['processed_lta','osm']:
        road_list=bundle['roads'][label];lookup={r.uid:r for r in road_list}
        active=[r for r in road_list if bundle['metadata'][r.uid]['preliminary_category']!=NOT]
        skipped=[policy_record(r,bundle['metadata'][r.uid]) for r in road_list if bundle['metadata'][r.uid]['preliminary_category']==NOT]
        p,f=run_stage(active,references,run_dir,label,config,workers,metadata=bundle['metadata'])
        for row in f:classify_row(row,lookup[row['uid']],bundle['metadata'][row['uid']])
        decisions.extend(f+skipped);all_parents.extend(p)
        if label=='processed_lta':
            # Unresolved primary geometry must not veto a well-supported OSM road.
            # Spatial uncertainty still has to pass the same website-based tests.
            extra=[]
            for row in f:
                if row['fragment_kind']=='matched' or row['category']==AUTO:
                    road=lookup[row['uid']]
                    extra.append(replace(road,uid=row['fragment_uid'],geometry=row['geometry'],
                                         confidence='confirmed' if row['fragment_kind']=='matched' else 'candidate'))
            references.extend(extra)
    # Audit automatic additions for same-grade near-duplicates. Quarantined
    # geometry remains in review instead of disappearing from the QA record.
    auto=[r.copy() for r in decisions if r['category']==AUTO and r['inclusion_action']=='candidate']
    for row in auto:row['fragment_kind']='missing'
    duplicate_pairs=candidate_duplicate_review(auto,config)
    quarantined={r['fragment_uid'] for r in auto if r['fragment_kind']=='uncertain'}
    for row in decisions:
        if row['fragment_uid'] in quarantined:
            row['category']=REVIEW;row['eligibility_reason']+=';automatic_overlap_audit_requires_review'
    candidates=canonical_candidates(decisions)
    assert all(r['geometry'].is_valid and not r['geometry'].is_empty for r in decisions)
    result=dict(bundle=bundle,parents=all_parents,decisions=decisions,candidates=candidates,
                duplicate_pairs=duplicate_pairs,config=config,fingerprint=fingerprint,
                input_hashes=input_hashes,matching_code_hashes=code_hashes,
                processing_seconds=time.perf_counter()-started,nus=nus)
    dump(output/'classification_result.pkl',result)
    summary=[]
    for category in [AUTO,REVIEW,NOT]:
        selected=[r for r in candidates if r['category']==category]
        summary.append(dict(category=category,canonical_candidate_intervals=len(selected),length_m=sum(r['geometry'].length for r in selected)))
    import pandas as pd
    pd.DataFrame(summary).to_csv(output/'classification_totals.csv',index=False)
    (output/'processing_stage.json').write_text(json.dumps(dict(policy=VERSION,fingerprint=fingerprint,processing_seconds=result['processing_seconds'],
                                                               summary=summary,source_profiles=bundle['profiles'],quarantined_overlap_pairs=len(duplicate_pairs)),indent=2))
    print(json.dumps({'output':str(output),'seconds':result['processing_seconds'],'summary':summary},indent=2),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['nus','singapore','package'],required=True)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='feature/road-network-conflation':raise RuntimeError('Wrong branch')
    root=ROOT/'local-outputs/conflation/singapore-production'
    if args.stage=='nus':
        result=process(root/'nus-final',nus=True,workers=min(args.workers,2))
        from production_nus_validation import validate_nus
        validate_nus(root/'nus-final',result)
    elif args.stage=='singapore':
        validation=root/'nus-final/NUS_FINAL_VALIDATION.json'
        if not validation.exists() or not json.loads(validation.read_text())['completed']:
            raise RuntimeError('Complete final NUS validation first.')
        process(root,nus=False,workers=args.workers)
    else:
        from production_delivery import finalise
        finalise(root,load(root/'classification_result.pkl'))


if __name__=='__main__':main()
