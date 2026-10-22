'use strict';
/* ARDS PPC editor helpers: caret-safe insertion, symbol palette, Tab and list
   behaviour. Zero external dependencies. This file only handles the student's
   own text in the textarea; it never touches teacher material. */
(() => {
  // Per-section outlines, taken verbatim from the PPC Field Manual skeleton in
  // guide.js (without the "# P1 — ..." headings, because the tab already names
  // the section).
  const SKELETONS={
    problem:'Domain and input types:\nRequired output relation Q(x,y):\nInfeasible/edge cases:\n',
    procedure:'State and initialization:\nTransitions and choice rule:\nStop condition and return value:\n',
    correctness:'Main lemma/invariant:\nInitialization/base:\nPreservation/inductive step:\nTermination:\nExit/postcondition:\nFeasibility and optimality if applicable:\n',
    complexity:'Input measure and cost model:\nTime bound (derived):\nAuxiliary space bound (derived):\n'
  };
  // label = what is shown, name = spoken name, text = inserted text,
  // back = how many characters to move the caret back after inserting.
  const SYMBOLS=[
    {label:'∀',name:'for all',text:'∀'},{label:'∃',name:'there exists',text:'∃'},
    {label:'∈',name:'element of',text:'∈'},{label:'∉',name:'not an element of',text:'∉'},
    {label:'⊆',name:'subset of or equal to',text:'⊆'},{label:'≤',name:'less than or equal to',text:'≤'},
    {label:'≥',name:'greater than or equal to',text:'≥'},{label:'≠',name:'not equal to',text:'≠'},
    {label:'⇒',name:'implies',text:'⇒'},{label:'⇔',name:'if and only if',text:'⇔'},
    {label:'Σ',name:'sum',text:'Σ'},{label:'∏',name:'product',text:'∏'},
    {label:'∧',name:'logical and',text:'∧'},{label:'∨',name:'logical or',text:'∨'},
    {label:'¬',name:'logical not',text:'¬'},
    {label:'\\( \\)',name:'inline math delimiters',text:'\\(  \\)',back:3},
    {label:'\\[ \\]',name:'display math delimiters',text:'\\[\n\n\\]',back:3}
  ];

  // Insert text at the caret (replacing any selection) in a way that keeps the
  // browser's native undo stack. execCommand is deprecated but is still the
  // only way to get undoable programmatic edits in a textarea; fall back to
  // setRangeText (not undoable, but never loses text) if it is unavailable.
  function insertAtCaret(ta,text,back=0){
    if(document.activeElement!==ta)ta.focus({preventScroll:true});
    let done=false;
    try{done=document.execCommand('insertText',false,text);}catch(e){done=false;}
    if(!done){
      ta.setRangeText(text,ta.selectionStart,ta.selectionEnd,'end');
      ta.dispatchEvent(new Event('input',{bubbles:true}));
    }
    if(back){const p=Math.max(0,ta.selectionStart-back);ta.setSelectionRange(p,p);}
  }
  function deleteRange(ta,from,to){
    ta.setSelectionRange(from,to);
    let done=false;
    try{done=document.execCommand('delete');}catch(e){done=false;}
    if(!done){ta.setRangeText('',from,to,'end');ta.dispatchEvent(new Event('input',{bubbles:true}));}
  }

  // Enter continues "1." / "1)" numbered lists and "-", "*", "+", "•" bullets.
  // Enter on an empty item ends the list.
  function continueList(event,ta){
    if(ta.selectionStart!==ta.selectionEnd)return;
    const pos=ta.selectionStart,value=ta.value;
    const lineStart=value.lastIndexOf('\n',pos-1)+1;
    const before=value.slice(lineStart,pos);
    const m=/^(\s*)(?:(\d+)([.)])|([-*+•]))\s+(.*)$/.exec(before);
    if(!m)return;
    const restOfLine=value.slice(pos,(value.indexOf('\n',pos)<0?value.length:value.indexOf('\n',pos)));
    event.preventDefault();
    if(!m[5].trim()&&!restOfLine.trim()){deleteRange(ta,lineStart,pos);return;}
    const marker=m[2]!==undefined?(m[1]+(Number(m[2])+1)+m[3]+' '):(m[1]+m[4]+' ');
    insertAtCaret(ta,'\n'+marker);
  }

  // Tab inserts two spaces. Escape then Tab (or Shift+Tab) leaves the box, so
  // keyboard users are never trapped.
  function bindTextarea(ta){
    let release=false;
    ta.addEventListener('blur',()=>{release=false;});
    ta.addEventListener('keydown',event=>{
      if(event.defaultPrevented||event.isComposing)return;
      if(event.key==='Escape'){release=true;return;}
      if(event.key==='Tab'){
        if(event.shiftKey||event.ctrlKey||event.metaKey||event.altKey||release)return;
        event.preventDefault();insertAtCaret(ta,'  ');return;
      }
      release=false;
      if(event.key==='Enter'&&!event.shiftKey&&!event.ctrlKey&&!event.metaKey&&!event.altKey)continueList(event,ta);
    });
  }

  // Build the symbol buttons. Keyboard activation keeps focus on the palette so
  // several symbols can be inserted in a row; a mouse click returns to the text.
  function buildPalette(root,ta){
    root.replaceChildren();
    for(const symbol of SYMBOLS){
      const button=document.createElement('button');
      button.type='button';
      button.className='symbol-button';
      button.textContent=symbol.label;
      button.title=symbol.name;
      button.setAttribute('aria-label','Insert '+symbol.name);
      button.addEventListener('click',event=>{
        const pointer=event.detail>0;
        insertAtCaret(ta,symbol.text,symbol.back||0);
        if(!pointer)button.focus({preventScroll:true});
      });
      root.append(button);
    }
  }

  window.ARDSEditor={SKELETONS,SYMBOLS,insertAtCaret,bindTextarea,buildPalette};
})();
