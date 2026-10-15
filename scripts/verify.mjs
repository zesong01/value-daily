import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {reportSchema} from '../src/report-schema.ts';
const root=new URL('../public/reports/',import.meta.url);
for(const file of await readdir(root)){
 if(!/^\d{4}-\d{2}-\d{2}-(AM|PM)\.json$/.test(file)&&file!=='latest.json')continue;
 const data=JSON.parse((await readFile(new URL(file,root),'utf8')).replace(/^\uFEFF/,''));
 reportSchema.parse(data);
}
const report=JSON.parse((await readFile(new URL('latest.json',root),'utf8')).replace(/^\uFEFF/,''));
const badFact=structuredClone(report);badFact.ideas[0].evidence[0].sourceIds=[];assert.equal(reportSchema.safeParse(badFact).success,false);
const badRef=structuredClone(report);badRef.conclusions[0].sourceIds=['unknown'];assert.equal(reportSchema.safeParse(badRef).success,false);
const badQuote=structuredClone(report);badQuote.markets[0].value=1234;badQuote.markets[0].asOf='';assert.equal(reportSchema.safeParse(badQuote).success,false);
const missingQuote=structuredClone(report);missingQuote.markets[0].value=null;missingQuote.markets[0].change=1;assert.equal(reportSchema.safeParse(missingQuote).success,false);
const index=JSON.parse((await readFile(new URL('index.json',root),'utf8')).replace(/^\uFEFF/,''));
for(const entry of index.entries)assert.ok(await readFile(new URL(entry.id+'.json',root)));
assert.equal(new Set(index.entries.map(e=>e.id)).size,index.entries.length);
console.log('PASS: all reports, facts, citations, quote timestamps and archive index.');
