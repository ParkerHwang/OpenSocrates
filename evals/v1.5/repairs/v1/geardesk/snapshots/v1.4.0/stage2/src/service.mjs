import {readFile,writeFile,rename,unlink,mkdir,rmdir,lstat} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {randomUUID} from 'node:crypto';
import {BusinessError,emptyStore,validateStore,validateCatalog,availability,quote,command,report} from './domain.mjs';

const error=(code,message,revision)=>({ok:false,revision,error:{code,message}});
const success=(data,revision)=>({ok:true,revision,data});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));

export function createService({dataDir,catalogPath,now=()=>new Date().toISOString()}) {
  if(typeof dataDir!=='string'||!dataDir||typeof catalogPath!=='string'||!catalogPath) throw new Error('dataDir and catalogPath are required');
  const dir=resolve(dataDir),file=join(dir,'store.json'),lock=join(dir,'.store.lock');
  async function catalog() {return validateCatalog(JSON.parse(await readFile(catalogPath,'utf8')));}
  async function store() {
    let raw;
    try {const stat=await lstat(file); if(!stat.isFile()) throw new BusinessError('VALIDATION','Invalid store file'); raw=await readFile(file,'utf8');} catch(e) {if(e.code==='ENOENT') return emptyStore(); throw e;}
    try {return validateStore(JSON.parse(raw));} catch {throw new BusinessError('VALIDATION','Invalid or unsupported store');}
  }
  async function persist(value) {
    const temp=join(dir,`.store-${randomUUID()}.tmp`);
    try {await writeFile(temp,JSON.stringify(value)); await rename(temp,file);} finally {await unlink(temp).catch(e=>{if(e.code!=='ENOENT') throw e;});}
  }
  async function locked(work) {
    await mkdir(dir,{recursive:true});
    for(let attempt=0;attempt<100;attempt++) {
      try {await mkdir(lock); break;} catch(e) {if(e.code!=='EEXIST') throw e; if(attempt===99) throw new BusinessError('BUSY','Store is busy'); await pause(20);}
    }
    try {return await work();} finally {await rmdir(lock);}
  }
  async function execute(operation,request={}) {
    let revision=0;
    try {
      if(operation==='command') return await locked(async()=>{
        const current=await store(); revision=current.revision;
        const c=await catalog();
        const outcome=command(current,c,request,now());
        if(!outcome.replay) await persist(outcome.store);
        return success(outcome.data,outcome.store.revision);
      });
      const current=await store(); revision=current.revision;
      const c=await catalog();
      const data={catalog:()=>c,quote:()=>quote(current,c,request),availability:()=>availability(current,c,request),reservations:()=>current.reservations.map(r=>structuredClone(r)),maintenance:()=>current.maintenance.map(m=>structuredClone(m)),report:()=>report(current)}[operation];
      if(!data) throw new BusinessError('VALIDATION','Unknown operation');
      return success(data(),revision);
    } catch(e) {
      if(e instanceof BusinessError) return error(e.code,e.message,revision);
      if(e instanceof SyntaxError || e instanceof TypeError || e instanceof RangeError) return error('VALIDATION',e.message,revision);
      return error('BUSY','Storage unavailable',revision);
    }
  }
  return {execute};
}
