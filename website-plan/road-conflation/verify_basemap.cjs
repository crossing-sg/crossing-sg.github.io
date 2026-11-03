/* Real Mapbox network verification on localhost. No production backend calls.
 * No basemap substitution, response mocks or production credential changes.
 */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const ROOT=path.resolve(__dirname,'../..'),BASE=process.env.QA_BASE_URL||'http://127.0.0.1:8765';
const PHASE=process.env.QA_PHASE||'after',OUT=path.join(ROOT,'local-outputs/basemap-fix',PHASE);
const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/crossings-v1.json'))).positive;
const redact=s=>String(s).replace(/access_token=[^&\s"']+/g,'access_token=REDACTED').replace(/pk\.[A-Za-z0-9_.-]+/g,'PUBLIC_TOKEN_REDACTED');
async function main(){
    fs.mkdirSync(OUT,{recursive:true});
    const chrome='C:/Program Files/Google/Chrome/Application/chrome.exe';
    const browser=await chromium.launch({headless:true,executablePath:fs.existsSync(chrome)?chrome:undefined,
        args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
    const result={phase:PHASE,browser:await browser.version(),networkResponses:[],requestFailures:[],pageErrors:[],views:[],googleBackendCalls:0};
    const pending=[];
    try{
        const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
        const cdp=await context.newCDPSession(page);await cdp.send('Network.enable');
        await cdp.send('Network.setBlockedURLs',{urls:['*://script.google.com/*','*://script.googleusercontent.com/*']});
        page.on('request',r=>{if(/script\.google/.test(r.url()))result.googleBackendCalls++;});
        page.on('response',r=>{
            if(/mapbox\.(com|cn)/.test(r.url()))pending.push((async()=>{
                const entry={url:redact(r.url()),status:r.status()};
                if(r.status()>=400)try{entry.body=redact((await r.text()).slice(0,2500));}catch{}
                result.networkResponses.push(entry);
            })());
        });
        page.on('requestfailed',r=>result.requestFailures.push({url:redact(r.url()),error:r.failure()?.errorText}));
        page.on('pageerror',e=>result.pageErrors.push(redact(e)));
        const mode=await (await page.request.get(BASE+'/__test/config')).json();assert.equal(mode.isolatedTests,false);
        const start=Date.now();await page.goto(BASE+'/propose.html?seg='+fixtures['Kent Ridge Drive'].seg_id);
        await page.waitForFunction(()=>typeof map!=='undefined',null,{timeout:30000});
        await page.evaluate(()=>{window.basemapErrors=[];window.roadEvents=[];
            map.on('error',e=>basemapErrors.push(String(e.error?.message||e.error||e)));
            map.on('sourcedata',e=>{if(e.sourceId==='gap'&&e.isSourceLoaded)roadEvents.push({at:performance.now(),type:'source-loaded'});});
        });
        try{await page.waitForFunction(()=>map.isStyleLoaded()&&map.getSource('draft')&&map.getZoom()>17,null,{timeout:60000});}
        catch(error){result.styleLoadError=String(error);}
        if(!result.styleLoadError){
            await page.waitForFunction(()=>roads.current&&roads.current.features.length>0,null,{timeout:30000});
            await page.waitForFunction(()=>map.loaded()&&!map.isMoving(),null,{timeout:30000});
            result.firstReadyMs=Date.now()-start;
            const snapshot=async name=>{
                const data=await page.evaluate(()=>{
                    const style=map.getStyle(),all=map.queryRenderedFeatures(),base=all.filter(f=>f.source!=='gap'&&f.source!=='draft');
                    return {configuredStyle:SITE.mapStyle,name:style.name,sourceNames:Object.keys(style.sources),layerCount:style.layers.length,
                        customLayers:['gap','gap-selected','draft-line','draft-points','draft-labels'].map(id=>({id,exists:!!map.getLayer(id)})),
                        basemapRoadFeatures:base.filter(f=>f.layer.type==='line'&&/road|street|bridge|tunnel/.test(f.layer.id)).length,
                        buildingFeatures:base.filter(f=>/building/.test(f.layer.id)).length,
                        labelFeatures:base.filter(f=>f.layer.type==='symbol').length,
                        labelExamples:[...new Set(base.filter(f=>f.layer.type==='symbol').map(f=>f.properties.name_en||f.properties.name||f.properties.ref).filter(Boolean))].slice(0,15),
                        metrics:roads.metrics,roadEvents,errors:basemapErrors,
                        resources:performance.getEntriesByType('resource').filter(r=>r.name.includes('/proposal-roads/')).map(r=>({path:new URL(r.name).pathname,transferBytes:r.transferSize,decodedBytes:r.decodedBodySize,duration:r.duration,start:r.startTime,responseEnd:r.responseEnd}))};
                });
                result.views.push({view:name,...data});return data;
            };
            const first=await snapshot('Kent Ridge Drive');
            assert.equal(first.configuredStyle,'mapbox://styles/mapbox/dark-v11');assert.ok(first.layerCount>50);
            assert.ok(first.basemapRoadFeatures>0,'No rendered basemap roads');assert.ok(first.buildingFeatures>0,'No rendered buildings');
            assert.ok(first.labelFeatures>0,'No rendered labels');assert.ok(first.customLayers.every(l=>l.exists));
            await page.screenshot({path:path.join(OUT,'real-basemap-nus.png'),fullPage:true});
            const f=fixtures['Kent Ridge Drive'];
            const points=await page.evaluate(f=>[map.project(f.a),map.project(f.b)].map(p=>({x:p.x,y:p.y})),f);
            const canvas=page.locator('.mapboxgl-canvas');await canvas.click({position:points[0]});await canvas.click({position:points[1]});
            await page.waitForFunction(id=>segment&&segment.seg_id===id,f.seg_id,{timeout:30000});
            await page.waitForFunction(()=>map.loaded()&&!map.isMoving());
            await page.screenshot({path:path.join(OUT,'real-basemap-ab.png'),fullPage:true});
            await snapshot('A/B selected with real basemap');
            await page.evaluate(()=>{window.panSourceUpdates=0;const source=map.getSource('gap'),set=source.setData;
                source.setData=function(data){panSourceUpdates++;return set.call(this,data);};});
            // A small pan inside the same metric tile set must not retile the data.
            await page.evaluate(()=>map.panBy([25,0],{duration:0}));await page.waitForFunction(()=>map.loaded());
            await snapshot('small pan');
            result.smallPanSourceUpdates=await page.evaluate(()=>panSourceUpdates);
            await page.goto(BASE+'/map.html');await page.waitForFunction(()=>typeof map!=='undefined'&&map.isStyleLoaded()&&map.getSource('blocks'),null,{timeout:60000});
            await page.evaluate(f=>map.jumpTo({center:f.a,zoom:17}),f);await page.waitForFunction(()=>map.loaded(),null,{timeout:30000});
            result.explore=await page.evaluate(()=>({style:SITE.mapStyle,layers:['gap','blocks','proposals','proposal-line'].every(id=>!!map.getLayer(id)),layerCount:map.getStyle().layers.length}));
            assert.equal(result.explore.style,'mapbox://styles/mapbox/dark-v11');assert.ok(result.explore.layers);
            await page.screenshot({path:path.join(OUT,'real-basemap-explore.png'),fullPage:true});
            result.allPassed=true;
        }
        result.finalErrors=await page.evaluate(()=>window.basemapErrors||[]).catch(()=>[]);
        await Promise.allSettled(pending);assert.equal(result.googleBackendCalls,0);
    }finally{
        fs.writeFileSync(path.join(OUT,'verification.json'),JSON.stringify(result,null,2));await browser.close();
    }
    console.log(JSON.stringify({allPassed:result.allPassed,firstReadyMs:result.firstReadyMs,smallPanSourceUpdates:result.smallPanSourceUpdates,views:result.views.map(v=>({view:v.view,name:v.name,layers:v.layerCount,roads:v.basemapRoadFeatures,buildings:v.buildingFeatures,labels:v.labelFeatures,metrics:v.metrics})),httpErrors:result.networkResponses.filter(r=>r.status>=400),styleLoadError:result.styleLoadError},null,2));
    if(!result.allPassed)process.exitCode=1;
}
main().catch(error=>{console.error(redact(error));process.exitCode=1;});
