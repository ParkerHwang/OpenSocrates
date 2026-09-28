// A per-cell browser tool, not an agent. Runs under a separate filesystem sandbox
// because macOS Codex shell sandbox IPC prevents Chromium startup.
const fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
  const readChecks={};
  for(const [name,target] of Object.entries(JSON.parse(process.env.EVAL_BROWSER_READ_PROBES))){
    try{fs.readFileSync(target);readChecks[name]=true;}catch{readChecks[name]=false;}
  }
  if(Object.values(readChecks).some(Boolean))throw Error('Browser isolation canary failed');
  const server=await chromium.launchServer({headless:true,executablePath:process.env.EVAL_CHROMIUM,host:'127.0.0.1',port:0});
  console.log(JSON.stringify({endpoint:server.wsEndpoint(),read_checks:readChecks,pid:server.process().pid}));
  let closed=false;
  async function close(){if(closed)return;closed=true;await server.close();process.exit(0);}
  process.stdin.resume();process.stdin.on('end',close);process.on('SIGTERM',close);
})().catch(e=>{console.error(String(e));process.exitCode=1;});
