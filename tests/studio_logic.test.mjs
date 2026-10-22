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
