import {readFile,writeFile,rename,mkdir,rm,lstat,open} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {DomainError,emptyStore,validateStore,validateCatalog,quote,availability,command,reservations,maintenance,report} from './domain.mjs';

const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function readStore(dataDir) {
  const file=path.join(dataDir,'store.json');
  try {
    const stat=await lstat(file);if(!stat.isFile()) throw new Error('Store must be a regular file');
    return validateStore(JSON.parse(await readFile(file,'utf8')));
  } catch(error) {if(error.code==='ENOENT') return emptyStore();throw error;}
}
async function lock(dataDir) {
  const lockPath=path.join(dataDir,'.store.lock');
  for(let attempt=0;attempt<100;attempt++) {
    try {await mkdir(lockPath);return async()=>rm(lockPath,{recursive:true,force:true});}
    catch(error) {if(error.code!=='EEXIST') throw error;await pause(20);}
  }
  throw new DomainError('BUSY','Store is busy');
}
async function persist(dataDir,store) {
  const temporary=path.join(dataDir,'.store-'+randomUUID()+'.tmp');
  try {
    const handle=await open(temporary,'wx',0o600);
    try {await handle.writeFile(JSON.stringify(store));await handle.sync();} finally {await handle.close();}
    await rename(temporary,path.join(dataDir,'store.json'));
  } finally {await rm(temporary,{force:true});}
}
export function createService({dataDir,catalogPath,now=()=>new Date().toISOString()}) {
  if(!dataDir||!catalogPath) throw new Error('Data directory and catalog path required');
  async function catalog() {return validateCatalog(JSON.parse(await readFile(catalogPath,'utf8')));}
  async function execute(operation,request={}) {
    let revision=0;
    try {
      if(operation==='command') {
        await mkdir(dataDir,{recursive:true}); const unlock=await lock(dataDir);
        try {
          const store=await readStore(dataDir);revision=store.revision;
          const current=await catalog();const outcome=command(current,store,request,{timestamp:now()});
          if(!outcome.replay) await persist(dataDir,outcome.store);
          return {ok:true,revision:outcome.store.revision,data:outcome.result};
        } finally {await unlock();}
      }
      const store=await readStore(dataDir);revision=store.revision;
      let data;
      switch(operation) {
        case 'catalog': data=await catalog();break;
        case 'quote': data=quote(await catalog(),store,request);break;
        case 'availability': data=availability(await catalog(),store,request);break;
        case 'reservations': data=reservations(store);break;
        case 'maintenance': data=maintenance(store);break;
        case 'report': data=report(store);break;
        default: throw new DomainError('VALIDATION','Unknown operation');
      }
      return {ok:true,revision,data};
    } catch(error) {
      if(error instanceof DomainError) return {ok:false,revision,error:{code:error.code,message:error.message}};
      // Invalid existing files are preserved and reported, without exposing filesystem details.
      return {ok:false,revision,error:{code:'VALIDATION',message:'Invalid catalog or store data'}};
    }
  }
  return {execute};
}
