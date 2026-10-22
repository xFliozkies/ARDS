import sqlite3
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import memory
import racg
import ards2
import ards_batch


def as_text_stdin(body):
    package=copy.deepcopy(body)
    package["io_contract"]={"encoding":"stdin_tokens_v1"}
    package["model"]["parameters"].update(
        input_encoding="stdin_tokens",output_encoding="stdout_text")
    samples=package["samples"]
    if len(samples)<2:
        samples.append({"input":"2","output":"2"})
    package["statement_display"]={
        "description":package["statement"],
        "input_format":"Read a single valid input token N.",
        "output_format":"Print the required answer as text.",
        "constraints":package["model"]["constraints"],
        "samples":[dict(s) for s in samples]}
    return package


class CycleRng:
    """Deterministic bounded RNG exclusively for isolated unit tests."""
    def __init__(self):
        self.calls = 0
    def __call__(self, n):
        self.calls += 1
        return (self.calls * 17 + 9) % n


class ARDSBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = memory.connect(Path(self.tmp.name) / "ards.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_clean_database_status_and_next_are_empty(self):
        overview=ards_batch.status(self.con)
        self.assertEqual(overview["total"],0)
        self.assertEqual(overview["by_stage"]["released"],0)
        self.assertIsNone(ards_batch.next_item(self.con)["next"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],0)

    def test_batch_100_authentic_draws_and_all_plans(self):
        result = ards_batch.create_batch(self.con, 100, CycleRng())
        self.assertEqual(result["first_id"], "RACG-0001")
        self.assertEqual(result["last_id"], "RACG-0100")
        self.assertEqual(result["generated_statements"], 0)
        all_rows = ards_batch.status(self.con, result["batch_id"], full=True)["items"]
        self.assertEqual(len(all_rows),100)
        self.assertEqual([x["ordinal"] for x in all_rows],list(range(1,101)))
        self.assertEqual(len({x["external_id"] for x in all_rows}),100)
        self.assertEqual(len({x["challenge_id"] for x in all_rows}),100)
        self.assertTrue(all(x["status"]=="selected" for x in self.con.execute(
            "SELECT status FROM challenges WHERE session_type='RACG'")))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM releases").fetchone()[0],0)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM reasoning_plans").fetchone()[0],100)
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["drawn"],100)
        self.assertEqual(ards_batch.next_item(self.con)["next"]["external_id"],"RACG-0001")
        previous = None
        for row in all_rows:
            expected_cont = row["roll_o"] <= 15 and previous is not None
            self.assertEqual(bool(row["continuation"]),expected_cont)
            self.assertEqual(row["presentation"],"story" if row["roll_p"]<=70 else "direct")
            if expected_cont:
                self.assertIsNone(row["roll_x"])
                self.assertEqual(row["topic_id"],previous["topic_id"])
                self.assertEqual(row["topic_label"],previous["topic_label"])
                self.assertGreaterEqual(row["difficulty"],previous["difficulty"])
            else:
                self.assertIsInstance(row["roll_x"],int)
                self.assertEqual(row["topic_id"],1+row["roll_x"]%100)
            self.assertIsInstance(row["z"],int)
            self.assertTrue(row["primary_pattern"])
            min_level = previous["difficulty"] if expected_cont else 1
            self.assertTrue(1 <= row["roll_y"] <= racg.difficulty_roll_size(min_level))
            self.assertEqual(row["difficulty"],racg.difficulty_from_roll(
                row["roll_y"],min_level))
            previous=row
        self.assertEqual(self.con.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        with self.assertRaisesRegex(ValueError,"Open batch"):
            ards_batch.create_batch(self.con,100,CycleRng())
        # The old single-selection tool correctly refuses while a batch exists;
        # agent must use 'next' and NOT reroll.
        with self.assertRaisesRegex(ValueError,"Unpresented"):
            memory.record_random_selection(self.con,racg.draw)

    def test_explicit_parallel_batch_extends_ids_without_hijacking_default(self):
        original=ards_batch.create_batch(self.con,5,CycleRng())
        first=ards_batch.status(self.con)
        self.assertEqual(first["batch_id"],original["batch_id"])
        with self.assertRaisesRegex(ValueError,"Open batch"):
            ards_batch.create_batch(self.con,2,CycleRng())
        extra=ards_batch.create_batch(self.con,20,CycleRng(),
                                     provenance="learner-additional-20",parallel=True)
        self.assertEqual(extra["first_id"],"RACG-0006")
        self.assertEqual(extra["last_id"],"RACG-0025")
        self.assertEqual(extra["generated_statements"],0)
        self.assertEqual(ards_batch.status(self.con)["batch_id"],original["batch_id"])
        self.assertEqual(ards_batch.next_item(self.con)["next"]["external_id"],"RACG-0001")
        self.assertEqual(ards_batch.status(self.con,extra["batch_id"])["total"],20)
        self.assertEqual(ards_batch.next_item(self.con,extra["batch_id"])["next"]["external_id"],"RACG-0006")
        self.assertEqual(ards_batch.status(self.con,original["batch_id"],True)["items"][-1]["external_id"],"RACG-0005")
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM reasoning_plans").fetchone()[0],25)

    def test_adopts_existing_pending_problem_without_changing_rolls_or_package(self):
        sampler=lambda previous:{
            "topic_id":43,"topic_label":"Mathematics","difficulty":3,
            "continuation":False,"story":True,"presentation":"story",
            "rolls":{"O":99,"X":142,"Y":56,"P":24}}
        old = memory.record_random_selection(self.con,sampler)
        old_id = old["external_id"]
        original = dict(self.con.execute(
            "SELECT * FROM challenges WHERE external_id=?",(old_id,)).fetchone())
        plan = ards2.plan(self.con,old_id,randbelow=lambda n:0)
        result = ards_batch.create_batch(self.con,8,CycleRng())
        self.assertEqual(result["adopted_existing"],old_id)
        self.assertEqual(result["first_id"],old_id)
        self.assertEqual(result["last_id"],"RACG-0008")
        now = dict(self.con.execute(
            "SELECT * FROM challenges WHERE external_id=?",(old_id,)).fetchone())
        self.assertEqual(original,now)
        self.assertEqual(ards2.inspect(self.con,old_id)["plan"]["primary_pattern"],
                         plan["primary_pattern"])

    def test_no_partial_batch_when_randomness_fails(self):
        class FailsAfter:
            def __init__(self):self.n=0
            def __call__(self,limit):
                self.n+=1
                if self.n>11:
                    raise RuntimeError("injected RNG failure")
                return 0
        with self.assertRaisesRegex(RuntimeError,"injected RNG failure"):
            ards_batch.create_batch(self.con,10,FailsAfter())
        for table in ("challenges","authoring_batches","authoring_batch_items","reasoning_plans"):
            self.assertEqual(self.con.execute("SELECT COUNT(*) FROM "+table).fetchone()[0],0)

    def test_unsupported_family_does_not_block_next_queue_item(self):
        ards_batch.create_batch(self.con,3,CycleRng())
        first=ards_batch.next_item(self.con)["next"]
        package={
          "title":"An unsupported review-only model",
          "statement":"Given valid inputs, determine the optimal certified object in the finite model.",
          "model":{"inputs":{"N":"Integer in [1,5]"},"hidden_variables":[],
                   "constraints":["1 <= N <= 5"],"objective":"Minimize the model objective",
                   "family":"new_unreviewed_family","parameters":{}},
          "patterns":[first["primary_pattern"]],
          "reference_solution":"Enumerate all candidates and select the minimum.",
          "proof":"An exhaustive finite search considers all feasible candidates; a finite minimum exists.",
          "teacher_ppc":{"problem":"Define finite input set and objective.",
                         "procedure":"Enumerate all candidates in a finite search.",
                         "correctness":"Exhaustive search is complete and terminates.",
                         "complexity":"Time bounded by candidate count, plus constant auxiliary state."},
          "samples":[{"input":"1","output":"1"}],
          "difficulty_estimate":first["difficulty"],
          "provenance":"isolated authored test package"
        }
        ards2.register(self.con,first["external_id"],as_text_stdin(package))
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["drafted"],1)
        verification=ards2.verify(self.con,first["external_id"])
        self.assertNotEqual(verification["outcome"],"test_verified")
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["under_review"],1)
        with self.assertRaises(ValueError):
            ards2.release(self.con,first["external_id"])
        self.assertEqual(ards_batch.next_item(self.con)["next"]["ordinal"],2)
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["released"],0)

    def test_review_reject_reopen_does_not_change_draw(self):
        ards_batch.create_batch(self.con,4,CycleRng())
        selected=ards_batch.next_item(self.con)["next"]
        identity=(selected["roll_o"],selected["roll_x"],selected["roll_y"],selected["roll_p"])
        ards_batch.mark_review(self.con,selected["external_id"],"No reviewed verifier yet")
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["under_review"],1)
        ards_batch.mark_review(self.con,selected["external_id"],"Fault in statement",True)
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["rejected"],1)
        with self.assertRaisesRegex(ValueError,"reopen"):
            ards_batch.mark_review(self.con,selected["external_id"],"oops")
        ards_batch.reopen(self.con,selected["external_id"],"Review requested")
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["drawn"],4)
        replay=ards_batch.next_item(self.con)["next"]
        self.assertEqual(identity,(replay["roll_o"],replay["roll_x"],replay["roll_y"],replay["roll_p"]))


    def test_first_normal_single_draw_from_fresh_db_starts_at_0001(self):
        def fixed(previous):
            self.assertIsNone(previous)
            return {"topic_id":43,"topic_label":"Mathematics","difficulty":3,
                    "continuation":False,"story":True,"presentation":"story",
                    "rolls":{"O":99,"X":42,"Y":56,"P":24}}
        result=memory.record_random_selection(self.con,fixed)
        self.assertEqual(result["external_id"],"RACG-0001")

    def test_first_party_verification_does_not_publish_batch_item(self):
        from test_ards2 import body
        class ChosenRolls:
            def __init__(self):self.values=iter([98,0,55,23,0])
            def __call__(self,n):
                val=next(self.values)
                self_check=0<=val<n
                if not self_check:raise AssertionError("wrong RNG bound")
                return val
        ards_batch.create_batch(self.con,1,ChosenRolls())
        entry=ards_batch.next_item(self.con)["next"]
        self.assertEqual(entry["topic_label"],"Algebraic modeling")
        self.assertEqual(entry["difficulty"],3)
        package=ards2.prepare_reference(as_text_stdin(body(primary=entry["primary_pattern"])))
        ards2.register(self.con,entry["external_id"],package)
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["drafted"],1)
        checked=ards2.verify(self.con,entry["external_id"])
        self.assertEqual(checked["outcome"],"test_verified")
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["under_review"],1)
        with self.assertRaisesRegex(ValueError,"independent review"):
            ards2.release(self.con,entry["external_id"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM releases").fetchone()[0],0)


    def test_corrected_draft_invalidates_old_verification_then_releases(self):
        from test_ards2 import body
        class Fixed:
            def __init__(self):self.values=iter([98,0,55,23,0])
            def __call__(self,n):return next(self.values)
        ards_batch.create_batch(self.con,1,Fixed())
        entry=ards_batch.next_item(self.con)["next"]
        original=ards2.prepare_reference(as_text_stdin(body(primary=entry["primary_pattern"])))
        ards2.register(self.con,entry["external_id"],original)
        first_verification=ards2.verify(self.con,entry["external_id"])
        self.assertEqual(first_verification["outcome"],"test_verified")
        changed=dict(original)
        changed["proof"]=original["proof"]+" This corrected explanation makes the exact cases explicit."
        changed["teacher_ppc"]=dict(original["teacher_ppc"])
        changed["teacher_ppc"]["correctness"]+=" This refinement is included before release."
        corrected=ards2.prepare_reference(changed)
        amended=ards2.revise_draft(self.con,entry["external_id"],corrected,
                                  "Clarify the teacher correctness proof")
        self.assertEqual(amended["revision"],2)
        self.assertTrue(amended["verification_required_again"])
        self.assertEqual(ards_batch.status(self.con)["by_stage"]["drafted"],1)
        with self.assertRaisesRegex(ValueError,"verification"):
            ards2.release(self.con,entry["external_id"])
        original_package=self.con.execute(
            "SELECT body_hash FROM problem_packages WHERE challenge_id=?",(entry["challenge_id"],)
        ).fetchone()[0]
        self.assertEqual(original_package,ards2.digest(original))
        self.assertNotEqual(original_package,ards2.inspect(self.con,entry["external_id"])["package_hash"])
        self.assertEqual(len(ards2.inspect(self.con,entry["external_id"])["draft_revisions"]),1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("UPDATE authoring_package_revisions SET reason='hacked'")
        self.con.rollback()
        renewed=ards2.verify(self.con,entry["external_id"])
        self.assertEqual(renewed["outcome"],"test_verified")
        with self.assertRaisesRegex(ValueError,"independent review"):
            ards2.release(self.con,entry["external_id"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM releases").fetchone()[0],0)
        self.assertIn(corrected["proof"],ards2.load_package(self.con,
                          ards2.get_challenge(self.con,entry["external_id"]))[1]["proof"])


    def test_queue_rolls_cannot_be_edited_after_selection(self):
        ards_batch.create_batch(self.con,2,CycleRng())
        first=ards_batch.next_item(self.con)["next"]
        with self.assertRaisesRegex(sqlite3.IntegrityError,"queued Classic RACG draw is immutable"):
            self.con.execute(
                "UPDATE challenges SET roll_o=roll_o+1 WHERE id=?",(first["challenge_id"],)
            )
        self.con.rollback()
        self.assertEqual(ards_batch.next_item(self.con)["next"]["roll_o"],first["roll_o"])

    def test_batch_does_not_mutate_actual_canonical_archive(self):
        # Each test's canonical path points into its own temporary directory.
        self.assertNotEqual(self.con.execute("PRAGMA database_list").fetchone()["file"],
                            str(memory.DEFAULT_DB))
        ards_batch.create_batch(self.con,4,CycleRng())
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],0)


if __name__=="__main__":
    unittest.main()
