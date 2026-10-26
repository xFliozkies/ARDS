"""Java judge checks use disposable fixtures and synthetic programs only."""
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
import java_judge
import test_website as fixtures
studio=fixtures.studio


class JavaFlowTests(unittest.TestCase):
    setUp=fixtures.WebsiteTests.setUp
    request=fixtures.WebsiteTests.request

    def test_timer_run_failure_acceptance_and_saved_source(self):
        problem='RACG-0003'
        session=studio.java_action(problem,{'action':'load'})
        self.assertIsNone(session['started_at'])
        started=studio.java_action(problem,{'action':'start'})['started_at']
        with patch.object(java_judge,'judge',return_value={'verdict':'Run complete'}):
            result=studio.java_action(problem,{'action':'run','source':'sample source'})
        self.assertIsNone(result['accepted_at'])
        with patch.object(java_judge,'test_suite',return_value=[{'input':'','output':'42'}]), patch.object(studio.ards2,'load_package',return_value=(None,{})), patch.object(java_judge,'judge',return_value={'verdict':'Wrong answer'}):
            result=studio.java_action(problem,{'action':'submit','source':'wrong source'})
        self.assertIsNone(result['accepted_at'])
        with patch.object(java_judge,'test_suite',return_value=[{'input':'','output':'42'}]), patch.object(studio.ards2,'load_package',return_value=(None,{})), patch.object(java_judge,'judge',return_value={'verdict':'Accepted'}):
            result=studio.java_action(problem,{'action':'submit','source':'accepted source'})
        self.assertIsNotNone(result['accepted_at'])
        session=studio.java_action(problem,{'action':'start'})
        self.assertEqual(started,session['started_at'])
        self.assertEqual(result['accepted_at'],session['accepted_at'])
        self.assertEqual(session['source'],'accepted source')
        self.assertEqual(session['last_submission']['verdict'],'Accepted')
        with sqlite3.connect(studio.WEB_DB) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM java_submissions').fetchone()[0],2)
        with studio.database() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)

    def test_pause_resume_stop_elapsed_and_reload(self):
        problem='RACG-0003'
        def action(name,stamp):
            with patch.object(studio,'now',return_value='2026-10-24T00:'+stamp+'+00:00'):
                return studio.java_action(problem,{'action':name})
        action('start','00:00')
        action('pause','00:10')
        self.assertIsNotNone(studio.java_action(problem,{'action':'load'})['paused_at'])
        result=action('resume','00:40')
        self.assertEqual(result['paused_seconds'],30)
        self.assertIsNone(result['paused_at'])
        action('pause','00:50')
        result=action('stop','01:20')
        self.assertEqual(result['stopped_at'],'2026-10-24T00:00:50+00:00')
        self.assertEqual(action('resume','01:30')['stopped_at'],result['stopped_at'])
        self.assertEqual(action('start','01:40')['started_at'],'2026-10-24T00:00:00+00:00')

    def test_route_security_validation_and_private_challenge(self):
        for asset in ('/java-editor.js','/java-editor.css'):
            self.assertEqual(self.request(asset)[0],200)
        self.assertEqual(self.request('/api/java/RACG-0003',{'action':'load'},token=False)[0],403)
        self.assertEqual(self.request('/api/java/UNKNOWN',{'action':'load'})[0],404)
        self.assertEqual(self.request('/api/java/RACG-0003',{'action':'save','source':42})[0],400)
        self.assertEqual(self.request('/api/java/RACG-0003',{'action':'bad'})[0],400)
        status,raw,_=self.request('/api/java/RACG-0003',{'action':'save','source':'my Java draft'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['source'],'my Java draft')

    @unittest.skipUnless(all(shutil.which(x) for x in ('java','javac','bwrap')),'JDK and bubblewrap required')
    def test_real_hidden_suite_and_evidence_binding(self):
        import hashlib
        module=self.temp/'reviewer.py'
        module.write_text("""def decode_stdin(raw): return raw
def encode_stdout(v): return str(v)+'\\n'
def edge_cases(): return ['3\\n','4\\n','5\\n']
def generate_cases(seed,count): return [str(i+10)+'\\n' for i in range(count)]
def oracle(raw): return int(raw)+1
""")
        package={'samples':[{'input':'1\n','output':'2\n'},{'input':'2\n','output':'3\n'}]}
        package_hash=studio.ards2.digest(package)
        with sqlite3.connect(studio.DB) as con:
            ch=con.execute('SELECT id FROM challenges WHERE external_id="RACG-0003"').fetchone()[0]
            con.execute("""INSERT INTO independent_reviews(challenge_id,package_hash,module_path,module_sha256,
                report_path,report_sha256,outcome,tests_run,evidence_json,created_at)
                VALUES (?,?,?,?,?,?,'passed',185,'{}',?)""",
                (ch,package_hash,'reviewer.py',hashlib.sha256(module.read_bytes()).hexdigest(),'report.json','0'*64,studio.now()))
        source='public class Main {public static void main(String[] args) {java.util.Scanner s=new java.util.Scanner(System.in);System.out.println(s.nextInt()+1);}}'
        studio.java_action('RACG-0003',{'action':'start'})
        with patch.object(studio,'ROOT',self.temp), patch.object(studio.ards2,'load_package',return_value=(None,package)):
            result=studio.java_action('RACG-0003',{'action':'submit','source':source})
            self.assertEqual(result['verdict'],'Accepted')
            self.assertEqual(result['passed'],185)
            self.assertIsNotNone(result['accepted_at'])
            self.assertEqual(result['package_hash'],package_hash)
            module.write_text(module.read_text()+'# modified\n')
            with self.assertRaisesRegex(ValueError,'integrity'):
                studio.java_action('RACG-0003',{'action':'submit','source':source})

    def test_first_failure_number_after_passes(self):
        tests=[{'input':str(i),'output':'yes'} for i in range(5)]
        with patch.object(java_judge.shutil,'which',return_value='/bin/true'), patch.object(java_judge,'execute',side_effect=[('OK','','')]+[('OK','yes','')]*3+[('OK','no','diagnostic')]):
            result=java_judge.judge('source',tests,private=True)
        self.assertEqual(result['passed'],3)
        self.assertEqual(result['total'],5)
        self.assertEqual(result['failure'],{'number':4,'verdict':'Wrong answer','input':'3','stdout':'no','stderr':'diagnostic','expected':'yes'})
        self.assertEqual(result['results'],[])

    def test_sample_derived_adapter_requires_roundtrip(self):
        module=types.SimpleNamespace(decode_stdin=lambda raw:{'a':list(map(int,raw.split()))[2:], 't':int(raw.split()[1])})
        adapter=java_judge.stdin_adapter(module,[{'input':'3 7\n1 2 4\n','output':'x'}])
        case={'a':[8,9], 't':17}
        self.assertEqual(module.decode_stdin(adapter(case)),case)
        self.assertEqual(adapter(case).split(),['2','17','8','9'])


@unittest.skipUnless(all(shutil.which(x) for x in ('java','javac','bwrap')),'JDK and bubblewrap required')
class JavaSandboxTests(unittest.TestCase):
    def test_compile_run_and_submission_failure_details(self):
        code='public class Main { public static void main(String[] a) {System.out.println("PRIVATE_INPUT_SENTINEL");} }'
        result=java_judge.judge(code,[{'input':'PRIVATE_INPUT_SENTINEL','output':'expected'}],private=True)
        self.assertEqual(result['verdict'],'Wrong answer')
        self.assertEqual(result['failure'],{'number':1,'verdict':'Wrong answer','input':'PRIVATE_INPUT_SENTINEL','stdout':'PRIVATE_INPUT_SENTINEL\n','stderr':'','expected':'expected'})
        self.assertEqual(result['passed'],0)
        result=java_judge.judge('public class Main { broken }',[{'input':''}])
        self.assertEqual(result['verdict'],'Compilation error')

    def test_archive_and_network_are_unavailable(self):
        code='''public class Main {public static void main(String[] args) throws Exception {
            System.out.println(java.nio.file.Files.exists(java.nio.file.Path.of("/home/shuani/MyFiles/AI/ARDS/data/ards.db")));
            try {new java.net.Socket("127.0.0.1",8765);System.out.println("connected");}
            catch(Exception e){System.out.println("blocked");}
        }}'''
        result=java_judge.judge(code,[{'input':'','output':'false blocked'}],private=True)
        self.assertEqual(result['verdict'],'Accepted')

    def test_process_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            status,_,_=java_judge.execute(Path(folder),['/usr/bin/sleep','10'],timeout=.1)
        self.assertEqual(status,'Time limit exceeded')
