const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),cp=require('node:child_process');
const ROOT=path.resolve(__dirname,'../..'),OUT=path.join(ROOT,'local-outputs/basemap-fix');
async function main(){
    const source=fs.readFileSync(path.join(ROOT,'website/js/site-config.js'),'utf8');
    const token=s=>s.match(/mapboxToken:\s*'([^']+)'/)[1];
    const normal=await fetch('http://127.0.0.1:8765/js/site-config.js'),normalText=await normal.text();
    assert.ok(normalText.includes("mapStyle: 'mapbox://styles/mapbox/dark-v11'"));
    assert.ok(!normalText.includes("mapStyle: '/__test/style.json'"));
    assert.equal(token(normalText),token(source));
    assert.equal(token(source),token(cp.execFileSync('git',['show','HEAD:website/js/site-config.js'],{cwd:ROOT,encoding:'utf8'})));
    assert.equal((await fetch('http://127.0.0.1:8765/__test/style.json')).status,404);
    const isolated=await (await fetch('http://127.0.0.1:8766/js/site-config.js')).text();
    assert.ok(isolated.includes("mapStyle: '/__test/style.json'"));
    assert.equal((await fetch('http://127.0.0.1:8766/__test/style.json')).status,200);
    const tile=await fetch('http://127.0.0.1:8765/data/proposal-roads/tiles/10_15.geojson');
    const text=await tile.text(),etag=tile.headers.get('etag');assert.ok(etag);
    const cached=await fetch('http://127.0.0.1:8765/data/proposal-roads/tiles/10_15.geojson',{headers:{'If-None-Match':etag}});
    assert.equal(cached.status,304);assert.equal((await cached.text()).length,0);
    const configCached=await fetch('http://127.0.0.1:8765/js/site-config.js',{headers:{'If-None-Match':normal.headers.get('etag')}});
    assert.equal(configCached.status,304);
    const result={allPassed:true,normalStyle:'mapbox://styles/mapbox/dark-v11',normalTestStyleEndpoint:404,
        explicitIsolatedStyle:'/__test/style.json',isolatedTestStyleEndpoint:200,sourceAndServedTokenUnchanged:true,
        tileBytes:Buffer.byteLength(text),revalidatedStatus:cached.status,revalidatedBodyBytes:0,configRevalidatedStatus:configCached.status};
    fs.mkdirSync(OUT,{recursive:true});fs.writeFileSync(path.join(OUT,'preview-modes.json'),JSON.stringify(result,null,2));console.log(result);
}
main().catch(error=>{console.error(error);process.exitCode=1;});
