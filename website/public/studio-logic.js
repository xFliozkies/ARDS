'use strict';
/* ARDS Studio: pure helpers (no DOM, no network, no storage).
   Shared by app.js in the browser and by the Node tests. Handles only
   student-visible data; it never sees teacher material. */
(() => {
  const SECTIONS=['problem','procedure','correctness','complexity'];
  const LEVELS=[1,2,3,4,5,6];

  /* ---- Routing ---------------------------------------------------------- */
  // Hash routes: #/ library, #/problem/<ID>, #/drafts, #/overview, #/method[/chapter]
  function parseRoute(hash){
    let h=String(hash||'');
    try{h=decodeURIComponent(h);}catch{}
    if(!h||h==='#'||h==='#/')return {name:'library'};
    let m=/^#\/problem\/(.*)$/.exec(h);
    if(m){
      const id=m[1].trim();
      return /^[A-Za-z0-9._-]{1,60}$/.test(id)?{name:'problem',id}:{name:'library',invalid:true};
    }
    if(h==='#/drafts')return {name:'drafts'};
    if(h==='#/overview')return {name:'overview'};
    m=/^#\/method(?:\/([A-Za-z0-9_-]*))?$/.exec(h);
    if(m)return {name:'guide',chapter:m[1]||'start'};
    return {name:'library',invalid:true};
  }
  function hashFor(route){
    if(route.name==='problem')return '#/problem/'+encodeURIComponent(route.id);
    if(route.name==='guide')return '#/method/'+(route.chapter||'start');
    if(route.name==='library')return '#/';
    return '#/'+route.name;
  }

  /* ---- Library filters -------------------------------------------------- */
  // The merged lifecycle control carries "progress:<value>" or "status:<value>".
  function lifecycleParam(value){
    const text=String(value||'');
    const i=text.indexOf(':');
    if(i<1)return null;
    const key=text.slice(0,i),rest=text.slice(i+1);
    if(!['progress','status'].includes(key)||!rest)return null;
    return [key,rest];
  }
  const LIFECYCLE_OPTIONS=[
    ['','All problems'],
    ['status:presented','Ready to solve'],
    ['progress:unattempted','Not attempted'],
    ['progress:attempted','Attempted'],
    ['status:evaluated','Reviewed'],
    ['progress:passed','Passed review'],
    ['progress:eligible','Reference not viewed'],
    ['progress:revealed','Reference viewed']
  ];
  function lifecycleLabel(value){
    const found=LIFECYCLE_OPTIONS.find(o=>o[0]===value);
    return found?found[1]:'';
  }
  function topicLabels(topics){
    const count={};
    (topics||[]).forEach(t=>{count[t.label]=(count[t.label]||0)+1;});
    return (topics||[]).map(t=>({id:t.id,text:count[t.label]>1?t.label+' ('+t.id+')':t.label}));
  }
  function familyLabel(family,topics){
    const text=String(family||'');
    const m=/^classic_topic_(\d+)$/.exec(text);
    if(m){
      const topic=(topics||[]).find(t=>String(t.id)===m[1]);
      if(topic&&topic.label)return topic.label;
    }
    const plain=text.replace(/^classic_/,'').replace(/[_-]+/g,' ').trim();
    return plain?plain.charAt(0).toUpperCase()+plain.slice(1):text;
  }
  function levelPips(level){
    const n=Number(level);
    return LEVELS.map(x=>Number.isFinite(n)&&x<=n);
  }
  function clampSplit(value){
    const n=Number(value);
    if(!Number.isFinite(n))return 50;
    return Math.min(75,Math.max(25,Math.round(n)));
  }
  // Split highlighted and plain parts of a label for the command palette.
  function highlightParts(text,query){
    const source=String(text==null?'':text);
    const q=String(query||'').trim().toLowerCase();
    if(!q)return [{text:source,match:false}];
    const lower=source.toLowerCase();
    const parts=[];
    let from=0,at;
    while((at=lower.indexOf(q,from))>=0){
      if(at>from)parts.push({text:source.slice(from,at),match:false});
      parts.push({text:source.slice(at,at+q.length),match:true});
      from=at+q.length;
    }
    if(from<source.length)parts.push({text:source.slice(from),match:false});
    return parts.length?parts:[{text:source,match:false}];
  }
  function rememberRecent(list,id,title,max=6){
    const clean=(Array.isArray(list)?list:[]).filter(x=>x&&typeof x.id==='string'&&x.id!==id);
    clean.unshift({id,title:String(title||'')});
    return clean.slice(0,max);
  }

  /* ---- Overview aggregation (numbers come only from the problem list) --- */
  function progressSummary(problems){
    const levels=LEVELS.map(level=>({level,released:0,attempted:0,passed:0}));
    const topics=new Map();
    for(const p of problems||[]){
      const lv=levels.find(x=>x.level===Number(p.difficulty));
      const key=p.topic_id==null?'none':String(p.topic_id);
      if(!topics.has(key))topics.set(key,{id:p.topic_id,label:p.topic_label||'Foundational reasoning',released:0,attempted:0,passed:0});
      const t=topics.get(key);
      for(const bucket of [lv,t]){
        if(!bucket)continue;
        bucket.released+=1;
        if(p.has_attempt)bucket.attempted+=1;
        if(p.passed)bucket.passed+=1;
      }
    }
    return {total:(problems||[]).length,levels,topics:[...topics.values()].sort((a,b)=>String(a.label).localeCompare(String(b.label)))};
  }

  /* ---- Student-visible statement as Markdown ----------------------------- */
  function fenceFor(text){
    const runs=String(text).match(/`+/g)||[];
    return '`'.repeat(Math.max(2,...runs.map(r=>r.length))+1);
  }
  function statementMarkdown(detail){
    const d=(detail&&detail.presentation_data)||{};
    const out=['# '+String((detail&&(detail.title||detail.id))||'Problem'),''];
    out.push(String(d.description||(detail&&detail.statement)||'').trim(),'');
    if(String(d.input_format||'').trim())out.push('## Input Format','',String(d.input_format).trim(),'');
    if(String(d.output_format||'').trim())out.push('## Output Format','',String(d.output_format).trim(),'');
    if(Array.isArray(d.constraints)&&d.constraints.length){
      out.push('## Constraints','');
      d.constraints.forEach(c=>out.push('- '+String(c).trim()));
      out.push('');
    }
    (Array.isArray(d.samples)?d.samples:[]).forEach((s,i)=>{
      out.push('## Sample '+(i+1),'');
      for(const [label,value] of [['Input',s.input],['Output',s.output]]){
        const text=String(value==null?'':value);
        const fence=fenceFor(text);
        out.push('**'+label+'**','',fence+'text',text,fence,'');
      }
    });
    return out.join('\n').replace(/\n{3,}/g,'\n\n').trimEnd()+'\n';
  }

  /* ---- Draft export ------------------------------------------------------ */
  const SECTION_LABELS={problem:'P1 · Problem specification',procedure:'P2 · Proposed algorithm',correctness:'C · Correctness proof',complexity:'K · Complexity analysis'};
  function draftMarkdown(id,title,draft,updatedAt){
    const parts=['# '+id+' — '+(title||'Untitled problem'),'',
      '_Draft exported from ARDS Studio. Not graded.'+(updatedAt?' Last saved '+updatedAt+'.':'')+'_',''];
    for(const s of SECTIONS)parts.push('## '+SECTION_LABELS[s],'',String((draft&&draft[s])||'')||'_(empty)_','');
    return parts.join('\n');
  }
  function draftsJson(entries){
    return JSON.stringify({exported_from:'ARDS Studio',graded:false,drafts:entries.map(e=>({
      id:e.id,title:e.title||'',updated_at:e.updated_at||null,
      sections:Object.fromEntries(SECTIONS.map(s=>[s,String((e.draft&&e.draft[s])||'')]))
    }))},null,2);
  }

  // Browse existing released problems only. This is not a new RACG draw.
  function pickNextProblem(problems,current,random=Math.random){
    const others=(problems||[]).filter(p=>p.id!==current.id&&!p.reference_revealed);
    if(!others.length)return null;
    const continuation=others.filter(p=>p.continuation_of===current.id);
    const sameTopic=others.filter(p=>current.topic_id!=null&&p.topic_id===current.topic_id);
    const choices=[[continuation,30],[sameTopic,40],[others,30]].filter(([pool])=>pool.length);
    const total=choices.reduce((n,[,weight])=>n+weight,0);
    let roll=random()*total;
    let pool=choices[choices.length-1][0];
    for(const [candidate,weight] of choices){if(roll<weight){pool=candidate;break;}roll-=weight;}
    return pool[Math.min(pool.length-1,Math.floor(random()*pool.length))];
  }

  const api={pickNextProblem,SECTIONS,LEVELS,parseRoute,hashFor,lifecycleParam,LIFECYCLE_OPTIONS,lifecycleLabel,topicLabels,familyLabel,
    levelPips,clampSplit,highlightParts,rememberRecent,progressSummary,fenceFor,statementMarkdown,draftMarkdown,draftsJson,SECTION_LABELS};
  if(typeof window!=='undefined')window.ARDSLogic=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})();
