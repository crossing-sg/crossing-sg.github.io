/* Real Chromium / Mapbox GL JS, with local background style and in-memory API.
 * Network routing prevents any call to the live Apps Script / Google Sheet.
 */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {ROOT}=require('./backend_harness.cjs');
const VENDOR=path.join(ROOT,'local-outputs/integration-qa/vendor');
const OUT=process.env.QA_OUTPUT_DIR || path.join(ROOT,'local-outputs/integration-qa');
fs.mkdirSync(OUT,{recursive:true});
const examples=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/crossings-v1.json')));
const fixtures=examples.positive,negative=examples.negative;
const BASE=process.env.QA_BASE_URL || 'http://127.0.0.1:8766';
async function main(){
    const windowsChrome='C:/Program Files/Google/Chrome/Application/chrome.exe';
    const browser=await chromium.launch({executablePath:process.env.QA_CHROME_PATH || (fs.existsSync(windowsChrome)?windowsChrome:undefined),headless:true,
        args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
    const findings={browser:await browser.version(),basemap:'Local dark background; external basemap/font service styling not verified.',
        backend:'Actual Code.gs in-memory mock; zero live backend requests.',screenshots:[],cases:[],performance:[],consoleErrors:[],renderErrors:[],blockedExternalRequests:[]};
    try{
        for(const mobile of [false,true]){
            const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:1000},deviceScaleFactor:1,
                isMobile:mobile,hasTouch:mobile});
            await context.route('**/*',async route=>{
                const u=route.request().url();
                if(u.startsWith(BASE)||u.startsWith('blob:')||u.startsWith('data:'))return route.continue();
                if(u.includes('mapbox-gl.js'))return route.fulfill({path:path.join(VENDOR,'mapbox-gl.js'),contentType:'text/javascript'});
                if(u.includes('mapbox-gl.css'))return route.fulfill({path:path.join(VENDOR,'mapbox-gl.css'),contentType:'text/css'});
                if(u.includes('intersection-observer'))return route.fulfill({path:path.join(VENDOR,'intersection-observer.js'),contentType:'text/javascript'});
                if(u.includes('scrollama'))return route.fulfill({path:path.join(VENDOR,'scrollama.js'),contentType:'text/javascript'});
                findings.blockedExternalRequests.push(u.replace(/access_token=[^&]+/g,'access_token=REDACTED'));return route.abort();
            });
            const page=await context.newPage();page.on('pageerror',err=>findings.consoleErrors.push({mobile,message:String(err)}));
            const mode=await (await page.request.get(BASE+'/__test/config')).json();
            assert.equal(mode.isolatedTests,true,'Run serve:isolated on port 8766; do not substitute the normal preview basemap');
            page.on('console',msg=>{if(msg.type()==='error')findings.renderErrors.push({mobile,message:msg.text()});});
            const control=async data=>{const r=await page.request.post(BASE+'/__test/control',{data});assert.equal(r.status(),200);return r.json();};
            async function ready(){await page.waitForFunction(()=>typeof map!=='undefined'&&map.isStyleLoaded()&&map.getSource('draft'),null,{timeout:30000});}
            async function mark(f){
                const center=[(f.a[0]+f.b[0])/2,(f.a[1]+f.b[1])/2];
                await page.evaluate(center=>{resetPoints();map.jumpTo({center,zoom:18});},center);
                await page.waitForFunction(()=>roads.current&&roads.current.features.length>=0);
                const canvas=page.locator('.mapboxgl-canvas');await canvas.scrollIntoViewIfNeeded();
                const ps=await page.evaluate(f=>[map.project(f.a),map.project(f.b)].map(p=>({x:p.x,y:p.y})),f);
                await canvas.click({position:ps[0]});await canvas.click({position:ps[1]});
                await page.waitForFunction(()=>!document.querySelector('#where').innerText.includes('Checking the road'));
                await page.waitForFunction(()=>map.loaded()&&!map.isMoving(),null,{timeout:15000});
                await page.waitForFunction(()=>new Set(map.queryRenderedFeatures({layers:['draft-points']}).map(f=>f.properties.label)).size===2,null,{timeout:15000}).catch(async error=>{
                    findings.mapDebug=await page.evaluate(()=>({points,draft:map.getSource('draft')._data,features:map.queryRenderedFeatures().map(f=>f.layer.id)}));throw error;
                });
            }
            await control({reset:true});
            const start=Date.now();await page.goto(BASE+'/propose.html');await ready();await page.waitForFunction(()=>roads.manifest);
            const initial=await page.evaluate(()=>({metrics:roads.metrics,resources:performance.getEntriesByType('resource').filter(r=>r.name.includes('/proposal-roads/')).map(r=>({url:r.name,bytes:r.decodedBodySize,duration:r.duration}))}));
            assert.equal(initial.resources.filter(r=>r.url.includes('/tiles/')).length,0);
            findings.performance.push({mobile,stage:'island_startup',elapsedMs:Date.now()-start,...initial});
            const desktopLabel=mobile?'mobile':'desktop';
            for(const name of ['existing','Engineering Drive 1','Kent Ridge Crescent','Kent Ridge Drive']){
                await mark(fixtures[name]);await page.waitForFunction(id=>segment&&segment.seg_id===id,fixtures[name].seg_id);
                findings.cases.push({mobile,case:name,seg_id:fixtures[name].seg_id,passed:true});
            }
            assert.match(await page.locator('#where').innerText(),/Not available/);
            await page.screenshot({path:path.join(OUT,desktopLabel+'-propose.png'),fullPage:true});findings.screenshots.push(desktopLabel+'-propose.png');
            findings.performance.push({mobile,stage:'NUS_interactions',data:await page.evaluate(()=>({metrics:roads.metrics,
                resources:performance.getEntriesByType('resource').filter(r=>r.name.includes('/proposal-roads/')).map(r=>({path:new URL(r.name).pathname,bytes:r.decodedBodySize,duration:r.duration}))}))});
            await mark(negative.ambiguous);assert.equal(await page.evaluate(()=>segment),null);assert.match(await page.locator('#where').innerText(),/more than one road|ambiguous/);
            findings.cases.push({mobile,case:'real NUS ambiguous parallel/intersection',passed:true});
            await mark(negative.restricted_or_grade);assert.equal(await page.evaluate(()=>segment),null);assert.match(await page.locator('#where').innerText(),/restricted|grade/);
            await page.screenshot({path:path.join(OUT,desktopLabel+'-review-refusal.png'),fullPage:true});findings.screenshots.push(desktopLabel+'-review-refusal.png');
            await mark({a:[103.6500,1.1900],b:[103.6500,1.1902]});assert.equal(await page.evaluate(()=>segment),null);
            assert.match(await page.locator('#where').innerText(),/No eligible road/);
            findings.cases.push({mobile,case:'unmatched sea location and grade refusal',passed:true});
            // Submit three real forms, never to the live endpoint; review then publish.
            for(let i=0;i<3;i++){
                if(i) {await page.goto(BASE+'/propose.html');await ready();}
                await mark(fixtures['Kent Ridge Drive']);await page.waitForFunction(()=>segment!==null);
                await page.getByLabel('Zebra crossing',{exact:true}).check();await page.getByLabel('Nearest crossing is too far',{exact:true}).check();
                let releaseRequest;
                if(i===0){
                    const paused=new Promise(resolve=>releaseRequest=resolve);
                    await page.route('**/__test_api',async route=>{await paused;await route.continue();});
                }
                await page.getByRole('button',{name:'Submit proposal',exact:true}).click();
                if(i===0){
                    await page.waitForFunction(()=>submissionBusy);
                    const marked=await page.evaluate(()=>points);await page.evaluate(()=>resetPoints());
                    assert.deepEqual(await page.evaluate(()=>points),marked);
                    releaseRequest();
                    findings.cases.push({mobile,case:'selection frozen during slow submission',passed:true});
                }
                await page.locator('#thanks').waitFor({state:'visible'});assert.match(await page.locator('#thanks-count').innerText(),/awaiting review/);
                if(i===0)await page.unroute('**/__test_api');
                if(i<2)await control({approve:true});
                const publicNow=await (await page.request.get(BASE+'/__test_api?view=segments')).json();assert.equal(publicNow.segments.length,0);
                assert.equal((await (await page.request.get(BASE+'/__test_api?view=summary')).json()).proposals,0);
                assert.equal((await (await page.request.get(BASE+'/__test_api?view=csv')).text()).split('\n').length,1);
            }
            await control({approve:true});
            await page.goto(BASE+'/map.html?layer=proposals');
            await page.waitForFunction(()=>typeof map!=='undefined'&&map.getSource('proposals')&&map.getSource('proposals')._data.features.length===1);
            const displayed=await page.evaluate(()=>map.getSource('proposals')._data.features[0]);
            assert.equal(displayed.properties.seg_id,fixtures['Kent Ridge Drive'].seg_id);
            const block=JSON.parse(fs.readFileSync(path.join(ROOT,'website/data/proposal-roads/registry',Math.floor(displayed.properties.seg_id/128)+'.json')));
            assert.deepEqual(displayed.geometry,block.segments[String(displayed.properties.seg_id)].g);
            await page.evaluate(f=>{const c=f.geometry.coordinates;map.jumpTo({center:c[0],zoom:18});openSegment(f.properties);},displayed);
            await page.locator('#info').waitFor({state:'visible'});assert.match(await page.locator('#info').innerText(),/Not available/);
            await page.getByRole('button',{name:'I need a crossing here too'}).click();await page.waitForFunction(()=>document.querySelector('#support-count').innerText==='1');
            assert.equal((await page.getByRole('link',{name:'Propose here'}).getAttribute('href')),'propose.html?seg='+fixtures['Kent Ridge Drive'].seg_id);
            await page.screenshot({path:path.join(OUT,desktopLabel+'-explore.png'),fullPage:true});findings.screenshots.push(desktopLabel+'-explore.png');
            // Existing analytical data sources and route interaction still work.
            await page.evaluate(()=>setTheme('gap'));assert.equal(await page.evaluate(()=>map.getLayoutProperty('gap','visibility')),'visible');
            assert.equal(await page.evaluate(()=>map.getSource('gap')._data),'data/gap_segments.geojson');
            await page.evaluate(()=>setTheme('detour'));assert.equal(await page.evaluate(()=>map.getLayoutProperty('blocks','visibility')),'visible');
            const postal=fs.readdirSync(path.join(ROOT,'website/data/routes')).find(x=>x.endsWith('.json')).replace('.json','');
            await page.evaluate(postal=>openBlock(postal,true),postal);await page.waitForFunction(()=>map.getSource('routes')._data.features.length>0);
            findings.cases.push({mobile,case:'Explore geometry/support/deep link, Crossing Gap and Walking Detour routes',passed:true});
            await page.goto(BASE+'/propose.html?seg='+fixtures['Kent Ridge Drive'].seg_id);await ready();await page.waitForFunction(()=>map.getZoom()>17);
            assert.equal(await page.evaluate(()=>Math.abs(map.getCenter().lng-103.78)<.03),true);
            await page.goto(BASE+'/index.html');const story=page.frameLocator('iframe');
            await story.locator('#stat-proposals').filter({hasText:'3'}).waitFor({timeout:30000});
            const frame=page.frames().find(f=>f.url().includes('/mapbox/index.html'));
            await frame.waitForFunction(()=>typeof map!=='undefined'&&map.getSource('proposals')&&map.getSource('proposals')._data.features.length===1);
            assert.equal(await frame.evaluate(()=>map.getSource('proposals')._data.features[0].properties.count),3);
            await page.screenshot({path:path.join(OUT,desktopLabel+'-home.png'),fullPage:true});findings.screenshots.push(desktopLabel+'-home.png');
            if(mobile){
                const boxes=await frame.evaluate(()=>({credit:document.querySelector('.credit').getBoundingClientRect().toJSON(),
                    buttons:document.querySelector('.hero-text .buttons').getBoundingClientRect().toJSON(),cards:document.querySelector('.cards').getBoundingClientRect().toJSON()}));
                assert.ok(boxes.credit.top>=boxes.buttons.bottom);assert.ok(boxes.cards.top>=boxes.credit.bottom);
                await frame.locator('#hero').screenshot({path:path.join(OUT,'mobile-home-content.png')});findings.screenshots.push('mobile-home-content.png');
                findings.cases.push({mobile,case:'Home mobile buttons/credit/cards have no overlap',passed:true});
            }
            await control({rejectFirst:true});await page.reload();
            await page.frameLocator('iframe').locator('#stat-proposals').filter({hasText:'0'}).waitFor({timeout:30000});
            const frame2=page.frames().find(f=>f.url().includes('/mapbox/index.html'));
            await frame2.waitForFunction(()=>typeof map!=='undefined'&&map.getSource('proposals')&&map.getSource('proposals')._data.features.length===0);
            findings.cases.push({mobile,case:'Home published-only totals/dots and suppression after count falls below three',passed:true});
            assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
            await page.route('**/proposal-roads/tiles/*.geojson',route=>route.abort());
            await page.goto(BASE+'/propose.html');await ready();
            await page.evaluate(f=>{
                map.jumpTo({center:f.a,zoom:18});points=[f.a,f.b];drawDraft();findSegment();
            },fixtures['Kent Ridge Drive']);
            await page.waitForFunction(()=>document.querySelector('#where').innerText.includes('could not load'));
            assert.equal(await page.evaluate(()=>segment),null);
            assert.equal(await page.evaluate(()=>map.getFilter('gap-selected')[2]),-1);
            findings.cases.push({mobile,case:'failed tile requests leave no stale road assignment',passed:true});
            await page.unroute('**/proposal-roads/tiles/*.geojson');
            await page.goto(BASE+'/propose.html');await ready();await mark(fixtures['Kent Ridge Drive']);
            await page.waitForFunction(()=>segment!==null);
            await page.getByLabel('Zebra crossing',{exact:true}).check();await page.getByLabel('Nearest crossing is too far',{exact:true}).check();
            let unsafePosts=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/__test_api'))unsafePosts++;});
            await page.route('**/__test_api?view=capabilities',route=>route.fulfill({json:{segments:[{seg_id:1,count:1}]}}));
            await page.getByRole('button',{name:'Submit proposal',exact:true}).click();
            await page.waitForFunction(()=>document.querySelector('#error').innerText.includes('Could not record'));
            assert.equal(unsafePosts,0);
            findings.cases.push({mobile,case:'incompatible pilot backend refused before any submission POST',passed:true});
            await context.close();
        }
        findings.all_passed=true;
    }finally{
        fs.writeFileSync(path.join(OUT,'browser-results.json'),JSON.stringify(findings,null,2));await browser.close();
    }
    console.log(JSON.stringify({passed:findings.all_passed,cases:findings.cases.length,screenshots:findings.screenshots,consoleErrors:findings.consoleErrors},null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
