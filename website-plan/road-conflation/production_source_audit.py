"""Follow up visual coordinate-jump findings without repairing original inputs."""
from collections import Counter
import hashlib,json,sqlite3,time,zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmium
import pandas as pd
from shapely.geometry import LineString

from conflate import ROOT
from production_delivery import write_json,sha


def longest_edge(geometry):
    parts=geometry.geoms if geometry.geom_type=='MultiLineString' else [geometry]
    return max((np.sqrt((np.diff(np.asarray(g.coords),axis=0)**2).sum(axis=1)).max(initial=0) for g in parts),default=0.)


def run_source_audit(output):
    started=time.perf_counter();output=Path(output);package=output/'singapore_proposal_network.gpkg'
    unverified=[]
    for source in ['processed_lta','osm']:
        data=gpd.read_file(package,layer=source+'_in_study',where="osm_link_method NOT IN ('ID_plus_normalized_geometry','ID_plus_sampled_geometry')")
        data['dataset']=source;data['maximum_edge_m']=data.geometry.map(longest_edge)
        unverified.append(data)
    frame=gpd.GeoDataFrame(pd.concat(unverified,ignore_index=True),crs=3414)
    frame.drop(columns='geometry').to_csv(output/'source_way_disagreements.csv',index=False)
    frame.to_file(package,layer='unverified_source_geometries',driver='GPKG')
    # Read the PBF again independently for the three visual-control ways.
    ids={33264400,656295995,775859255}
    class Controls(osmium.SimpleHandler):
        def __init__(self):super().__init__();self.rows=[]
        def way(self,w):
            if int(w.id) in ids:
                self.rows.append(dict(way_id=int(w.id),name=w.tags.get('name',''),osm_version=int(w.version),
                    osm_timestamp=str(w.timestamp),geometry=LineString([(n.lon,n.lat) for n in w.nodes])))
    controls=Controls();controls.apply_file(str(ROOT/'local-data/osm/pbf/Singapore.osm.pbf'),locations=True,idx='flex_mem')
    direct=gpd.GeoDataFrame(controls.rows,crs=4326).to_crs(3414)
    examples=[];geometries=[]
    for sid in sorted(ids):
        shp=gpd.read_file(ROOT/'local-data/osm/Singapore-shp/shape/roads.shp',where=f'osm_id={sid}').to_crs(3414).iloc[0]
        pbf=direct.loc[direct.way_id.eq(sid)].iloc[0]
        item=dict(way_id=sid,name=shp['name'] or '',shapefile_length_m=shp.geometry.length,
                  pbf_length_m=pbf.geometry.length,shapefile_maximum_edge_m=longest_edge(shp.geometry),
                  pbf_maximum_edge_m=longest_edge(pbf.geometry),pbf_version=int(pbf.osm_version),pbf_timestamp=pbf.osm_timestamp)
        assert shp.geometry.hausdorff_distance(pbf.geometry)>1000
        examples.append(item)
        for source,line in [('supplied_shapefile',shp.geometry),('independent_PBF_read',pbf.geometry)]:
            geometries.append(dict(item,source=source,geometry=line))
    example_frame=gpd.GeoDataFrame(geometries,crs=3414)
    example_frame.to_file(package,layer='source_disagreement_examples',driver='GPKG')
    archive=ROOT/'local-data/osm/Singapore.osm.shp.zip'
    with zipfile.ZipFile(archive) as z:
        member=next(n for n in z.namelist() if n.replace('\\','/').endswith('/roads.shp') or n=='roads.shp')
        archive_hash=hashlib.sha256(z.read(member)).hexdigest()
    extracted_hash=sha(ROOT/'local-data/osm/Singapore-shp/shape/roads.shp')
    assert archive_hash==extracted_hash
    auto=gpd.read_file(package,layer='auto_candidate_intervals',columns=['fragment_uid','link_method','geometry','length_m','osm_name','highway'])
    auto['maximum_edge_m']=auto.geometry.map(longest_edge)
    auto.loc[auto.maximum_edge_m.gt(1000)].drop(columns='geometry').to_csv(output/'automatic_long_straight_edge_watchlist.csv',index=False)
    assert auto.link_method.isin(['ID_plus_normalized_geometry','ID_plus_sampled_geometry']).all()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig,axes=plt.subplots(1,3,figsize=(17,7),layout='constrained')
    land=gpd.read_file(package,layer='study_boundary')
    for ax,item in zip(axes,examples):
        land.plot(ax=ax,facecolor='#faf9f5',edgecolor='#b6b9b5',linewidth=.4)
        for source,color,lw in [('supplied_shapefile','#d16a13',1.3),('independent_PBF_read','#00845c',2.5)]:
            data=example_frame[example_frame.way_id.eq(item['way_id'])&example_frame.source.eq(source)]
            data.plot(ax=ax,color=color,linewidth=lw)
        ext=example_frame.loc[example_frame.way_id.eq(item['way_id'])].total_bounds
        ax.set_xlim(ext[0]-1000,ext[2]+1000);ax.set_ylim(ext[1]-1000,ext[3]+1000);ax.set_aspect('equal')
        ax.set_title(f'{item["name"] or "Unnamed service road"}\nOSM way {item["way_id"]}',fontsize=10)
        ax.ticklabel_format(style='plain',useOffset=False);ax.tick_params(labelsize=7)
        ax.set_xlabel('SVY21 easting (m)');ax.set_ylabel('SVY21 northing (m)')
    fig.suptitle('Confirmed supplied-geometry / PBF disagreements — retained in review, never automatic',fontsize=14)
    fig.legend(handles=[Line2D([0],[0],color=c,lw=2,label=l) for c,l in [('#d16a13','Supplied Shapefile geometry'),('#00845c','Independent PBF geometry read')]],
               loc='outside lower center',ncol=2)
    fig.savefig(output/'maps/SOURCE_GEOMETRY_DISAGREEMENT.png',dpi=300);plt.close(fig)
    with sqlite3.connect(package) as db:assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    stats=dict(unverified_source_parts=len(frame),by_dataset=dict(Counter(frame.dataset)),
               unverified_parts_with_edge_over_1km=int(frame.maximum_edge_m.gt(1000).sum()),
               controls=examples,raw_shapefile_equals_zip_member=True,shapefile_sha256=extracted_hash,
               automatic_long_edge_watchlist=len(auto.loc[auto.maximum_edge_m.gt(1000)]),
               all_automatic_geometry_links_verified=True,seconds=time.perf_counter()-started,
               interpretation='Confirmed coordinate disagreements, not a reconstruction of editing history. Raw inputs and PBF are preserved. Long edges alone are not proof of bad geometry. All unverified source representations remain outside automatic eligibility.')
    write_json(output/'source_geometry_audit.json',stats)
    return stats


def refresh_review_metadata(output,stats):
    """Refresh final artifacts when this additional visual audit runs separately."""
    output=Path(output);summary=json.loads((output/'QA_SUMMARY.json').read_text())
    previous_seconds=summary.get('source_geometry_audit',{}).get('seconds',0)
    summary['source_geometry_audit']=stats;summary['gpkg_bytes']=(output/'singapore_proposal_network.gpkg').stat().st_size
    summary['additional_visual_source_audit_seconds']=stats['seconds']
    summary['total_processing_and_packaging_seconds']+=stats['seconds']-previous_seconds
    summary['layer_counts']['unverified_source_geometries']=stats['unverified_source_parts']
    summary['layer_counts']['source_disagreement_examples']=len(stats['controls'])*2
    write_json(output/'QA_SUMMARY.json',summary)
    tests=json.loads((output/'production_validation.json').read_text())
    tests.update(independent_pbf_read_confirms_source_disagreements=True,raw_shapefile_equals_zip_member=True,
                 unverified_source_geometry_auto_included=False,geopackage_integrity_after_visual_audit=True)
    write_json(output/'production_validation.json',tests)
    text=(output/'QA_REPORT.md').read_text(encoding='utf-8')
    appendix=['','## Additional source-geometry finding from visual inspection','',
       f'{stats["unverified_source_parts"]:,} in-study source parts do not pass original-ID plus geometry corroboration: '+
       ', '.join(f'{source}: {count:,}' for source,count in stats['by_dataset'].items())+'. All are outside automatic eligibility.',
       '',
       'The long orange chords visible on the overview are QA source representations, not additions. Independent re-reading of the raw PBF confirms large coordinate disagreements for the following controls. The local roads.shp is byte-identical to the original ZIP member, so these differences were not introduced by this workflow.',
       '',
       '| OSM way | Name | Supplied Shapefile length | Independent PBF length |',
       '|---|---|---:|---:|',
       *[f'| {r["way_id"]} | {r["name"] or "Unnamed service road"} | {r["shapefile_length_m"]/1000:.3f} km | {r["pbf_length_m"]/1000:.3f} km |' for r in stats['controls']],
       '',
       'Use source_way_disagreements.csv and the unverified_source_geometries / source_disagreement_examples GeoPackage layers for source-level investigation. This does not establish when or why the coordinate differences arose; no original source geometry was repaired or replaced. The automatic_long_straight_edge_watchlist.csv has three long Tuas roads whose geometries ARE corroborated by the PBF. Long edges alone do not make them duplicates or errors; public proposal suitability/opening/access at the port merits targeted verification.',
       '',
       f'This additional source audit took {stats["seconds"]:.1f} seconds. The final GeoPackage size is {summary["gpkg_bytes"]/1e6:.2f} MB. Main proposal delivery and IDs are unchanged.']
    text=text.split('\n## Additional source-geometry finding from visual inspection')[0]
    (output/'QA_REPORT.md').write_text(text+'\n'.join(appendix)+'\n',encoding='utf-8')
    paths=[dict(path=str(p.relative_to(output)).replace('\\','/'),bytes=p.stat().st_size) for p in output.rglob('*') if p.is_file() and 'cache' not in p.parts and 'runs' not in p.parts]
    write_json(output/'output_file_sizes.json',paths)


if __name__=='__main__':
    path=ROOT/'local-outputs/conflation/singapore-production'
    stats=run_source_audit(path);refresh_review_metadata(path,stats)
    print(json.dumps(stats,indent=2))
