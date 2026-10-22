#!/usr/bin/env python3
"""Record reference-PPC exposure outside the website (e.g., an AI chat).

Recording is one-way. An independently graded passing first attempt prior
to exposure retains credit; no later attempt may earn independent credit.
Historical submissions and assessments are never deleted.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import memory


def mark(db, external_id, provenance="chat"):
    with memory.connect(db) as con:
        challenge=memory.get_challenge(con,external_id)
        if not challenge["statement"] or challenge["status"] in ("selected","abandoned"):
            raise ValueError("Reference exposure must refer to a presented challenge.")
        with con:
            first=con.execute("""
                SELECT a.id FROM attempts a
                JOIN assessments s ON s.id=(SELECT MAX(x.id) FROM assessments x WHERE x.attempt_id=a.id)
                WHERE a.challenge_id=? AND a.stage='first' AND a.independent=1
                      AND a.hint_level=0 AND s.correct=1
                LIMIT 1
            """,(challenge["id"],)).fetchone()
            con.execute(
                "INSERT OR IGNORE INTO solution_reveals(challenge_id,revealed_at,provenance,notes,preserved_attempt_id) VALUES (?,?,?,?,?)",
                (challenge["id"],memory.now(),provenance,
                 "Teacher reference PPC was exposed outside the ARDS website.",
                 first["id"] if first else None)
            )
        row=con.execute("SELECT revealed_at,provenance FROM solution_reveals WHERE challenge_id=?",
                        (challenge["id"],)).fetchone()
        return {"challenge_id":external_id,"reference_revealed":True,
                "assessment_eligible":False,"revealed_at":row["revealed_at"],
                "provenance":row["provenance"]}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["mark"])
    parser.add_argument("challenge_id")
    parser.add_argument("--provenance",choices=["chat","website","manual","other"],default="chat")
    parser.add_argument("--db",type=Path,default=memory.DEFAULT_DB)
    args=parser.parse_args()
    print(json.dumps(mark(args.db,args.challenge_id,args.provenance),indent=2))
