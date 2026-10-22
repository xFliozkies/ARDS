#!/usr/bin/env python3
"""Conservative, provenance-aware longitudinal ARDS summaries.

Never equate assistance-dependent performance with independent performance.
Never impute missing data or claim comparability across different difficulties.
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
import memory


def summarise(con):
    rows=[dict(r) for r in con.execute("""
    SELECT c.external_id,c.title,c.session_type,c.difficulty,c.topic_label,
           a.id AS attempt_id, a.independent,a.hint_level,a.minutes_to_first_solution,
           a.time_source,a.confidence_percent,a.provenance,
           s.correct,s.optimality_verified,s.reviewer,s.id AS assessment_id,
           EXISTS(SELECT 1 FROM solution_reveals sr WHERE sr.challenge_id=c.id) AS solution_revealed,
           EXISTS(SELECT 1 FROM solution_reveals sr WHERE sr.challenge_id=c.id
                AND sr.preserved_attempt_id=a.id) AS protected_pass
    FROM attempts a JOIN challenges c ON c.id=a.challenge_id
    LEFT JOIN assessments s ON s.id=(
        SELECT MAX(ss.id) FROM assessments ss WHERE ss.attempt_id=a.id
    )
    WHERE a.stage='first' ORDER BY a.id
    """)]
    count_all=con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]
    counted=[r for r in rows if r["independent"]==1 and (not r["solution_revealed"] or r["protected_pass"]) and r["correct"] is not None]
    success=sum(int(r["correct"]) for r in counted)
    results={
      "total_challenges":count_all,
      "first_attempts_recorded":len(rows),
      "independent_first_attempts_recorded":sum(r["independent"]==1 and (not r["solution_revealed"] or r["protected_pass"]) for r in rows),
      "revealed_challenges_excluded":sum(bool(r["solution_revealed"] and not r["protected_pass"]) for r in rows),
      "passed_before_reveal_preserved":sum(bool(r["protected_pass"]) for r in rows),
      "independent_first_attempts_graded":len(counted),
      "independent_first_attempts_correct":success,
      "independent_success_rate":round(success/len(counted),4) if counted else None,
      "assisted_revisions_recorded":con.execute(
        "SELECT COUNT(*) FROM attempts WHERE stage IN ('revision','followup')"
      ).fetchone()[0],
      "historical_summary_only_attempts":sum(r["provenance"]=="summary_only" for r in rows),
      "difficulty_breakdown":{},
      "time_statistics":{},
      "calibration":{},
      "limitations":[]
    }
    by_level=defaultdict(list)
    for r in counted:
        by_level[str(r["difficulty"]) if r["difficulty"] is not None else "unknown"].append(r)
    for level,subset in sorted(by_level.items()):
        results["difficulty_breakdown"][level]={
          "n_graded":len(subset),
          "n_correct":sum(int(r["correct"]) for r in subset),
          "success_rate":round(sum(int(r["correct"]) for r in subset)/len(subset),4),
        }
    timed=[r["minutes_to_first_solution"] for r in rows
            if r["independent"]==1 and (not r["solution_revealed"] or r["protected_pass"]) and r["minutes_to_first_solution"] is not None]
    if timed:
        results["time_statistics"]={
            "n":len(timed),"median_minutes":round(statistics.median(timed),2),
            "mean_minutes":round(statistics.mean(timed),2),
            "self_reported_n":sum(r["independent"]==1 and (not r["solution_revealed"] or r["protected_pass"]) and r["time_source"]=="self-reported"
                                  for r in rows),
            "instrumented_n":sum(r["independent"]==1 and (not r["solution_revealed"] or r["protected_pass"]) and r["time_source"]=="instrumented"
                                 for r in rows),
        }
    scored=[r for r in counted if r["confidence_percent"] is not None]
    if len(scored)>=5:
        brier=statistics.mean((r["confidence_percent"]/100-r["correct"])**2 for r in scored)
        results["calibration"]={"n":len(scored),"brier_score":round(brier,4),
                                "note":"Lower is better; interpret across matched task distributions."}
    else:
        results["calibration"]={"n":len(scored),"brier_score":None,
                                "note":"At least 5 scored independent attempts required even to display a preliminary metric."}
    results["limitations"].append(
        "Difficulty and topic are not automatically calibrated, so trend comparisons require matched problems.")
    if any(r["provenance"]=="summary_only" for r in rows):
        results["limitations"].append(
            "Some historical submissions survive only as summaries, not verbatim solutions.")
    results["limitations"].append(
        "Revealing a PPC prevents new independent scores. Earlier independently graded passing first attempts are preserved when certified before reveal; other revealed attempts are excluded.")
    results["limitations"].append(
        "Record counts and rates are descriptive, not psychometric or causal evidence.")
    return results


def main():
    p=argparse.ArgumentParser(description="ARDS evidence-based progress statistics")
    p.add_argument("--db",type=Path,default=memory.DEFAULT_DB)
    args=p.parse_args()
    with memory.connect(args.db) as con:
        print(json.dumps(summarise(con),indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
