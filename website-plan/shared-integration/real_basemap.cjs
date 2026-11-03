/* Read-only Mapbox validation. All Google backend domains are blocked. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const ROOT=path.resolve(__dirname,'../..'),BASE='http://127.0.0.1:8768';
const OUT=path.join(ROOT,'local-outputs/shared-integration');fs.mkdirSync(OUT,{recursive:true});
const report={base:'785b7533',realMapbox:true,googleRequests:0,pageErrors:[],rasterLayers:[],nonRasterLayersVerified:0};
async function main(){
    const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',
        args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
    try{
        const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
        let originalStyle;
        await context.route('**/*',async route=>{
            const url=route.request().url();
            if(/script\.google(?:usercontent)?\.com/.test(url)){report.googleRequests++;return route.abort();}
            if(url.includes('/styles/v1/mapbox/satellite-streets-v12')&&!url.includes('/sprite')){
                const response=await route.fetch();originalStyle=await response.json();return route.fulfill({response});
            }
            return route.continue();
        });
        page.on('pageerror',e=>report.pageErrors.push(String(e)));
        await page.goto(BASE+'/propose.html');
        await page.waitForFunction(()=>typeof map!=='undefined'&&map.isStyleLoaded()&&map.getSource('draft'),null,{timeout:60000});
        await page.evaluate(()=>map.jumpTo({center:[103.851,1.284],zoom:17}));
        await page.waitForFunction(()=>map.loaded()&&!map.isMoving(),null,{timeout:60000});
        const actual=await page.evaluate(()=>({style:map.getStyle(),configured:SITE.proposeStyle,
            labelFeatures:map.queryRenderedFeatures().filter(f=>f.layer.type==='symbol').length,
            canvasFilter:getComputedStyle(map.getCanvas()).filter}));
        assert.equal(actual.configured,'mapbox://styles/mapbox/satellite-streets-v12');assert.equal(actual.canvasFilter,'none');
        assert.ok(originalStyle?.layers?.length);
        const expected={'raster-saturation':-.25,'raster-hue-rotate':40,'raster-contrast':-.3,'raster-brightness-min':0,'raster-brightness-max':.5};
        for(const layer of originalStyle.layers){
            const current=actual.style.layers.find(l=>l.id===layer.id);assert.ok(current,layer.id);
            if(layer.type==='raster'){
                for(const [key,value] of Object.entries(expected))assert.equal(current.paint[key],value,key);
                report.rasterLayers.push({id:layer.id,paint:current.paint});
            }else{
                assert.deepEqual(current.paint||{},layer.paint||{},layer.id+' paint');
                assert.deepEqual(current.layout||{},layer.layout||{},layer.id+' layout');
                report.nonRasterLayersVerified++;
            }
        }
        assert.ok(report.rasterLayers.length);assert.ok(actual.labelFeatures>0);report.renderedLabels=actual.labelFeatures;
        await page.screenshot({path:path.join(OUT,'proposal-satellite-approved.png'),fullPage:true});
        const f=JSON.parse(fs.readFileSync(path.join(ROOT,'website-plan/osm-complete/fixtures.json'))).positive.footway;
        await page.evaluate(f=>map.jumpTo({center:f.a,zoom:18}),f);
        await page.waitForFunction(()=>roads.current&&roads.current.features.length>0);
        const canvas=page.locator('.mapboxgl-canvas'),pixels=await page.evaluate(f=>[map.project(f.a),map.project(f.b)].map(p=>({x:p.x,y:p.y})),f);
        await canvas.click({position:pixels[0]});await canvas.click({position:pixels[1]});
        await page.waitForFunction(id=>segment&&segment.seg_id===id,f.seg_id);report.osmRoadMatched=true;
        await page.goto(BASE+'/map.html');
        await page.waitForFunction(()=>typeof map!=='undefined'&&map.isStyleLoaded()&&map.getSource('blocks'),null,{timeout:60000});
        report.exploreStyle=await page.evaluate(()=>SITE.mapStyle);
        assert.equal(report.exploreStyle,'mapbox://styles/mapbox/dark-v11');
        assert.equal(report.googleRequests,0);assert.deepEqual(report.pageErrors,[]);report.passed=true;
    }finally{await browser.close();fs.writeFileSync(path.join(__dirname,'real-basemap-results.json'),JSON.stringify(report,null,2)+'\n');}
    console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(String(e).replace(/pk\.[\w.-]+/g,'PUBLIC_TOKEN_REDACTED'));process.exitCode=1;});
