import http from 'node:http';
import {readFile,realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseArgs} from './src/args.mjs';
import {createService} from './src/service.mjs';
const webRoot=path.join(path.dirname(fileURLToPath(import.meta.url)),'web');
const routes={GET:{'/api/catalog':'catalog','/api/reservations':'reservations','/api/maintenance':'maintenance','/api/report':'report'},POST:{'/api/quote':'quote','/api/availability':'availability','/api/command':'command'}};
const statuses={VALIDATION:400,NOT_FOUND:404,CAPACITY:409,INVALID_TRANSITION:409,REVISION_CONFLICT:409,IDEMPOTENCY_CONFLICT:409,BUSY:409};
const json=(response,status,value)=>{response.writeHead(status,{'content-type':'application/json; charset=utf-8'});response.end(JSON.stringify(value));};
const failure=(code,message)=>({ok:false,revision:0,error:{code,message}});
try {
  const {dataDir,catalogPath,port}=parseArgs(process.argv.slice(2),{server:true});
  const service=createService({dataDir,catalogPath});
  const server=http.createServer(async(request,response)=>{
    try {
      const pathname=new URL(request.url,'http://localhost').pathname;
      if(pathname==='/api/health'&&request.method==='GET') return json(response,200,{ok:true});
      const operation=routes[request.method]?.[pathname];
      if(operation) {
        let payload={};
        if(request.method==='POST') {
          let body='';for await(const chunk of request) {body+=chunk;if(body.length>1024*1024) return json(response,413,failure('VALIDATION','Request too large'));}
          try {payload=body.trim()?JSON.parse(body):{};}catch {return json(response,400,failure('VALIDATION','Invalid JSON'));}
        }
        const result=await service.execute(operation,payload);
        return json(response,result.ok?200:statuses[result.error.code]??400,result);
      }
      if(pathname.startsWith('/api/')) return json(response,404,failure('NOT_FOUND','Route not found'));
      if(request.method!=='GET') return json(response,405,failure('NOT_FOUND','Route not found'));
      let decoded;try {decoded=decodeURIComponent(pathname);}catch{return json(response,400,failure('VALIDATION','Invalid path'));}
      if(decoded.includes('\\')||decoded.includes('\0')||decoded.split('/').includes('..')) return json(response,404,failure('NOT_FOUND','File not found'));
      const target=path.resolve(webRoot,'.'+(decoded==='/'?'/index.html':decoded));
      if(!target.startsWith(webRoot+path.sep)) return json(response,404,failure('NOT_FOUND','File not found'));
      let resolved;try {resolved=await realpath(target);}catch{return json(response,404,failure('NOT_FOUND','File not found'));}
      if(!resolved.startsWith(webRoot+path.sep)) return json(response,404,failure('NOT_FOUND','File not found'));
      const content=await readFile(resolved);
      const type={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.mjs':'text/javascript; charset=utf-8'}[path.extname(resolved)]??'application/octet-stream';
      response.writeHead(200,{'content-type':type});response.end(content);
    } catch {json(response,500,failure('VALIDATION','Request failed'));}
  });
  server.listen(port,'127.0.0.1',()=>process.stdout.write(JSON.stringify({port:server.address().port})+'\n'));
} catch(error) {process.stderr.write(error.message+'\n');process.exitCode=1;}
