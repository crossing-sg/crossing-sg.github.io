const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {ROOT,createBackend,body}=require('./backend_harness.cjs');
const geometry=require('../../website/js/road-geometry.js');
const roads=require('../../website/js/proposal-roads.js');
const OUTPUT=path.join(ROOT,'local-outputs/integration-qa');
const manifest=JSON.parse(fs.readFileSync(path.join(ROOT,'website/data/proposal-roads/manifest.json')));
const legacy=JSON.parse(fs.readFileSync(path.join(ROOT,'website/data/gap_segments.geojson'))).features;
const examples=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/crossings-v1.json')));
assert.equal(examples.version,manifest.version);
const fixtures=examples.positive,negative=examples.negative;
const finder=createBackend();
function result(a,b){const n=finder.ctx.neighborhood(a,b);return geometry.choose(a,b,n.features,n.guards);}
fs.mkdirSync(OUTPUT,{recursive:true});
fs.writeFileSync(path.join(OUTPUT,'browser-fixtures.json'),JSON.stringify(fixtures,null,2));
fs.writeFileSync(path.join(OUTPUT,'negative-fixtures.json'),JSON.stringify(negative,null,2));

test('real existing and five NUS named-road fixtures pass exact shared validation',()=>{
    for(const f of Object.values(fixtures)){const r=result(f.a,f.b);assert.equal(r.ok,true);assert.equal(r.feature.properties.seg_id,f.seg_id);}
});
test('null and zero crossing distances remain distinct in the UI',()=>{
    assert.equal(roads.distance(null),'Not available');assert.equal(roads.distance('0'),'Not available');assert.equal(roads.distance(0),'0 m');
});
const origin=[103.78,1.30],xy=(x,y)=>[origin[0]+x/(111195*Math.cos(origin[1]*Math.PI/180)),origin[1]+y/111195];
function line(id,coords){return {type:'Feature',properties:{seg_id:id,dist_m:null},geometry:{type:'LineString',coordinates:coords.map(p=>xy(...p))}};}
const horizontal=line(1,[[-50,0],[50,0]]),parallel=line(2,[[-50,5],[50,5]]),vertical=line(3,[[0,-50],[0,50]]);
test('nearby non-crossed road is never selected by its closer vertices',()=>{
    const near=line(2,[[-1,5],[1,5]]);assert.equal(geometry.choose(xy(0,-3),xy(0,3),[horizontal,near],[]).feature.properties.seg_id,1);
});
test('multiple parallel roads and complex intersecting roads fail closed',()=>{
    assert.equal(geometry.choose(xy(0,-12),xy(0,12),[horizontal,parallel],[]).reason,'ambiguous');
    assert.equal(geometry.choose(xy(-10,-10),xy(10,10),[horizontal,vertical],[]).reason,'ambiguous');
});
test('adjacent collinear shared endpoints use a stable ID, not render order',()=>{
    const l=line(7,[[-20,0],[0,0]]),r=line(4,[[0,0],[20,0]]);
    assert.equal(geometry.choose(xy(0,-10),xy(0,10),[l,r,l],[]).feature.properties.seg_id,4);
    assert.equal(geometry.choose(xy(0,-10),xy(0,10),[r,l],[]).feature.properties.seg_id,4);
});
test('grade/access guards, unmatched points, collinear and >80 m placements are refused',()=>{
    assert.equal(geometry.choose(xy(0,-10),xy(0,10),[horizontal],[horizontal]).reason,'restricted_or_grade');
    assert.equal(geometry.choose(xy(0,10),xy(0,20),[horizontal],[]).reason,'unmatched');
    assert.equal(geometry.choose(xy(-10,0),xy(10,0),[horizontal],[]).reason,'unmatched');
    assert.equal(geometry.choose(xy(0,-45),xy(0,45),[horizontal],[]).reason,'length');
});
test('first, second, third PENDING proposals remain private on every GET surface',()=>{
    const b=createBackend(),f=fixtures['Kent Ridge Drive'];
    for(let i=0;i<3;i++){
        const ack=b.post(body(f));assert.equal(ack.ok,true);assert.equal(ack.status,'pending');assert.equal(ack.count,undefined);
        assert.deepEqual(b.get().segments,[]);assert.equal(b.get('summary').proposals,0);assert.equal(b.get('summary').lastUpdated,'-');
        assert.equal(b.get('csv').split('\n').length,1);
    }
});
test('first APPROVED proposal exposes its road, approximate line, summary and CSV',()=>{
    const b=createBackend(),f=fixtures['Engineering Drive 1'];
    for(let i=0;i<3;i++){
        assert.equal(b.post(body(f)).ok,true);b.approve(i);
        const res=b.get();assert.equal(res.segments.length,1);
        assert.equal(b.get('summary').proposals,i+1);
        assert.equal(b.get('csv').split('\n').length,2);
    }
    const s=b.get().segments[0];assert.equal(s.seg_id,f.seg_id);assert.equal(s.dist_m,null);assert.equal(s.count,3);assert.equal(s.reviewed,true);
    assert.ok(Array.isArray(s.line));assert.equal('a_lng' in s,false);assert.equal('story' in s,false);assert.equal(b.get('csv').includes('"null"'),false);
});
test('pending activity on another segment cannot change public counts or last-updated',()=>{
    const b=createBackend();for(let i=0;i<3;i++)b.post(body(fixtures.existing));b.approveAll();
    const before=b.get('summary');b.post(body(fixtures['Computing Drive']));assert.deepEqual(b.get('summary'),before);
});
test('rejection of the only approved row removes geometry, CSV and summary contribution',()=>{
    const b=createBackend();for(let i=0;i<3;i++)b.post(body(fixtures.existing));b.approveAll();
    b.sheets.get('proposals').values.slice(2).forEach(r=>r[11]='rejected');assert.equal(b.get().segments.length,1);
    b.sheets.get('proposals').values[1][11]='rejected';assert.equal(b.get().segments.length,0);assert.equal(b.get('summary').proposals,0);
    assert.equal(b.get('csv').split('\n').length,1);
});
test('new IDs validate against membership, not numeric range, and canonical distance wins',()=>{
    const b=createBackend(),f=fixtures['Kent Ridge Crescent'];
    assert.equal(b.post(body(f,{seg_id:1.2})).ok,false);assert.equal(b.post(body(f,{seg_id:90000000})).ok,false);
    assert.equal(b.post(body(f,{seg_id:fixtures.existing.seg_id})).ok,false);
    const oldIds=new Set(legacy.map(f=>f.properties.seg_id));let hole=0;while(oldIds.has(hole))hole++;
    assert.equal(b.ctx.road(hole),null);
    assert.equal(b.post(body(f,{registry_version:'stale'})).ok,false);
    assert.equal(b.post(body(f,{dist_m:999999})).ok,true);assert.equal(b.sheets.get('proposals').values[1][2],'');
});
test('zero canonical crossing distance is stored as zero, not null or blank',()=>{
    const b=createBackend(),f=fixtures.existing,r=b.ctx.road(f.seg_id);r.d=0;
    const old=b.ctx.road;b.ctx.road=id=>id===f.seg_id?r:old(id);
    assert.equal(b.post(body(f)).ok,true);assert.equal(b.sheets.get('proposals').values[1][2],0);
});
test('forged, out-of-country, degenerate and oversized crossings cannot be stored',()=>{
    const b=createBackend(),f=fixtures['Kent Ridge Drive'];
    for(const patch of [{a:[0,0]},{a:f.b},{b:[f.a[0],f.a[1]+.01]},{a:['103.78',1.3]},{seg_id:'57988'},{request_id:'bad'}]){
        assert.equal(b.post(body(f,patch)).ok,false);
    }
    assert.equal(b.sheets.get('proposals').values.length,1);
});
test('a client cannot approve its own row or force a public count',()=>{
    const b=createBackend();
    assert.equal(b.post(body(fixtures.existing,{status:'ok',review_status:'approved',count:3})).ok,true);
    assert.equal(b.sheets.get('proposals').values[1][11],'pending');assert.equal(b.sheets.get('proposals').values[1][15],'pending');
    assert.equal(b.get().segments.length,0);
});
test('real grade/access and ambiguous NUS crossings are refused server-side',()=>{
    for(const reason of ['ambiguous','restricted_or_grade']){
        const b=createBackend(),f=negative[reason],n=b.ctx.neighborhood(f.a,f.b);
        const candidate=n.features.find(r=>geometry.hits(f.a,f.b,r.geometry).length);
        assert.ok(candidate);
        const response=b.post(body(fixtures.existing,{a:f.a,b:f.b,seg_id:candidate.properties.seg_id}));
        assert.equal(response.ok,false);assert.equal(response.error,reason);
        assert.equal(b.sheets.get('proposals').values.length,1);
    }
});
test('idempotent retries do not inflate the publication count; formulas are text',()=>{
    const b=createBackend(),d=body(fixtures.existing,{story:'=IMPORTXML("http://example.invalid","x")'});
    assert.equal(b.post(d).ok,true);assert.equal(b.post(d).ok,true);assert.equal(b.sheets.get('proposals').values.length,2);
    assert.equal(b.sheets.get('proposals').values[1][9],d.story);
});
test('support works only on published segments and retries are idempotent',()=>{
    const b=createBackend(),f=fixtures.existing;
    const support=body(f,{kind:'support'});assert.equal(b.post(support).ok,false);
    for(let i=0;i<3;i++)b.post(body(f));b.approveAll();assert.equal(b.post(support).ok,true);assert.equal(b.post(support).ok,true);
    assert.equal(b.get().segments[0].support,1);
});
test('pilot status=ok imports publish immediately, but new rows remain moderated',()=>{
    const b=createBackend(),f=fixtures.existing,sh=b.sheets.get('proposals');
    sh.values=[Array.from(b.ctx.PROPOSAL_HEADERS).slice(0,12)];
    for(let i=0;i<3;i++)sh.appendRow([new Date(),f.seg_id,f.dist_m,...f.a,...f.b,'Zebra crossing','Other','','','ok']);
    b.ctx.setup();assert.equal(sh.values.length,4);assert.equal(b.get().segments.length,1);
    assert.equal(b.get().segments[0].count,3);assert.ok(Array.isArray(b.get().segments[0].line));
    sh.values[1][11]='rejected';sh.values[2][11]='rejected';assert.equal(b.get().segments[0].count,1);
    sh.values[1][11]='pending';sh.values[2][11]='pending';assert.equal(b.get().segments[0].count,1);
});
test('backend rejects zero thresholds and corrupt static data',()=>{
    const b=createBackend();b.ctx.MIN_PROPOSALS=0;assert.equal(b.get().ok,false);
    const c=createBackend();c.cache.set('roads:'+c.ctx.ROAD_MANIFEST_SHA256,'{}');assert.equal(c.post(body(fixtures.existing)).ok,false);
});
test('capabilities exposes policy without hidden proposal activity',()=>{
    const b=createBackend(),before=b.get('capabilities');
    assert.equal(before.moderation_required,true);assert.equal(before.max_crossing_m,80);assert.equal(before.count,undefined);
    b.post(body(fixtures.existing));assert.deepEqual(b.get('capabilities'),before);
});
test('client refuses pilot/unreviewed aggregates and stale versions',()=>{
    global.SITE={proposalNetworkVersion:manifest.version};
    assert.throws(()=>roads.publicSegments({segments:[{seg_id:1,count:1}]}));
    const res={api_version:'proposal-api-v2',registry_version:manifest.version,publication_min:1,line_min:1,
        segments:[{seg_id:1,count:1,reviewed:true},{seg_id:2,count:2,reviewed:true},{seg_id:3,count:20,reviewed:false}]};
    assert.deepEqual(roads.publicSegments(res).map(s=>s.seg_id),[1,2]);
});
test('tile loader fetches visible tiles only, deduplicates boundaries and caps concurrency',async()=>{
    global.SITE={proposalNetworkVersion:manifest.version};const seen=[];
    global.fetch=async url=>{seen.push(url);const text=fs.readFileSync(path.join(ROOT,'website',url),'utf8');return {ok:true,text:async()=>text};};
    const store=new roads.Store('data/proposal-roads');
    for(const id of ['',null,false,'1e3','0x10'])await assert.rejects(store.feature(id));
    await store.init();assert.equal(seen.length,1);
    const f=fixtures['Kent Ridge Drive'],pad=.001;
    const data=await store.area([f.a[0]-pad,f.a[1]-pad,f.a[0]+pad,f.a[1]+pad]);
    assert.ok(seen.filter(s=>s.includes('/tiles/')).length<10);
    assert.equal(new Set(data.features.map(f=>f.properties.seg_id)).size,data.features.length);
    assert.ok(store.metrics.peakConcurrent<=4);const n=seen.length;await store.area([f.a[0]-pad,f.a[1]-pad,f.a[0]+pad,f.a[1]+pad]);assert.equal(seen.length,n);
    await assert.rejects(store.area([103.59,1.15,104.10,1.48]));
    assert.equal((await store.feature('0')).properties.seg_id,0);
});
test('display tiles do not wait for guards, but selection fails closed if guards fail',async()=>{
    global.SITE={proposalNetworkVersion:manifest.version};const seen=[];
    global.fetch=async url=>{
        seen.push(url);if(url.includes('/guards/'))throw Error('Simulated unavailable restrictions');
        const text=fs.readFileSync(path.join(ROOT,'website',url),'utf8');return {ok:true,text:async()=>text};
    };
    const store=new roads.Store('data/proposal-roads'),f=fixtures['Kent Ridge Drive'];
    const bounds=[f.a[0]-.0001,f.a[1]-.0001,f.a[0]+.0001,f.a[1]+.0001];
    const data=await store.area(bounds,{displayOnly:true});
    assert.ok(data.features.length);assert.equal(data.guardsReady,false);assert.equal(data.guards,null);
    assert.ok(!seen.some(u=>u.includes('/guards/')));
    await assert.rejects(store.area(bounds),/restrictions/);
});
test('small pans reuse the uploaded tile set and zooming out clears it only once',async()=>{
    global.SITE={proposalNetworkVersion:manifest.version};
    global.fetch=async url=>({ok:true,text:async()=>fs.readFileSync(path.join(ROOT,'website',url),'utf8')});
    const f=fixtures['Kent Ridge Drive'],handlers={},uploads=[];let zoom=18,shift=0;
    const map={on:(name,fn)=>handlers[name]=fn,getZoom:()=>zoom,
        getBounds:()=>({getWest:()=>f.a[0]-.0001+shift,getSouth:()=>f.a[1]-.0001,getEast:()=>f.a[0]+.0001+shift,getNorth:()=>f.a[1]+.0001}),
        getSource:()=>({setData:data=>uploads.push(data)})};
    const store=new roads.Store('data/proposal-roads');store.attach(map,'gap');
    await new Promise(setImmediate);assert.equal(uploads.length,1);
    shift=.0000001;handlers.moveend();await new Promise(setImmediate);assert.equal(uploads.length,1);
    zoom=15;handlers.moveend();assert.equal(uploads.length,2);assert.equal(uploads[1].features.length,0);
    handlers.moveend();assert.equal(uploads.length,2);
});
