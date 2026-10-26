'use strict';
(()=>{
 const el=id=>document.getElementById('java-'+id);
 let editorMode='ppc';
 try{if(localStorage.getItem('ards-editor-choice')==='java')editorMode='java';}catch{}
 const editorScroll={ppc:0,java:0};
 function chooseEditor(mode,{focus=false,initial=false}={}){
  if(mode===editorMode&&!initial){if(focus)document.getElementById('choose-'+mode).focus({preventScroll:true});return;}
  const previous=editorMode,panel=document.querySelector('.editor-panel');
  if(!initial){editorScroll[previous]=panel.scrollTop;if(previous==='ppc')saveDraft(true);else if(id&&!loading)save();}
  editorMode=mode;
  document.getElementById('view-problem').dataset.editor=mode;
  for(const name of ['ppc','java']){
   const selected=name===mode,button=document.getElementById('choose-'+name);
   button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;
   document.getElementById(name+'-workspace').hidden=!selected;
  }
  document.getElementById('editor-choice-help').textContent=mode==='java'?'':'Develop your specification, algorithm, proof, and complexity.';
  document.getElementById('panel-write').textContent=mode==='java'?'Code':'Write';
  if(!initial){try{localStorage.setItem('ards-editor-choice',mode);}catch{}panel.scrollTop=editorScroll[mode];}
  if(focus)document.getElementById('choose-'+mode).focus({preventScroll:true});
  if(mode==='java')lines();
  clock();
 }
 const starter='import java.io.*;\nimport java.util.*;\n\npublic class Main {\n    public static void main(String[] args) throws Exception {\n        // Read input and print your answer here.\n    }\n}\n';
 let id=null, session={}, timer, busy=false, loading=false, request=0, escapeTab=false;
 const pending=new Map();
 const key=problem=>'ards-java-source:'+problem;
 const keywords=new Set('abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while var record sealed permits yield true false null'.split(' '));
 function highlight(source){
  const tokens=source.match(/\/\/[^\n]*|\/\*[\s\S]*?(?:\*\/|$)|"""[\s\S]*?(?:"""|$)|"(?:\\[\s\S]|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?|\b\d[\w.]*|[A-Za-z_$][\w$]*|[\s\S]/g)||[];
  const escape=value=>value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return tokens.map(token=>{const kind=token.startsWith('//')||token.startsWith('/*')?'comment':/^['"]/.test(token)?'string':keywords.has(token)?'keyword':/^\d/.test(token)?'number':/^[A-Z][\w$]*$/.test(token)?'type':'';return kind?'<span class="java-token-'+kind+'">'+escape(token)+'</span>':escape(token);}).join('')+'\n';
 }
 function lines(){
  // Match the native editing viewport, excluding its scrollbars. Otherwise the
  // color layer clamps early at the bottom/right and drifts from the caret.
  el('highlight').style.width=el('source').clientWidth+'px';
  el('highlight').style.height=el('source').clientHeight+'px';
  el('highlight').innerHTML=highlight(el('source').value);el('highlight').scrollTop=el('source').scrollTop;el('highlight').scrollLeft=el('source').scrollLeft;el('lines').textContent=Array.from({length:el('source').value.split('\n').length},(_,i)=>i+1).join('\n');el('lines').scrollTop=el('source').scrollTop;}
 async function call(problem,action,extra={}){const previous=pending.get(problem)||Promise.resolve();const next=previous.catch(()=>{}).then(()=>api('/api/java/'+encodeURIComponent(problem),{method:'POST',body:JSON.stringify({action,...extra})}));pending.set(problem,next);try{return await next;}finally{if(pending.get(problem)===next)pending.delete(problem);}}
 function backup(){try{localStorage.setItem(key(id),el('source').value);}catch{el('save').textContent='Browser recovery unavailable';}}
 async function save(){if(!id)return;const problem=id,source=el('source').value;try{await call(problem,'save',{source});try{if(localStorage.getItem(key(problem))===source)localStorage.removeItem(key(problem));}catch{}if(problem===id&&source===el('source').value)el('save').textContent='Saved locally';}catch(e){if(problem===id)el('save').textContent='Not saved to server: '+e.message;}}
 function clock(){
  const finished=Boolean(session.accepted_at||session.stopped_at);
  el('stop').hidden=!session.started_at||finished;
  if(!session.started_at){el('timed').textContent='Start time';return;}
  const end=session.stopped_at||session.paused_at||session.accepted_at||new Date().toISOString();
  const seconds=Math.max(0,Math.floor((Date.parse(end)-Date.parse(session.started_at))/1000-(session.paused_seconds||0)));
  const elapsed=[Math.floor(seconds/3600),Math.floor(seconds/60%60),seconds%60].map(value=>String(value).padStart(2,'0')).join(':');
  el('timed').textContent=elapsed+' · '+(finished?'Finished':session.paused_at?'Resume':'Pause');
  el('timed').title=finished?'Timer finished':session.paused_at?'Resume timer':'Pause timer';
 }
 function controls(){el('run').disabled=el('submit').disabled=el('source').disabled=busy||loading;el('timed').disabled=busy||loading||Boolean(session.stopped_at||session.accepted_at);el('stop').disabled=busy||loading;clock();}
 for(const name of ['ppc','java']){
  const button=document.getElementById('choose-'+name);
  button.addEventListener('click',()=>chooseEditor(name));
  button.addEventListener('keydown',e=>{
   if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
   e.preventDefault();
   chooseEditor(e.key==='Home'?'ppc':e.key==='End'?'java':editorMode==='ppc'?'java':'ppc',{focus:true});
  });
 }
 document.addEventListener('keydown',e=>{
  if(state.view!=='problem')return;
  if(e.altKey&&/^[1-4]$/.test(e.key)&&editorMode==='java')chooseEditor('ppc');
  if(editorMode==='java'&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){
   e.preventDefault();e.stopImmediatePropagation();if(id&&!loading)save();
  }
 },true);
 chooseEditor(editorMode,{initial:true});
 function feedback(r,custom=false){return r.verdict+(custom?' · Custom input execution (not graded)':r.total?' · '+r.passed+'/'+r.total+' tests passed':'')+(r.details?'\n'+r.details:'')+(r.failure?'\n\nFailed test '+r.failure.number+': '+r.failure.verdict+'\nInput:\n'+r.failure.input+'\nYour output:\n'+r.failure.stdout+(r.failure.expected!=null?'\nExpected output:\n'+r.failure.expected:'')+(r.failure.stderr?'\nErrors:\n'+r.failure.stderr:''):(r.results||[]).map((t,i)=>'\n\nTest '+(i+1)+': '+t.verdict+'\nOutput:\n'+t.stdout+(t.expected!=null?'\nExpected:\n'+t.expected:'')+(t.stderr?'\nErrors:\n'+t.stderr:'')).join(''));}
 window.addEventListener('ards-java-open',async event=>{const n=++request;clearTimeout(timer);if(id&&!loading)save();id=event.detail;loading=true;session={};el('source').value='';lines();el('result').textContent='Run samples or custom input, then submit against all available tests.';el('save').textContent='Loading…';controls();try{const s=await call(id,'load');if(n!==request)return;session=s;if(s.last_submission){const r=s.last_submission;el('result').textContent='Last submission: '+feedback(r);}let recovery=null;try{recovery=localStorage.getItem(key(id));}catch{}el('source').value=recovery??s.source??starter;if(!el('source').value)el('source').value=starter;loading=false;el('save').textContent=recovery!==null&&recovery!==s.source?'Browser recovery restored':'Saved locally';lines();controls();}catch(e){if(n===request){el('result').textContent=e.message;el('source').value=starter;loading=false;lines();controls();}}});
 el('source').addEventListener('input',()=>{lines();backup();el('save').textContent='Saving…';clearTimeout(timer);timer=setTimeout(save,600);});
 el('source').addEventListener('scroll',lines);
 new ResizeObserver(lines).observe(el('source'));
 el('source').addEventListener('keydown',e=>{
  if(e.isComposing)return;
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();e.stopPropagation();save();return;}
  if(e.key==='Escape'){escapeTab=true;return;}
  const t=e.target,a=t.selectionStart,b=t.selectionEnd;
  if(!e.ctrlKey&&!e.metaKey&&!e.altKey){
   const pairs={'{':'}','(':')','[':']',"'":"'",'"':'"'},next=t.value[a];
   if(a===b&&')] }\'"'.replace(' ','').includes(e.key)&&next===e.key){e.preventDefault();t.setSelectionRange(a+1,a+1);return;}
   if(pairs[e.key]){
    const quote=e.key==='"'||e.key==="'";
    if(a!==b||!quote||!/[\w\\]/.test(t.value[a-1]||'')&&!/[\w]/.test(next||'')){
     e.preventDefault();const selected=t.value.slice(a,b);window.ARDSEditor.insertAtCaret(t,e.key+selected+pairs[e.key],1);
     if(a!==b)t.setSelectionRange(a+1,b+1);return;
    }
   }
   if(e.key==='Backspace'&&a===b&&a>0&&pairs[t.value[a-1]]===next){e.preventDefault();t.setSelectionRange(a-1,a+1);window.ARDSEditor.insertAtCaret(t,'');return;}
  }
  if(e.key==='Tab' &&!escapeTab&&!e.ctrlKey&&!e.metaKey&&!e.altKey){
   e.preventDefault();
   if(a===b&&!e.shiftKey){window.ARDSEditor.insertAtCaret(t,'    ');}
   else{
    const from=t.value.lastIndexOf('\n',a-1)+1;
    const end=b>a&&t.value[b-1]==='\n'?b-1:b;
    const next=t.value.indexOf('\n',end),to=next<0?t.value.length:next;
    const original=t.value.slice(from,to);
    const changed=original.split('\n').map(line=>e.shiftKey?line.replace(/^( {1,4}|\t)/,''):'    '+line).join('\n');
    t.setSelectionRange(from,to);window.ARDSEditor.insertAtCaret(t,changed);
    if(a!==b)t.setSelectionRange(from,from+changed.length);
    else {const p=Math.max(from,a-(original.length-changed.length));t.setSelectionRange(p,p);}
   }
  }else if(e.key==='Enter'&&!e.ctrlKey&&!e.metaKey&&!e.altKey){
   e.preventDefault();const before=t.value.slice(t.value.lastIndexOf('\n',a-1)+1,a);
   const indent=(before.match(/^[ \t]*/)||[''])[0]+(before.trimEnd().endsWith('{')?'    ':'');
   const closing=before.trimEnd().endsWith('{')&&t.value[b]==='}';
   window.ARDSEditor.insertAtCaret(t,'\n'+indent+(closing?'\n'+indent.slice(0,-4):''),closing?indent.length-4+1:0);
  }
  escapeTab=false;
 });
 el('source').addEventListener('blur',()=>{escapeTab=false;});
 el('input-mode').onchange=()=>el('stdin-label').classList.toggle('hidden',el('input-mode').value!=='custom');
 async function timerAction(action){if(!id||busy||loading)return;const n=request,problem=id;el('timed').disabled=el('stop').disabled=true;try{const updated=await call(problem,action);if(n===request)session=updated;}catch(e){if(n===request)el('result').textContent=e.message;}if(n===request)controls();}
 el('timed').onclick=()=>timerAction(!session.started_at?'start':session.paused_at?'resume':'pause');
 el('stop').onclick=()=>timerAction('stop');
 async function run(action){if(busy||!id)return;busy=true;controls();clearTimeout(timer);backup();const problem=id,n=request,source=el('source').value,custom=action==='run'&&el('input-mode').value==='custom';el('result').textContent=action==='submit'?'Submitting… Checking all available tests.':'Compiling and running…';try{const result=await call(problem,action,{source,...(custom?{stdin:el('stdin').value}:{})});if(n!==request)return;session={...session,started_at:result.started_at,accepted_at:result.accepted_at,paused_at:result.paused_at,stopped_at:result.stopped_at,paused_seconds:result.paused_seconds};el('result').textContent=feedback(result,custom);el('save').textContent='Saved locally';}catch(e){if(n===request)el('result').textContent=e.message;}finally{busy=false;controls();}}
 el('run').onclick=()=>run('run');el('submit').onclick=()=>run('submit');
 el('download').onclick=()=>{const url=URL.createObjectURL(new Blob([el('source').value],{type:'text/plain'}));const a=document.createElement('a');a.href=url;a.download='Main.java';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 setInterval(clock,1000);
})();
