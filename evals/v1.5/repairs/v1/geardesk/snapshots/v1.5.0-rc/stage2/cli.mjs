import {parseArgs} from './src/args.mjs';
import {createService} from './src/service.mjs';
let response;
try {
  const {dataDir,catalogPath,operation}=parseArgs(process.argv.slice(2));
  let body='';for await (const chunk of process.stdin) body+=chunk;
  let request={};if(body.trim()) request=JSON.parse(body);
  response=await createService({dataDir,catalogPath}).execute(operation,request);
} catch(error) {response={ok:false,revision:0,error:{code:'VALIDATION',message:error instanceof SyntaxError?'Invalid JSON':error.message}};}
process.stdout.write(JSON.stringify(response)+'\n');
if(!response.ok) process.exitCode=1;
