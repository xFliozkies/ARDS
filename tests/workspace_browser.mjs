// Run only against the disposable fixture server described in HANDOFF_UI_UX.md.
const {chromium}=await import(process.env.ARDS_PLAYWRIGHT_MODULE||'playwright');
const base=process.env.ARDS_UI_TEST_URL;
if(!base)throw Error('Set ARDS_UI_TEST_URL to the disposable fixture server URL');
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:process.env.ARDS_CHROMIUM_PATH||undefined,headless:true,args:['--no-sandbox']});
const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']});
const page=await context.newPage();const errors=[],external=[],writes=[];
page.on('request',r=>{if(r.method()==='POST')writes.push(r.postData()||'');});
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(base))external.push(r.url());});
await page.goto(base+'/#/problem/RACG-0003');
await page.locator('#problem-title').filter({hasText:'Synthetic Lantern'}).waitFor();
for(const width of [375,768,1280]){
 await page.setViewportSize({width,height:900});
 await page.locator('#panel-problem').evaluate(el=>el.click());
 assert.equal(await page.locator('.statement-panel').isVisible(),true);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'page overflow '+width);
 if(width<=1000){
  assert.equal(await page.locator('.editor-panel').isVisible(),false);
  await page.locator('#panel-write').click();
  assert.equal(await page.locator('.editor-panel').isVisible(),true);
  await page.locator('#ppc-input').fill('Own text '+width);
  await page.locator('#panel-problem').click();await page.locator('#panel-write').click();
  assert.equal(await page.locator('#ppc-input').inputValue(),'Own text '+width);
 }
 await page.screenshot({path:(process.env.ARDS_SCREENSHOT_DIR||'/tmp')+'/workspace-'+width+'.png',fullPage:true});
}
await page.locator('#workspace-divider').focus();await page.keyboard.press('ArrowRight');
assert.equal(await page.locator('#workspace-divider').getAttribute('aria-valuenow'),'52');
await page.locator('details').filter({has:page.locator('#scratch-notes')}).evaluate(el=>el.open=true);
await page.locator('#scratch-notes').fill('Private scratch');
await page.locator('#ppc-input').fill('Student proof');
await page.locator('#self-check').evaluate(el=>el.open=true);
assert.equal(await page.locator('#self-check-questions li').count(),4);
const first=page.locator('.sample-card').first();
const sample=await first.locator('pre').textContent();
await first.getByRole('button').click();assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),sample);
await page.locator('#copy-statement').click();assert.match(await page.evaluate(()=>navigator.clipboard.readText()),/## Input Format/);
await page.locator('#save-draft').click();await page.waitForTimeout(700);
await page.reload();await page.locator('#problem-title').filter({hasText:'Synthetic Lantern'}).waitFor();
assert.equal(await page.locator('#scratch-notes').inputValue(),'Private scratch');
assert.equal(await page.locator('#ppc-input').inputValue(),'Student proof');
assert.equal(writes.some(body=>body.includes('Private scratch')),false,'scratch notes must never enter draft writes');
assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
console.log('PASS: 375/768/1280 layout, mobile preservation, keyboard divider, notes persistence, prompts, exact sample copy, Markdown copy, no page errors or external requests');
await browser.close();
