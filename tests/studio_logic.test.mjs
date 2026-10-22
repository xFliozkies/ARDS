import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),logic=require('../website/public/studio-logic.js');
test('routes reject invalid IDs and tolerate malformed escapes',()=>{
 assert.deepEqual(logic.parseRoute('#/problem/RACG-0003'),{name:'problem',id:'RACG-0003'});
 assert.equal(logic.parseRoute('#/problem/../../private').invalid,true);
 assert.equal(logic.parseRoute('#/problem/%E0%A4%A').invalid,true);
 for(const name of ['library','drafts','overview'])assert.equal(logic.parseRoute(logic.hashFor({name})).name,name);
});
test('progress counts problems once and preserves zero levels',()=>{
 assert.equal(logic.progressSummary([]).levels.length,6);
 const result=logic.progressSummary([{difficulty:1,topic_id:7,topic_label:'One',has_attempt:1,passed:0},{difficulty:1,topic_id:7,topic_label:'One',has_attempt:1,passed:1},{difficulty:6,topic_id:8,topic_label:'Two',has_attempt:0,passed:0}]);
 assert.deepEqual(result.levels[0],{level:1,released:2,attempted:2,passed:1});
 assert.equal(result.topics[0].released,2);assert.equal(result.total,3);
});
test('draft JSON exports only student section allowlist verbatim',()=>{
 const own={problem:'  exact\ntext\n',procedure:'P2',correctness:'C',complexity:'K',teacher_ppc:'SECRET'};
 const exported=logic.draftsJson([{id:'A',draft:own,reference_ppc:'SECRET'}]);
 assert.ok(!exported.includes('SECRET'));assert.equal(JSON.parse(exported).drafts[0].sections.problem,own.problem);
});
test('lifecycle distinguishes server status from progress',()=>{
 assert.deepEqual(logic.lifecycleParam('status:evaluated'),['status','evaluated']);
 assert.deepEqual(logic.lifecycleParam('progress:revealed'),['progress','revealed']);
 assert.equal(logic.lifecycleParam('teacher:proof'),null);
});
test('next browsing uses 30/40/30 pools and renormalizes missing choices',()=>{
 const current={id:'A',topic_id:7};
 const rows=[current,{id:'B',topic_id:7,continuation_of:'A'},{id:'C',topic_id:7},{id:'D',topic_id:8}];
 const choose=(rows,roll,index=0)=>{let calls=0;return logic.pickNextProblem(rows,current,()=>calls++===0?roll:index);};
 assert.equal(choose(rows,0.29).id,'B');
 assert.equal(choose(rows,0.30,0.99).id,'C');
 assert.equal(choose(rows,0.69,0.99).id,'C');
 assert.equal(choose(rows,0.70,0.99).id,'D');
 const noContinuation=rows.filter(p=>p.id!=='B');
 assert.equal(choose(noContinuation,0.56).id,'C');
 assert.equal(choose(noContinuation,0.58,0.99).id,'D');
 assert.equal(choose([current,{id:'D',topic_id:8}],0).id,'D');
 assert.equal(choose([current],0),null);
});
test('Next excludes viewed references from every selection pool',()=>{
 const current={id:'A',topic_id:7};
 const viewed=[{id:'B',topic_id:7,continuation_of:'A',reference_revealed:1},
               {id:'C',topic_id:7,reference_revealed:true},
               {id:'D',topic_id:8,reference_revealed:1}];
 const eligible={id:'E',topic_id:8,reference_revealed:0};
 for(const roll of [0,0.29,0.3,0.69,0.7,0.99]){
  let calls=0;
  assert.equal(logic.pickNextProblem([current,...viewed,eligible],current,()=>calls++===0?roll:0.99).id,'E');
 }
 assert.equal(logic.pickNextProblem([current,...viewed],current),null);
 // Removing a viewed continuation renormalizes the remaining 40:30 pools.
 const same={id:'F',topic_id:7,reference_revealed:false};
 for(const [roll,expected] of [[0.56,'F'],[0.58,'E']]){
  let calls=0;
  assert.equal(logic.pickNextProblem([current,...viewed,same,eligible],current,()=>calls++===0?roll:0.99).id,expected);
 }
});
