/* Exhaustive supplementary-ID geometric reachability, without any submissions.
 * This does not establish road width, legal access or physical crossing safety.
 */
const fs=require('node:fs'),path=require('node:path');
const {ROOT}=require('./backend_harness.cjs'),G=require('../../website/js/road-geometry.js');
const BASE=path.join(ROOT,'website/data/proposal-roads'),OUT=path.join(ROOT,'local-outputs/integration-qa');
const manifest=JSON.parse(fs.readFileSync(path.join(BASE,'manifest.json'))),cache=new Map();
function bounds(f){
    const lines=f.geometry.type==='LineString'?[f.geometry.coordinates]:f.geometry.coordinates;
    const b=[Infinity,Infinity,-Infinity,-Infinity];
    for(const l of lines)for(const p of l){b[0]=Math.min(b[0],p[0]);b[1]=Math.min(b[1],p[1]);b[2]=Math.max(b[2],p[0]);b[3]=Math.max(b[3],p[1]);}
    return b;
}
function overlap(a,b){return a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1];}
function tile(t){
    if(!cache.has(t.key)){
        const pair=[t.url,t.guard_url].map(p=>JSON.parse(fs.readFileSync(path.join(BASE,p))).features.map(f=>({f,b:bounds(f)})));
        cache.set(t.key,pair);
    }
    return cache.get(t.key);
}
function neighborhood(a,b){
    const q=[Math.min(a[0],b[0])-.00005,Math.min(a[1],b[1])-.00005,Math.max(a[0],b[0])+.00005,Math.max(a[1],b[1])+.00005];
    const maps=[new Map(),new Map()];
    for(const t of manifest.tiles)if(overlap(t.bbox,q)){
        tile(t).forEach((list,i)=>list.forEach(r=>{if(overlap(r.b,q))maps[i].set(i?r.f.id:r.f.properties.seg_id,r.f);}));
    }
    return {features:[...maps[0].values()],guards:[...maps[1].values()]};
}
function placement(g,fraction,width){
    const coords=g.type==='LineString'?g.coordinates:g.coordinates[0];
    const distances=coords.slice(1).map((p,i)=>G.metres(coords[i],p)),sum=distances.reduce((a,b)=>a+b,0);
    let at=sum*fraction,i=0;while(i<distances.length-1&&at>distances[i])at-=distances[i++];
    const a=coords[i],b=coords[i+1],t=distances[i]?at/distances[i]:.5;
    const c=[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t],cos=Math.cos(c[1]*Math.PI/180);
    const v=[(b[0]-a[0])*cos,b[1]-a[1]],l=Math.hypot(...v),n=[-v[1]/l,v[0]/l];
    return [-1,1].map(s=>[Number((c[0]+s*n[0]*width/2/(111195*cos)).toFixed(6)),Number((c[1]+s*n[1]*width/2/111195).toFixed(6))]);
}
const started=Date.now(),records=[],reviewFeatures=[];
for(const number of Object.keys(manifest.registry_blocks)){
    const block=JSON.parse(fs.readFileSync(path.join(BASE,'registry',number+'.json')));
    for(const [id,row] of Object.entries(block.segments)){
        const sid=Number(id);if(sid<=57987)continue;
        let success=null,trials=0;const reasons={};
        for(const fraction of [.5,.25,.75]){
            for(const width of [24,12,6]){
                const [a,b]=placement(row.g,fraction,width),near=neighborhood(a,b),r=G.choose(a,b,near.features,near.guards);trials++;
                if(r.ok&&r.feature.properties.seg_id===sid){success={a,b,width,fraction};break;}
                const reason=r.ok?'adjacent_shared_endpoint_canonical_id':r.reason;reasons[reason]=(reasons[reason]||0)+1;
            }
            if(success)break;
        }
        records.push({seg_id:sid,reachable:!!success,trials,...(success||{}),reasons});
        if(!success)reviewFeatures.push({type:'Feature',id:sid,properties:{seg_id:sid,reason_presence:JSON.stringify(reasons),
            review:'No reliable placement in the sampled set; retain geometry and inspect alternative placement, road topology and guard context.'},geometry:row.g});
    }
}
if(records.length!==14006)throw Error('Supplementary count changed');
const failed=records.filter(r=>!r.reachable),reasons={};for(const r of failed)for(const key of Object.keys(r.reasons))reasons[key]=(reasons[key]||0)+1;
const result={schema:1,version:manifest.version,tested:records.length,reachable:records.length-failed.length,needs_targeted_review:failed.length,
    failure_reason_presence_counts:reasons,seconds:(Date.now()-started)/1000,
    scope:'Up to nine synthetic perpendicular A/B placements per supplementary segment, at 25/50/75% and widths 24/12/6m. A failed sample set is not proof that no valid placement exists. A passing placement is not a physical/road-width/access safety assessment.'};
fs.writeFileSync(path.join(OUT,'supplementary-selection-summary.json'),JSON.stringify(result,null,2));
const columns=['seg_id','reachable','trials','width','fraction','a','b','reasons'];
const csv=[columns.join(',')].concat(records.map(r=>columns.map(k=>'"'+String(typeof r[k]==='object'?JSON.stringify(r[k]):r[k]??'').replaceAll('"','""')+'"').join(','))).join('\n');
fs.writeFileSync(path.join(OUT,'supplementary-selection.csv'),csv);
fs.writeFileSync(path.join(OUT,'selection-review-priority.json'),JSON.stringify(failed,null,2));
fs.writeFileSync(path.join(OUT,'selection-review.geojson'),JSON.stringify({type:'FeatureCollection',features:reviewFeatures}));
console.log(JSON.stringify(result,null,2));
