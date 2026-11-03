"""Geometry and actual-source-JavaScript tests; no live browser/backend writes."""
import json,math,subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import LineString,Point,box,mapping
from shapely.ops import substring,transform
from shapely.strtree import STRtree
from pyproj import Transformer

from conflate import ROOT,angle,tangent,frame
from production_policy import AUTO,REVIEW,NOT

NODE=Path('C:/Users/sherl/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
TO_WGS=Transformer.from_crs(3414,4326,always_xy=True)


def proposed_rows(result):
    rows=[dict(seg_id=r.seg_id,uid=r.uid,geometry=r.geometry,existing=True) for r in result['bundle']['existing']]
    next_id=10000000
    for row in result['candidates']:
        if row['category']!=AUTO:continue
        line=row['geometry'];cuts=list(np.arange(0,line.length-1e-7,50))+[line.length]
        if len(cuts)>2 and cuts[-1]-cuts[-2]<.01:cuts.pop(-2)
        for a,b in zip(cuts[:-1],cuts[1:]):
            rows.append(dict(seg_id=next_id,uid=row['fragment_uid'],geometry=substring(line,a,b),existing=False));next_id+=1
    return rows


def screen(lon,lat,zoom):
    size=512*2**zoom
    return ((lon+180)/360*size,(.5-math.log(math.tan(math.pi/4+math.radians(lat)/2))/(2*math.pi))*size)


def make_fixture(roads,tree,point,direction,fixture_id,network,road,zoom=17,half=12):
    normal=np.array([-direction[1],direction[0]])
    a=(point.x-normal[0]*half,point.y-normal[1]*half);b=(point.x+normal[0]*half,point.y+normal[1]*half)
    aw=TO_WGS.transform(*a);bw=TO_WGS.transform(*b)
    ap=screen(*aw,zoom);bp=screen(*bw,zoom)
    rectangle=box(min(ap[0],bp[0])-4,min(ap[1],bp[1])-4,max(ap[0],bp[0])+4,max(ap[1],bp[1])+4)
    ab=LineString([ap,bp]);mid=ab.interpolate(.5,normalized=True)
    found=[];expected=[]
    for i in tree.query(point.buffer(55)):
        row=roads[int(i)];geographic=transform(TO_WGS.transform,row['geometry'])
        projected=LineString([screen(x,y,zoom) for x,y in geographic.coords])
        if projected.buffer(3).intersects(rectangle):
            found.append(dict(type='Feature',properties={'seg_id':row['seg_id'],'dist_m':None},geometry=mapping(geographic)))
            if projected.crosses(ab) or (projected.intersects(ab) and not projected.overlaps(ab)):
                expected.append((projected.distance(mid),row['seg_id']))
    expected.sort()
    return dict(fixture_id=fixture_id,network=network,road=road,zoom=zoom,a=aw,b=bw,features=found,expected=expected[0][1] if expected else None)


def validate_nus(output,result):
    output=Path(output);rows=proposed_rows(result)
    old=[r for r in rows if r['existing']]
    trees={name:STRtree([r['geometry'] for r in values]) for name,values in [('existing',old),('proposed',rows)]}
    ways=gpd.read_file(result['bundle']['pbf_cache'],layer='highway_ways')
    targets=['Kent Ridge Crescent','Kent Ridge Drive','Computing Drive','Engineering Drive 1','Engineering Drive 2','Engineering Drive 4','Research Link','Science Drive 4']
    fixtures=[];coverage=[]
    for name in targets:
        selected=ways[ways['name'].eq(name)]
        samples=[]
        for geometry in selected.geometry:
            clipped=geometry.intersection(result['bundle']['mask'])
            from conflate import line_parts
            for line in line_parts(clipped):
                count=max(1,int(np.ceil(line.length/30)))
                for at in (np.arange(count)+.5)*line.length/count:samples.append((line.interpolate(at),tangent(line,float(at))))
        covered={key:0 for key in trees}
        for number,(point,direction) in enumerate(samples):
            for key,values in [('existing',old),('proposed',rows)]:
                for i in trees[key].query(point,predicate='dwithin',distance=3):
                    line=values[int(i)]['geometry']
                    if angle(direction,tangent(line,line.project(point)))<=25:covered[key]+=1;break
                if number%2==0:
                    for zoom in [16,17,18]:fixtures.append(make_fixture(values,trees[key],point,direction,f'{name}:{number}:{key}:{zoom}',key,name,zoom))
        coverage.append(dict(road=name,samples=len(samples),existing_covered=covered['existing'],proposed_covered=covered['proposed'],
                             existing_percent=100*covered['existing']/len(samples) if samples else 0,
                             proposed_percent=100*covered['proposed']/len(samples) if samples else 0))
    # Deterministic adversarial controls demonstrate vertex and bbox defects.
    origin=np.array([21100.,31000.])
    for label,half in [('non_crossed_nearby_road',3),('parallel_nearest_vertex_error',12)]:
        controls=[dict(seg_id=90000001,geometry=LineString([origin+[-40,0],origin+[40,0]])),
                  dict(seg_id=90000002,geometry=LineString([origin+[-1,5],origin+[1,5]]))]
        fixtures.append(make_fixture(controls,STRtree([r['geometry'] for r in controls]),Point(*origin),np.array([1.,0.]),label,'control',label,17,half))
    (output/'AB_fixtures.json').write_text(json.dumps(fixtures))
    subprocess.run([str(NODE),str(Path(__file__).parent/'selection_harness.js'),str(Path(__file__).parent/'fixtures/pilot-selector-v1.js'),
                    str(output/'AB_fixtures.json'),str(output/'AB_results.json')],check=True)
    tested=json.loads((output/'AB_results.json').read_text())
    for row in tested:
        row['current_correct']=row['current']==row['expected'];row['reference_correct']=row['reference']==row['expected']
        row['crossed_road_available']=row['expected'] is not None
        row['current_correct_road_selected']=row['expected'] is not None and row['current_correct']
        row['reference_correct_road_selected']=row['expected'] is not None and row['reference_correct']
    pd.DataFrame(tested).to_csv(output/'AB_selection_tests.csv',index=False)
    pd.DataFrame(coverage).to_csv(output/'named_road_coverage.csv',index=False)
    summary=pd.DataFrame(tested).groupby(['network','zoom']).agg(tests=('fixture_id','size'),crossed_road_available=('crossed_road_available','sum'),
           current_correct_road_selected=('current_correct_road_selected','sum'),reference_correct_road_selected=('reference_correct_road_selected','sum'),
           current_correct=('current_correct','sum'),reference_correct=('reference_correct','sum')).reset_index()
    summary.to_csv(output/'AB_selection_summary.csv',index=False)
    controls=[r for r in tested if r['network']=='control']
    assert all(r['reference_correct'] for r in controls)
    assert all(not r['current_correct'] for r in controls)
    assert all(r['geometry'].is_valid for r in rows)
    frame(result['candidates']).to_file(output/'NUS_final.gpkg',layer='classified_candidates',driver='GPKG')
    gpd.GeoDataFrame(rows,crs=3414).to_file(output/'NUS_final.gpkg',layer='proposed_roads',driver='GPKG')
    validation=dict(completed=True,existing_pilot_ids_preserved=len(old),proposed_features=len(rows),
                    matching_code_hashes=result['matching_code_hashes'],
                    automatic_candidate_intervals=sum(r['category']==AUTO for r in result['candidates']),
                    named_road_coverage=coverage,selector_summary=summary.to_dict('records'),adversarial_controls=controls,
                    selector_scope='historical_pre_integration_pilot',
                    confirmed_findings=['The archived pre-integration selector does not enforce intersection and ranks vertices.',
                                        'Current integration source and privacy checks are validated separately; see INTEGRATION.md and INTEGRATION_QA.md.'],
                    limitations=['This reproducible data-phase comparison executes the frozen pre-integration pilot selector, not the current asynchronous frontend.',
                                 'No live Mapbox browser or real user submissions were used. Access/grade/parallel uncertainties remain in QA.'])
    (output/'NUS_FINAL_VALIDATION.json').write_text(json.dumps(validation,indent=2))
    from production_maps import nus_map
    nus_map(output,result,rows,coverage)
    print(json.dumps(validation,indent=2),flush=True)
