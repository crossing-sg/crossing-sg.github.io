const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {ROOT,createBackend,body}=require('../road-conflation/backend_harness.cjs');
const roads=require('../../website/js/proposal-roads.js');
const geometry=require('../../website/js/road-geometry.js');
const directory=path.join(ROOT,'website/data/osm-complete/proposal-roads');
const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json')));
const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures.json'))).positive;
const backend=()=>createBackend({dataDirectory:directory});
const request=(f,patch={})=>body(f,{registry_version:manifest.version,...patch});

test('generated backend pin and frontend configuration identify the exact new release',()=>{
    const source=fs.readFileSync(path.join(ROOT,'apps-script/RegistryConfig.gs'),'utf8');
    assert.ok(source.includes(manifest.version));
    assert.ok(source.includes(crypto.createHash('sha256').update(fs.readFileSync(path.join(directory,'manifest.json'))).digest('hex')));
    assert.ok(fs.readFileSync(path.join(ROOT,'website/js/site-config.js'),'utf8').includes(manifest.version));
});
test('all available highway categories and previously excluded service/access fixtures submit privately',()=>{
    const b=backend();
    const stats=JSON.parse(fs.readFileSync(path.join(__dirname,'statistics.json')));
    assert.deepEqual(Object.keys(stats.highway_categories).sort(),Object.keys(fixtures).filter(k=>stats.highway_categories[k]).sort());
    for(const [label,f] of Object.entries(fixtures)){
        const n=b.ctx.neighborhood(f.a,f.b),r=geometry.choose(f.a,f.b,n.features,n.guards);
        assert.equal(r.ok,true,label);assert.equal(r.feature.properties.seg_id,f.seg_id,label);
        assert.equal(b.post(request(f)).ok,true,label);
    }
    assert.deepEqual(b.get().segments,[]);
    assert.equal(b.sheets.get('proposals').values.length,Object.keys(fixtures).length+1);
});
test('new OSM proposal persists canonical identity/distance, then publishes and resolves for Explore',async()=>{
    const b=backend(),f=fixtures.footway;
    for(let i=0;i<3;i++)assert.equal(b.post(request(f,{dist_m:999})).ok,true);
    assert.equal(b.sheets.get('proposals').values[1][1],f.seg_id);
    assert.equal(b.sheets.get('proposals').values[1][2],'');
    b.approveAll();const s=b.get().segments[0];assert.equal(s.seg_id,f.seg_id);assert.equal(s.count,3);assert.ok(s.line);
    global.SITE={proposalNetworkVersion:manifest.version};
    global.fetch=async url=>new Response(fs.readFileSync(path.join(ROOT,'website',url)));
    const store=new roads.Store('data/osm-complete/proposal-roads');
    const canonical=await store.feature(s.seg_id);
    assert.equal(canonical.properties.highway,'footway');assert.equal(canonical.properties.osm_id,f.properties.osm_id);
    assert.ok(geometry.hits(f.a,f.b,canonical.geometry).length);
    assert.equal(roads.publicSegments(b.get()).length,1);
});
test('legacy v2 records retain aggregates and lines across the additive release',()=>{
    const b=backend(),f=fixtures.footway;
    for(let i=0;i<3;i++)assert.equal(b.post(request(f)).ok,true);
    b.approveAll();const sh=b.sheets.get('proposals');
    // Use an actual prior-release geometry to verify version migration.
    const old=JSON.parse(fs.readFileSync(path.join(ROOT,'website-plan/road-conflation/fixtures/crossings-v1.json'))).positive.existing;
    for(const row of sh.values.slice(1)){
        row[1]=old.seg_id;row[3]=old.a[0];row[4]=old.a[1];row[5]=old.b[0];row[6]=old.b[1];row[13]=manifest.compatible_versions[0];
    }
    const s=b.get().segments[0];assert.equal(s.seg_id,old.seg_id);assert.equal(s.count,3);assert.ok(s.line);
});
test('compressed visible-area loader deduplicates tile borders and bounds requests',async()=>{
    global.SITE={proposalNetworkVersion:manifest.version};const seen=[];
    global.fetch=async url=>{seen.push(url);return new Response(fs.readFileSync(path.join(ROOT,'website',url)));};
    const store=new roads.Store('data/osm-complete/proposal-roads'),f=fixtures.service;
    await store.init();assert.equal(seen.length,1);
    const n=await store.area([f.a[0]-.0005,f.a[1]-.0005,f.a[0]+.0005,f.a[1]+.0005]);
    assert.equal(new Set(n.features.map(f=>f.properties.seg_id)).size,n.features.length);
    assert.ok(n.features.some(v=>v.properties.seg_id===f.seg_id));assert.ok(store.metrics.peakConcurrent<=4);
    await assert.rejects(store.area([103.48,1.1,104.6,1.55]));
    const count=seen.length;await store.area([f.a[0]-.0005,f.a[1]-.0005,f.a[0]+.0005,f.a[1]+.0005]);assert.equal(count,seen.length);
});
test('forged IDs, stale release and oversized crossing never reach storage',()=>{
    const b=backend(),f=fixtures.service;
    for(const p of [{seg_id:99999999},{registry_version:'old'},{b:[f.a[0],f.a[1]+.01]},{a:[0,0]}])assert.equal(b.post(request(f,p)).ok,false);
    assert.equal(b.sheets.get('proposals').values.length,1);
});
