"""ARDS Studio integration and persistence regression tests.
Tests operate on an isolated SQLite backup, never the production ARDS archive.
"""
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'website'))
import server as studio


class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.temp = Path(self.folder.name)
        db=self.temp/'ards.db'
        # A deterministic, synthetic problem in a disposable DB. Never
        # depend on, import, or copy the learner's active archive.
        import memory
        import hashlib
        with memory.connect(db) as con:
            statement="# Synthetic Lantern Coverage Test\n\nGiven $N$ stall coordinates and radius $R$, compute the **minimum** number of lanterns covering all stalls.\n\n## Input\n\n- The first line contains $N$ and $R$.\n- The second line contains $N$ integer coordinates.\n\n## Constraints\n\n- $1 \\le N \\le 200000$\n- $0 \\le R \\le 10^9$\n- $0 \\le X_i \\le 10^9$\n- Lantern coordinates must be nonnegative.\n- Duplicate stalls are allowed.\n\n## Output\n\nReturn the **minimum** number of lanterns covering all stalls.\n\n## Examples\n\n**Example 1**\nInput:\n```text\n6 2\n1 2 4 7 8 12\n```\nOutput:\n```text\n3\n```\n\n**Example 2**\nInput:\n```text\n5 0\n5 1 1 7 5\n```\nOutput:\n```text\n3\n```\n\n**Example 3**\nInput:\n```text\n5 3\n0 3 6 9 12\n```\nOutput:\n```text\n2\n```\n"
            con.execute("""
                INSERT INTO challenges(
                    external_id,session_type,status,source,topic_id,topic_label,
                    difficulty,title,statement,statement_hash,presentation,
                    created_at,presented_at
                ) VALUES (?,'RACG','presented','synthetic_test_fixture',
                          71,'Greedy interval coverage',2,?,?,?,'story',?,?)
            """,('RACG-0003','Synthetic Lantern Coverage',
                 statement,hashlib.sha256(statement.strip().encode()).hexdigest(),
                 '2020-01-01','2020-01-01'))
            con.commit()
        self.one=patch.object(studio,'DB',db)
        self.two=patch.object(studio,'WEB_DB',self.temp/'studio.db')
        self.one.start();self.two.start()
        self.addCleanup(self.one.stop);self.addCleanup(self.two.stop)
        studio.initialize_site()
        self.httpd = ThreadingHTTPServer(('127.0.0.1',0),studio.Handler)
        thread=threading.Thread(target=self.httpd.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base=f'http://127.0.0.1:{self.httpd.server_port}'

    def request(self,path,body=None,token=True):
        payload=json.dumps(body).encode() if body is not None else None
        headers={'Accept':'application/json'}
        if payload is not None:
            headers['Content-Type']='application/json'
            if token:headers['X-ARDS-Session']=studio.TOKEN
        req=urllib.request.Request(self.base+path,data=payload,headers=headers,
                                   method='POST' if payload is not None else 'GET')
        try:
            with urllib.request.urlopen(req,timeout=5) as response:
                return response.status,response.read(),response.headers
        except urllib.error.HTTPError as err:
            return err.code,err.read(),err.headers

    def test_student_reviews_are_token_protected_allowlisted_and_undetermined(self):
        import memory
        import ppc_assess
        with memory.connect(studio.DB) as con:
            memory.add_attempt(con,'RACG-0003','Student original submission',stage='first',provenance='verbatim')
            attempt=con.execute('SELECT MAX(id) FROM attempts').fetchone()[0]
            report={"reviewer_kind":"human","reviewer":"Fixture reviewer","verdict":"undetermined",
                    "proof_assurance":"reasoned_review","teacher_ppc":"PRIVATE_SENTINEL",
                    "sections":{key:{"status":"uncertain","finding":"The submitted reasoning leaves this specific boundary obligation unresolved.",
                                    "evidence":"The student's quantified claim has no argument for the empty boundary in the domain.",
                                    "uncertainty":"Needs further review.","hidden_tests":"PRIVATE_SENTINEL"} for key in studio.SECTIONS}}
            ppc_assess.record(con,attempt,report)
        self.assertEqual(self.request('/api/reviews/RACG-0003')[0],403)
        request=urllib.request.Request(self.base+'/api/reviews/RACG-0003',headers={'X-ARDS-Session':studio.TOKEN})
        with urllib.request.urlopen(request) as response:
            raw=response.read()
        self.assertNotIn(b'PRIVATE_SENTINEL',raw)
        review=json.loads(raw)['reviews'][0]
        self.assertEqual(review['verdict'],'undetermined')
        self.assertEqual(set(review['sections']),set(studio.SECTIONS))
        self.assertEqual(review['sections']['correctness']['uncertainty'],'Needs further review.')
        request=urllib.request.Request(self.base+'/api/reviews/UNRELEASED',headers={'X-ARDS-Session':studio.TOKEN})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code,404)

    def test_latest_undetermined_review_does_not_leave_a_stale_pass(self):
        import memory
        with memory.connect(studio.DB) as con:
            memory.add_attempt(con,'RACG-0003','Original student reasoning',stage='first',provenance='verbatim')
            attempt=con.execute('SELECT MAX(id) FROM attempts').fetchone()[0]
            memory.add_assessment(con,attempt,reviewer='Fixture reviewer',correct=True,evidence='Initial synthetic review')
            memory.add_assessment(con,attempt,reviewer='Fixture correction',correct=None,evidence='A proof gap remains unresolved')
        code,raw,_=self.request('/api/problems')
        self.assertEqual(code,200)
        self.assertFalse(json.loads(raw)['problems'][0]['passed'])
        code,raw,_=self.request('/api/problems?progress=passed')
        self.assertEqual(json.loads(raw)['problems'],[])
        code,raw,_=self.request('/api/problems/RACG-0003')
        self.assertFalse(json.loads(raw)['has_passing_assessment'])

    def test_continuation_navigation_uses_recorded_order_and_hides_private_parent(self):
        import memory
        with memory.connect(studio.DB) as con:
            original=con.execute("SELECT * FROM challenges WHERE external_id='RACG-0003'").fetchone()
            for ident,status,continuation,statement in [
                ('UI-CONT','presented',1,original['statement']),
                ('UI-PRIVATE-PARENT','selected',0,None),
                ('UI-AFTER-PRIVATE','presented',1,original['statement'])]:
                con.execute("""INSERT INTO challenges(external_id,session_type,status,source,title,statement,statement_hash,difficulty,topic_id,topic_label,continuation,created_at)
                    VALUES (?,'RACG',?,'synthetic_test_fixture',?,?,?,?,?,?,?,?)""",
                    (ident,status,'Synthetic navigation',statement,original['statement_hash'],2,71,'Synthetic topic',continuation,'2020-01-01'))
        code,raw,_=self.request('/api/problems')
        self.assertEqual(code,200)
        rows={p['id']:p for p in json.loads(raw)['problems']}
        self.assertEqual(rows['UI-CONT']['continuation_of'],'RACG-0003')
        self.assertIsNone(rows['UI-AFTER-PRIVATE']['continuation_of'])
        self.assertNotIn(b'UI-PRIVATE-PARENT',raw)

    def test_editor_script_is_served_locally_and_loaded_by_the_page(self):
        status,body,headers=self.request('/editor.js')
        self.assertEqual(status,200)
        self.assertIn('javascript',headers.get('Content-Type',''))
        self.assertIn("script-src 'self'",headers.get('Content-Security-Policy',''))
        source=body.decode()
        self.assertNotIn('http://',source)
        self.assertNotIn('https://',source)
        self.assertIn('window.ARDSEditor',source)
        _,page,_=self.request('/')
        self.assertIn('src="/editor.js"',page.decode())

    def test_registered_unverified_batch_is_hidden_from_learner(self):
        import memory,ards2,ards_batch
        from test_ards2 import body
        from test_ards_batch import as_text_stdin

        class Draw:
            def __init__(self): self.n=iter([98,0,55,23,0])  # weighted Y=56 -> Level 3
            def __call__(self,limit):
                value=next(self.n)
                if not 0<=value<limit: raise AssertionError('Bad test RNG bound')
                return value

        with memory.connect(studio.DB) as db:
            batch=ards_batch.create_batch(db,1,Draw())
            challenge=ards_batch.next_item(db)["next"]
            private=as_text_stdin(body(primary=challenge["primary_pattern"]))
            ards2.register(db,challenge["external_id"],private)
            ards_batch.mark_review(db,challenge["external_id"],"No reviewed verifier exists")
        ident=challenge["external_id"]

        code,raw,_=self.request('/api/problems?page=1&per_page=12')
        self.assertEqual(code,200)
        result=json.loads(raw)
        self.assertNotIn(ident,[x['id'] for x in result['problems']])
        self.assertNotIn('teacher_ppc',raw.decode())
        self.assertNotIn(private['teacher_ppc']['correctness'],raw.decode())
        self.assertNotIn('reference_solution',raw.decode())

        code,raw,_=self.request('/api/problems/'+ident)
        self.assertEqual(code,404)
        self.assertNotIn('teacher_ppc',raw.decode())
        self.assertNotIn('reference_solution',raw.decode())

        code,raw,_=self.request('/api/problems?status=under_review')
        self.assertEqual(code,200)
        self.assertNotIn(ident,[x['id'] for x in json.loads(raw)['problems']])
        code,raw,_=self.request('/api/overview')
        self.assertEqual(code,200)
        summary=json.loads(raw)
        self.assertEqual(summary['authored'],2)
        self.assertEqual(summary['under_review'],1)
        self.assertEqual(summary['published'],1)
        code,raw,_=self.request('/api/problems?progress=eligible')
        self.assertEqual(code,200)
        self.assertNotIn(ident,[x['id'] for x in json.loads(raw)['problems']])

        attempted={k:'A complete formal '+k for k in studio.SECTIONS}
        code,_,_=self.request('/api/submissions/'+ident,
                {'ppc':attempted,'independent':True})
        self.assertEqual(code,404)
        code,_,_=self.request('/api/reveal/'+ident,{'confirm':True})
        self.assertEqual(code,404)
        with memory.connect(studio.DB) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts WHERE challenge_id=?',
                                        (challenge['challenge_id'],)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM solution_reveals WHERE challenge_id=?',
                                        (challenge['challenge_id'],)).fetchone()[0],0)

        code,raw,_=self.request('/api/drafts/'+ident,attempted)
        self.assertEqual(code,404)
        code,raw,_=self.request('/api/drafts/'+ident)
        self.assertEqual(code,404)
        code,html,_=self.request('/')
        self.assertNotIn(b'<option value="under_review">',html)

    def test_browse_original_challenges_without_any_mutation(self):
        before=sqlite3.connect(studio.DB).execute(
            'SELECT id,external_id,status FROM challenges ORDER BY id').fetchall()
        code,raw,headers=self.request('/api/problems')
        self.assertEqual(code,200)
        problems=json.loads(raw)['problems']
        self.assertIn('RACG-0003',[p['id'] for p in problems])
        self.assertNotIn('statement',problems[0])
        code,raw,_=self.request('/api/problems/RACG-0003')
        self.assertEqual(code,200)
        self.assertEqual(json.loads(raw)['status'],'presented')
        self.assertEqual(headers['X-Frame-Options'],'DENY')
        after=sqlite3.connect(studio.DB).execute(
            'SELECT id,external_id,status FROM challenges ORDER BY id').fetchall()
        self.assertEqual(before,after)

    def test_light_assets_and_no_dark_theme(self):
        code,html,_=self.request('/')
        self.assertEqual(code,200)
        self.assertIn(b'PPC editor',html)
        code,css,_=self.request('/app.css')
        self.assertEqual(code,200)
        self.assertIn(b'color-scheme:light',css)
        self.assertNotIn(b'prefers-color-scheme:dark',css)
        code,script,_=self.request('/app.js')
        self.assertEqual(code,200)
        self.assertIn(b'api/submissions/',script)

    def test_reference_ppc_uses_safe_formatted_modal_document(self):
        status,script,_=self.request('/workspace-ui.js')
        self.assertEqual(status,200)
        self.assertIn(b"function showReference(data,studentDraft)",script)
        self.assertIn(b"window.ARDSStatement.referenceRich(value)",script)
        code,renderer,_=self.request('/statement-renderer.js')
        self.assertEqual(code,200)
        self.assertIn(b"function referenceRich(raw)",renderer)
        self.assertIn(b"typesetReferenceExpressions",renderer)
        self.assertIn(b"reference-contents",script)
        status,html,_=self.request('/')
        self.assertEqual(status,200)
        self.assertIn(b'aria-modal="true"',html)
        status,css,_=self.request('/workspace.css')
        self.assertEqual(status,200)
        self.assertIn(b".reference-entry .statement-markdown",css)

    def test_reveal_uses_ards_confirmation_modal_not_browser_confirm(self):
        status,app,_=self.request('/app.js')
        self.assertEqual(status,200)
        start=app.index(b'function revealReference(){')
        end=app.index(b'async function saveDraft(',start)
        handler=app[start:end]
        self.assertNotIn(b'confirm(',handler)
        self.assertIn(b'window.ARDSUI.confirmReveal(id,()=>loadReference(id))',handler)
        self.assertIn(b'if(!state.current || state.current.id!==id',handler)
        self.assertIn(b"api('/api/reveal/'",handler)
        # No request is allowed to occur in the consent/display-only path.
        self.assertLess(handler.index(b'window.ARDSUI.confirmReveal'),handler.index(b"api('/api/reveal/'"))
        status,ui,_=self.request('/workspace-ui.js')
        self.assertEqual(status,200)
        self.assertIn(b'function confirmReveal(id,onConfirm)',ui)
        self.assertIn(b"{label:'Cancel',action:()=>{}}",ui)
        self.assertIn(b"{label:'Reveal PPC',primary:true,action:onConfirm}",ui)
        status,css,_=self.request('/workspace.css')
        self.assertEqual(status,200)
        self.assertIn(b'.reveal-confirmation-list',css)

    def test_headerless_navigation_preserves_mobile_and_editor_layout(self):
        status,html,_=self.request('/')
        self.assertEqual(status,200)
        self.assertNotIn(b'<header class="topbar">',html)
        self.assertNotIn(b'id="breadcrumb-current"',html)
        self.assertNotIn(b'id="expand-sidebar"',html)
        self.assertNotIn(b'class="avatar"',html)
        self.assertIn(b'id="mobile-menu"',html)
        self.assertIn(b'id="collapse-sidebar"',html)
        for route,required,removed in (
            ('/app.js',b"$('mobile-menu').addEventListener",b"$('breadcrumb-current')"),
            ('/workspace-ui.js',b"setSidebar(",b"$('expand-sidebar')"),
            ('/workspace.css',b'#view-problem{height:100dvh;}',b'NO-MATCH-EXPECTED')
        ):
            code,body,_=self.request(route)
            self.assertEqual(code,200)
            self.assertIn(required,body)
            self.assertNotIn(removed,body)
        code,css,_=self.request('/workspace.css')
        self.assertEqual(code,200)
        self.assertIn(b'#view-problem .problem-top{padding-left:68px;}',css)
        self.assertIn(b'#mobile-menu{',css)

    def test_ppc_field_manual_is_substantive_and_light_only(self):
        code, html, _ = self.request('/')
        self.assertEqual(code, 200)
        self.assertIn(b'THE PPC FIELD MANUAL', html)
        self.assertIn(b'id="manual-chapters"', html)
        self.assertIn(b'id="editor-open-guide"', html)
        for path in ('/guide.js', '/guide.css', '/guide-content.html'):
            response, data, _ = self.request(path)
            self.assertEqual(response, 200, path)
            self.assertGreater(len(data), 3000)
        _, content, _ = self.request('/guide-content.html')
        self.assertEqual(content.count(b'class="manual-lesson"'), 8)
        self.assertIn(b'Loop invariant', content)
        self.assertIn(b'P1 / SPECIFICATION', content)
        self.assertIn(b'ASYMPTOTIC UPPER BOUND', content)
        self.assertIn(b'manual-notation-query', content)
        self.assertIn(b'manual-self-check', content)
        self.assertNotIn(b'RACG-0003', content)  # No hints for unresolved challenge.

    def test_typography_refinement_and_removed_decorative_labels(self):
        status, html, _ = self.request('/')
        self.assertEqual(status, 200)
        for omitted in (b'08 CHAPTERS', b'FORMAL DEFINITIONS', b'WORKED EXAMPLES',
                        b'PROOF CHECKLISTS', b'Local workspace', b'v0.1',
                        b'Your reasoning, saved on your device.'):
            self.assertNotIn(omitted, html)
        self.assertIn(b'/typography.css', html)
        status, css, _ = self.request('/typography.css')
        self.assertEqual(status, 200)
        self.assertIn(b'--font-body: 1rem', css)
        self.assertIn(b'--font-ui: .875rem', css)
        self.assertIn(b'color-scheme: light', css)
        self.assertIn(b'@media(max-width:700px)', css)

    def test_write_autosaved_draft_and_submit_to_isolated_archive(self):
        payload={'problem':'For each valid input x, return the minimum k.',
                 'procedure':'Sort stalls and greedily place light.',
                 'correctness':'The exchange argument preserves optimal coverage.',
                 'complexity':'O(N log N) time, O(N) space for a copied array.'}
        code,raw,_=self.request('/api/drafts/RACG-0003',payload)
        self.assertEqual(code,200,raw)
        code,raw,_=self.request('/api/drafts/RACG-0003')
        self.assertEqual(code,200)
        self.assertEqual(json.loads(raw)['procedure'],payload['procedure'])
        row=sqlite3.connect(studio.DB).execute(
            "SELECT status FROM challenges WHERE external_id='RACG-0003'").fetchone()
        self.assertEqual(row[0],'presented','Saving a draft must not change ARDS status')
        code,raw,_=self.request('/api/submissions/RACG-0003',payload)
        self.assertEqual(code,201,raw)
        self.assertEqual(json.loads(raw)['stage'],'first')
        con=sqlite3.connect(studio.DB)
        attempt=con.execute("""SELECT a.submission,a.stage FROM attempts a
             JOIN challenges c ON c.id=a.challenge_id WHERE c.external_id='RACG-0003'
             ORDER BY a.id DESC LIMIT 1""").fetchone()
        self.assertIn('## C · Correctness proof',attempt[0])
        self.assertEqual(attempt[1],'first')
        code,raw,_=self.request('/api/submissions/RACG-0003',payload)
        self.assertEqual(code,201,raw)
        self.assertEqual(json.loads(raw)['stage'],'revision')

    def test_reference_reveal_preserves_previously_graded_independent_pass(self):
        import hashlib
        import memory
        import analytics
        teacher={
            'problem':'P1 — a precise output specification, private reference',
            'procedure':'P2 — a reference algorithm never shown in the public statement',
            'correctness':'C — explicit proof and termination argument',
            'complexity':'K — time O(N), extra space O(1) with derivation',
        }
        with memory.connect(studio.DB) as db:
            baseline=analytics.summarise(db)['independent_first_attempts_graded']
            ch=memory.get_challenge(db,'RACG-0003')
            aid=memory.add_attempt(db,'RACG-0003','independent attempt',stage='first',
                                   provenance='verbatim',hint_level=0,independent=True)
            memory.add_assessment(db,aid,'test reviewer',correct=True,evidence='Isolated test evidence.')
            self.assertEqual(analytics.summarise(db)['independent_first_attempts_graded'],baseline+1)
            body={'teacher_ppc':teacher, 'title':'Test package', 'statement':'No spoilers'}
            source=json.dumps(body,sort_keys=True)
            digest=hashlib.sha256(source.encode()).hexdigest()
            db.execute('INSERT INTO problem_packages(challenge_id,body_json,body_hash,created_at) VALUES (?,?,?,?)',
                       (ch['id'],source,digest,'2026-10-20'))
            cur=db.execute('INSERT INTO verification_runs(challenge_id,package_hash,outcome,tests_run,details_json,created_at) VALUES (?,?,?,?,?,?)',
                       (ch['id'],digest,'test_verified',1,'{}','2026-10-20'))
            db.execute('INSERT INTO releases(challenge_id,verification_id,package_hash,released_at) VALUES (?,?,?,?)',
                       (ch['id'],cur.lastrowid,digest,'2026-10-20'))
            db.commit()
        status,data,_=self.request('/api/problems/RACG-0003')
        self.assertEqual(status,200)
        public=json.loads(data)
        self.assertTrue(public['reference_available'])
        self.assertFalse(public['reference_revealed'])
        self.assertNotIn('private reference',data.decode())
        for route in ('/api/problems','/api/drafts/RACG-0003'):
            status,data,_=self.request(route)
            self.assertEqual(status,200)
            self.assertNotIn('private reference',data.decode())
        status,data,_=self.request('/api/reveal/RACG-0003',{'confirm':False})
        self.assertEqual(status,400)
        status,data,_=self.request('/api/reveal/RACG-0003',{'confirm':True},token=False)
        self.assertEqual(status,403)
        status,data,_=self.request('/api/reveal/RACG-0003',{'confirm':True})
        self.assertEqual(status,200,data)
        revealed=json.loads(data)
        self.assertEqual(revealed['reference_ppc'],teacher)
        self.assertTrue(revealed['assessment_eligible'])
        self.assertTrue(revealed['passed_before_reveal'])
        first_time=revealed['revealed_at']
        status,data,_=self.request('/api/reveal/RACG-0003',{'confirm':True})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(data)['revealed_at'],first_time)
        with memory.connect(studio.DB) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM solution_reveals WHERE challenge_id=?',(ch['id'],)).fetchone()[0],1)
            summary=analytics.summarise(db)
            self.assertEqual(summary['independent_first_attempts_graded'],baseline+1)
            self.assertEqual(summary['passed_before_reveal_preserved'],1)
            self.assertEqual(summary['revealed_challenges_excluded'],0)
        status,data,_=self.request('/api/problems/RACG-0003')
        self.assertEqual(status,200)
        self.assertTrue(json.loads(data)['reference_revealed'])

    def test_codex_jsonl_teacher_ppc_import_is_statement_bound_and_non_leaking(self):
        import hashlib
        import import_teacher_ppcs
        with sqlite3.connect(studio.DB) as db:
            statement=db.execute("SELECT statement FROM challenges WHERE external_id='RACG-0003'").fetchone()[0]
        source_hash=hashlib.sha256(statement.strip().encode("utf-8")).hexdigest()
        teacher={key:"Codex authored private "+key for key in studio.SECTIONS}
        row={"challenge_id":"RACG-0003","statement_sha256":source_hash,"teacher_ppc":teacher}
        path=self.temp/'codex-teacher.jsonl'
        path.write_text(json.dumps(row)+"\n",encoding="utf-8")
        dry=import_teacher_ppcs.import_batch(studio.DB,path,apply=False,expected=1)
        self.assertEqual(dry['new_references'],1)
        with sqlite3.connect(studio.DB) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM teacher_references').fetchone()[0],0)
        applied=import_teacher_ppcs.import_batch(studio.DB,path,apply=True,expected=1)
        self.assertEqual(applied['new_references'],1)
        repeat=import_teacher_ppcs.import_batch(studio.DB,path,apply=True,expected=1)
        self.assertEqual(repeat['already_present'],1)
        status,public,_=self.request('/api/problems/RACG-0003')
        self.assertEqual(status,200)
        self.assertTrue(json.loads(public)['reference_available'])
        self.assertNotIn('Codex authored private',public.decode())
        status,private,_=self.request('/api/reveal/RACG-0003',{"confirm":True})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(private)['reference_ppc'],teacher)
        self.assertIn('NOT independently verified',json.loads(private)['verification_scope'])
        bad=dict(row);bad['statement_sha256']='0'*64
        path.write_text(json.dumps(bad)+"\n",encoding="utf-8")
        with self.assertRaises(ValueError):
            import_teacher_ppcs.import_batch(studio.DB,path,apply=True)

    def test_latest_codex_edition_is_displayed_without_leaking_teacher_ppc(self):
        with studio.database() as con:
            row=con.execute("""SELECT c.external_id,e.statement,e.package_json,e.edition
                FROM challenges c JOIN classic_authoring_editions e ON e.challenge_id=c.id
                WHERE e.edition=(SELECT MAX(t.edition) FROM classic_authoring_editions t
                                 WHERE t.challenge_id=c.id)
                ORDER BY c.id LIMIT 1""").fetchone()
        if row is None:
            self.skipTest("No authored Classic RACG editions in this snapshot")
        ident=row["external_id"]
        package=json.loads(row["package_json"])
        status,raw,_=self.request('/api/problems/'+ident)
        self.assertEqual(status,200)
        info=json.loads(raw)
        self.assertEqual(info['statement'],row['statement'])
        self.assertEqual(info['edition'],row['edition'])
        self.assertTrue(info['reference_available'])
        self.assertNotIn('reference_solution',raw.decode())
        self.assertNotIn('teacher_ppc',raw.decode())
        with studio.database() as con:
            ch=con.execute("SELECT * FROM challenges WHERE external_id=?",(ident,)).fetchone()
            private,assurance=studio._load_teacher_ppc(con,ch)
        self.assertEqual(set(private),set(studio.SECTIONS))
        self.assertIn('Drafted',assurance)
        status,raw,_=self.request('/api/problems')
        self.assertEqual(status,200)
        entry=next(x for x in json.loads(raw)['problems'] if x['id']==ident)
        self.assertEqual(entry['title'],package['title'])
        self.assertNotIn('reference_solution',raw.decode())

    def test_unreleased_or_incomplete_reference_cannot_be_exposed(self):
        status,data,_=self.request('/api/reveal/RACG-0003',{'confirm':True})
        self.assertEqual(status,400)
        con=sqlite3.connect(studio.DB)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM solution_reveals').fetchone()[0],0)
        con.close()

    def test_facets_similarity_and_codechef_statement_format(self):
        status,data,_=self.request('/api/facets')
        self.assertEqual(status,200)
        facets=json.loads(data)
        self.assertGreater(len(facets['topics']),0)
        self.assertIn('comparison',facets)
        sample_id='RACG-0096' if studio.problem_detail('RACG-0096') else 'RACG-0003'
        status,data,_=self.request('/api/problems/'+sample_id)
        self.assertEqual(status,200)
        presentation=json.loads(data)['presentation_data']
        self.assertTrue(presentation['samples'])
        self.assertTrue(presentation['samples'][0]['input'])
        self.assertTrue(presentation['samples'][0]['output'])
        self.assertTrue(all('return YES' not in x for x in presentation['constraints']))
        for uri in ('/api/problems?progress=unattempted','/api/problems?presentation=story',
                    '/api/problems?topic=81','/api/problems?sort=difficulty_asc',
                    '/api/problems?similar_to='+sample_id,'/api/problems/'+sample_id+'/similar'):
            code,raw,_=self.request(uri)
            self.assertEqual(code,200,uri)
            self.assertIsInstance(json.loads(raw)['problems'],list)
        code,_,_=self.request('/api/problems?similar_to=NONEXISTENT')
        self.assertEqual(code,400)
        code,raw,_=self.request('/workspace-ui.js')
        self.assertEqual(code,200)
        self.assertIn(b'preview(',raw)
        code,raw,_=self.request('/workspace.css')
        self.assertEqual(code,200)
        self.assertIn(b'overscroll-behavior:contain',raw)
        self.assertIn(b'.sidebar-collapsed',raw)
        code,raw,_=self.request('/')
        self.assertEqual(code,200)
        self.assertIn(b'id="reveal-reference"',raw)
        self.assertNotIn(b'id="reference-section"',raw)
        self.assertNotIn(b'id="editor-prompts"',raw)

    def test_ungraded_reveal_disqualifies_future_submissions(self):
        import memory,analytics,hashlib
        teacher={key:'Answer for '+key for key in studio.SECTIONS}
        with memory.connect(studio.DB) as db:
            baseline=analytics.summarise(db)['independent_first_attempts_graded']
            ch=memory.get_challenge(db,'RACG-0003')
            source=json.dumps({'teacher_ppc':teacher},sort_keys=True)
            hashv=hashlib.sha256(source.encode()).hexdigest()
            db.execute("INSERT INTO problem_packages(challenge_id,body_json,body_hash,created_at) VALUES (?,?,?,?)",
                       (ch['id'],source,hashv,'test'))
            verify=db.execute("""INSERT INTO verification_runs(
                challenge_id,package_hash,outcome,tests_run,details_json,created_at)
                VALUES (?,?,?,?,?,?)""",(ch['id'],hashv,'test_verified',1,'{}','test'))
            db.execute("INSERT INTO releases(challenge_id,verification_id,package_hash,released_at) VALUES (?,?,?,?)",
                       (ch['id'],verify.lastrowid,hashv,'test'))
            db.commit()
        initial={s:'An independent PPC: '+s for s in studio.SECTIONS}
        code,raw,_=self.request('/api/submissions/RACG-0003',
                                 {'ppc':initial,'independent':True})
        self.assertEqual(code,201,raw)
        self.assertTrue(json.loads(raw)['independent'])
        code,raw,_=self.request('/api/reveal/RACG-0003',{'confirm':True})
        self.assertEqual(code,200,raw)
        self.assertFalse(json.loads(raw)['assessment_eligible'])
        code,raw,_=self.request('/api/submissions/RACG-0003',
                                 {'ppc':initial,'independent':True})
        self.assertEqual(code,201,raw)
        self.assertFalse(json.loads(raw)['independent'])
        with memory.connect(studio.DB) as db:
            rows=db.execute("SELECT stage,independent FROM attempts WHERE challenge_id=? ORDER BY id",
                           (ch['id'],)).fetchall()
            self.assertEqual([(x['stage'],x['independent']) for x in rows],[('first',1),('revision',0)])
            self.assertEqual(analytics.summarise(db)['independent_first_attempts_graded'],baseline)

    def test_problem_pagination_and_filter_first_layout(self):
        code,raw,_=self.request('/')
        self.assertEqual(code,200)
        self.assertNotIn(b'Your archive',raw)
        self.assertNotIn(b'Choose a challenge. Build your reasoning, one proof at a time.',raw)
        self.assertNotIn(b'id="problem-total"',raw)
        for key in (b'id="problem-pagination"',b'id="page-previous"',
                    b'id="page-next"',b'id="page-numbers"',b'id="page-size"'):
            self.assertIn(key,raw)
        code,raw,_=self.request('/api/problems')
        self.assertEqual(code,200)
        all_problems=json.loads(raw)['problems']
        if len(all_problems)<25:
            # Synthetic pagination fixtures in a test-only database backup.
            with sqlite3.connect(studio.DB) as db:
                for i in range(30):
                    db.execute("""INSERT INTO challenges(external_id,session_type,status,source,topic_id,
                          topic_label,difficulty,title,statement,created_at)
                          SELECT ?,session_type,status,source,topic_id,topic_label,
                          difficulty,?,statement,created_at FROM challenges WHERE external_id='RACG-0003'""",
                          ('TEST-PAGINATION-'+str(i).zfill(3),'Pagination fixture '+str(i)))
                db.commit()
            code,raw,_=self.request('/api/problems')
            self.assertEqual(code,200)
            all_problems=json.loads(raw)['problems']
        self.assertGreater(len(all_problems),24)
        ids=[p['id'] for p in all_problems]
        code,raw,_=self.request('/api/problems?page=1&per_page=12')
        self.assertEqual(code,200)
        first=json.loads(raw)
        self.assertEqual(first['total'],len(ids))
        self.assertEqual(first['page'],1)
        self.assertEqual(first['per_page'],12)
        self.assertEqual([p['id'] for p in first['problems']],ids[:12])
        self.assertEqual(first['pages'],(len(ids)+11)//12)
        code,raw,_=self.request('/api/problems?page=2&per_page=12')
        self.assertEqual(code,200)
        self.assertEqual([p['id'] for p in json.loads(raw)['problems']],ids[12:24])
        code,raw,_=self.request('/api/problems?page=9999&per_page=12')
        self.assertEqual(code,200)
        last=json.loads(raw)
        self.assertEqual(last['page'],last['pages'])
        self.assertEqual([p['id'] for p in last['problems']],ids[(last['pages']-1)*12:])
        code,raw,_=self.request('/api/problems?page=1&per_page=24&difficulty=1')
        self.assertEqual(code,200)
        result=json.loads(raw)
        self.assertTrue(all(p['difficulty']==1 for p in result['problems']))
        self.assertLessEqual(len(result['problems']),24)
        similar_id='RACG-0096' if studio.problem_detail('RACG-0096') else 'RACG-0003'
        code,raw,_=self.request('/api/problems?page=1&per_page=12&similar_to='+similar_id)
        self.assertEqual(code,200)
        self.assertTrue(all(p['id']!=similar_id for p in json.loads(raw)['problems']))
        for url in ('/api/problems?page=0&per_page=12','/api/problems?page=1&per_page=13',
                    '/api/problems?page=oops','/api/problems?page=-1'):
            code,_,_=self.request(url)
            self.assertEqual(code,400,url)
        code,raw,_=self.request('/app.js')
        self.assertEqual(code,200)
        self.assertIn(b'goToProblemPage',raw)

    def test_codechef_rendering_assets_and_canonical_markup(self):
        code,html,_=self.request('/')
        self.assertEqual(code,200)
        for resource in (b'/vendor/katex.min.css',b'/vendor/katex.min.js',
                         b'/vendor/markdown-it.min.js',b'/statement-renderer.js'):
            self.assertIn(resource,html)
        for route in ('/vendor/katex.min.css','/vendor/katex.min.js',
                      '/vendor/markdown-it.min.js','/statement-renderer.js',
                      '/vendor/fonts/KaTeX_Main-Regular.woff2'):
            response,payload,_=self.request(route)
            self.assertEqual(response,200,route)
            self.assertGreater(len(payload),100)
        for blocked in ('/vendor/server.py','/vendor/fonts/not-a-real-font.woff2'):
            response,_,_=self.request(blocked)
            self.assertEqual(response,404,blocked)
        code,raw,_=self.request('/api/problems/RACG-0003')
        self.assertEqual(code,200)
        detail=json.loads(raw)
        show=detail['presentation_data']
        self.assertEqual(show['format'],'ards-codechef-v1')
        self.assertEqual(len(show['samples']),3)
        self.assertEqual(show['samples'][0]['input'],'6 2\n1 2 4 7 8 12')
        self.assertEqual(show['samples'][0]['output'],'3')
        self.assertGreaterEqual(len(show['constraints']),3)
        self.assertIn('The first line contains',show['input_format'])
        self.assertIn('minimum',show['output_format'])
        self.assertNotIn('## Examples',show['description'])
        self.assertNotIn('notes',show)
        self.assertTrue(all(set(s)=={'input','output'} for s in show['samples']))
        self.assertNotIn('teacher_ppc',raw.decode())
        response,js,_=self.request('/statement-renderer.js')
        self.assertEqual(response,200)
        self.assertIn(b'html:false',js)
        self.assertIn(b'trust:false',js)
        self.assertNotIn(b'if(s.explanation',js)
        self.assertNotIn(b"heading(container,'Note')",js)
        response,css,_=self.request('/workspace.css')
        self.assertEqual(response,200)
        self.assertIn(b'grid-template-columns:subgrid',css)
        self.assertIn(b'.statement-constraints',css)
        self.assertIn(b'.sample-grid',css)

    def test_security_filters_and_validation(self):
        valid={section:'text' for section in studio.SECTIONS}
        code,_,_=self.request('/api/drafts/RACG-0003',valid,token=False)
        self.assertEqual(code,403)
        code,_,_=self.request('/api/submissions/UNKNOWN',valid)
        self.assertEqual(code,404)
        code,_,_=self.request('/api/drafts/RACG-0003',{'problem':'only field'})
        self.assertEqual(code,400)
        code,_,_=self.request('/api/submissions/RACG-0003',
                              {'problem':'ok','procedure':'ok','correctness':'ok','complexity':''})
        self.assertEqual(code,400)
        code,_,_=self.request('/api/problems?difficulty=11')
        self.assertEqual(code,400)
        self.assertIn('RACG-0003',[p['id'] for p in studio.list_problems(difficulty='2')])


if __name__=='__main__':
    unittest.main()
