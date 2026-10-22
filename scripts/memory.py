#!/usr/bin/env python3
"""ARDS durable memory: SQLite records, full-text search, assessments, and audit.

Python standard library only. Original independent attempts and assessments are
append-only; missing historical evidence remains explicitly missing.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_DB = BASE / "data" / "ards.db"
DIMENSIONS = (
    "modeling", "discovery", "correctness_reasoning", "edge_cases",
    "complexity", "optimization", "transfer", "calibration",
)
STAGES = ("first", "revision", "followup")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def as_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def output(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def connect(path=DEFAULT_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    con.execute("PRAGMA journal_mode = WAL")
    schema(con)
    return con


def schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_id TEXT NOT NULL UNIQUE,
        session_type TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN
            ('selected','presented','attempted','evaluated','abandoned')),
        source TEXT NOT NULL DEFAULT 'native',
        topic_id INTEGER CHECK(topic_id IS NULL OR topic_id BETWEEN 1 AND 100),
        topic_label TEXT,
        difficulty INTEGER CHECK(difficulty IS NULL OR difficulty BETWEEN 1 AND 6),
        title TEXT,
        statement TEXT,
        statement_hash TEXT,
        constraints_json TEXT,
        presentation TEXT CHECK(presentation IS NULL OR presentation IN ('story','direct')),
        continuation INTEGER CHECK(continuation IS NULL OR continuation IN (0,1)),
        roll_o INTEGER CHECK(roll_o IS NULL OR roll_o BETWEEN 1 AND 100),
        roll_x INTEGER CHECK(roll_x IS NULL OR roll_x >= 0),
        roll_y INTEGER CHECK(roll_y IS NULL OR roll_y >= 0),
        roll_p INTEGER CHECK(roll_p IS NULL OR roll_p BETWEEN 1 AND 100),
        selected_at TEXT,
        presented_at TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_challenges_session_status ON challenges(session_type, status);
    CREATE INDEX IF NOT EXISTS idx_challenges_topic_difficulty ON challenges(topic_label, difficulty);

    CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_id INTEGER NOT NULL REFERENCES challenges(id),
        stage TEXT NOT NULL CHECK(stage IN ('first','revision','followup')),
        submission TEXT NOT NULL CHECK(length(trim(submission))>0),
        provenance TEXT NOT NULL CHECK(provenance IN ('verbatim','summary_only')),
        independent INTEGER NOT NULL CHECK(independent IN (0,1)),
        hint_level INTEGER CHECK(hint_level IS NULL OR hint_level BETWEEN 0 AND 4),
        minutes_to_first_solution REAL CHECK(minutes_to_first_solution IS NULL OR minutes_to_first_solution >= 0),
        time_source TEXT CHECK(time_source IS NULL OR time_source IN ('self-reported','instrumented')),
        confidence_percent INTEGER CHECK(confidence_percent IS NULL OR confidence_percent BETWEEN 0 AND 100),
        submitted_at TEXT NOT NULL,
        notes TEXT,
        CHECK (minutes_to_first_solution IS NULL OR time_source IS NOT NULL),
        CHECK (stage != 'first' OR independent = 0 OR hint_level = 0)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_one_first_attempt
        ON attempts(challenge_id) WHERE stage = 'first';
    CREATE INDEX IF NOT EXISTS idx_attempts_challenge ON attempts(challenge_id);

    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL REFERENCES attempts(id),
        assessed_at TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        rubric_version TEXT NOT NULL DEFAULT 'ARDS-eight-dimension-v1',
        correct INTEGER CHECK(correct IS NULL OR correct IN (0,1)),
        optimality_verified INTEGER CHECK(optimality_verified IS NULL OR optimality_verified IN (0,1)),
        time_complexity TEXT,
        space_complexity TEXT,
        modeling INTEGER CHECK(modeling IS NULL OR modeling BETWEEN 0 AND 4),
        discovery INTEGER CHECK(discovery IS NULL OR discovery BETWEEN 0 AND 4),
        correctness_reasoning INTEGER CHECK(correctness_reasoning IS NULL OR correctness_reasoning BETWEEN 0 AND 4),
        edge_cases INTEGER CHECK(edge_cases IS NULL OR edge_cases BETWEEN 0 AND 4),
        complexity INTEGER CHECK(complexity IS NULL OR complexity BETWEEN 0 AND 4),
        optimization INTEGER CHECK(optimization IS NULL OR optimization BETWEEN 0 AND 4),
        transfer INTEGER CHECK(transfer IS NULL OR transfer BETWEEN 0 AND 4),
        calibration INTEGER CHECK(calibration IS NULL OR calibration BETWEEN 0 AND 4),
        legacy_score TEXT,
        evidence TEXT,
        notes TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_assessments_attempt ON assessments(attempt_id, id);

    -- Permanent, non-secret learner exposure record. An answer revealed at
    -- ANY point disqualifies the entire challenge from independent metrics.
    CREATE TABLE IF NOT EXISTS solution_reveals (
        challenge_id INTEGER PRIMARY KEY REFERENCES challenges(id),
        revealed_at TEXT NOT NULL,
        provenance TEXT NOT NULL DEFAULT 'ards-studio',
        notes TEXT
    );
    CREATE TRIGGER IF NOT EXISTS no_update_solution_reveals BEFORE UPDATE ON solution_reveals
      BEGIN SELECT RAISE(ABORT,'solution reveals are permanent'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_solution_reveals BEFORE DELETE ON solution_reveals
      BEGIN SELECT RAISE(ABORT,'solution reveals are permanent'); END;

    -- Importable teacher references can be attached to authentic Classic RACG
    -- challenge records without claiming ARDS reference verification succeeded.
    -- Hash-binding rejects solutions for a different statement revision.
    -- Legacy authored-edition records are optional, but the website queries
    -- their schema on every new installation. Keep it available even at zero.
    CREATE TABLE IF NOT EXISTS classic_authoring_editions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_id INTEGER NOT NULL REFERENCES challenges(id),
        edition INTEGER NOT NULL CHECK(edition >= 2),
        original_statement_sha256 TEXT NOT NULL,
        statement_sha256 TEXT NOT NULL,
        statement TEXT NOT NULL,
        package_json TEXT NOT NULL,
        assurance TEXT NOT NULL CHECK(assurance='authored_unverified'),
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(challenge_id,edition)
    );
    CREATE TRIGGER IF NOT EXISTS no_update_classic_edition BEFORE UPDATE ON classic_authoring_editions
      BEGIN SELECT RAISE(ABORT,'Classic authored editions are immutable'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_classic_edition BEFORE DELETE ON classic_authoring_editions
      BEGIN SELECT RAISE(ABORT,'Classic authored editions are immutable'); END;

    CREATE TABLE IF NOT EXISTS teacher_references (
        challenge_id INTEGER PRIMARY KEY REFERENCES challenges(id),
        statement_sha256 TEXT NOT NULL,
        ppc_json TEXT NOT NULL,
        provenance TEXT NOT NULL,
        assurance TEXT NOT NULL DEFAULT 'authored_unverified',
        created_at TEXT NOT NULL
    );
    CREATE TRIGGER IF NOT EXISTS no_update_teacher_references BEFORE UPDATE ON teacher_references
      BEGIN SELECT RAISE(ABORT,'teacher references are immutable; publish a reviewed revision'); END;
    CREATE TRIGGER IF NOT EXISTS no_delete_teacher_references BEFORE DELETE ON teacher_references
      BEGIN SELECT RAISE(ABORT,'teacher references are immutable'); END;

    CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_id INTEGER NOT NULL REFERENCES challenges(id),
        attempt_id INTEGER REFERENCES attempts(id),
        kind TEXT NOT NULL CHECK(kind IN ('strength','weakness','insight','uncertain')),
        concept TEXT NOT NULL,
        evidence TEXT NOT NULL,
        observed_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_observations_concept ON observations(concept);
    CREATE VIRTUAL TABLE IF NOT EXISTS challenge_fts USING fts5(
        title, statement, topic_label,
        content='challenges', content_rowid='id', tokenize='unicode61'
    );
    CREATE TRIGGER IF NOT EXISTS challenge_fts_insert AFTER INSERT ON challenges BEGIN
        INSERT INTO challenge_fts(rowid,title,statement,topic_label)
        VALUES(new.id,new.title,new.statement,new.topic_label);
    END;
    CREATE TRIGGER IF NOT EXISTS challenge_fts_delete AFTER DELETE ON challenges BEGIN
        INSERT INTO challenge_fts(challenge_fts,rowid,title,statement,topic_label)
        VALUES('delete',old.id,old.title,old.statement,old.topic_label);
    END;
    CREATE TRIGGER IF NOT EXISTS challenge_fts_update AFTER UPDATE ON challenges BEGIN
        INSERT INTO challenge_fts(challenge_fts,rowid,title,statement,topic_label)
        VALUES('delete',old.id,old.title,old.statement,old.topic_label);
        INSERT INTO challenge_fts(rowid,title,statement,topic_label)
        VALUES(new.id,new.title,new.statement,new.topic_label);
    END;
    """)
    with con:
        con.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES ('schema_version','1')")
    # Older archives already have solution_reveals. Add a protected first-attempt
    # pointer without changing any historical exposure events.
    columns={col[1] for col in con.execute("PRAGMA table_info(solution_reveals)")}
    if "preserved_attempt_id" not in columns:
        con.execute("ALTER TABLE solution_reveals ADD COLUMN preserved_attempt_id INTEGER REFERENCES attempts(id)")
    # ARDS 2.0 is an additive, idempotent schema migration; historical data stays intact.
    from ards2 import ensure_schema
    ensure_schema(con)


def get_challenge(con, external_id):
    row = con.execute("SELECT * FROM challenges WHERE external_id=?", (external_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown challenge: " + external_id)
    return dict(row)


def latest_racg(con):
    # Continuations extend an actually presented challenge, not an abandoned
    # selection that never became an authored problem.
    row = con.execute("""
        SELECT * FROM challenges
        WHERE session_type='RACG' AND status IN ('presented','attempted','evaluated')
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    if row is None:
        return None
    r = dict(row)
    return {
        "topic_id": r["topic_id"], "topic_label": r["topic_label"],
        "difficulty": r["difficulty"], "external_id": r["external_id"],
    }


def record_random_selection(con, sampler):
    """Atomic, unique RACG draw. Refuse concurrent/pending unpresented selection."""
    with con:
        con.execute("BEGIN IMMEDIATE")
        pending = con.execute(
            "SELECT external_id FROM challenges WHERE session_type='RACG' AND status='selected' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if pending:
            raise ValueError("Unpresented RACG selection " + pending["external_id"] +
                             " exists. Present it or explicitly abandon it first.")
        previous = latest_racg(con)
        selected = sampler(previous)
        o, x, y, p = (selected["rolls"][k] for k in ("O", "X", "Y", "P"))
        if (type(o) is not int or type(y) is not int or type(p) is not int
                or not 1 <= o <= 100 or not 1 <= p <= 100):
            raise ValueError("Invalid O/Y/P rolls")
        if selected["continuation"]:
            if previous is None or x is not None:
                raise ValueError("Invalid continuation X/prior state")
            if selected["topic_id"] != previous["topic_id"] or selected["difficulty"] < previous["difficulty"]:
                raise ValueError("Continuation cannot change topic or decrease difficulty")
        elif x is None or not (0 <= x < 100000):
            raise ValueError("Fresh topic requires X")
        if x is not None and not selected["continuation"] and selected["topic_id"] != 1 + x % 100:
            raise ValueError("Topic ID not consistent with X")
        if selected["story"] != (p <= 70):
            raise ValueError("Story flag inconsistent with P")
        if selected["continuation"] != (o <= 15 and previous is not None):
            raise ValueError("Continuation branch inconsistent with O and previous challenge")
        import racg
        min_level = previous["difficulty"] if selected["continuation"] else 1
        try:
            expected_level = racg.difficulty_from_roll(y, min_level)
        except ValueError as exc:
            raise ValueError("Invalid O/Y/P rolls: " + str(exc)) from exc
        if selected["difficulty"] != expected_level:
            raise ValueError("Difficulty inconsistent with weighted Y or prior difficulty")
        if selected["difficulty"] not in range(1,7):
            raise ValueError("Difficulty out of range")
        last_num = con.execute(
            "SELECT COALESCE(MAX(CAST(SUBSTR(external_id,6) AS INTEGER)),0) FROM challenges "
            "WHERE external_id GLOB 'RACG-[0-9]*'"
        ).fetchone()[0]
        challenge_id = f"RACG-{last_num+1:04d}"
        stamp = now()
        con.execute("""
            INSERT INTO challenges (
                external_id,session_type,status,topic_id,topic_label,difficulty,
                presentation,continuation,roll_o,roll_x,roll_y,roll_p,
                selected_at,created_at,source,notes
            ) VALUES (?, 'RACG','selected', ?,?,?, ?,?,?,?,?,?, ?,?,'native',?)
        """, (challenge_id, selected["topic_id"], selected["topic_label"],
              selected["difficulty"], selected["presentation"],int(selected["continuation"]),
              o,x,y,p,stamp,stamp,
              "RACG draw: a topic selection, not yet an authored or verified problem."))
        return dict(selected, external_id=challenge_id, status="selected")


def present_challenge(con, challenge_id, title, statement, constraints=None, notes=None):
    if not title.strip() or not statement.strip():
        raise ValueError("Title and full statement are required")
    if constraints is not None and not isinstance(constraints, dict):
        raise ValueError("Constraints must be a JSON object")
    fingerprint=hashlib.sha256(statement.encode("utf8")).hexdigest()
    # Duplicate hints must not override the random topic/difficulty selection.
    # Exact hash matches are reliable; TF-IDF matches are only potential overlap.
    exact=[r["external_id"] for r in con.execute(
        "SELECT external_id FROM challenges WHERE statement_hash=? AND external_id<>?",
        (fingerprint,challenge_id))]
    lexical=near(con,title+" "+statement,limit=5,exclude_id=challenge_id)
    with con:
        challenge = get_challenge(con, challenge_id)
        if challenge["status"] != "selected":
            raise ValueError("Challenge must be 'selected' and not yet presented")
        stamp = now()
        con.execute("""
            UPDATE challenges SET title=?, statement=?, statement_hash=?, constraints_json=?,
              status='presented', presented_at=?, notes=COALESCE(?, notes)
            WHERE external_id=? AND status='selected'
        """, (title.strip(),statement.strip(),fingerprint,
              as_json(constraints or {}),stamp,notes,challenge_id))
    result=get_challenge(con,challenge_id)
    result["duplicate_check"]={"exact_duplicates":exact,
                              "lexical_candidates":lexical,
                              "lexical_search_not_semantic":True,
                              "random_selection_unchanged":True}
    return result


def abandon_selection(con, challenge_id, reason):
    if not reason.strip():
        raise ValueError("Abandonment requires a reason")
    with con:
        row = get_challenge(con, challenge_id)
        if row["status"] != "selected":
            raise ValueError("Only an unpresented selection can be abandoned")
        con.execute("UPDATE challenges SET status='abandoned', notes=? WHERE external_id=?",
                    ("Abandoned selection: "+reason, challenge_id))
    return get_challenge(con, challenge_id)


def add_attempt(con, challenge_id, submission, stage="first", provenance="verbatim",
                hint_level=None, independent=None, minutes=None, time_source=None,
                confidence=None, notes=None, submitted_at=None):
    if stage not in STAGES or provenance not in ("verbatim","summary_only"):
        raise ValueError("Invalid stage or provenance")
    if not submission or not submission.strip():
        raise ValueError("Cannot record an empty attempt")
    if hint_level is not None and (type(hint_level) is not int or not 0 <= hint_level <= 4):
        raise ValueError("Hint level must be 0..4")
    if confidence is not None and (type(confidence) is not int or not 0 <= confidence <= 100):
        raise ValueError("Confidence must be 0..100")
    if minutes is not None and (minutes < 0 or not math.isfinite(minutes)):
        raise ValueError("Minutes must be nonnegative and finite")
    if (minutes is not None and time_source is None) or time_source not in (None,"self-reported","instrumented"):
        raise ValueError("Timed attempts require a valid time source")
    if independent is None:
        # Absence of recorded hints does not, by itself, prove independence.
        independent = False
    if independent and (stage != "first" or hint_level != 0):
        raise ValueError("Independence requires first attempt with 0 hints")
    with con:
        challenge = get_challenge(con, challenge_id)
        if challenge["status"] in ("selected","abandoned"):
            raise ValueError("Cannot attempt unpresented/abandoned challenge")
        if independent and con.execute(
            "SELECT 1 FROM solution_reveals WHERE challenge_id=?", (challenge["id"],)
        ).fetchone():
            raise ValueError("Reference PPC was revealed; this challenge is ineligible for independent assessment")
        prior = con.execute("SELECT COUNT(*) FROM attempts WHERE challenge_id=?", (challenge["id"],)).fetchone()[0]
        if stage == "first" and prior:
            raise ValueError("Original first attempt is immutable; use 'revision' or 'followup'")
        if stage != "first" and not prior:
            raise ValueError("Record the original first attempt before revisions")
        cursor = con.execute("""
            INSERT INTO attempts(challenge_id,stage,submission,provenance,independent,
            hint_level,minutes_to_first_solution,time_source,confidence_percent,submitted_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (challenge["id"],stage,submission,provenance,int(independent),
              hint_level,minutes,time_source,confidence,submitted_at or now(),notes))
        con.execute("UPDATE challenges SET status='attempted' WHERE id=? AND status='presented'", (challenge["id"],))
        return int(cursor.lastrowid)


def add_assessment(con, attempt_id, reviewer, correct=None, optimality=None,
                   time_complexity=None, space_complexity=None, scores=None,
                   evidence=None, notes=None, legacy_score=None):
    if correct not in (None, True, False) or optimality not in (None,True,False):
        raise ValueError("Correct/optimality must be true, false or unknown")
    scores = scores or {}
    if set(scores) - set(DIMENSIONS):
        raise ValueError("Invalid rubric dimensions: " + str(set(scores)-set(DIMENSIONS)))
    for name, value in scores.items():
        if value is not None and (type(value) is not int or not 0 <= value <= 4):
            raise ValueError("Each rubric score must be 0..4 or null")
    if not reviewer or not reviewer.strip():
        raise ValueError("Reviewer is required")
    if (correct is not None or optimality is not None or any(v is not None for v in scores.values())) and not (evidence and evidence.strip()):
        raise ValueError("Any substantive correctness or rubric judgment requires evidence")
    with con:
        row = con.execute("SELECT a.challenge_id FROM attempts a WHERE a.id=?", (attempt_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown attempt ID")
        columns = list(DIMENSIONS)
        sql = ("INSERT INTO assessments(attempt_id,assessed_at,reviewer,correct,optimality_verified,"
               "time_complexity,space_complexity,legacy_score,evidence,notes,"
               + ",".join(columns) + ") VALUES (" + ",".join(["?"] * (10 + len(columns))) + ")")
        fields = (attempt_id,now(),reviewer, None if correct is None else int(correct),
                  None if optimality is None else int(optimality), time_complexity,
                  space_complexity,legacy_score,evidence,notes,
                  *(scores.get(n) for n in columns))
        cursor = con.execute(sql, fields)
        con.execute("UPDATE challenges SET status='evaluated' WHERE id=?", (row["challenge_id"],))
        return int(cursor.lastrowid)


def add_observation(con, challenge_id, kind, concept, evidence, attempt_id=None):
    if kind not in ("strength","weakness","insight","uncertain") or not concept.strip() or not evidence.strip():
        raise ValueError("Observation must have a valid kind, concept and evidence")
    with con:
        challenge=get_challenge(con,challenge_id)
        if attempt_id is not None:
            row=con.execute("SELECT challenge_id FROM attempts WHERE id=?", (attempt_id,)).fetchone()
            if row is None or row["challenge_id"] != challenge["id"]:
                raise ValueError("Attempt ID must belong to this challenge")
        cursor=con.execute("""
          INSERT INTO observations(challenge_id,attempt_id,kind,concept,evidence,observed_at)
          VALUES(?,?,?,?,?,?)
        """,(challenge["id"],attempt_id,kind,concept,evidence,now()))
        return int(cursor.lastrowid)


def search(con, query, limit=10):
    # Quote tokenized words to avoid FTS5 syntax errors/operator injection.
    tokens=re.findall(r"\w+",query,flags=re.UNICODE)[:20]
    if not tokens:
        return []
    phrase=" OR ".join('"'+t.replace('"','""')+'"' for t in tokens)
    rows=con.execute("""
        SELECT c.external_id,c.title,c.topic_label,c.difficulty,c.status,
        snippet(challenge_fts,1,'[',']',' … ',18) AS excerpt,
        bm25(challenge_fts) AS rank
        FROM challenge_fts JOIN challenges c ON c.id=challenge_fts.rowid
        WHERE challenge_fts MATCH ? AND c.statement IS NOT NULL
        ORDER BY rank LIMIT ?
    """,(phrase,limit)).fetchall()
    return [dict(r) for r in rows]


STOP_WORDS=set(("the a an is are of on and or to in for it this that with be by as at from "
                "each given find determine you can array number numbers integer integers "
                "n input output example problem given following must does what how their "
                "one two than all such which any there exists possible your should").split())


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+",text.lower()) if len(w)>1 and w not in STOP_WORDS]


def near(con, text, limit=5, exclude_id=None):
    """Lexical TF-IDF cosine; NOT vector embedding or full semantic equivalence."""
    candidates=con.execute("""
        SELECT external_id,title,statement,topic_label FROM challenges
        WHERE statement IS NOT NULL
    """).fetchall()
    docs=[(r["external_id"],r["title"],tokens((r["title"] or "")+" "+
          (r["statement"] or "")+" "+(r["topic_label"] or ""))) for r in candidates
          if r["external_id"] != exclude_id]
    query=tokens(text)
    if not query or not docs:
        return []
    df=Counter()
    for *_, terms in docs:
        df.update(set(terms))
    N=len(docs)
    weights=lambda t: {word:(1+math.log(freq))*(1+math.log((N+1)/(df[word]+1)))
                       for word,freq in Counter(t).items()}
    q=weights(query)
    qnorm=math.sqrt(sum(v*v for v in q.values()))
    results=[]
    for identifier,title,terms in docs:
        v=weights(terms)
        denom=qnorm*math.sqrt(sum(x*x for x in v.values()))
        score=sum(q[w]*v.get(w,0) for w in q)/denom if denom else 0
        if score>0:
            results.append({"external_id":identifier,"title":title,
                            "lexical_cosine":round(score,4)})
    return sorted(results,key=lambda r:r["lexical_cosine"],reverse=True)[:limit]


def import_legacy(con, root=BASE):
    """Import only what is evidenced; safe to run repeatedly."""
    imported=[]
    progress=root/"data/progress.csv"
    if progress.exists():
        with progress.open(newline="",encoding="utf8") as f:
            rows=list(csv.DictReader(f))
        for r in rows:
            ident=(r.get("problem_id") or "").strip()
            if ident != "B1":
                # Other entries require explicit source mapping; do not silently invent.
                continue
            with con:
                exists=con.execute("SELECT id FROM challenges WHERE external_id=?",(ident,)).fetchone()
                if exists:
                    continue
                con.execute("""
                    INSERT INTO challenges(external_id,session_type,status,source,difficulty,
                        title,selected_at,created_at,notes)
                    VALUES (?,'baseline','evaluated','historical_summary',?,?,?, ?,?)
                """,(ident, int(r["difficulty"]) if r.get("difficulty") else None,
                     "Non-Decreasing Sequence",r["date"],now(),
                     "Original complete statement and verbatim learner submission were not saved; summary-only import."))
                attempt=add_attempt(con,ident,
                    "Historical summary only: independently derived the optimal streaming greedy algorithm; "
                    "O(N) time, O(1) auxiliary space. Original solution text unavailable.",
                    stage="first",provenance="summary_only",hint_level=int(r["hint_level"]),
                    independent=True,minutes=float(r["minutes_to_first_solution"]),
                    time_source=r["time_source"],confidence=int(r["confidence_percent"]),
                    submitted_at=r["date"],notes="Imported from historical progress.csv.")
                add_assessment(con,attempt,reviewer="historical_summary",
                    correct=True,optimality=True,
                    time_complexity="O(N)",space_complexity="O(1)",
                    legacy_score="21/24 provisional (old scale; NOT eight-dimension rubric)",
                    evidence="Previous session summary only; not independently regraded from full text.",
                    notes="Rubric sub-scores missing. Do not infer them.")
                imported.append(ident)
    previous=root/"data/last_challenge.json"
    if previous.is_file():
        r=json.loads(previous.read_text(encoding="utf8"))
        ident=f"RACG-{int(r['challenge_number']):04d}"
        statement_file=r.get("statement_file")
        statement=(root/statement_file).read_text(encoding="utf8") if statement_file else None
        rolls=r.get("rolls",{})
        with con:
            exists=con.execute("SELECT id FROM challenges WHERE external_id=?",(ident,)).fetchone()
            if not exists:
                con.execute("""
                    INSERT INTO challenges(
                        external_id,session_type,status,source,topic_id,topic_label,difficulty,
                        title,statement,statement_hash,constraints_json,presentation,continuation,
                        roll_o,roll_x,roll_y,roll_p,selected_at,presented_at,created_at,notes
                    ) VALUES(?,'RACG','presented','historical_import',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,(ident,r["topic_id"],r["topic_label"],r["difficulty"],r.get("title"),
                     statement,hashlib.sha256(statement.encode("utf8")).hexdigest() if statement else None,
                     as_json(r.get("constraints",{})),r.get("presentation"),
                     int(r["continuation"]),rolls.get("O"),rolls.get("X"),rolls.get("Y"),
                     rolls.get("P"),r["date"],r["date"],now(),
                     r.get("notes","")+" Topic ID 86 legacy mismatch preserved as historical fact."))
                imported.append(ident)
    return imported


def status(con):
    counts={r["status"]:r["n"] for r in con.execute(
        "SELECT status,COUNT(*) AS n FROM challenges GROUP BY status")}
    latest=con.execute("""SELECT external_id,title,status,topic_label,difficulty,
                               roll_o,roll_x,roll_y,roll_p
                        FROM challenges WHERE session_type='RACG' ORDER BY id DESC LIMIT 1""").fetchone()
    return {"total_challenges":sum(counts.values()),"by_status":counts,
            "total_attempts":con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
            "total_assessments":con.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
            "latest_racg":dict(latest) if latest else None}


def doctor(con):
    integrity=con.execute("PRAGMA integrity_check").fetchone()[0]
    fkeys=[tuple(row) for row in con.execute("PRAGMA foreign_key_check")]
    fts_consistency="ok"
    try:
        con.execute("INSERT INTO challenge_fts(challenge_fts,rank) VALUES('integrity-check',1)")
    except sqlite3.DatabaseError as e:
        fts_consistency=str(e)
    return {"integrity_check":integrity,"foreign_key_errors":fkeys,
            "fts_consistency":fts_consistency, **status(con)}


def parse_bool(s):
    if s is None or s == "unknown":
        return None
    if s == "yes":
        return True
    if s == "no":
        return False
    raise ValueError("Expected yes, no, or unknown")


def main():
    p=argparse.ArgumentParser(description="ARDS SQLite memory store")
    p.add_argument("--db",type=Path,default=DEFAULT_DB)
    sp=p.add_subparsers(dest="action",required=True)
    sp.add_parser("init",help="Create an empty ARDS database; does not import historical records")
    p.add_argument("--legacy-root",type=Path,help="Explicitly import test or historical legacy data on init only")
    sp.add_parser("status")
    sp.add_parser("doctor")
    ls=sp.add_parser("list")
    ls.add_argument("--limit",type=int,default=30)
    ls.add_argument("--status")
    sho=sp.add_parser("show")
    sho.add_argument("challenge")
    prs=sp.add_parser("present",help="Attach verified full statement to pending draw")
    prs.add_argument("challenge")
    prs.add_argument("--title",required=True)
    prsinput=prs.add_mutually_exclusive_group(required=True)
    prsinput.add_argument("--file",type=Path)
    prsinput.add_argument("--stdin",action="store_true",help="Read full statement from stdin")
    prs.add_argument("--constraints-file",type=Path)
    prs.add_argument("--notes")
    ab=sp.add_parser("abandon",help="Abandon an unpresented selection with justification")
    ab.add_argument("challenge")
    ab.add_argument("--reason",required=True)
    att=sp.add_parser("attempt")
    att.add_argument("challenge")
    attinput=att.add_mutually_exclusive_group(required=True)
    attinput.add_argument("--file",type=Path)
    attinput.add_argument("--stdin",action="store_true",help="Read the learner submission verbatim from stdin")
    att.add_argument("--stage",choices=STAGES,default="first")
    att.add_argument("--provenance",choices=("verbatim","summary_only"),default="verbatim")
    att.add_argument("--hint-level",type=int)
    att.add_argument("--independent",choices=("yes","no"))
    att.add_argument("--minutes",type=float)
    att.add_argument("--time-source",choices=("self-reported","instrumented"))
    att.add_argument("--confidence",type=int)
    att.add_argument("--notes")
    ass=sp.add_parser("assess")
    ass.add_argument("attempt_id",type=int)
    ass.add_argument("--reviewer",required=True)
    ass.add_argument("--correct",choices=("yes","no","unknown"),default="unknown")
    ass.add_argument("--optimality",choices=("yes","no","unknown"),default="unknown")
    ass.add_argument("--time-complexity")
    ass.add_argument("--space-complexity")
    ass.add_argument("--scores-file",type=Path)
    ass.add_argument("--evidence")
    ass.add_argument("--notes")
    obs=sp.add_parser("observe")
    obs.add_argument("challenge")
    obs.add_argument("--kind",required=True,choices=("strength","weakness","insight","uncertain"))
    obs.add_argument("--concept",required=True)
    obs.add_argument("--evidence",required=True)
    obs.add_argument("--attempt-id",type=int)
    sea=sp.add_parser("search")
    sea.add_argument("query")
    sea.add_argument("--limit",type=int,default=10)
    sim=sp.add_parser("near")
    sim.add_argument("--file",type=Path,required=True)
    sim.add_argument("--limit",type=int,default=5)
    sim.add_argument("--exclude-id")
    bak=sp.add_parser("backup")
    bak.add_argument("--dest",type=Path)
    args=p.parse_args()
    if hasattr(args,"limit") and not 1<=args.limit<=100:
        p.error("--limit must be 1..100")
    with connect(args.db) as con:
        try:
            if args.action=="init":
                output({"imported":import_legacy(con,root=args.legacy_root) if args.legacy_root else [],"status":status(con)})
            elif args.action=="status":
                output(status(con))
            elif args.action=="doctor":
                output(doctor(con))
            elif args.action=="list":
                query="SELECT external_id,title,status,session_type,topic_label,difficulty FROM challenges"
                params=[]
                if args.status:
                    query+=" WHERE status=?"
                    params.append(args.status)
                query+=" ORDER BY id DESC LIMIT ?"
                params.append(args.limit)
                output([dict(row) for row in con.execute(query,params)])
            elif args.action=="show":
                challenge=get_challenge(con,args.challenge)
                attempts=[]
                for attempt in con.execute("SELECT * FROM attempts WHERE challenge_id=? ORDER BY id",(challenge["id"],)):
                    item=dict(attempt)
                    item["assessments"]=[dict(row) for row in con.execute(
                        "SELECT * FROM assessments WHERE attempt_id=? ORDER BY id",(attempt["id"],))]
                    attempts.append(item)
                challenge["attempts"]=attempts
                challenge["observations"]=[dict(row) for row in con.execute(
                    "SELECT * FROM observations WHERE challenge_id=? ORDER BY id",(challenge["id"],))]
                output(challenge)
            elif args.action=="present":
                obj=json.loads(args.constraints_file.read_text(encoding="utf8")) if args.constraints_file else None
                import sys
                statement=sys.stdin.read() if args.stdin else args.file.read_text(encoding="utf8")
                output(present_challenge(con,args.challenge,args.title,statement,
                                         obj,args.notes))
            elif args.action=="abandon":
                output(abandon_selection(con,args.challenge,args.reason))
            elif args.action=="attempt":
                import sys
                submission=sys.stdin.read() if args.stdin else args.file.read_text(encoding="utf8")
                iid=add_attempt(con,args.challenge,submission,
                    args.stage,args.provenance,args.hint_level,
                    {"yes":True,"no":False}.get(args.independent),args.minutes,
                    args.time_source,args.confidence,args.notes)
                output({"attempt_id":iid,"challenge":args.challenge,"stage":args.stage})
            elif args.action=="assess":
                scores=json.loads(args.scores_file.read_text(encoding="utf8")) if args.scores_file else {}
                iid=add_assessment(con,args.attempt_id,args.reviewer,parse_bool(args.correct),
                    parse_bool(args.optimality),args.time_complexity,args.space_complexity,
                    scores,args.evidence,args.notes)
                output({"assessment_id":iid,"attempt_id":args.attempt_id})
            elif args.action=="observe":
                output({"observation_id":add_observation(con,args.challenge,args.kind,args.concept,
                                                         args.evidence,args.attempt_id)})
            elif args.action=="search":
                output(search(con,args.query,args.limit))
            elif args.action=="near":
                output({"method":"lexical_tf-idf_cosine_not_embeddings",
                        "matches":near(con,args.file.read_text(encoding="utf8"),
                                       args.limit,args.exclude_id)})
            elif args.action=="backup":
                dest=args.dest or BASE/"data/backups"/("ards-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".db")
                dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.resolve()==Path(args.db).resolve():
                    raise ValueError("Backup target cannot be active database")
                if dest.exists():
                    raise FileExistsError(dest)
                with sqlite3.connect(dest) as target:
                    con.backup(target)
                output({"backup":str(dest),"bytes":dest.stat().st_size})
        except (ValueError,sqlite3.IntegrityError) as e:
            p.error(str(e))


if __name__=="__main__":
    main()
