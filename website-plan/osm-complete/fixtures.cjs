/* Find short, unambiguous placements on actual newly added geometry. */
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib');
const {createBackend,ROOT}=require('../road-conflation/backend_harness.cjs');
const geometry=require('../../website/js/road-geometry.js');
const directory=path.join(ROOT,'website/data/osm-complete/proposal-roads');
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json')));
const read=p=>JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(directory,p))));
const positive={},backend=createBackend({dataDirectory:directory});
function candidate(feature){
    const coords=feature.geometry.coordinates;
    if(feature.geometry.type!=='LineString')return null;
    for(let j=1;j<coords.length;j++){
        const a=coords[j-1],b=coords[j];
        if(geometry.metres(a,b)<.02)continue;
        const center=[(a[0]+b[0])/2,(a[1]+b[1])/2],cos=Math.cos(center[1]*Math.PI/180);
        const dx=(b[0]-a[0])*cos,dy=b[1]-a[1],norm=Math.hypot(dx,dy);
        for(const span of [3,5,8]){
            const v=[-dy/norm*span/(111195*cos),dx/norm*span/111195];
            const p=center.map((c,k)=>Number((c-v[k]).toFixed(6))),q=center.map((c,k)=>Number((c+v[k]).toFixed(6)));
            const neighborhood=backend.ctx.neighborhood(p,q),result=geometry.choose(p,q,neighborhood.features,neighborhood.guards);
            if(result.ok&&result.feature.properties.seg_id===feature.properties.seg_id){
                return {a:p,b:q,seg_id:feature.properties.seg_id,dist_m:feature.properties.dist_m,properties:feature.properties};
            }
        }
    }
    return null;
}
for(const tile of manifest.tiles){
    for(const f of read(tile.url).features){
        const p=f.properties;
        if(p.source!=='osm')continue;
        const labels=[p.highway];
        if(p.access==='private')labels.push('private_access');
        if(p.service==='parking_aisle')labels.push('parking_aisle');
        if(p.service==='driveway')labels.push('driveway');
        if(labels.every(k=>positive[k]))continue;
        const placement=candidate(f);
        if(placement)for(const key of labels)positive[key]??=placement;
    }
    if(Object.keys(positive).length>=36)break;
}
const originals=JSON.parse(fs.readFileSync(path.join(ROOT,'website-plan/road-conflation/fixtures/crossings-v1.json'))).positive;
for(const key of ['existing','Kent Ridge Drive']){
    const f=originals[key],n=backend.ctx.neighborhood(f.a,f.b),r=geometry.choose(f.a,f.b,n.features,n.guards);
    if(r.ok&&r.feature.properties.seg_id===f.seg_id)positive[key]=f;
}
fs.writeFileSync(path.join(__dirname,'fixtures.json'),JSON.stringify({version:manifest.version,positive,note:'Synthetic test placements, never sent to a live backend.'},null,2)+'\n');
console.log('Matched fixtures:',Object.keys(positive));
if(!positive.footway||!positive.service||!positive.private_access||!positive.parking_aisle)throw Error('Required fixtures missing');
