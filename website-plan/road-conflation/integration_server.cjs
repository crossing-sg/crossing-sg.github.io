/* Loopback-only, isolated website + actual Apps Script mocked in memory.
 * This server is a development tool, outside the GitHub Pages publication root.
 * It has no Google credentials and cannot make external backend requests.
 */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const harness=require('./backend_harness.cjs'),{ROOT}=harness;
const createBackend=()=>harness.createBackend({dataDirectory:process.env.QA_ROAD_DATA_DIR});
const body=f=>harness.body(f,process.env.QA_ROAD_VERSION?{registry_version:process.env.QA_ROAD_VERSION}:{});
const fixtures=JSON.parse(fs.readFileSync(process.env.QA_ROAD_FIXTURES || path.join(__dirname,'fixtures/crossings-v1.json'))).positive;
const args=process.argv.slice(2);
const isolatedTests=args.includes('--isolated-tests');
const portIndex=args.indexOf('--port');
const port=Number(portIndex>=0?args[portIndex+1]:8765);
if(!Number.isInteger(port)||port<1024||port>65535)throw Error('Use --port followed by a port from 1024 to 65535');
for(let i=0;i<args.length;i++){if(args[i]==='--isolated-tests')continue;if(args[i]==='--port'){i++;continue;}throw Error('Unknown server option: '+args[i]);}
const origin='http://127.0.0.1:'+port;
let backend=createBackend();const requests=[];
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.geojson':'application/geo+json',
    '.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml','.pbf':'application/x-protobuf','.csv':'text/csv'};
const server=http.createServer(async(req,res)=>{
    const url=new URL(req.url,'http://127.0.0.1');requests.push({path:url.pathname,time:Date.now()});
    function send(code,data,type='application/json'){res.writeHead(code,{'Content-Type':type+'; charset=utf-8','Cache-Control':'no-store'});res.end(typeof data==='string'||Buffer.isBuffer(data)?data:JSON.stringify(data));}
    try{
        if(url.pathname==='/__test_api'){
            if(req.method==='POST'){
                let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>12000)throw Error('Request too large');}
                return send(200,backend.post(JSON.parse(raw)));
            }
            const data=backend.get(url.searchParams.get('view')||'segments');return send(200,data,typeof data==='string'?'text/csv':'application/json');
        }
        if(url.pathname==='/__test/control'){
            let raw='';for await(const chunk of req)raw+=chunk;
            const d=JSON.parse(raw||'{}');
            if(d.reset)backend=createBackend();
            if(d.seed){for(let i=0;i<(d.count||1);i++){const result=backend.post(body(fixtures[d.seed]));if(!result.ok)throw Error(JSON.stringify(result));}}
            if(d.approve)backend.approveAll();
            if(d.rejectFirst)backend.sheets.get('proposals').values[1][11]='rejected';
            return send(200,{ok:true,rows:backend.sheets.get('proposals').values.length-1,segments:backend.get().segments});
        }
        if(url.pathname==='/__test/requests')return send(200,requests);
        if(url.pathname==='/__test/config')return send(200,{isolatedTests,port,basemap:isolatedTests?'offline-test':'mapbox://styles/mapbox/dark-v11',backend:'in-memory'});
        if(url.pathname==='/__test/style.json'&&isolatedTests)return send(200,{version:8,name:'Isolated QA background',glyphs:origin+'/__test/glyphs/{fontstack}/{range}.pbf',
            sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#1b1e23'}}]});
        if(url.pathname.startsWith('/__test/glyphs/')&&isolatedTests)return send(200,fs.readFileSync(path.join(ROOT,'local-outputs/integration-qa/vendor/glyphs-0-255.pbf')),'application/x-protobuf');
        const isVendor=url.pathname.startsWith('/__vendor/');
        const base=isVendor?path.join(ROOT,'local-outputs/integration-qa/vendor'):path.join(ROOT,'website');
        const suffix=isVendor?url.pathname.slice('/__vendor/'.length):url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));
        const file=path.resolve(base,suffix);
        if(!file.startsWith(base+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile())return send(404,'Not found','text/plain');
        let content=fs.readFileSync(file);
        if(file===path.join(ROOT,'website/js/site-config.js')){
            content=content.toString().replace(/appsScriptUrl: '[^']*'/,"appsScriptUrl: '/__test_api'").replace(/proposalApiUrl: '[^']*'/,"proposalApiUrl: '/__test_api'");
            if(isolatedTests)content=content.replace(/mapStyle: '[^']*'/,"mapStyle: '/__test/style.json'").replace(/proposeStyle: '[^']*'/,"proposeStyle: '/__test/style.json'");
        }
        if(isolatedTests)return send(200,content,types[path.extname(file)]||'application/octet-stream');
        // Normal local development revalidates changed files immediately but may
        // reuse unchanged response bodies. Hash the served (possibly rewritten)
        // bytes, so a cached old test-config response cannot survive this fix.
        const etag='"'+crypto.createHash('sha256').update(content).digest('base64url')+'"';
        const headers={'Content-Type':(types[path.extname(file)]||'application/octet-stream')+'; charset=utf-8','Cache-Control':'no-cache','ETag':etag};
        if(req.headers['if-none-match']===etag){res.writeHead(304,headers);return res.end();}
        res.writeHead(200,headers);return res.end(content);
    }catch(error){return send(500,{ok:false,error:String(error)});}
});
server.listen(port,'127.0.0.1',()=>console.log('Local preview: '+origin+' (in-memory backend; '+(isolatedTests?'EXPLICIT offline automated-test basemap':'original Mapbox dark-v11 basemap')+')'));
