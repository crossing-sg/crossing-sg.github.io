const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const basemap=require('../../website/js/proposal-basemap.js');
const ROOT=path.resolve(__dirname,'../..');
const {execFileSync}=require('node:child_process');
const expected={'raster-saturation':-.25,'raster-hue-rotate':40,'raster-contrast':-.3,'raster-brightness-min':0,'raster-brightness-max':.5};
test('approved preview conversion modifies only raster paint, preserving street and label styles',()=>{
    const layers=[{id:'satellite',type:'raster',paint:{'raster-opacity':.8}},{id:'road-primary',type:'line',paint:{'line-color':'#fff'}},
        {id:'road-label',type:'symbol',layout:{'text-field':['get','name']},paint:{'text-color':'#fff'}},
        {id:'draft-points',type:'circle',paint:{'circle-radius':9}}];
    const original=structuredClone(layers);
    const map={getStyle:()=>({layers}),setPaintProperty:(id,k,v)=>layers.find(l=>l.id===id).paint[k]=v};
    basemap.apply(map);assert.deepEqual(layers.slice(1),original.slice(1));
    assert.deepEqual(layers[0].paint,{'raster-opacity':.8,...expected});
    basemap.apply(map);assert.deepEqual(layers[0].paint,{'raster-opacity':.8,...expected});
});
test('latest teammate crossing styles and detour interaction functions are retained',()=>{
    const before=execFileSync('git',['show','785b7533:website/js/explore.js'],{cwd:ROOT,encoding:'utf8'});
    const after=fs.readFileSync(path.join(ROOT,'website/js/explore.js'),'utf8');
    for(const id of ['proposals','proposal-crossings','proposal-line']){
        const start=before.indexOf("map.addLayer({ id: '"+id+"'");
        const end=before.indexOf('});',start)+3;
        assert.ok(after.includes(before.slice(start,end)),id+' paint/layout changed');
    }
    for(const name of ['setTheme','updateRefs','openBlock']){
        const start=before.indexOf('function '+name+'('),next=before.indexOf('\nfunction ',start+1);
        const chunk=before.slice(start,next<0?undefined:next),end=chunk.lastIndexOf('\n}')+2;
        // These two additions predate this release and do not alter the
        // retained basemap/route behavior being tested.
        const normalized=after
            .replace("    var proposalStats = document.getElementById('proposal-statistics');\n", '')
            .replace("    if (proposalStats) { proposalStats.hidden = theme !== 'proposals' || !proposalPublication || !proposalPublication.summary; }\n", '')
            .replace("    openPostal = String(postal);\n", '');
        assert.ok(normalized.includes(chunk.slice(0,end)),name+' changed beyond accepted enhancements');
    }
});
test('only Proposal loads/applies the imagery helper; latest satellite selection remains configured',()=>{
    const ctx={};vm.runInNewContext(fs.readFileSync(path.join(ROOT,'website/js/site-config.js'),'utf8'),ctx);
    assert.equal(ctx.SITE.proposeStyle,'mapbox://styles/mapbox/satellite-streets-v12');
    assert.equal(ctx.SITE.mapStyle,'mapbox://styles/mapbox/dark-v11');
    assert.match(ctx.SITE.appsScriptUrl,/^https:\/\/script.google.com\//);assert.equal(ctx.SITE.proposalApiUrl,'');
    assert.match(fs.readFileSync(path.join(ROOT,'website/js/propose.js'),'utf8'),/style: SITE.proposeStyle/);
    for(const file of ['website/index.html','website/map.html','website/mapbox/index.html']){
        assert.ok(!fs.readFileSync(path.join(ROOT,file),'utf8').includes('proposal-basemap.js'));
    }
});
