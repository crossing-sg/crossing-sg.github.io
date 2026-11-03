/* Execute the actual .gs source against in-memory Sheets and local static data.
 * There is deliberately no network implementation or production Sheet handle.
 */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..');
class Sheet {
    constructor(name){this.name=name;this.values=[];}
    getLastRow(){return this.values.length;}
    setFrozenRows(){return this;}
    appendRow(row){this.values.push(Array.from(row));}
    getRange(row,col,n=1,m=1){
        if(typeof row==='string')return {setDataValidation(){return this;}};
        const sheet=this;
        return {getValues(){return Array.from({length:n},(_,i)=>Array.from({length:m},(_,j)=>sheet.values[row-1+i]?.[col-1+j]??''));},
            setValues(values){values.forEach((line,i)=>{sheet.values[row-1+i]??=[];line.forEach((v,j)=>sheet.values[row-1+i][col-1+j]=v);});return this;},
            setFontWeight(){return this;},setDataValidation(){return this;}};
    }
}
function createBackend(options={}){
    const dataDirectory=path.resolve(ROOT,options.dataDirectory || 'website/data/proposal-roads');
    const sheets=new Map(),cache=new Map(),calls=[];
    const ss={getSheetByName:name=>sheets.get(name),insertSheet(name){const sh=new Sheet(name);sheets.set(name,sh);return sh;}};
    const ctx=vm.createContext({console,SpreadsheetApp:{getActiveSpreadsheet:()=>ss,newDataValidation:()=>({requireValueInList(){return this;},build(){return {};}})},
        PropertiesService:{getScriptProperties:()=>({getProperty:()=> 'https://fixture.invalid/data/proposal-roads'})},
        CacheService:{getScriptCache:()=>({get:key=>cache.get(key)||null,put:(key,v)=>cache.set(key,v)})},
        LockService:{getScriptLock:()=>({waitLock(){},releaseLock(){}})},
        Utilities:{DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'utf8'},
            ungzip:blob=>({getDataAsString:()=>require('node:zlib').gunzipSync(blob).toString('utf8')}),
            computeDigest:(algorithm,text)=>Array.from(crypto.createHash('sha256').update(text,'utf8').digest(),n=>n>127?n-256:n),
            newBlob:text=>({getBytes:()=>Array.from(Buffer.from(text,'utf8'))}),
            formatDate:date=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'Asia/Singapore'}).format(date)},
        UrlFetchApp:{fetch(url){
            if(!url.startsWith('https://fixture.invalid/data/proposal-roads/'))throw Error('External request forbidden in tests');
            const suffix=url.slice('https://fixture.invalid/data/proposal-roads/'.length);
            const file=path.resolve(dataDirectory,suffix);
            if(!file.startsWith(dataDirectory+path.sep))throw Error('Traversal');
            calls.push(suffix);const bytes=fs.readFileSync(file);return {getResponseCode:()=>200,getContentText:()=>bytes.toString('utf8'),getBlob:()=>bytes};
        }},ContentService:{MimeType:{JSON:'json',CSV:'csv'},createTextOutput:text=>({text,mime:null,setMimeType(mime){this.mime=mime;return this;}})}});
    for(const name of ['RegistryConfig.gs','RoadGeometry.gs','Code.gs'])vm.runInContext(fs.readFileSync(path.join(ROOT,'apps-script',name),'utf8'),ctx,{filename:name});
    // Each suite pins its own immutable release; never use a remote URL.
    const manifestBytes=fs.readFileSync(path.join(dataDirectory,'manifest.json'));
    ctx.ROAD_REGISTRY_VERSION=JSON.parse(manifestBytes).version;
    ctx.ROAD_MANIFEST_SHA256=crypto.createHash('sha256').update(manifestBytes).digest('hex');
    ctx.setup();
    return {ctx,sheets,cache,calls,
        post(data){return JSON.parse(ctx.doPost({postData:{contents:JSON.stringify(data)}}).text);},
        get(view='segments'){const r=ctx.doGet({parameter:{view}});return r.mime==='csv'?r.text:JSON.parse(r.text);},
        approve(index){const sh=sheets.get('proposals'),row=sh.values[index+1];row[11]='ok';row[15]='approved';},
        approveAll(){sheets.get('proposals').values.slice(1).forEach(r=>{r[11]='ok';r[15]='approved';});}};
}
function body(fixture,overrides={}){
    return {kind:'proposal',seg_id:fixture.seg_id,registry_version:JSON.parse(fs.readFileSync(path.join(ROOT,'website/data/proposal-roads/manifest.json'))).version,
        request_id:crypto.randomUUID(),a:fixture.a,b:fixture.b,type:'Zebra crossing',reason:'Nearest crossing is too far',story:'',website:'',...overrides};
}
module.exports={ROOT,createBackend,body};
