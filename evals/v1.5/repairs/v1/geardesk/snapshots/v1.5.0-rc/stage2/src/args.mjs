export function parseArgs(argv,{server=false}={}) {
  const result={};let operation;
  for(let i=0;i<argv.length;i++) {
    const arg=argv[i];
    if(['--data-dir','--catalog','--port'].includes(arg)) {if(i+1>=argv.length) throw new Error('Missing '+arg);result[arg.slice(2).replaceAll('-','')]=argv[++i];}
    else if(!operation) operation=arg;else throw new Error('Unexpected argument');
  }
  if(!result.datadir||!result.catalog||(!server&&!operation)) throw new Error('Usage: --data-dir PATH --catalog PATH '+(server?'--port PORT':'OPERATION'));
  const port=result.port===undefined?3000:Number(result.port);
  if(server&&(!Number.isInteger(port)||port<0||port>65535)) throw new Error('Invalid port');
  return {dataDir:result.datadir,catalogPath:result.catalog,port,operation};
}
