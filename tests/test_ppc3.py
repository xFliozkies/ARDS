"""PPC 3.0 small proof kernel: positive and adversarial conformance suite."""
import copy
import json
import random
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ppc3


def v(name):
    return {"op":"var","name":name}


def binary(op,a,b):
    return {"op":op,"left":a,"right":b}


def h(name):
    return {"rule":"hyp","name":name}


def swap(a,b):
    return {
        "kind":"propositional",
        "assumptions":{"pair":binary("and",v(a),v(b))},
        "conclusion":binary("and",v(b),v(a)),
        "proof":{"rule":"and_intro",
                 "left":{"rule":"and_right","source":h("pair")},
                 "right":{"rule":"and_left","source":h("pair")}}}


def compose(a,b,c):
    return {
        "kind":"propositional",
        "assumptions":{"pq":binary("imp",v(a),v(b)),
                       "qr":binary("imp",v(b),v(c))},
        "conclusion":binary("imp",v(a),v(c)),
        "proof":{"rule":"imp_intro","name":"localP","assumption":v(a),
                 "body":{"rule":"imp_elim","imp":h("qr"),
                         "arg":{"rule":"imp_elim","imp":h("pq"),
                                "arg":h("localP")}}}}


def machine(seed):
    rnd=random.Random(seed)
    domain=list(range(1+rnd.randrange(4)))
    cases=[]
    for n in domain:
        output=n*n+seed
        size=2+rnd.randrange(5)
        states={}
        for i in range(size):
            succ=["s"+str(i+1)] if i<size-1 else []
            if i+2<size and rnd.random()<0.4:
                succ.append("s"+str(i+2))
            states["s"+str(i)]={"halt":i==size-1,"next":succ,"output":output}
        cases.append({"input_id":n,"states":states,"initial":["s0"],
                      "allowed_outputs":[output]})
    return {"kind":"finite_transition_system","input_domain":domain,"cases":cases}


class PPC3Tests(unittest.TestCase):
    def test_propositional_rules_prove_100_cases_with_truth_table_audit(self):
        certs=[swap("p"+str(i),"q"+str(i)) if i%2==0 else
               compose("p"+str(i),"q"+str(i),"r"+str(i))
               for i in range(100)]
        self.assertEqual(len({ppc3.fingerprint(c) for c in certs}),100)
        for cert in certs:
            result=ppc3.check_proposition(cert)
            self.assertEqual(result["status"],"fragment_machine_checked",result)
            self.assertTrue(result["truth_table"]["entailed"])
            self.assertTrue(result["truth_table"]["audited"])

    def test_100_explicit_finite_state_models_prove_total_correctness(self):
        generated=[machine(seed) for seed in range(100)]
        self.assertEqual(len({ppc3.fingerprint(m) for m in generated}),100)
        for cert in generated:
            result=ppc3.check_machine(cert)
            self.assertEqual(result["status"],"finite_domain_machine_checked",result)
            self.assertGreaterEqual(result["reachable_states"],2)

    def test_false_goal_is_rejected_even_with_valid_proof_term(self):
        obj=swap("P","Q")
        obj["conclusion"]=v("P")
        self.assertEqual(ppc3.check_proposition(obj)["status"],"rejected")

    def test_forged_assumption_is_rejected(self):
        obj=swap("P","Q")
        obj["proof"]["left"]=h("forged")
        self.assertEqual(ppc3.check_proposition(obj)["status"],"rejected")

    def test_unproven_axiom_and_sorry_like_holes_are_rejected(self):
        obj=swap("P","Q")
        obj["proof"]={"rule":"axiom","conclusion":obj["conclusion"]}
        self.assertEqual(ppc3.check_proposition(obj)["status"],"rejected")
        obj["proof"]={"rule":"sorry"}
        self.assertEqual(ppc3.check_proposition(obj)["status"],"rejected")

    def test_disjunction_elimination_requires_matching_branches(self):
        obj={"kind":"propositional",
             "assumptions":{"disjunction":binary("or",v("A"),v("B"))},
             "conclusion":binary("or",v("B"),v("A")),
             "proof":{
                 "rule":"or_elim","source":h("disjunction"),
                 "left_name":"left","right_name":"right",
                 "left_proof":{"rule":"or_right","other":v("B"),"proof":h("left")},
                 "right_proof":{"rule":"or_left","other":v("A"),"proof":h("right")}}}
        # Both branches derive B∨A.
        self.assertEqual(ppc3.check_proposition(obj)["status"],"fragment_machine_checked")
        obj["proof"]["right_proof"]={"rule":"hyp","name":"right"}
        self.assertEqual(ppc3.check_proposition(obj)["status"],"rejected")

    def test_truth_table_can_identify_countermodel(self):
        premises={"h":ppc3.parse_formula(v("P"))}
        goal=ppc3.parse_formula(v("Q"))
        a=ppc3.audit_truth_table(premises,goal)
        self.assertTrue(a["audited"])
        self.assertFalse(a["entailed"])
        self.assertTrue(a["countermodel"]["P"])
        self.assertFalse(a["countermodel"]["Q"])

    def test_finite_machine_rejects_nontermination(self):
        cert=machine(2)
        nodes=cert["cases"][0]["states"]
        nodes["s1"]["next"]=["s1"]
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_finite_machine_rejects_bad_terminal_output(self):
        cert=machine(2)
        cert["cases"][0]["allowed_outputs"]=["wrong"]
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_finite_machine_rejects_deadlock(self):
        cert=machine(2)
        states=cert["cases"][0]["states"]
        states["s0"]["next"]=[]
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_finite_machine_rejects_missing_input_case(self):
        cert=machine(2)
        cert["cases"].pop()
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_finite_machine_rejects_dangling_edge(self):
        cert=machine(2)
        cert["cases"][0]["states"]["s0"]["next"]=["does_not_exist"]
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_finite_machine_rejects_terminal_that_keeps_running(self):
        cert=machine(2)
        states=cert["cases"][0]["states"]
        final=list(states)[-1]
        states[final]["next"]=["s0"]
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_finite_machine_rejects_duplicate_inputs(self):
        cert=machine(2)
        cert["input_domain"].append(cert["input_domain"][0])
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_finite_machine_nondeterministic_infinite_branch_fails(self):
        cert=machine(2)
        states=cert["cases"][0]["states"]
        states["s0"]["next"].append("s0")
        self.assertEqual(ppc3.check_machine(cert)["status"],"rejected")

    def test_ards_package_bound_fragment_check_and_no_proof_promotion(self):
        import ards2
        import ppc2
        package=ppc2.make_problem(0,random.Random(101))
        proof=swap("X","Y")
        package["ppc3"]={"model_hash":ppc3.fingerprint(package["model"]),
                         "scope":"auxiliary_propositional_lemma",
                         "certificate":proof}
        res=ards2.verify_body(package)
        self.assertEqual(res["outcome"],"test_verified")
        self.assertNotIn("machine_checked",res["outcome"])
        bad=copy.deepcopy(package)
        bad["ppc3"]["certificate"]["conclusion"]=v("X")
        self.assertEqual(ards2.verify_body(bad)["outcome"],"failed")
        bad=copy.deepcopy(package)
        bad["ppc3"]["model_hash"]="0"*64
        self.assertEqual(ards2.verify_body(bad)["outcome"],"failed")

    def test_100_adversarial_mutations_do_not_receive_certificate(self):
        for seed in range(100):
            proof=swap("P"+str(seed),"Q"+str(seed))
            # New atomic proposition is not entailed by the existing pair.
            proof["conclusion"]=v("Unrelated"+str(seed))
            self.assertEqual(ppc3.check_proposition(proof)["status"],"rejected")
            graph=machine(seed)
            # The first state lies on a path from an initial state and now loops.
            graph["cases"][0]["states"]["s0"]["next"]=["s0"]
            self.assertEqual(ppc3.check_machine(graph)["status"],"rejected")

    def test_lean_bridge_axiom_validation_is_strict(self):
        import ppc3_lean
        accepted=("'PPC3.cakeCost_correct' depends on axioms: [propext]\n"
                  "'PPC3.conjunction_swap' does not depend on any axioms\n"
                  "'PPC3.implication_compose' does not depend on any axioms\n")
        self.assertEqual(ppc3_lean._axioms(accepted)["PPC3.cakeCost_correct"],["propext"])
        with self.assertRaises(ValueError):
            ppc3_lean._axioms(accepted.replace("[propext]","[sorryAx]"))
        with self.assertRaises(ValueError):
            ppc3_lean._axioms(accepted.replace("[propext]","[Classical.choice]"))
        with self.assertRaises(ValueError):
            ppc3_lean._axioms(accepted.replace("'PPC3.conjunction_swap' does not depend on any axioms\n",""))

    def test_lean_bridge_checks_real_examples_if_installed(self):
        import ppc3_lean
        if not ppc3_lean._tool("lean") or not ppc3_lean._tool("leanchecker"):
            self.skipTest("Lean or leanchecker not installed")
        result=ppc3_lean.check_examples()
        self.assertEqual(result["status"],"lean_example_checked",result)
        self.assertTrue(result["lean_kernel_checked"])
        self.assertEqual(result["axiom_dependencies"]["PPC3.conjunction_swap"],[])

    def test_lean_status_does_not_claim_execution(self):
        result=ppc3.lean_status()
        self.assertFalse(result["machine_checked_by_lean"])
        self.assertTrue(Path(result["lean_example"]).exists())


if __name__=="__main__":
    unittest.main()
