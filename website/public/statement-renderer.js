'use strict';
/* CodeChef-inspired, offline Markdown + KaTeX statement presentation.
 * All problem text is escaped by markdown-it (html:false); math is rendered
 * with KaTeX (trust:false). Executable HTML and remote images are disallowed.
 */
(() => {
 const el=(tag,cls='',text)=>{
   const node=document.createElement(tag);
   if(cls)node.className=cls;
   if(text!==undefined)node.textContent=String(text);
   return node;
 };
 function markdown(){
   if(!window.markdownit)throw Error('The offline Markdown renderer is unavailable');
   const instance=window.markdownit({html:false,linkify:false,breaks:true,typographer:false});
   instance.disable(['image']);
   return instance;
 }
 function mathMarkup(formula,display){
   const math=document.createElement(display?'div':'span');
   math.className=display?'statement-math-block':'statement-math-inline';
   if(window.katex){
     try{
       window.katex.render(formula,math,{
         displayMode:display,throwOnError:false,trust:false,
         strict:'ignore',maxExpand:150,maxSize:20,output:'htmlAndMathml'
       });
     }catch(error){math.textContent=formula;}
   }else{math.textContent=formula;}
   return math;
 }
 function maskedMath(raw){
   const fragments=[];
   const text=String(raw).replace(/\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\\\(([\s\S]*?)\\\)|\$([^$\n]+)\$/g,
     (full,a,b,c,d)=>{
       if(d && /^\s*\d+(?:\.\d+)?\s*$/.test(d))return full; // currency, not math
       const formula=(a??b??c??d).trim();
       if(!formula)return full;
       const placeholder='ARDSMATHSEGMENT'+fragments.length+'END';
       fragments.push({formula,display:a!==undefined||b!==undefined,placeholder});
       return placeholder;
     });
   return {text,fragments};
 }
 function fillMath(container,fragments){
   if(!fragments.length)return;
   const token=/ARDSMATHSEGMENT(\d+)END/g;
   const walk=document.createTreeWalker(container,NodeFilter.SHOW_TEXT);
   const targets=[];
   while(walk.nextNode()){
     const text=walk.currentNode;
     if(!text.nodeValue.includes('ARDSMATHSEGMENT'))continue;
     if(text.parentElement?.closest('pre,code,kbd'))continue;
     targets.push(text);
   }
   for(const text of targets){
     // A standalone display formula is block content, not a div nested in a
     // paragraph. Let CSS center it and handle horizontal overflow.
     const standalone=/^\s*ARDSMATHSEGMENT(\d+)END\s*$/.exec(text.nodeValue);
     const standRecord=standalone?fragments[Number(standalone[1])]:null;
     if(standRecord?.display && text.parentElement?.tagName==='P'
            && text.parentElement.childNodes.length===1){
       text.parentElement.replaceWith(mathMarkup(standRecord.formula,true));
       continue;
     }
     const frag=document.createDocumentFragment();
     let last=0,match;
     token.lastIndex=0;
     while((match=token.exec(text.nodeValue))!==null){
       if(match.index>last)frag.append(document.createTextNode(text.nodeValue.slice(last,match.index)));
       const record=fragments[Number(match[1])];
       frag.append(record?mathMarkup(record.formula,record.display):document.createTextNode(match[0]));
       last=match.index+match[0].length;
     }
     if(last<text.nodeValue.length)frag.append(document.createTextNode(text.nodeValue.slice(last)));
     text.replaceWith(frag);
   }
 }
 function typesetLegacyTokens(container){
   // Older ARDS statements used X_i and 10^9 without TeX delimiters.
   // Upgrade simple variable tokens without touching verbatim sample/code data.
   const walk=document.createTreeWalker(container,NodeFilter.SHOW_TEXT);
   const targets=[];
   while(walk.nextNode()){
     const t=walk.currentNode;
     if(t.parentElement?.closest('pre,code,kbd,.katex'))continue;
     if(/\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9]+\b|\b(?:[A-Za-z]+|\d+)\^-?\d+\b/.test(t.nodeValue))targets.push(t);
     else if(t.nodeValue.includes('<=')||t.nodeValue.includes('>=')){
       t.nodeValue=t.nodeValue.replace(/<=/g,'≤').replace(/>=/g,'≥');
     }
   }
   const tokens=/\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9]+\b|\b(?:[A-Za-z]+|\d+)\^-?\d+\b/g;
   for(const t of targets){
     const text=t.nodeValue;
     const frag=document.createDocumentFragment();
     let last=0,match;
     tokens.lastIndex=0;
     while((match=tokens.exec(text))!==null){
       if(match.index>last)frag.append(document.createTextNode(text.slice(last,match.index).replace(/<=/g,'≤').replace(/>=/g,'≥')));
       frag.append(mathMarkup(match[0],false));
       last=match.index+match[0].length;
     }
     if(last<text.length)frag.append(document.createTextNode(text.slice(last).replace(/<=/g,'≤').replace(/>=/g,'≥')));
     t.replaceWith(frag);
   }
 }
 function rich(raw,reference=false){
   const box=el('div','statement-markdown');
   if(!raw)return box;
   const masked=maskedMath(String(raw));
   box.innerHTML=markdown().render(masked.text);
   fillMath(box,masked.fragments);
   if(reference)typesetReferenceExpressions(box);
   typesetLegacyTokens(box);
   return box;
 }
 // Archived teacher PPCs can predate the authoring requirement to use TeX.
 // Only upgrade clear, self-contained ASCII mathematical expressions. Never
 // guess missing equations, and never edit or re-save the canonical reference.
 function typesetReferenceExpressions(container){
   const patterns=[
     /\b[A-Za-z][A-Za-z0-9]*\([^()\n]{1,48}\)\s*=\s*\([^()\n]{1,110}\)/g,
     /\b[A-Za-z]\^\d+(?:\s*[+\-*]\s*[A-Za-z]\^\d+)+\s*(?:[<>=]\s*\d+)?/g,
     /\|[A-Za-z][A-Za-z0-9]*\|\s*=\s*[A-Za-z0-9]+/g,
     /\bO\([A-Za-z0-9^+\-*/\s]{2,90}\)/g,
     /\b(?:[A-Za-z][A-Za-z0-9]*|\d+)(?:\s*(?:<=|>=|!=|=|<|>)\s*(?:[A-Za-z][A-Za-z0-9]*|\d+)){1,3}/g
   ];
   const walk=document.createTreeWalker(container,NodeFilter.SHOW_TEXT);
   const targets=[];
   while(walk.nextNode()){
     const node=walk.currentNode;
     if(node.parentElement?.closest('pre,code,kbd,.katex,.statement-math-inline,.statement-math-block'))continue;
     if(patterns.some(pattern=>{pattern.lastIndex=0;return pattern.test(node.nodeValue)}))targets.push(node);
   }
   for(const node of targets){
     const text=node.nodeValue;
     const matches=[];
     for(const pattern of patterns){
       pattern.lastIndex=0;
       for(const match of text.matchAll(pattern)){
         const start=match.index,end=start+match[0].length;
         matches.push({start,end,formula:match[0]});
       }
     }
     matches.sort((a,b)=>a.start-b.start||b.end-a.end);
     const selected=[];
     let used=0;
     for(const match of matches){
       if(match.start>=used){selected.push(match);used=match.end;}
     }
     if(!selected.length)continue;
     const fragment=document.createDocumentFragment();
     let end=0;
     for(const match of selected){
       if(match.start>end)fragment.append(document.createTextNode(text.slice(end,match.start)));
       const formula=match.formula.replace(/<=/g,'\\leq ').replace(/>=/g,'\\geq ')
           .replace(/!=/g,'\\ne ');
       fragment.append(mathMarkup(formula,false));
       end=match.end;
     }
     if(end<text.length)fragment.append(document.createTextNode(text.slice(end)));
     node.replaceWith(fragment);
   }
 }
 function referenceRich(raw){
   const source=String(raw||'');
   // Older PPCs were exported as a single undifferentiated paragraph.
   // Insert presentation-only paragraph breaks; preserve all wording.
   const hasStructure=/\n\s*\n|(^|\n)\s*(?:#{1,6}\s|[-*]\s|\d+\.\s)|\\\[|\\\]|\$\$/.test(source);
   let display=source;
   if(!hasStructure){
     const sentences=source.trim().split(/(?<=[.!?])\s+(?=[A-Z][a-z])/);
     if(sentences.length>=4){
       const paragraphs=[];
       for(let i=0;i<sentences.length;i+=2)paragraphs.push(sentences.slice(i,i+2).join(' '));
       display=paragraphs.join('\n\n');
     }
   }
   return rich(display,true);
 }
 function formulaConstraint(line){
   const t=String(line).trim();
   const looksMath=/[<>=≤≥]/.test(t)&&/^[0-9A-Za-z_\s,.\-\+\^()[\]{}|<>=≤≥*\/\\]+$/.test(t);
   if(!looksMath)return rich(t);
   const cleaned=t.replace(/<=|≤/g,'\\leq ').replace(/>=|≥/g,'\\geq ')
       .replace(/(?<=\d),(?=\d{3}(?:\D|$))/g,'{,}');
   return mathMarkup(cleaned,false);
 }
 function sampleCard(name,value,index){
   const box=el('section','sample-card');
   const title=el('div','sample-card-title',name);
   const copy=el('button','tool-button','Copy');copy.type='button';
   copy.setAttribute('aria-label','Copy sample '+(index+1)+' '+name.toLowerCase());
   copy.addEventListener('click',async()=>{
     try{await navigator.clipboard.writeText(String(value));copy.textContent='Copied';}
     catch{copy.textContent='Copy failed';}
     setTimeout(()=>{copy.textContent='Copy';},1800);
   });
   title.append(copy);box.append(title,el('pre','sample-code',value));
   return box;
 }
 function heading(parent,name){
   const title=el('h3','statement-section-title',name);
   title.dataset.statementSection=name;parent.append(title);
 }
 function render(container,detail){
   const source=detail.presentation_data||{};
   const data={
     description:source.description||detail.statement||'',
     input_format:source.input_format||'',
     output_format:source.output_format||'',
     constraints:Array.isArray(source.constraints)?source.constraints:[],
     samples:Array.isArray(source.samples)?source.samples:[]
   };
   container.replaceChildren();
   container.classList.add('codechef-statement');
   const intro=rich(data.description);
   intro.classList.add('statement-introduction');
   container.append(intro);
   if(data.input_format.trim()){
     heading(container,'Input Format');
     container.append(rich(data.input_format));
   }
   if(data.output_format.trim()){
     heading(container,'Output Format');
     container.append(rich(data.output_format));
   }
   if(data.constraints.length){
     heading(container,'Constraints');
     const ul=el('ul','statement-constraints');
     for(const line of data.constraints){
       const li=el('li');
       li.append(formulaConstraint(line));ul.append(li);
     }
     container.append(ul);
   }
   for(const [index,s] of data.samples.entries()){
     heading(container,'Sample '+(index+1)+':');
     const group=el('div','sample-grid');
     group.append(sampleCard('Input',s.input,index),sampleCard('Output',s.output,index));
     container.append(group);
   }
 }
 window.ARDSStatement={render,rich,referenceRich};
})();