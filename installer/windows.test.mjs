import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,existsSync,rmSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {assetNameFor,isSafeArchivePath,parseChecksumText,PRODUCT_VERSION} from './opensocrates.mjs';

const root = fileURLToPath(new URL('../',import.meta.url));
test('Windows native asset identity preserves content-only filenames', {skip:process.platform!=='win32'},()=>{
  assert.equal(assetNameFor('codex'),`opensocrates-${PRODUCT_VERSION}-codex-plugin-windows-x64.zip`);
  assert.equal(assetNameFor('opencode'),`opensocrates-${PRODUCT_VERSION}-opencode-plugin.zip`);
});
test('Windows aliases and alternate streams are not archive paths',()=>{
  for(const value of ['C:/escape','a:stream','a/CON.txt','a/nul','a/file.','a/file ','a/../b','a\\b']) assert.equal(isSafeArchivePath(value),false,value);
  assert.equal(isSafeArchivePath('한글 space/file.json'),true);
});
test('checksum parser binds digest to the expected asset',()=>{
  assert.throws(()=>parseChecksumText('a'.repeat(64)+'  different.zip',assetNameFor('codex')));
});
test('Windows auto-update is explicitly unavailable',{skip:process.platform!=='win32'},()=>{
  const result=spawnSync(process.execPath,[join(root,'installer/opensocrates.mjs'),'auto-update','enable'],{encoding:'utf8'});
  assert.equal(result.status,1);
  assert.match(result.stderr,/unavailable on Windows/);
});
test('packed npm distribution carries and executes the Windows helper',{skip:process.platform!=='win32'},()=>{
  const scratch=mkdtempSync(join(tmpdir(),'OpenSocrates npm 한글 space '));
  try {
    const npm=process.env.npm_execpath || join(dirname(process.execPath),'node_modules/npm/bin/npm-cli.js');
    assert.ok(existsSync(npm));
    const packed=spawnSync(process.execPath,[npm,'pack','--json','--ignore-scripts','--pack-destination',scratch],{cwd:root,encoding:'utf8'});
    assert.equal(packed.status,0,packed.stderr);
    const archive=join(scratch,JSON.parse(packed.stdout)[0].filename);
    const unpacked=spawnSync('tar.exe',['-xzf',archive,'-C',scratch],{encoding:'utf8'});
    assert.equal(unpacked.status,0,unpacked.stderr);
    assert.ok(existsSync(join(scratch,'package/installer/windows.ps1')));
    assert.equal(readFileSync(join(scratch,'package/installer/windows.ps1'),'utf8'),readFileSync(join(root,'installer/windows.ps1'),'utf8'));
    const result=spawnSync(process.execPath,[join(scratch,'package/installer/opensocrates.mjs'),'auto-update','status'],{cwd:scratch,encoding:'utf8'});
    assert.equal(result.status,0,result.stderr);
    assert.match(result.stdout,/unavailable on Windows/);
  } finally { rmSync(scratch,{recursive:true,force:true}); }
});
