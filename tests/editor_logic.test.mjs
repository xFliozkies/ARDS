// Unit tests for website/public/editor.js using a fake textarea (no browser needed).
// Run: node --test tests/editor_logic.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const pub=path.join(here,'..','website','public');

class FakeTextarea{
  constructor(value=''){this.value=value;this.selectionStart=this.selectionEnd=value.length;this.handlers={};}
  focus(){globalThis.document.activeElement=this;}
  setSelectionRange(s,e){this.selectionStart=s;this.selectionEnd=e;}
  setRangeText(text,s,e){this.value=this.value.slice(0,s)+text+this.value.slice(e);this.selectionStart=this.selectionEnd=s+text.length;}
  dispatchEvent(){}
  addEventListener(type,fn){this.handlers[type]=fn;}
  press(key,mods={}){
    const event={key,shiftKey:false,ctrlKey:false,metaKey:false,altKey:false,isComposing:false,defaultPrevented:false,
      preventDefault(){this.defaultPrevented=true;},...mods};
    this.handlers.keydown(event);
    return event;
  }
}

// execCommand is unavailable here, so every edit goes through the setRangeText fallback.
globalThis.document={activeElement:null,execCommand:()=>false};
globalThis.window=globalThis;
await import(pathToFileURL(path.join(pub,'editor.js')).href);
const Editor=globalThis.ARDSEditor;

function boxed(value){const ta=new FakeTextarea(value);Editor.bindTextarea(ta);return ta;}

test('Enter continues a numbered list',()=>{
  const ta=boxed('1. first');
  const e=ta.press('Enter');
  assert.equal(e.defaultPrevented,true);
  assert.equal(ta.value,'1. first\n2. ');
});
test('Enter continues a bullet list and keeps indentation',()=>{
  const ta=boxed('  - item');
  ta.press('Enter');
  assert.equal(ta.value,'  - item\n  - ');
});
test('Enter on an empty list item ends the list',()=>{
  const ta=boxed('1. first\n2. ');
  ta.press('Enter');
  assert.equal(ta.value,'1. first\n');
});
test('Enter on a normal line is left to the browser',()=>{
  const ta=boxed('Let D be the set of inputs.');
  const e=ta.press('Enter');
  assert.equal(e.defaultPrevented,false);
  assert.equal(ta.value,'Let D be the set of inputs.');
});
test('Tab inserts two spaces; Escape then Tab, and Shift+Tab, leave the box',()=>{
  const ta=boxed('x');
  assert.equal(ta.press('Tab').defaultPrevented,true);
  assert.equal(ta.value,'x  ');
  ta.press('Escape');
  assert.equal(ta.press('Tab').defaultPrevented,false);
  assert.equal(ta.value,'x  ');
  ta.handlers.blur();
  assert.equal(ta.press('Tab',{shiftKey:true}).defaultPrevented,false);
});
test('Math delimiter snippets leave the caret between the delimiters',()=>{
  const ta=boxed('a ');
  const inline=Editor.SYMBOLS.find(s=>s.label==='\\( \\)');
  Editor.insertAtCaret(ta,inline.text,inline.back);
  assert.equal(ta.value,'a \\(  \\)');
  assert.equal(ta.selectionStart,5);
  const display=Editor.SYMBOLS.find(s=>s.label==='\\[ \\]');
  const tb=boxed('');
  Editor.insertAtCaret(tb,display.text,display.back);
  assert.equal(tb.value,'\\[\n\n\\]');
  assert.equal(tb.selectionStart,3);
});
test('Insertion replaces the selection and keeps the surrounding text',()=>{
  const ta=boxed('for x in S');
  ta.setSelectionRange(4,5);
  Editor.insertAtCaret(ta,'∈');
  assert.equal(ta.value,'for ∈ in S');
});
test('Per-section outlines come from the manual skeleton in guide.js',()=>{
  const guide=fs.readFileSync(path.join(pub,'guide.js'),'utf8');
  for(const [section,text] of Object.entries(Editor.SKELETONS)){
    for(const line of text.split('\n').filter(Boolean)){
      assert.ok(guide.includes(line),section+': "'+line+'" is not in the manual skeleton');
    }
  }
  assert.deepEqual(Object.keys(Editor.SKELETONS),['problem','procedure','correctness','complexity']);
});
