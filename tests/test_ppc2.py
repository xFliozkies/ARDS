"""PPC 2.0 contract, negative controls and ARDS dual-benchmark regressions."""
import copy
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ppc2
import ards2
import racg


class PPC2Tests(unittest.TestCase):
    def fixture(self, i=0):
        return ppc2.make_problem(i,random.Random(20261020+i))

    def test_contract_valid_for_each_proof_technique(self):
        techniques=set()
        for i in range(7):
            obj=self.fixture(i)
            verified=ppc2.check_certificate(obj)
            self.assertEqual(verified["status"],"structure_checked",verified)
            self.assertFalse(verified["proof_checked"])
            techniques.add(verified["technique"])
            self.assertEqual(ards2.verify_body(obj)["outcome"],"test_verified")
        self.assertEqual(len(techniques),6)  # seven families, six proof techniques

    def test_reject_missing_required_obligations(self):
        for i in range(7):
            obj=self.fixture(i)
            ob=obj["ppc"]["obligations"]
            obj["ppc"]["obligations"]=[x for x in ob if x["id"]!="termination"]
            self.assertEqual(ppc2.check_certificate(obj)["status"],"rejected")

    def test_reject_false_proof_labels_and_wrong_model_hash(self):
        obj=self.fixture()
        obj["ppc"]["asserted_status"]="machine_checked"
        self.assertEqual(ppc2.check_certificate(obj)["status"],"rejected")
        obj=self.fixture()
        obj["model"]["parameters"]["full"]+=1
        self.assertEqual(ppc2.check_certificate(obj)["status"],"rejected")

    def test_reject_invalid_dependency_graph_and_non_object_sections(self):
        obj=self.fixture()
        obj["ppc"]["obligations"][0]["depends_on"]=[obj["ppc"]["obligations"][0]["id"]]
        self.assertEqual(ppc2.check_certificate(obj)["status"],"rejected")
        obj=self.fixture()
        obj["ppc"]["problem"]=[]
        self.assertEqual(ppc2.check_certificate(obj)["status"],"rejected")
        obj=self.fixture()
        obj["ppc"]["obligations"][0]["depends_on"]=["not-a-lemma"]
        self.assertEqual(ppc2.check_certificate(obj)["status"],"rejected")

    def test_false_samples_fail_in_all_seven_families(self):
        for i in range(7):
            obj=self.fixture(i)
            obj["samples"][0]["output"]="not-the-answer"
            self.assertEqual(ards2.verify_body(obj)["outcome"],"failed",obj["id"])

    def test_algorithm_edge_cases(self):
        self.assertEqual(ppc2._missing_fast([]),1)
        self.assertEqual(ppc2._missing_fast([1,2,3]),4)
        self.assertEqual(ppc2._missing_fast([1,1,0,-5]),2)
        self.assertEqual(ppc2._lamps_fast([0,0,4,4],0),2)
        self.assertEqual(ppc2._lamps_oracle([0,0,4,4],0),2)
        self.assertEqual(ppc2._lamps_fast([1,2,3,4,5],1),2)
        self.assertFalse(ppc2._graph_fast(3,[(0,1)],0,2,True))
        self.assertTrue(ppc2._graph_oracle(3,[(0,1),(1,2)],0,2,True))

    def test_deterministic_100_problem_stress_and_immutability(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=ppc2.run_stress(100,20261020,tmp)
            self.assertEqual(first["generated"],100)
            self.assertEqual(first["dual_pass"],100, [x for x in first["results"] if x["problems"]])
            self.assertEqual(first["dual_fail"],0)
            self.assertEqual(len(first["families"]),7)
            self.assertEqual(first["unique_full_package_hashes"],100)
            self.assertGreater(first["finite_checks"],100000)
            self.assertTrue(all(first["negative_controls"].values()))
            self.assertEqual(first["proofs_machine_checked"],0)
            stored=Path(tmp)/"seed-20261020-n100"
            self.assertEqual(len((stored/"problems.jsonl").read_text().splitlines()),100)
            second=ppc2.run_stress(100,20261020,tmp)
            self.assertEqual(first,second)
            (stored/"report.json").write_text("tampered",encoding="utf-8")
            with self.assertRaises(FileExistsError):
                ppc2.run_stress(100,20261020,tmp)

    def test_new_families_can_pass_full_ards_release_and_teacher_export(self):
        import memory
        with tempfile.TemporaryDirectory() as tmp:
            con=memory.connect(Path(tmp)/"ards.db")
            try:
                cases=[(3,"Arrays"),(4,"Arrays"),(5,"Greedy choices"),(6,"Graph reachability")]
                for i,topic in cases:
                    p=self.fixture(i)
                    selection=lambda previous,i=i,topic=topic,p=p: {
                        "topic_id":20+i,"topic_label":topic,
                        "difficulty":p["difficulty_estimate"],"continuation":False,
                        "story":False,"presentation":"direct",
                        "rolls":{"O":99,"X":19+i,"Y":1+sum(racg.DIFFICULTY_WEIGHTS[:p["difficulty_estimate"]-1]),"P":99}}
                    ident=memory.record_random_selection(con,selection)["external_id"]
                    planned=ards2.plan(con,ident,randbelow=lambda n:0)
                    if planned["primary_pattern"] not in p["patterns"]:
                        p["patterns"].append(planned["primary_pattern"])
                    ards2.register(con,ident,p)
                    self.assertEqual(ards2.verify(con,ident)["outcome"],"test_verified")
                    self.assertTrue(ards2.release(con,ident)["released"])
                    student=ards2.export_text(con,ident,"student")
                    teacher=ards2.export_text(con,ident,"teacher")
                    self.assertNotIn("PPC 2.0 proof-obligation",student)
                    self.assertIn("PPC 2.0 proof-obligation",teacher)
                    self.assertIn("not machine-proved",teacher)
                self.assertEqual(memory.doctor(con)["integrity_check"],"ok")
            finally:
                con.close()

    def test_no_modification_to_live_racg_during_stress(self):
        # Only temp paths; PPC generator must not import the production DB or draw O/X/Y/P.
        with tempfile.TemporaryDirectory() as tmp:
            ppc2.run_stress(7,771,tmp)
            p=Path(tmp)/"seed-771-n7"/"problems.jsonl"
            for raw in p.read_text().splitlines():
                case=json.loads(raw)
                self.assertTrue(case["provenance"].startswith("PPC 2.0 deterministic"))
                self.assertNotIn("rolls",case)
                self.assertNotIn("external_id",case)


if __name__ == "__main__":
    unittest.main()
