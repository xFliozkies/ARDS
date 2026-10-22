import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import memory
import ards2


def fake_selection(previous):
    return {
      "topic_id": 43, "topic_label": "Mathematics",
      "difficulty": 3, "continuation": False,
      "story": True, "presentation": "story",
      "rolls":{"O":99,"X":142,"Y":56,"P":24},
    }


def body(family="tiered_price", primary="F01"):
    return ards2.prepare_reference(_authored_body(family,primary))


def _authored_body(family="tiered_price", primary="F01"):
    if family == "tiered_price":
        return {
          "title":"Aquarium Ticket Discount",
          "statement":"An aquarium charges 60 coins per ticket. For groups of at least 4, each ticket costs 45 coins. Find the total price for N tickets, 1 <= N <= 10.",
          "difficulty_estimate":3,
          "patterns":[primary,"F02"] if primary!="F02" else [primary],
          "provenance":"original-generated-test-fixture",
          "model":{
            "inputs":{"N":"positive integer"},
            "hidden_variables":[],
            "constraints":["1 <= N <= 10","discount applies to all tickets iff N >= 4"],
            "objective":"Compute the cost of N tickets.",
            "family":"tiered_price",
            "parameters":{"threshold":4,"full":60,"discounted":45,"min_n":1,"max_n":10}
          },
          "reference_solution":"Use N * (45 if N >= 4 else 60).",
          "proof":"For N < 4 every ticket costs 60; otherwise all N tickets cost 45.",
          "teacher_ppc":{
              "problem":"For N in [1,10], return N times 60 if N<4, otherwise N times 45.",
              "procedure":"Read N, choose per-ticket price with N>=4, output N*price, then halt.",
              "correctness":"The two exhaustive branches return precisely the stated price; one constant-time calculation terminates.",
              "complexity":"Under bounded-word arithmetic, time O(1) and auxiliary space O(1)."
          },
          "samples":[{"input":"3\n","output":"180\n"},{"input":"4\n","output":"180\n"}],
        }
    return {
       "title":"Shift Constraint",
       "statement":"Given a nonempty lowercase string S, can both a single left rotation and a single right rotation of the same V equal S?",
       "difficulty_estimate":3,
       "patterns":[primary,"S03"] if primary!="S03" else [primary],
       "provenance":"original-generated-test-fixture",
       "model":{
          "inputs":{"S":"nonempty string"},
          "hidden_variables":["V"],
          "constraints":["L(V)=S","R(V)=S"],
          "objective":"Determine whether such V exists.",
          "family":"opposite_rotations",
          "parameters":{"alphabet":"abc","exhaustive_max_n":7}
       },
       "reference_solution":"Check for each i, S[i] == S[(i+2)%n].",
       "proof":"L(V)=S implies V=R(S). Then R(V)=S iff R^2(S)=S.",
       "teacher_ppc":{
           "problem":"Given a nonempty lowercase string S, return existence of V satisfying both left and right rotations to S.",
           "procedure":"Scan every index i and check whether S[i]=S[(i+2) mod n]; return true if all comparisons match.",
           "correctness":"The left-rotation constraint uniquely determines V, so a solution exists iff S is periodic by two; bounded index scan terminates.",
           "complexity":"The scan costs O(n) time and O(1) auxiliary space on indexed strings."
       },
       "samples":[{"input":"abab","output":"YES"},{"input":"abc","output":"NO"}]
    }


class ARDS2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.con=memory.connect(Path(self.tmp.name)/"ards.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def create(self):
        sel=memory.record_random_selection(self.con,fake_selection)
        p=ards2.plan(self.con,sel["external_id"],randbelow=lambda n:0)
        return sel["external_id"],p["primary_pattern"]

    def test_catalog_has_all_three_layers_and_distinct_ids(self):
        catalog=ards2.patterns()
        self.assertEqual(len(catalog["patterns"]),30)
        self.assertEqual({p["layer"] for p in catalog["patterns"]},
                         {"foundational","structural","compositional"})

    def test_migration_keeps_legacy_and_is_idempotent(self):
        memory.import_legacy(self.con,root=ROOT/"tests"/"fixtures"/"legacy",)
        first=memory.get_challenge(self.con,"RACG-0002")
        for _ in range(3):
            ards2.ensure_schema(self.con)
        self.assertEqual(first,memory.get_challenge(self.con,"RACG-0002"))
        self.assertEqual(self.con.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0],"2")
        self.assertEqual(memory.doctor(self.con)["integrity_check"],"ok")

    def test_plan_roll_is_saved_only_once_and_does_not_change_random_selection(self):
        ident,primary=self.create()
        ch=memory.get_challenge(self.con,ident)
        self.assertEqual((ch["roll_o"],ch["roll_x"],ch["roll_y"],ch["roll_p"]),(99,142,56,24))
        self.assertEqual(ch["difficulty"],3)
        with self.assertRaises(sqlite3.IntegrityError):
            ards2.plan(self.con,ident,randbelow=lambda n:0)
        self.assertTrue(primary)
        self.assertEqual(ards2.inspect(self.con,ident)["plan"]["z"],0)

    def test_no_new_problem_registered_without_private_ppc(self):
        ident,primary=self.create()
        proposed=body(primary=primary)
        del proposed["teacher_ppc"]
        with self.assertRaisesRegex(ValueError,"private teacher_ppc"):
            ards2.register(self.con,ident,proposed)
        self.assertIsNone(self.con.execute("SELECT challenge_id FROM problem_packages").fetchone())

    def test_no_release_without_verification(self):
        ident,primary=self.create()
        ards2.register(self.con,ident,body(primary=primary))
        with self.assertRaisesRegex(ValueError,"verification"):
            ards2.release(self.con,ident)
        self.assertEqual(memory.get_challenge(self.con,ident)["status"],"selected")

    def test_price_oracle_exhaustive_and_student_teacher_export(self):
        ident,primary=self.create()
        p=body(primary=primary)
        ards2.register(self.con,ident,p)
        result=ards2.verify(self.con,ident)
        self.assertEqual(result["outcome"],"test_verified")
        self.assertEqual(result["tests_run"],12)
        released=ards2.release(self.con,ident)
        self.assertTrue(released["released"])
        self.assertFalse(released["proof_reviewed"])
        student=ards2.export_text(self.con,ident,"student")
        teacher=ards2.export_text(self.con,ident,"teacher")
        self.assertNotIn("The applicable price",student)
        self.assertNotIn("Correctness argument",student)
        self.assertIn("The applicable price",teacher)
        self.assertIn("Formal model",teacher)
        dest=Path(self.tmp.name)/"student.md"
        exported=ards2.export_file(self.con,ident,"student",dest)
        self.assertTrue(exported["saved"])
        self.assertEqual(dest.read_text(encoding="utf-8"),student)
        with self.assertRaises(FileExistsError):
            ards2.export_file(self.con,ident,"student",dest)
        self.assertEqual(ards2.inspect(self.con,ident)["release"]["package_hash"],ards2.digest(p))

    def test_rotations_exhaustive_oracle(self):
        original=body("opposite_rotations")
        verified=ards2.verify_body(original)
        self.assertEqual(verified["outcome"],"test_verified")
        self.assertEqual(verified["tests_run"],sum(3**i for i in range(1,8))+2)
        for s in ("a","ab","abab","aaaaa","abc","ababa"):
            fast,slow=ards2._rotate_methods(s)
            self.assertEqual(fast,slow)

    def test_comparison_maxima_independent_graph_oracle(self):
        p=body("opposite_rotations")
        p["model"]["family"]="comparison_maxima"
        p["model"]["parameters"]={"exhaustive_max_n":10}
        p["samples"]=[{"input":"10","output":"2"},{"input":"01","output":"1"},
                      {"input":"101","output":"2"}]
        p=ards2.prepare_reference(p)
        result=ards2.verify_body(p)
        self.assertEqual(result["outcome"],"test_verified")
        self.assertEqual(result["tests_run"],sum(2**(n-1) for n in range(2,11))+3)
        self.assertEqual(ards2._maxima_methods("001110"),(2,2))

    def test_model_family_must_match_original_randomized_topic(self):
        ident,primary=self.create()
        p=body("opposite_rotations",primary)
        with self.assertRaisesRegex(ValueError,"incompatible"):
            ards2.register(self.con,ident,p)

    def test_pattern_profile_is_evidence_only(self):
        ident,primary=self.create()
        ards2.register(self.con,ident,body(primary=primary))
        ards2.verify(self.con,ident)
        ards2.release(self.con,ident)
        report=ards2.pattern_profile(self.con)
        self.assertTrue(report["not_a_calibrated_skill_rating"])
        self.assertEqual(report["patterns"],{})
        aid=memory.add_attempt(self.con,ident,"Use a threshold branch",stage="first",
                               hint_level=0,independent=True)
        memory.add_assessment(self.con,aid,"reviewer",correct=True,evidence="Correct branch")
        report=ards2.pattern_profile(self.con)
        self.assertEqual(report["patterns"][primary]["independent_correct"],1)

    def test_amendment_preserves_original_and_exports_latest(self):
        ident,primary=self.create()
        original=body(primary=primary)
        ards2.register(self.con,ident,original)
        ards2.verify(self.con,ident)
        ards2.release(self.con,ident)
        corrected=json.loads(json.dumps(original))
        corrected["title"]="Museum Tickets Revision"
        corrected["statement"]="Updated wording; 60 coins normally, 45 each for N >= 4."
        out=ards2.amend(self.con,ident,corrected,"Clarity improvement")
        self.assertEqual(out["revision"],2)
        self.assertEqual(memory.get_challenge(self.con,ident)["statement"],original["statement"])
        student=ards2.export_text(self.con,ident,"student")
        teacher=ards2.export_text(self.con,ident,"teacher")
        self.assertIn("Updated wording",student)
        self.assertNotIn("The applicable price",student)
        self.assertIn("The applicable price",teacher)
        self.assertIn("Published statement revision: 2",student)
        self.assertEqual(len(ards2.inspect(self.con,ident)["revisions"]),1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("DELETE FROM published_revisions")
        self.con.rollback()
        wrong=json.loads(json.dumps(corrected))
        wrong["samples"][0]["output"]="999"
        with self.assertRaisesRegex(ValueError,"verification"):
            ards2.amend(self.con,ident,wrong,"Bad correction")
        self.assertEqual(len(ards2.inspect(self.con,ident)["revisions"]),1)

    def test_complete_new_cli_lifecycle(self):
        # Exercise the real CLI on a disposable database; never draw into production.
        ident=memory.record_random_selection(self.con,fake_selection)["external_id"]
        def cli(*args):
            result=subprocess.run([sys.executable,str(ROOT/"scripts"/"ards2.py"),
                                   "--db",str(Path(self.tmp.name)/"ards.db"),*args],
                                  capture_output=True,text=True,check=True)
            return json.loads(result.stdout)
        planned=cli("plan",ident)
        self.assertTrue(planned["classic_racg_unchanged"])
        packet=body(primary=planned["primary_pattern"])
        filepath=Path(self.tmp.name)/"packet.json"
        filepath.write_text(json.dumps(packet),encoding="utf-8")
        self.assertTrue(cli("register",ident,"--file",str(filepath))["saved"])
        self.assertEqual(cli("verify",ident)["outcome"],"test_verified")
        self.assertTrue(cli("release",ident)["released"])
        dest=Path(self.tmp.name)/"teacher.md"
        self.assertTrue(cli("export",ident,"--edition","teacher","--out",str(dest))["saved"])
        self.assertIn("Correctness argument",dest.read_text(encoding="utf-8"))
        self.assertEqual(cli("inspect",ident)["challenge"]["status"],"presented")

    def test_bad_sample_blocks_release(self):
        ident,primary=self.create()
        p=body(primary=primary)
        p["samples"][0]["output"]="999"
        ards2.register(self.con,ident,p)
        self.assertEqual(ards2.verify(self.con,ident)["outcome"],"failed")
        with self.assertRaises(ValueError):
            ards2.release(self.con,ident)
        self.assertEqual(memory.get_challenge(self.con,ident)["status"],"selected")

    def test_unrecognized_family_is_experimental_not_verified(self):
        ident,primary=self.create()
        p=body(primary=primary)
        p["model"]["family"]="unreviewed_ai_created_solver"
        ards2.register(self.con,ident,p)
        self.assertEqual(ards2.verify(self.con,ident)["outcome"],"experimental")
        with self.assertRaises(ValueError):
            ards2.release(self.con,ident)

    def test_package_and_verification_are_immutable(self):
        ident,primary=self.create()
        ards2.register(self.con,ident,body(primary=primary))
        ards2.verify(self.con,ident)
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("UPDATE problem_packages SET body_json='{}'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("DELETE FROM verification_runs")
        self.con.rollback()

    def test_incomplete_historical_teacher_export_is_blocked(self):
        memory.import_legacy(self.con,root=ROOT/"tests"/"fixtures"/"legacy",)
        student=ards2.export_text(self.con,"RACG-0002","student")
        self.assertIn("RACG-0002",student)
        with self.assertRaises(ValueError):
            ards2.export_text(self.con,"RACG-0002","teacher")

    def test_no_training_cap_and_no_new_draw_during_migration(self):
        before=self.con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
        ards2.ensure_schema(self.con)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],before)
        self.assertNotIn("mastery",dict(self.con.execute("SELECT * FROM metadata").fetchall()))
        self.assertEqual(memory.doctor(self.con)["integrity_check"],"ok")

    def test_invalid_catalog_or_sample_inputs(self):
        p=body()
        p["patterns"]=["unknown"]
        with self.assertRaisesRegex(ValueError,"Pattern IDs"):
            ards2.validate_package(p)
        p=body()
        p["model"]["parameters"]["threshold"]="four"
        self.assertEqual(ards2.verify_body(p)["outcome"],"failed")


if __name__=="__main__":
    unittest.main()
