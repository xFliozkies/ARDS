/* Full local UI regression/axe checks. Run against workspace_fixture.py --count 30.
   Playwright is a development tool, not a shipped runtime dependency.
   ARDS_PLAYWRIGHT_MODULE may point to its index.mjs outside the repository.
   ARDS_UI_TEST_URL must point to the disposable fixture, never the learner DB.
*/
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const {chromium}=await import(process.env.ARDS_PLAYWRIGHT_MODULE||'playwright');
// With no URL, own and clean up fresh synthetic fixtures automatically.
const {spawn}=await import('node:child_process');
const fixtures=[];
async function startFixture(count){
 const child=spawn('python3',[new URL('./workspace_fixture.py',import.meta.url).pathname,'--count',String(count)],{stdio:['ignore','pipe','ignore']});fixtures.push(child);
 return await new Promise((resolve,reject)=>{child.stdout.once('data',chunk=>resolve(chunk.toString().trim()));child.once('error',reject);child.once('exit',code=>reject(Error('Fixture exited '+code)));});
}
process.on('exit',()=>{for(const child of fixtures)child.kill('SIGINT');});
const base=process.env.ARDS_UI_TEST_URL||await startFixture(30);
const output=process.env.ARDS_SCREENSHOT_DIR||'/tmp/ards-studio-ui';await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.ARDS_CHROMIUM_PATH||undefined,args:['--no-sandbox']});
try {
const context=await browser.newContext({permissions:['clipboard-read','clipboard-write'],acceptDownloads:true});
const page=await context.newPage();const errors=[],external=[],responses=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(!r.url().startsWith(base))external.push(r.url());});
page.on('response',async r=>{if(r.url().includes('/api/')&&!r.url().includes('/api/reveal/')){try{responses.push(await r.text());}catch{}}});
const visible=async id=>page.locator(id).first().waitFor({state:'visible'});
const go=async hash=>{await page.evaluate(hash=>{location.hash=hash;},hash);};
await page.goto(base+'/#/');await visible('.problem-item');
assert.match(await page.locator('.problem-item').first().textContent(),/Synthetic UI problem/,'Browser writes require the synthetic fixture');
await page.locator('#more-filters-toggle').click();await visible('#filter-topic');
await page.locator('#filter-topic').selectOption('1');await page.waitForTimeout(200);
await page.locator('#filter-chips').getByRole('button',{name:'Remove Synthetic topic 1'}).click();
await page.waitForTimeout(200);
await page.locator('#page-size').selectOption('12');await page.locator('#filter-level').selectOption('2');
await page.waitForTimeout(200);await page.locator('#filter-chips').getByRole('button',{name:'Remove Level 2'}).click();
await page.waitForTimeout(200);
await page.locator('#page-next').click();await page.waitForTimeout(200);
assert.match(await page.locator('#pagination-summary').textContent(),/13–24/);
await page.reload();await visible('.problem-item');assert.match(await page.locator('#pagination-summary').textContent(),/13–24/);
await page.locator('.problem-item').first().click();await visible('#view-problem');
await page.goBack();await visible('#view-library');
assert.match(await page.locator('#pagination-summary').textContent(),/13–24/);
await page.goForward();await visible('#view-problem');
await go('#/problem/RACG-0003');await page.locator('#problem-title').filter({hasText:'Synthetic Lantern'}).waitFor();
await page.locator('.assessment-review').waitFor();assert.equal(await page.locator('[data-verdict="undetermined"]').count(),1);
assert.equal(await page.locator('.reference-comparison').count(),0);
for(const s of ['problem','procedure','correctness','complexity']){
 await page.locator('#tab-'+s).click();await page.locator('#ppc-input').fill('Own '+s+' \\(n^2\\)');
}
await page.locator('#mode-preview').click();assert.ok(await page.locator('#ppc-preview .katex').count());
await page.locator('#mode-write').click();await page.locator('#save-draft').click();await page.waitForTimeout(300);
await page.locator('#submit-ppc').click();await visible('#workspace-dialog-overlay');
await page.locator('#workspace-dialog-actions').getByRole('button',{name:'Cancel'}).click();
await page.locator('#reveal-reference').click();await visible('#workspace-dialog-overlay');
await page.locator('.reveal-reflection').fill('Unresolved boundary');
await page.locator('#workspace-dialog-actions').getByRole('button',{name:'Cancel'}).click();
assert.equal(await page.locator('.reference-comparison').count(),0);
assert.ok(responses.every(s=>!s.includes('TEACHER_SENTINEL')&&!s.includes('PRIVATE_DRAFT_SENTINEL')),'pre-reveal public response privacy');
assert.ok(!(await page.locator('body').textContent()).includes('TEACHER_SENTINEL'));
await go('#/drafts');await visible('.draft-table');
const downloading=page.waitForEvent('download');await page.locator('#export-all-json').click();
const download=await downloading;const exported=JSON.parse(await fs.readFile(await download.path(),'utf8'));
const exportedDraft=exported.drafts.find(x=>x.id==='RACG-0003');assert.equal(exportedDraft.sections.correctness,'Own correctness \\(n^2\\)');
assert.ok(!JSON.stringify(exported).includes('TEACHER_SENTINEL'));
const axe=await fs.readFile(new URL('./vendor/axe.min.js',import.meta.url),'utf8');
for(const width of [375,768,1280]){
 await page.setViewportSize({width,height:900});
 for(const [name,hash,selector] of [['library','#/','#view-library'],['problem','#/problem/RACG-0003','#view-problem'],['manual','#/method/proof','#view-guide'],['overview','#/overview','#view-overview'],['drafts','#/drafts','#view-drafts']]){
  await go(hash);await visible(selector);await page.waitForTimeout(200);
  if(name==='manual')await visible('#manual-chapter-content .manual-lesson:not([hidden])');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'horizontal overflow '+name+' '+width);
  await page.evaluate(axe);const results=await page.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}));
  const severe=results.violations.filter(x=>['serious','critical'].includes(x.impact));
  await fs.writeFile(path.join(output,`${name}-${width}-axe.json`),JSON.stringify(results.violations,null,2));
  assert.deepEqual(severe.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)})),[],name+' '+width+' axe');
  await page.screenshot({path:path.join(output,`${name}-${width}.png`),fullPage:true});
 }
}
await page.setViewportSize({width:1280,height:900});await go('#/problem/RACG-0003');await visible('#view-problem');
// Dialog focus trap and focus restoration, with keyboard alone.
await page.locator('#editor-open-guide').focus();await page.keyboard.press('Enter');await visible('#workspace-dialog-overlay');
await page.keyboard.press('Shift+Tab');assert.ok(await page.locator('#workspace-dialog-overlay').evaluate(el=>el.contains(document.activeElement)));
await page.keyboard.press('Escape');assert.equal(await page.locator('#editor-open-guide').evaluate(el=>el===document.activeElement),true);
await page.keyboard.press('Control+k');await visible('#search-overlay');
await page.locator('#command-query').fill('manual chapter');await page.waitForTimeout(250);assert.ok(await page.locator('#command-results mark').count());
await page.keyboard.press('Escape');
await page.emulateMedia({media:'print'});assert.equal(await page.locator('.editor-panel').isVisible(),false);assert.equal(await page.locator('.statement-panel').isVisible(),true);
await page.pdf({path:path.join(output,'statement-print.pdf')});await page.emulateMedia({media:'screen'});
// Expired writes must retain a recoverable mirror without displaying the token.
await page.route('**/api/drafts/RACG-0003',route=>route.request().method()==='POST'?route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({error:'Missing local session token or JSON content type.'})}):route.continue());
await page.locator('#ppc-input').fill('Recover this unsaved text');await page.locator('#save-draft').click();await visible('#session-banner');
assert.match(await page.locator('#save-status').textContent(),/Save failed/);
assert.match(await page.evaluate(()=>localStorage.getItem('ards-mirror:RACG-0003')),/Recover this/);
page.once('dialog',dialog=>dialog.accept());await page.reload();await visible('#workspace-dialog-overlay');
assert.match(await page.locator('#workspace-dialog-title').textContent(),/Recover unsaved text/);
await page.locator('#workspace-dialog-actions').getByRole('button',{name:'Use browser copy'}).click();
assert.equal(await page.locator('#ppc-input').inputValue(),'Recover this unsaved text');
await page.unroute('**/api/drafts/RACG-0003');await page.locator('#save-draft').click();await page.waitForTimeout(250);
// Reference content/comparison is created only after affirmative consent.
await page.locator('#reveal-reference').click();await page.locator('#workspace-dialog-actions').getByRole('button',{name:'Reveal PPC',exact:true}).click();
await visible('.reference-comparison');
await page.emulateMedia({media:'print'});assert.equal(await page.locator('#app').isVisible(),false);await page.pdf({path:path.join(output,'reference-print.pdf')});await page.emulateMedia({media:'screen'});
assert.match(await page.locator('.reference-modal-content').textContent(),/TEACHER_SENTINEL/);
await page.keyboard.press('Escape');
await go('#/problem/UI-PRIVATE');await visible('#view-unavailable');
assert.ok(!(await page.locator('body').textContent()).includes('PRIVATE_DRAFT_SENTINEL'));
assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
console.log('PASS: routing/history/pagination, reviews, draft JSON, preview, consent/comparison, keyboard dialog, expired-save recovery, private selection 404; 15 responsive screenshots and axe checks');
const emptyBase=await startFixture(0),empty=await context.newPage();await empty.goto(emptyBase+'/#/overview');
await empty.locator('#view-overview').waitFor({state:'visible'});await empty.waitForTimeout(200);
assert.match(await empty.locator('#overview-levels').textContent(),/No released problems/);
assert.equal(await empty.locator('#sidebar-count').textContent(),'0');
await empty.locator('#overview-levels a').click();await empty.locator('#view-guide').waitFor({state:'visible'});
await empty.goBack();await empty.reload();await empty.locator('#view-overview').waitFor({state:'visible'});
await empty.evaluate(axe);assert.deepEqual(await empty.evaluate(async()=> (await axe.run()).violations.filter(x=>['serious','critical'].includes(x.impact)).map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)}))),[]);
console.log('PASS: empty overview/manual/back/refresh/axe, print statement and reference PDFs');
} finally {await browser.close();for(const child of fixtures)child.kill('SIGINT');}
