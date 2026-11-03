"""Local maps and QA for the NUS PBF enrichment and grouped-review stage."""
from pathlib import Path
import json

import geopandas as gpd
import pandas as pd
import shapely

from refine_candidates import A,B,C,COLORS


def markdown_table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in rows])


def create_maps(output,data,groups,prior):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    output=Path(output)
    legend=[Line2D([0],[0],color=COLORS['existing'],lw=2,label='Existing website'),
            Line2D([0],[0],color=COLORS[A],lw=2,label='Eligible candidates (provisional)'),
            Line2D([0],[0],color=COLORS[C],lw=2,label='Uncertain: grouped review'),
            Line2D([0],[0],color=COLORS[B],lw=1,ls='--',label='Excluded source context')]
    excluded=prior['B_excluded_context']
    keys=shapely.to_wkb(shapely.normalize(shapely.set_precision(excluded.geometry.to_numpy(),.05)))
    excluded=excluded.loc[~pd.Series(keys,index=excluded.index).duplicated()]
    def draw(ax,bounds):
        from shapely.geometry import box
        window=box(*bounds)
        for frame,color,width,alpha,style,z in [
            (excluded,COLORS[B],.5,.55,'--',1),
            (prior['C_spatial_review_context'],COLORS[C],.6,.4,'-',2),
            (data[data.enriched_category==C],COLORS[C],1.5,1.,'-',3),
            (data[data.enriched_category==A],COLORS[A],2.,1.,'-',4),
            (prior['website_roads'],COLORS['existing'],1.9,1.,'-',5)]:
            view=frame[frame.geometry.intersects(window)]
            if len(view):view.plot(ax=ax,color=color,linewidth=width,alpha=alpha,linestyle=style,zorder=z)
        ax.set_xlim(bounds[0],bounds[2]);ax.set_ylim(bounds[1],bounds[3]);ax.set_aspect('equal')
        ax.ticklabel_format(useOffset=False,style='plain');ax.set_facecolor('#faf9f5')
        ax.grid(alpha=.12);ax.set_xlabel('SVY21 easting (m)');ax.set_ylabel('SVY21 northing (m)')
    named=data[data.review_name.isin(['Kent Ridge Crescent','Kent Ridge Drive'])]
    west,south,east,north=named.total_bounds
    fig,ax=plt.subplots(figsize=(10,13),layout='constrained')
    draw(ax,(west-150,south-150,east+150,north+150))
    for name in ['Kent Ridge Crescent','Kent Ridge Drive','Engineering Drive 1','Engineering Drive 4','Computing Drive','Research Link']:
        rows=data[data.review_name.eq(name)]
        if not len(rows):continue
        row=rows.loc[rows.length_m.idxmax()];point=row.geometry.interpolate(.5,normalized=True)
        ax.annotate(name,(point.x,point.y),xytext=(5,8),textcoords='offset points',fontsize=9,
                    bbox=dict(facecolor='white',edgecolor='none',alpha=.9),zorder=10)
    manual=groups[groups.category==C].head(10)
    for _,row in manual.iterrows():
        ax.annotate(f'R{int(row.priority_rank)}',(row.easting,row.northing),fontsize=8,color='#792981',
                    bbox=dict(facecolor='white',edgecolor='#792981',boxstyle='round,pad=.15',alpha=.9),zorder=11)
    ax.set_title('NUS roads after OSM tag enrichment\nR labels identify prioritised review groups; missing access is not public permission.',fontsize=13,pad=10)
    fig.legend(handles=legend,loc='outside lower center',ncol=2,fontsize=9)
    fig.savefig(output/'nus_enriched_closeup.png',dpi=300);plt.close(fig)
    selected=[]
    for name in ['Computing Drive','Engineering Drive 4']:
        candidates=groups[(groups.category==C) & groups.road_names.str.contains(name,regex=False)]
        if len(candidates):selected.append(candidates.iloc[0])
    for _,row in groups[(groups.category==C) & groups.geometry_risk].iterrows():
        if row.group_id not in {g.group_id for g in selected}:selected.append(row)
        if len(selected)>=3:break
    for _,row in groups[(groups.category==C) & groups.service_group.eq('parking_driveway_or_special_access')].iterrows():
        if row.group_id not in {g.group_id for g in selected}:selected.append(row)
        if len(selected)>=4:break
    for _,row in groups[groups.category==C].iterrows():
        if row.group_id not in {g.group_id for g in selected}:selected.append(row)
        if len(selected)>=4:break
    selected=selected[:4]
    pbf=gpd.read_file(output/'pbf_nus_extract.gpkg',layer='highway_ways')
    fig,axes=plt.subplots(2,2,figsize=(14,13),layout='constrained')
    for ax in axes.flat:ax.set_visible(False)
    map_rows=[]
    for ax,row in zip(axes.flat,selected):
        ax.set_visible(True)
        w,s,e,n=row.geometry.bounds
        radius=max(80,min(220,max(e-w,n-s)*.65))
        x,y=(w+e)/2,(s+n)/2
        draw(ax,(x-radius,y-radius,x+radius,y+radius))
        # PBF outlines make source-ID geometry conflicts visible independently.
        member=data[data.review_group_id.eq(row.group_id)]
        if member.match_method.str.startswith('unresolved').any():
            original_ids={int(v) for v in member.source_id if str(v).isdigit()}
            shapes=pbf[pbf.way_id.isin(original_ids)]
            if len(shapes):shapes.plot(ax=ax,color='#147d92',linewidth=1.7,linestyle='--',zorder=6)
        gpd.GeoSeries([row.geometry],crs=3414).plot(ax=ax,color='#792981',linewidth=3,linestyle=':',zorder=7)
        label=row.road_names if len(row.road_names)<45 else row.road_names[:42]+'...'
        ax.set_title(f'R{int(row.priority_rank)} | {label}\n{row.interval_count} intervals / {row.length_m:.0f} m | {row.service_group}',fontsize=10)
        map_rows.append(dict(group_id=row.group_id,priority_rank=int(row.priority_rank),road_names=row.road_names,
                             interval_count=int(row.interval_count),length_m=row.length_m))
    fig.legend(handles=legend+[Line2D([0],[0],color='#792981',lw=3,ls=':',label='Selected review group'),
                              Line2D([0],[0],color='#147d92',lw=2,ls='--',label='Same-ID PBF geometry, if unresolved')],
               loc='outside lower center',ncol=3,fontsize=9)
    fig.suptitle('Remaining uncertain NUS road groups | review evidence, not published changes',fontsize=14)
    fig.savefig(output/'remaining_review_groups.png',dpi=300);plt.close(fig)
    pd.DataFrame(map_rows).to_csv(output/'mapped_review_groups.csv',index=False)


def create_report(output,data,groups,result):
    output=Path(output)
    counts=result['counts'];manual=groups[groups.category==C]
    count_rows=[]
    for code,label,previous in [(A,'Eligible',161),(B,'Excluded',0),(C,'Uncertain / manual review',602)]:
        count_rows.append([label,previous,counts[code]['intervals'],f"{counts[code]['length_m']/1000:.3f}"])
    service=data[data.road_class.eq('service')]
    service_rows=[]
    for (bucket,category),group in service.groupby(['service_group','enriched_category']):
        service_rows.append([bucket,category,len(group),f'{group.length_m.sum()/1000:.3f}'])
    cov=pd.read_csv(output/'recovered_tag_coverage.csv')
    coverage_rows=[]
    for tag in ['highway','service','access','vehicle','motor_vehicle','foot','name','oneway','layer','bridge','tunnel']:
        all_row=cov[(cov.scope=='all_763') & cov.tag.eq(tag)].iloc[0]
        service_row=cov[(cov.scope=='service_590') & cov.tag.eq(tag)].iloc[0]
        coverage_rows.append([tag,int(all_row.tagged_intervals),int(service_row.tagged_intervals),f'{all_row.tagged_length_m/1000:.3f}'])
    top=[]
    for _,row in manual.head(15).iterrows():
        top.append([f'R{int(row.priority_rank)}',row.road_names,int(row.interval_count),f'{row.length_m:.0f}',row.review_action])
    changes=pd.read_csv(output/'classification_change_matrix.csv')
    change_rows=[[r.previous_category,r.enriched_category,int(r.intervals),f'{r.length_m/1000:.3f}'] for r in changes.itertuples()]
    unresolved=data[~data.tags_applied]
    conflict_rows=[[r.source_id,r['name'],f'{r.id_geometry_max_offset_m:.2f}',r.match_method,int(r.fallback_qualified_count)] for _,r in unresolved.iterrows()]
    restricted=data[data.service_group.eq('explicit_access_restriction')]
    qualified=sum(data.tags_applied)
    qareport=f'''# NUS OSM attribute enrichment and grouped-review QA

Prepared (Singapore): {result['created_singapore']}. Scope: the same **763 NUS candidate intervals / 28.688023 km**, including 590 service intervals. No whole-island road analysis or live-site change.

## Updated result and comparison

{markdown_table(['Category','Previous intervals','Updated intervals','Updated km'],count_rows)}

The categories retain every original candidate interval, geometry and fragment_uid. Existing website seg_id values are never changed. Eligible remains provisional; the outputs do not certify public ownership or change proposal publication rules.

{markdown_table(['Previous category','Updated category','Intervals','km'],change_rows)}

Parking aisles and driveways remain in manual review, consistent with the preceding classification policy. Their subtype is now evidence-based where tagged, so a reviewer can make a grouped policy decision. Explicit private/no/destination/permit restrictions also stay visible for review. No service-road category is automatically excluded en masse. The zero excluded count, if present, means no newly corroborated non-road feature entered this candidate pool; previously excluded paths remain a separate context layer.

## Raw data and recovered tags

The original Shapefile contains only osm_id, name, ref, type, oneway, bridge and maxspeed. It does not retain all original OSM tags.

Raw file: local-data/osm/pbf/Singapore.osm.pbf, downloaded from [the user-specified BBBike URL](https://download.bbbike.org/osm/bbbike/Singapore/Singapore.osm.pbf).
PBF SHA-256: `{result['pbf_sha256']}`.
PBF snapshot: `{result['pbf_snapshot'].get('osmosis_replication_timestamp','unknown')}`. This is the snapshot timestamp, not the download date or a guarantee of current ground conditions.

The PBF was streamed to extract 4,516 nearby highway ways and 175 barrier nodes, retaining full geometry, all available way tags as JSON, version/timestamp and node IDs. No island-wide conflation was run. The PBF download and extraction manifests record file sizes, HTTP metadata, bounds and snapshot data.

Tag presence after reliable linkage (missing tags remain missing):

{markdown_table(['Tag','All 763 intervals','Of 590 service intervals','All tagged length km'],coverage_rows)}

Recovering a way's tags does not imply that all requested keys are present. Geometry-verified links recover attributes for {qualified} intervals. Coverage and tag combinations are in recovered_tag_coverage.csv and classification_summary.csv. Original source attributes are retained separately; recovered tags use the osm_ prefix.

## Identifier validation and spatial fallback

- All candidate source IDs were checked as possible OSM way IDs. They were not accepted on identity alone, especially for the processed primary data whose provenance remains unverified.
- Validation samples every <=2 m, including interval endpoints. It requires maximum offset <=1 m, 95th-percentile offset <=0.5 m, projected length ratio >=75%, >=95% actual overlap in a 1 m flat-ended way corridor, and median local angle <=15 degrees (or virtually coincident geometry <2 cm).
- If the ID fails, a 5 m spatial search evaluates compatible classes and names with the same geometry requirements. A unique qualifying fallback may supply tags; multiple or zero qualifying ways remain unresolved. Unverified same-ID tags are stored separately and never silently applied.
- Match counts: {json.dumps(result['matches'])}.

Unresolved links:

{markdown_table(['Original source ID','Name','Max same-ID offset m','Method','Qualified alternatives'],conflict_rows)}

OSM_way_link_audit.csv records metrics and fallback alternatives for every interval. An identifier-plus-geometry association supports use of this current OSM tag record; it does not prove original LTA geometry provenance. Different snapshots, source editing and shifted centreline fragments can still require review.

## Service-road decisions

{markdown_table(['Recovered evidence group','Eligibility','Intervals','km'],service_rows)}

The service evidence groups distinguish: positive tagged motor access; tagged parking/driveway/special access; explicit restrictions; and insufficient purpose/access/link evidence. Restrictions take precedence in this table, so a private driveway belongs to the restriction group but retains osm_service=driveway in the register.

Eligibility requires the earlier spatial/grade/boundary safeguards as well as positive permission evidence for a newly promoted service road. Explicit access=yes/permissive, or a more-specific positive vehicle tag, can support a likely accessible vehicular route. Parking/development-name context, restricted or conflicting mode tags, barrier restrictions, parking/driveway subtype and unresolved geometry keep it uncertain.

Missing access tags never mean public access. Named campus roads with lanes/sidewalk/turn-marking evidence remain in scope and are prioritised, even when permissions are insufficient to promote them. Lanes/sidewalks establish route function, not legal permission. Generic residential roads may retain their earlier provisional road-type eligibility where no conflicting evidence appears; this is not a newly verified public-access decision.

Associated barrier restrictions are tested only when a tagged node lies within 2 m of the particular candidate interval. This is supporting evidence, not a complete routing/gate-access model. {len(restricted)} intervals have explicit restrictive way evidence; barrier and inherited spatial concerns are separately recorded.

Tag interpretation references: [OSM access](https://wiki.openstreetmap.org/wiki/Key:access), [service subtypes](https://wiki.openstreetmap.org/wiki/Key:service), and [permissive access](https://wiki.openstreetmap.org/wiki/Tag:access%3Dpermissive). Permissive indicates owner-granted access, not public ownership or an irrevocable right. Motor_vehicle then vehicle then access provides the reported motor permission; explicit conflicts with general private/no access remain review cases. Foot restrictions are evaluated separately.

## Grouped manual review and priorities

The updated {result['manual_intervals']} uncertain intervals are consolidated into **{result['manual_review_groups']} compact road-review groups**, then organised into **{result['manual_review_batches']} prioritised review batches**. Original way-level rows are also available; grouping by way alone offers little reduction because many source intervals already correspond to distinct ways.

- First link fragments to verified current OSM way identities; retain unresolved source identities explicitly.
- Named roads join by name, consistent category/access/evidence regime and <=15 m spatial continuity. They are corridor-review groups, not merged analytical road geometry.
- Unnamed roads join in fixed 200 m neighbourhood cells using shared OSM nodes or <=3 m endpoint-to-line connections. Different grades, access regimes, purposes and geometry-risk cases remain separate.
- Group IDs hash member fragment IDs deterministically. No analytical segment IDs or geometry are modified.
- Road-group CSV rows include actual subtype/access values, decision reasons, link method and barrier evidence. Permission and service-subtype regimes are kept separate even within restricted-access areas.
- prioritised_review_batches.csv combines named-corridor subgroups or roads in 400 m local policy areas with consistent subtype and permission evidence. Area batches can be disconnected and are explicitly not physical road identities or blanket approvals. Group and interval memberships remain traceable.
- Kent Ridge Crescent/Drive and named NUS internal roads receive first priority. Geometry-link/displaced cases and connected unknown-purpose roads follow. Explicit restrictions and identified parking/driveways can be assessed as coherent policy groups.

All-priority groups include already eligible Kent Ridge roads for corridor verification; grouped_manual_review.csv contains only updated uncertain intervals. group_membership.csv preserves the interval-to-group link; way_level_review_groups.csv records original-way grouping. Candidate-pool grouping does not silently reclassify the older spatial-review context outside these 763 intervals.

Top uncertain groups (R numbers match the maps and all-priority CSV):

{markdown_table(['Map rank','Road / area','Intervals','Metres','Review action'],top)}

## Deliverables and visual checks

- nus_enriched.gpkg: existing website roads, all enriched candidates, A/B/C candidate layers, manual-review group and batch geometry, all priority groups, verified matched PBF ways, and prior excluded/spatial-review context. Default blue/green/grey/orange layer styles are embedded.
- nus_enriched_closeup.png: 300 dpi NUS road overview with priority group labels.
- remaining_review_groups.png: 300 dpi close-ups of campus service corridors, geometry conflicts and remaining uncertain groups. Dashed cyan shows same-ID PBF geometry in unresolved examples.
- enriched_candidate_register.csv: original IDs and all recovered tags, effective permission, linkage evidence, decision and group membership.
- grouped_manual_review.csv: one row per prioritised uncertain road group, with source-way IDs, member fragment IDs, lengths, permission evidence and review action.
- prioritised_review_batches.csv: a shorter work queue for corridor and local-area policy review, linked back to every road group and interval.
- classification_change_matrix.csv and classification_summary.csv: comparison with 161 eligible / 602 uncertain, plus class/access/subtype totals.

Maps compare local datasets; no basemap, field survey or independent street-condition verification was performed. “Likely accessible” is an evidence-qualified candidate status, not deployment approval. Campus connector roads remain in review and in scope where access is not established.

## Reproducibility and preservation

The existing isolated Python environment now includes pyosmium. Pinned additional requirements are in requirements-enrichment.txt. APIs follow [pyosmium's handler documentation](https://docs.osmcode.org/pyosmium/latest/user_manual/05-Working-with-Handlers/).

```powershell
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' 'website-plan/road-conflation/fetch_osm_pbf.py'
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' 'website-plan/road-conflation/extract_nus_pbf.py'
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' 'website-plan/road-conflation/enrich_candidates.py'
```

All outputs stay in Git-ignored local-data/osm/pbf and local-outputs/conflation/nus-enriched. Prior NUS outputs, original inputs, website, Apps Script backend, existing 55,115 segment IDs and three-proposal publication settings are protected by final SHA-256 checks in preservation_check.json. No whole-island analysis, commit or push occurred.
'''
    (output/'QA_ENRICHMENT.md').write_text(qareport,encoding='utf-8')
