'use strict';
/* ARDS problem reader, independent scrolling and modal UI; no external JS. */
(() => {
  const $=id=>document.getElementById(id);
  const h=(tag,cls,text)=>{
    const n=document.createElement(tag);if(cls)n.className=cls;
    if(text!==undefined)n.textContent=text;
    return n;
  };
  let previousFocus=null;
  const supers={'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻'};
  function math(s){
    return String(s).replace(/<=/g,'≤').replace(/>=/g,'≥')
      .replace(/\^(-?\d+)/g,(_,digits)=>[...digits].map(c=>supers[c]||c).join(''))
      .replace(/\*/g,'×').replace(/([^\s])\s*<=\s*/g,'$1 ≤ ');
  }
  function card(title,value){
    const outer=h('section','sample-card');
    const cap=h('div','sample-card-title',title);
    const pre=h('pre','sample-code',value);
    outer.append(cap,pre);return outer;
  }
  function renderStatement(el,detail){
    if(!window.ARDSStatement)throw Error('Statement renderer failed to load');
    return window.ARDSStatement.render(el,detail);
  }
  function closeModal(){
    $('workspace-dialog-overlay').classList.add('hidden');
    $('workspace-dialog-content').replaceChildren();
    $('workspace-dialog-actions').replaceChildren();
    document.body.classList.remove('modal-open');
    previousFocus?.focus?.();
  }
  function openModal(title,subtitle,content,actions=[]){
    previousFocus=document.activeElement;
    $('workspace-dialog-title').textContent=title;
    $('workspace-dialog-subtitle').textContent=subtitle||'';
    const body=$('workspace-dialog-content');
    body.replaceChildren();
    if(content)body.append(content);
    const footer=$('workspace-dialog-actions');footer.replaceChildren();
    for(const action of actions){
      const button=h('button',action.primary?'button button-primary':'button button-outline',action.label);
      button.type='button';
      button.addEventListener('click',()=>{closeModal();action.action();});
      footer.append(button);
    }
    $('workspace-dialog-overlay').classList.remove('hidden');
    document.body.classList.add('modal-open');
    $('workspace-dialog-close').focus();
  }
  async function preview(id,fetchProblem,openProblem,showSimilar){
    const detail=await fetchProblem(id);
    const content=h('div','preview-content');
    renderStatement(content,detail);
    openModal(detail.title,detail.id+' · Level '+(detail.difficulty??'—'),content,[
      {label:'Find similar problems',action:()=>showSimilar(detail.id)},
      {label:'Open PPC workspace',primary:true,action:()=>openProblem(detail.id)}
    ]);
  }
  async function explain(section){
    const chapter={problem:'spec',procedure:'algorithm',correctness:'proof',complexity:'complexity'}[section]||'spec';
    const response=await fetch('/guide-content.html',{cache:'no-store'});
    if(!response.ok)throw Error('Cannot load PPC manual.');
    const raw=await response.text();
    const doc=new DOMParser().parseFromString(raw,'text/html');
    const article=[...doc.querySelectorAll('.manual-lesson')].find(el=>el.dataset.id===chapter);
    if(!article)throw Error('Guide chapter is unavailable.');
    const content=h('div','help-content');
    const heading=article.querySelector('.manual-reading-head');
    const main=article.querySelector('.manual-body');
    if(heading)content.append(document.importNode(heading,true));
    if(main)content.append(document.importNode(main,true));
    // Only display the explanation: chapter navigation must not change.
    content.querySelectorAll('button').forEach(button=>button.remove());
    openModal(({problem:'Problem specification',procedure:'Proposed algorithm',correctness:'Correctness proof',complexity:'Complexity analysis'})[section],
      'PPC framework reference',content);
  }
  function confirmReveal(id,onConfirm){
    // This dialog is the consent step. Do not call the reveal endpoint until
    // the user explicitly activates the affirmative button.
    const content=h('div','reveal-confirmation');
    content.append(h('p','reveal-confirmation-intro',
      'Opening the teacher reference is permanent for this challenge and changes which attempts can receive independent credit.'));
    const consequences=h('ul','reveal-confirmation-list');
    for(const message of [
      'Independent passes already graded will remain counted.',
      'Later attempts cannot earn new independent assessment credit.',
      'Ungraded or unsuccessful attempts will not be preserved.'
    ])consequences.append(h('li','',message));
    content.append(consequences);
    openModal('Reveal reference PPC?',id+' · Assessment consequences',content,[
      {label:'Cancel',action:()=>{}},
      {label:'Reveal PPC',primary:true,action:onConfirm}
    ]);
    // Safe default: pressing Enter must not immediately reveal the solution.
    $('workspace-dialog-actions').querySelector('button')?.focus();
  }
  function showReference(data){
    // A proper modal reference document, not four unformatted excerpts.
    // ARDSStatement.rich uses local Markdown-It (HTML disabled) and untrusted KaTeX.
    const content=h('article','reference-modal-content');
    const intro=h('p','reference-assurance',data.verification_scope);
    content.append(intro);
    const sections=[
      ['problem','P1','Problem specification'],
      ['procedure','P2','Proposed Algorithm'],
      ['correctness','C','Correctness proof'],
      ['complexity','K','Complexity analysis']
    ];
    const navigation=h('nav','reference-contents');
    navigation.setAttribute('aria-label','Reference PPC sections');
    for(const [key,short,name] of sections){
      const button=h('button','reference-jump',short+' · '+name);
      button.type='button';
      button.addEventListener('click',()=>{
        const target=content.querySelector('[data-ppc-section="'+key+'"]');
        target?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
      });
      navigation.append(button);
    }
    content.append(navigation);
    for(const [key,short,name] of sections){
      const section=h('section','reference-entry');
      section.dataset.ppcSection=key;
      section.append(h('h3','reference-section-heading',short+' · '+name));
      const value=data.reference_ppc?.[key]||'No reference provided for this section.';
      section.append(window.ARDSStatement.referenceRich(value));
      content.append(section);
    }
    openModal('Reference PPC',data.message,content);
  }
  function setSidebar(collapsed){
    document.getElementById('app').classList.toggle('sidebar-collapsed',collapsed);
    $('collapse-sidebar').setAttribute('aria-expanded',String(!collapsed));
    $('collapse-sidebar').setAttribute('aria-label',collapsed?'Expand navigation rail':'Collapse sidebar');
    $('collapse-sidebar').title=collapsed?'Expand sidebar':'Collapse sidebar';
    localStorage.setItem('ards-sidebar-collapsed',collapsed?'1':'0');
  }
  function init(){
    $('collapse-sidebar').addEventListener('click',()=>{
      if($('app').classList.contains('sidebar-collapsed'))setSidebar(false);
      else setSidebar(true);
    });
    setSidebar(localStorage.getItem('ards-sidebar-collapsed')==='1');
    $('workspace-dialog-close').addEventListener('click',closeModal);
    $('workspace-dialog-overlay').addEventListener('click',e=>{
      if(e.target===$('workspace-dialog-overlay'))closeModal();
    });
    document.addEventListener('keydown',e=>{
      const overlay=$('workspace-dialog-overlay');
      if(overlay.classList.contains('hidden'))return;
      if(e.key==='Escape')closeModal();
      else if(e.key==='Tab')trapTab(e,overlay);
    });
  }
  // Keep Tab / Shift+Tab inside a modal container (WP2: dialogs trap focus).
  function trapTab(e,container){
    const items=[...container.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
      .filter(el=>el.offsetParent!==null||el===document.activeElement);
    if(!items.length){e.preventDefault();return;}
    const first=items[0],last=items[items.length-1];
    if(!container.contains(document.activeElement)){e.preventDefault();first.focus();}
    else if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  }
  window.ARDSUI={init,renderStatement,preview,explain,confirmReveal,showReference,closeModal,openModal,trapTab};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
  else init();
})();
