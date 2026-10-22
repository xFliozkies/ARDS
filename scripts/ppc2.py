#!/usr/bin/env python3
"""PPC 2.0 structural conformance checker and reproducible dual ARDS/PPC benchmark.

This is NOT a theorem prover. It verifies structure/traceability and runs bounded,
independent first-party ARDS oracles. Never execute untrusted generated code.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import random
from collections import deque
from pathlib import Path
import strict_json

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.0"
TECHNIQUES = {
    "case_analysis": {"coverage", "correctness_each_case"},
    "loop_invariant": {"initialization", "preservation", "exit_implies_post"},
    "induction": {"base_case", "inductive_step"},
    "exchange_argument": {"feasibility", "exchange_step", "global_optimality"},
    "graph_reachability": {"encoding_equivalence", "exploration_complete"},
    "combinatorial_bound": {"lower_bound", "upper_bound_achievable"},
    "prefix_aggregation": {"prefix_invariant", "query_identity"},
    "search_exhaustion": {"search_complete", "witness_or_counterexample"},
}
COMMON = {"specification_total", "algorithm_defined", "termination",
          "partial_correctness", "complexity"}
EXTRA_FAMILIES = {"missing_positive", "range_sum", "interval_lamps", "graph_reachability"}


def canonical(data):
    return strict_json.canonical(data)


def sha256(data):
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def check_certificate(body):
    try:
        strict_json.validate(body)
        return _check_certificate(body)
    except (ValueError,TypeError,KeyError,RecursionError) as exc:
        return {"status":"rejected","errors":[str(exc)],"proof_checked":False,
                "reason_code":"resource_limit" if isinstance(exc,strict_json.ResourceLimitError) else "invalid_certificate"}


def _check_certificate(body):
    """Enforce a *structural* certificate contract. No semantic inference checking."""
    problems = []
    if not isinstance(body, dict) or not isinstance(body.get("model"), dict):
        return {"status": "rejected", "errors": ["missing model"], "proof_checked": False}
    c = body.get("ppc")
    if not isinstance(c, dict):
        return {"status": "rejected", "errors": ["missing ppc certificate"], "proof_checked": False}
    if c.get("version") != VERSION:
        problems.append("unknown PPC version")
    if c.get("model_hash") != sha256(body["model"]):
        problems.append("certificate does not bind to this exact mathematical model")
    if c.get("asserted_status") not in ("drafted", "structure_checked"):
        problems.append("unearned proof status")
    tech = c.get("technique")
    if not isinstance(tech,str) or tech not in TECHNIQUES:
        problems.append("unknown proof technique")
        tech = None
    for section, fields in {
        "problem": ("domain", "codomain", "postcondition", "objective_kind"),
        "algorithm": ("state", "initialization", "transition", "halt", "output", "cost_model"),
        "complexity": ("input_measure", "time_bound", "space_bound", "derivation"),
    }.items():
        part = c.get(section)
        if not isinstance(part, dict) or any(
                not isinstance(part.get(k), str) or not part[k].strip() for k in fields):
            problems.append("incomplete " + section + " contract")
    obs = c.get("obligations")
    if not isinstance(obs, list) or not obs:
        problems.append("missing proof obligations")
        obs = []
    ids = set()
    graph = {}
    for ob in obs:
        if not isinstance(ob, dict):
            problems.append("non-object obligation")
            continue
        name = ob.get("id")
        if not isinstance(name, str) or not name.strip() or name in ids:
            problems.append("invalid or duplicate obligation ID")
            continue
        ids.add(name)
        graph[name] = ob.get("depends_on", [])
        if any(not isinstance(ob.get(k), str) or not ob[k].strip()
               for k in ("claim", "argument")):
            problems.append("empty proof claim or argument: " + name)
        if not isinstance(graph[name], list) or not all(
                isinstance(v, str) for v in graph[name]):
            problems.append("invalid dependencies for: " + name)
            graph[name] = []
    required = COMMON | TECHNIQUES.get(tech, set())
    problem_meta = c.get("problem") if isinstance(c.get("problem"), dict) else {}
    if problem_meta.get("objective_kind") == "optimization":
        required |= {"optimality", "feasibility"}
    if problem_meta.get("requires_witness"):
        required.add("existential_witness")
    missing = sorted(required - ids)
    if missing:
        problems.append("missing obligations: " + ", ".join(missing))
    color = {}
    for v in graph:
        if color.get(v)==2:
            continue
        color[v]=1
        stack=[(v,iter(graph[v]))]
        while stack:
            current, edges=stack[-1]
            u=next(edges,None)
            if u is None:
                color[current]=2; stack.pop(); continue
            if u not in graph or color.get(u)==1:
                problems.append("cyclic or unresolved proof dependency: " + u)
                stack.clear(); break
            if color.get(u)!=2:
                color[u]=1; stack.append((u,iter(graph[u])))
        if problems and any("dependency:" in p for p in problems):
            break
    return {"status": "rejected" if problems else "structure_checked",
            "errors": problems, "proof_checked": False,
            "obligation_count": len(ids), "technique": tech}


def _missing_fast(a):
    n = len(a)
    seen = [False] * (n + 2)
    for x in a:
        if 1 <= x <= n + 1:
            seen[x] = True
    return next(k for k in range(1, n + 2) if not seen[k])


def _missing_oracle(a):
    s = set(a)
    k = 1
    while k in s:
        k += 1
    return k


def _range_fast(a, l, r):
    prefix = [0]
    for x in a:
        prefix.append(prefix[-1] + x)
    return prefix[r + 1] - prefix[l]


def _range_oracle(a, l, r):
    return sum(a[l:r + 1])


def _lamps_fast(a, radius):
    a = sorted(a)
    count, i = 0, 0
    while i < len(a):
        farthest = a[i] + 2 * radius
        count += 1
        while i < len(a) and a[i] <= farthest:
            i += 1
    return count


def _lamps_oracle(a, radius):
    """Enumerate all subsets of canonical rightmost centers, independent of greedy."""
    a = list(a)
    if not a:
        return 0
    centers = [x + radius for x in sorted(set(a))]
    for k in range(1, len(centers) + 1):
        for subset in itertools.combinations(centers, k):
            if all(any(abs(x - c) <= radius for c in subset) for x in a):
                return k
    raise AssertionError("No feasible lantern placement")


def _graph_fast(n, edges, source, target, directed):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        if not directed:
            adj[v].append(u)
    seen = {source}
    q = deque([source])
    while q:
        u = q.popleft()
        if u == target:
            return True
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                q.append(v)
    return False


def _graph_oracle(n, edges, source, target, directed):
    reachable = [[i == j for j in range(n)] for i in range(n)]
    for u, v in edges:
        reachable[u][v] = True
        if not directed:
            reachable[v][u] = True
    for mid in range(n):
        for u in range(n):
            for v in range(n):
                reachable[u][v] = reachable[u][v] or (
                    reachable[u][mid] and reachable[mid][v])
    return reachable[source][target]


def _valid_graph(n, edges, source, target):
    return (type(n) is int and n >= 1 and type(source) is int and
            type(target) is int and 0 <= source < n and 0 <= target < n and
            isinstance(edges, list) and all(
                isinstance(e, (tuple, list)) and len(e) == 2 and
                all(type(v) is int and 0 <= v < n for v in e) for e in edges))


def verify_extra_family(body):
    """Finite oracle checks for four additional built-in algorithm families."""
    model = body["model"]
    family, p = model["family"], model["parameters"]
    checked = 0
    try:
        if family == "missing_positive":
            m, alphabet = p.get("max_len"), p.get("alphabet")
            if type(m) is not int or not 1 <= m <= 5 or not isinstance(alphabet, list) or not 2 <= len(alphabet) <= 5 or len(set(map(str,alphabet))) != len(alphabet) or any(type(v) is not int for v in alphabet):
                raise ValueError("Invalid missing-positive bounds")
            for n in range(m + 1):
                for a in itertools.product(alphabet, repeat=n):
                    if _missing_fast(a) != _missing_oracle(a):
                        return {"outcome":"failed","tests_run":checked+1,"reason":"Mismatch: "+repr(a)}
                    checked += 1
            for s in body["samples"]:
                a = strict_json.loads(s["input"])
                if not isinstance(a, list) or any(type(v) is not int for v in a) or len(a)>m or any(v not in alphabet for v in a) or str(_missing_fast(a)) != s["output"].strip():
                    raise ValueError("Invalid missing-positive sample")
                checked += 1
        elif family == "range_sum":
            m, alphabet = p.get("max_len"), p.get("alphabet")
            if type(m) is not int or not 1 <= m <= 5 or not isinstance(alphabet,list) or not 1 <= len(alphabet) <= 5 or any(type(v) is not int for v in alphabet):
                raise ValueError("Invalid range-sum bounds")
            for n in range(1, m+1):
                for a in itertools.product(alphabet, repeat=n):
                    for l in range(n):
                        for r in range(l,n):
                            if _range_fast(a,l,r) != _range_oracle(a,l,r):
                                return {"outcome":"failed","tests_run":checked+1,"reason":"Mismatch: "+repr((a,l,r))}
                            checked += 1
            for s in body["samples"]:
                v = strict_json.loads(s["input"])
                a, queries = v["array"], v["queries"]
                if not isinstance(a,list) or not 1 <= len(a) <= m or any(type(x) is not int or x not in alphabet for x in a) or not isinstance(queries,list) or any(
                  not isinstance(q,list) or len(q)!=2 or any(type(x) is not int for x in q) or not 0<=q[0]<=q[1]<len(a) for q in queries):
                    raise ValueError("Invalid range-sum sample")
                outputs = strict_json.loads(s["output"])
                if (not isinstance(outputs,list) or any(type(x) is not int for x in outputs) or
                        outputs != [_range_fast(a,*q) for q in queries]):
                    raise ValueError("Wrong range-sum sample")
                checked += 1
        elif family == "interval_lamps":
            radius,m,max_coord = (p.get(k) for k in ("radius","max_stalls","max_coord"))
            if any(type(v) is not int for v in (radius,m,max_coord)) or not 0 <= radius <= 8 or not 1 <= m <= 5 or not 0 <= max_coord <= 9:
                raise ValueError("Invalid lantern bounds")
            for n in range(1,m+1):
                for a in itertools.combinations_with_replacement(range(max_coord+1),n):
                    if _lamps_fast(a,radius) != _lamps_oracle(a,radius):
                        return {"outcome":"failed","tests_run":checked+1,"reason":"Mismatch: "+repr(a)}
                    checked += 1
            for s in body["samples"]:
                a = strict_json.loads(s["input"])
                if not isinstance(a,list) or not 1<=len(a)<=m or any(type(v) is not int or not 0<=v<=max_coord for v in a) or str(_lamps_fast(a,radius)) != s["output"].strip():
                    raise ValueError("Invalid lantern sample")
                checked += 1
        elif family == "graph_reachability":
            n, directed = p.get("max_nodes"),p.get("directed")
            if type(n) is not int or not 2 <= n <= 4 or type(directed) is not bool:
                raise ValueError("Invalid graph bounds")
            for size in range(2,n+1):
                candidates = [(u,v) for u in range(size) for v in range(size)
                              if u != v and (directed or u<v)]
                for bits in itertools.product((0,1),repeat=len(candidates)):
                    edges = [e for bit,e in zip(bits,candidates) if bit]
                    for target in range(size):
                        if _graph_fast(size,edges,0,target,directed) != _graph_oracle(size,edges,0,target,directed):
                            return {"outcome":"failed","tests_run":checked+1,"reason":"Mismatch: "+repr(edges)}
                        checked += 1
            for s in body["samples"]:
                v = strict_json.loads(s["input"])
                size, edges, src, dst = (v[k] for k in ("n","edges","source","target"))
                if (not _valid_graph(size,edges,src,dst) or not 2<=size<=n or
                        any(u==v for u,v in edges)):
                    raise ValueError("Invalid graph sample")
                expected = "YES" if _graph_fast(size,edges,src,dst,directed) else "NO"
                if s["output"].strip() != expected:
                    raise ValueError("Wrong graph sample")
                checked += 1
        else:
            return {"outcome":"experimental","tests_run":0,"reason":"Unrecognized PPC family"}
    except (ValueError,TypeError,KeyError,IndexError,OverflowError) as exc:
        return {"outcome":"failed","tests_run":checked,"reason":str(exc)}
    return {"outcome":"test_verified","tests_run":checked,
            "reason":"Bounded independent oracles and provided samples agree; universal proof NOT checked."}


# PPC certificates are human-authored argument scaffolds, NOT generated formal proofs.
FAMILY_PROOFS = {
 "tiered_price": {
    "technique":"case_analysis", "kind":"function", "pattern":["F02","F03"],
    "post":"Return n multiplied by full price when n<threshold, otherwise n multiplied by discounted price.",
    "core":"For any valid n, exactly one of n<threshold and n>=threshold holds. The applicable price is charged to every cake, so multiplying by n returns the specification.",
    "steps":{"coverage":"The trichotomy of integer comparison partitions n into n<threshold and n>=threshold.",
             "correctness_each_case":"Substituting the per-item price defined for each branch gives n*price in both cases."},
    "complexity":("1","O(1)","O(1)","One comparison and one multiplication under bounded-word RAM."),
 },
 "opposite_rotations": {
    "technique":"loop_invariant", "kind":"decision", "pattern":["S01","S03"],
    "post":"YES iff there exists V with both L(V)=S and R(V)=S.",
    "core":"L(V)=S uniquely implies V=R(S). Substituting into R(V)=S yields R^2(S)=S, equivalently S[i]=S[(i+2) mod n] for all indices.",
    "steps":{"initialization":"Before checking index 0, no comparison has failed and the empty prefix satisfies the invariant.",
             "preservation":"After processing index i, the accumulated Boolean equals the conjunction of comparisons for all indices <=i.",
             "exit_implies_post":"After n comparisons the conjunction covers all indices, exactly the feasibility condition."},
    "complexity":("n=|S|","O(n)","O(1)","Each of n indices is checked once with constant additional state."),
 },
 "comparison_maxima": {
    "technique":"combinatorial_bound", "kind":"counting", "pattern":["S05","S10","C01"],
    "post":"Count indices that can be the global maximum in some integer array compatible with adjacent comparison bits.",
    "core":"A peak position is necessary: to its left the adjacent inequality must rise into it, to its right it must fall away. Every such local peak is sufficient: orient each comparison edge from greater to smaller; a line of oriented edges is acyclic, and a local peak can be made the unique maximum by a topological ordering (or height assignment).",
    "steps":{"lower_bound":"Any position that is maximum must beat its immediate neighbors; hence it must satisfy the peak predicate.",
             "upper_bound_achievable":"For each satisfying index, add edges from it to all other nodes; none can lead back to it because both adjacent edges point outward. The directed graph remains acyclic and has a strictly decreasing integer labeling from that index."},
    "complexity":("n=|S|+1","O(n)","O(1)","Evaluate the candidate predicate at each of n positions."),
 },
 "missing_positive": {
    "technique":"loop_invariant", "kind":"function", "pattern":["F06","S04"],
    "post":"Return the least positive integer absent from an integer array.",
    "core":"Among n values at least one of 1..n+1 is missing. Mark only in-range positive values and scan increasing candidates; the first unmarked integer is precisely the least missing positive.",
    "steps":{"initialization":"The empty scanned prefix contains no marked values.",
             "preservation":"Processing each element changes exactly its in-range presence flag; the flags describe the scanned prefix.",
             "exit_implies_post":"At loop end the flags describe the entire array; ascending scan returns the least unmarked 1..n+1."},
    "complexity":("n=number of elements","O(n)","O(n)","Boolean presence table length n+2 and two finite linear passes."),
 },
 "range_sum": {
    "technique":"prefix_aggregation", "kind":"function", "pattern":["S06"],
    "post":"Return the sum of the values in each inclusive query interval [l,r].",
    "core":"Let pref[0]=0 and pref[i+1]=pref[i]+A[i]. By induction pref[k] is the sum of A[0..k-1]; subtracting pref[l] from pref[r+1] cancels the prefix before l.",
    "steps":{"prefix_invariant":"After processing i elements, pref[i] equals the sum of the first i values.",
             "query_identity":"pref[r+1]-pref[l] telescopes to sum of A[l..r]."},
    "complexity":("n=array length; q=query count","O(n+q)","O(n)","One prefix construction and O(1) processing per query."),
 },
 "interval_lamps": {
    "technique":"exchange_argument", "kind":"optimization", "pattern":["C08","S10"],
    "post":"Minimize the number of lanterns of radius R needed to cover all stalls at nonnegative coordinates.",
    "core":"For the leftmost uncovered stall x, some lantern in any solution must cover x. Shifting the lantern used for x to center x+R cannot lose coverage of any remaining stall at coordinates >=x, and covers all stalls up to x+2R. Thus some optimum shares the greedy first lantern; repeat on the suffix.",
    "steps":{"feasibility":"Each greedy lantern at x+R covers the current first stall and every stall through x+2R.",
             "exchange_step":"In an optimal suffix solution replace the lantern covering x by the one centered at x+R; all yet-uncovered stalls are >=x, so coverage is preserved.",
             "global_optimality":"Exchange followed by induction on remaining uncovered stalls shows there is an optimum beginning with each greedy placement."},
    "complexity":("n=number of stalls","O(n log n)","O(n)","Sort stalls then scan once; sorting copy counted as auxiliary storage."),
 },
 "graph_reachability": {
    "technique":"graph_reachability", "kind":"decision", "pattern":["C12","S09"],
    "post":"YES iff target is reachable from source by a path respecting edge direction.",
    "core":"BFS begins with the source and adds only vertices reached from a visited vertex. Inductively every visited vertex has a valid source path. Any reachable target has a finite path; when each preceding vertex is removed from the queue, its successor is eventually discovered.",
    "steps":{"encoding_equivalence":"Adjacency lists represent exactly the directed or undirected input edges.",
             "exploration_complete":"Every reachable vertex is discovered by induction on shortest path length; unreachable vertices cannot be discovered."},
    "complexity":("n=vertices; m=edges","O(n+m)","O(n+m)","Adjacency construction, queue and visited set process each vertex and edge bounded times."),
 },
}


def make_certificate(model, family):
    p = FAMILY_PROOFS[family]
    technique = p["technique"]
    arguments = {
        "specification_total":"The input domains, representation and required output relation are stated in the model and its accompanying statement.",
        "algorithm_defined":"State and transitions in the prescribed family algorithm are defined for all inputs satisfying the stated domain.",
        "termination":"The family algorithm processes a finite array, finite string, finite graph, or strictly shrinking uncovered suffix, using a finite loop bound or decreasing natural-number measure.",
        "partial_correctness":p["core"],
        "complexity":p["complexity"][3],
    }
    arguments.update(p["steps"])
    if p["kind"] == "optimization":
        arguments.update({
            "optimality":p["steps"]["global_optimality"],
            "feasibility":p["steps"]["feasibility"]})
    obs = []
    for name in sorted(arguments):
        obs.append({"id":name,"claim":name.replace("_"," ")+" is established for this problem family.",
                    "argument":arguments[name], "depends_on":[]})
    return {
        "version":VERSION, "model_hash":sha256(model),
        "asserted_status":"drafted", "technique":technique,
        "problem":{"domain":canonical(model["inputs"]),
                   "codomain":"Output defined by the exact model objective",
                   "postcondition":p["post"],"objective_kind":p["kind"]},
        "algorithm":{"state":"Family-specific finite scan state, arrays and counters",
                     "initialization":"Empty/zero state, initial source or leftmost uncovered stall",
                     "transition":"Advance by one input unit or consume next valid element",
                     "halt":"Finite loop completed or no uncovered/unvisited elements remain",
                     "output":"Computed family answer",
                     "cost_model":"Unit-cost RAM for bounded integer words; sorting comparisons unit cost"},
        "complexity":{"input_measure":p["complexity"][0],
                      "time_bound":p["complexity"][1],
                      "space_bound":p["complexity"][2],
                      "derivation":p["complexity"][3]},
        "obligations":obs
    }


def make_problem(index, rng):
    """Seven families, case-specific mathematical parameters and sample values."""
    import ards2
    family = list(FAMILY_PROOFS)[index % len(FAMILY_PROOFS)]
    name = "PPC2-STRESS-%03d" % (index + 1)
    n = 2 + index % 3
    if family == "tiered_price":
        threshold=2+(index%7)
        full=52+index*3
        discounted=max(0,full-(4+index%19))
        params={"threshold":threshold,"full":full,"discounted":discounted,"min_n":1,"max_n":threshold+4}
        sample_n=threshold if index%2 else threshold-1
        sin,sout=str(sample_n),str(sample_n*(discounted if sample_n>=threshold else full))
        statement=f"Given an integer N from 1 to {threshold+4}, each item costs {full} units, or {discounted} units for all items when N >= {threshold}. Output total cost."
        inputs={"N":f"integer, 1..{threshold+4}"}
        constraints=["All N items use the same threshold-based unit price."]
        objective="Compute the total purchase cost."
    elif family == "opposite_rotations":
        alpha="ab" if index%2 else "abc"
        maximum=4+index%3
        params={"alphabet":alpha,"exhaustive_max_n":maximum}
        sin="abab" if index%2 else "abc"
        sout="YES" if ards2._rotate_methods(sin)[0] else "NO"
        statement=f"For a nonempty string S over {alpha}, length <= {maximum}, determine if one V has both its left and right one-step rotations equal S."
        inputs={"S":f"string of characters in {alpha}, length 1..{maximum}"}
        constraints=["L(V)=S and R(V)=S must hold for the same V."]
        objective="Output YES if such a string V exists, otherwise NO."
    elif family == "comparison_maxima":
        maximum=5+index%4
        params={"exhaustive_max_n":maximum}
        sin="".join(rng.choice("01") for _ in range(2+index%4))
        sout=str(ards2._maxima_methods(sin)[0])
        statement=f"An unknown integer array has adjacent comparisons S of 0 (increase) and 1 (decrease). For length N<= {maximum}, count positions that can be global maxima in some compatible array. Input S has N-1 bits."
        inputs={"S":f"binary string, length 1..{maximum-1}"}
        constraints=["Bit 0 means Ai<Ai+1; bit 1 means Ai>Ai+1."]
        objective="Count indices for which a compatible maximum witness exists."
    elif family == "missing_positive":
        alphabet=[-2,0,1,2,3] if index%2 else [-1,1,2,4]
        maximum=2+index%3
        params={"alphabet":alphabet,"max_len":maximum}
        arr=[rng.choice(alphabet) for _ in range(maximum)]
        sin=canonical(arr)
        sout=str(_missing_fast(arr))
        statement=f"Given an integer array of length 0..{maximum} with elements in {alphabet}, output the least positive integer absent from the array."
        inputs={"A":f"array length 0..{maximum}, elements in {alphabet}"}
        constraints=["Duplicates are allowed; missing candidate is positive."]
        objective="Find smallest absent positive integer."
    elif family == "range_sum":
        alphabet=[-3,0,2] if index%2 else [-1,1,4]
        maximum=2+index%3
        params={"alphabet":alphabet,"max_len":maximum}
        arr=[rng.choice(alphabet) for _ in range(maximum)]
        queries=[[0,maximum-1],[maximum-1,maximum-1]]
        sin=canonical({"array":arr,"queries":queries})
        sout=canonical([_range_fast(arr,*q) for q in queries])
        statement=f"Given array A of length 1..{maximum} over {alphabet} and inclusive zero-based range queries [l,r], return a sum for every query."
        inputs={"A":f"array length 1..{maximum} over {alphabet}","queries":"valid inclusive index ranges"}
        constraints=["Each query satisfies 0<=l<=r<length(A)."]
        objective="Return exact sums of all query intervals."
    elif family == "interval_lamps":
        radius=index%4
        max_stalls=3+index%2
        max_coord=5+index%3
        params={"radius":radius,"max_stalls":max_stalls,"max_coord":max_coord}
        arr=sorted(rng.randrange(max_coord+1) for _ in range(max_stalls))
        sin=canonical(arr)
        sout=str(_lamps_fast(arr,radius))
        statement=f"Given 1..{max_stalls} stall coordinates in [0,{max_coord}], place minimum lanterns at nonnegative real positions. Each covers distance <= {radius}. Output the minimum."
        inputs={"stalls":f"array of 1..{max_stalls} integer coordinates in [0,{max_coord}]"}
        constraints=[f"Lantern position any real >=0; each covers all stalls within radius {radius}."]
        objective="Minimize number of lanterns covering all stalls."
    else:
        max_nodes=3+index%2
        directed=bool(index%2)
        params={"max_nodes":max_nodes,"directed":directed}
        n=max_nodes
        edges=[[u,u+1] for u in range(n-1)] if index%3 else [[0,1]]
        source,target=0,n-1
        sin=canonical({"n":n,"edges":edges,"source":source,"target":target})
        sout="YES" if _graph_fast(n,edges,source,target,directed) else "NO"
        statement=f"On a {'directed' if directed else 'undirected'} graph of 2..{max_nodes} nodes labeled 0..n-1, determine if target is reachable from source."
        inputs={"graph":f"{'directed' if directed else 'undirected'} graph with 2..{max_nodes} vertices",
                "source_target":"vertex indices in range"}
        constraints=["Edges join valid distinct vertices."]
        objective="Determine whether a source-target path exists."
    model={"inputs":inputs,"hidden_variables":[],"constraints":constraints,
           "objective":objective,"family":family,"parameters":params}
    proof=FAMILY_PROOFS[family]
    obj={"id":name, "title":"Validation problem "+name+": "+family.replace("_"," "),
         "statement":statement,"difficulty_estimate":{"tiered_price":1,
         "opposite_rotations":2,"comparison_maxima":3,"missing_positive":2,
         "range_sum":2,"interval_lamps":3,"graph_reachability":2}[family],
         "patterns":proof["pattern"],"provenance":"PPC 2.0 deterministic synthetic validation corpus; not an issued RACG challenge",
         "model":model,"reference_solution":proof["core"],"proof":proof["core"]+" "+ " ".join(proof["steps"].values()),
         "samples":[{"input":sin,"output":sout}],
         # A synthetic validation problem also travels with a private four-part
         # teacher PPC; formal certificate remains a separate evidence object.
         "teacher_ppc":{
             "problem":"Inputs: "+str(inputs)+". Constraints: "+ "; ".join(constraints)+
                        ". Required result: "+objective,
             "procedure":"Reference algorithm ("+family+"): "+proof["core"],
             "correctness":proof["core"]+" "+ " ".join(proof["steps"].values())+
                           " Finite-loop termination and any domain assumptions require review.",
             "complexity":"Input measure: "+str(proof["complexity"][0])+
                          ". Time: "+str(proof["complexity"][1])+
                          ". Extra space: "+str(proof["complexity"][2])+
                          ". Derivation: "+str(proof["complexity"][3])
         },
         "ppc":make_certificate(model,family)}
    ards2.validate_package(obj)
    return ards2.prepare_reference(obj)


def run_stress(count=100,seed=20261020,directory=None):
    import ards2
    from benchmark_io import provenance, write_immutable
    if type(count) is not int or not 1<=count<=1000:
        raise ValueError("count must be in 1..1000")
    rng=random.Random(seed)
    results=[]
    packets=[]
    totals={}
    for i in range(count):
        packet=make_problem(i,rng)
        check=check_certificate(packet)
        tested=ards2.verify_body(packet)
        family=packet["model"]["family"]
        entry={"id":packet["id"],"family":family,
               "package_sha256":sha256(packet),
               "ppc_status":check["status"],"proof_checked":check["proof_checked"],
               "ards_status":tested["outcome"],"bounded_tests":tested["tests_run"],
               "problems":check["errors"]+([tested["reason"]] if tested["outcome"]!="test_verified" else [])}
        totals[family]=totals.get(family,0)+1
        results.append(entry)
        packets.append(packet)
    # Negative controls: the linter must catch bad contracts; oracle must catch a false sample.
    mutant=make_problem(0,random.Random(seed))
    mutant["ppc"]["obligations"]=[o for o in mutant["ppc"]["obligations"]
                                    if o["id"]!="termination"]
    no_termination=check_certificate(mutant)["status"]=="rejected"
    mutant=make_problem(0,random.Random(seed))
    mutant["ppc"]["asserted_status"]="machine_checked"
    forged_status=check_certificate(mutant)["status"]=="rejected"
    mutant=make_problem(0,random.Random(seed))
    mutant["model"]["parameters"]["full"]+=1
    mismatch=check_certificate(mutant)["status"]=="rejected"
    mutant=make_problem(0,random.Random(seed))
    mutant["ppc"]["obligations"][0]["depends_on"]=[mutant["ppc"]["obligations"][0]["id"]]
    cyclic=check_certificate(mutant)["status"]=="rejected"
    mutant=make_problem(0,random.Random(seed))
    mutant["samples"][0]["output"]="incorrect"
    bad_output=ards2.verify_body(mutant)["outcome"]=="failed"
    negatives={"missing_termination":no_termination,"forged_machine_proof":forged_status,
               "changed_model":mismatch,"circular_dependency":cyclic,"bad_sample":bad_output}
    valid=sum(r["ppc_status"]=="structure_checked" and r["ards_status"]=="test_verified" for r in results)
    report={"protocol":"PPC 2.0 x ARDS 2.0","seed":seed,"requested":count,
            "provenance":provenance(),
            "generated":len(results),"dual_pass":valid,
            "dual_fail":count-valid,"families":totals,
            "finite_checks":sum(r["bounded_tests"] for r in results),
            "negative_controls":negatives,
            "unique_full_package_hashes":len(set(r["package_sha256"] for r in results)),
            "proofs_machine_checked":0,
            "scope":"Seven reviewed parametric families, NOT all 100 RACG topics. Bounded oracle evidence and PPC structural validation, NOT theorem checking.",
            "results":results}
    if directory is not None:
        folder=Path(directory) / ("seed-%d-n%d" % (seed,count))
        contents={"problems.jsonl":"".join(canonical(p)+"\n" for p in packets),
                  "report.json":json.dumps(report,indent=2,ensure_ascii=False)+"\n"}
        # Immutable benchmark corpus: equal reruns reuse files; a changed
        # generator must use a new seed/version, not silently rewrite history.
        write_immutable(folder,contents)
    return report


def main():
    parser=argparse.ArgumentParser(description="PPC 2.0 formal contract linter and bounded benchmark")
    sub=parser.add_subparsers(dest="command",required=True)
    c=sub.add_parser("check")
    c.add_argument("--file",type=Path,required=True)
    s=sub.add_parser("stress")
    s.add_argument("--count",type=int,default=100)
    s.add_argument("--seed",type=int,default=20261020)
    s.add_argument("--out",type=Path,default=ROOT/"data"/"validation"/"ppc2"/"hardened-v1")
    args=parser.parse_args()
    if args.command=="check":
        try:
            result=check_certificate(strict_json.load(args.file))
        except (ValueError,OSError) as exc:
            result={"status":"rejected","errors":[str(exc)],"proof_checked":False}
    else:
        if not 1<=args.count<=1000:
            parser.error("count must be in 1..1000")
        result=run_stress(args.count,args.seed,args.out)
        result={k:v for k,v in result.items() if k!="results"}
        if result["dual_fail"] or not all(result["negative_controls"].values()):
            print(json.dumps(result,indent=2))
            raise SystemExit(1)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if result.get("status")=="rejected":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
