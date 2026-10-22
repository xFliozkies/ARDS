#!/usr/bin/env python3
"""Evidence-based PPC review packet and structured assessment recording.

This is *not* an automatic theorem prover or an LLM. A separate human/AI
reviewer must inspect the learner's actual PPC and provide detailed evidence.
A draft/submission by itself cannot earn a positive grade.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import memory

FIELDS=("problem","procedure","correctness","complexity")
RESULTS=("supported","incorrect","incomplete","uncertain")
VERDICTS=("correct","incorrect","undetermined")


def attempt_packet(con, attempt_id):
    attempt=con.execute(
        "SELECT a.*,c.external_id,c.title,c.statement,c.status AS challenge_status "
        "FROM attempts a JOIN challenges c ON c.id=a.challenge_id WHERE a.id=?",
        (attempt_id,)
    ).fetchone()
    if attempt is None:
        raise ValueError("Unknown attempt ID")
    # Preserve the learner submission verbatim, without guessing its structure.
    return {
        "attempt_id":attempt_id,"challenge":attempt["external_id"],
        "title":attempt["title"],"statement":attempt["statement"],
        "attempt_stage":attempt["stage"],"independent_attested":bool(attempt["independent"]),
        "submission_verbatim":attempt["submission"],
        "review_instructions":"Evaluate P1/P2/C/K independently. Identify missing preconditions, "
                              "counterexamples, unjustified invariants, and incorrect complexity. "
                              "Do not simply compare wording with a reference. Do not claim formal verification.",
        "reference_ppc_included":False
    }


def validate_report(report):
    if not isinstance(report,dict):
        raise ValueError("Review must be a JSON object")
    if report.get("reviewer_kind") not in ("ai","human"):
        raise ValueError("reviewer_kind must be ai or human")
    if not isinstance(report.get("reviewer"),str) or len(report["reviewer"].strip())<3:
        raise ValueError("A reviewer identity is required")
    if report.get("verdict") not in VERDICTS:
        raise ValueError("Verdict must be correct, incorrect or undetermined")
    if report.get("proof_assurance") not in ("reasoned_review","executed_counterexample","formal_proof"):
        raise ValueError("Unknown proof_assurance; reasoned_review is NOT formal proof")
    sections=report.get("sections")
    if not isinstance(sections,dict) or set(sections)!=set(FIELDS):
        raise ValueError("Each P1/P2/C/K section requires review")
    for field in FIELDS:
        item=sections[field]
        if not isinstance(item,dict) or item.get("status") not in RESULTS:
            raise ValueError("Missing meaningful status for "+field)
        if not isinstance(item.get("finding"),str) or len(item["finding"].strip())<35:
            raise ValueError("Specific finding required for "+field)
        if not isinstance(item.get("evidence"),str) or len(item["evidence"].strip())<45:
            raise ValueError("Mathematical evidence and reasoning required for "+field)
    scores=report.get("scores",{})
    if not isinstance(scores,dict) or set(scores)-set(memory.DIMENSIONS):
        raise ValueError("Unknown rubric dimension")
    for score in scores.values():
        if score is not None and (type(score) is not int or not 0<=score<=4):
            raise ValueError("Rubric values must be 0..4 or null")
    verdict=report["verdict"]
    statuses=[sections[x]["status"] for x in FIELDS]
    if verdict=="correct" and any(s!="supported" for s in statuses):
        raise ValueError("A correct verdict requires supported findings for all four PPC sections")
    if verdict=="incorrect" and "incorrect" not in statuses:
        raise ValueError("An incorrect verdict requires at least one demonstrated incorrect component")
    if verdict=="undetermined" and all(s=="supported" for s in statuses):
        raise ValueError("Undetermined requires an explicit proof gap or uncertainty")
    if report["proof_assurance"]=="formal_proof":
        certificate=report.get("certificate")
        if not isinstance(certificate,dict) or not isinstance(certificate.get("path"),str) or not isinstance(certificate.get("sha256"),str):
            raise ValueError("Formal proof requires independently verifiable certificate metadata")
        # This tool does not verify certificates, so it must not certify formal proof.
        raise ValueError("Formal proof not supported by this assessment command; use the restricted proof verifier")
    if report["proof_assurance"]=="executed_counterexample":
        test=report.get("counterexample")
        if not isinstance(test,dict) or not all(isinstance(test.get(k),str) and test[k].strip()
                                                 for k in ("input","expected","actual","reproduction")):
            raise ValueError("Executed counterexamples require reproducible input, expected, actual and reproduction")
    if verdict=="correct" and report["proof_assurance"]=="executed_counterexample":
        raise ValueError("A failing counterexample cannot support a correct verdict")
    return report


def record(con,attempt_id,report):
    report=validate_report(report)
    packet=attempt_packet(con,attempt_id)
    latest=con.execute(
        "SELECT id FROM assessments WHERE attempt_id=? ORDER BY id DESC LIMIT 1",
        (attempt_id,)
    ).fetchone()
    verdict=report["verdict"]
    formatted={
      "assurance":"AI/human reasoning review, not machine-certified total correctness",
      "learner_attempt_id":attempt_id,
      "original_submission_unchanged":True,
      "reference_ppc_exposure":False,
      "report":report
    }
    evidence=json.dumps(formatted,ensure_ascii=False,sort_keys=True)
    scores=report.get("scores",{})
    if latest and report.get("supersedes_assessment_id")!=latest["id"]:
        raise ValueError("Later assessments must explicitly cite the preceding assessment ID")
    assessment_id=memory.add_assessment(
        con,attempt_id,reviewer=report["reviewer"],
        correct={"correct":True,"incorrect":False,"undetermined":None}[verdict],
        optimality=None,
        scores=scores,
        time_complexity=report.get("time_complexity"),
        space_complexity=report.get("space_complexity"),
        evidence=evidence,
        notes="Reviewer kind: "+report["reviewer_kind"]+"; assurance: "+report["proof_assurance"]
    )
    return {
        "assessment_id":assessment_id,"challenge":packet["challenge"],
        "attempt_id":attempt_id,"verdict":verdict,
        "assurance":"reasoned_review_not_formal_proof",
        "reference_ppc_revealed":False
    }


def main():
    p=argparse.ArgumentParser(description="Review PPC attempts with explicit evidence; does not generate judgments")
    p.add_argument("--db",type=Path,default=memory.DEFAULT_DB)
    sub=p.add_subparsers(dest="action",required=True)
    packet=sub.add_parser("packet",help="Fetch a private review packet for an existing attempt")
    packet.add_argument("attempt_id",type=int)
    assess=sub.add_parser("record",help="Record a completed external reviewer report")
    assess.add_argument("attempt_id",type=int)
    assess.add_argument("--file",type=Path,required=True)
    args=p.parse_args()
    with memory.connect(args.db) as con:
        if args.action=="packet":
            result=attempt_packet(con,args.attempt_id)
        else:
            result=record(con,args.attempt_id,json.loads(args.file.read_text(encoding="utf8")))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
