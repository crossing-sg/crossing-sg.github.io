"""Local NUS classification QA maps and report; no external map/data requests."""
from pathlib import Path
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from refine_candidates import A,B,C,COLORS,NON_ROADS,OUT_OF_SCOPE


def markdown(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in rows])


def create_maps(output,layers,parents,core):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    output=Path(output)
    website=layers['website_roads']
    eligible=layers['A_eligible_candidates']
    manual=layers['C_manual_candidates']
    context=layers['C_spatial_review_context']
    excluded=layers['B_excluded_context']
    # Rendering-only de-duplication of source representations; layers retain all records.
    def render_unique(data):
        keys=shapely.to_wkb(shapely.normalize(shapely.set_precision(data.geometry.to_numpy(),.05)))
        return data.loc[~pd.Series(keys,index=data.index).duplicated()]
    context=render_unique(context)
    excluded=render_unique(excluded)
    legend=[Line2D([0],[0],color=COLORS['existing'],lw=2,label='Existing website roads'),
            Line2D([0],[0],color=COLORS[A],lw=2,label='A: eligible vehicular candidates'),
            Line2D([0],[0],color=COLORS[B],lw=1,ls='--',label='B: excluded source context'),
            Line2D([0],[0],color=COLORS[C],lw=2,label='C: manual / spatial review')]

    def draw(ax,bounds):
        from shapely.geometry import box
        region=box(*bounds)
        for data,color,width,alpha,style,z in [
            (excluded,COLORS[B],.55,.55,'--',1),
            (context,COLORS[C],.85,.65,'-',2),
            (manual,COLORS[C],1.65,.95,'-',3),
            (eligible,COLORS[A],2.,1.,'-',4),
            (website,COLORS['existing'],1.8,1.,'-',5)]:
            view=data.loc[data.geometry.intersects(region)]
            if len(view):view.plot(ax=ax,color=color,linewidth=width,alpha=alpha,linestyle=style,zorder=z)
        ax.set_xlim(bounds[0],bounds[2]);ax.set_ylim(bounds[1],bounds[3]);ax.set_aspect('equal')
        ax.set_facecolor('#faf9f5');ax.ticklabel_format(useOffset=False,style='plain')
        ax.set_xlabel('SVY21 easting (m)');ax.set_ylabel('SVY21 northing (m)')
        ax.grid(alpha=.15)

    def label_roads(ax,names):
        for name in names:
            data=parents[(parents.dataset=='processed_lta') & parents.name.eq(name)]
            if not len(data):continue
            road=data.loc[data.length_m.idxmax()]
            p=road.geometry.interpolate(.5,normalized=True)
            xmin,xmax=ax.get_xlim();ymin,ymax=ax.get_ylim()
            if xmin<=p.x<=xmax and ymin<=p.y<=ymax:
                ax.annotate(name,(p.x,p.y),xytext=(6,7),textcoords='offset points',fontsize=9,
                            bbox=dict(facecolor='white',edgecolor='none',alpha=.88),zorder=10)

    for filename,bounds,title,size in [
        ('nus_refined_overview.png',core.bounds,'NUS pilot: refined crossing-road eligibility',(11,13)),
        ('nus_kent_ridge_focus.png',None,'Kent Ridge Crescent / Drive and campus internal roads',(10,13))]:
        if bounds is None:
            named=parents[(parents.dataset=='processed_lta') & parents.name.isin(['Kent Ridge Crescent','Kent Ridge Drive'])]
            west,south,east,north=named.total_bounds
            bounds=(west-120,south-120,east+120,north+120)
        fig,ax=plt.subplots(figsize=size,layout='constrained')
        draw(ax,bounds)
        label_roads(ax,['Kent Ridge Crescent','Kent Ridge Drive','Computing Drive','Engineering Drive 1','Research Link'])
        ax.set_title(title+'\nEligible is provisional; public access and service subtypes remain unverified.',fontsize=13,pad=12)
        fig.legend(handles=legend,loc='outside lower center',ncol=2,fontsize=9,framealpha=.95)
        fig.savefig(output/filename,dpi=300)
        plt.close(fig)

    choices=[]
    for name,title in [('Kent Ridge Crescent','Confirmed coverage gap in website geometry'),('Kent Ridge Drive','Confirmed coverage gap in website geometry')]:
        possible=eligible.loc[eligible.name.eq(name)].sort_values('length_m',ascending=False)
        if len(possible):choices.append((title,possible.iloc[0],'original candidate / A'))
    parking=manual.loc[manual.parking_name_hint].sort_values('length_m',ascending=False)
    if not len(parking):parking=manual.loc[manual.road_class.eq('service')].sort_values('length_m',ascending=False)
    if len(parking):choices.append(('Service / parking access: manual review',parking.iloc[0],'original candidate / C'))
    uncertain=parents[(parents.dataset=='processed_lta') & parents.name.eq('Clementi Road') & parents.reason.fillna('').str.contains('displacement_or_parallel')]
    if len(uncertain):choices.append(('Displaced or parallel: unresolved',uncertain.sort_values('length_m',ascending=False).iloc[0],'previous spatial review context'))
    fig,axes=plt.subplots(2,2,figsize=(14,13),layout='constrained')
    examples=[]
    for ax in axes.flat:ax.set_visible(False)
    for ax,(title,selected,scope) in zip(axes.flat,choices):
        ax.set_visible(True)
        point=selected.geometry.interpolate(.5,normalized=True)
        radius=max(85,min(160,selected.length_m*.6))
        bounds=(point.x-radius,point.y-radius,point.x+radius,point.y+radius)
        draw(ax,bounds)
        gpd.GeoSeries([selected.geometry],crs=3414).plot(ax=ax,color='#5a286d',linewidth=3.5,linestyle=':',zorder=8)
        name=selected['name'] or '(unnamed)'
        ax.set_title(title+'\n'+name+' | source '+str(selected.source_id),fontsize=11)
        examples.append(dict(label=title,name=name,dataset=selected.dataset,source_id=str(selected.source_id),
                             uid=selected.get('fragment_uid',selected.uid),scope=scope,
                             easting=point.x,northing=point.y,public_access='unverified',
                             qualification='Confirmed absence from supplied website geometry, not independent ground/ownership verification.' if '/ A' in scope else 'Unresolved; no automatic acceptance or deletion.'))
    fig.legend(handles=legend+[Line2D([0],[0],color='#5a286d',lw=3,ls=':',label='Selected example')],loc='outside lower center',ncol=3)
    fig.suptitle('NUS refinement: website coverage gaps and ambiguous cases',fontsize=15)
    fig.savefig(output/'nus_refined_examples.png',dpi=300)
    plt.close(fig)
    pd.DataFrame(examples).to_csv(output/'visual_review_examples.csv',index=False)
    return examples


def create_report(output,result,refined,layers,attribution):
    output=Path(output)
    counts=result['categories']
    summary=pd.read_csv(output/'classification_summary.csv')
    original=pd.read_csv(output/'original_candidate_audit.csv')
    order=pd.read_csv(output/'source_order_comparison.csv')
    geometry=json.loads((output/'source_geometry_comparison.json').read_text())
    original_rows=[[r.dataset,r.road_class,'unknown: absent field',int(r.intervals),f'{r.length_m/1000:.3f}'] for r in original.itertuples()]
    refined_rows=[[r.category,r.dataset,r.road_class,int(r.intervals),f'{r.length_m/1000:.3f}'] for r in summary.itertuples()]
    count_rows=[[label,counts[key]['intervals'],f"{counts[key]['length_m']/1000:.3f}"] for key,label in [(A,'A — Eligible vehicular candidates'),(B,'B — Excluded from the original candidates'),(C,'C — Manual review')]]
    order_rows=[[r.experiment,int(r.intervals),int(r.distinct_source_ids),f'{r.length_m/1000:.3f}'] for r in order.loc[order.fragment_kind=='missing'].itertuples()]
    service=refined[refined.road_class.eq('service')]
    parking=refined[refined.parking_name_hint]
    driveway=refined[refined.entrance_driveway_name_hint]
    risks=refined[refined.spatial_flag.ne('')]
    access_unknown=int(refined.access_status.eq('not_available').sum())
    attr_rows=[[r['primary_reference_role'],f"{r['osm_matched_length_m']/1000:.3f}"] for r in attribution['attribution']]
    reverse=json.loads((output/'osm_first_missing_primary_attribution.json').read_text())
    reverse_rows=[[r['primary_reference_role'],f"{r['osm_matched_length_m']/1000:.3f}"] for r in reverse['attribution']]
    name_rows=[]
    for (name,category),group in refined[refined.name.isin(['Kent Ridge Crescent','Kent Ridge Drive','Computing Drive','Engineering Drive 1','Research Link'])].groupby(['name','category']):
        name_rows.append([name,category,len(group),f'{group.length_m.sum()/1000:.3f}'])
    context_rows=[]
    for name in ['B_excluded_context','C_spatial_review_context']:
        data=layers[name]
        context_rows.append([name,len(data),f'{data.geometry.length.sum()/1000:.3f}'])
    missing_fields=json.loads((output/'access_attribute_availability.json').read_text())
    known_schemas='\n'.join('- '+name+': `'+', '.join(info['available_fields'])+'`.' for name,info in missing_fields.items())
    qa=f'''# NUS candidate refinement QA

Created (Singapore): {result['created_singapore']}. Scope: existing NUS 10 m pilot only. No whole-island analysis, website/backend change, original-data edit, or original pilot overwrite.

## Result for the original 763 candidate intervals

Original count: **763 intervals**, **{result['original_length_m']/1000:.6f} km**, representing 757 source IDs across both datasets. These are source intervals, not necessarily 50 m website segments.

{markdown(['Category','Intervals','Length (km)'],count_rows)}

The categories partition the original 763 intervals without splitting, deleting, modifying or renumbering them. All original fragment_uid values and geometry are retained. Existing website segment IDs remain unchanged. A is eligibility by vehicular road type and conservative spatial checks; public access is not certified, and nothing is published or allocated a new numeric seg_id.

## Original classification, source and access audit

{markdown(['Source','Road class','Access evidence','Intervals','Length (km)'],original_rows)}

No footways, cycleways, steps or pedestrian-only paths occur among the original 763 candidates. They were filtered out by the earlier pilot, so B contains zero original candidate intervals. The map still shows excluded source context so these paths can be inspected separately.

There are **{len(service)} service intervals / {service.length_m.sum()/1000:.3f} km**. All supplied service roads default to C because service subtypes and access restrictions are unavailable. Named campus service roads remain in C; a familiar road name is not evidence that it is a public, appropriate crossing-proposal road.

Access restrictions are **unknown for {access_unknown} / 763 original intervals**. Confirmed counts of private driveways and parking aisles cannot be determined from these files. Name clues flag {len(parking)} intervals / {parking.length_m.sum()/1000:.3f} km mentioning parking, and {len(driveway)} intervals / {driveway.length_m.sum()/1000:.3f} km mentioning entrance/exit/driveway/private/condo. These overlapping clues are review aids, not authoritative restrictions or subtype assignments.

Actual raw schemas inspected:

{known_schemas}

Neither input includes access, vehicle, motor_vehicle, motorcar, service, foot or bicycle restriction/subtype fields. Unknown is never converted to unrestricted. No external tags, assumptions from osmid names, or ownership inference were added.

## Refined classification rules and breakdown

- A: residential/living-street/primary/secondary/tertiary/unclassified vehicular classes with no identified spatial, grade, boundary or access conflict. Appropriate service roads can be A only with explicit positive access plus an unambiguous supported subtype; none of the current service records supplies that evidence.
- B: footways, pedestrian paths, cycleways, steps, generic paths, bridleways, corridors, elevators and similarly unsuitable features. Motorways, motorway links and non-operational construction/proposed features are also out of crossing-proposal scope. This is exclusion from candidate eligibility, not deletion of source geometry.
- C: all ambiguous service roads, explicit restricted/private/parking/driveway records if present, links/unknown classes needing crossing-suitability review, independent-parallel evidence, unresolved parent matches, grade concerns, clipped pilot-boundary sources and newly detected possible displaced/parallel representations.
- Names such as Car Park Entrance Way are hints only. A service road called Computing Drive or Engineering Drive remains available in C for a knowledgeable reviewer to verify; it is not automatically discarded.

{markdown(['Category','Source','Class','Intervals','Length (km)'],refined_rows)}

Selected NUS roads:

{markdown(['Name','Category','Intervals','Length (km)'],name_rows)}

Full per-interval decisions, reasons, access status, name hints, parent status and spatial diagnostics: candidate_review_register.csv. Grouped source/class/access/category totals: classification_summary.csv.

## Spatial recheck of possible displaced existing roads

An independent audit samples every candidate at <=2 m spacing, searches 50 m, and requires local direction <=30 degrees, projected length correspondence >=30%, endpoint overshoot <=5 m, and actual flat-ended corridor overlap. A >=60% aligned/overlap fraction within 20 m, or >=80% within 30 m, creates a review flag. >=80% close alignment within 3 m plus corridor overlap also flags a possible existing-road duplicate. Distance alone never accepts or deletes a road.

**{len(risks)} original intervals / {risks.length_m.sum()/1000:.3f} km** received additional spatial-review flags. Some may be genuine nearby parallel roads or valid junction connectors; all remain visible in C. Parent uncertainty, independent parallel evidence and access classification can create additional C records. This intentionally favours review over false certainty. Details: independent_spatial_audit.csv.

Close-duplicate flags: {int(refined.spatial_flag.eq('possible_duplicate_existing_road').sum())}; within-20 m displaced/parallel flags: {int(refined.spatial_flag.eq('possible_displacement_or_parallel_within_20m').sum())}; wider-30 m flags: {int(refined.spatial_flag.eq('possible_wide_displacement_or_parallel_within_30m').sum())}. These diagnostics do not independently confirm a mistaken match or a genuine parallel road.

The older 0.5 m duplication audit did not establish that every candidate was missing: larger shifts, tangent/window differences and partial matches can still be ambiguous. This wider audit directly tests those cases. It does not claim every flag is an error in the earlier matcher.

## Why 761 primary intervals but only two further OSM fragments?

1. **Sequential reference coverage is the main attribution mechanism.** In the original run, primary roads were considered first. OSM was then compared with the website plus all eligible primary intervals, including unresolved ones. Every original matched OSM parent selected processed-primary references. The two new OSM intervals are both from one service source ID, 1569622212: its parent is 41.093 m, with 31.093 m labelled missing and 10 m uncertain. Both fragments now remain in C.
2. **The current geometries overlap extensively.** Of {geometry['primary_clipped_parts']} clipped primary parts, {geometry['primary_parts_also_in_OSM_at_5cm']} also occur in OSM on a 5 cm precision grid; OSM has {geometry['osm_clipped_parts']} clipped parts. This describes current-file geometry, not original LTA/OSM provenance.
3. **Segmentation changes counts.** The 761 primary candidate intervals represent 756 source IDs; the two OSM fragments represent one ID. Splitting alone creates five additional primary intervals and one additional OSM interval. One source feature is not one website segment.
4. **Road classification dominates crossing eligibility.** {len(service)} of 763 intervals are service roads with unknown access/subtype. No non-road paths leaked into these candidates, but potentially unsuitable parking/driveway access remains hidden inside service. This refinement handles it explicitly.

The raw pilot contains {geometry['primary_legacy_scope_parts']} primary parts and {geometry['osm_legacy_scope_parts']} OSM parts inside the legacy drivable/review class scope. The net 22-part OSM excess consists of 19 more originally excluded parts and three more in-scope parts; it is not a 761-road coverage difference. Full source-class counts/lengths are in pilot_source_class_comparison.csv.

Order-only control using the same legacy matcher and class policy, NUS only:

{markdown(['Experiment','Missing intervals','Source IDs','Length (km)'],order_rows)}

The OSM-first run is a diagnostic, not another approved network. It isolates source order; residual differences also reflect geometry, coverage, class/grade metadata and partial-match rules. Those interacting effects cannot be uniquely divided into causal percentages without additional controlled policies and ground truth.

OSM-first missing length mapped to the original primary interval roles, using 5 m samples and a <=0.1 m coincident-geometry condition:

{markdown(['Original primary role or non-coincidence','OSM-first missing length (km)'],reverse_rows)}

This distinguishes geometry already represented as primary candidates from primary uncertainty and non-coincident geometry. It is a sampled diagnostic, not a new approved classification. Original layer/bridge/tunnel metadata differs between the sources; in particular OSM lacks layer and tunnel fields, so order controls need not produce identical uncertainty/connectivity outcomes.

Original matched OSM length, sampled against primary interval roles:

{markdown(['Primary interval role','OSM matched length (km)'],attr_rows)}

These are source-representation lengths, not additional or unique physical-road kilometres. Overlap with a primary candidate does not independently verify access or crossing suitability. Matched-versus-uncertain attribution uses 5 m sampled primary geometry; details and distances are recorded in osm_reference_attribution.json.

## QGIS and visual verification

Open **nus_refined.gpkg**. Core layers:

- website_roads: blue; all 204 existing pilot features, IDs and coordinates preserved.
- A_eligible_candidates: green; provisional road-type/spatial eligibility.
- B_excluded_candidates: original-candidate exclusions (empty here).
- C_manual_candidates: orange; unresolved original candidates.
- B_excluded_context: grey dashed; source context already excluded, plus non-road features previously held as spatial uncertainty.
- C_spatial_review_context: orange; earlier unresolved spatial intervals outside the original candidate pool.
- original_candidates: all 763, with category and evidence fields, for audit.
- pilot_boundary: fixed NUS analysis extent.

Default colour styles are embedded in the GeoPackage layer_styles table. Maps are 300 dpi with matching colours and legends:

- nus_refined_overview.png — original NUS extent and all four groups.
- nus_kent_ridge_focus.png — Kent Ridge Crescent / Drive and nearby campus roads.
- nus_refined_examples.png — two website-geometry coverage gaps plus service/parking and displaced/parallel review examples.

“Confirmed gap” on these maps means absent from the supplied website geometry. It does not certify present-day physical conditions, public ownership or pedestrian-crossing suitability. No basemap, satellite imagery or field survey was used. Named campus service roads can be visually followed in orange and reviewed without disappearing from the network.

Additional context (separate denominator; not added to the 763-category totals):

{markdown(['Context layer','Source intervals/features','Length (km)'],context_rows)}

Context combines overlapping primary and OSM representations; summed lengths are not unique road coverage. Rendering de-duplicates coincident context solely for legibility; the GeoPackage retains the source records.
Class/source counts and lengths for these separate context layers are in context_classification_audit.csv.

## Validation, preservation and remaining uncertainty

- A+B+C exactly preserves the 763 intervals and original total length, unique fragment IDs, feature order and exact geometry.
- Exported layers were reopened to check counts, validity, metric CRS, IDs and geometry; SQLite integrity checks passed.
- Existing 55,115 global segment IDs and all 204 pilot IDs are preserved. Final SHA-256 checks cover website/backend/tracked files, original inputs and previous pilot outputs. See refinement_manifest.json and preservation_check.json.
- No original Crossing Gap analysis, website/backend functionality, source data or previous pilot output was modified. No whole-island processing, commits or pushes occurred.
- Remaining: absent access/service subtype data, unverifiable private/parking status, primary provenance/history, close parallel-versus-displaced geometry, source metadata/grade omissions and lack of independent field-labelled ground truth. There is no automatic A assignment for ambiguous service/private/parallel roads and no automatic removal of C geometry.

Reproduce from repository root with the existing isolated interpreter:

```powershell
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' -m unittest discover -s 'website-plan/road-conflation' -v
& '.\\local-outputs\\road-conflation-venv\\Scripts\\python.exe' 'website-plan/road-conflation/refine_candidates.py'
```

This script has no whole-island mode and writes to local-outputs/conflation/nus-refined. Existing website IDs are never reassigned and new numeric IDs are not allocated.
'''
    (output/'QA_REFINEMENT.md').write_text(qa,encoding='utf-8')
