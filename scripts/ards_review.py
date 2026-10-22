#!/usr/bin/env python3
"""Evidence-backed, per-problem independent review for ARDS.

Review code is TRUSTED LOCAL CODE written separately from the problem author.
Never run arbitrary uploaded scripts here. Reviews test independent candidate
and brute-force oracles; successful checks are NOT mathematical formal proofs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys

# -I isolates the reviewer subprocess from ambient import paths. Explicitly
# trust only this repository's scripts directory for the harness imports.
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ards2
import memory

ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "reviewers"
SEED = 20261020
GENERATED = 180
MIN_UNIQUE = 100
REVIEW_FIELDS = ("specification_analysis", "correctness_analysis",
                 "complexity_analysis", "edge_case_analysis",
                 "independence_statement", "limitations")

# Identifiers are intentionally distinct for *each* recorded difficulty.
# The substantive level criteria and concrete examples live in
# references/specification_comprehension.md.
COMPREHENSION_PROFILES = {
    1: "L1_plain_foundations",
    2: "L2_concrete_relations",
    3: "L3_defined_abstraction",
    4: "L4_standard_domain_terms",
    5: "L5_layered_formalism",
    6: "L6_dense_mathematical_model",
}



def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_path(path, suffix):
    path = Path(path).resolve()
    if path.suffix != suffix or not path.is_relative_to(REVIEWS.resolve()):
        raise ValueError("Reviewer source must reside within reviewers/ and use " + suffix)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Reviewer source not found or is a symlink: " + str(path))
    return path


def validate_review(report, body):
    if not isinstance(report, dict) or report.get("decision") != "approve":
        raise ValueError("A written independent review with decision=approve is required")
    if not isinstance(report.get("reviewer_id"), str) or not report["reviewer_id"].strip():
        raise ValueError("Reviewer identity is required")
    author = body.get("provenance", "")
    if report["reviewer_id"].strip().lower() == author.strip().lower():
        raise ValueError("Reviewer cannot identify as the author")
    for key in REVIEW_FIELDS:
        text = report.get(key)
        if not isinstance(text, str) or len(text.strip()) < 80:
            raise ValueError("Substantive independent review required for " + key)
    if report.get("independently_derived") is not True:
        raise ValueError("Reviewer must describe independent derivation explicitly")
    # A separate specification review is required before algorithmic evidence
    # can authorize publication. This is reviewer attestation, not a proof
    # that the natural-language task is semantically unambiguous.
    audit=report.get("specification_review")
    if not isinstance(audit,dict):
        raise ValueError("Independent specification_review is required for every problem")
    level=body["difficulty_estimate"]
    expected_policy=("accessible_without_topic_prerequisites"
                     if level<=3 else "abstract_interpretation_permitted")
    if audit.get("difficulty")!=level or type(audit.get("difficulty")) is not int:
        raise ValueError("Specification review must match the recorded difficulty")
    if audit.get("comprehension_policy")!=expected_policy:
        raise ValueError("Specification review must apply the correct level-dependent comprehension policy")
    profile=COMPREHENSION_PROFILES.get(level)
    if audit.get("level_profile")!=profile:
        raise ValueError("Specification review must name the exact six-level comprehension profile")
    finding=audit.get("level_specific_evidence")
    if not isinstance(finding,str) or len(finding.strip())<160:
        raise ValueError("Specification review needs a substantive level_specific_evidence analysis")
    quote=audit.get("student_text_quote")
    if not isinstance(quote,str) or len(quote.strip())<12:
        raise ValueError("Specification review must quote a specific learner-visible phrase")
    # Verify a real verbatim phrase is being cited from student-facing content.
    display=body.get("statement_display",{})
    visible=[body.get("statement","")]
    if isinstance(display,dict):
        visible.extend(display.get(key,"") for key in ("description","input_format","output_format")
                       if isinstance(display.get(key),str))
        visible.extend(v for v in display.get("constraints",[]) if isinstance(v,str))
    if not any(quote in text for text in visible):
        raise ValueError("Specification review quotation not found in learner-visible statement")
    for key in ("symbols_and_objects","terminology_and_prerequisites",
                "io_and_output_validity","ambiguity_and_edge_cases"):
        if not isinstance(audit.get(key),str) or len(audit[key].strip())<80:
            raise ValueError("Specification review needs problem-specific evidence for "+key)
    if audit.get("verdict")!="pass":
        raise ValueError("Independent specification review must pass before publication")
    validate_ppc_review(report.get("ppc_review"), body["teacher_ppc"])


def validate_ppc_review(audit, ppc):
    """Check auditable P1-to-C traceability, not the truth of a natural-language proof."""
    if not isinstance(audit, dict) or audit.get("verdict") != "pass":
        raise ValueError("Independent PPC formal review with verdict=pass is required")
    for key in ("input_domain_quote", "output_relation_quote"):
        quote = audit.get(key)
        if not isinstance(quote, str) or len(quote.strip()) < 12 or quote not in ppc["problem"]:
            raise ValueError("PPC review must quote the actual P1 " + key)
    for key in ("claim_quote", "reasoning_quote", "termination_quote"):
        quote = audit.get(key)
        if not isinstance(quote, str) or len(quote.strip()) < 12 or quote not in ppc["correctness"]:
            raise ValueError("PPC review must quote the actual C " + key)
    for key in ("domain_and_output_analysis", "method_and_logical_justification",
                "termination_and_boundaries", "math_presentation_analysis",
                "limitations"):
        value = audit.get(key)
        if not isinstance(value, str) or len(value.strip()) < 100:
            raise ValueError("PPC review requires substantive analysis of " + key)
    if audit.get("all_p1_obligations_covered") is not True:
        raise ValueError("PPC review must explicitly examine coverage of all P1 obligations")
    mappings = audit.get("obligation_mapping")
    if not isinstance(mappings, list) or not mappings:
        raise ValueError("PPC review needs explicit P1-to-C obligation_mapping")
    seen = set()
    for item in mappings:
        if not isinstance(item, dict) or set(item) != {"p1_quote", "c_quote", "justification"}:
            raise ValueError("PPC obligation mapping requires p1_quote, c_quote, justification")
        p1, c, why = (item.get(k) for k in ("p1_quote", "c_quote", "justification"))
        if (not isinstance(p1, str) or len(p1.strip()) < 12 or p1 not in ppc["problem"]
                or not isinstance(c, str) or len(c.strip()) < 12 or c not in ppc["correctness"]
                or not isinstance(why, str) or len(why.strip()) < 80):
            raise ValueError("PPC proof obligations need exact P1/C quotes and a substantive reason")
        if p1 in seen:
            raise ValueError("PPC proof obligation duplicated")
        seen.add(p1)


def _worker(payload):
    # Worker executes only a trusted local reviewer module, NEVER author code.
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (12, 13))
        resource.setrlimit(resource.RLIMIT_AS, (420 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    except (ValueError, OSError):
        pass
    module_path = source_path(payload["module"], ".py")
    spec = importlib.util.spec_from_file_location("ards_independent_reviewer", module_path)
    if not spec or not spec.loader:
        raise ValueError("Reviewer module could not be loaded")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("candidate", "oracle", "edge_cases", "generate_cases"):
        if not callable(getattr(mod, attr, None)):
            raise ValueError("Reviewer module is missing: " + attr)
    if mod.candidate is mod.oracle:
        raise ValueError("Candidate and oracle must be distinct implementations")
    samples = payload["samples"]
    text_io=payload.get("io_encoding")=="stdin_tokens_v1"
    if text_io and not all(callable(getattr(mod,k,None)) for k in ("decode_stdin","encode_stdout")):
        raise ValueError("Text-IO reviewer must implement decode_stdin and encode_stdout")
    edges = mod.edge_cases()
    generated = mod.generate_cases(SEED, GENERATED)
    if not isinstance(edges,list) or len(edges) < 3 or len(edges) > 80:
        raise ValueError("At least three and at most 80 explicit edge cases required")
    if not isinstance(generated,list) or len(generated) < GENERATED or len(generated)>1000:
        raise ValueError("Not enough deterministically generated test cases")
    tests = []
    for sample in samples:
        if text_io:
            tests.append(("sample",mod.decode_stdin(sample["input"]),sample["output"]))
        else:
            tests.append(("sample",json.loads(sample["input"]),json.loads(sample["output"])))
    tests.extend(("edge", case, None) for case in edges)
    tests.extend(("generated", case, None) for case in generated)
    if len({json.dumps(x[1],sort_keys=True,ensure_ascii=False,separators=(",",":")) for x in tests}) < MIN_UNIQUE:
        raise ValueError("Review cases lack input diversity")
    all_hash=hashlib.sha256()
    out_hash=hashlib.sha256()
    checked={"sample":0,"edge":0,"generated":0}
    for tag,case,expected in tests:
        # Force roundtrippable JSON input. Protect against one solver mutating it.
        raw=json.dumps(case,sort_keys=True,ensure_ascii=False,allow_nan=False)
        first=mod.candidate(copy.deepcopy(case))
        second=mod.oracle(copy.deepcopy(case))
        a=json.dumps(first,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":"))
        b=json.dumps(second,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":"))
        if a!=b:
            raise ValueError("Differential disagreement on "+tag+" case "+raw[:350]+": "+a[:200]+" != "+b[:200])
        if tag=="sample":
            if text_io:
                rendered=mod.encode_stdout(first)
                if not isinstance(rendered,str):
                    raise ValueError("encode_stdout must return text")
                if rendered.strip()!=expected.strip():
                    raise ValueError("Official stdout sample mismatch for "+raw[:350])
            else:
                exp=json.dumps(expected,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":"))
                if a!=exp:
                    raise ValueError("Official sample mismatch: "+raw[:350]+" expected "+exp[:200]+" obtained "+a[:200])
        checked[tag]+=1
        all_hash.update((tag+":"+raw+"\n").encode())
        out_hash.update((a+"\n").encode())
    return {"outcome":"passed", "samples":checked["sample"],"edges":checked["edge"],
            "generated":checked["generated"],"tests_run":len(tests),
            "distinct_inputs":len({json.dumps(x[1],sort_keys=True,ensure_ascii=False,separators=(",",":")) for x in tests}),
            "case_set_sha256":all_hash.hexdigest(),"output_set_sha256":out_hash.hexdigest(),
            "seed":SEED,"assurance":"independent_candidate_and_brute_oracle_differential_testing_not_formal_proof"}


def test_module(path, samples, io_encoding=None):
    payload={"module":str(path),"samples":samples,"io_encoding":io_encoding}
    try:
        process=subprocess.run(
            [sys.executable,"-I","-B",str(Path(__file__).resolve()),"worker"],
            input=json.dumps(payload),capture_output=True,text=True,timeout=20,
            cwd=str(ROOT),env={"PYTHONDONTWRITEBYTECODE":"1","PYTHONHASHSEED":"0"}
        )
    except subprocess.TimeoutExpired:
        return {"outcome":"failed","reason":"Reviewer test process exceeded 20 seconds","tests_run":0}
    if process.returncode:
        return {"outcome":"failed","reason":(process.stderr or process.stdout)[-1500:],
                "tests_run":0}
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError:
        return {"outcome":"failed","reason":"Reviewer produced invalid evidence JSON","tests_run":0}


def check(con, challenge_id, module_path, report_path, proposed_body=None):
    mod=source_path(module_path,".py")
    report_file=source_path(report_path,".json")
    challenge=ards2.get_challenge(con,challenge_id)
    batch=con.execute("SELECT 1 FROM authoring_batch_items WHERE challenge_id=?",
                      (challenge["id"],)).fetchone()
    if not batch:
        raise ValueError("Independent review applies only to registered batch challenges")
    if proposed_body is None:
        if challenge["status"]!="selected":
            raise ValueError("For published challenges, provide a corrected proposal with --file")
        package, body=ards2.load_package(con,challenge)
        package_hash=package["body_hash"]
    else:
        if challenge["status"]!="presented":
            raise ValueError("Re-review of a proposed publication revision requires an already released challenge")
        _, old=ards2.latest_published_body(con,challenge)
        body=proposed_body
        if body["model"]["family"]!=old["model"]["family"] or body["difficulty_estimate"]!=challenge["difficulty"]:
            raise ValueError("Publication revision cannot change original mathematical family or difficulty")
        if not ards2.contest_io_ready(body,required=True):
            raise ValueError("Proposed revision must supply independently verified stdin/stdout text samples")
        package_hash=ards2.digest(body)
    ards2.validate_package(body)
    if not ards2.contest_io_ready(body,required=True):
        raise ValueError("Independent batch review requires complete stdin/stdout contract")
    if "teacher_ppc" not in body:
        raise ValueError("Package is missing complete private PPC")
    report=json.loads(report_file.read_text(encoding="utf8"))
    validate_review(report,body)
    result=test_module(mod,body["samples"],body.get("io_contract",{}).get("encoding"))
    evidence={
        "protocol":"independent_review_v1",
        "package_sha256":package_hash,
        "reviewer_id":report["reviewer_id"],"written_review_sha256":sha(report_file),
        "reviewer_module_sha256":sha(mod),
        "review_harness_sha256":sha(Path(__file__)),
        "reviewer_input_protocol":body.get("io_contract",{}).get("encoding"),
        "scope":"Trusted reviewer-written Python candidate vs separately derived oracle; "
                "deterministic cases and written analysis. Not a universal proof.",
        **result
    }
    outcome="passed" if (result.get("outcome")=="passed" and
                         result.get("samples") == len(body["samples"]) and
                         result.get("edges",0)>=3 and result.get("generated",0)>=GENERATED and
                         result.get("distinct_inputs",0)>=MIN_UNIQUE) else "failed"
    with con:
        record=con.execute("""INSERT INTO independent_reviews(
            challenge_id,package_hash,module_path,module_sha256,report_path,report_sha256,
            outcome,tests_run,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (challenge["id"],package_hash,str(mod.relative_to(ROOT)),sha(mod),
             str(report_file.relative_to(ROOT)),sha(report_file),outcome,
             result.get("tests_run",0),ards2.canonical(evidence),ards2.stamp()))
        run=con.execute("""INSERT INTO verification_runs
            (challenge_id,package_hash,outcome,tests_run,details_json,created_at)
            VALUES(?,?,?,?,?,?)""",
            (challenge["id"],package_hash,
             "test_verified" if outcome=="passed" else "failed",
             result.get("tests_run",0),
             ards2.canonical({**evidence,"review_id":record.lastrowid,
                              "review_outcome":outcome}),
             ards2.stamp()))
    return {"challenge":challenge_id,"review_id":record.lastrowid,
            "verification_id":run.lastrowid,"outcome":outcome,**evidence}


def approved_evidence(con, challenge, pkg_hash, verification):
    if verification is None:
        return False
    try:
        details=json.loads(verification["details_json"])
    except (ValueError,TypeError):
        return False
    if details.get("protocol")!="independent_review_v1" or details.get("review_outcome")!="passed":
        return False
    r=con.execute("SELECT * FROM independent_reviews WHERE id=? AND challenge_id=?",
                  (details.get("review_id"),challenge["id"])).fetchone()
    if r is None or r["outcome"]!="passed" or r["package_hash"]!=pkg_hash:
        return False
    if verification["package_hash"]!=pkg_hash or verification["outcome"]!="test_verified":
        return False
    try:
        archived=json.loads(r["evidence_json"])
    except (ValueError,TypeError):
        return False
    historical=dict(details)
    historical.pop("review_id",None)
    historical.pop("review_outcome",None)
    if archived!=historical:
        return False
    # The executable verifier itself is part of the reviewed evidence.
    if details.get("review_harness_sha256")!=sha(Path(__file__)):
        return False
    if details.get("reviewer_input_protocol")!="stdin_tokens_v1":
        return False
    if r["tests_run"] < GENERATED+3+2:
        return False
    for path_field,hash_field,suffix in (
        ("module_path","module_sha256",".py"),("report_path","report_sha256",".json")):
        try:
            path=source_path(ROOT/r[path_field],suffix)
            if sha(path)!=r[hash_field]:return False
        except (ValueError,OSError):
            return False
    if details.get("written_review_sha256")!=r["report_sha256"] or details.get("reviewer_module_sha256")!=r["module_sha256"]:
        return False
    if details.get("package_sha256")!=pkg_hash or details.get("tests_run")!=r["tests_run"]:
        return False
    if details.get("samples",0)<2 or details.get("edges",0)<3 or details.get("generated",0)<GENERATED:
        return False
    if details.get("distinct_inputs",0)<MIN_UNIQUE:
        return False
    try:
        report=json.loads((ROOT/r["report_path"]).read_text(encoding="utf8"))
        if report.get("decision")!="approve" or not report.get("independently_derived"):
            return False
        if report.get("reviewer_id")!=details.get("reviewer_id"):
            return False
        if any(not isinstance(report.get(key),str) or len(report[key].strip())<80 for key in REVIEW_FIELDS):
            return False
        ppc_review=report.get("ppc_review")
        if (not isinstance(ppc_review,dict) or ppc_review.get("verdict")!="pass"
                or ppc_review.get("all_p1_obligations_covered") is not True
                or not isinstance(ppc_review.get("obligation_mapping"),list)
                or not ppc_review["obligation_mapping"]):
            return False
        audit=report.get("specification_review")
        if not isinstance(audit,dict) or audit.get("verdict")!="pass":
            return False
        if type(audit.get("difficulty")) is not int or audit["difficulty"]!=challenge["difficulty"]:
            return False
        expected=("accessible_without_topic_prerequisites" if challenge["difficulty"]<=3
                  else "abstract_interpretation_permitted")
        if audit.get("comprehension_policy")!=expected:
            return False
        if audit.get("level_profile")!=COMPREHENSION_PROFILES.get(challenge["difficulty"]):
            return False
        if not isinstance(audit.get("level_specific_evidence"),str) or len(audit["level_specific_evidence"].strip())<160:
            return False
        if not isinstance(audit.get("student_text_quote"),str) or len(audit["student_text_quote"].strip())<12:
            return False
        if any(not isinstance(audit.get(k),str) or len(audit[k].strip())<80
               for k in ("symbols_and_objects","terminology_and_prerequisites",
                         "io_and_output_validity","ambiguity_and_edge_cases")):
            return False
    except (OSError,ValueError,TypeError):
        return False
    return True


def main():
    p=argparse.ArgumentParser(description="Evidence-backed independent review of a registered ARDS challenge")
    p.add_argument("--db",type=Path,default=memory.DEFAULT_DB)
    sub=p.add_subparsers(dest="cmd",required=True)
    run=sub.add_parser("check")
    run.add_argument("challenge")
    run.add_argument("--module",type=Path,required=True,help="Trusted local reviewers/RACG-XXXX.py")
    run.add_argument("--report",type=Path,required=True,help="Independent written reviewers/RACG-XXXX.json")
    run.add_argument("--file",type=Path,help="Full proposed versioned package for independent re-review of an already published problem")
    stat=sub.add_parser("status")
    stat.add_argument("--limit",type=int,default=100)
    sub.add_parser("workflow")
    sub.add_parser("worker")
    args=p.parse_args()
    if args.cmd=="worker":
        try:
            print(json.dumps(_worker(json.load(sys.stdin)),ensure_ascii=False))
        except Exception as e:
            print(type(e).__name__+": "+str(e),file=sys.stderr)
            sys.exit(1)
        return
    if args.cmd=="workflow":
        print("1. Write independent reviewer module and written review in reviewers/. "
              "2. Run check. 3. Run ards2.py release CHALLENGE on a passed hash-matching review.")
        return
    with memory.connect(args.db) as con:
        if args.cmd=="check":
            result=check(con,args.challenge,args.module,args.report,
                         json.loads(args.file.read_text(encoding="utf8")) if args.file else None)
        else:
            result=[dict(x) for x in con.execute("""
                SELECT c.external_id,c.status,
                    (SELECT outcome FROM independent_reviews r WHERE r.challenge_id=c.id ORDER BY id DESC LIMIT 1) AS last_review,
                    (SELECT tests_run FROM independent_reviews r WHERE r.challenge_id=c.id ORDER BY id DESC LIMIT 1) AS tests
                FROM challenges c JOIN authoring_batch_items i ON i.challenge_id=c.id
                ORDER BY i.batch_id,i.ordinal LIMIT ?""",(args.limit,))]
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
