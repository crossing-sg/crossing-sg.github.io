/* Real Chromium/Mapbox rendering. All non-loopback requests are blocked. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const ROOT=path.resolve(__dirname,'../..'),BASE=process.env.QA_BASE_URL || 'http://127.0.0.1:8766';
const examples=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures.json'))),fixtures=examples.positive;
const VENDOR=path.join(ROOT,'local-outputs/integration-qa/vendor'),OUT=path.join(ROOT,'local-outputs/osm-complete/browser');
fs.mkdirSync(OUT,{recursive:true});
async function main(){
    const exe='C:/Program Files/Google/Chrome/Application/chrome.exe';
    const browser=await chromium.launch({executablePath:process.env.QA_CHROME_PATH||(fs.existsSync(exe)?exe:undefined),headless:true,
        args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
    const report={version:examples.version,browser:await browser.version(),backend:'Actual Apps Script source; in-memory Sheets only',basemap:'Offline Mapbox GL rendering; external basemap blocked',cases:[],performance:[],errors:[],blocked:[]};
    try{
        for(const mobile of [false,true]){
            const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:1000},deviceScaleFactor:1,isMobile:mobile,hasTouch:mobile});
            await context.route('**/*',async route=>{
                const url=route.request().url();
                if(url.startsWith(BASE)||url.startsWith('blob:')||url.startsWith('data:'))return route.continue();
                for(const name of ['mapbox-gl.js','mapbox-gl.css','intersection-observer.js','scrollama.js']){
                    if(url.includes(name) || (name==='intersection-observer.js'&&url.includes('intersection-observer')) || (name==='scrollama.js'&&url.includes('scrollama'))){return route.fulfill({path:path.join(VENDOR,name),contentType:name.endsWith('.css')?'text/css':'text/javascript'});}
                }
                report.blocked.push(new URL(url).origin);return route.abort();
            });
            const page=await context.newPage();page.on('pageerror',e=>report.errors.push(String(e)));
            const control=async data=>(await page.request.post(BASE+'/__test/control',{data})).json();
            const ready=()=>page.waitForFunction(()=>typeof map!=='undefined'&&map.isStyleLoaded()&&map.getSource('draft'),null,{timeout:30000});
            assert.equal((await(await page.request.get(BASE+'/__test/config')).json()).isolatedTests,true);
            await control({reset:true});let start=Date.now();await page.goto(BASE+'/propose.html');await ready();await page.waitForFunction(()=>roads.manifest);
            const metrics=await page.evaluate(()=>({requests:roads.metrics.requests,tiles:performance.getEntriesByType('resource').filter(r=>r.name.includes('/tiles/')).length,
                bytes:performance.getEntriesByType('resource').filter(r=>r.name.includes('/proposal-roads/')).reduce((n,r)=>n+r.encodedBodySize,0)}));
            assert.equal(metrics.tiles,0);report.performance.push({mobile,stage:'island_startup',elapsedMs:Date.now()-start,...metrics});
            async function mark(f){
                start=Date.now();
                await page.evaluate(f=>{resetPoints();map.jumpTo({center:[(f.a[0]+f.b[0])/2,(f.a[1]+f.b[1])/2],zoom:18});},f);
                await page.waitForFunction(()=>roads.current&&roads.current.features.length>0);
                const canvas=page.locator('.mapboxgl-canvas');await canvas.scrollIntoViewIfNeeded();
                const pixels=await page.evaluate(f=>[map.project(f.a),map.project(f.b)].map(p=>({x:p.x,y:p.y})),f);
                await canvas.click({position:pixels[0]});await canvas.click({position:pixels[1]});
                await page.waitForFunction(()=>points.length===2&&!document.querySelector('#where').innerText.includes('Checking the road'));
                await page.waitForFunction(id=>segment&&segment.seg_id===id,f.seg_id,{timeout:30000});
                report.performance.push({mobile,stage:f.properties?.highway||'legacy',elapsedMs:Date.now()-start,
                    ...await page.evaluate(()=>({visibleFeatures:roads.current.features.length,metrics:roads.metrics,
                        bytes:performance.getEntriesByType('resource').filter(r=>r.name.includes('/proposal-roads/')).reduce((n,r)=>n+r.encodedBodySize,0)}))});
            }
            for(const key of ['existing','footway','service','parking_aisle','private_access','motorway','steps']){
                await mark(fixtures[key]);report.cases.push({mobile,case:'select '+key,passed:true});
            }
            const f=fixtures.footway;
            for(let i=0;i<3;i++){
                if(i){await page.goto(BASE+'/propose.html');await ready();}
                await mark(f);
                await page.getByLabel('Zebra crossing',{exact:true}).check();
                await page.getByLabel('Nearest crossing is too far',{exact:true}).check();
                await page.getByRole('button',{name:'Submit proposal',exact:true}).click();
                await page.locator('#thanks').waitFor({state:'visible'});
                assert.equal((await(await page.request.get(BASE+'/__test_api?view=segments')).json()).segments.length,0);
            }
            await control({approve:true});
            await page.goto(BASE+'/map.html?layer=proposals');
            await page.waitForFunction(()=>typeof map!=='undefined'&&map.getSource('proposals')&&map.getSource('proposals')._data.features.length===1);
            assert.equal(await page.evaluate(()=>map.getSource('proposals')._data.features[0].properties.seg_id),f.seg_id);
            await page.evaluate(f=>map.jumpTo({center:[(f.a[0]+f.b[0])/2,(f.a[1]+f.b[1])/2],zoom:18}),f);
            await page.waitForFunction(()=>map.queryRenderedFeatures({layers:['proposals']}).length>0);
            await page.waitForFunction(()=>map.queryRenderedFeatures({layers:['proposal-crossings']}).length>0);
            await page.screenshot({path:path.join(OUT,(mobile?'mobile':'desktop')+'-explore.png'),fullPage:true});
            report.cases.push({mobile,case:'three private submissions -> approve -> Explore OSM geometry',passed:true});
            await control({rejectFirst:true});await page.evaluate(()=>loadProposals());
            await page.waitForFunction(()=>map.getSource('proposals')._data.features.length===0&&map.getSource('proposal-crossings')._data.features.length===0);
            report.cases.push({mobile,case:'teammate white crossing lines clear with below-threshold aggregate',passed:true});
            await page.getByLabel('Crossing gap',{exact:true}).check();
            await page.waitForFunction(()=>map.getLayoutProperty('gap','visibility')==='visible'&&map.queryRenderedFeatures({layers:['gap']}).length>0);
            await page.getByLabel('Walking detour',{exact:true}).check();
            await page.evaluate(()=>openBlock(650121,true));
            await page.waitForFunction(()=>document.getElementById('info').innerText.includes('Postal 650121')&&map.getSource('routes')._data.features.length>0);
            report.cases.push({mobile,case:'Crossing Gap render and Walking Detour route card',passed:true});
            await page.goto(BASE+'/propose.html?seg='+f.seg_id);await ready();
            await page.waitForFunction(()=>map.getZoom()>17&&!map.isMoving());await mark(f);
            await page.screenshot({path:path.join(OUT,(mobile?'mobile':'desktop')+'-propose.png'),fullPage:true});
            // Dense city tiles, then a small pan: no repeat worker uploads.
            await page.evaluate(()=>{resetPoints();map.jumpTo({center:[103.851,1.284],zoom:17});});
            await page.waitForTimeout(400);await page.waitForFunction(()=>roads.current&&roads.current.features.length>0);
            const dense=await page.evaluate(()=>({features:roads.current.features.length,requests:roads.metrics.requests,uploads:roads.metrics.sourceUpdates}));
            await page.evaluate(()=>map.panBy([1,0],{duration:0}));await page.waitForTimeout(300);
            assert.ok((await page.evaluate(()=>roads.metrics.sourceUpdates))<=dense.uploads+1);
            report.performance.push({mobile,stage:'dense_downtown',...dense});
            assert.ok((await page.evaluate(()=>roads.metrics.peakConcurrent))<=4);
            report.cases.push({mobile,case:'canonical deep link; dense viewport; bounded concurrency',passed:true});
            if(mobile){
                const cdp=await context.newCDPSession(page);
                await cdp.send('Network.enable');
                await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:93750});
                await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
                const began=Date.now();await page.goto(BASE+'/propose.html');await ready();await page.waitForFunction(()=>roads.manifest);
                report.performance.push({mobile,stage:'simulated_1_6Mbps_150ms_4xCPU_startup',elapsedMs:Date.now()-began});
                await mark(f);
                report.cases.push({mobile,case:'throttled connection and CPU select OSM footway',passed:true});
            }
            await context.close();
        }
        assert.deepEqual(report.errors,[]);
        fs.writeFileSync(path.join(__dirname,'browser-results.json'),JSON.stringify(report,null,2)+'\n');
        console.log(JSON.stringify(report,null,2));
    }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
