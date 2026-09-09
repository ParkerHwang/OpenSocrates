#!/usr/bin/env node
// Windows native launcher. All input stays in memory; never invoke a shell.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const [mode, host, event, ...extra] = process.argv.slice(2);
const hook = mode === 'hook';
function unavailable(code) {
  if (!hook) process.stdout.write(JSON.stringify({decision:'pass',diagnostic:{code,status:'unavailable'}})+'\n');
  process.exit(0);
}
const events = new Set(['session_started','user_prompt_submitted','skill_invoked','tool_succeeded','tool_failed','tool_batch_completed','completion_candidate','pre_compaction','post_compaction','session_ended']);
if (!['codex','claude'].includes(host) || extra.length ||
    !(hook ? events.has(event) : mode === 'decision' ? !event || event === '--stream' : mode === 'control' && !event)) unavailable('invalid_arguments');
if (process.platform !== 'win32' || process.arch !== 'x64') unavailable('unsupported_platform');
const runtime = fileURLToPath(new URL('../runtime/windows-x64/opensocrates-runtime/opensocrates-runtime.exe', import.meta.url));
if (!existsSync(runtime)) unavailable('missing_runtime');
let payload;
if (hook && host === 'codex' && event === 'session_started') {
  const chunks = []; let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 4194304) process.exit(0);
    chunks.push(chunk);
  }
  payload = Buffer.concat(chunks);
  try { if (JSON.parse(payload.toString('utf8')).source !== 'compact') process.exit(0); }
  catch { process.exit(0); }
}
const args = hook ? ['hook',event,'--host',host] : mode === 'decision' ? ['decision',...(event ? [event] : [])] : ['control','apply','--host',host];
const child = spawn(runtime,args,{windowsHide:true,stdio:[payload ? 'pipe' : 'inherit','inherit',hook ? 'ignore' : 'inherit']});
if (payload) { child.stdin.on('error',()=>{}); child.stdin.end(payload); }
child.on('error',()=>unavailable('launcher_unavailable'));
child.on('exit',code=>{process.exitCode=hook ? 0 : code ?? 1;});
// Stop only our own descendant tree when the host cancels the launcher.
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>{
  if (child.pid) spawn('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
});
