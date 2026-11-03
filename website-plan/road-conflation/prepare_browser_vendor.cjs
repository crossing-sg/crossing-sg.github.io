/* Optional, explicit local test dependency download; never calls a Sheet/API. */
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..'),OUT=path.join(ROOT,'local-outputs/integration-qa/vendor');
async function main(){
    fs.mkdirSync(OUT,{recursive:true});
    const token=fs.readFileSync(path.join(ROOT,'website/js/site-config.js'),'utf8').match(/mapboxToken:\s*'([^']+)'/)[1];
    const files={
        'mapbox-gl.js':'https://api.mapbox.com/mapbox-gl-js/v2.11.0/mapbox-gl.js',
        'mapbox-gl.css':'https://api.mapbox.com/mapbox-gl-js/v2.11.0/mapbox-gl.css',
        'scrollama.js':'https://unpkg.com/scrollama@3.2.0/build/scrollama.js',
        'intersection-observer.js':'https://unpkg.com/intersection-observer@0.12.0/intersection-observer.js',
        'glyphs-0-255.pbf':'https://api.mapbox.com/fonts/v1/mapbox/DIN%20Pro%20Bold,Arial%20Unicode%20MS%20Bold/0-255.pbf?access_token='+encodeURIComponent(token)};
    const hashes={};
    for(const [name,url] of Object.entries(files)){
        const dest=path.join(OUT,name);
        if(!fs.existsSync(dest)){
            const r=await fetch(url);if(!r.ok)throw Error('Could not download '+name+' (HTTP '+r.status+')');
            let data=Buffer.from(await r.arrayBuffer());if(name.endsWith('.pbf')&&data[0]===31&&data[1]===139)data=zlib.gunzipSync(data);
            fs.writeFileSync(dest,data);
        }
        const data=fs.readFileSync(dest);if(data.length<1000)throw Error('Invalid test dependency: '+name);
        hashes[name]={bytes:data.length,sha256:crypto.createHash('sha256').update(data).digest('hex')};
    }
    fs.writeFileSync(path.join(OUT,'dependency-checksums.json'),JSON.stringify(hashes,null,2));console.log(hashes);
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
