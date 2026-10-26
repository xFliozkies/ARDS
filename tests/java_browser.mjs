/* Disposable synthetic fixture only; no learner archive access. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {spawn} from 'node:child_process';
const {chromium}=await import(process.env.ARDS_PLAYWRIGHT_MODULE||'playwright');
const fixture=spawn('python3',[new URL('./workspace_fixture.py',import.meta.url).pathname],{stdio:['ignore','pipe','ignore']});
const base=await new Promise((resolve,reject)=>{fixture.stdout.once('data',x=>resolve(x.toString().trim()));fixture.once('error',reject);});
const browser=await chromium.launch({headless:true,executablePath:process.env.ARDS_CHROMIUM_PATH||undefined,args:['--no-sandbox']});
try{
 const axe=await fs.readFile(new URL('./vendor/axe.min.js',import.meta.url),'utf8');
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/java-editor.css',async route=>{const response=await route.fetch();await route.fulfill({response,body:(await response.text())+'\n#java-source::-webkit-scrollbar{width:15px;height:15px}'});});
 await page.goto(base+'/#/problem/RACG-0003');
 await page.locator('#choose-java').click();
 await page.locator('#java-save').filter({hasText:'Saved locally'}).waitFor();
 // Force both scrollbars and click a rendered token at the bottom of a long file.
 for(const width of [1280,375]){
  await page.setViewportSize({width,height:900});
  if(width===375)await page.locator('#panel-write').click();
  for(const trailing of ['', '\n']){
   const source=Array.from({length:40},(_,i)=>'    for (int i = 0; i < 100; i++) { // '+i+' '+ 'x'.repeat(100)).join('\n')+trailing;
   await page.locator('#java-source').fill(source);
   await page.locator('#java-source').scrollIntoViewIfNeeded();
   await page.locator('#java-source').evaluate(e=>{e.scrollTop=e.scrollHeight;e.scrollLeft=16;e.dispatchEvent(new Event('scroll'));});
   await page.locator('#java-highlight .java-token-keyword').nth(76).waitFor({state:'attached'});
   const target=await page.locator('#java-highlight .java-token-keyword').nth(76).boundingBox();
   await page.mouse.click(target.x+2,target.y+target.height/2);
   const state=await page.locator('#java-source').evaluate(e=>({line:e.value.slice(0,e.selectionStart).split('\n').length,top:e.scrollTop,left:e.scrollLeft,width:e.clientWidth,height:e.clientHeight}));
   assert.equal(state.line,39,`${width}px: clicked rendered line 39`);
   const mirror=await page.locator('#java-highlight').evaluate(e=>({top:e.scrollTop,left:e.scrollLeft,width:e.clientWidth,height:e.clientHeight}));
   assert.deepEqual(mirror,{top:state.top,left:state.left,width:state.width,height:state.height});
  }
 }
 await page.setViewportSize({width:1280,height:900});
 await page.locator('#java-source').fill('one\ntwo');
 await page.locator('#java-source').selectText();await page.locator('#java-source').press('Tab');
 assert.equal(await page.locator('#java-source').inputValue(),'    one\n    two');
 await page.locator('#java-source').press('Shift+Tab');
 assert.equal(await page.locator('#java-source').inputValue(),'one\ntwo');
 for(const [open,close] of [['{','}'],['(',')'],['[',']'],["'","'"],['"','"']]){
  await page.locator('#java-source').fill('');await page.locator('#java-source').press(open);
  assert.equal(await page.locator('#java-source').inputValue(),open+close);
  await page.locator('#java-source').press(close);
  assert.equal(await page.locator('#java-source').inputValue(),open+close);
  await page.locator('#java-source').fill('');await page.locator('#java-source').press(open);await page.locator('#java-source').press('Backspace');
  assert.equal(await page.locator('#java-source').inputValue(),'');
 }
 await page.locator('#java-source').press('{');await page.locator('#java-source').press('Enter');
 assert.equal(await page.locator('#java-source').inputValue(),'{\n    \n}');
 const code='public class Main { public static void main(String[] args) {System.out.println("<b>42</b>");} }';
 await page.locator('#java-source').fill(code);
 assert.equal(await page.locator('#java-highlight .java-token-keyword').first().textContent(),'public');
 assert.equal(await page.locator('#java-highlight b').count(),0);
 assert.equal(await page.locator('#java-timed').evaluate(e=>e.previousElementSibling.id),'toggle-focus');
 await page.locator('#java-save').filter({hasText:'Saved locally'}).waitFor();
 await page.locator('#choose-ppc').click();
 assert.equal(await page.locator('#java-source').isVisible(),false);
 assert.equal(await page.locator('#save-draft').isVisible(),true);
 await page.locator('#ppc-input').fill('My independent draft survives editor switching.');
 await page.locator('#choose-ppc').focus();await page.locator('#choose-ppc').press('ArrowRight');
 assert.equal(await page.locator('#choose-java').getAttribute('aria-selected'),'true');
 assert.equal(await page.locator('#java-source').inputValue(),code);
 assert.equal(await page.locator('#save-draft').isVisible(),false);
 assert.equal(await page.locator('#submit-ppc').isVisible(),false);
 await page.locator('#choose-java').press('Home');
 assert.equal(await page.locator('#ppc-input').inputValue(),'My independent draft survives editor switching.');
 await page.locator('#choose-ppc').press('End');
 await page.locator('#java-timed').click();
 await page.locator('#java-timed').filter({hasText:'Pause'}).waitFor();
 await page.locator('#java-timed').click();
 await page.locator('#java-timed').filter({hasText:'Resume'}).waitFor();
 await page.reload();await page.locator('#java-save').filter({hasText:'Saved locally'}).waitFor();
 await page.locator('#java-timed').filter({hasText:'Resume'}).waitFor();
 await page.locator('#java-timed').click();
 await page.locator('#java-timed').filter({hasText:'Pause'}).waitFor();
 await page.locator('#java-input-mode').selectOption('custom');
 await page.locator('#java-stdin').fill('');await page.locator('#java-run').click();
 await page.locator('#java-result').filter({hasText:'Run complete'}).waitFor();
 assert.match(await page.locator('#java-result').textContent(),/<b>42<\/b>/);
 assert.equal(await page.locator('#java-result b').count(),0);
 assert.doesNotMatch(await page.locator('#java-timed').textContent(),/Finished/);
 await page.reload();await page.locator('#java-save').filter({hasText:'Saved locally'}).waitFor();
 assert.equal(await page.locator('#choose-java').getAttribute('aria-selected'),'true');
 assert.equal(await page.locator('#ppc-input').isVisible(),false);
 assert.equal(await page.locator('#java-source').inputValue(),code);
 assert.match(await page.locator('#java-timed').textContent(),/\d{2}:\d{2}:\d{2} · Pause/);
 await page.locator('#choose-ppc').click();

 await page.locator('#choose-java').click();
 await page.locator('#java-source').fill('public class Main { invalid }');await page.locator('#java-run').click();
 await page.locator('#java-result').filter({hasText:'Compilation error'}).waitFor();
 assert.doesNotMatch(await page.locator('#java-timed').textContent(),/Finished/);
 const failure={verdict:'Wrong answer',passed:3,total:185,failure:{number:4,verdict:'Wrong answer',input:'<input>\n',stdout:'actual\n',expected:'expected\n',stderr:'diagnostic'}};
 await page.route('**/api/java/RACG-0003',async route=>{
  const body=route.request().postDataJSON();
  if(body.action==='submit')return route.fulfill({json:failure});
  const response=await route.fetch();const data=await response.json();
  if(body.action==='load')data.last_submission=failure;
  await route.fulfill({json:data});
 });
 await page.locator('#java-submit').click();
 await page.locator('#java-result').filter({hasText:'Failed test 4'}).waitFor();
 for(const text of ['3/185','<input>','actual','expected','diagnostic'])assert.ok((await page.locator('#java-result').textContent()).includes(text));
 assert.equal(await page.locator('#java-result input').count(),0);
 await page.reload();await page.locator('#java-result').filter({hasText:'Failed test 4'}).waitFor();
 await page.unroute('**/api/java/RACG-0003');
 await page.locator('#java-stop').click();
 await page.locator('#java-timed').filter({hasText:'Finished'}).waitFor();
 assert.equal(await page.locator('#java-stop').isVisible(),false);
 await fs.mkdir('/tmp/ards-java-ui',{recursive:true});
 for(const width of [1280,375]){
  await page.setViewportSize({width,height:900});
  if(width===375){await page.locator('#panel-write').click();}
  await page.locator('#choose-java').scrollIntoViewIfNeeded();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.evaluate(axe);
  const violations=await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})));
  assert.deepEqual(violations,[],width+' Java accessibility');
  await page.screenshot({path:'/tmp/ards-java-ui/'+width+'.png'});
 }
 assert.deepEqual(errors,[]);console.log('PASS: PPC/Java picker, keyboard tabs, preserved drafts, remembered choice, contextual actions, timer visibility, Java editor, autosave/reload, timer persistence, custom run, compilation error, escaped output, desktop/mobile layout');
}finally{await browser.close();fixture.kill('SIGINT');}
