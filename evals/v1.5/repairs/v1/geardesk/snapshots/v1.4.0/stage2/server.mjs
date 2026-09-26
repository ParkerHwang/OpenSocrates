import {createServer} from 'node:http';
import {readFile,realpath} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createService} from './src/service.mjs';

function args(argv) {
  const values={};
  for(let i=0;i<argv.length;i+=2) {if(!['--data-dir','--catalog','--port'].includes(argv[i])) throw new Error('Unknown argument'); values[argv[i]]=argv[i+1];}
  const port=Number(values['--port']);
  if(!values['--data-dir']||!values['--catalog']||!Number.isInteger(port)||port<0||port>65535) throw new Error('Usage: node server.mjs --data-dir PATH --catalog PATH --port PORT');
  return {dataDir:values['--data-dir'],catalogPath:values['--catalog'],port};
}
const {port,...config}=args(process.argv.slice(2));
const service=createService(config);
const webRoot=resolve(fileURLToPath(new URL('./web/',import.meta.url)));
const routes={'GET /api/catalog':'catalog','POST /api/quote':'quote','POST /api/availability':'availability','POST /api/command':'command','GET /api/reservations':'reservations','GET /api/maintenance':'maintenance','GET /api/report':'report'};
const json=(res,status,body)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(body));};
const server=createServer(async(req,res)=>{
  try {
    let pathname;
    try {pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);} catch {return json(res,400,{ok:false,revision:0,error:{code:'VALIDATION',message:'Invalid URL'}});}
    if(pathname==='/api/health'&&req.method==='GET') return json(res,200,{ok:true});
    const operation=routes[`${req.method} ${pathname}`];
    if(operation) {
      let input={};
      if(req.method==='POST') {
        let body=''; for await(const chunk of req) {body+=chunk; if(body.length>1024*1024) return json(res,413,{ok:false,revision:0,error:{code:'VALIDATION',message:'Request too large'}});}
        try {input=body.trim()?JSON.parse(body):{};} catch {return json(res,400,{ok:false,revision:0,error:{code:'VALIDATION',message:'Invalid JSON'}});}
      }
      const result=await service.execute(operation,input);
      const statuses={VALIDATION:400,NOT_FOUND:404,CAPACITY:409,INVALID_TRANSITION:409,REVISION_CONFLICT:409,IDEMPOTENCY_CONFLICT:409,BUSY:409};
      return json(res,result.ok?200:statuses[result.error.code]??400,result);
    }
    if(pathname.startsWith('/api/')) return json(res,404,{ok:false,revision:0,error:{code:'NOT_FOUND',message:'Unknown route'}});
    if(req.method!=='GET'&&req.method!=='HEAD') return json(res,405,{ok:false,revision:0,error:{code:'VALIDATION',message:'Unsupported method'}});
    const target=resolve(webRoot,'.'+(pathname==='/'?'/index.html':pathname));
    if(target!==webRoot&&!target.startsWith(webRoot+sep)) return json(res,404,{ok:false,revision:0,error:{code:'NOT_FOUND',message:'Unknown file'}});
    const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.mjs':'text/javascript; charset=utf-8'}[extname(target)];
    if(!mime) return json(res,404,{ok:false,revision:0,error:{code:'NOT_FOUND',message:'Unknown file'}});
    try {const real=await realpath(target);if(!real.startsWith(webRoot+sep)) throw new Error('Outside web root');const body=await readFile(real);res.writeHead(200,{'Content-Type':mime});res.end(req.method==='HEAD'?undefined:body);} catch {json(res,404,{ok:false,revision:0,error:{code:'NOT_FOUND',message:'Unknown file'}});}
  } catch {json(res,500,{ok:false,revision:0,error:{code:'BUSY',message:'Server error'}});}
});
server.listen(port,'127.0.0.1',()=>process.stdout.write(JSON.stringify({port:server.address().port})+'\n'));
