/* Own a fresh disposable fixture by default; optional ARDS_UI_TEST_URL must be synthetic. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.ARDS_PLAYWRIGHT_MODULE||'playwright');
let fixture;
let base=process.env.ARDS_UI_TEST_URL;
if(!base){
 const {spawn}=await import('node:child_process');
 fixture=spawn('python3',[new URL('./workspace_fixture.py',import.meta.url).pathname,'--count','30'],{stdio:['ignore','pipe','ignore']});
 process.on('exit',()=>fixture.kill('SIGINT'));
 base=await new Promise((resolve,reject)=>{fixture.stdout.once('data',x=>resolve(x.toString().trim()));fixture.once('error',reject);fixture.once('exit',code=>reject(Error('Fixture exited '+code)));});
}
const browser=await chromium.launch({executablePath:process.env.ARDS_CHROMIUM_PATH||undefined,args:['--no-sandbox']});
try{
const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(base);await page.locator('.problem-item').first().waitFor();
assert.match(await page.locator('.problem-item').first().textContent(),/Synthetic UI/);
assert.equal(await page.locator('.stats-strip').count(),0);
const libraryOrder=await page.evaluate(()=>['filter-set','problem-pagination','problem-list'].map(id=>document.getElementById(id).getBoundingClientRect().top));
assert.ok(libraryOrder[0]<libraryOrder[1]&&libraryOrder[1]<libraryOrder[2],'pagination between filters and table');
assert.equal(await page.locator('#result-count').textContent(),'');
assert.equal(await page.locator('#library-search').evaluate(el=>getComputedStyle(el).borderTopWidth),'0px');
const heights=await page.locator('#filter-set > .library-search, #filter-set > .select-wrap:not(.hidden), #filter-set > button').evaluateAll(els=>els.filter(el=>getComputedStyle(el).display!=='none').map(el=>el.getBoundingClientRect().height));
assert.equal(new Set(heights).size,1);
const initialTop=await page.locator('.problem-table').evaluate(el=>el.getBoundingClientRect().top);
await page.locator('#library-search').fill('Synthetic');await page.waitForTimeout(650);
assert.match(await page.locator('#result-count').textContent(),/matching problems/);
assert.equal(await page.locator('#filter-chips').textContent(),'','search does not duplicate input as a chip');
const feedbackHeight=await page.locator('#filter-summary').evaluate(el=>el.getBoundingClientRect().height);
assert.ok(feedbackHeight<=40,'compact search feedback');
assert.ok(await page.locator('.problem-table').evaluate(el=>el.getBoundingClientRect().top)>initialTop);
assert.notEqual(await page.locator('.search-result-space').evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
await page.locator('#library-search').fill('');await page.waitForTimeout(650);assert.equal(await page.locator('#result-count').textContent(),'');
assert.equal(await page.locator('.problem-table').evaluate(el=>el.getBoundingClientRect().top),initialTop);
await page.screenshot({path:'/tmp/ards-polish-library.png',fullPage:true});
await page.goto(base+'/#/problem/RACG-0003');await page.locator('#view-problem').waitFor({state:'visible'});
assert.equal(await page.locator('#go-back').innerText(),'Back');
assert.equal(await page.locator('.editor-heading,#section-kicker').count(),0);
assert.equal(await page.locator('#reveal-reference').evaluate(el=>el.parentElement.lastElementChild===el),true);
assert.equal(await page.locator('.editor-toolbar').evaluate(el=>!!el.closest('.writing-area')),false);
assert.equal(await page.locator('#submit-ppc').evaluate(el=>!!el.closest('.editor-submit-actions')),true);
assert.equal(await page.locator('#next-section').evaluate(el=>!!el.closest('.editor-submit-actions')),true);
assert.equal(await page.locator('#statement-nav > span').count(),0);
const rects=await page.evaluate(()=>Object.fromEntries(['problem-title','statement-nav','copy-statement'].map(id=>[id,document.getElementById(id).getBoundingClientRect().top])));
assert.ok(rects['statement-nav']<rects['problem-title']&&rects['copy-statement']<rects['problem-title']);
const actions=await page.locator('.problem-top-right').boundingBox(),nav=await page.locator('.problem-top').boundingBox();
assert.ok(Math.abs(actions.x+actions.width/2-(nav.x+nav.width/2))<2);
const math=await page.evaluate(()=>{
 const target=document.createElement('div');window.ARDSStatement.render(target,{presentation_data:{description:'Synthetic constraint regression',constraints:['\\(1\\le A<B\\le10^6\\)','\\(0\\le L\\le U\\le10^{15}\\)']}});
 return {count:target.querySelectorAll('.katex').length,errors:target.querySelectorAll('.katex-error').length};
});assert.deepEqual(math,{count:2,errors:0});
for(const width of [375,768,1280]){
 await page.setViewportSize({width,height:900});await page.waitForTimeout(100);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow '+width);
 const toolCenter=await page.locator('.toolbar-actions').evaluate(el=>{const own=el.getBoundingClientRect(),bar=el.closest('.editor-toolbar').getBoundingClientRect();return Math.abs(own.x+own.width/2-bar.x-bar.width/2);});
 if(width>1000)assert.ok(toolCenter<2,'centered tool group');
 if(width<=1000)await page.locator('#panel-problem').click();
 await page.locator('.statement-panel').evaluate(el=>el.scrollTop=550);
 const panel=await page.locator('.statement-panel').boundingBox(),sticky=await page.locator('.statement-controls').boundingBox();
 assert.ok(Math.abs(panel.y-sticky.y)<3,'sticky header '+width);
 await page.screenshot({path:'/tmp/ards-polish-problem-'+width+'.png',fullPage:true});
}
await page.setViewportSize({width:1280,height:900});await page.locator('#go-back').click();await page.locator('#view-drafts').waitFor({state:'visible'});
await page.goto(base+'/#/problem/RACG-0003');await page.locator('#view-problem').waitFor({state:'visible'});
await page.locator('#next-problem').click();await page.waitForTimeout(500);assert.notEqual(await page.locator('#problem-id').textContent(),'RACG-0003');
assert.deepEqual(errors,[]);
console.log('PASS: uniform controls, borderless search, animated count, removed labels, toolbar placement, centered actions, LaTeX constraints, responsive sticky controls, workspace Back and Next');
}finally{await browser.close();fixture?.kill('SIGINT');}
