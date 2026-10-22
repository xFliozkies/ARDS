#!/usr/bin/env python3
"""Strict, transactional Codex teacher-PPC import for authentic ARDS challenges.

A batch record must bind its author PPC to the exact statement hash of a
published canonical challenge. No claim of algorithm verification is made.
No RACG draw, challenge status, attempt, or assessment is modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import memory
import strict_json

SECTIONS={"problem","procedure","correctness","complexity"}


def statement_digest(text):
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def validate_record(item):
    if not isinstance(item,dict) or set(item)!={"challenge_id","statement_sha256","teacher_ppc"}:
        raise ValueError("Every record requires only challenge_id, statement_sha256, teacher_ppc")
    ident,hashed,ppc=(item[k] for k in ("challenge_id","statement_sha256","teacher_ppc"))
    if not isinstance(ident,str) or not ident.startswith("RACG-") or len(ident)>40:
        raise ValueError("Invalid Classic RACG challenge identifier")
    if not isinstance(hashed,str) or len(hashed)!=64 or not all(c in "0123456789abcdef" for c in hashed):
        raise ValueError(f"Invalid statement_sha256 for {ident}")
    if not isinstance(ppc,dict) or set(ppc)!=SECTIONS or any(
        not isinstance(ppc[k],str) or not ppc[k].strip() or len(ppc[k])>25000 for k in SECTIONS
    ):
        raise ValueError(f"Complete four-section teacher PPC required for {ident}")
    return item


def load_jsonl(path):
    size=path.stat().st_size
    if size<=0 or size>12_000_000:
        raise ValueError("Batch file empty or exceeds 12 MB")
    rows=[]
    seen=set()
    for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():
            continue
        entry=validate_record(strict_json.loads(line))
        if entry["challenge_id"] in seen:
            raise ValueError(f"Duplicate ID at line {n}: {entry['challenge_id']}")
        seen.add(entry["challenge_id"])
        rows.append(entry)
        if len(rows)>1000:
            raise ValueError("Batch exceeds 1,000 records")
    if not rows:
        raise ValueError("No teacher PPCs in file")
    return rows


def import_batch(db,path,apply=False,expected=None):
    items=load_jsonl(Path(path))
    if expected is not None and len(items)!=expected:
        raise ValueError(f"Expected {expected} PPCs, found {len(items)}")
    output={"batch_items":len(items),"validated":0,"already_present":0,
            "new_references":0,"mode":"apply" if apply else "check_only",
            "source_file":str(path)}
    with memory.connect(db) as con:
        # Transaction checks the whole corpus before any reference is written.
        con.execute("BEGIN IMMEDIATE")
        try:
            prepared=[]
            for item in items:
                ch=memory.get_challenge(con,item["challenge_id"])
                if not ch["statement"] or ch["status"] in ("selected","abandoned"):
                    raise ValueError("Unpublished challenge: "+item["challenge_id"])
                edition=con.execute(
                    "SELECT statement,statement_sha256 FROM classic_authoring_editions WHERE challenge_id=? ORDER BY edition DESC LIMIT 1",
                    (ch["id"],)
                ).fetchone()
                # Codex's authored editions hash exact source bytes, whereas
                # legacy challenge hashes normalize leading/trailing space.
                actual=(hashlib.sha256(edition["statement"].encode("utf-8")).hexdigest()
                        if edition else statement_digest(ch["statement"]))
                if edition and actual!=edition["statement_sha256"]:
                    raise ValueError("Corrupt authored edition hash: "+item["challenge_id"])
                if actual!=item["statement_sha256"]:
                    raise ValueError("Statement hash mismatch: "+item["challenge_id"])
                if not edition and ch["statement_hash"] and ch["statement_hash"]!=actual:
                    raise ValueError("Canonical statement hash inconsistent: "+item["challenge_id"])
                payload=strict_json.canonical(item["teacher_ppc"])
                prior=con.execute("SELECT ppc_json,statement_sha256 FROM teacher_references WHERE challenge_id=?",
                                  (ch["id"],)).fetchone()
                if prior:
                    if prior["ppc_json"]!=payload or prior["statement_sha256"]!=actual:
                        raise ValueError("Immutable teacher PPC conflicts with prior reference: "+item["challenge_id"])
                    output["already_present"]+=1
                else:
                    prepared.append((ch["id"],actual,payload))
                output["validated"]+=1
            if apply:
                for challenge_id,hashed,payload in prepared:
                    con.execute(
                        "INSERT INTO teacher_references(challenge_id,statement_sha256,ppc_json,provenance,assurance,created_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (challenge_id,hashed,payload,"codex_batch_import","authored_unverified",memory.now())
                    )
                output["new_references"]=len(prepared)
                con.commit()
            else:
                output["new_references"]=len(prepared)
                con.rollback()
        except Exception:
            con.rollback()
            raise
    return output


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Safely attach Codex teacher PPCs to canonical Classic RACG challenges")
    parser.add_argument("jsonl",type=Path)
    parser.add_argument("--db",type=Path,default=memory.DEFAULT_DB)
    parser.add_argument("--expected",type=int,default=None)
    parser.add_argument("--apply",action="store_true",help="Commit after complete validation; otherwise dry run")
    args=parser.parse_args()
    try:
        print(json.dumps(import_batch(args.db,args.jsonl,args.apply,args.expected),indent=2))
    except (ValueError,OSError,KeyError) as exc:
        parser.error(str(exc))
