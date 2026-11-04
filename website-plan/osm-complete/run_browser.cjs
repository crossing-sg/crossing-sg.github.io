/* Own and stop the local test server in the browser's process environment. */
const {spawn}=require('node:child_process'),path=require('node:path');
const server=spawn(process.execPath,[path.join(__dirname,'server.cjs'),'--isolated-tests','--port','8767'],{stdio:['ignore','pipe','inherit'],windowsHide:true});
let started=false;
server.stdout.on('data',data=>{
    process.stdout.write(data);
    if(started||!data.toString().includes('Local preview:'))return;
    started=true;
    const runner=spawn(process.execPath,[path.join(__dirname,'browser.cjs')],{stdio:'inherit',windowsHide:true,
        env:{...process.env,QA_BASE_URL:'http://127.0.0.1:8767'}});
    runner.on('exit',code=>{server.kill();process.exitCode=code||0;});
});
server.on('exit',code=>{if(!started)process.exitCode=code||1;});
process.on('exit',()=>server.kill());
