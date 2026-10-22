'use strict';

/* Static offline PPC manual. Never evaluates or executes entered PPC prose. */
(() => {
const chapters=[
 ['start','Orientation','START HERE'],
 ['spec','P1 · Specification','THE CORE'],
 ['algorithm','P2 · Procedure','THE CORE'],
 ['proof','C · Correctness','THE CORE'],
 ['methods','Proof techniques','PROOF TOOLBOX'],
 ['complexity','Complexity','THE CORE'],
 ['notation','Notation dictionary','REFERENCE'],
 ['example','Worked PPC & checklist','PRACTICE']
];
const methodData={
 invariant:{title:'Loop invariant',description:'Use for sequential scans and iterative updates.',points:['State I, the relationship between current state and already-processed input.','Initialization: I holds before the first iteration.','Preservation: each continuing step maintains I.','Exit: I and the stopping condition imply the postcondition.','Termination: prove a finite bound or decreasing variant.'],warning:'Preservation alone does not prove that the invariant starts true or delivers the required answer.'},
 induction:{title:'Mathematical induction',description:'Use for recursive decomposition or structural properties.',points:['Base case: prove the smallest input.','Hypothesis: state correctness for strictly smaller subproblems.','Step: derive correctness on the present input from valid smaller ones.','Termination: each recursive call must decrease a well-founded measure.'],warning:'Do not assume correctness on the same input that you must prove.'},
 greedy:{title:'Exchange argument',description:'Use when greedy choices claim to produce a global optimum.',points:['Prove the greedy result is feasible.','Take any optimal solution and locate its first different choice.','Exchange that choice for the greedy one without losing feasibility or quality.','Repeat or induct to obtain an optimum using every greedy choice.','Prove the process terminates.'],warning:'The exchange step must preserve every constraint; "locally best" is not proof of global optimality.'},
 graph:{title:'Reachability induction',description:'Use for DFS/BFS discovery and unweighted shortest paths.',points:['Prove graph vertices and edges encode the original problem.','Soundness: every discovered vertex has a valid path from the source.','Completeness: every reachable vertex is eventually discovered.','For shortest path claims, prove BFS exploration is nondecreasing in distance.','Prove finite exploration with a visited rule.'],warning:'Merely saying BFS visits everything omits the completeness argument.'},
 binary:{title:'Search invariant',description:'Use for binary search over monotone predicates.',points:['Establish the needed monotonicity of the decision predicate.','State an invariant preserving the answer in a candidate interval.','Show each branch maintains the invariant.','Show intervals shrink and handle boundary cases.','At termination, prove the result is the correct extremal feasible value.'],warning:'Ordering the domain does not ensure the answer predicate is monotone.'},
 counting:{title:'Bijection or matching bounds',description:'Use for counting, constructions, and lower/upper bound matching.',points:['Define what counts as a distinct object or feasible witness.','For bijections, prove injectivity and surjectivity.','For optimization, derive a lower bound applicable to all valid solutions.','Construct a solution attaining that bound.','Check duplicates and overcounting.'],warning:'Counting plausible candidates is not the same as proving each has a witness.'}
};
const skeleton='# P1 — Problem specification\nDomain and input types:\nRequired output relation Q(x,y):\nInfeasible/edge cases:\n\n# P2 — Proposed algorithm\nState and initialization:\nTransitions and choice rule:\nStop condition and return value:\n\n# C — Correctness proof\nMain lemma/invariant:\nInitialization/base:\nPreservation/inductive step:\nTermination:\nExit/postcondition:\nFeasibility and optimality if applicable:\n\n# K — Complexity\nInput measure and cost model:\nTime bound (derived):\nAuxiliary space bound (derived):\n';
let current='start';
let mounted=false;
const el=id=>document.getElementById(id);
async function mount(){
  if(mounted)return;
  const request=await fetch('/guide-content.html',{cache:'no-store'});
  if(!request.ok)throw Error('Manual contents unavailable.');
  const parser=new DOMParser();
  const html=parser.parseFromString(await request.text(),'text/html');
  const nodes=html.querySelectorAll('.manual-lesson');
  if(nodes.length!==chapters.length)throw Error('Manual chapter count mismatch');
  const chaptersList=el('manual-chapters');
  const reading=el('manual-chapter-content');
  let prev='';
  for(const [index,entry] of chapters.entries()){
    const [id,label,group]=entry;
    if(group!==prev){const h=document.createElement('p');h.className='manual-nav-group';h.textContent=group;chaptersList.append(h);prev=group;}
    const button=document.createElement('button');button.type='button';button.className='manual-chapter-nav';button.dataset.chapter=id;
    const num=document.createElement('span');num.className='manual-nav-index';num.textContent=String(index+1).padStart(2,'0');
    const name=document.createElement('span');name.textContent=label;button.append(num,name);
    button.addEventListener('click',()=>select(id));
    chaptersList.append(button);
  }
  const content=el('manual-chapter-content');
  nodes.forEach(node=>{
    const id=node.dataset.id;
    if(!chapters.some(x=>x[0]===id))return;
    content.append(document.importNode(node,true));
  });
  mounted=true;
  el('manual-prev').addEventListener('click',()=>select(chapters[Math.max(0,chapters.findIndex(c=>c[0]===current)-1)][0]));
  el('manual-next').addEventListener('click',()=>select(chapters[Math.min(chapters.length-1,chapters.findIndex(c=>c[0]===current)+1)][0]));
  el('manual-start').addEventListener('click',()=>select('spec'));
  el('manual-copy-template').addEventListener('click',copySkeleton);
  reading.addEventListener('click',event=>{
    const b=event.target.closest('button');
    if(!b)return;
    if(b.dataset.manualGo)select(b.dataset.manualGo);
    if(b.dataset.reveal){
      const answer=el(b.dataset.reveal);if(!answer)return;
      answer.hidden=!answer.hidden;
      b.setAttribute('aria-expanded',String(!answer.hidden));
      b.textContent=answer.hidden?'Reveal the explanation ↓':'Hide the explanation ↑';
    }
    if(b.id==='manual-open-editor')el('nav-drafts').click();
  });
  el('manual-technique').addEventListener('change',renderTechnique);
  el('manual-notation-query').addEventListener('input',filterNotation);
  el('manual-self-check').addEventListener('change',updateChecklist);
  select('start',{scroll:false,hash:false});
}
function select(id,{scroll=true,hash=true}={}){
  if(!mounted)return;
  const index=Math.max(0,chapters.findIndex(c=>c[0]===id));
  const name=chapters[index][0];current=name;
  document.querySelectorAll('.manual-lesson').forEach(node=>node.hidden=node.dataset.id!==name);
  document.querySelectorAll('.manual-chapter-nav').forEach(button=>{
    const active=button.dataset.chapter===name;
    button.classList.toggle('active',active);
    if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
  });
  el('manual-progress').textContent=String(index+1).padStart(2,'0')+' / '+String(chapters.length).padStart(2,'0');
  el('manual-prev').disabled=index===0;
  el('manual-next').disabled=index===chapters.length-1;
  if(name==='methods')renderTechnique();
  if(hash&&location.hash.startsWith('#/method'))history.replaceState(null,'','#/method/'+name);
  // Chapter changes reset only the reading position, not the whole page.
  // The chapter navigation keeps its own scroll position and remains sticky.
  if(scroll&&!el('view-guide').classList.contains('hidden')){
    const reader=el('manual-chapter-content');
    const top=reader.getBoundingClientRect().top+window.scrollY-82;
    window.scrollTo({top:Math.max(0,top),behavior:'instant'});
  }
}
function renderTechnique(){
  const method=methodData[el('manual-technique').value];
  const root=el('manual-technique-detail');
  root.replaceChildren();
  const head=document.createElement('div');head.className='manual-tech-head';
  const strong=document.createElement('strong');strong.textContent=method.title;
  const sub=document.createElement('p');sub.textContent=method.description;
  head.append(strong,sub);
  const ol=document.createElement('ol');ol.className='manual-ordered';
  method.points.forEach(item=>{const li=document.createElement('li');li.textContent=item;ol.append(li);});
  const warning=document.createElement('div');warning.className='manual-pitfall';warning.textContent='Common failure: '+method.warning;
  root.append(head,ol,warning);
}
function filterNotation(){
  const q=el('manual-notation-query').value.trim().toLowerCase();
  document.querySelectorAll('#manual-symbol-rows > div').forEach(item=>{
    item.hidden=!(item.dataset.search+' '+item.textContent).toLowerCase().includes(q);
  });
}
function updateChecklist(){
  const boxes=[...el('manual-self-check').querySelectorAll('input[type=checkbox]')];
  const count=boxes.filter(x=>x.checked).length;
  el('manual-check-progress').textContent=count+' of '+boxes.length+' items reviewed'+(count===boxes.length?' · Re-read your proof before submitting.':'');
}
async function copySkeleton(){
  try{
    await navigator.clipboard.writeText(skeleton);
    const btn=el('manual-copy-template');btn.textContent='Copied ✓';
    setTimeout(()=>{btn.textContent='Copy PPC skeleton';},1500);
  }catch{
    const input=document.createElement('textarea');input.value=skeleton;
    input.className='manual-copy-fallback';input.readOnly=true;
    el('manual-chapter-content').prepend(input);input.focus();input.select();
  }
}
async function open(id='start'){
  try{
    await mount();
    el('nav-method').click();
    select(id);
  }catch(err){
    console.error('PPC guide unavailable',err);
    const slot=el('manual-chapter-content');
    if(slot)slot.textContent='The manual could not load. Please reload the page.';
  }
}
window.PPCGuide={open,select};
const boot=async()=>{
 try{
  await mount();
  const hash=decodeURIComponent(location.hash);
  if(hash.startsWith('#/method/'))select(hash.slice('#/method/'.length),{scroll:false,hash:false});
 }catch(err){console.error(err);}
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();