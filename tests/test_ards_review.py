"""Independent reviewer proof-of-process: isolated data and reviewer source copies."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import memory
import ards2
import ards_batch
import ards_review


class DeterministicDraw:
    def __init__(self): self.rolls=iter((98,0,0,24,0))
    def __call__(self,n):
        value=next(self.rolls)
        assert 0<=value<n
        return value


def specimen(pattern):
    return {
        "title":"Independent review testing fixture: palindrome prefix",
        "statement":"You are given a nonempty string s of lowercase letters a, b, and c. A prefix is the first L characters of s, starting at the beginning without skipping any. A prefix is a palindrome if it reads the same from left to right and right to left. Find the largest possible L.",
        "difficulty_estimate":1, "patterns":[pattern],
        "provenance":"synthetic_fixture_author_not_reviewer",
        "model":{"inputs":{"s":"nonempty abc string of length at most 2000"},
                 "hidden_variables":[],
                 "constraints":["1 <= len(s) <= 2000","s is over alphabet abc"],
                 "objective":"Maximum L such that s[0:L] is a palindrome",
                 "family":"independent_review_test_palindrome","parameters":{"input_encoding":"stdin_tokens","output_encoding":"stdout_text"}},
        "io_contract":{"encoding":"stdin_tokens_v1"},
        "statement_display":{"description":"A prefix is the first L characters of the given string, with no skipped characters. It is a palindrome when it reads the same from left to right and right to left. Print the greatest possible L.","input_format":"Read one string s.","output_format":"Print one integer.","constraints":["1 <= len(s) <= 2000"],"samples":[{"input":"abac","output":"3"},{"input":"bc","output":"1"}]},
        "reference_solution":"For lengths n down to one, test reflected character pairs.",
        "proof":"A prefix is a palindrome if and only if all symmetric pairs are equal.",
        "teacher_ppc":{
            "problem":r"""**Input domain.** Let \(D\) contain nonempty strings \(s=(s_1,\ldots,s_n)\) with one-based positions and

\[
1\le n\le 2000,\qquad s_i\in\{a,b,c\}.
\]

**Required output.** Return the maximum integer \(L\) for which

\[
1\le L\le n,\qquad
\forall j\in[1,\lfloor L/2\rfloor],\ s_j=s_{L+1-j}.
\]

A one-character prefix always satisfies the relation, so a valid result exists.""",
            "procedure":"Check each length n to one by mirrored character comparisons.",
            "correctness":r"""**Theorem.** For every \(s\in D\), P2 terminates and returns the maximum prefix length satisfying P1.

**Proof — candidate validity.** For a fixed \(L\), the pairwise comparison succeeds if and only if

\[
\forall j\in[1,\lfloor L/2\rfloor],\quad s_j=s_{L+1-j}.
\]

This is precisely the predicate in P1, so every accepted length is valid.

**Optimality.** Lengths are examined in descending order. Each larger candidate was rejected by a mismatching pair and cannot satisfy P1, so the first accepted length is maximal.

**Termination and boundary.** There are at most \(n\) candidate lengths, each with at most \(\lfloor L/2\rfloor\) finite comparisons. The candidate \(L=1\) vacuously satisfies the predicate, so the search always returns an answer even for \(n=1\).

Therefore P2 terminates and satisfies the entire P1 output relation for every legal input.""",
            "complexity":"At most n candidate lengths and n comparisons each, so O(n squared) time and O(1) extra space."},
        "samples":[{"input":"abac","output":"3"},
                   {"input":"bc","output":"1"}]
    }


class IndependentReviewTests(unittest.TestCase):
    def setUp(self):
        self.dbtmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.dbtmp.cleanup)
        self.files=tempfile.TemporaryDirectory(dir=ards_review.REVIEWS,prefix="test_review_")
        self.addCleanup(self.files.cleanup)
        self.module=Path(self.files.name)/"RACG-0001.py"
        self.report=Path(self.files.name)/"RACG-0001.json"
        shutil.copyfile(ROOT/"tests"/"fixtures"/"reviewers"/"RACG-0001-text.py",self.module)
        shutil.copyfile(ROOT/"tests"/"fixtures"/"reviewers"/"RACG-0001-text.json",self.report)
        self.con=memory.connect(Path(self.dbtmp.name)/"ards.db")
        self.addCleanup(self.con.close)
        ards_batch.create_batch(self.con,1,DeterministicDraw())
        self.entry=ards_batch.next_item(self.con)["next"]
        self.ident=self.entry["external_id"]
        self.body=specimen(self.entry["primary_pattern"])
        ards2.register(self.con,self.ident,self.body)

    def check(self):
        return ards_review.check(self.con,self.ident,self.module,self.report)

    def test_passed_independent_review_can_release(self):
        result=self.check()
        self.assertEqual(result["outcome"],"passed")
        self.assertEqual(result["samples"],2)
        self.assertEqual(result["generated"],180)
        self.assertGreaterEqual(result["edges"],3)
        self.assertGreaterEqual(result["distinct_inputs"],100)
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["verified"],1)
        released=ards2.release(self.con,self.ident)
        self.assertTrue(released["released"])
        self.assertEqual(released["verification"],"tested_and_ai_reviewed")
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["released"],1)
        student=ards2.export_text(self.con,self.ident,"student")
        self.assertNotIn(self.body["teacher_ppc"]["correctness"],student)
        self.assertEqual(self.con.execute("PRAGMA integrity_check").fetchone()[0],"ok")

    def test_missing_ppc_proof_review_blocks_approval(self):
        report=json.loads(self.report.read_text(encoding="utf-8"))
        del report["ppc_review"]
        self.report.write_text(json.dumps(report),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"PPC formal review"):
            self.check()
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM independent_reviews").fetchone()[0],0)

    def test_unanchored_ppc_quotes_block_approval(self):
        for key in ("input_domain_quote","output_relation_quote","claim_quote",
                    "reasoning_quote","termination_quote"):
            with self.subTest(key=key):
                report=json.loads((ROOT/"tests"/"fixtures"/"reviewers"/"RACG-0001-text.json").read_text(encoding="utf-8"))
                report["ppc_review"][key]="Invented text that does not appear in the teacher PPC."
                with self.assertRaisesRegex(ValueError,"PPC review must quote"):
                    ards_review.validate_review(report,self.body)

    def test_missing_proof_obligation_or_unjustified_coverage_blocks_approval(self):
        base=json.loads(self.report.read_text(encoding="utf-8"))
        for change in ("mapping","coverage","justification"):
            report=json.loads(json.dumps(base))
            if change=="mapping":
                report["ppc_review"]["obligation_mapping"]=[]
            elif change=="coverage":
                report["ppc_review"]["all_p1_obligations_covered"]=False
            else:
                report["ppc_review"]["obligation_mapping"][0]["justification"]="Because yes"
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError,"PPC"):
                    ards_review.validate_review(report,self.body)

    def test_missing_math_presentation_review_blocks_approval(self):
        report=json.loads(self.report.read_text(encoding="utf-8"))
        del report["ppc_review"]["math_presentation_analysis"]
        with self.assertRaisesRegex(ValueError,"math_presentation_analysis"):
            ards_review.validate_review(report,self.body)

    def test_stale_reviewer_code_prevents_release(self):
        self.assertEqual(self.check()["outcome"],"passed")
        self.module.write_text(self.module.read_text()+"\n# Changed after review\n")
        with self.assertRaisesRegex(ValueError,"evidence"):
            ards2.release(self.con,self.ident)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM releases").fetchone()[0],0)

    def test_stale_review_report_prevents_release(self):
        self.assertEqual(self.check()["outcome"],"passed")
        self.report.write_text(self.report.read_text()+"\n")
        with self.assertRaisesRegex(ValueError,"evidence"):
            ards2.release(self.con,self.ident)

    def test_revised_package_invalidates_approval(self):
        self.assertEqual(self.check()["outcome"],"passed")
        newer=dict(self.body)
        newer["proof"]=newer["proof"]+" This revised explanation is a new unverified candidate."
        ards2.revise_draft(self.con,self.ident,newer,"Correcting the explanation before publishing")
        with self.assertRaisesRegex(ValueError,"verification"):
            ards2.release(self.con,self.ident)
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["drafted"],1)

    def test_approval_statement_cannot_override_bad_code(self):
        self.module.write_text(self.module.read_text()+"\n\ndef candidate(data):\n    return -1\n")
        result=self.check()
        self.assertEqual(result["outcome"],"failed")
        self.assertIn("sample",result["reason"].lower())
        with self.assertRaisesRegex(ValueError,"verification"):
            ards2.release(self.con,self.ident)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM independent_reviews WHERE outcome='passed'").fetchone()[0],0)


    def test_new_batch_registration_rejects_json_only_io(self):
        with tempfile.TemporaryDirectory() as folder:
            with memory.connect(Path(folder)/"fresh.db") as con:
                ards_batch.create_batch(con,1,DeterministicDraw())
                slot=ards_batch.next_item(con)["next"]
                raw=specimen(slot["primary_pattern"])
                raw["model"]["parameters"]={"batch_id":1,"input_encoding":"JSON","output_encoding":"JSON"}
                with self.assertRaisesRegex(ValueError,"stdin/stdout"):
                    ards2.register(con,slot["external_id"],raw)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM problem_packages").fetchone()[0],0)

    def test_batch_io_contract_cannot_be_removed_by_revision(self):
        bad=json.loads(json.dumps(self.body))
        bad.pop("io_contract")
        with self.assertRaisesRegex(ValueError,"stdin/stdout"):
            ards2.revise_draft(self.con,self.ident,bad,"Try to bypass I/O requirements")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM authoring_package_revisions").fetchone()[0],0)

    def test_plain_text_revision_requires_independent_new_evidence(self):
        self.assertEqual(self.check()["outcome"],"passed")
        self.assertTrue(ards2.release(self.con,self.ident)["released"])
        candidate=json.loads(json.dumps(self.body))
        candidate["model"]["parameters"].update(batch_id=1,input_encoding="stdin_tokens",output_encoding="stdout_text")
        candidate["model"]["inputs"]={"S":"One text input token"}
        candidate["io_contract"]={"encoding":"stdin_tokens_v1"}
        candidate["statement"]="The only line contains S. Print the maximum palindromic prefix length."
        candidate["statement_display"]={
            "description":self.body["statement_display"]["description"]+" The input string is named S.",
            "input_format":"The only input line contains one string S.",
            "output_format":"Print a single integer.",
            "constraints":["1 <= len(S) <= 2000"],
            "samples":[{"input":"abac","output":"3"},{"input":"bc","output":"1"}]}
        candidate["samples"]=[{"input":"abac","output":"3"},{"input":"bc","output":"1"}]
        candidate["teacher_ppc"]["correctness"]+=" The revised procedure still checks mirrored pairs."
        self.assertTrue(ards2.contest_io_ready(candidate))
        with self.assertRaisesRegex(ValueError,"independent review evidence"):
            ards2.amend(self.con,self.ident,candidate,"Change test I/O contract")
        new_module=Path(self.files.name)/"RACG-0001-text.py"
        new_report=Path(self.files.name)/"RACG-0001-text.json"
        shutil.copyfile(ROOT/"tests"/"fixtures"/"reviewers"/"RACG-0001-text.py",new_module)
        shutil.copyfile(ROOT/"tests"/"fixtures"/"reviewers"/"RACG-0001-text.json",new_report)
        self.assertEqual(ards_review.check(self.con,self.ident,new_module,new_report,
                                           proposed_body=candidate)["outcome"],"passed")
        changed=ards2.amend(self.con,self.ident,candidate,"Review new stdin/stdout contract")
        self.assertEqual(changed["revision"],2)
        self.assertEqual(ards2.latest_published_body(self.con,
                         ards2.get_challenge(self.con,self.ident))[1]["samples"][0]["input"],"abac")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM releases").fetchone()[0],1)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM published_revisions").fetchone()[0],1)
        self.assertEqual(self.con.execute("PRAGMA integrity_check").fetchone()[0],"ok")


    def test_forged_latest_review_details_do_not_authorize_release(self):
        self.assertEqual(self.check()["outcome"],"passed")
        prior=self.con.execute("SELECT * FROM verification_runs ORDER BY id DESC LIMIT 1").fetchone()
        forged=json.loads(prior["details_json"])
        forged["reviewer_id"]="Unknown independent reviewer"
        with self.con:
            self.con.execute(
                "INSERT INTO verification_runs(challenge_id,package_hash,outcome,tests_run,details_json,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (self.entry["challenge_id"],prior["package_hash"],"test_verified",
                 prior["tests_run"],json.dumps(forged),memory.now()))
        with self.assertRaisesRegex(ValueError,"evidence"):
            ards2.release(self.con,self.ident)
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["under_review"],1)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM releases").fetchone()[0],0)

    def test_specification_audit_matches_recorded_difficulty(self):
        report=json.loads(self.report.read_text())
        omitted=dict(report)
        omitted.pop("specification_review")
        with self.assertRaisesRegex(ValueError,"specification_review"):
            ards_review.validate_review(omitted,self.body)
        wrong=json.loads(json.dumps(report))
        wrong["specification_review"]["difficulty"]=4
        with self.assertRaisesRegex(ValueError,"recorded difficulty"):
            ards_review.validate_review(wrong,self.body)
        wrong=json.loads(json.dumps(report))
        wrong["specification_review"]["comprehension_policy"]="abstract_interpretation_permitted"
        with self.assertRaisesRegex(ValueError,"level-dependent"):
            ards_review.validate_review(wrong,self.body)

    def test_higher_levels_permit_abstract_comprehension(self):
        report=json.loads(self.report.read_text())
        level_four=json.loads(json.dumps(self.body))
        level_four["difficulty_estimate"]=4
        report["specification_review"]["difficulty"]=4
        report["specification_review"]["comprehension_policy"]="abstract_interpretation_permitted"
        report["specification_review"]["level_profile"]="L4_standard_domain_terms"
        ards_review.validate_review(report,level_four)
        report["specification_review"]["terminology_and_prerequisites"]="No concerns."
        with self.assertRaisesRegex(ValueError,"problem-specific"):
            ards_review.validate_review(report,level_four)

    def test_each_level_requires_its_own_profile(self):
        report=json.loads(self.report.read_text())
        profiles=ards_review.COMPREHENSION_PROFILES
        self.assertEqual(set(profiles),set(range(1,7)))
        self.assertEqual(len(set(profiles.values())),6)
        policy_by_level=lambda level: ("accessible_without_topic_prerequisites"
                                       if level<=3 else "abstract_interpretation_permitted")
        for level,profile in profiles.items():
            with self.subTest(level=level):
                package=json.loads(json.dumps(self.body))
                package["difficulty_estimate"]=level
                current=json.loads(json.dumps(report))
                current["specification_review"].update(
                    difficulty=level,comprehension_policy=policy_by_level(level),
                    level_profile=profile)
                ards_review.validate_review(current,package)
                current["specification_review"]["level_profile"]="L1_plain_foundations" if level!=1 else "L6_dense_mathematical_model"
                with self.assertRaisesRegex(ValueError,"exact six-level"):
                    ards_review.validate_review(current,package)

    def test_reviewer_must_quote_student_statement_and_analyze_exact_level(self):
        report=json.loads(self.report.read_text())
        audit=report["specification_review"]
        audit["student_text_quote"]="An impressive sentence absent from every field"
        with self.assertRaisesRegex(ValueError,"quotation not found"):
            ards_review.validate_review(report,self.body)
        audit["student_text_quote"]="A prefix is the first L characters of the given string"
        audit["level_specific_evidence"]="Level 1 is accessible."
        with self.assertRaisesRegex(ValueError,"level_specific_evidence"):
            ards_review.validate_review(report,self.body)
        audit["level_specific_evidence"]="The learner-visible definition of prefix says that its letters must occur at the beginning without gaps. The palindrome rule also explicitly describes reading in both directions. A reader can check validity without prior knowledge of string algorithms."
        ards_review.validate_review(report,self.body)

    def test_six_level_policy_has_distinct_exemplars_and_review_questions(self):
        rubric=(ROOT/"references"/"specification_comprehension.md").read_text()
        for level,profile in ards_review.COMPREHENSION_PROFILES.items():
            with self.subTest(level=level):
                self.assertIn(profile,rubric)
                marker="### Level "+str(level)+" — "
                self.assertIn(marker,rubric)
                section=rubric.split(marker,1)[1].split("\\n### Level ",1)[0]
                for heading in ("**Acceptable:**","**Reject:**","**Pass test:**"):
                    self.assertIn(heading,section)

    def test_written_review_is_required(self):
        report=json.loads(self.report.read_text())
        report["correctness_analysis"]="Looks good"
        self.report.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,"correctness_analysis"):
            self.check()
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM independent_reviews").fetchone()[0],0)


if __name__=="__main__":
    unittest.main()
