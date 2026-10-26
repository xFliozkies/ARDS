"""Local Java judge. Student processes see only a temporary work directory."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time

LOCK = threading.Lock()


def execute(work, command, stdin='', timeout=5):
    # No host home, archive, network, or writable system paths inside the sandbox.
    command=[str(Path(shutil.which(command[0])).resolve()), *command[1:]]
    config=[]
    for path in Path('/etc').glob('java-*'):
        if path.is_dir(): config.extend(['--ro-bind',str(path),str(path)])
    args = ['bwrap', '--unshare-all', '--die-with-parent', '--new-session',
            '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
            '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
            '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
            '--bind', str(work), '/work', '--chdir', '/work',
            '--clearenv', '--setenv', 'PATH', '/usr/bin', '--setenv', 'HOME', '/work',
            *config, '--', '/bin/bash', '-c', 'ulimit -t 10; ulimit -f 256; ulimit -u 128; exec "$@"', 'judge', *command]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=out, stderr=err, start_new_session=True)
        try:
            p.communicate(stdin.encode(), timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            return 'Time limit exceeded', '', ''
        out.seek(0); err.seek(0)
        stdout=out.read(65537); stderr=err.read(65537)
        if len(stdout)>65536 or len(stderr)>65536:
            return 'Output limit exceeded', '', ''
        return ('OK' if p.returncode == 0 else 'Runtime error'), stdout.decode(errors='replace'), stderr.decode(errors='replace')


def flatten(value):
    if isinstance(value, dict):
        return ' '.join(flatten(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return ' '.join(flatten(v) for v in value)
    return str(value)


def stdin_adapter(module, samples):
    """Infer only layouts exactly matching every official sample; validate each case."""
    decoded=[module.decode_stdin(s["input"]) for s in samples]
    first=decoded[0]
    import re
    from judge_stdin import encode
    match=re.search(r'RACG-(\d+)',getattr(module,'__file__',''))
    if match:
        number=int(match[1])
        try:
            if all(encode(number,case).split()==sample['input'].split() for case,sample in zip(decoded,samples)):
                return lambda case: encode(number,case)
        except (KeyError,IndexError,TypeError):
            pass
    if isinstance(first,str) and all(case.split()==sample["input"].split() for case,sample in zip(decoded,samples)):
        return lambda case: case
    def at(case,path):
        for key in path: case=case[key]
        return case
    roots=[((),)]
    if isinstance(first,dict): roots=[tuple((k,) for k in first)]
    elif isinstance(first,list) and len(first)<=6:
        roots.append(tuple((i,) for i in range(len(first))))
    def tokens(case,expr):
        kind,path=expr
        value=at(case,path)
        return str(len(value)).split() if kind=="len" else flatten(value).split()
    target=samples[0]["input"].split()
    for groups in roots:
        lengths=[("len",())] if isinstance(first,(list,dict,str)) else []
        lengths += [("len",p) for p in groups if isinstance(at(first,p),(list,str))]
        lengths=list(dict.fromkeys(lengths))
        def search(pos,remaining,plan,extra):
            if pos==len(target) and not remaining:
                yield plan; return
            if len(plan)>len(groups)+3: return
            options=[("value",p) for p in remaining]+(lengths if extra<3 else [])
            for expr in options:
                chunk=tokens(first,expr)
                if not chunk or target[pos:pos+len(chunk)]!=chunk: continue
                yield from search(pos+len(chunk),tuple(p for p in remaining if p!=expr[1]) if expr[0]=="value" else remaining,plan+[expr],extra+(expr[0]=="len"))
        for index,plan in enumerate(search(0,groups,[],0)):
            if index>200: break
            if any([t for expr in plan for t in tokens(case,expr)]!=sample["input"].split() for case,sample in zip(decoded,samples)):
                continue
            def render(case,plan=plan):
                header=[];blocks=[]
                for kind,path in plan:
                    value=at(case,path)
                    if kind=="len": header.append(str(len(value)))
                    elif isinstance(value,(list,dict)):
                        if header: blocks.append(" ".join(header));header=[]
                        items=list(value.values()) if isinstance(value,dict) else value
                        if items and isinstance(items[0],(list,dict)):
                            blocks.extend(flatten(row) for row in items)
                        else: blocks.append(flatten(items))
                    else: header.append(str(value))
                if header: blocks.append(" ".join(header))
                return "\n".join(blocks)+"\n"
            try:
                if all(json.dumps(module.decode_stdin(render(case)),sort_keys=True)==json.dumps(case,sort_keys=True) for case in decoded):
                    return render
            except (ValueError,IndexError,StopIteration,AssertionError,TypeError):
                continue
    raise ValueError("Submission unavailable: this problem needs a reviewed stdin test adapter.")


def test_suite(con, challenge, package, root):
    # Prefer exact stored hash: canonical fingerprint formatting is owned by ards2.
    import ards2
    digest=ards2.digest(package)
    review=con.execute('SELECT * FROM independent_reviews WHERE challenge_id=? AND package_hash=? AND outcome="passed" ORDER BY id DESC LIMIT 1', (challenge['id'],digest)).fetchone()
    if not review:
        raise ValueError('Submission unavailable: no matching reviewed test suite for this problem version.')
    path=(root/review['module_path']).resolve()
    if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=review['module_sha256']:
        raise ValueError('Submission unavailable: test suite integrity check failed.')
    spec=importlib.util.spec_from_file_location('judge_reviewer',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import ards_review
    cases=module.edge_cases()+module.generate_cases(ards_review.SEED, ards_review.GENERATED)
    tests=list(package['samples'])
    adapter=stdin_adapter(module,tests)
    for case in cases:
        raw=adapter(case)
        # Never guess an encoding: require an exact decode round trip.
        try:
            matches=json.dumps(module.decode_stdin(raw),sort_keys=True)==json.dumps(case,sort_keys=True)
        except (ValueError,IndexError,StopIteration,AssertionError,TypeError):
            matches=False
        if not matches:
            raise ValueError('Submission unavailable: this problem needs a reviewed stdin test adapter. You can still run samples or custom input.')
        tests.append({'input':raw,'output':module.encode_stdout(module.oracle(case))})
    if len(tests)<=len(package['samples']):
        raise ValueError('Submission unavailable: hidden tests are missing.')
    return tests


def judge(source, tests, private=False):
    if not all(shutil.which(x) for x in ('java','javac','bwrap')):
        raise ValueError('Install a JDK and bubblewrap to enable Java execution.')
    if not LOCK.acquire(blocking=False):
        raise ValueError('The Java runner is busy. Please try again shortly.')
    try:
        with tempfile.TemporaryDirectory(prefix='ards-java-') as directory:
            work=Path(directory); (work/'Main.java').write_text(source)
            status, out, err=execute(work,['javac','-J-Xmx256m','-encoding','UTF-8','-proc:none','Main.java'],timeout=15)
            if status!='OK':
                return {'verdict':'Compilation error' if status=='Runtime error' else status,'details':err or out}
            results=[]
            passed=0
            deadline=time.monotonic()+60
            for number, test in enumerate(tests, 1):
                if time.monotonic()>deadline:
                    return {"verdict":"Judge time budget exceeded", "passed":passed,"total":len(tests)}
                status,out,err=execute(work,['java','-Xmx256m','-XX:ActiveProcessorCount=2','-cp','/work','Main'],test['input'])
                if status=='OK' and 'output' in test and out.split()!=test['output'].split():
                    status='Wrong answer'
                if not private:
                    results.append({'verdict':status,'stdout':out,'stderr':err,'expected':test.get('output')})
                if status!='OK':
                    return {'verdict':status,'passed':passed,'total':len(tests),'results':results,
                            'failure':{'number':number,'verdict':status,'input':test['input'],
                                       'stdout':out,'stderr':err,'expected':test.get('output')}}
                passed += 1
            return {'verdict':'Accepted' if private else 'Run complete','passed':len(tests),'total':len(tests),'results':results}
    finally:
        LOCK.release()
