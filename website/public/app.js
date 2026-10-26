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
  markActive(name==='drafts'||(name==='problem'&&state.problemOrigin==='drafts')?'nav-drafts':name==='overview'?'nav-overview':name==='guide'?'nav-method':'nav-library');
  $('sidebar').classList.remove('visible');
  $('mobile-menu').setAttribute('aria-expanded','false');
  $('mobile-menu').setAttribute('aria-label','Open navigation');
  window.scrollTo({top:0,behavior:'instant'});
}
function refreshStats(stats){
  $('sidebar-count').textContent=stats.published;
  $('overview-details').innerHTML=[
    ['Authored problems (including private review queue)',stats.authored],
    ['Awaiting verification',stats.under_review],
    ['Released for assessed practice',stats.published],
    ['Saved PPC drafts',stats.drafts],['Submitted PPCs',stats.attempts],
    ['Independent graded attempts',stats.independent_graded],
    ['Problems with reference viewed',stats.revealed],
    ['Recorded reviews',stats.assessments],
    ['Privacy','Local-only'],['Difficulty policy','Classic RACG']
  ].map(([name,value])=>'<div class="overview-row"><span>'+esc(name)+'</span><strong>'+esc(value)+'</strong></div>').join('');
}
function statusFor(problem){
  if(problem.review_only||problem.status==='under_review')return {label:'Under review',cls:'review'};
  if(problem.reference_revealed)return {label:'Reference viewed',cls:'done'};
  if(problem.passed)return {label:'Passed review',cls:'done'};
  if(problem.status==='presented')return {label:'Ready to solve',cls:'open'};
  if(problem.status==='attempted')return {label:'Attempted',cls:'open'};
  if(problem.status==='evaluated')return {label:'Reviewed',cls:''};
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
      '<span><span class="level-chip">Level '+esc(p.difficulty??'—')+'</span><span class="level-pips" aria-hidden="true">'+[1,2,3,4,5,6].map(n=>n<=p.difficulty?'▰':'▱').join('')+'</span></span>'+
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
    ['filter-presentation','presentation'],
    ['filter-similar','similar_to'],['filter-sort','sort']
  ]){
    const value=$(control).value;
    if(value)query.set(key,value);
  }
  const lifecycle=window.ARDSLogic.lifecycleParam($('filter-progress').value);
  if(lifecycle)query.set(...lifecycle);
  saveLibraryState();renderFilterChips();
  $('problem-list').setAttribute('aria-busy','true');
  const data=await api('/api/problems?'+query);
  $('problem-list').setAttribute('aria-busy','false');
  if(requestId!==state.problemRequestId)return;
  state.problems=data.problems;
  state.page=data.page;
  state.pages=data.pages;
  state.total=data.total;
  renderProblems();saveLibraryState();
  const searching=Boolean(state.search.trim());
  $('result-count').textContent=searching?data.total+' matching problems':'';
  $('result-count').classList.toggle('has-results',searching);
  $('filter-summary')?.classList.toggle('has-search',searching);
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
  fill($('filter-topic'),window.ARDSLogic.topicLabels(data.topics),x=>x.id,x=>x.text);
  fill($('filter-family'),data.families,x=>x,x=>window.ARDSLogic.familyLabel(x,data.topics));
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
  try{const [stats,problems]=await Promise.all([api('/api/overview'),allPublicProblems()]);refreshStats(stats);renderOverview(problems);}catch(err){notify('Could not load workspace overview: '+err.message,true);}
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
  for(const s of SECTIONS)parts.push('## '+SECTION_LABELS[s],'',state.draft[s]||'_(empty)_','');
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
async function openProblem(id,{fromRoute=false}={}){
  if(!fromRoute){state.problemOrigin=state.view==='problem'?(state.problemOrigin||'drafts'):state.view==='drafts'?'drafts':'library';try{sessionStorage.setItem('ards-problem-origin',state.problemOrigin);}catch{}rememberLibraryScroll();navigate('#/problem/'+encodeURIComponent(id));return;}
  try{state.problemOrigin=sessionStorage.getItem('ards-problem-origin')||'library';}catch{}
  const request=++problemOpenRequest;
  $('workspace-loading').classList.remove('hidden');
  if(state.current&&state.current.id!==id&&state.draft)await saveDraft(true);
  try{
    const [problem,draft]=await Promise.all([api('/api/problems/'+encodeURIComponent(id)),api('/api/drafts/'+encodeURIComponent(id))]);
    if(request!==problemOpenRequest||window.ARDSLogic.parseRoute(location.hash).id!==id)return;
    state.current=problem;window.dispatchEvent(new CustomEvent("ards-java-open",{detail:problem.id}));state.draft={};SECTIONS.forEach(s=>state.draft[s]=draft[s]||'');
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
    rememberRecentProblem(problem);
    renderAssessments(problem);
    offerLocalMirror(id,draft);
  }catch(err){if(request!==problemOpenRequest)return;switchView('unavailable');$('unavailable-message').textContent=err.status===404?'Problem not found. It may not be released.':err.message;}
  finally{if(request===problemOpenRequest)$('workspace-loading').classList.add('hidden');}
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
    $('problem-progress').textContent='REFERENCE VIEWED';
    button.textContent='View PPC';
    $('independent-attest').disabled=true;
    preserveText();
    window.ARDSUI.showReference(result,state.draft);
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
    state.current.attempt_count=(state.current.attempt_count||0)+1;
    clearMirror(state.current.id);
    setSaveState('idle','Submitted · '+response.stage);
    await loadOverview();
  }catch(err){if(!handleWriteError(err))notify('Could not submit PPC: '+err.message,true);}
  finally{state.busy=false;$('submit-ppc').disabled=Boolean(state.current?.review_only)||!allFilled();}
}
function goLibrary(){navigate('#/');}
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
  const request=++commandRequest;
  const root=$('command-results');root.replaceChildren();
  const add=(label,action,secondary='')=>{
    const button=document.createElement('button');button.type='button';button.className='command-result';
    const text=document.createElement('span');
    for(const part of window.ARDSLogic.highlightParts(label,query)){
      const node=document.createElement(part.match?'mark':'span');node.textContent=part.text;text.append(node);
    }
    const small=document.createElement('small');small.textContent=secondary;button.append(text,small);
    button.addEventListener('click',()=>{hideCommand();action();});root.append(button);
  };
  const actions=[['Open drafts',()=>navigate('#/drafts')],['Go to overview',()=>navigate('#/overview')],['Save draft',()=>saveDraft(false)],
    ...['start','spec','algorithm','proof','methods','complexity','notation','example'].map((chapter,i)=>['Open manual chapter '+(i+1)+' · '+chapter,()=>navigate('#/method/'+chapter)])];
  for(const [label,action] of actions)if(label.toLowerCase().includes(query.toLowerCase())&&(label!=='Save draft'||state.view==='problem'))add(label,action,'Action');
  try{
    const result=await api('/api/problems?'+new URLSearchParams({q:query}));if(request!==commandRequest)return;
    const recent=readStored('ards-recent-problems',[]),rows=result.problems;
    rows.sort((a,b)=>{const rank=id=>{const n=recent.findIndex(x=>x.id===id);return n<0?999:n;};return rank(a.id)-rank(b.id);});
    for(const p of rows)add(p.title,()=>openProblem(p.id),(recent.some(x=>x.id===p.id)?'Recent · ':'')+p.id);
    if(!root.childElementCount)root.textContent='No matches.';
  }catch(err){if(request===commandRequest)notify(err.message,true);}
}
function bind(){
  bindSimilarPicker();
  bindRemaining();
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
  $('nav-drafts').addEventListener('click',()=>navigate('#/drafts'));
  $('nav-overview').addEventListener('click',()=>navigate('#/overview'));
  $('nav-method').addEventListener('click',()=>navigate('#/method/start'));
  $('learn-ppc').addEventListener('click',()=>$('nav-method').click());
  $('go-back').addEventListener('click',()=>navigate('#/drafts'));
  $('next-problem').addEventListener('click',nextProblem);
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
/* Routing, student-only draft discovery, and library session state. */
let problemOpenRequest=0,routeRequest=0,commandRequest=0;
const FILTER_IDS=['filter-level','filter-topic','filter-family','filter-presentation','filter-progress','filter-similar','filter-sort'];
let draftEntries=[];
function readStored(key,fallback){try{return JSON.parse(localStorage.getItem(key))??fallback;}catch{return fallback;}}
function rememberRecentProblem(p){
  try{localStorage.setItem('ards-recent-problems',JSON.stringify(window.ARDSLogic.rememberRecent(readStored('ards-recent-problems',[]),p.id,p.title)));}catch{}
}
function saveLibraryState(){
  try{sessionStorage.setItem('ards-library-state',JSON.stringify({page:state.page,perPage:state.perPage,search:state.search,scroll:state.libraryScroll||0,filters:Object.fromEntries(FILTER_IDS.map(id=>[id,$(id).value]))}));}catch{}
}
function rememberLibraryScroll(){if(state.view==='library'){state.libraryScroll=window.scrollY;saveLibraryState();}}
function restoreLibraryState(){
  try{
    const saved=JSON.parse(sessionStorage.getItem('ards-library-state')||'null');if(!saved)return;
    state.page=Math.max(1,Number(saved.page)||1);state.perPage=[12,24,48].includes(saved.perPage)?saved.perPage:12;
    state.search=String(saved.search||'');state.libraryScroll=Number(saved.scroll)||0;
    $('library-search').value=state.search;$('page-size').value=state.perPage;
    for(const id of FILTER_IDS)if(saved.filters?.[id]!==undefined)$(id).value=saved.filters[id];
    syncSimilarSelection();
  }catch{}
}
function navigate(hash){
  rememberLibraryScroll();
  if(location.hash===hash){route();return;}location.hash=hash;
}
async function route(){
  const version=++routeRequest;
  const route=window.ARDSLogic.parseRoute(location.hash);
  if(state.view==='library')rememberLibraryScroll();
  if(state.current&&state.draft){clearTimeout(state.saveTimer);await saveDraft(true);writeMirror();}
  if(version!==routeRequest)return;
  if(route.name==='problem'){await openProblem(route.id,{fromRoute:true});return;}
  ++problemOpenRequest;$('workspace-loading').classList.add('hidden');
  if(route.name==='guide'){
    switchView('guide');window.PPCGuide?.select(route.chapter,{hash:false,scroll:false});
  }else if(route.name==='overview'){switchView('overview');await loadOverview();}
  else if(route.name==='drafts'){switchView('drafts');await loadDrafts();}
  else{
    switchView('library');await Promise.all([loadProblems(),updateContinue()]);
    if(version===routeRequest)window.scrollTo({top:state.libraryScroll||0,behavior:'instant'});
    if(route.invalid)notify('Unknown page. Showing the problem library.');
  }
}
async function nextProblem(){
  const button=$('next-problem');if(button.disabled||!state.current)return;button.disabled=true;
  try{
    const rows=await allPublicProblems();
    const picked=window.ARDSLogic.pickNextProblem(rows,state.current);
    if(!picked){notify('No other released problems with an unviewed reference are available.');return;}
    await saveDraft(true);openProblem(picked.id);
  }catch(err){notify('Could not open the next problem: '+err.message,true);}
  finally{button.disabled=false;}
}
async function allPublicProblems(){
  let rows=[],page=1;
  do{
    const result=await api('/api/problems?'+new URLSearchParams({page,per_page:48}));
    rows.push(...result.problems);if(page>=result.pages)break;page++;
  }while(true);
  return rows;
}
async function loadDrafts(){
  const root=$('draft-list');root.replaceChildren(skeleton('Loading saved drafts'));
  try{
    const problems=await allPublicProblems();
    const entries=await Promise.all(problems.map(async p=>({id:p.id,title:p.title,draft:await api('/api/drafts/'+encodeURIComponent(p.id))})));
    draftEntries=entries.filter(e=>e.draft.updated_at).map(e=>({...e,updated_at:e.draft.updated_at}));
    draftEntries.sort((a,b)=>b.updated_at.localeCompare(a.updated_at));root.replaceChildren();
    if(!draftEntries.length){root.textContent='No saved drafts yet. Open a problem and start writing.';return;}
    const table=document.createElement('table');table.className='draft-table';
    const head=document.createElement('thead');head.innerHTML='<tr><th scope="col">Problem</th><th scope="col">Last saved</th><th scope="col">Sections with content</th></tr>';table.append(head);
    const body=document.createElement('tbody');
    for(const e of draftEntries){
      const row=document.createElement('tr'),name=document.createElement('td'),button=document.createElement('button');
      button.type='button';button.className='text-link';button.textContent=e.title+' · '+e.id;button.addEventListener('click',()=>openProblem(e.id));name.append(button);
      const date=document.createElement('td');date.textContent=new Date(e.updated_at).toLocaleString();
      const sections=document.createElement('td');sections.textContent=SECTIONS.map((s,i)=>['P1','P2','C','K'][i]+': '+(e.draft[s].trim()?'filled':'empty')).join(' · ');
      row.append(name,date,sections);body.append(row);
    }
    table.append(body);root.append(table);
  }catch(err){root.textContent='Could not load drafts: '+err.message;}
}
function downloadText(text,name,type){
  const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([text],{type}));link.download=name;
  document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
}
function skeleton(label){
  const node=document.createElement('div');node.className='skeleton-row';node.setAttribute('role','status');node.setAttribute('aria-label',label);return node;
}
async function updateContinue(){
  $('continue-card').classList.add('hidden');if(!state.lastSelected)return;
  try{
    const p=await api('/api/problems/'+encodeURIComponent(state.lastSelected));
    $('continue-title').textContent=p.title;$('continue-meta').textContent=p.id+' · Level '+p.difficulty;
    $('continue-card').classList.remove('hidden');
  }catch{}
}
function renderFilterChips(){
  const root=$('filter-chips');root.replaceChildren();let count=0;
  const chip=(label,action)=>{const b=document.createElement('button');b.type='button';b.className='filter-chip';b.textContent=label+' ×';b.setAttribute('aria-label','Remove '+label);b.addEventListener('click',action);root.append(b);};
  const reload=()=>loadProblems('',{resetPage:true}).catch(e=>notify(e.message,true));
  for(const id of FILTER_IDS){
    const el=$(id);if(!el.value||(id==='filter-sort'&&el.value==='newest'))continue;
    const label=id==='filter-similar'?'Similar to '+el.value:el.selectedOptions[0]?.textContent||el.value;
    chip(label,()=>{el.value=id==='filter-sort'?'newest':'';syncSimilarSelection();reload();});
    if(['filter-topic','filter-family','filter-presentation','filter-similar'].includes(id))count++;
  }
  if(root.childElementCount){const b=document.createElement('button');b.type='button';b.className='tool-button';b.textContent='Clear all';b.addEventListener('click',()=>{for(const id of FILTER_IDS)$(id).value=id==='filter-sort'?'newest':'';state.search='';$('library-search').value='';syncSimilarSelection();reload();});root.append(b);}
  $('more-filters-count').hidden=!count;$('more-filters-count').textContent=String(count);
}
function bindRemaining(){
  const loading=document.createElement('div');loading.id='workspace-loading';loading.className='workspace-loading hidden';loading.append(skeleton('Loading problem'));$('app').append(loading);
  $('unavailable-back').addEventListener('click',goLibrary);
  $('continue-open').addEventListener('click',()=>openProblem(state.lastSelected));
  const more=document.createElement('div');more.id='more-filters-panel';more.className='more-filters-panel';more.hidden=true;
  for(const control of document.querySelectorAll('#filter-set .secondary-filter'))more.append(control);
  $('filter-set').append(more);$('more-filters-toggle').setAttribute('aria-controls',more.id);
  const closeMore=()=>{more.hidden=true;$('more-filters-toggle').setAttribute('aria-expanded','false');};
  $('more-filters-toggle').addEventListener('click',()=>{more.hidden=!more.hidden;$('more-filters-toggle').setAttribute('aria-expanded',String(!more.hidden));});
  document.addEventListener('click',e=>{if(!more.contains(e.target)&&!$('more-filters-toggle').contains(e.target))closeMore();});
  more.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();closeMore();$('more-filters-toggle').focus();}});
  $('export-all-md').addEventListener('click',()=>downloadText(draftEntries.map(e=>window.ARDSLogic.draftMarkdown(e.id,e.title,e.draft,e.updated_at)).join('\n---\n\n'),'ards-drafts.md','text/markdown;charset=utf-8'));
  $('export-all-json').addEventListener('click',()=>downloadText(window.ARDSLogic.draftsJson(draftEntries),'ards-drafts.json','application/json;charset=utf-8'));
}
function renderOverview(problems){
  const summary=window.ARDSLogic.progressSummary(problems),root=$('overview-levels');root.replaceChildren();
  if(!summary.total){
    const p=document.createElement('p');p.textContent='No released problems yet. Your released, attempted, and passed counts will appear here.';
    const link=document.createElement('a');link.href='#/method/start';link.textContent='Read the PPC manual';root.append(p,link);
  }else{
    const heading=document.createElement('h2');heading.textContent='Progress by level';root.append(heading);
    for(const row of summary.levels)root.append(progressRow('Level '+row.level,row));
  }
  const topics=$('overview-topics');topics.replaceChildren(...summary.topics.map(row=>progressRow(row.label,row)));
}
function progressRow(label,row){
  const section=document.createElement('section');section.className='progress-row';
  const heading=document.createElement('h3');heading.textContent=label;
  const counts=document.createElement('p');counts.textContent=row.released+' released · '+row.attempted+' attempted · '+row.passed+' passed review';
  const meter=document.createElement('meter');meter.min=0;meter.max=Math.max(1,row.released);meter.value=row.attempted;meter.setAttribute('aria-label',label+': attempted '+row.attempted+' of '+row.released+' released');
  section.append(heading,counts,meter);return section;
}
async function renderAssessments(problem){
  const root=$('assessment-panel');root.replaceChildren();
  const title=document.createElement('h3');title.textContent='Recorded reviews';
  const note=document.createElement('p');note.textContent="A review is a reviewer's critique, not a machine proof. Submissions are not auto-graded.";root.append(title,note);
  try{
    const {reviews}=await api('/api/reviews/'+encodeURIComponent(problem.id),{headers:{'X-ARDS-Session':state.token}});
    if(state.current?.id!==problem.id)return;
    if(!reviews.length){const p=document.createElement('p');p.textContent='No recorded reviews yet.';root.append(p);}
    for(const review of reviews){
      const details=document.createElement('details');details.className='assessment-review';details.dataset.verdict=review.verdict;
      const summary=document.createElement('summary');summary.textContent=review.verdict.charAt(0).toUpperCase()+review.verdict.slice(1)+' · '+review.reviewer+' · '+new Date(review.assessed_at).toLocaleDateString()+' · attempt '+review.attempt_id;
      details.append(summary);
      for(const section of SECTIONS){
        const heading=document.createElement('h4');heading.textContent=SECTION_LABELS[section];details.append(heading);
        const finding=review.sections[section];
        if(!finding){const p=document.createElement('p');p.textContent='No structured section finding recorded.';details.append(p);continue;}
        for(const [field,label] of [['status','Finding status'],['finding','Finding'],['evidence','Evidence'],['uncertainty','Stated uncertainty']]){
          const p=document.createElement('p');p.textContent=label+': '+(finding[field]||'Not separately recorded.');details.append(p);
        }
      }
      root.append(details);
    }
  }catch(err){if(state.current?.id===problem.id){const p=document.createElement('p');p.textContent='Reviews unavailable: '+err.message;root.append(p);}}
}
async function init(){
  try{
    const session=await api('/api/session');state.token=session.token;
    bind();await loadFacets();restoreLibraryState();await Promise.all([loadProblems(),loadOverview(),updateContinue()]);
    window.addEventListener('hashchange',route);await route();
  }catch(err){
    const network=err instanceof TypeError&&/fetch|network|load failed/i.test(err.message);
    $('problem-list').innerHTML='<div class="empty-state">'+(network
      ?'Could not connect to ARDS: '+esc(err.message)+'.<br>Check that the local server is running.'
      :'ARDS could not start: '+esc(err.message)+'.<br>If you just updated the files, restart the local server and hard-refresh (Ctrl+Shift+R).')+'</div>';}
}
init();
