import {createService} from './src/service.mjs';

function args(argv) {
  const values={}; let operation;
  for(let i=0;i<argv.length;i++) {
    if(argv[i]==='--data-dir'||argv[i]==='--catalog') values[argv[i]]=argv[++i];
    else if(!operation) operation=argv[i]; else throw new Error('Unexpected argument');
  }
  if(!values['--data-dir']||!values['--catalog']||!operation) throw new Error('Usage: node cli.mjs --data-dir PATH --catalog PATH OPERATION');
  return {dataDir:values['--data-dir'],catalogPath:values['--catalog'],operation};
}
let result;
try {
  const {dataDir,catalogPath,operation}=args(process.argv.slice(2));
  let input=''; for await(const chunk of process.stdin) input+=chunk;
  const request=input.trim()?JSON.parse(input):{};
  result=await createService({dataDir,catalogPath}).execute(operation,request);
} catch(e) {result={ok:false,revision:0,error:{code:'VALIDATION',message:e.message}};}
process.stdout.write(JSON.stringify(result)+'\n');
if(!result.ok) process.exitCode=1;
