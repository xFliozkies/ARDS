#!/usr/bin/env python3
"""Persistent Classic RACG batch queue.

A queue reserves authentic, recorded random selections and Z reasoning plans.
It does NOT invent statements or certify proofs. Each item may be authored and
verified independently; unsupported families stay under review, not published.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
from pathlib import Path

import ards2
import memory
import racg


def _previous(row):
    return {
        "topic_id": row["topic_id"],
        "topic_label": row["topic_label"],
        "difficulty": row["difficulty"],
    } if row else None


def _plan(con, challenge_id: int, topic_label: str, randbelow):
    catalog = ards2.patterns()
    domain = ards2.topic_domain(topic_label)
    eligible = sorted(x["id"] for x in catalog["patterns"]
                      if domain in x["tags"] or "general" in x["tags"])
    if not eligible:
        raise ValueError("No valid reasoning patterns for " + topic_label)
    z = randbelow(len(eligible))
    if type(z) is not int or not 0 <= z < len(eligible):
        raise ValueError("Invalid Z reasoning roll")
    con.execute(
        "INSERT INTO reasoning_plans"
        "(challenge_id,z,eligible_json,primary_pattern,catalog_version,created_at)"
        " VALUES (?,?,?,?,?,?)",
        (challenge_id, z, ards2.canonical(eligible), eligible[z],
         catalog["version"], memory.now())
    )
    return {"Z": z, "primary_pattern": eligible[z]}


def _validate_selection(selected, previous):
    rolls = selected["rolls"]
    o, x, y, p = (rolls[k] for k in ("O", "X", "Y", "P"))
    if (type(o) is not int or type(y) is not int or type(p) is not int
        or not 1 <= o <= 100 or not 1 <= p <= 100):
        raise ValueError("Invalid Classic RACG rolls")
    expected_continue = bool(o <= 15 and previous is not None)
    if type(selected["continuation"]) is not bool or selected["continuation"] != expected_continue:
        raise ValueError("Invalid continuation decision")
    if expected_continue:
        if x is not None or selected["topic_id"] != previous["topic_id"]:
            raise ValueError("Continuation may not change topic or draw X")
        expected_topic = previous["topic_label"]
    else:
        if type(x) is not int or not 0 <= x < 100000:
            raise ValueError("Fresh topic requires an authentic X roll")
        if selected["topic_id"] != 1 + x % 100:
            raise ValueError("Topic does not match X")
        expected_topic = racg.catalog()[selected["topic_id"]]
    if selected["topic_label"] != expected_topic:
        raise ValueError("Topic label changed from recorded selection")
    min_level = previous["difficulty"] if expected_continue else 1
    level = racg.difficulty_from_roll(y, min_level)
    if selected["difficulty"] != level or selected["presentation"] != ("story" if p <= 70 else "direct"):
        raise ValueError("Level or presentation does not match its random roll")


def _insert_selection(con, selected, randbelow):
    last_number = con.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(external_id,6) AS INTEGER)),0) "
        "FROM challenges WHERE external_id GLOB 'RACG-[0-9]*'"
    ).fetchone()[0]
    external_id = f"RACG-{last_number + 1:04d}"
    stamp = memory.now()
    rolls = selected["rolls"]
    cursor = con.execute("""
      INSERT INTO challenges(
        external_id,session_type,status,source,topic_id,topic_label,difficulty,
        presentation,continuation,roll_o,roll_x,roll_y,roll_p,
        selected_at,created_at,notes
      ) VALUES (?,?,?,'native',?,?,?,?,?,?,?,?,?,?,?,?)
    """, (external_id, "RACG", "selected",
          selected["topic_id"], selected["topic_label"], selected["difficulty"],
          selected["presentation"], int(selected["continuation"]),
          rolls["O"], rolls["X"], rolls["Y"], rolls["P"],
          stamp, stamp,
          "Batch Classic RACG selection awaiting private PPC and verification."))
    _plan(con, cursor.lastrowid, selected["topic_label"], randbelow)
    return cursor.lastrowid, external_id


def create_batch(con, count=100, randbelow=None, provenance="classic-racg-batch", parallel=False):
    """Atomically reserve count authentic selections; adopt one unbatched pending draw.

    Exactly one existing unbatched pending selection is adopted as ordinal 1
    instead of rerolling it. Selections are not public challenges until released.
    """
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("count must be between 1 and 1000")
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("provenance is required")
    rng = randbelow or secrets.randbelow
    con.execute("BEGIN IMMEDIATE")
    try:
        open_batches = con.execute("""
          SELECT b.id FROM authoring_batches b
          JOIN authoring_batch_items i ON i.batch_id=b.id
          WHERE i.stage NOT IN ('released','rejected') LIMIT 1
        """).fetchone()
        if open_batches and not parallel:
            raise ValueError("Open batch exists (ID " + str(open_batches["id"]) +
                             "); resume it with 'status' or 'next' rather than rerolling")
        dangling = con.execute("""
          SELECT c.* FROM challenges c
          LEFT JOIN authoring_batch_items i ON i.challenge_id=c.id
          WHERE c.session_type='RACG' AND c.status='selected' AND i.id IS NULL
          ORDER BY c.id
        """).fetchall()
        if len(dangling) > 1:
            raise ValueError("Multiple unbatched pending selections; reconcile them before batching")
        if parallel and dangling:
            raise ValueError("Parallel batch cannot adopt or bypass an unbatched pending draw")
        adopted = dangling[0] if dangling else None
        previous = _previous(adopted)
        if previous is None:
            if parallel:
                # Explicit extension of the reserved stream, not the last released item.
                prior=con.execute("SELECT * FROM challenges WHERE session_type='RACG' ORDER BY id DESC LIMIT 1").fetchone()
                previous=_previous(prior)
            else:
                previous=memory.latest_racg(con)
        cursor = con.execute(
            "INSERT INTO authoring_batches(requested_count,created_at,provenance,notes) VALUES (?,?,?,?)",
            (count, memory.now(), provenance,
             "All O/X/Y/P are saved on challenges; each Z is saved in reasoning_plans.")
        )
        batch_id = cursor.lastrowid
        result = []
        if adopted:
            plan_row = con.execute(
                "SELECT 1 FROM reasoning_plans WHERE challenge_id=?", (adopted["id"],)
            ).fetchone()
            if not plan_row:
                _plan(con, adopted["id"], adopted["topic_label"], rng)
            con.execute(
                "INSERT INTO authoring_batch_items(batch_id,ordinal,challenge_id,stage,updated_at) "
                "VALUES (?,?,?,'drawn',?)",
                (batch_id, 1, adopted["id"], memory.now())
            )
            result.append(adopted["external_id"])
        for ordinal in range(len(result) + 1, count + 1):
            chosen = racg.draw(previous, randbelow=rng)
            _validate_selection(chosen, previous)
            row_id, external_id = _insert_selection(con, chosen, rng)
            con.execute(
                "INSERT INTO authoring_batch_items(batch_id,ordinal,challenge_id,stage,updated_at) "
                "VALUES (?,?,?,'drawn',?)",
                (batch_id, ordinal, row_id, memory.now())
            )
            result.append(external_id)
            previous = _previous(chosen)
        con.commit()
    except Exception:
        con.rollback()
        raise
    return {
        "batch_id": batch_id, "requested": count, "reserved": len(result),
        "adopted_existing": adopted["external_id"] if adopted else None,
        "first_id": result[0], "last_id": result[-1],
        "generated_statements": 0,
        "verification_scope": "Authentic selections only; no solutions, oracle tests or releases claimed.",
    }


def _batch_id(con, requested):
    if requested is not None:
        row = con.execute("SELECT id FROM authoring_batches WHERE id=?", (requested,)).fetchone()
        if not row:
            raise ValueError("Unknown batch " + str(requested))
        return row["id"]
    # Keep Codex's oldest unfinished queue as the default when the learner
    # explicitly requests a separate parallel batch. New work uses --batch ID.
    row = con.execute("""
        SELECT b.id FROM authoring_batches b
        WHERE EXISTS(
            SELECT 1 FROM authoring_batch_items i
            LEFT JOIN releases r ON r.challenge_id=i.challenge_id
            WHERE i.batch_id=b.id AND i.stage NOT IN ('released','rejected')
                  AND r.id IS NULL
        ) ORDER BY b.id ASC LIMIT 1
    """).fetchone()
    if row is None:
        row=con.execute("SELECT id FROM authoring_batches ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        raise ValueError("No authoring batch. Run 'create --count 100'.")
    return row["id"]


def derived_stage(con, item):
    if item["stage"] == "rejected":
        return "rejected"
    if item["released_id"] is not None:
        return "released"
    if item["body_hash"] is None:
        return "under_review" if item["stage"] == "under_review" else "drawn"
    if item["verification_outcome"] == "test_verified" and item["verified_hash"] == item["body_hash"]:
        # A first-party test pass is NOT independent reviewer approval.
        # Check the actual hash-bound review and its on-disk evidence.
        from ards_review import approved_evidence
        verified=con.execute("SELECT * FROM verification_runs WHERE id=?",
                             (item["verification_id"],)).fetchone()
        challenge=ards2.get_challenge(con,item["external_id"])
        if verified and approved_evidence(con,challenge,item["body_hash"],verified):
            return "verified"
        return "under_review"
    if item["verification_outcome"] in ("experimental", "failed"):
        return "under_review"
    return "under_review" if item["stage"] == "under_review" else "drafted"


def items(con, batch_id):
    sql = """
      SELECT i.id,i.batch_id,i.ordinal,i.stage,i.review_note,i.challenge_id,
             c.external_id,c.topic_id,c.topic_label,c.difficulty,c.presentation,
             c.roll_o,c.roll_x,c.roll_y,c.roll_p,c.continuation,c.status AS challenge_status,
             rp.z,rp.primary_pattern,COALESCE(pr.body_hash,p.body_hash) AS body_hash,
             v.id AS verification_id,v.outcome AS verification_outcome,v.package_hash AS verified_hash,
             r.id AS released_id
      FROM authoring_batch_items i
      JOIN challenges c ON c.id=i.challenge_id
      LEFT JOIN reasoning_plans rp ON rp.challenge_id=c.id
      LEFT JOIN problem_packages p ON p.challenge_id=c.id
      LEFT JOIN authoring_package_revisions pr ON pr.id=(
          SELECT MAX(pr2.id) FROM authoring_package_revisions pr2 WHERE pr2.challenge_id=c.id)
      LEFT JOIN verification_runs v ON v.id=(
         SELECT MAX(v2.id) FROM verification_runs v2 WHERE v2.challenge_id=c.id
      )
      LEFT JOIN releases r ON r.challenge_id=c.id
      WHERE i.batch_id=? ORDER BY i.ordinal
    """
    rows = [dict(x) for x in con.execute(sql, (batch_id,))]
    for row in rows:
        row["effective_stage"] = derived_stage(con, row)
    return rows


def status(con, batch_id=None, full=False):
    if batch_id is None and not con.execute("SELECT 1 FROM authoring_batches LIMIT 1").fetchone():
        if full:
            return {"batch_id":None,"total":0,"items":[]}
        return {"batch_id":None,"total":0,"by_stage":{key:0 for key in
                ("drawn","drafted","under_review","verified","released","rejected")},
                "next_to_author":None,"next_to_review":None,"all_released":False}
    bid = _batch_id(con, batch_id)
    rows = items(con, bid)
    if full:
        return {"batch_id": bid, "total": len(rows), "items": rows}
    summary = {stage: sum(x["effective_stage"] == stage for x in rows)
               for stage in ("drawn", "drafted", "under_review", "verified", "released", "rejected")}
    return {"batch_id": bid, "total": len(rows), "by_stage": summary,
            "next_to_author": next((x["external_id"] for x in rows if x["effective_stage"] == "drawn"), None),
            "next_to_review": next((x["external_id"] for x in rows if x["effective_stage"] == "under_review"), None),
            "all_released": summary["released"] == len(rows)}


def next_item(con, batch_id=None, stage="drawn"):
    if batch_id is None and not con.execute("SELECT 1 FROM authoring_batches LIMIT 1").fetchone():
        return {"batch_id":None,"stage":stage,"next":None}
    bid = _batch_id(con, batch_id)
    options = [x for x in items(con, bid) if x["effective_stage"] == stage]
    if not options:
        return {"batch_id": bid, "stage": stage, "next": None}
    row = options[0]
    return {"batch_id": bid, "stage": stage, "next": row}


def mark_review(con, external_id, reason, rejected=False):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Review reason must be nonempty")
    row = con.execute("""
      SELECT i.*,c.external_id FROM authoring_batch_items i
      JOIN challenges c ON c.id=i.challenge_id WHERE c.external_id=?
    """, (external_id,)).fetchone()
    if not row:
        raise ValueError("Challenge is not part of an authoring batch")
    if row["stage"] == "released":
        raise ValueError("Cannot change released item")
    if row["stage"] == "rejected" and not rejected:
        raise ValueError("Rejected item requires explicit 'reopen'")
    if con.execute("SELECT 1 FROM releases WHERE challenge_id=?", (row["challenge_id"],)).fetchone():
        raise ValueError("Cannot change released item")
    with con:
        con.execute(
            "UPDATE authoring_batch_items SET stage=?,review_note=?,updated_at=? WHERE id=?",
            ("rejected" if rejected else "under_review",
             reason.strip(), memory.now(), row["id"])
        )
    return {"challenge": external_id, "stage": "rejected" if rejected else "under_review",
            "reason": reason.strip()}


def reopen(con, external_id, reason):
    if not isinstance(reason,str) or not reason.strip():
        raise ValueError("Reopening requires justification")
    row = con.execute("""
      SELECT i.*,p.id AS pkg_id FROM authoring_batch_items i
      JOIN challenges c ON c.id=i.challenge_id
      LEFT JOIN problem_packages p ON p.challenge_id=c.id WHERE c.external_id=?
    """,(external_id,)).fetchone()
    if not row or row["stage"] != "rejected":
        raise ValueError("Only a rejected, queued item can be reopened")
    target = "drafted" if row["pkg_id"] else "drawn"
    with con:
        con.execute("UPDATE authoring_batch_items SET stage=?,review_note=?,updated_at=? WHERE id=?",
                    (target, reason.strip(), memory.now(), row["id"]))
    return {"challenge": external_id, "stage": target, "reason": reason.strip()}


def sync(con, batch_id=None):
    bid = _batch_id(con, batch_id)
    current = items(con, bid)
    with con:
        for row in current:
            if row["stage"] != row["effective_stage"]:
                con.execute("UPDATE authoring_batch_items SET stage=?,updated_at=? WHERE id=?",
                            (row["effective_stage"], memory.now(), row["id"]))
    return status(con, bid)


def main():
    parser = argparse.ArgumentParser(description="Persistent Classic RACG batch authoring queue")
    parser.add_argument("--db",type=Path,default=memory.DEFAULT_DB)
    sub = parser.add_subparsers(dest="action",required=True)
    create = sub.add_parser("create",help="Reserve a batch of authentic Classic RACG draws and Z plans")
    create.add_argument("--count",type=int,default=100)
    create.add_argument("--parallel",action="store_true",help="Explicitly reserve a new independent batch while older authoring continues")
    for name in ("status","next","sync"):
        p = sub.add_parser(name)
        p.add_argument("--batch",type=int)
        if name == "status":p.add_argument("--full",action="store_true")
        if name == "next":p.add_argument("--stage",choices=("drawn","drafted","under_review","verified"),default="drawn")
    for name in ("review","reject","reopen"):
        p = sub.add_parser(name)
        p.add_argument("challenge")
        p.add_argument("--reason",required=True)
    args = parser.parse_args()
    try:
        with memory.connect(args.db) as con:
            if args.action == "create": result = create_batch(con,args.count,
                    provenance="classic-racg-additional-batch" if args.parallel else "classic-racg-batch",
                    parallel=args.parallel)
            elif args.action == "status": result = status(con,args.batch,args.full)
            elif args.action == "next": result = next_item(con,args.batch,args.stage)
            elif args.action == "sync": result = sync(con,args.batch)
            elif args.action == "review": result = mark_review(con,args.challenge,args.reason)
            elif args.action == "reject": result = mark_review(con,args.challenge,args.reason,True)
            else: result = reopen(con,args.challenge,args.reason)
    except (ValueError,sqlite3.Error,OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
