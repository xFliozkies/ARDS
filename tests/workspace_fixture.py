"""Disposable website fixture: python3 tests/workspace_fixture.py [--count 0|1|30].

Use the printed URL as ARDS_UI_TEST_URL for the browser checks.
No learner archive is read or modified. Default: one reviewed synthetic problem
with an imported teacher sentinel, plus a private unreleased selection.
"""
import argparse
import hashlib
import json
import time
from test_website import WebsiteTests, studio
import memory
import ppc_assess

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--count',type=int,default=1)
    args=parser.parse_args()
    fixture=WebsiteTests()
    fixture.setUp()
    with memory.connect(studio.DB) as con:
        if args.count==0:
            con.execute('DELETE FROM challenges')
        else:
            ch=con.execute('SELECT * FROM challenges').fetchone()
            teacher={key:'TEACHER_SENTINEL_'+key for key in studio.SECTIONS}
            con.execute('INSERT INTO teacher_references(challenge_id,statement_sha256,ppc_json,provenance,created_at) VALUES (?,?,?,?,?)',
                        (ch['id'],hashlib.sha256(ch['statement'].strip().encode()).hexdigest(),json.dumps(teacher),'synthetic_ui_fixture',studio.now()))
            memory.add_attempt(con,'RACG-0003','Synthetic original submission',stage='first',provenance='verbatim')
            attempt=con.execute('SELECT MAX(id) FROM attempts').fetchone()[0]
            report={'reviewer_kind':'human','reviewer':'Synthetic reviewer','verdict':'undetermined','proof_assurance':'reasoned_review',
                    'sections':{key:{'status':'uncertain','finding':'The submitted claim leaves a boundary condition unresolved in this synthetic review.',
                                     'evidence':'The submitted universal quantification has no supporting argument at the domain boundary.',
                                     'uncertainty':'The boundary argument needs a separate review.'} for key in studio.SECTIONS}}
            ppc_assess.record(con,attempt,report)
            for i in range(1,args.count):
                con.execute("""INSERT INTO challenges(external_id,session_type,status,source,difficulty,title,statement,statement_hash,created_at,topic_id,topic_label)
                    VALUES (?,'RACG','presented','synthetic_ui_fixture',?,?,?,?,?,?,?)""",
                    (f'UI-{i:04}',i%6+1,f'Synthetic UI problem {i}',ch['statement'],ch['statement_hash'],studio.now(),i%3+1,f'Synthetic topic {i%3+1}'))
            con.execute("""INSERT INTO challenges(external_id,session_type,status,source,difficulty,title,created_at)
                VALUES ('UI-PRIVATE','RACG','selected','synthetic_ui_fixture',1,'PRIVATE_DRAFT_SENTINEL',?)""",(studio.now(),))
        con.commit()
    print(fixture.base,flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        fixture.doCleanups()
