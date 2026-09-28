// Read-only import and render. Never exports or changes an XLSX.
const fs=require('node:fs/promises');
const path=require('node:path');
(async()=>{
 const {FileBlob,SpreadsheetFile}=await import(require.resolve('@oai/artifact-tool'));
 const root=path.join(__dirname,'documents');
 for(const name of (await fs.readdir(root)).sort()){
  const dir=path.join(root,name);const spec=JSON.parse(await fs.readFile(path.join(dir,'workbook-source.json'),'utf8'));
  const result={cell:name,engine:'Artifact Tool import/render; original XLSX unchanged',sheet:spec.sheet,range:'A1:L24'};
  try{
   const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(spec.path));
   const inspect=await wb.inspect({kind:'region',sheetId:spec.sheet,range:'A1:L24',maxChars:8000,tableMaxRows:8,tableMaxCols:12});
   await fs.writeFile(path.join(dir,'workbook-region.ndjson'),inspect.ndjson);
   const image=await wb.render({sheetName:spec.sheet,range:'A1:L24',scale:1,format:'png'});
   await fs.writeFile(spec.output,new Uint8Array(await image.arrayBuffer()));result.rendered=true;
  }catch(e){result.rendered=false;result.error=String(e)}
  await fs.writeFile(path.join(dir,'workbook-render.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }
})().catch(e=>{console.error(String(e));process.exitCode=1});
