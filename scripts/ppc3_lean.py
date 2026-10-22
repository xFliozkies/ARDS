#!/usr/bin/env python3
"""Pinned Lean statements, isolated compilation, and bundled kernel replay.

Only hash-approved local sources are executed. All compilation and replay uses
an offline bubblewrap sandbox, bounded workers, 64 MiB thread stacks, a 4 GiB
address-space cap, and unique evidence directories. No Python refinement or
external multi-kernel verification is inferred from these example theorems.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import resource
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
import strict_json

ROOT=Path(__file__).resolve().parents[1]
TRUSTED=ROOT/'references/PPC3Examples.lean'
EXPECTED=ROOT/'references/PPC3Expected.lean'
RULES=ROOT/'references/PPC3RuleSoundness.lean'
MANIFEST=ROOT/'references/ppc3_lean_manifest.json'
ARTIFACT_DIR=ROOT/'data/validation/lean/runs'
THEOREMS={
    'PPC3.cakeCost_correct':frozenset({'propext'}),
    'PPC3.conjunction_swap':frozenset(),
    'PPC3.implication_compose':frozenset(),
}
RULE_THEOREMS={'PPCAudit.satisfies_cons':frozenset(),
               'PPCAudit.inference_soundness':frozenset()}


def _tool(name):
    found=shutil.which(name)
    local=Path.home()/'.elan/bin'/name
    return found or (str(local) if local.exists() else None)


def _execute(argv, env=None, timeout=60, cwd=ROOT):
    def limits():
        resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        resource.setrlimit(resource.RLIMIT_CPU,(timeout+5,timeout+5))
    with subprocess.Popen(argv,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,preexec_fn=limits,start_new_session=True) as process:
        try:
            stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        return subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)


def _axioms(output, theorems=None):
    reports={}
    for name,expected in (THEOREMS if theorems is None else theorems).items():
        matches=re.findall(r"^'"+re.escape(name)+r"' (does not depend on any axioms|depends on axioms: \[([^\]]*)\])\s*$",
                           output,flags=re.MULTILINE)
        if len(matches)!=1:
            raise ValueError('Missing or duplicated Lean axiom report: '+name)
        actual=frozenset(x.strip() for x in matches[0][1].split(',') if x.strip())
        if actual!=expected:
            raise ValueError('Unapproved axioms for '+name+': '+str(sorted(actual)))
        reports[name]=sorted(actual)
    if any(s in output for s in ('sorryAx','unsound','_native','Lean.trustCompiler')):
        raise ValueError('Unexpected proof hole or compiler-trust axiom')
    return reports


def _approved_sources():
    manifest=strict_json.load(MANIFEST)
    expected_names={path.name for path in (TRUSTED,EXPECTED,RULES)}
    if (not isinstance(manifest,dict) or manifest.get('schema')!='ppc3-approved-lean-v1' or
            not isinstance(manifest.get('sources'),dict) or set(manifest['sources'])!=expected_names or
            any(not isinstance(h,str) or re.fullmatch('[0-9a-f]{64}',h) is None for h in manifest['sources'].values()) or
            not isinstance(manifest.get('lean_version'),str) or not isinstance(manifest.get('lake_version'),str)):
        raise ValueError('Invalid approved Lean manifest')
    sources={}
    for path in (TRUSTED,EXPECTED,RULES):
        with path.open('rb') as stream:
            blob=stream.read(1024*1024+1)
        if len(blob)>1024*1024:
            raise strict_json.ResourceLimitError('Approved Lean source exceeds byte budget')
        if hashlib.sha256(blob).hexdigest()!=manifest['sources'].get(path.name):
            raise ValueError('Unreviewed Lean source: '+str(path))
        sources[path.name]=blob
    return manifest,sources


def _sandbox(bwrap,prefix,work,argv):
    return [bwrap,'--ro-bind','/','/','--tmpfs','/home','--tmpfs','/root',
            '--tmpfs','/tmp','--tmpfs','/run','--tmpfs','/var','--dev','/dev','--proc','/proc',
            '--clearenv','--ro-bind',str(prefix),str(prefix),'--bind',str(work),str(work),
            '--setenv','PATH',str(prefix/'bin')+':/usr/bin:/bin',
            '--setenv','LEAN_PATH',str(work),'--setenv','LEAN_STACK_SIZE_KB','65536',
            '--setenv','LEAN_NUM_THREADS','2','--unshare-all','--die-with-parent',
            '--new-session','--chdir',str(work),'--',*map(str,argv)]


def check_examples(*, fresh=False):
    commands=[]
    work=None
    def finish(result):
        result['commands']=commands
        if work is not None:
            result['evidence_directory']=str(work)
            with (work/'result.json').open('x',encoding='utf8') as stream:
                json.dump(result,stream,indent=2)
        return result
    try:
        manifest,sources=_approved_sources()  # fail before executing any changed source
        lean,bwrap=_tool('lean'),shutil.which('bwrap')
        if not lean or not bwrap:
            return finish({'status':'unavailable','lean_kernel_checked':False,
                           'reason':'Lean and bubblewrap isolation are required'})
        env=os.environ.copy()
        for key in list(env):
            if key.startswith(('LEAN_','LAKE_')):
                env.pop(key)
        env.update(LEAN_STACK_SIZE_KB='65536',LEAN_NUM_THREADS='2')
        version=_execute([lean,'--version'],env=env,timeout=15)
        prefix_result=_execute([lean,'--print-prefix'],env=env,timeout=15)
        if version.returncode or prefix_result.returncode or not re.search(
                r'version '+re.escape(manifest['lean_version'])+r',',version.stdout):
            raise ValueError('Cannot identify the approved Lean toolchain')
        prefix=Path(prefix_result.stdout.strip()).resolve()
        lean=prefix/'bin/lean';checker=prefix/'bin/leanchecker';lake=prefix/'bin/lake'
        if not checker.is_file():
            raise ValueError('Bundled checker missing from the identified Lean toolchain')
        lake_ver=_execute([str(lake),'--version'],env=env,timeout=15) if lake.is_file() else None
        if lake_ver and (lake_ver.returncode or not lake_ver.stdout.startswith('Lake version '+manifest['lake_version'])):
            raise ValueError('Unexpected Lake toolchain version')
        ARTIFACT_DIR.mkdir(parents=True,exist_ok=True)
        work=Path(tempfile.mkdtemp(prefix='run-',dir=ARTIFACT_DIR)).resolve()
        for name,blob in sources.items():
            with (work/name).open('xb') as stream:
                stream.write(blob)
        def invoke(args,timeout=60):
            argv=_sandbox(bwrap,prefix,work,args)
            result=_execute(argv,env=env,timeout=timeout,cwd=work)
            commands.append({'argv':argv,'exit_code':result.returncode,
                             'stdout':result.stdout,'stderr':result.stderr})
            if result.returncode:
                raise ValueError('Isolated Lean operation failed: '+(result.stdout+'\n'+result.stderr)[-5000:])
            return result
        axioms={}
        for module,expected in (('PPC3Examples',THEOREMS),('PPC3RuleSoundness',RULE_THEOREMS),('PPC3Expected',None)):
            result=invoke([lean,'-j2','-o',work/(module+'.olean'),work/(module+'.lean')])
            if expected is not None:
                axioms.update(_axioms(result.stdout+'\n'+result.stderr,expected))
        if fresh:
            invoke([checker,'--fresh','PPC3Expected'],timeout=180)
        else:
            for module in ('PPC3Examples','PPC3RuleSoundness','PPC3Expected'):
                invoke([checker,module])
        # Do not bind evidence to source bytes changed after review/copy.
        if _approved_sources()[1]!=sources:
            raise ValueError('Lean source changed during verification')
        return finish({'status':'lean_example_checked','lean_kernel_checked':True,
            'checker':'leanchecker (bundled kernel, no external checker claimed)',
            'checker_mode':'fresh replay including imports' if fresh else 'module replay from imports',
            'sandbox':'bubblewrap, offline, private home/tmp, reviewed inputs only',
            'resource_limits':{'address_space_gib':4,'thread_stack_kib':65536,'workers':2},
            'lean_version':version.stdout.strip(),'lake_version':lake_ver.stdout.strip() if lake_ver else None,
            'source_sha256':manifest['sources']['PPC3Examples.lean'],
            'artifact_sha256':hashlib.sha256((work/'PPC3Examples.olean').read_bytes()).hexdigest(),
            'source_hashes':manifest['sources'],
            'tool_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (lean,checker)},
            'axiom_dependencies':axioms,'statements_checked':'PPC3Expected.lean type ascriptions and pinned definitions',
            'proof_file':str(TRUSTED),
            'scope':'Three named examples and the abstract rule-soundness theorem/helper only. Python checker and program refinement remain unproved.'})
    except (subprocess.TimeoutExpired,strict_json.ResourceLimitError) as exc:
        return finish({'status':'resource_limit','lean_kernel_checked':False,'reason':str(exc)})
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        return finish({'status':'rejected','lean_kernel_checked':False,'reason':str(exc)})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh',action='store_true',help='Separate replay of the full import closure (bounded to 180 seconds)')
    args=parser.parse_args()
    result=check_examples(fresh=args.fresh)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    raise SystemExit(0 if result['lean_kernel_checked'] else 1)
