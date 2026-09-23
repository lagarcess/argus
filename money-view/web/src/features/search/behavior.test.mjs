import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';

const bundled = await build({entryPoints:[new URL('./contracts.ts',import.meta.url).pathname],bundle:true,write:false,platform:'node',format:'esm'});
const { selectionIndex, targetQuery, targetSchema } = await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString('base64')}`);

test('keyboard selection respects empty and bounded visual lists',()=>{
  assert.equal(selectionIndex(0,'ArrowDown',0),-1);
  assert.equal(selectionIndex(0,'ArrowUp',3),0);
  assert.equal(selectionIndex(2,'ArrowDown',3),2);
  assert.equal(selectionIndex(0,'End',3),2);
  assert.equal(selectionIndex(2,'Home',3),0);
  assert.equal(selectionIndex(1,'Escape',3),1);
});

test('navigation exposes only typed artifact keys, never external URLs',()=>{
  const target=targetSchema.parse({page:'chat',record_id:'conversation-1',conversation_id:'conversation-1',account_id:null,decision:null,url:'https://untrusted.example'});
  assert.deepEqual(targetQuery(target),{record_id:'conversation-1',conversation_id:'conversation-1'});
  assert.equal(targetSchema.safeParse({...target,page:'https://untrusted.example'}).success,false);
});

test('deposit and account targets retain owned record identifiers',()=>{
  const deposit=targetSchema.parse({page:'deposits',record_id:'decision-1',conversation_id:null,account_id:null,decision:'decision-1'});
  assert.deepEqual(targetQuery(deposit),{record_id:'decision-1',decision:'decision-1'});
  const transaction=targetSchema.parse({page:'transactions',record_id:'transaction-1',conversation_id:null,account_id:'account-1',decision:null});
  assert.deepEqual(targetQuery(transaction),{record_id:'transaction-1',account_id:'account-1'});
});
