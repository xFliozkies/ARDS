'use strict';

/* ARDS Studio: intentionally zero external runtime dependencies.
   User PPC text never becomes executable HTML. */
const $=id=>document.getElementById(id);
const SECTIONS=['problem','procedure','correctness','complexity'];
const META={
  problem:{kicker:'P1 · FORMALIZATION',title:'Problem specification',description:'Define the input domain, preconditions, objective, and required output relation.',placeholder:'Let D denote the set of valid inputs...\n\nFor every x ∈ D, the result must satisfy...'},
  procedure:{kicker:'P2 · THE CONSTRUCTION',title:'Proposed algorithm',description:'Describe initialization, transformations, invariants, termination, and the returned answer.',placeholder:'Algorithm:\n1. Initialize ...\n2. For each ...\n3. Return ...'},
  correctness:{kicker:'C · THE ARGUMENT',title:'Correctness proof',description:'Establish well-definedness, partial correctness, termination, and optimality if relevant.',placeholder:'Claim. For every valid input ...\n\nProof. ...\n\nThe invariant initially holds because ...'},
  complexity:{kicker:'K · RESOURCE ANALYSIS',title:'Time & space complexity',description:'Declare the input measure and derive time and auxiliary-space bounds.',placeholder:'Let N be the input size.\n\nTime: O(...) because ...\nSpace: O(...) because ...'}
};
const SECTION_PROMPTS={
  problem:['What are the input and output types?','Which inputs are valid, including boundaries?','What precise relation Q(x,y) makes an output correct?','What happens if no feasible solution exists?'],
  procedure:['What is initialized before the first step?','What changes during one iteration or recursive call?','What exactly causes termination?','What is returned in each valid case?'],
  correctness:['What is the invariant or central lemma?','Why does it hold initially and remain true?','Why does termination imply the required answer?','How do you prove termination and, if needed, global optimality?'],
  complexity:['What does each input-size parameter represent?','What operations dominate running time?','What extra arrays, maps or recursion frames are needed?','Which cost model and implementation limits apply?']
};
const state={token:'',problems:[],page:1,perPage:12,total:0,pages:1,problemRequestId:0,current:null,section:'problem',draft:null,loadedDraft:null,view:'library',saveTimer:null,busy:false,lastSelected:localStorage.getItem('ards-last-selected')||null,
  mode:'write',saveKind:'idle',saveText:'Not saved yet',savedAt:0,saving:false,resave:false,savePromise:null,mirrorTimer:null,reloading:false,search:''};
let toastTimer=null;
let comparisonProblems=[];
let similarActive=-1;

function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function notify(message,isError=false){const el=$('toast');el.textContent=message;el.classList.toggle('error',isError);el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),3600);}
async function api(url,options={}){
  let response;
  try{
    response=await fetch(url,{cache:'no-store',credentials:'same-origin',
      ...options,headers:{...(options.body?{'Content-Type':'application/json','X-ARDS-Session':state.token}:{}),...(options.headers||{})}});
  }catch{throw Object.assign(Error('Cannot reach the local ARDS server'),{network:true});}
  let value;
  try{value=await response.json();}catch{throw Error('Unexpected server response');}
  if(!response.ok){const err=Error(value.error||'Request failed');err.status=response.status;throw err;}
  return value;
}
/* A write rejected for a missing/old session token or bad origin means the local
   server was restarted. Reveal also returns 403 for eligibility, so match the message. */
function handleWriteError(err){
  if(err&&err.status===403&&/session token|request origin/i.test(err.message||'')){
    $('session-banner').classList.remove('hidden');
    writeMirror();
    return true;
  }
  return false;
}
function markActive(id){document.querySelectorAll('.nav-link').forEach(x=>x.classList.toggle('active',x.id===id));}
function switchView(name){
  state.view=name;
  document.querySelectorAll('.page').forEach(x=>x.classList.add('hidden'));
  $('view-'+name).classList.remove('hidden');
  markActive(name==='problem'?'nav-drafts':name==='overview'?'nav-overview':name==='guide'?'nav-method':'nav-library');
  $('sidebar').classList.remove('visible');
  $('mobile-menu').setAttribute('aria-expanded','false');
  $('mobile-menu').setAttribute('aria-label','Open navigation');
  window.scrollTo({top:0,behavior:'instant'});
}
function refreshStats(stats){
  $('stat-problems').textContent=stats.published;
  $('stat-attempts').textContent=stats.attempts;
  $('stat-assessments').textContent=stats.assessments;
  $('stat-drafts').textContent=stats.drafts;
  $('sidebar-count').textContent=stats.published;
  $('overview-details').innerHTML=[
    ['Authored problems (including private review queue)',stats.authored],
    ['Awaiting verification',stats.under_review],
    ['Released for assessed practice',stats.published],
    ['Saved PPC drafts',stats.drafts],['Recorded reasoning attempts',stats.attempts],
    ['Independent graded attempts',stats.independent_graded],
    ['Reference-opened challenges excluded',stats.revealed],
    ['Archived assessment records',stats.assessments],
    ['Privacy','Local-only'],['Difficulty policy','Classic RACG']
  ].map(([name,value])=>'<div class="overview-row"><span>'+esc(name)+'</span><strong>'+esc(value)+'</strong></div>').join('');
}
function statusFor(problem){
  if(problem.review_only||problem.status==='under_review')return {label:'Under review',cls:'review'};
  if(problem.reference_revealed)return {label:'Reference opened',cls:'done'};
  if(problem.passed)return {label:'Passed review',cls:'done'};
  if(problem.status==='presented')return {label:'Ready to solve',cls:'open'};
  if(problem.status==='attempted')return {label:'Attempted',cls:'open'};
  if(problem.status==='evaluated')return {label:'Evaluated',cls:'done'};
  return {label:problem.status,cls:''};
}
function renderProblemPagination(){
  const total=state.total;
  const page=state.page;
  const pages=state.pages;
  const first=total?(page-1)*state.perPage+1:0;
  const last=Math.min(total,page*state.perPage);
  $('pagination-summary').textContent=total?'Showing '+first+'–'+last+' of '+total+' problems':'No matching problems';
  $('page-previous').disabled=page<=1;
  $('page-next').disabled=page>=pages;
  const root=$('page-numbers');
  root.replaceChildren();
  const candidates=new Set([1,pages]);
  if(pages<=7){for(let n=1;n<=pages;n++)candidates.add(n);}
  else{for(let n=page-1;n<=page+1;n++)if(n>=1&&n<=pages)candidates.add(n);}
  const numbers=[...candidates].sort((a,b)=>a-b);
  let previous=0;
  for(const n of numbers){
    if(previous && n-previous>1){
      const dots=document.createElement('span');
      dots.className='pagination-ellipsis';
      dots.textContent='…';
      dots.setAttribute('aria-hidden','true');
      root.append(dots);
    }
    const button=document.createElement('button');
    button.type='button';
    button.className='pagination-number'+(n===page?' active':'');
    button.textContent=String(n);
    button.setAttribute('aria-label','Go to page '+n);
    if(n===page)button.setAttribute('aria-current','page');
    button.disabled=n===page;
    button.addEventListener('click',()=>goToProblemPage(n));
    root.append(button);
    previous=n;
  }
  $('problem-pagination').classList.toggle('is-empty',!total);
}
function goToProblemPage(page){
  if(page<1||page>state.pages||page===state.page)return;
  state.page=page;
  loadProblems('',{scrollToList:true}).catch(err=>notify('Could not change page: '+err.message,true));
}

function renderProblems(){
  const list=$('problem-list');
  const problems=state.problems;
  renderProblemPagination();
  if(!problems.length){list.innerHTML='<div class="empty-state">No matching problems. Adjust the filters or clear the similar-to selection.</div>';return;}
  list.replaceChildren();
  for(const p of problems){
    const status=statusFor(p);
    const row=document.createElement('div');row.className='problem-row';
    const b=document.createElement('button');
    b.type='button';b.className='problem-item';
    b.innerHTML='<span class="problem-name"><strong>'+esc(p.title||'Untitled problem')+'</strong><small>'+esc(p.id)+'</small></span>'+
      '<span class="problem-topic">'+esc(p.topic_label||'Foundational reasoning')+'</span>'+
      '<span><span class="level-chip">Level '+esc(p.difficulty??'—')+'</span></span>'+
      '<span class="status-chip '+esc(status.cls)+'">'+esc(status.label)+'</span>'+
      '<svg class="icon row-arrow"><use href="#i-chevron"></use></svg>';
    b.addEventListener('click',()=>openProblem(p.id));
    const actions=document.createElement('div');actions.className='row-actions';
    const preview=document.createElement('button');preview.type='button';preview.title='Preview '+p.title;
    preview.setAttribute('aria-label','Preview '+p.title);
    preview.innerHTML='<svg class="icon"><use href="#i-book"></use></svg>';
    preview.addEventListener('click',()=>previewProblem(p.id));
    const similar=document.createElement('button');similar.type='button';similar.title='Find problems similar to '+p.title;
    similar.setAttribute('aria-label','Similar to '+p.title);
    similar.innerHTML='<svg class="icon"><use href="#i-search"></use></svg>';
    similar.addEventListener('click',()=>showSimilar(p.id));
    actions.append(preview,similar);row.append(b,actions);list.append(row);
  }
}
async function loadProblems(search='',{resetPage=false,scrollToList=false}={}){
  if(resetPage)state.page=1;
  const requestId=++state.problemRequestId;
  const query=new URLSearchParams();
  query.set('page',state.page);
  query.set('per_page',state.perPage);
  const term=search||state.search;
  if(term)query.set('q',term);
  for(const [control,key] of [
    ['filter-level','difficulty'],['filter-status','status'],
    ['filter-topic','topic'],['filter-family','family'],
    ['filter-presentation','presentation'],['filter-progress','progress'],
    ['filter-similar','similar_to'],['filter-sort','sort']
  ]){
    const value=$(control).value;
    if(value)query.set(key,value);
  }
  const data=await api('/api/problems?'+query);
  if(requestId!==state.problemRequestId)return;
  state.problems=data.problems;
  state.page=data.page;
  state.pages=data.pages;
  state.total=data.total;
  renderProblems();
  if(scrollToList && state.view==='library')document.querySelector('.problem-table').scrollIntoView({block:'start',behavior:'instant'});
}
async function loadFacets(){
  const data=await api('/api/facets');
  const fill=(element,records,key,label)=>{
    const original=element.value;
    while(element.options.length>1)element.remove(1);
    for(const item of records){
      const opt=document.createElement('option');
      opt.value=key(item);opt.textContent=label(item);element.append(opt);
    }
    element.value=original;
  };
  fill($('filter-topic'),data.topics,x=>x.id,x=>x.id+' · '+x.label);
  fill($('filter-family'),data.families,x=>x,x=>x.replace(/^classic_topic_/,'Family · Topic '));
  comparisonProblems=data.comparison;
  syncSimilarSelection();
}
async function previewProblem(id){
  try{
    await window.ARDSUI.preview(id,async target=>api('/api/problems/'+encodeURIComponent(target)),openProblem,showSimilar);
  }catch(err){notify('Preview unavailable: '+err.message,true);}
}
function syncSimilarSelection(){
  const selected=comparisonProblems.find(p=>p.id===$('filter-similar').value);
  $('similar-query').value=selected?selected.id+' · '+selected.title:'';
  $('similar-clear').hidden=!selected;
}
function closeSimilarOptions(){
  $('similar-options').hidden=true;
  $('similar-query').setAttribute('aria-expanded','false');
  $('similar-query').removeAttribute('aria-activedescendant');
  similarActive=-1;
}
function selectSimilar(id){
  $('filter-similar').value=id;
  syncSimilarSelection();
  closeSimilarOptions();
  loadProblems('',{resetPage:true}).catch(err=>notify(err.message,true));
}
function renderSimilarOptions(){
  const query=$('similar-query').value.trim().toLowerCase();
  const selected=comparisonProblems.find(p=>p.id===$('filter-similar').value);
  const fullLabel=selected?(selected.id+' · '+selected.title).toLowerCase():'';
  const matches=comparisonProblems.filter(p=>query===fullLabel || (p.id+' '+p.title).toLowerCase().includes(query));
  const root=$('similar-options');
  root.replaceChildren();
  similarActive=-1;
  $('similar-query').removeAttribute('aria-activedescendant');
  for(const [index,p] of matches.entries()){
    const option=document.createElement('button');
    option.type='button';option.role='option';option.id='similar-option-'+index;
    option.tabIndex=-1;
    option.setAttribute('aria-selected',String(p.id===$('filter-similar').value));
    option.textContent=p.id+' · '+p.title;
    option.addEventListener('mousedown',e=>e.preventDefault());
    option.addEventListener('click',()=>selectSimilar(p.id));
    root.append(option);
  }
  if(!matches.length){
    const empty=document.createElement('div');empty.className='similar-empty';
    empty.setAttribute('role','status');empty.textContent='No matching challenges.';root.append(empty);
  }
  root.hidden=false;
  $('similar-query').setAttribute('aria-expanded','true');
}
function bindSimilarPicker(){
  const input=$('similar-query');
  input.addEventListener('focus',renderSimilarOptions);
  input.addEventListener('input',()=>{
    $('similar-clear').hidden=!input.value&&!$('filter-similar').value;
    if(!input.value)selectSimilar('');
    renderSimilarOptions();
  });
  input.addEventListener('blur',()=>{syncSimilarSelection();closeSimilarOptions();});
  input.addEventListener('keydown',e=>{
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();syncSimilarSelection();closeSimilarOptions();return;}
    if(!['ArrowDown','ArrowUp','Enter'].includes(e.key))return;
    if(e.key==='Enter'){
      e.preventDefault();
      const options=$('similar-options').querySelectorAll('[role="option"]');
      if(!$('similar-options').hidden && options.length)options[similarActive<0?0:similarActive].click();
      return;
    }
    e.preventDefault();
    if($('similar-options').hidden)renderSimilarOptions();
    const options=[...$('similar-options').querySelectorAll('[role="option"]')];
    if(!options.length)return;
    similarActive=(similarActive+(e.key==='ArrowDown'?1:similarActive<0?0:-1)+options.length)%options.length;
    options.forEach((option,index)=>option.classList.toggle('active',index===similarActive));
    input.setAttribute('aria-activedescendant',options[similarActive].id);
    options[similarActive].scrollIntoView({block:'nearest'});
  });
  $('similar-clear').addEventListener('mousedown',e=>e.preventDefault());
  $('similar-clear').addEventListener('click',()=>{selectSimilar('');input.focus();});
}
function showSimilar(id){
  $('filter-similar').value=id;
  syncSimilarSelection();
  closeSimilarOptions();
  state.page=1;
  goLibrary();
}
async function loadOverview(){
  try{refreshStats(await api('/api/overview'));}catch(err){notify('Could not load workspace overview: '+err.message,true);}
}
/* ---- Local mirror: the latest unsaved text per problem, kept in this browser only.
   It holds the student's own words and is cleared once the server has them. ---- */
const MIRROR_PREFIX='ards-mirror:';
const mirrorKey=id=>MIRROR_PREFIX+id;
function clearMirror(id){try{localStorage.removeItem(mirrorKey(id));}catch{}}
function writeMirror(){
  if(!state.current||!state.draft)return;
  try{
    if(JSON.stringify(state.draft)===state.loadedDraft)clearMirror(state.current.id);
    else localStorage.setItem(mirrorKey(state.current.id),JSON.stringify({draft:state.draft,at:Date.now()}));
  }catch{}
}
function offerLocalMirror(id,serverDraft){
  let saved=null;
  try{saved=JSON.parse(localStorage.getItem(mirrorKey(id))||'null');}catch{}
  if(!saved||!saved.draft)return;
  const local={};
  SECTIONS.forEach(s=>{local[s]=typeof saved.draft[s]==='string'?saved.draft[s]:'';});
  if(JSON.stringify(local)===state.loadedDraft){clearMirror(id);return;}
  const serverTime=Date.parse(serverDraft&&serverDraft.updated_at);
  if(Number.isFinite(serverTime)&&saved.at&&saved.at<=serverTime){clearMirror(id);return;}
  const body=document.createElement('p');
  body.textContent='This browser holds text for this problem from '+(saved.at?new Date(saved.at).toLocaleString():'an earlier session')+
    ' that never reached the saved draft. Which version do you want to keep?';
  window.ARDSUI.openModal('Recover unsaved text?',id,body,[
    {label:'Use saved draft',action:()=>clearMirror(id)},
    {label:'Use browser copy',primary:true,action:()=>{
      state.draft=local;
      showSection(state.section,{skipPreserve:true});
      scheduleSave();
    }}
  ]);
}

/* ---- Save state ---- */
function relativeTime(ms){
  const minutes=Math.floor((Date.now()-ms)/60000);
  if(minutes<1)return 'just now';
  if(minutes<60)return minutes+' min ago';
  return Math.floor(minutes/60)+' h ago';
}
function renderSaveStatus(){
  const labels={unsaved:'Unsaved changes',saving:'Saving…',failed:'Save failed – retry'};
  const text=state.saveKind==='saved'?'Saved '+relativeTime(state.savedAt):(labels[state.saveKind]||state.saveText||'Not saved yet');
  $('save-status').textContent=text;
  $('save-status').dataset.state=state.saveKind;
  return text;
}
function setSaveState(kind,text){
  const changed=kind!==state.saveKind;
  state.saveKind=kind;
  if(text!==undefined)state.saveText=text;
  if(kind==='saved')state.savedAt=Date.now();
  const label=renderSaveStatus();
  // Announce only meaningful transitions, never the passing of time.
  if(changed&&(kind==='saved'||kind==='failed'))$('save-announce').textContent=label;
}
setInterval(()=>{if(state.saveKind==='saved')renderSaveStatus();},30000);

/* ---- Section tabs, preview, symbols, outline ---- */
const TAB_NAMES={problem:'01 Problem',procedure:'02 Procedure',correctness:'03 Proof',complexity:'04 Complexity'};
const SECTION_LABELS={problem:'P1 · Problem specification',procedure:'P2 · Proposed algorithm',correctness:'C · Correctness proof',complexity:'K · Complexity analysis'};
function updateCharCount(){$('character-count').textContent=$('ppc-input').value.length+' characters';}
function updateTabStates(){
  document.querySelectorAll('.editor-tab').forEach(btn=>{
    const section=btn.dataset.section;
    const text=state.draft?.[section]||'';
    const filled=text.trim().length>0;
    const mark=btn.querySelector('.tab-state');
    if(mark){mark.textContent=filled?'✓':'○';mark.dataset.filled=filled?'1':'0';}
    btn.setAttribute('aria-label',TAB_NAMES[section]+', '+(filled?text.length+' characters':'empty'));
  });
}
function onTabKeydown(e){
  const tabs=[...document.querySelectorAll('.editor-tab')];
  const i=tabs.indexOf(e.currentTarget);
  let n;
  if(e.key==='ArrowRight')n=(i+1)%tabs.length;
  else if(e.key==='ArrowLeft')n=(i-1+tabs.length)%tabs.length;
  else if(e.key==='Home')n=0;
  else if(e.key==='End')n=tabs.length-1;
  else return;
  e.preventDefault();
  showSection(tabs[n].dataset.section);
  tabs[n].focus();
}
function renderPreview(){
  preserveText();
  const box=$('ppc-preview');
  box.replaceChildren();
  const text=$('ppc-input').value;
  if(!text.trim()){
    const p=document.createElement('p');p.className='preview-empty';
    p.textContent='Nothing to preview yet. Switch to Write and add some text.';
    box.append(p);return;
  }
  try{box.append(window.ARDSStatement.rich(text));}
  catch{const pre=document.createElement('pre');pre.className='preview-fallback';pre.textContent=text;box.append(pre);}
}
function setMode(mode){
  state.mode=mode;
  const preview=mode==='preview';
  $('mode-write').classList.toggle('active',!preview);
  $('mode-write').setAttribute('aria-pressed',String(!preview));
  $('mode-preview').classList.toggle('active',preview);
  $('mode-preview').setAttribute('aria-pressed',String(preview));
  $('ppc-input').classList.toggle('hidden',preview);
  $('ppc-preview').classList.toggle('hidden',!preview);
  $('insert-skeleton').disabled=preview;
  $('toggle-symbols').disabled=preview;
  if(preview){closeSymbols();renderPreview();}
}
function closeSymbols(){
  $('symbol-palette').classList.add('hidden');
  $('toggle-symbols').setAttribute('aria-expanded','false');
}
function toggleSymbols(){
  const open=$('symbol-palette').classList.toggle('hidden')===false;
  $('toggle-symbols').setAttribute('aria-expanded',String(open));
  if(open&&!$('symbol-palette').childElementCount){
    if(!window.ARDSEditor){notify('Editor helpers did not load. Hard-refresh the page (Ctrl+Shift+R) or restart the local server.',true);$('symbol-palette').classList.add('hidden');$('toggle-symbols').setAttribute('aria-expanded','false');return;}
    window.ARDSEditor.buildPalette($('symbol-palette'),$('ppc-input'));
  }
}
function onPaletteKeydown(e){
  if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeSymbols();$('toggle-symbols').focus();return;}
  if(e.key!=='ArrowRight'&&e.key!=='ArrowLeft')return;
  const buttons=[...$('symbol-palette').querySelectorAll('button')];
  const i=buttons.indexOf(document.activeElement);
  if(i<0)return;
  e.preventDefault();
  buttons[(i+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length].focus();
}
function insertOutline(){
  const ta=$('ppc-input');
  const text=window.ARDSEditor?.SKELETONS[state.section];
  if(!text)return;
  const insert=()=>{
    ta.focus();
    if(!ta.value.trim())ta.setSelectionRange(0,ta.value.length);
    window.ARDSEditor.insertAtCaret(ta,text);
  };
  if(!ta.value.trim()){insert();return;}
  const body=document.createElement('p');
  body.textContent='This section already has text. The outline will be inserted at your cursor; nothing is replaced or deleted.';
  window.ARDSUI.openModal('Insert outline here?',META[state.section].kicker,body,[
    {label:'Cancel',action:()=>{}},
    {label:'Insert at cursor',primary:true,action:insert}
  ]);
  $('workspace-dialog-actions').querySelector('button')?.focus();
}
function exportDraft(){
  if(!state.current||!state.draft)return;
  preserveText();
  const parts=['# '+state.current.id+' — '+(state.current.title||'Untitled problem'),'','_Draft exported from ARDS Studio. Not graded._',''];
  for(const s of SECTIONS)parts.push('## '+SECTION_LABELS[s],'',state.draft[s].trimEnd()||'_(empty)_','');
  const blob=new Blob([parts.join('\n')],{type:'text/markdown;charset=utf-8'});
  const link=document.createElement('a');
  link.href=URL.createObjectURL(blob);
  link.download=String(state.current.id).replace(/[^A-Za-z0-9._-]/g,'_')+'-ppc-draft.md';
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(link.href),1000);
}
function preserveText(){if(state.draft)state.draft[state.section]=$('ppc-input').value;}
function allFilled(){return Boolean(state.draft&&SECTIONS.every(s=>state.draft[s].trim()));}
function showSection(section,{skipPreserve=false}={}){
  if(!skipPreserve)preserveText();
  state.section=section;
  const meta=META[section];
  $('section-kicker').textContent=meta.kicker;
  $('section-title').textContent=meta.title;
  $('section-description').textContent=meta.description;
  $('ppc-input').placeholder=meta.placeholder;
  $('ppc-input').value=state.draft?.[section]||'';
  $('self-check-questions').replaceChildren(...SECTION_PROMPTS[section].map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));
  updateCharCount();
  document.querySelectorAll('.editor-tab').forEach(btn=>{
    const active=btn.dataset.section===section;
    btn.classList.toggle('active',active);
    btn.setAttribute('aria-selected',active?'true':'false');
    btn.tabIndex=active?0:-1;
  });
  $('ppc-panel').setAttribute('aria-labelledby','tab-'+section);
  updateTabStates();
  if(state.mode==='preview')renderPreview();
  $('next-section').textContent='';
  const next=SECTIONS[(SECTIONS.indexOf(section)+1)%SECTIONS.length];
  $('next-section').append('Next: '+(next==='correctness'?'Proof':META[next].title.split(' ')[0])+' ');
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('class','icon');const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-arrow');svg.appendChild(use);$('next-section').appendChild(svg);
  $('submit-ppc').disabled=Boolean(state.current?.review_only)||!allFilled();
}
async function openProblem(id){
  if(state.current&&state.current.id!==id&&state.draft)await saveDraft(true);
  try{
    const [problem,draft]=await Promise.all([api('/api/problems/'+encodeURIComponent(id)),api('/api/drafts/'+encodeURIComponent(id))]);
    state.current=problem;state.draft={};SECTIONS.forEach(s=>state.draft[s]=draft[s]||'');
    state.loadedDraft=JSON.stringify(state.draft);
    state.lastSelected=id;localStorage.setItem('ards-last-selected',id);
    $('problem-id').textContent=problem.id;
    $('problem-level').textContent='LEVEL '+(problem.difficulty??'—');
    $('problem-topic').textContent=String(problem.topic_label||'GENERAL').toUpperCase();
    $('problem-title').textContent=problem.title;
    window.ARDSUI.renderStatement($('problem-statement'),problem);
    window.ARDSUI.setupWorkspace(problem);
    $('reference-exclusion')?.classList?.add('hidden');
    $('problem-progress').textContent=statusFor(problem).label.toUpperCase();
    $('problem-review-note').classList.toggle('hidden',!problem.review_only);
    $('submit-ppc').disabled=Boolean(problem.review_only);
    $('submit-ppc').title=problem.review_only?'Under review: submissions are disabled until verified release':'';
    $('submit-ppc').classList.toggle('hidden',Boolean(problem.review_only));
    $('independent-attest').closest('label').classList.toggle('hidden',Boolean(problem.review_only));
    $('reveal-reference').classList.toggle('hidden',!problem.reference_available);
    $('reveal-reference').textContent=problem.reference_revealed?'View PPC':'Reveal PPC';
    $('independent-attest').checked=false;
    $('independent-attest').disabled=Boolean(problem.review_only||problem.reference_revealed||problem.attempt_count>0);
    $('independent-attest').closest('label').classList.toggle('disabled',$('independent-attest').disabled);
    state.savedAt=0;
    setSaveState('idle',draft.updated_at?'Last draft: '+new Date(draft.updated_at).toLocaleDateString():problem.review_only?'Review-only · private drafts can be saved':'Not saved yet');
    showSection('problem',{skipPreserve:true});
    setMode('write');
    switchView('problem');
    document.querySelector('.statement-panel').scrollTop=0;
    document.querySelector('.editor-panel').scrollTop=0;
    history.replaceState(null,'','#/problem/'+encodeURIComponent(id));
    offerLocalMirror(id,draft);
  }catch(err){notify('Could not open problem: '+err.message,true);}
}
function revealReference(){
  if(!state.current || !state.current.reference_available)return;
  const id=state.current.id;
  if(!state.current.reference_revealed){
    window.ARDSUI.confirmReveal(id,()=>loadReference(id));
    return;
  }
  loadReference(id);
}
async function loadReference(id){
  if(!state.current || state.current.id!==id || !state.current.reference_available)return;
  const button=$('reveal-reference');
  if(button.disabled)return;
  button.disabled=true;
  try{
    const result=await api('/api/reveal/'+encodeURIComponent(id),
      {method:'POST',body:JSON.stringify({confirm:true})});
    if(!state.current || state.current.id!==id)return;
    state.current.reference_revealed=true;
    $('problem-progress').textContent='REFERENCE OPENED';
    button.textContent='View PPC';
    $('independent-attest').disabled=true;
    window.ARDSUI.showReference(result);
    await loadProblems();
    notify(result.message);
  }catch(err){notify('Could not reveal PPC: '+err.message,true);}
  finally{button.disabled=false;}
}

async function saveDraft(silent=false){
  if(!state.current||!state.draft)return;
  preserveText();
  if(JSON.stringify(state.draft)===state.loadedDraft){
    if(!silent)notify('Draft is already saved');
    // Edited back to what the server already has: the label must not stay on "Unsaved".
    if(state.saveKind==='unsaved'){const prev=state.savedAt;setSaveState(prev?'saved':'idle');state.savedAt=prev;renderSaveStatus();}
    writeMirror();
    return;
  }
  // One save at a time. A save requested meanwhile is repeated afterwards with the newest text,
  // and callers (such as opening another problem) await the whole chain.
  if(state.saving){state.resave=true;return state.savePromise;}
  state.saving=true;
  state.savePromise=(async()=>{
    try{
      do{
        state.resave=false;
        const id=state.current.id;
        const serialized=JSON.stringify(state.draft);
        if(serialized===state.loadedDraft)break;
        setSaveState('saving');
        try{
          await api('/api/drafts/'+encodeURIComponent(id),{method:'POST',body:serialized});
        }catch(err){
          setSaveState('failed');
          writeMirror();
          if(!handleWriteError(err))notify('Draft save failed: '+err.message,true);
          return;
        }
        state.loadedDraft=serialized;
        setSaveState(JSON.stringify(state.draft)===serialized?'saved':'unsaved');
        writeMirror();
        if(!silent)notify('Your PPC draft has been saved.');
        loadOverview();
      }while(state.resave);
    }finally{state.saving=false;}
  })();
  return state.savePromise;
}
function scheduleSave(){
  preserveText();
  setSaveState('unsaved');
  $('submit-ppc').disabled=Boolean(state.current?.review_only)||!allFilled();
  updateCharCount();
  updateTabStates();
  clearTimeout(state.saveTimer);
  state.saveTimer=setTimeout(()=>saveDraft(true),1800);
  clearTimeout(state.mirrorTimer);
  state.mirrorTimer=setTimeout(writeMirror,300);
}
async function submitPPC(){
  if(state.current?.review_only)return notify('This problem is under review. Save a private draft; formal assessment opens after verified release.',true);
  preserveText();
  if(!allFilled())return notify('Complete every PPC section before submitting.',true);
  const content=document.createElement('div');
  content.className='submit-confirmation';
  const list=document.createElement('ul');
  list.className='submit-sections';
  for(const s of SECTIONS){
    const li=document.createElement('li');
    const length=state.draft[s].length;
    li.textContent=SECTION_LABELS[s]+' — '+(state.draft[s].trim()?'filled ('+length+' characters)':'empty');
    list.append(li);
  }
  const para=text=>{const p=document.createElement('p');p.textContent=text;return p;};
  content.append(list,
    para('Independent, without hints: '+($('independent-attest').checked?'ticked.':'not ticked.')),
    para(state.current?.attempt_count>0
      ?'This will be recorded as a later submission (a revision) in the permanent attempt history.'
      :'This will be recorded as your original attempt in the permanent attempt history.'),
    para('Submitting saves your PPC for review. It is not auto-graded, and no correctness result is claimed.'));
  window.ARDSUI.openModal('Submit this PPC?',state.current.id+' · '+(state.current.title||''),content,[
    {label:'Cancel',action:()=>{}},
    {label:'Submit PPC',primary:true,action:performSubmit}
  ]);
  // Safe default: Enter must not submit; focus starts on Cancel.
  $('workspace-dialog-actions').querySelector('button')?.focus();
}
async function performSubmit(){
  if(state.busy||!state.current||!state.draft)return;
  state.busy=true;$('submit-ppc').disabled=true;
  try{
    const response=await api('/api/submissions/'+encodeURIComponent(state.current.id),
      {method:'POST',body:JSON.stringify({ppc:state.draft,independent:$('independent-attest').checked})});
    notify(response.independent?'Independent first attempt recorded; it still requires correctness assessment.':'PPC recorded for review; no automatic pass is claimed.');
    $('independent-attest').disabled=true;
    state.loadedDraft=JSON.stringify(state.draft);
    setSaveState('idle','Submitted · '+response.stage);
    await loadOverview();
  }catch(err){if(!handleWriteError(err))notify('Could not submit PPC: '+err.message,true);}
  finally{state.busy=false;$('submit-ppc').disabled=Boolean(state.current?.review_only)||!allFilled();}
}
function goLibrary(){
  if(state.view==='problem'){clearTimeout(state.saveTimer);saveDraft(true);}
  switchView('library');history.replaceState(null,'','#/');
  loadProblems().catch(err=>notify(err.message,true));
}
let commandOpener=null;
async function showCommand(){
  if($('search-overlay').classList.contains('hidden'))commandOpener=document.activeElement;
  $('search-overlay').classList.remove('hidden');
  $('command-query').value='';
  $('command-query').focus();
  await renderCommandResults('');
}
function hideCommand(){
  if($('search-overlay').classList.contains('hidden'))return;
  $('search-overlay').classList.add('hidden');
  const target=commandOpener;commandOpener=null;
  if(target&&document.contains(target)&&typeof target.focus==='function')target.focus();
}
async function renderCommandResults(query){
  try{
    const data=await api('/api/problems?'+new URLSearchParams({q:query}));
    const root=$('command-results');root.innerHTML='';
    if(!data.problems.length){root.innerHTML='<div class="empty-state">No matches.</div>';return;}
    for(const p of data.problems){
      const b=document.createElement('button');b.type='button';b.className='command-result';
      b.innerHTML='<svg class="icon"><use href="#i-file"></use></svg><span>'+esc(p.title)+'</span><small>'+esc(p.id)+'</small>';
      b.addEventListener('click',()=>{hideCommand();openProblem(p.id);});
      root.appendChild(b);
    }
  }catch(err){notify(err.message,true);}
}
function bind(){
  bindSimilarPicker();
  window.ARDSUI.bindWorkspace();
  document.addEventListener('keydown',e=>{
    if(e.altKey&&/^[1-4]$/.test(e.key)&&state.view==='problem'){
      e.preventDefault();showSection(SECTIONS[Number(e.key)-1]);$('ppc-input').focus();
    }
    if(e.key==='?'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!e.target.closest('input,textarea,select,[contenteditable]')){
      const content=document.createElement('p');
      content.textContent='Ctrl+K or /: search. Ctrl+S: save draft. Alt+1–4: switch PPC section. Escape then Tab: leave the editor. Arrow keys: resize the focused divider. ? : show shortcuts.';
      window.ARDSUI.openModal('Keyboard shortcuts','',content);
    }
  });
  $('nav-library').addEventListener('click',goLibrary);
  $('nav-drafts').addEventListener('click',()=>state.lastSelected?openProblem(state.lastSelected):notify('Open a problem to start your PPC draft.'));
  $('nav-overview').addEventListener('click',()=>{switchView('overview');history.replaceState(null,'','#/overview');loadOverview();});
  $('nav-method').addEventListener('click',()=>{if(state.view==='problem'){clearTimeout(state.saveTimer);saveDraft(true);}switchView('guide');history.replaceState(null,'','#/method/'+(window.PPCGuide?'start':'start'));if(window.PPCGuide)window.PPCGuide.select('start');});
  $('learn-ppc').addEventListener('click',()=>$('nav-method').click());
  $('go-back').addEventListener('click',goLibrary);
  $('editor-open-guide').addEventListener('click',()=>window.ARDSUI.explain(state.section).catch(err=>notify(err.message,true)));
  $('overview-back').addEventListener('click',goLibrary);
  $('filter-level').addEventListener('change',()=>loadProblems('',{resetPage:true}).catch(err=>notify(err.message,true)));
  $('filter-status').addEventListener('change',()=>loadProblems('',{resetPage:true}).catch(err=>notify(err.message,true)));
  for(const id of ['filter-topic','filter-family','filter-presentation','filter-progress','filter-sort']){
    $(id).addEventListener('change',()=>loadProblems('',{resetPage:true}).catch(err=>notify(err.message,true)));
  }
  $('page-previous').addEventListener('click',()=>goToProblemPage(state.page-1));
  $('page-next').addEventListener('click',()=>goToProblemPage(state.page+1));
  $('page-size').addEventListener('change',()=>{
    state.perPage=Number($('page-size').value);
    loadProblems('',{resetPage:true,scrollToList:true}).catch(err=>notify('Could not change page size: '+err.message,true));
  });
  $('refresh-library').addEventListener('click',async()=>{
    try{await loadFacets();await Promise.all([loadProblems(),loadOverview()]);notify('Problem archive refreshed.');}
    catch(err){notify('Refresh failed: '+err.message,true);}
  });
  document.querySelectorAll('.editor-tab').forEach(btn=>btn.addEventListener('click',()=>showSection(btn.dataset.section)));
  $('ppc-input').addEventListener('input',scheduleSave);
  // editor.js is an enhancement (Tab, list continuation, symbols). If it failed
  // to load, the textarea still works; do not take the whole app down.
  if(window.ARDSEditor)window.ARDSEditor.bindTextarea($('ppc-input'));
  else console.warn('ARDS editor helpers (editor.js) did not load; using a plain textarea.');
  $('mode-write').addEventListener('click',()=>{setMode('write');$('ppc-input').focus();});
  $('mode-preview').addEventListener('click',()=>setMode('preview'));
  $('toggle-symbols').addEventListener('click',toggleSymbols);
  $('symbol-palette').addEventListener('keydown',onPaletteKeydown);
  $('insert-skeleton').addEventListener('click',insertOutline);
  document.querySelectorAll('.editor-tab').forEach(btn=>btn.addEventListener('keydown',onTabKeydown));
  $('export-draft').addEventListener('click',exportDraft);
  $('toggle-focus').addEventListener('click',()=>{
    const on=$('view-problem').classList.toggle('focus-mode');
    $('toggle-focus').setAttribute('aria-pressed',String(on));
    $('toggle-focus').textContent=on?'Show statement':'Focus';
  });
  $('session-reload').addEventListener('click',()=>{state.reloading=true;location.reload();});
  let librarySearchTimer=null;
  $('library-search').addEventListener('input',e=>{
    clearTimeout(librarySearchTimer);
    librarySearchTimer=setTimeout(()=>{
      state.search=e.target.value.trim();
      loadProblems('',{resetPage:true}).catch(err=>notify(err.message,true));
    },250);
  });
  window.addEventListener('beforeunload',e=>{
    preserveText();
    writeMirror();
    if(state.reloading||!state.current||!state.draft)return;
    if(JSON.stringify(state.draft)!==state.loadedDraft){e.preventDefault();e.returnValue='';}
  });
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden'){preserveText();writeMirror();}});
  $('next-section').addEventListener('click',()=>showSection(SECTIONS[(SECTIONS.indexOf(state.section)+1)%SECTIONS.length]));
  $('save-draft').addEventListener('click',()=>saveDraft(false));
  $('submit-ppc').addEventListener('click',submitPPC);
  $('reveal-reference').addEventListener('click',revealReference);
  $('mobile-menu').addEventListener('click',()=>{
    const open=$('sidebar').classList.toggle('visible');
    $('mobile-menu').setAttribute('aria-expanded',String(open));
    $('mobile-menu').setAttribute('aria-label',open?'Close navigation':'Open navigation');
  });
  $('open-command').addEventListener('click',showCommand);
  $('search-overlay').addEventListener('click',e=>{if(e.target===$('search-overlay'))hideCommand();});
  let searchTimer=null;
  $('command-query').addEventListener('input',e=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>renderCommandResults(e.target.value.trim()),150);});
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();saveDraft(false);}
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'||(e.key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName))){
      e.preventDefault();showCommand();}
    if(e.key==='Escape')hideCommand();
    if(e.key==='Tab'&&!$('search-overlay').classList.contains('hidden'))window.ARDSUI?.trapTab(e,$('search-overlay'));
  });
}
async function init(){
  try{
    const session=await api('/api/session');state.token=session.token;
    bind();await loadFacets();await Promise.all([loadProblems(),loadOverview()]);
    const hash=decodeURIComponent(location.hash);
    if(hash.startsWith('#/problem/')){await openProblem(hash.slice(10));}
    else if(hash.startsWith('#/method')){$('nav-method').click();if(window.PPCGuide){const chapter=hash.slice('#/method/'.length);if(chapter&&chapter!==hash)window.PPCGuide.select(chapter);}}
    else if(hash==='#/overview'){$('nav-overview').click();}
  }catch(err){
    const network=err instanceof TypeError&&/fetch|network|load failed/i.test(err.message);
    $('problem-list').innerHTML='<div class="empty-state">'+(network
      ?'Could not connect to ARDS: '+esc(err.message)+'.<br>Check that the local server is running.'
      :'ARDS could not start: '+esc(err.message)+'.<br>If you just updated the files, restart the local server and hard-refresh (Ctrl+Shift+R).')+'</div>';}
}
init();
