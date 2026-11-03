const {spawn}=require('node:child_process'),path=require('node:path');
const server=spawn(process.execPath,[path.join(__dirname,'../osm-complete/server.cjs'),'--port','8768'],{stdio:['ignore','pipe','inherit'],windowsHide:true});
let started=false;
server.stdout.on('data',data=>{
    process.stdout.write(data);if(started||!data.toString().includes('Local preview:'))return;started=true;
    const run=spawn(process.execPath,[path.join(__dirname,'real_basemap.cjs')],{stdio:'inherit',windowsHide:true});
    run.on('exit',code=>{server.kill();process.exitCode=code||0;});
});
server.on('exit',code=>{if(!started)process.exitCode=code||1;});process.on('exit',()=>server.kill());
