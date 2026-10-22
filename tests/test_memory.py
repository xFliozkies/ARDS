import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "scripts"))
import memory
import analytics


def selection(previous, continued=False):
    return {
      "topic_id":86 if continued else 43,
      "topic_label":"Missing Elements" if continued else "Connectivity and components",
      "difficulty":3,
      "continuation":continued,
      "story":not continued,
      "presentation":"direct" if continued else "story",
      "historical_catalog_mismatch":continued,
      "rolls":{"O":2 if continued else 99,"X":None if continued else 142,
               "Y":56,"P":99 if continued else 24},
    }


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/"test.db"
        self.conn=memory.connect(self.db)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def seed(self):
        items=memory.import_legacy(self.conn,root=ROOT/"tests"/"fixtures"/"legacy")
        self.assertEqual(items, ["B1","RACG-0002"])

    def selected(self):
        self.seed()
        return memory.record_random_selection(self.conn,lambda previous: selection(previous))

    def presented(self):
        s=self.selected()
        memory.present_challenge(self.conn,s["external_id"],"Connected Places",
                                 "Given a graph, find the number of connected components.",
                                 {"N_max":100000})
        return s["external_id"]

    def test_import_is_idempotent_and_preserves_large_historical_rolls(self):
        self.seed()
        self.assertEqual(memory.import_legacy(self.conn,root=ROOT/"tests"/"fixtures"/"legacy"),[])
        r=memory.get_challenge(self.conn,"RACG-0002")
        self.assertEqual((r["roll_x"],r["roll_y"],r["roll_p"]), (757785,75816,91))
        self.assertEqual(r["topic_label"],"Missing Elements")
        self.assertEqual(memory.get_challenge(self.conn,"B1")["status"],"evaluated")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],1)

    def test_draw_in_db_is_pending_and_id_unique(self):
        s=self.selected()
        self.assertEqual(s["external_id"],"RACG-0003")
        self.assertEqual(memory.get_challenge(self.conn,"RACG-0003")["roll_p"],24)
        with self.assertRaisesRegex(ValueError,"Unpresented"):
            memory.record_random_selection(self.conn,lambda previous: selection(previous))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],3)

    def test_continuation_from_legacy_preserves_actual_topic(self):
        self.seed()
        r=memory.record_random_selection(self.conn,lambda previous: selection(previous,True))
        self.assertTrue(r["continuation"])
        self.assertIsNone(r["rolls"]["X"])
        self.assertEqual(r["topic_label"],"Missing Elements")
        self.assertEqual(r["difficulty"],3)

    def test_invalid_rolls_rollback_without_new_challenge(self):
        self.seed()
        with self.assertRaisesRegex(ValueError,"Invalid O/Y/P"):
            memory.record_random_selection(self.conn,
                lambda previous: dict(selection(previous),rolls={"O":1,"X":1,"Y":1,"P":101}))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],2)

    def test_present_only_once_and_fts_indexes_statement(self):
        ident=self.presented()
        self.assertEqual(memory.get_challenge(self.conn,ident)["status"],"presented")
        self.assertIn(ident,[r["external_id"] for r in memory.search(self.conn,"connected graph")])
        with self.assertRaisesRegex(ValueError,"selected"):
            memory.present_challenge(self.conn,ident,"Other title","Different statement")

    def test_attempt_first_is_immutable_and_revision_is_distinct(self):
        ident=self.presented()
        first=memory.add_attempt(self.conn,ident,"I would do a DFS.",hint_level=0,independent=True,
                          confidence=80,minutes=7.5,time_source="self-reported")
        self.assertTrue(self.conn.execute("SELECT independent FROM attempts WHERE id=?",(first,)).fetchone()[0])
        with self.assertRaisesRegex(ValueError,"immutable"):
            memory.add_attempt(self.conn,ident,"A revised fake first.",hint_level=0)
        revision=memory.add_attempt(self.conn,ident,"I updated the approach.",
                          stage="revision",hint_level=2)
        self.assertNotEqual(first,revision)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM attempts WHERE challenge_id=(SELECT id FROM challenges WHERE external_id=?)",(ident,)).fetchone()[0],2)

    def test_duplicate_check_reports_exact_and_lexical_without_changing_draw(self):
        first=self.presented()
        next_draw=memory.record_random_selection(self.conn,lambda previous: selection(previous))
        result=memory.present_challenge(self.conn,next_draw["external_id"],"Connected Places",
                      "Given a graph, find the number of connected components.",
                      {"N_max":100000})
        self.assertIn(first,result["duplicate_check"]["exact_duplicates"])
        self.assertTrue(any(x["external_id"]==first for x in
                            result["duplicate_check"]["lexical_candidates"]))
        self.assertEqual(result["topic_id"],next_draw["topic_id"])
        self.assertEqual(result["roll_p"],next_draw["rolls"]["P"])

    def test_no_independence_without_confirmed_zero_hints(self):
        ident=self.presented()
        aid=memory.add_attempt(self.conn,ident,"I think I can use a stack.")
        self.assertEqual(self.conn.execute("SELECT independent FROM attempts WHERE id=?",(aid,)).fetchone()[0],0)
        with self.assertRaises(ValueError):
            memory.add_attempt(self.conn,ident,"Revision",stage="revision",independent=True,hint_level=0)

    def test_assessments_append_and_incomplete_scores_are_null(self):
        ident=self.presented()
        aid=memory.add_attempt(self.conn,ident,"DFS from every unvisited node.",
                               hint_level=0,confidence=75)
        first=memory.add_assessment(self.conn,aid,"assistant",correct=True,optimality=True,
              time_complexity="O(V+E)",scores={"modeling":3},
              evidence="DFS visits each connected component")
        second=memory.add_assessment(self.conn,aid,"second-review",correct=False,
              evidence="Hypothetical disagreement; do not replace first review")
        self.assertNotEqual(first,second)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM assessments WHERE attempt_id=?",(aid,)).fetchone()[0],2)
        self.assertIsNone(self.conn.execute("SELECT complexity FROM assessments WHERE id=?",(first,)).fetchone()[0])

    def test_observation_evidence_and_attempt_must_match(self):
        ident=self.presented()
        aid=memory.add_attempt(self.conn,ident,"DFS visits neighbors",hint_level=0)
        oid=memory.add_observation(self.conn,ident,"insight","Connectivity",
                     "Learner explicitly mentioned exploring neighbors.",aid)
        self.assertGreater(oid,0)
        with self.assertRaises(ValueError):
            memory.add_observation(self.conn,"RACG-0002","weakness","Graphs","No evidence",aid)

    def test_search_quotes_sql_and_fts_integrity(self):
        self.seed()
        results=memory.search(self.conn,'"missing"; DROP TABLE challenges;')
        self.assertTrue(any(r["external_id"]=="RACG-0002" for r in results))
        report=memory.doctor(self.conn)
        self.assertEqual(report["integrity_check"],"ok")
        self.assertEqual(report["foreign_key_errors"],[])
        self.assertEqual(report["fts_consistency"],"ok")

    def test_near_is_lexical_and_does_not_use_opaque_vector(self):
        self.seed()
        out=memory.near(self.conn,"What is the smallest positive integer missing from an array?")
        self.assertEqual(out[0]["external_id"],"RACG-0002")
        self.assertTrue(0<out[0]["lexical_cosine"]<=1)

    def test_statistics_are_conservative(self):
        self.seed()
        report=analytics.summarise(self.conn)
        self.assertEqual(report["independent_first_attempts_graded"],1)
        self.assertEqual(report["independent_first_attempts_correct"],1)
        self.assertIsNone(report["calibration"]["brier_score"])
        self.assertEqual(report["historical_summary_only_attempts"],1)

    def test_abandon_requires_justification(self):
        s=self.selected()
        with self.assertRaises(ValueError):
            memory.abandon_selection(self.conn,s["external_id"]," ")
        memory.abandon_selection(self.conn,s["external_id"],"No verified problem was authored.")
        self.assertEqual(memory.get_challenge(self.conn,s["external_id"])["status"],"abandoned")
        self.assertEqual(memory.latest_racg(self.conn)["external_id"],"RACG-0002")
        s2=memory.record_random_selection(self.conn,lambda prev: selection(prev))
        self.assertEqual(s2["external_id"],"RACG-0004")


if __name__=="__main__":
    unittest.main()
