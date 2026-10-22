#!/usr/bin/env python3
"""Reproducible, append-only 100+100 PPC 3.0 conformance corpus.

The corpus tests *restricted* proof checking, NOT universal theorem proving.
No changes to the production SQLite database or classic RACG draws.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))
import ppc3
from benchmark_io import provenance, write_immutable
from test_ppc3 import swap,compose,machine


def run(count=100, seed=20261020, save=True, directory=None):
    if type(count) is not int or not 1<=count<=1000:
        raise ValueError("count must be in 1..1000")
    proofs=[]
    machines=[]
    failures=[]
    for i in range(count):
        p=(swap(f"p{i+seed}",f"q{i+seed}") if i%2==0 else
           compose(f"p{i+seed}",f"q{i+seed}",f"r{i+seed}"))
        m=machine(i+seed)
        a=ppc3.check_proposition(p)
        b=ppc3.check_machine(m)
        proofs.append(p)
        machines.append(m)
        if a["status"]!="fragment_machine_checked":
            failures.append({"index":i,"propositional":a})
        if b["status"]!="finite_domain_machine_checked":
            failures.append({"index":i,"finite_machine":b})
    rejected_proofs=rejected_nontermination=0
    for i in range(count):
        badp=swap("X"+str(i+seed),"Y"+str(i+seed))
        badp["conclusion"]={"op":"var","name":"Unrelated"+str(i+seed)}
        rejected_proofs+=ppc3.check_proposition(badp)["status"]=="rejected"
        badm=machine(i+seed)
        badm["cases"][0]["states"]["s0"]["next"]=["s0"]
        rejected_nontermination+=ppc3.check_machine(badm)["status"]=="rejected"
    neg={"invalid_conclusion_rejected":rejected_proofs==count,
         "nontermination_rejected":rejected_nontermination==count}
    report={"protocol":"PPC 3.0 restricted formal verification",
            "provenance":provenance(),
            "seed":seed,"generated_proposition_proofs":len(proofs),
            "generated_finite_models":len(machines),
            "passed":2*count-len(failures),
            "failed":len(failures),
            "negative_controls":neg,
            "adversarial_cases_checked":2*count,
            "adversarial_cases_rejected":rejected_proofs+rejected_nontermination,
            "distinct_proofs":len({ppc3.fingerprint(p) for p in proofs}),
            "distinct_models":len({ppc3.fingerprint(m) for m in machines}),
            "lean_theorems_checked":0,
            "unrestricted_algorithms_proven":0,
            "scope":"Synthetic propositional proof templates and finite explicitly enumerated machines; not 100 novel mathematical families, not universal algorithm proofs",
            "failures":failures}
    if save:
        base=Path(directory) if directory is not None else ROOT/"data"/"validation"/"ppc3"/"hardened-v1"
        folder=base/f"seed-{seed}-n{count}"
        outputs={"propositions.jsonl":"".join(ppc3.canonical(p)+"\n" for p in proofs),
                 "finite-machines.jsonl":"".join(ppc3.canonical(m)+"\n" for m in machines),
                 "report.json":json.dumps(report,indent=2,ensure_ascii=False)+"\n"}
        write_immutable(folder,outputs)
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--count",type=int,default=100)
    parser.add_argument("--seed",type=int,default=20261020)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    result=run(args.count,args.seed,directory=args.out)
    print(json.dumps(result,indent=2))
    if result["failed"] or not all(result["negative_controls"].values()):
        raise SystemExit(1)
