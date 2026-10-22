#!/usr/bin/env python3
"""ARDS 2.0: auditable reasoning plans, typed problem packages, verification and exports.

Standard library only. No user-provided program is executed: automated checks are
restricted to first-party, reviewed oracle families. Unrecognized models remain
experimental, never automatically "verified".
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import strict_json

ROOT = Path(__file__).resolve().parents[1]
PATTERNS_FILE = ROOT / "references" / "reasoning_patterns.json"
ALLOWED_LAYERS = {"foundational", "structural", "compositional"}
FAMILIES = {"tiered_price", "opposite_rotations", "comparison_maxima",
            "missing_positive", "range_sum", "interval_lamps", "graph_reachability"}
SCHEMA_VERSION = "2"


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(obj):
    return strict_json.canonical(obj)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def ensure_schema(con):
    """Add-only migration. Never alter historical challenge, attempt or rubric data."""
    con.executescript("""

    -- Batch selections are immutable once drawn. Workflow status is
    -- independent of student publication and verification evidence.
    CREATE TABLE IF NOT EXISTS authoring_batches(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      requested_count INTEGER NOT NULL CHECK(requested_count BETWEEN 1 AND 1000),
      created_at TEXT NOT NULL,
      provenance TEXT NOT NULL,
      notes TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS authoring_batch_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      batch_id INTEGER NOT NULL REFERENCES authoring_batches(id),
      ordinal INTEGER NOT NULL CHECK(ordinal>=1),
      challenge_id INTEGER NOT NULL UNIQUE REFERENCES challenges(id),
      stage TEXT NOT NULL DEFAULT 'drawn' CHECK(stage IN
        ('drawn','drafted','under_review','verified','released','rejected')),
      review_note TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      UNIQUE(batch_id,ordinal)
    );
    CREATE INDEX IF NOT EXISTS idx_batch_items_stage
        ON authoring_batch_items(batch_id,stage,ordinal);
    CREATE TRIGGER IF NOT EXISTS no_change_batch_identity BEFORE UPDATE OF
      batch_id,ordinal,challenge_id ON authoring_batch_items
      BEGIN SELECT RAISE(ABORT,'batch draw identity is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_change_queued_racg_draw BEFORE UPDATE OF
      topic_id,topic_label,difficulty,presentation,continuation,
      roll_o,roll_x,roll_y,roll_p ON challenges
      WHEN EXISTS(SELECT 1 FROM authoring_batch_items i WHERE i.challenge_id=OLD.id)
      BEGIN SELECT RAISE(ABORT,'queued Classic RACG draw is immutable'); END;
    CREATE TABLE IF NOT EXISTS reasoning_plans(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL UNIQUE REFERENCES challenges(id),
      z INTEGER NOT NULL CHECK(z>=0),
      eligible_json TEXT NOT NULL,
      primary_pattern TEXT NOT NULL,
      catalog_version INTEGER NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS authoring_package_revisions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL REFERENCES challenges(id),
      revision INTEGER NOT NULL CHECK(revision>=2),
      reason TEXT NOT NULL CHECK(length(trim(reason))>0),
      body_json TEXT NOT NULL,
      body_hash TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(challenge_id,revision)
    );
    CREATE TRIGGER IF NOT EXISTS no_update_authoring_revision BEFORE UPDATE ON authoring_package_revisions
      BEGIN SELECT RAISE(ABORT,'authoring revisions are immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_authoring_revision BEFORE DELETE ON authoring_package_revisions
      BEGIN SELECT RAISE(ABORT,'authoring revisions are immutable'); END;
    CREATE TABLE IF NOT EXISTS problem_packages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL UNIQUE REFERENCES challenges(id),
      body_json TEXT NOT NULL,
      body_hash TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    -- Executed independent-review evidence is append-only and bound to
    -- the exact registered package, reviewer program, and written review.
    CREATE TABLE IF NOT EXISTS independent_reviews(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL REFERENCES challenges(id),
      package_hash TEXT NOT NULL,
      module_path TEXT NOT NULL,
      module_sha256 TEXT NOT NULL,
      report_path TEXT NOT NULL,
      report_sha256 TEXT NOT NULL,
      outcome TEXT NOT NULL CHECK(outcome IN ('passed','failed')),
      tests_run INTEGER NOT NULL CHECK(tests_run>=0),
      evidence_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_independent_review_challenge
      ON independent_reviews(challenge_id,id);
    CREATE TRIGGER IF NOT EXISTS no_update_independent_review
      BEFORE UPDATE ON independent_reviews
      BEGIN SELECT RAISE(ABORT,'independent reviews are immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_independent_review
      BEFORE DELETE ON independent_reviews
      BEGIN SELECT RAISE(ABORT,'independent reviews are immutable'); END;
    CREATE TABLE IF NOT EXISTS verification_runs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL REFERENCES challenges(id),
      package_hash TEXT NOT NULL,
      outcome TEXT NOT NULL CHECK(outcome IN ('test_verified','experimental','failed')),
      tests_run INTEGER NOT NULL CHECK(tests_run>=0),
      details_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS releases(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL UNIQUE REFERENCES challenges(id),
      verification_id INTEGER NOT NULL REFERENCES verification_runs(id),
      package_hash TEXT NOT NULL,
      released_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS published_revisions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL REFERENCES challenges(id),
      revision INTEGER NOT NULL CHECK(revision>=2),
      reason TEXT NOT NULL CHECK(length(trim(reason))>0),
      body_json TEXT NOT NULL,
      body_hash TEXT NOT NULL,
      verification_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(challenge_id,revision)
    );
    CREATE TRIGGER IF NOT EXISTS no_update_published_revision BEFORE UPDATE ON published_revisions
      BEGIN SELECT RAISE(ABORT,'published revisions are immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_published_revision BEFORE DELETE ON published_revisions
      BEGIN SELECT RAISE(ABORT,'published revisions are immutable'); END;
    CREATE TABLE IF NOT EXISTS export_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      challenge_id INTEGER NOT NULL REFERENCES challenges(id),
      edition TEXT NOT NULL CHECK(edition IN ('student','teacher')),
      path TEXT NOT NULL,
      content_hash TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_verification_challenge ON verification_runs(challenge_id,id);
    CREATE INDEX IF NOT EXISTS idx_export_challenge ON export_events(challenge_id);
    CREATE TRIGGER IF NOT EXISTS no_update_reasoning_plan BEFORE UPDATE ON reasoning_plans
      BEGIN SELECT RAISE(ABORT,'reasoning plan history is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_reasoning_plan BEFORE DELETE ON reasoning_plans
      BEGIN SELECT RAISE(ABORT,'reasoning plan history is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_update_problem_package BEFORE UPDATE ON problem_packages
      BEGIN SELECT RAISE(ABORT,'problem package is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_problem_package BEFORE DELETE ON problem_packages
      BEGIN SELECT RAISE(ABORT,'problem package is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_update_verification BEFORE UPDATE ON verification_runs
      BEGIN SELECT RAISE(ABORT,'verification history is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_verification BEFORE DELETE ON verification_runs
      BEGIN SELECT RAISE(ABORT,'verification history is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_update_release BEFORE UPDATE ON releases
      BEGIN SELECT RAISE(ABORT,'release history is immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_release BEFORE DELETE ON releases
      BEGIN SELECT RAISE(ABORT,'release history is immutable'); END;
    """)
    with con:
        con.execute("INSERT INTO metadata(key,value) VALUES('schema_version',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (SCHEMA_VERSION,))


def patterns():
    payload = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    data = payload["patterns"]
    if len(data) != 30 or len({p["id"] for p in data}) != len(data):
        raise ValueError("Pattern catalog must contain 30 distinct IDs")
    for p in data:
        if p["layer"] not in ALLOWED_LAYERS or not p["tags"] or not p["description"]:
            raise ValueError("Invalid reasoning pattern: " + p["id"])
    return payload


def topic_domain(label):
    name = (label or "").lower()
    if any(t in name for t in ("string", "substring", "palindrom", "character", "pattern matching")):
        return "strings"
    if any(t in name for t in ("graph", "tree", "path", "connectivity", "dfs", "bfs")):
        return "graphs"
    if any(t in name for t in ("math", "arithmetic", "number theory", "gcd", "geometry")):
        return "math"
    if any(t in name for t in ("array", "sorting", "prefix", "two pointers", "sliding",
                                "greedy", "sequence", "search", "missing element")):
        return "arrays"
    return "general"


def get_challenge(con, external_id):
    row = con.execute("SELECT * FROM challenges WHERE external_id=?", (external_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown challenge: " + external_id)
    return dict(row)


def plan(con, external_id, randbelow=None):
    ch = get_challenge(con, external_id)
    if ch["status"] != "selected" or ch["session_type"] != "RACG":
        raise ValueError("Only a selected RACG challenge may receive a new plan")
    catalog = patterns()
    domain = topic_domain(ch["topic_label"])
    eligible = sorted(p["id"] for p in catalog["patterns"]
                      if domain in p["tags"] or "general" in p["tags"])
    randbelow = randbelow or secrets.randbelow
    z = randbelow(len(eligible))
    if type(z) is not int or not 0 <= z < len(eligible):
        raise ValueError("Invalid pattern random roll")
    with con:
        con.execute("INSERT INTO reasoning_plans "
                    "(challenge_id,z,eligible_json,primary_pattern,catalog_version,created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (ch["id"], z, canonical(eligible), eligible[z],
                     catalog["version"], stamp()))
    return {"challenge": external_id, "domain": domain, "Z": z,
            "eligible_count": len(eligible), "primary_pattern": eligible[z],
            "difficulty": ch["difficulty"], "classic_racg_unchanged": True}


def validate_package(body, primary_pattern=None):
    strict_json.validate(body)
    if not isinstance(body, dict):
        raise ValueError("Package must be a JSON object")
    for field in ("title","statement","model","patterns","reference_solution","proof",
                  "samples","difficulty_estimate","provenance"):
        if field not in body:
            raise ValueError("Missing package field: " + field)
    if any(not isinstance(body[k], str) or not body[k].strip()
           for k in ("title","statement","reference_solution","proof","provenance")):
        raise ValueError("Title, statement, solution, proof and provenance must be nonempty")
    if not isinstance(body["difficulty_estimate"], int) or type(body["difficulty_estimate"]) is bool or not 1 <= body["difficulty_estimate"] <= 6:
        raise ValueError("Difficulty estimate must be 1..6")
    # Retain optional validation for historical/experimental packages. New
    # registrations and release are gated separately: teacher PPC is required.
    # Never expose this object in student-facing statements or exports.
    if "teacher_ppc" in body:
        reference = body["teacher_ppc"]
        fields = {"problem", "procedure", "correctness", "complexity"}
        if (not isinstance(reference, dict) or set(reference) != fields or
                any(not isinstance(reference[k], str) or not reference[k].strip()
                    for k in fields)):
            raise ValueError("teacher_ppc must contain four complete text sections: problem, procedure, correctness, complexity")
    model = body["model"]
    if not isinstance(model, dict):
        raise ValueError("Model must be an object")
    for k in ("inputs","hidden_variables","constraints","objective","family","parameters"):
        if k not in model:
            raise ValueError("Missing formal model field: " + k)
    if not isinstance(model["inputs"], dict) or not model["inputs"]:
        raise ValueError("Model inputs must be a nonempty object")
    if not isinstance(model["hidden_variables"], list):
        raise ValueError("Hidden variables must be a list")
    if not isinstance(model["constraints"], list) or not model["constraints"]:
        raise ValueError("Model constraints must be nonempty")
    if not all(isinstance(s,str) and s.strip() for s in model["constraints"]):
        raise ValueError("Constraints must be nonempty strings")
    if not isinstance(model["objective"], str) or not model["objective"].strip():
        raise ValueError("Model objective is required")
    if not isinstance(model["parameters"], dict):
        raise ValueError("Model parameters must be an object")
    if not isinstance(model["family"],str) or not model["family"].strip():
        raise ValueError("Model family must be a nonempty string")
    ids = {p["id"] for p in patterns()["patterns"]}
    selected = body["patterns"]
    if (not isinstance(selected,list) or not selected or any(type(p) is not str for p in selected) or
            len(set(selected)) != len(selected) or any(p not in ids for p in selected)):
        raise ValueError("Pattern IDs must be unique and exist in catalog")
    if primary_pattern and primary_pattern not in selected:
        raise ValueError("Package must include its selected primary reasoning pattern")
    if not isinstance(body["samples"],list) or not body["samples"]:
        raise ValueError("At least one sample input/output is required")
    for sample in body["samples"]:
        if not isinstance(sample,dict) or not all(k in sample for k in ("input","output")):
            raise ValueError("Samples require input and output")
        if not isinstance(sample["input"],str) or not isinstance(sample["output"],str):
            raise ValueError("Samples must be text")


def register(con, external_id, body):
    ch = get_challenge(con, external_id)
    if ch["status"] != "selected":
        raise ValueError("Package registration requires a selected challenge")
    p = con.execute("SELECT primary_pattern FROM reasoning_plans WHERE challenge_id=?",
                    (ch["id"],)).fetchone()
    if p is None:
        raise ValueError("Run 'plan' first")
    validate_package(body, p["primary_pattern"])
    if "teacher_ppc" not in body:
        raise ValueError("Registration blocked: new problems require a complete private teacher_ppc (P1/P2/C/K)")
    if not contest_io_ready(body,required=is_batch_challenge(con,ch["id"])):
        raise ValueError("Registration blocked: database-queued batch problems require CodeChef-style stdin/stdout and matching text samples; author metadata cannot bypass the I/O policy")
    domain = topic_domain(ch["topic_label"])
    family = body["model"]["family"]
    if (family == "tiered_price" and domain not in ("math", "general")) or (family == "opposite_rotations" and domain != "strings") or (family == "comparison_maxima" and domain not in ("arrays", "strings")):
        raise ValueError("First-party model family is incompatible with the randomized topic")
    if family in ("missing_positive", "range_sum") and domain not in ("arrays", "general"):
        raise ValueError("Model family is incompatible with the randomized topic")
    if family == "interval_lamps" and domain not in ("arrays", "math", "general"):
        raise ValueError("Model family is incompatible with the randomized topic")
    if family == "graph_reachability" and domain != "graphs":
        raise ValueError("Model family is incompatible with the randomized topic")
    if body["difficulty_estimate"] != ch["difficulty"]:
        raise ValueError("Difficulty mismatch; revise the problem instead of changing the RACG roll")
    with con:
        con.execute("INSERT INTO problem_packages "
                    "(challenge_id,body_json,body_hash,created_at) VALUES(?,?,?,?)",
                    (ch["id"], canonical(body), digest(body), stamp()))
    return {"challenge": external_id, "package_hash": digest(body),
            "status": "experimental", "saved": True}


def load_package(con, ch):
    """Get newest immutable *pre-release* candidate, else original package."""
    row = con.execute(
        "SELECT * FROM authoring_package_revisions WHERE challenge_id=? "
        "ORDER BY revision DESC LIMIT 1", (ch["id"],)
    ).fetchone()
    if row is None:
        row = con.execute(
            "SELECT * FROM problem_packages WHERE challenge_id=?", (ch["id"],)
        ).fetchone()
    if row is None:
        raise ValueError("No ARDS 2.0 package registered")
    return dict(row), json.loads(row["body_json"])


def revise_draft(con, external_id, body, reason):
    """Append a new immutable private candidate before publication.

    Verification evidence is hash-bound to the candidate, so prior evidence
    becomes stale and cannot authorize release of a changed statement/PPC.
    """
    if not isinstance(reason,str) or not reason.strip():
        raise ValueError("A draft correction requires a documented reason")
    ch = get_challenge(con,external_id)
    if ch["session_type"] != "RACG" or ch["status"] != "selected":
        raise ValueError("Only unpublished selected RACG packages may be revised")
    previous,old = load_package(con,ch)
    planned = con.execute(
        "SELECT primary_pattern FROM reasoning_plans WHERE challenge_id=?", (ch["id"],)
    ).fetchone()
    if not planned:
        raise ValueError("Missing original reasoning plan")
    validate_package(body, planned["primary_pattern"])
    if "teacher_ppc" not in body:
        raise ValueError("Draft revision requires a complete private teacher PPC")
    if not contest_io_ready(body,required=is_batch_challenge(con,ch["id"])):
        raise ValueError("Draft revision blocked: batch input/output must use standard stdin/stdout")
    if body["difficulty_estimate"] != ch["difficulty"]:
        raise ValueError("Draft revision may not change recorded RACG difficulty")
    if body["model"]["family"] != old["model"]["family"]:
        raise ValueError("Changing mathematical family requires separate review; the original draw remains unchanged")
    if digest(body) == digest(old):
        raise ValueError("Revision must change package content")
    number = con.execute(
        "SELECT COALESCE(MAX(revision),1)+1 FROM authoring_package_revisions WHERE challenge_id=?",
        (ch["id"],)
    ).fetchone()[0]
    with con:
        con.execute(
            "INSERT INTO authoring_package_revisions"
            "(challenge_id,revision,reason,body_json,body_hash,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (ch["id"],number,reason.strip(),canonical(body),digest(body),stamp())
        )
    return {"challenge":external_id,"revision":number,"body_hash":digest(body),
            "previous_preserved":True,"verification_required_again":True}



def _price_methods(n, params):
    threshold, full, discounted = (params[k] for k in ("threshold","full","discounted"))
    return (n * (discounted if n >= threshold else full),
            sum(discounted if n >= threshold else full for _ in range(n)))


def _rotate_left(s):
    return s[1:]+s[:1]


def _rotate_right(s):
    return s[-1:]+s[:-1]


def _rotate_methods(s):
    n = len(s)
    fast = all(s[i] == s[(i+2) % n] for i in range(n))
    # L(V)=S has a unique V=R(S); test the other equation independently.
    witness = _rotate_right(s)
    slow = _rotate_left(witness) == s and _rotate_right(witness) == s
    return (fast, slow)


def _topological_witness(s, candidate):
    """Independent feasibility oracle: add strict max edges and test DAG."""
    n=len(s)+1
    graph=[[] for _ in range(n)]
    indeg=[0]*n
    def edge(u,v):
        graph[u].append(v)
        indeg[v]+=1
    for i, bit in enumerate(s):
        if bit=="0":
            edge(i+1,i)
        else:
            edge(i,i+1)
    for j in range(n):
        if j!=candidate:
            edge(candidate,j)
    todo=[i for i in range(n) if indeg[i]==0]
    count=0
    while todo:
        u=todo.pop()
        count+=1
        for v in graph[u]:
            indeg[v]-=1
            if indeg[v]==0:
                todo.append(v)
    return count==n


def _maxima_methods(s):
    n=len(s)+1
    fast=sum((i==0 or s[i-1]=="0") and (i==n-1 or s[i]=="1")
             for i in range(n))
    slow=sum(_topological_witness(s,i) for i in range(n))
    return fast,slow


def _reference_binding(body):
    from ppc2 import FAMILY_PROOFS
    reference=FAMILY_PROOFS.get(body["model"]["family"])
    registry={**reference,"complexity":list(reference["complexity"])} if reference else None
    return {"schema":"first_party_reference_v1", "family":body["model"]["family"],
            "model_sha256":digest(body["model"]),
            "solution_sha256":digest(body["reference_solution"]),
            "argument_sha256":digest(body["proof"]),
            "registry_sha256":digest(registry),
            "scope":"Registered reference implementation and explanation; bounded tests only"}


def _reference_identity(body):
    return {**_reference_binding(body),
            "source_sha256":{name:hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                              for name in ("ards2.py","ppc2.py","strict_json.py","ppc3.py")}}


def prepare_reference(body):
    """Explicitly substitute the registered explanation; never approve submitted prose."""
    from ppc2 import FAMILY_PROOFS
    validate_package(body)
    family=body["model"]["family"]
    if family not in FAMILY_PROOFS:
        raise ValueError("No registered first-party reference for this family")
    result=strict_json.loads(canonical(body))
    reference=FAMILY_PROOFS[family]
    result["reference_solution"]=reference["core"]
    result["proof"]=reference["core"]+" "+" ".join(reference["steps"].values())
    result["reference_binding"]=_reference_binding(result)
    return result


def reference_matches(body):
    from ppc2 import FAMILY_PROOFS
    reference=FAMILY_PROOFS.get(body["model"]["family"])
    return bool(reference and body.get("reference_binding")==_reference_binding(body) and
                body["reference_solution"]==reference["core"] and
                body["proof"]==reference["core"]+" "+" ".join(reference["steps"].values()))


def _finite_correspondence(model, cert):
    """Check only the implemented finite pricing specification adapter, never refinement."""
    if model["family"]!="tiered_price":
        raise ValueError("No finite specification adapter for this family; use auxiliary_finite_model")
    p=model["parameters"]
    if any(type(p.get(k)) is not int for k in ("min_n","max_n","threshold","full","discounted")):
        raise ValueError("Invalid pricing parameters for finite specification adapter")
    if not 1<=p["min_n"]<=p["max_n"]<=1000:
        raise ValueError("Invalid finite pricing domain")
    domain=cert["input_domain"]
    expected=list(range(p["min_n"],p["max_n"]+1))
    if any(type(n) is not int for n in domain) or sorted(domain)!=expected:
        raise ValueError("Finite proof does not cover the exact pricing input domain")
    for case in cert["cases"]:
        n=case["input_id"]
        value=n*(p["full"] if n<p["threshold"] else p["discounted"])
        if canonical(case["allowed_outputs"])!=canonical([value]):
            raise ValueError("Finite proof postcondition differs from the pricing specification")


def verify_body(body):
    """Test registered references; record the precise subject and unproved correspondences."""
    try:
        validate_package(body)
        result=_verify_body(body)
        result["verified_subject"]="registered_first_party_reference_and_samples"
        result["reference_binding_matches"]=reference_matches(body)
        result["authored_solution_status"]=("registered_reference_text" if result["reference_binding_matches"]
                                            else "unverified_proposal")
        result["statement_correspondence"]="requires_review"
        result["implementation_refinement"]="unproved"
        result["ppc_argument_semantics"]="unverified"
        result["reference_identity"]=_reference_identity(body)
        if result["outcome"]=="test_verified" and not result["reference_binding_matches"]:
            result["reference_test_outcome"]="test_verified"
            result["outcome"]="experimental"
            result["reason"]="Built-in reference tests passed, but the authored solution is unverified; prepare a registered reference package before release"
        return result
    except (ValueError,TypeError,KeyError,IndexError,RecursionError) as exc:
        return {"outcome":"failed","tests_run":0,"reason":str(exc),
                "reason_code":"resource_limit" if isinstance(exc,strict_json.ResourceLimitError) else "invalid_package"}


def _verify_body(body):
    model = body["model"]
    family = model["family"]
    params = model["parameters"]
    if "ppc" in body:
        from ppc2 import check_certificate
        certificate = check_certificate(body)
        if certificate["status"] != "structure_checked":
            return {"outcome": "failed", "tests_run": 0, "reason": "PPC contract rejected: " + "; ".join(certificate["errors"])}
    if "ppc3" in body:
        from ppc3 import check_proposition, check_machine, fingerprint
        attestation = body["ppc3"]
        if (not isinstance(attestation, dict) or
                set(attestation) != {"model_hash", "scope", "certificate"} or
                attestation["model_hash"] != fingerprint(model) or
                attestation["scope"] not in ("auxiliary_propositional_lemma", "explicit_finite_model", "auxiliary_finite_model") or
                not isinstance(attestation["certificate"], dict)):
            return {"outcome": "failed", "tests_run": 0,
                    "reason": "Invalid or unbound PPC 3.0 fragment certificate"}
        if attestation["scope"] == "auxiliary_propositional_lemma":
            proof_result = check_proposition(attestation["certificate"])
            required_status = "fragment_machine_checked"
        else:
            proof_result = check_machine(attestation["certificate"])
            required_status = "finite_domain_machine_checked"
        if proof_result["status"] != required_status:
            return {"outcome": "failed", "tests_run": 0,
                    "reason": "PPC 3.0 rejected formal fragment: " + proof_result.get("reason", "unknown")}
        if attestation["scope"]=="explicit_finite_model":
            _finite_correspondence(model,attestation["certificate"])
        # A checked *fragment* is not sufficient to certify the whole algorithm.
    if family in ("missing_positive", "range_sum", "interval_lamps", "graph_reachability"):
        from ppc2 import verify_extra_family
        result=verify_extra_family(body)
        if "ppc3" in body:
            result["fragment_evidence"]={**proof_result,"attachment_scope":attestation["scope"],
                                         "correspondence":"auxiliary_only"}
        return result
    checked = 0
    examples = []
    try:
        if family == "tiered_price":
            keys = ("threshold", "full", "discounted", "min_n", "max_n")
            if any(type(params.get(k)) is not int for k in keys):
                raise ValueError("Price family needs integer threshold/full/discounted/min_n/max_n")
            if not (1 <= params["min_n"] <= params["max_n"] <= 1000
                    and 1 <= params["threshold"] <= 1000
                    and params["full"] >= 0 and params["discounted"] >= 0):
                raise ValueError("Invalid price family bounds")
            for n in range(params["min_n"], params["max_n"]+1):
                fast, slow = _price_methods(n, params)
                if fast != slow:
                    return {"outcome":"failed","tests_run":checked+1,"reason":"Oracle disagreement"}
                checked += 1
            for sample in body["samples"]:
                n=int(sample["input"].strip())
                if not params["min_n"]<=n<=params["max_n"]:
                    raise ValueError("Pricing sample outside the specified domain")
                fast, _ = _price_methods(n,params)
                if sample["output"].strip() != str(fast):
                    return {"outcome":"failed","tests_run":checked+1,"reason":"Sample mismatch"}
                checked += 1
        elif family == "opposite_rotations":
            alphabet = params.get("alphabet")
            maximum = params.get("exhaustive_max_n")
            if (not isinstance(alphabet,str) or not 1 <= len(alphabet) <= 4 or
                len(set(alphabet)) != len(alphabet) or type(maximum) is not int or
                not 1 <= maximum <= 8 or sum(len(alphabet)**n for n in range(1,maximum+1)) > 100000):
                raise ValueError("Invalid bounded rotation oracle parameters")
            for n in range(1, maximum+1):
                for chars in itertools.product(alphabet,repeat=n):
                    s = "".join(chars)
                    fast, slow = _rotate_methods(s)
                    if fast != slow:
                        return {"outcome":"failed","tests_run":checked+1,
                                "reason":"Oracle disagreement", "counterexample":s}
                    checked += 1
            for sample in body["samples"]:
                s = sample["input"].strip()
                if not s or any(c not in alphabet for c in s) or sample["output"].strip() not in ("YES","NO"):
                    return {"outcome":"failed","tests_run":checked+1,"reason":"Invalid sample"}
                fast, _ = _rotate_methods(s)
                if sample["output"].strip() != ("YES" if fast else "NO"):
                    return {"outcome":"failed","tests_run":checked+1,"reason":"Sample mismatch"}
                checked += 1
        elif family == "comparison_maxima":
            maximum = params.get("exhaustive_max_n")
            if type(maximum) is not int or not 2 <= maximum <= 13:
                raise ValueError("Comparison maxima needs exhaustive_max_n in 2..13")
            for n in range(2,maximum+1):
                for bits in itertools.product("01",repeat=n-1):
                    s="".join(bits)
                    fast,slow=_maxima_methods(s)
                    if fast!=slow:
                        return {"outcome":"failed","tests_run":checked+1,
                                "reason":"Oracle disagreement","counterexample":s}
                    checked+=1
            for sample in body["samples"]:
                s=sample["input"].strip()
                if not s or len(s)>=maximum or any(bit not in "01" for bit in s):
                    return {"outcome":"failed","tests_run":checked+1,"reason":"Invalid comparison sample"}
                fast,_=_maxima_methods(s)
                if sample["output"].strip()!=str(fast):
                    return {"outcome":"failed","tests_run":checked+1,"reason":"Sample mismatch"}
                checked+=1
        else:
            return {"outcome":"experimental","tests_run":0,
                    "reason":"No reviewed first-party reference oracle for this model family"}
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return {"outcome":"failed","tests_run":checked,
                "reason":"Invalid family or sample: "+str(exc)}
    result={"outcome":"test_verified","tests_run":checked,
            "reason":"Reference/oracle agree on bounded domain and provided samples. "
                     "This is not a universal formal proof or independent proof review."}
    if "ppc3" in body:
        result["fragment_evidence"]={**proof_result,"attachment_scope":attestation["scope"],
            "correspondence":"finite_specification_relation_checked" if attestation["scope"]=="explicit_finite_model" else "auxiliary_only",
            "implementation_refinement":"unproved"}
    return result


def verify(con, external_id):
    ch = get_challenge(con, external_id)
    if ch["status"] != "selected":
        raise ValueError("Only an unpresented package can be tested for release")
    pkg, body = load_package(con,ch)
    result = verify_body(body)
    with con:
        cursor = con.execute("INSERT INTO verification_runs "
                             "(challenge_id,package_hash,outcome,tests_run,details_json,created_at) "
                             "VALUES (?,?,?,?,?,?)",
                             (ch["id"],pkg["body_hash"],result["outcome"],
                              result["tests_run"],canonical(result),stamp()))
    return dict(result,verification_id=cursor.lastrowid,challenge=external_id)


def is_batch_challenge(con, challenge_id):
    """Immutable database membership, not optional author-supplied metadata."""
    return con.execute("SELECT 1 FROM authoring_batch_items WHERE challenge_id=?",
                       (challenge_id,)).fetchone() is not None


def contest_io_ready(body, required=False):
    """Require actual plain-text stdin/stdout for registered RACG batch items.

    The original 100 were authored with JSON requests; that is *not*
    competitive-programming stdin. Do not release them without per-problem
    versioned conversion and separately checked text samples.
    """
    params=body.get("model",{}).get("parameters",{})
    if not required:
        return True
    contract=body.get("io_contract")
    if not isinstance(contract,dict) or contract.get("encoding")!="stdin_tokens_v1":
        return False
    if params.get("input_encoding") not in ("stdin_tokens","stdin_lines"):
        return False
    if params.get("output_encoding")!="stdout_text":
        return False
    display=body.get("statement_display",{})
    if not isinstance(display,dict):
        return False
    if "notes" in display or any(isinstance(s,dict) and "explanation" in s for s in display.get("samples",[])):
        return False
    if not all(isinstance(display.get(k),str) and display[k].strip()
               for k in ("input_format","output_format")):
        return False
    if "JSON" in (display["input_format"]+display["output_format"]).upper():
        return False
    samples=body.get("samples",[])
    shown=display.get("samples",[])
    if not isinstance(shown,list) or len(shown)!=len(samples) or len(shown)<2:
        return False
    for expected,visible in zip(samples,shown):
        if not isinstance(expected,dict) or not isinstance(visible,dict):
            return False
        if expected.get("input")!=visible.get("input") or expected.get("output")!=visible.get("output"):
            return False
        if not isinstance(expected.get("input"),str) or not expected["input"].strip():
            return False
        if not isinstance(expected.get("output"),str) or not expected["output"].strip():
            return False
        # A statement claiming text I/O cannot keep JSON arrays or objects
        # in the actual samples. Scalar numbers are ordinary contest output.
        for raw in (expected["input"],expected["output"]):
            token=raw.lstrip()
            if token.startswith(("{","[")):
                try:
                    if isinstance(json.loads(token),(dict,list)):
                        return False
                except (ValueError,TypeError):
                    pass
    return True


def release(con, external_id):
    """Public issuance is gated by current successful bounded verification."""
    import memory
    ch = get_challenge(con,external_id)
    if ch["status"] != "selected":
        raise ValueError("Only selected challenges may be released")
    pkg,body = load_package(con,ch)
    if "teacher_ppc" not in body:
        raise ValueError("Release blocked: the four-part teacher PPC must be stored alongside the problem")
    queued=is_batch_challenge(con,ch["id"])
    if not contest_io_ready(body,required=queued):
        raise ValueError("Release blocked: queued batch problem lacks valid stdin/stdout contract; JSON-only I/O is not permitted")
    verified = con.execute("SELECT * FROM verification_runs WHERE challenge_id=? "
                           "ORDER BY id DESC LIMIT 1",(ch["id"],)).fetchone()
    if (not verified or verified["package_hash"] != pkg["body_hash"] or
            verified["outcome"] != "test_verified"):
        raise ValueError("Release blocked: no matching successful first-party verification")
    evidence=strict_json.loads(verified["details_json"])
    independently_reviewed=evidence.get("protocol")=="independent_review_v1"
    if queued and not independently_reviewed:
        raise ValueError("Release blocked: every queued batch challenge requires independent review evidence; first-party checks alone are insufficient")
    if independently_reviewed:
        from ards_review import approved_evidence
        if not approved_evidence(con,ch,pkg["body_hash"],verified):
            raise ValueError("Release blocked: independent reviewer evidence missing, stale or incomplete")
    else:
        if not reference_matches(body):
            raise ValueError("Release blocked: authored solution is unverified; prepare a registered reference package first")
        if (not evidence.get("reference_binding_matches") or
                evidence.get("reference_identity")!=_reference_identity(body)):
            raise ValueError("Release blocked: reference evidence is stale; verify with the current checker")
    exact = con.execute("SELECT external_id FROM challenges WHERE statement_hash=? "
                        "AND id<>? ORDER BY id",(hashlib.sha256(body["statement"].strip().encode("utf-8")).hexdigest(),
                                                 ch["id"])).fetchall()
    if exact:
        raise ValueError("Release blocked: exact duplicate statements exist")
    if body["difficulty_estimate"] != ch["difficulty"]:
        raise ValueError("Difficulty mismatch")
    # One DB transaction: user-visible challenge and release record either both commit or neither.
    with con:
        cursor = con.execute("""
        UPDATE challenges
        SET title=?,statement=?,statement_hash=?,constraints_json=?,
            status='presented',presented_at=?
        WHERE id=? AND status='selected'""",
        (body["title"].strip(),body["statement"].strip(),
         hashlib.sha256(body["statement"].strip().encode("utf-8")).hexdigest(),
         canonical(body["model"].get("parameters",{})),stamp(),ch["id"]))
        if cursor.rowcount != 1:
            raise ValueError("Concurrent modification prevented release")
        con.execute("INSERT INTO releases(challenge_id,verification_id,package_hash,released_at) "
                    "VALUES(?,?,?,?)",(ch["id"],verified["id"],pkg["body_hash"],stamp()))
    return {"challenge":external_id,"status":"presented",
            "verification":"tested_and_ai_reviewed" if independently_reviewed else "test_verified",
            "verified_subject":"independent_candidate_oracle_tests_and_written_review" if independently_reviewed
                else "registered_first_party_reference_and_samples",
            "statement_correspondence":"AI-reviewed; not formally proved" if independently_reviewed else "requires_review",
            "implementation_refinement":"test_evidence_only; universal proof unproved",
            "released":True,"proof_reviewed":independently_reviewed,
            "notes":"Independent differential testing and written AI review, not a formal proof"
                if independently_reviewed else "The built-in solver has bounded test evidence, not a machine-checked universal proof",
            "lexical_duplicates":memory.near(con,body["title"]+" "+body["statement"],
                                             limit=5,exclude_id=external_id)}


def latest_published_body(con, ch):
    row=con.execute("SELECT revision,body_json FROM published_revisions "
                    "WHERE challenge_id=? ORDER BY revision DESC LIMIT 1",
                    (ch["id"],)).fetchone()
    if row:
        return row["revision"],json.loads(row["body_json"])
    pkg,body=load_package(con,ch)
    return 1,body


def amend(con,external_id,body,reason):
    """Append a fully checked correction; never rewrite the original release."""
    if not reason or not reason.strip():
        raise ValueError("Corrections require a documented reason")
    ch=get_challenge(con,external_id)
    release_row=con.execute("SELECT * FROM releases WHERE challenge_id=?",(ch["id"],)).fetchone()
    if not release_row:
        raise ValueError("Only released ARDS 2.0 problems may be amended")
    previous_version,old=latest_published_body(con,ch)
    plan_row=con.execute("SELECT primary_pattern FROM reasoning_plans WHERE challenge_id=?",(ch["id"],)).fetchone()
    validate_package(body, plan_row["primary_pattern"] if plan_row else None)
    if body["difficulty_estimate"]!=ch["difficulty"]:
        raise ValueError("A revision cannot retroactively change RACG difficulty")
    if body["model"]["family"]!=old["model"]["family"]:
        raise ValueError("A change of mathematical family requires a new challenge")
    if digest(body)==digest(old):
        raise ValueError("A revision must change content")
    if "teacher_ppc" not in body:
        raise ValueError("Correction must include a complete teacher PPC")
    queued=is_batch_challenge(con,ch["id"])
    if not contest_io_ready(body,required=queued):
        raise ValueError("Correction requires a complete standard stdin/stdout contract for batch problems")
    result=verify_body(body)
    if not queued and result["outcome"]=="test_verified" and reference_matches(body):
        evidence_scope="first_party"
    else:
        from ards_review import approved_evidence
        reviewed=con.execute(
            "SELECT * FROM verification_runs WHERE challenge_id=? AND package_hash=? "
            "ORDER BY id DESC LIMIT 1",(ch["id"],digest(body))).fetchone()
        if not approved_evidence(con,ch,digest(body),reviewed):
            raise ValueError("Correction requires matching successful independent review evidence (verification) for this exact revision")
        result=json.loads(reviewed["details_json"])
        evidence_scope="tested_and_ai_reviewed"
    with con:
        con.execute("INSERT INTO published_revisions "
                    "(challenge_id,revision,reason,body_json,body_hash,verification_json,created_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (ch["id"],previous_version+1,reason.strip(),
                     canonical(body),digest(body),canonical(result),stamp()))
    return {"challenge":external_id,"revision":previous_version+1,
            "verification":result,"original_preserved":True}


def export_text(con, external_id, edition):
    if edition not in ("student","teacher"):
        raise ValueError("Edition must be student or teacher")
    ch=get_challenge(con,external_id)
    if not ch["statement"] or ch["status"] in ("selected","abandoned"):
        raise ValueError("Only complete presented challenges can be exported")
    published=con.execute("SELECT * FROM releases WHERE challenge_id=?",(ch["id"],)).fetchone()
    version, current=(latest_published_body(con,ch) if published else (0,None))
    title=current["title"] if current else (ch["title"] or external_id)
    statement=current["statement"] if current else ch["statement"]
    header = "# "+title+"\n\n"
    header += "Challenge: "+external_id+"\n\n"
    header += "Original source: "+ch["source"]+"\n\n"
    if version > 1:
        header += "Published statement revision: "+str(version)+" (original archived).\n\n"
    header += statement.strip()+"\n"
    if edition == "student":
        return header
    pkg,original_body=load_package(con,ch)
    body=current or original_body
    released=con.execute("SELECT * FROM releases WHERE challenge_id=?", (ch["id"],)).fetchone()
    if not released or released["package_hash"] != pkg["body_hash"]:
        raise ValueError("Teacher edition requires a released, verified ARDS 2.0 package")
    result = header+"\n---\n\n# Teacher's Answer Key\n\n"
    result+="Verification subject: the registered first-party reference and samples. Bounded testing is not a universal proof. "
    result+="Statement correspondence requires review; executable implementation refinement is unproved.\n\n"
    if not reference_matches(body):
        result+="Historical authored solution: unverified by this checker; the stored release has not been retroactively certified.\n\n"
    if "teacher_ppc" in body:
        result+="## Private PPC (P1 / P2 / C / K)\n\n"
        for label,key in (("P1 — Problem specification","problem"),("P2 — Procedure","procedure"),
                          ("C — Correctness","correctness"),("K — Complexity","complexity")):
            result+="### "+label+"\n\n"+body["teacher_ppc"][key].strip()+"\n\n"
    result+="## Algorithm\n\n"+body["reference_solution"].strip()+"\n\n"
    result+="## Correctness argument\n\n"+body["proof"].strip()+"\n\n"
    result+="## Formal model\n\n"+json.dumps(body["model"],indent=2,ensure_ascii=False)+"\n\n"
    result+="## Reasoning patterns\n\n"+", ".join(body["patterns"])+"\n\n"
    if "ppc" in body:
        result+="## PPC 2.0 proof-obligation certificate (structure only)\n\n"
        result+="Obligations are structurally checked; natural-language arguments are not machine-proved.\n\n"
        result+="```json\n"+json.dumps(body["ppc"],indent=2,ensure_ascii=False)+"\n```\n\n"
    if "ppc3" in body:
        result+="## PPC 3.0 restricted proof evidence\n\n"
        result+="This certificate proves only its explicitly stated formal fragment, not universal correctness of the problem or a Java implementation.\n\n"
        result+="```json\n"+json.dumps(body["ppc3"],indent=2,ensure_ascii=False)+"\n```\n\n"
    result+="## Samples\n\n"
    for case in body["samples"]:
        result+="Input:\n\n"+"```text\n"+case["input"].strip()+"\n```\n\n"
        result+="Expected output:\n\n"+"```text\n"+case["output"].strip()+"\n```\n\n"
    return result


def export_file(con,external_id,edition,path):
    path=Path(path)
    data=export_text(con,external_id,edition)
    if path.exists():
        raise FileExistsError("Refuse overwrite: "+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(data,encoding="utf-8")
    ch=get_challenge(con,external_id)
    with con:
        con.execute("INSERT INTO export_events "
                    "(challenge_id,edition,path,content_hash,created_at) VALUES (?,?,?,?,?)",
                    (ch["id"],edition,str(path),hashlib.sha256(data.encode()).hexdigest(),stamp()))
    return {"challenge":external_id,"edition":edition,"path":str(path),
            "bytes":path.stat().st_size,"saved":True}


def inspect(con,external_id):
    ch=get_challenge(con,external_id)
    plan_row=con.execute("SELECT * FROM reasoning_plans WHERE challenge_id=?",(ch["id"],)).fetchone()
    package_row=con.execute("SELECT * FROM authoring_package_revisions WHERE challenge_id=? ORDER BY revision DESC LIMIT 1",(ch["id"],)).fetchone()
    if package_row is None:
        package_row=con.execute("SELECT * FROM problem_packages WHERE challenge_id=?",(ch["id"],)).fetchone()
    verifications=[dict(r) for r in con.execute("SELECT * FROM verification_runs "
                                                "WHERE challenge_id=? ORDER BY id",(ch["id"],))]
    release_row=con.execute("SELECT * FROM releases WHERE challenge_id=?",(ch["id"],)).fetchone()
    revisions=[dict(r) for r in con.execute("SELECT revision,reason,body_hash,verification_json,created_at "
                                            "FROM published_revisions WHERE challenge_id=? ORDER BY revision",(ch["id"],))]
    draft_revisions=[dict(r) for r in con.execute("SELECT revision,reason,body_hash,created_at FROM authoring_package_revisions WHERE challenge_id=? ORDER BY revision",(ch["id"],))]
    return {"revisions":revisions,"draft_revisions":draft_revisions,"challenge":{k:ch[k] for k in ("external_id","title","status","difficulty",
                                          "topic_id","topic_label","roll_o","roll_x","roll_y","roll_p")},
            "plan":dict(plan_row) if plan_row else None,
            "package_hash":package_row["body_hash"] if package_row else None,
            "verification_runs":verifications,
            "release":dict(release_row) if release_row else None}


def pattern_profile(con):
    """Descriptive only: known, graded first attempts; no inferred skill rating."""
    rows = con.execute("""
      SELECT pp.body_json, a.id AS attempt_id, a.independent,
        (SELECT s.correct FROM assessments s
         WHERE s.attempt_id=a.id ORDER BY s.id DESC LIMIT 1) AS correct
      FROM problem_packages pp
      JOIN releases r ON r.challenge_id=pp.challenge_id
      JOIN attempts a ON a.challenge_id=pp.challenge_id AND a.stage='first'
    """).fetchall()
    counters = {}
    for row in rows:
        ids = json.loads(row["body_json"])["patterns"]
        for pattern in ids:
            d = counters.setdefault(pattern, {"graded_first":0,"independent_graded":0,
                                              "independent_correct":0})
            if row["correct"] is None:
                continue
            d["graded_first"] += 1
            if row["independent"]:
                d["independent_graded"] += 1
                d["independent_correct"] += int(row["correct"])
    return {"method":"observed first attempts, latest evidence-based assessment per attempt",
            "not_a_calibrated_skill_rating":True,"patterns":counters}


def _main():
    import memory
    parser=argparse.ArgumentParser(description="ARDS 2.0 verified reasoning and teaching archive")
    parser.add_argument("--db",type=Path,default=memory.DEFAULT_DB)
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("catalog")
    sub.add_parser("archive")
    sub.add_parser("profile")
    for name in ("plan","inspect","verify","release"):
        p=sub.add_parser(name)
        p.add_argument("challenge")
    reg=sub.add_parser("register")
    reg.add_argument("challenge")
    reg.add_argument("--file",type=Path,required=True)
    redraft=sub.add_parser("revise-draft",help="Append immutable pre-release corrected package; old verification becomes stale")
    redraft.add_argument("challenge")
    redraft.add_argument("--file",type=Path,required=True)
    redraft.add_argument("--reason",required=True)
    prep=sub.add_parser("prepare-reference")
    prep.add_argument("--file",type=Path,required=True)
    prep.add_argument("--out",type=Path,required=True)
    corr=sub.add_parser("amend")
    corr.add_argument("challenge")
    corr.add_argument("--file",type=Path,required=True)
    corr.add_argument("--reason",required=True)
    exp=sub.add_parser("export")
    exp.add_argument("challenge")
    exp.add_argument("--edition",required=True,choices=("student","teacher"))
    exp.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.action=="prepare-reference":
        result=prepare_reference(strict_json.load(args.file))
        with args.out.open("x",encoding="utf8") as stream:
            stream.write(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
        print(json.dumps({"saved":True,"path":str(args.out),"scope":"Registered reference text; bounded tests still required"}))
        return
    with memory.connect(args.db) as con:
        if args.action=="catalog":
            result=patterns()
        elif args.action=="archive":
            result=[dict(r) for r in con.execute(
                "SELECT external_id,title,status,topic_label,difficulty FROM challenges ORDER BY id DESC")]
        elif args.action=="profile":
            result=pattern_profile(con)
        elif args.action=="plan":
            result=plan(con,args.challenge)
        elif args.action=="inspect":
            result=inspect(con,args.challenge)
        elif args.action=="register":
            result=register(con,args.challenge,strict_json.load(args.file))
        elif args.action=="revise-draft":
            result=revise_draft(con,args.challenge,strict_json.load(args.file),args.reason)
        elif args.action=="amend":
            result=amend(con,args.challenge,strict_json.load(args.file),args.reason)
        elif args.action=="verify":
            result=verify(con,args.challenge)
        elif args.action=="release":
            result=release(con,args.challenge)
        elif args.action=="export":
            result=export_file(con,args.challenge,args.edition,args.out)
    print(json.dumps(result,indent=2,ensure_ascii=False,default=str))


def main():
    try:
        _main()
    except (ValueError,TypeError,KeyError,OSError,sqlite3.Error) as exc:
        print(json.dumps({"outcome":"failed","saved":False,"reason":str(exc)}))
        raise SystemExit(1)


if __name__=="__main__":
    main()
