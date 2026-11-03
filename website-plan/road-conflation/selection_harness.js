const fs=require('fs'),vm=require('vm');
const {chooseCrossedRoad}=require('./production_selection_reference.js');
const [website,fixtures,output]=process.argv.slice(2);
const source=fs.readFileSync(website,'utf8');
const start=source.indexOf('function findSegment()'),end=source.indexOf('function resetPoints()');
if(start<0||end<start) throw new Error('Cannot locate current website selector');
const context={MAX_LENGTH:80,segment:null,showWhere:()=>{},points:[],Math};
vm.createContext(context);vm.runInContext(source.slice(start,end),context);
const results=[];
for(const fixture of JSON.parse(fs.readFileSync(fixtures,'utf8'))) {
  const project=p=>{
    const size=512*2**fixture.zoom,lat=p[1]*Math.PI/180;
    return {x:(p[0]+180)/360*size,y:(.5-Math.log(Math.tan(Math.PI/4+lat/2))/(2*Math.PI))*size};
  };
  context.points=[fixture.a,fixture.b];context.segment=null;
  context.map={project,setFilter:()=>{},queryRenderedFeatures:()=>fixture.features};
  context.findSegment();
  const a=project(fixture.a),b=project(fixture.b);
  const fixed=chooseCrossedRoad(fixture.features.map(f=>({seg_id:f.properties.seg_id,
    screen:f.geometry.coordinates.map(p=>{const q=project(p);return[q.x,q.y];})})),[a.x,a.y],[b.x,b.y]);
  results.push({fixture_id:fixture.fixture_id,current:context.segment?context.segment.seg_id:null,
    reference:fixed?fixed.seg_id:null,expected:fixture.expected,network:fixture.network,road:fixture.road,zoom:fixture.zoom});
}
fs.writeFileSync(output,JSON.stringify(results));
