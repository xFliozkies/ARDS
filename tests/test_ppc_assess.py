import tempfile
import unittest
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import memory
import ppc_assess

def report(verdict="correct"):
    status="supported" if verdict=="correct" else "uncertain"
    return {
        "reviewer_kind":"ai", "reviewer":"Independent reviewer agent",
        "verdict":verdict,"proof_assurance":"reasoned_review",
        "sections":{k:{
             "status":status,
             "finding":"The learner's argument identifies a concrete claim for "+k+" and its exact constraints.",
             "evidence":"The review must compare the learner's particular argument against the problem specification and explain why the claimed relation is valid in all cases."
        } for k in ppc_assess.FIELDS},
        "scores":{"modeling":3,"correctness_reasoning":3}
    }


class PPCAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.con=memory.connect(Path(self.tmp.name)/"learner.db")
        self.addCleanup(self.con.close)
        self.con.execute("""
            INSERT INTO challenges(external_id,session_type,status,source,topic_label,
                title,statement,created_at,presented_at)
            VALUES('TEST-0001','RACG','presented','synthetic','arrays',
                'Synthetic task','Count values.', '2020-01-01','2020-01-01')
        """)
        self.con.commit()
        self.attempt=memory.add_attempt(self.con,'TEST-0001',
                         'P1: values; P2: count; C: invariant; K: linear',
                         stage='first',independent=True,hint_level=0)

    def test_packet_preserves_verbatim_and_keeps_teacher_ppc_private(self):
        packet=ppc_assess.attempt_packet(self.con,self.attempt)
        self.assertEqual(packet["submission_verbatim"],
                         'P1: values; P2: count; C: invariant; K: linear')
        self.assertFalse(packet["reference_ppc_included"])
        self.assertNotIn("teacher_ppc",packet)

    def test_records_evidence_backed_graded_attempt_without_reveal(self):
        result=ppc_assess.record(self.con,self.attempt,report())
        self.assertEqual(result["verdict"],"correct")
        self.assertFalse(result["reference_ppc_revealed"])
        row=self.con.execute("SELECT * FROM assessments WHERE id=?",
                             (result["assessment_id"],)).fetchone()
        self.assertEqual(row["correct"],1)
        self.assertIn("reasoned_review",row["evidence"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM solution_reveals").fetchone()[0],0)

    def test_no_correct_grade_when_proof_is_uncertain(self):
        incomplete=report()
        incomplete["sections"]["correctness"]["status"]="uncertain"
        with self.assertRaisesRegex(ValueError,"all four"):
            ppc_assess.record(self.con,self.attempt,incomplete)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],0)

    def test_unknown_result_remains_unknown(self):
        res=ppc_assess.record(self.con,self.attempt,report("undetermined"))
        row=self.con.execute("SELECT correct FROM assessments WHERE id=?",(res["assessment_id"],)).fetchone()
        self.assertIsNone(row["correct"])

    def test_improper_confidence_and_unsubstantiated_formal_claim_rejected(self):
        claimed=report()
        claimed["proof_assurance"]="formal_proof"
        with self.assertRaisesRegex(ValueError,"Formal proof"):
            ppc_assess.record(self.con,self.attempt,claimed)
        claimed=report("incorrect")
        with self.assertRaisesRegex(ValueError,"incorrect component"):
            ppc_assess.record(self.con,self.attempt,claimed)

    def test_review_revision_explicitly_links_prior_assessment(self):
        first=ppc_assess.record(self.con,self.attempt,report("undetermined"))
        with self.assertRaisesRegex(ValueError,"preceding assessment ID"):
            ppc_assess.record(self.con,self.attempt,report())
        newer=report()
        newer["supersedes_assessment_id"]=first["assessment_id"]
        second=ppc_assess.record(self.con,self.attempt,newer)
        self.assertNotEqual(first["assessment_id"],second["assessment_id"])


if __name__=="__main__":
    unittest.main()
