#!/usr/bin/env python3
"""PPC 3.0 trusted *restricted* proof checker.

Precisely delimited claims:
  - natural-deduction proof terms for intuitionistic propositional logic;
  - total correctness of explicitly FINITE, fully enumerated transition systems.
No Python eval or untrusted solver execution; no generic algorithm theorem proofs.
In each fragment, acceptance implies truth in the specified mathematical semantics
provided the small trusted checker is implemented correctly. No external Lean
proof-checking is claimed.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import shutil
from pathlib import Path
import strict_json
from strict_json import ResourceLimitError

ROOT = Path(__file__).resolve().parents[1]
MAX_NODES = 10000
MAX_DEPTH = 100
MAX_ATOMS_FOR_AUDIT = 12
MAX_SEMANTIC_WORK = 2000000


class ProofError(ValueError):
    pass


def canonical(value):
    return strict_json.canonical(value)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf8")).hexdigest()


def parse_formula(value, depth=0):
    """Strict grammar with immutable canonical tuples. No Python expressions."""
    if depth > MAX_DEPTH:
        raise ResourceLimitError("formula nesting exceeds limit")
    if not isinstance(value, dict) or "op" not in value:
        raise ProofError("formula must contain op")
    op = value["op"]
    if op == "var":
        if set(value) != {"op", "name"} or not isinstance(value["name"], str) or not value["name"].isidentifier() or len(value["name"]) > 80:
            raise ProofError("invalid propositional variable")
        return ("var", value["name"])
    if op in ("top", "bot"):
        if set(value) != {"op"}:
            raise ProofError("unexpected fields for constant")
        return (op,)
    if op == "not":
        if set(value) != {"op", "arg"}:
            raise ProofError("not requires arg")
        return ("imp", parse_formula(value["arg"], depth+1), ("bot",))
    if op in ("and", "or", "imp", "iff"):
        if set(value) != {"op", "left", "right"}:
            raise ProofError("binary formula requires left/right")
        lhs, rhs = parse_formula(value["left"],depth+1),parse_formula(value["right"],depth+1)
        if op == "iff":
            return ("and", ("imp",lhs,rhs),("imp",rhs,lhs))
        return (op,lhs,rhs)
    raise ProofError("unsupported logical operation")


def nodes(node):
    return strict_json.validate(node)


def formula_equal(left, right):
    """Structural equality of normalized DAGs, without exponential unfolding."""
    todo = [(left, right)]
    seen = set()
    while todo:
        a, b = todo.pop()
        if a is b:
            continue
        pair = (id(a), id(b))
        if pair in seen:
            continue
        seen.add(pair)
        if a[0] != b[0] or len(a) != len(b):
            return False
        if a[0] == "var":
            if a[1] != b[1]:
                return False
        else:
            todo.extend(zip(a[1:], b[1:]))
        if len(seen) > 4 * MAX_NODES:
            raise ResourceLimitError("normalized formula comparison budget exceeded")
    return True


def formula_nodes(formulas):
    seen = set()
    todo = list(formulas)
    while todo:
        f = todo.pop()
        if id(f) in seen:
            continue
        seen.add(id(f))
        yield f
        if f[0] != "var":
            todo.extend(f[1:])


def atoms(formula):
    return {f[1] for f in formula_nodes([formula]) if f[0] == "var"}


def evaluate(formula, assignment, cache=None):
    cache = {} if cache is None else cache
    todo = [(formula, False)]
    while todo:
        f, ready = todo.pop()
        if id(f) in cache:
            continue
        op = f[0]
        if op == "var":
            cache[id(f)] = assignment[f[1]]
        elif op in ("top", "bot"):
            cache[id(f)] = op == "top"
        elif op in ("and", "or", "imp"):
            if not ready:
                todo.append((f, True))
                todo.extend((child, False) for child in f[1:])
            else:
                a, b = cache[id(f[1])], cache[id(f[2])]
                cache[id(f)] = (a and b) if op == "and" else (a or b) if op == "or" else (not a or b)
        else:
            raise ProofError("unsupported internal formula")
    return cache[id(formula)]


def _deduce(proof, env, depth=0, budget=None):
    """Proof-term typing by checking exact introduction/elimination rules."""
    if budget is None:
        budget = [MAX_NODES]
    budget[0] -= 1
    if budget[0] < 0 or depth > MAX_DEPTH:
        raise ResourceLimitError("proof size/depth limit")
    if not isinstance(proof, dict) or not isinstance(proof.get("rule"), str):
        raise ProofError("invalid proof term")
    rule = proof["rule"]
    def expect(*keys):
        if set(proof) != {"rule", *keys}:
            raise ProofError("invalid fields for rule " + rule)
    def sub(key, next_env=None):
        return _deduce(proof[key], env if next_env is None else next_env, depth+1,budget)
    if rule == "hyp":
        expect("name")
        ident=proof["name"]
        if not isinstance(ident,str) or ident not in env:
            raise ProofError("unknown hypothesis")
        return env[ident]
    if rule == "top_intro":
        expect()
        return ("top",)
    if rule == "and_intro":
        expect("left","right")
        return ("and",sub("left"),sub("right"))
    if rule in ("and_left","and_right"):
        expect("source")
        f=sub("source")
        if f[0]!="and":
            raise ProofError("and elimination requires conjunction")
        return f[1] if rule=="and_left" else f[2]
    if rule in ("or_left","or_right"):
        expect("proof","other")
        f=sub("proof")
        g=parse_formula(proof["other"])
        return ("or",f,g) if rule=="or_left" else ("or",g,f)
    if rule=="imp_intro":
        expect("name","assumption","body")
        name=proof["name"]
        if not isinstance(name,str) or not name.isidentifier() or name in env:
            raise ProofError("hypothesis name is invalid or would shadow an existing hypothesis")
        antecedent=parse_formula(proof["assumption"])
        extended={**env,name:antecedent}
        return ("imp", antecedent, sub("body",extended))
    if rule=="imp_elim":
        expect("imp","arg")
        maj=sub("imp")
        minor=sub("arg")
        if maj[0]!="imp" or not formula_equal(maj[1],minor):
            raise ProofError("implication elimination mismatch")
        return maj[2]
    if rule=="or_elim":
        expect("source","left_name","left_proof","right_name","right_proof")
        disj=sub("source")
        if disj[0]!="or":
            raise ProofError("or elimination requires disjunction")
        a,b=proof["left_name"],proof["right_name"]
        if (not isinstance(a,str) or not a.isidentifier() or a in env or
            not isinstance(b,str) or not b.isidentifier() or b in env):
            raise ProofError("invalid branch-local hypothesis")
        left=sub("left_proof",{**env,a:disj[1]})
        right=sub("right_proof",{**env,b:disj[2]})
        if not formula_equal(left, right):
            raise ProofError("or branches must produce the same conclusion")
        return left
    if rule=="bot_elim":
        expect("source","conclusion")
        if sub("source")!=("bot",):
            raise ProofError("ex falso requires a derivation of false")
        return parse_formula(proof["conclusion"])
    raise ProofError("unrecognized inference rule: " + rule)


def audit_truth_table(hypotheses, goal):
    """Independent finite semantic check of the *sequent* for ≤12 atoms."""
    names=sorted(set().union(atoms(goal),*(atoms(v) for v in hypotheses.values())))
    if len(names)>MAX_ATOMS_FOR_AUDIT:
        return {"audited":False,"reason":"more than 12 atoms"}
    work = sum(1 for _ in formula_nodes([goal, *hypotheses.values()])) * (2 ** len(names))
    if work > MAX_SEMANTIC_WORK:
        return {"audited":False,"reason":"secondary semantic audit work budget exceeded"}
    checked=0
    for bits in itertools.product((False,True),repeat=len(names)):
        env=dict(zip(names,bits))
        checked+=1
        cache = {}
        if all(evaluate(p,env,cache) for p in hypotheses.values()) and not evaluate(goal,env,cache):
            return {"audited":True,"entailed":False,"checked":checked,
                    "countermodel":env}
    return {"audited":True,"entailed":True,"checked":checked}


def check_proposition(cert):
    """Return fragment-level machine proof result, with optional model binding."""
    try:
        if not isinstance(cert,dict) or set(cert) != {"kind","assumptions","conclusion","proof"} or cert["kind"]!="propositional":
            raise ProofError("unsupported proposition certificate shape")
        strict_json.validate(cert, max_nodes=MAX_NODES)
        hyps=cert["assumptions"]
        if not isinstance(hyps,dict) or len(hyps)>50 or any(
                not isinstance(n,str) or not n.isidentifier() for n in hyps):
            raise ProofError("invalid hypotheses")
        parsed={k:parse_formula(v) for k,v in hyps.items()}
        conclusion=parse_formula(cert["conclusion"])
        inferred=_deduce(cert["proof"],parsed)
        if not formula_equal(inferred,conclusion):
            raise ProofError("proof concludes a different proposition")
        audit=audit_truth_table(parsed,conclusion)
        if audit.get("audited") and not audit["entailed"]:
            raise ProofError("trusted checker inconsistency: semantic countermodel!")
        return {"status":"fragment_machine_checked","fragment":"intuitionistic_propositional",
                "certificate_sha256":fingerprint(cert),"truth_table":audit,
                "scope":"The formal propositional sequent ONLY; no algorithm-correctness claim"}
    except ResourceLimitError as exc:
        return {"status":"resource_limit","fragment":"intuitionistic_propositional","reason":str(exc)}
    except (ProofError,TypeError,ValueError,KeyError,RecursionError) as exc:
        return {"status":"rejected","fragment":"intuitionistic_propositional","reason":str(exc)}


def _check_case(case):
    if not isinstance(case,dict) or set(case)!={"input_id","states","initial","allowed_outputs"}:
        raise ProofError("invalid transition-system case")
    states=case["states"]
    if not isinstance(states,dict) or not states:
        raise ProofError("empty or invalid finite state set")
    if len(states)>10000:
        raise ResourceLimitError("finite state set exceeds 10000 states")
    if any(not isinstance(s,str) or not s for s in states):
        raise ProofError("state IDs must be strings")
    start=case["initial"]
    if not isinstance(start,list) or not start or any(not isinstance(x,str) or x not in states for x in start):
        raise ProofError("initial states missing or invalid")
    permitted=case["allowed_outputs"]
    if not isinstance(permitted,list) or not permitted:
        raise ProofError("postcondition must permit at least one output")
    for key,node in states.items():
        if not isinstance(node,dict) or set(node)!={"halt","next","output"}:
            raise ProofError("state fields invalid for "+key)
        if type(node["halt"]) is not bool or not isinstance(node["next"],list):
            raise ProofError("state types invalid for "+key)
        if len(set(map(canonical,node["next"]))) != len(node["next"]) or any(
                not isinstance(s,str) or s not in states for s in node["next"]):
            raise ProofError("transition points outside finite state space")
        if node["halt"] and node["next"]:
            raise ProofError("halted state cannot have outgoing transitions")
        if not node["halt"] and "output" not in node:
            raise ProofError("invalid output representation")
    permitted = {canonical(value) for value in permitted}
    color={}
    reachable=set()
    visited_edges=0
    stack=[]
    def enter(s):
        color[s]=1
        reachable.add(s)
        node=states[s]
        if node["halt"]:
            if canonical(node["output"]) not in permitted:
                raise ProofError("terminal output violates specified postcondition")
        else:
            if not node["next"]:
                raise ProofError("reachable nonterminal deadlock")
        stack.append((s, iter(node["next"])))
    for s in start:
        if color.get(s)==2:
            continue
        enter(s)
        while stack:
            current, successors=stack[-1]
            v=next(successors,None)
            if v is None:
                color[current]=2
                stack.pop()
                continue
            visited_edges+=1
            if color.get(v)==1:
                raise ProofError("reachable cycle: infinite execution is possible")
            if color.get(v)!=2:
                enter(v)
    return {"reachable_states":len(reachable),"reachable_edges":visited_edges,
            "finite_state_count":len(states)}


def check_machine(cert):
    """Exact total correctness for the finite domain *as explicitly enumerated*."""
    try:
        if not isinstance(cert,dict) or set(cert)!={"kind","input_domain","cases"} or cert["kind"]!="finite_transition_system":
            raise ProofError("invalid finite-state certificate shape")
        strict_json.validate(cert)
        domain=cert["input_domain"]
        cases=cert["cases"]
        if not isinstance(domain,list) or not domain or not isinstance(cases,list):
            raise ProofError("must provide finite explicit nonempty input domain")
        if len(domain)>1000:
            raise ResourceLimitError("finite input domain exceeds 1000 cases")
        ids=[canonical(x) for x in domain]
        if len(ids)!=len(set(ids)):
            raise ProofError("duplicate domain element")
        caseids=[canonical(c.get("input_id")) if isinstance(c,dict) else None for c in cases]
        if len(caseids)!=len(set(caseids)) or set(ids)!=set(caseids):
            raise ProofError("uncovered, duplicate, or out-of-domain input cases")
        total_s=total_e=0
        for c in cases:
            counts=_check_case(c)
            total_s+=counts["reachable_states"]
            total_e+=counts["reachable_edges"]
        return {"status":"finite_domain_machine_checked",
                "fragment":"explicit_finite_transition_system",
                "certificate_sha256":fingerprint(cert),"input_cases":len(domain),
                "reachable_states":total_s,"reachable_edges":total_e,
                "scope":"Total correctness for exactly this enumerated input domain and explicitly supplied transition semantics; no assertion about arbitrary external code"}
    except ResourceLimitError as exc:
        return {"status":"resource_limit","fragment":"explicit_finite_transition_system","reason":str(exc)}
    except (ProofError,TypeError,ValueError,KeyError,RecursionError) as exc:
        return {"status":"rejected","fragment":"explicit_finite_transition_system","reason":str(exc)}


def lean_status():
    def installed(name):
        return shutil.which(name) is not None or (Path.home()/".elan"/"bin"/name).exists()
    return {"lean_available":installed("lean"),
            "lake_available":installed("lake"),
            "leanchecker_available":installed("leanchecker"),
            "lean4checker_deprecated":True,
            "lean_example":str(ROOT/"references"/"PPC3Examples.lean"),
            "machine_checked_by_lean":False,
            "note":"This command only detects installed executables; run scripts/ppc3_lean.py to compile the actual proofs, audit their axioms and replay them through leanchecker."}


def main():
    p=argparse.ArgumentParser(description="PPC 3.0 restricted sound proof checker")
    sub=p.add_subparsers(dest="action",required=True)
    s=sub.add_parser("proposition")
    s.add_argument("--file",type=Path,required=True)
    m=sub.add_parser("finite-machine")
    m.add_argument("--file",type=Path,required=True)
    sub.add_parser("lean-status")
    args=p.parse_args()
    if args.action=="lean-status":
        res=lean_status()
    else:
        try:
            obj, source_hash=strict_json.load_with_digest(args.file)
            res=check_proposition(obj) if args.action=="proposition" else check_machine(obj)
            res["source_sha256"]=source_hash
        except ResourceLimitError as exc:
            res={"status":"resource_limit","reason":str(exc)}
        except (ValueError,OSError) as exc:
            res={"status":"rejected","reason":str(exc)}
    print(json.dumps(res,indent=2,ensure_ascii=False))
    if res.get("status") in ("rejected","resource_limit"):
        raise SystemExit(1)


if __name__=="__main__":
    main()
