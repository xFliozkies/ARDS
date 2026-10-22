#!/usr/bin/env python3
"""ARDS Studio — local-only, light-themed problem browser and PPC workspace.

Uses the canonical ARDS database read-only for browsing, and its existing
memory.add_attempt transaction for final learner attempts. In-progress PPC
drafts are stored in a separate SQLite database to avoid changing challenge
statuses prematurely.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(__file__).resolve().parent
DB = ROOT / "data" / "ards.db"
WEB_DB = ROOT / "data" / "ards-studio.db"
sys.path.insert(0, str(ROOT / "scripts"))
import memory
import ards2
from statement_format import format_statement

MAX_BODY = 120_000
SECTIONS = ("problem", "procedure", "correctness", "complexity")
TOKEN = secrets.token_urlsafe(32)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize_site(db=None):
    db = WEB_DB if db is None else Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    # Additive canonical migration for permanent answer-exposure records.
    # Never changes historical attempts or challenges.
    if DB.exists():
        with memory.connect(DB):
            pass
    con = sqlite3.connect(db, timeout=10)
    try:
        con.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS ppc_drafts(
                challenge_id TEXT PRIMARY KEY,
                problem TEXT NOT NULL DEFAULT '',
                procedure TEXT NOT NULL DEFAULT '',
                correctness TEXT NOT NULL DEFAULT '',
                complexity TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ppc_draft_revisions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_id TEXT NOT NULL,
                body_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_draft_rev_challenge
               ON ppc_draft_revisions(challenge_id, id DESC);
        """)
    finally:
        con.close()


def database():
    # Read-only connection never mutates production records during browsing.
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def list_problems(search="", difficulty="", status="", limit=250, topic="", family="", presentation="", progress="", similar_to="", sort="newest"):
    """List released problems and safe, registered batch previews.

    An authored but unverified package has no challenges.statement until
    release. Never return its private body_json or accept an assessment for it.
    """
    with database() as con:
        query = """
          WITH candidates AS (
            SELECT c.*,rp.primary_pattern,e.edition,e.assurance AS edition_assurance,
                   e.statement AS edition_statement,
                   e.package_json AS edition_body,
                   pub.body_json AS published_body,pub.revision AS published_revision,
                   COALESCE(pr.body_json,p.body_json) AS draft_body,
                   CASE WHEN c.statement IS NULL AND b.id IS NOT NULL
                         AND p.id IS NOT NULL AND c.status='selected'
                        THEN 1 ELSE 0 END AS review_only,
                   CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END AS released
            FROM challenges c
            LEFT JOIN reasoning_plans rp ON rp.challenge_id=c.id
            LEFT JOIN classic_authoring_editions e ON e.id=(
                SELECT MAX(x.id) FROM classic_authoring_editions x
                WHERE x.challenge_id=c.id)
            LEFT JOIN authoring_batch_items b ON b.challenge_id=c.id
            LEFT JOIN problem_packages p ON p.challenge_id=c.id
            LEFT JOIN authoring_package_revisions pr ON pr.id=(
                SELECT MAX(x.id) FROM authoring_package_revisions x
                WHERE x.challenge_id=c.id)
            LEFT JOIN releases r ON r.challenge_id=c.id
            LEFT JOIN published_revisions pub ON pub.id=(
                SELECT MAX(x.id) FROM published_revisions x WHERE x.challenge_id=c.id)
          ),
          visible AS (
            SELECT external_id AS id, id AS challenge_id,
                   CASE WHEN review_only=1 THEN json_extract(draft_body,'$.title')
                        ELSE COALESCE(json_extract(edition_body,'$.title'),json_extract(published_body,'$.title'),title) END AS title,
                   CASE WHEN review_only=1 THEN 'under_review' ELSE status END AS status,
                   difficulty,topic_id,topic_label,presentation,session_type,created_at,
                   CASE WHEN review_only=1
                        THEN COALESCE(json_extract(draft_body,'$.model.family'),'')
                        ELSE COALESCE(json_extract(edition_body,'$.model.family'),json_extract(published_body,'$.model.family'),'') END AS family,
                   COALESCE(primary_pattern,'') AS reasoning_pattern,
                   review_only, released AS release_record,
                   COALESCE(edition,published_revision) AS edition, edition_assurance,
                   CASE WHEN review_only=1 THEN json_extract(draft_body,'$.statement')
                        ELSE COALESCE(edition_statement,json_extract(published_body,'$.statement_display.description'),statement) END AS statement
            FROM candidates
            WHERE review_only=0 AND COALESCE(edition_statement,statement) IS NOT NULL
          )
          SELECT v.*,
                 EXISTS(SELECT 1 FROM attempts a JOIN assessments s ON s.attempt_id=a.id
                        WHERE a.challenge_id=v.challenge_id AND a.stage='first' AND s.correct=1) AS passed,
                 EXISTS(SELECT 1 FROM solution_reveals x WHERE x.challenge_id=v.challenge_id) AS reference_revealed,
                 EXISTS(SELECT 1 FROM attempts a WHERE a.challenge_id=v.challenge_id) AS has_attempt
          FROM visible v WHERE 1=1
        """
        args = []
        if search:
            query += " AND (lower(v.title) LIKE ? OR lower(v.statement) LIKE ? OR lower(v.topic_label) LIKE ? OR lower(v.id) LIKE ?)"
            term = "%" + search.lower() + "%"
            args.extend((term,term,term,term))
        if difficulty:
            query += " AND v.difficulty=?"
            args.append(int(difficulty))
        if status:
            query += " AND v.status=?"
            args.append(status)
        if topic:
            query+=" AND v.topic_id=?"
            args.append(int(topic))
        if family:
            query+=" AND v.family=?"
            args.append(family)
        if presentation:
            query+=" AND v.presentation=?"
            args.append(presentation)
        if progress=="unattempted":
            query+=" AND NOT EXISTS(SELECT 1 FROM attempts a WHERE a.challenge_id=v.challenge_id)"
        elif progress=="attempted":
            query+=" AND EXISTS(SELECT 1 FROM attempts a WHERE a.challenge_id=v.challenge_id)"
        elif progress=="passed":
            query+=" AND EXISTS(SELECT 1 FROM attempts a JOIN assessments s ON s.attempt_id=a.id WHERE a.challenge_id=v.challenge_id AND s.correct=1)"
        elif progress=="revealed":
            query+=" AND EXISTS(SELECT 1 FROM solution_reveals r WHERE r.challenge_id=v.challenge_id)"
        elif progress=="eligible":
            query+=" AND v.review_only=0 AND NOT EXISTS(SELECT 1 FROM solution_reveals r WHERE r.challenge_id=v.challenge_id)"
        elif progress:
            raise ValueError("Invalid progress filter")
        order={"newest":"v.challenge_id DESC","oldest":"v.challenge_id ASC",
               "difficulty_asc":"v.difficulty ASC,v.challenge_id DESC",
               "difficulty_desc":"v.difficulty DESC,v.challenge_id DESC",
               "topic":"v.topic_id ASC,v.challenge_id DESC"}.get(sort)
        if order is None:
            raise ValueError("Invalid sort")
        query += " ORDER BY "+order+" LIMIT ?"
        args.append(limit)
        rows = [dict(x) for x in con.execute(query,args)]
    for x in rows:
        x.pop("statement",None)
        x.pop("challenge_id",None)
    if similar_to:
        base=next((p for p in list_problems(limit=-1) if p["id"]==similar_to),None)
        if base is None:
            raise ValueError("Unknown comparison problem")
        def score(p):
            return (8*int(p["topic_id"] is not None and p["topic_id"]==base["topic_id"])+
                    5*int(bool(p["family"]) and p["family"]==base["family"])+
                    4*int(bool(p["reasoning_pattern"]) and p["reasoning_pattern"]==base["reasoning_pattern"])+
                    2*int(p["difficulty"]==base["difficulty"]))
        rows=[dict(p,similarity_score=score(p)) for p in rows if p["id"]!=base["id"] and score(p)>2]
        rows.sort(key=lambda p:(-p["similarity_score"], abs((p["difficulty"] or 0)-(base["difficulty"] or 0)),p["id"]))
    return rows



def problem_facets():
    rows=list_problems(limit=250)
    return {"topics":[{"id":i,"label":label} for i,label in
                      sorted({(x["topic_id"],x["topic_label"] or "Topic "+str(x["topic_id"])) for x in rows if x["topic_id"]})],
            "families":sorted({x["family"] for x in rows if x["family"]}),
            "comparison":[{"id":x["id"],"title":x["title"]} for x in rows]}

def latest_classic_edition(con, challenge_id):
    return con.execute(
        "SELECT * FROM classic_authoring_editions WHERE challenge_id=? ORDER BY edition DESC LIMIT 1",
        (challenge_id,)
    ).fetchone()


def displayed_statement(challenge,edition):
    return edition["statement"] if edition else challenge["statement"]


def displayed_hash(challenge,edition):
    text=displayed_statement(challenge,edition)
    if edition:
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest()  # Codex edition 2 convention
        if digest!=edition["statement_sha256"]:
            raise ValueError("Authored edition statement hash mismatch")
        return digest
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def authored_edition_ppc(edition):
    """Derive readable P1/P2/C/K from Codex's full archived authoring package."""
    body=json.loads(edition["package_json"])
    model=body.get("model",{})
    ppc=body.get("ppc",{})
    problem=ppc.get("problem",{})
    complexity=ppc.get("complexity",{})
    if not all(isinstance(part,dict) for part in (model,ppc,problem,complexity)):
        raise ValueError("Malformed archived PPC")
    ref=body.get("reference_solution")
    proof=body.get("proof")
    termination=body.get("termination")
    if not all(isinstance(s,str) and s.strip() for s in (ref,proof,termination)):
        raise ValueError("The archived PPC lacks a reference algorithm, proof or termination argument")
    if any(not isinstance(complexity.get(k),str) or not complexity[k].strip()
           for k in ("input_measure","time_bound","space_bound","derivation")):
        raise ValueError("The archived PPC has no complete resource analysis")
    spec=(
        "Inputs and valid domain:\n"+str(problem.get("domain",""))+
        "\n\nRequired result:\n"+str(problem.get("postcondition",""))+
        "\n\nOutput type:\n"+str(problem.get("codomain",""))+
        "\n\nObjective:\n"+str(model.get("objective",""))+
        "\n\nConstraints:\n"+"\n".join(str(x) for x in model.get("constraints",[]))
    )
    return {
       "problem":spec,
       "procedure":ref,
       "correctness":proof+"\n\nTermination:\n"+termination,
       "complexity":"Input measure: "+complexity["input_measure"]+
           "\nTime: "+complexity["time_bound"]+
           "\nExtra space: "+complexity["space_bound"]+
           "\nDerivation: "+complexity["derivation"]
    }


def problem_detail(external_id):
    with database() as con:
        ch=con.execute(
            "SELECT * FROM challenges WHERE external_id=?",
            (external_id,)
        ).fetchone()
        if not ch:
            return None
        # Safely browse registered, versioned batch drafts without publishing
        # or exposing the private teacher PPC. Unregistered selections are hidden.
        if ch["statement"] is None:
            # Authoring packages are private, even with a guessed challenge ID.
            return None
        edition=latest_classic_edition(con,ch["id"])
        published=con.execute("SELECT revision,body_json,body_hash,verification_json FROM published_revisions WHERE challenge_id=? ORDER BY revision DESC LIMIT 1",(ch["id"],)).fetchone() if not edition else None
        latest_body=json.loads(published["body_json"]) if published else None
        result={
            "id":ch["external_id"],
            "title":ch["title"],
            "statement":latest_body["statement"] if latest_body else displayed_statement(ch,edition),
            "status":ch["status"],
            "difficulty":ch["difficulty"],
            "topic_label":ch["topic_label"],
            "presentation":ch["presentation"],
            "created_at":ch["created_at"],
            "presented_at":ch["presented_at"],
            "edition":edition["edition"] if edition else (published["revision"] if published else None),
            "reference_revealed":bool(con.execute(
                "SELECT 1 FROM solution_reveals WHERE challenge_id=?",(ch["id"],)
            ).fetchone()),
            "attempt_count":con.execute(
                "SELECT COUNT(*) FROM attempts WHERE challenge_id=?",(ch["id"],)
            ).fetchone()[0],
        }
        if edition:
            package=json.loads(edition["package_json"])
            result["title"]=package.get("title") or result["title"]
            try:
                authored_edition_ppc(edition)
                available=True
            except (ValueError,TypeError,KeyError):
                available=False
        else:
            released=con.execute("SELECT package_hash FROM releases WHERE challenge_id=?",(ch["id"],)).fetchone()
            package=latest_body or {}
            available=bool(latest_body and isinstance(latest_body.get("teacher_ppc"),dict))
            if released and not latest_body:
                try:
                    pkg,package=ards2.load_package(con,ch)
                    available=bool(pkg["body_hash"]==released["package_hash"] and
                                   isinstance(package.get("teacher_ppc"),dict))
                except ValueError:
                    pass
        imported=con.execute(
            "SELECT 1 FROM teacher_references WHERE challenge_id=? AND statement_sha256=?",
            (ch["id"],displayed_hash(ch,edition))
        ).fetchone()
        if latest_body:
            result["title"]=latest_body["title"]
        result["reference_available"]=available or bool(imported)
        result["edition_assurance"]=edition["assurance"] if edition else None
        result["topic_id"]=ch["topic_id"]
        result["family"]=package.get("model",{}).get("family") if package else None
        result["has_passing_assessment"]=bool(con.execute("""
             SELECT 1 FROM attempts a JOIN assessments x ON x.attempt_id=a.id
             WHERE a.challenge_id=? AND a.stage='first' AND a.independent=1 AND a.hint_level=0
                   AND x.correct=1""",(ch["id"],)).fetchone())
        sr=con.execute("SELECT preserved_attempt_id FROM solution_reveals WHERE challenge_id=?",
                       (ch["id"],)).fetchone()
        result["passed_before_reveal"]=bool(sr and sr["preserved_attempt_id"])
        result["presentation_data"]=format_statement(
             result["statement"],package)
        if latest_body:
            # Older publication bytes remain immutable; the public raw-string
            # fallback must not expose the retired Explanation/Note sections.
            from statement_format import public_markdown
            result["statement"]=public_markdown(result["presentation_data"])
        return result


def get_draft(external_id):
    with sqlite3.connect(WEB_DB) as con:
        row = con.execute(
            "SELECT problem,procedure,correctness,complexity,updated_at FROM ppc_drafts WHERE challenge_id=?",
            (external_id,)).fetchone()
    if not row:
        return {key:"" for key in SECTIONS}|{"updated_at":None}
    return dict(zip((*SECTIONS,"updated_at"),row))


def validate_ppc(body):
    if not isinstance(body,dict):
        raise ValueError("PPC submission must be an object")
    if set(body) != set(SECTIONS):
        raise ValueError("PPC fields must be exactly: "+", ".join(SECTIONS))
    for key in SECTIONS:
        val = body[key]
        if not isinstance(val,str) or len(val)>25000:
            raise ValueError(f"{key} must be text of at most 25,000 characters")
    return {key:body[key] for key in SECTIONS}


def write_draft(external_id, body):
    body=validate_ppc(body)
    moment=now()
    with sqlite3.connect(WEB_DB,timeout=10) as con:
        con.execute("""
            INSERT INTO ppc_drafts
              (challenge_id,problem,procedure,correctness,complexity,updated_at)
              VALUES(?,?,?,?,?,?)
            ON CONFLICT(challenge_id) DO UPDATE SET
              problem=excluded.problem,procedure=excluded.procedure,
              correctness=excluded.correctness,complexity=excluded.complexity,
              updated_at=excluded.updated_at
        """, (external_id,*[body[key] for key in SECTIONS],moment))
        con.execute(
            "INSERT INTO ppc_draft_revisions(challenge_id,body_json,created_at) VALUES (?,?,?)",
            (external_id,json.dumps(body,ensure_ascii=False,sort_keys=True),moment))
    return {"saved":True,"updated_at":moment}


def format_ppc(body):
    return ("# PPC — Problem Specification, Proposed Algorithm, Correctness Proof\n\n"
            "## P1 · Problem specification\n\n"+body["problem"].strip()+
            "\n\n## P2 · Proposed algorithm\n\n"+body["procedure"].strip()+
            "\n\n## C · Correctness proof\n\n"+body["correctness"].strip()+
            "\n\n## Complexity\n\n"+body["complexity"].strip()+"\n")


def submit_ppc(external_id,body):
    independent_attested=False
    if isinstance(body,dict) and set(body)=={"ppc","independent"}:
        if type(body["independent"]) is not bool: raise ValueError("Invalid independence attestation")
        independent_attested=body["independent"]
        body=body["ppc"]
    body=validate_ppc(body)
    if not all(body[key].strip() for key in SECTIONS):
        raise ValueError("Complete all four PPC sections before submitting.")
    # The canonical memory module enforces immutable first attempts and revisions.
    with memory.connect(DB) as con:
        row=memory.get_challenge(con,external_id)
        if row["status"] in ("selected","abandoned") or not row["statement"]:
            raise ValueError("Only presented problems can receive PPC submissions.")
        first=con.execute(
            "SELECT COUNT(*) FROM attempts WHERE challenge_id=?",(row["id"],)
        ).fetchone()[0]==0
        revealed=bool(con.execute(
            "SELECT 1 FROM solution_reveals WHERE challenge_id=?",(row["id"],)).fetchone())
        independent=bool(first and independent_attested and not revealed)
        result=memory.add_attempt(con,external_id,format_ppc(body),
                                 stage="first" if first else "revision",
                                 provenance="verbatim",
                                 hint_level=0 if independent else None,independent=independent,
                                 notes="Submitted using ARDS Studio; first-attempt independence learner-attested.")
    write_draft(external_id,body)
    return {"submitted":True,"stage":"first" if first else "revision",
            "independent":independent,"graded":False,
            "message":"Attempt archived; grading requires a separate evidence-based assessment.",
            "result":result if isinstance(result,(dict,str,int,list,type(None))) else str(result)}



def _load_teacher_ppc(con, challenge):
    """Return complete source-bound teacher material and honest assurance label."""
    edition=latest_classic_edition(con,challenge["id"])
    current_hash=displayed_hash(challenge,edition)
    published=con.execute("SELECT revision,body_json,body_hash,verification_json FROM published_revisions WHERE challenge_id=? ORDER BY revision DESC LIMIT 1",(challenge["id"],)).fetchone() if not edition else None
    if published:
        body=json.loads(published["body_json"])
        evidence=json.loads(published["verification_json"])
        if ards2.digest(body)!=published["body_hash"] or evidence.get("package_sha256")!=published["body_hash"] or evidence.get("review_outcome")!="passed":
            raise ValueError("Published reference edition has invalid review evidence")
        teacher=body.get("teacher_ppc")
        if not isinstance(teacher,dict) or set(teacher)!=set(SECTIONS) or any(not isinstance(teacher[k],str) or not teacher[k].strip() for k in SECTIONS):
            raise ValueError("Published reference edition is missing PPC sections")
        return {k:teacher[k] for k in SECTIONS}, "Independently AI-reviewed with bounded tests; mathematical arguments are not machine-proved. Reference edition "+str(published["revision"])
    if edition:
        try:
            return authored_edition_ppc(edition), (
                "Codex-authored edition "+str(edition["edition"])+
                " teacher PPC. Drafted, not independently or mechanically verified."
            )
        except (ValueError,TypeError,KeyError):
            pass
    # Released ARDS packages can be used for the original statement only.
    # Do not show an older solution for a different authored edition.
    row=con.execute("SELECT package_hash FROM releases WHERE challenge_id=?",
                    (challenge["id"],)).fetchone()
    if row and edition is None:
        pkg,package=ards2.load_package(con,challenge)
        if pkg["body_hash"]!=row["package_hash"]:
            raise ValueError("Released teacher PPC does not match the published package")
        teacher=package.get("teacher_ppc")
        if isinstance(teacher,dict) and set(teacher)==set(SECTIONS) and all(
            isinstance(teacher[k],str) and teacher[k].strip() for k in SECTIONS
        ):
            return {k:teacher[k] for k in SECTIONS}, "Released teacher reference; test verification does not equal mathematical proof."
    imported=con.execute("""SELECT ppc_json,assurance,statement_sha256
        FROM teacher_references WHERE challenge_id=?""",(challenge["id"],)).fetchone()
    if imported and imported["statement_sha256"]==current_hash:
        teacher=json.loads(imported["ppc_json"])
        if isinstance(teacher,dict) and set(teacher)==set(SECTIONS) and all(
            isinstance(teacher[k],str) and teacher[k].strip() for k in SECTIONS
        ):
            return teacher, "AI-authored teacher reference; algorithm and proof NOT independently verified."
    raise ValueError("No complete, statement-bound reference PPC has been imported or released for this problem.")


def reveal_reference_ppc(external_id):
    """One-way learner exposure. Written BEFORE any secret is sent to the client."""
    with memory.connect(DB) as con:
        challenge = memory.get_challenge(con, external_id)
        if not challenge["statement"] or challenge["status"] in ("selected", "abandoned"):
            raise ValueError("Only presented challenges may reveal reference PPCs.")
        teacher,assurance = _load_teacher_ppc(con, challenge)
        with con:
            first=con.execute("""
                SELECT a.id FROM attempts a
                JOIN assessments x ON x.id=(SELECT MAX(y.id) FROM assessments y WHERE y.attempt_id=a.id)
                WHERE a.challenge_id=? AND a.stage='first' AND a.independent=1
                      AND a.hint_level=0 AND x.correct=1 LIMIT 1
            """,(challenge["id"],)).fetchone()
            con.execute(
                "INSERT OR IGNORE INTO solution_reveals(challenge_id,revealed_at,provenance,notes,preserved_attempt_id) "
                "VALUES (?,?,?,?,?)",
                (challenge["id"], now(), "ards-studio", "Learner explicitly opened complete reference PPC.",
                 first["id"] if first else None)
            )
        row = con.execute(
            "SELECT revealed_at,preserved_attempt_id FROM solution_reveals WHERE challenge_id=?",
            (challenge["id"],)
        ).fetchone()
    return {
        "challenge_id": external_id,
        "reference_revealed": True,
        "assessment_eligible": bool(row["preserved_attempt_id"]),
        "passed_before_reveal": bool(row["preserved_attempt_id"]),
        "revealed_at": row["revealed_at"],
        "reference_ppc": teacher,
        "verification_scope": assurance,
        "message": ("Verified passing independent first attempt preserved. Subsequent work is practice-only."
                    if row["preserved_attempt_id"] else
                    "Reference revealed. This challenge cannot earn new independent assessment credit.")
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ARDS-Studio/0.1"
    def log_message(self, fmt,*args):
        print("%s %s"%(now(),fmt%args),file=sys.stderr)

    def _send(self,data,status=200,content_type="application/json; charset=utf-8"):
        payload=(json.dumps(data,ensure_ascii=False).encode("utf-8") if
                 "application/json" in content_type else data)
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self,obj,status=200):
        self._send(obj,status)

    def _file(self,filename,typ):
        content=(SITE/"public"/filename).read_bytes()
        self._send(content,content_type=typ)

    def _error(self,status,message):
        self._json({"error":message},status)

    def _valid_host(self):
        # Localhost-only, no remote interfaces; reject host headers for other hosts.
        return self.headers.get("Host","").split(":")[0] in ("127.0.0.1","localhost")

    def do_GET(self):
        if not self._valid_host():
            return self._error(403,"This interface is localhost-only.")
        path=urlparse(self.path).path
        params=parse_qs(urlparse(self.path).query)
        try:
            if path in ("/","/index.html"):
                return self._file("index.html","text/html; charset=utf-8")
            if path=="/app.css":
                return self._file("app.css","text/css; charset=utf-8")
            if path=="/app.js":
                return self._file("app.js","text/javascript; charset=utf-8")
            if path=="/statement-renderer.js":
                return self._file("statement-renderer.js","text/javascript; charset=utf-8")
            if path=="/workspace-ui.js":
                return self._file("workspace-ui.js","text/javascript; charset=utf-8")
            # Fixed, local-only vendor resources; never concatenate unchecked paths.
            if path in ("/vendor/markdown-it.min.js", "/vendor/katex.min.js"):
                return self._file(path.lstrip("/"),"text/javascript; charset=utf-8")
            if path=="/vendor/katex.min.css":
                return self._file("vendor/katex.min.css","text/css; charset=utf-8")
            if path.startswith("/vendor/fonts/"):
                name=path.rsplit("/",1)[-1]
                if (name and name in {p.name for p in (SITE/"public/vendor/fonts").glob("*")}
                    and name.lower().endswith((".woff2",".woff",".ttf"))):
                    kind="font/woff2" if name.endswith(".woff2") else ("font/woff" if name.endswith(".woff") else "font/ttf")
                    return self._file("vendor/fonts/"+name,kind)
                return self._error(404,"Font not found")
            if path=="/workspace.css":
                return self._file("workspace.css","text/css; charset=utf-8")
            if path=="/guide.js":
                return self._file("guide.js","text/javascript; charset=utf-8")
            if path=="/guide.css":
                return self._file("guide.css","text/css; charset=utf-8")
            if path=="/typography.css":
                return self._file("typography.css","text/css; charset=utf-8")
            if path=="/guide-content.html":
                return self._file("guide-content.html","text/html; charset=utf-8")
            if path=="/api/session":
                return self._json({"token":TOKEN,"version":"0.1","theme":"light"})
            if path=="/api/facets":
                return self._json(problem_facets())
            if path=="/api/problems":
                difficulty=params.get("difficulty",[""])[0]
                if difficulty and (not difficulty.isdigit() or not 1<=int(difficulty)<=6):
                    return self._error(400,"Difficulty must be 1–6.")
                topic=params.get("topic",[""])[0]
                if topic and (not topic.isdigit() or not 1<=int(topic)<=100):
                    return self._error(400,"Topic must be 1–100.")
                filters=dict(
                    search=params.get("q",[""])[0][:100],difficulty=difficulty,
                    status=params.get("status",[""])[0][:32],
                    topic=topic, family=params.get("family",[""])[0][:120],
                    presentation=params.get("presentation",[""])[0][:12],
                    progress=params.get("progress",[""])[0][:20],
                    similar_to=params.get("similar_to",[""])[0][:40],
                    sort=params.get("sort",["newest"])[0][:22])
                # Backwards compatible: callers without a page get the existing list.
                if "page" not in params:
                    return self._json({"problems":list_problems(**filters)})
                raw_page=params["page"][0]
                raw_size=params.get("per_page",["12"])[0]
                if (not raw_page.isdigit() or not raw_size.isdigit()
                    or int(raw_page)<1 or int(raw_page)>100000
                    or int(raw_size) not in (12,24,48)):
                    return self._error(400,"Invalid pagination parameters.")
                page=int(raw_page)
                per_page=int(raw_size)
                # Filter and rank before paging, especially for similar-to searches.
                problems=list_problems(limit=-1,**filters)
                total=len(problems)
                pages=max(1,(total+per_page-1)//per_page)
                page=min(page,pages)
                start=(page-1)*per_page
                return self._json({"problems":problems[start:start+per_page],
                    "total":total,"page":page,"per_page":per_page,"pages":pages})
            if path.startswith("/api/problems/") and path.endswith("/similar"):
                external_id=path.split("/")[-2]
                if not problem_detail(external_id): return self._error(404,"Problem not found")
                return self._json({"problems":list_problems(similar_to=external_id)[:15]})
            if path.startswith("/api/problems/"):
                external_id=path.rsplit("/",1)[-1]
                detail=problem_detail(external_id)
                return self._json(detail) if detail else self._error(404,"Problem not found")
            if path.startswith("/api/drafts/"):
                external_id=path.rsplit("/",1)[-1]
                if not problem_detail(external_id):
                    return self._error(404,"Problem not found")
                return self._json(get_draft(external_id))
            if path=="/api/overview":
                with database() as con:
                    stats={
                        "challenges":con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],
                        "published":con.execute("SELECT COUNT(*) FROM challenges WHERE statement IS NOT NULL").fetchone()[0],
                        "attempts":con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
                        "assessments":con.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
                        "revealed":con.execute("SELECT COUNT(*) FROM solution_reveals").fetchone()[0],
                        "independent_graded":con.execute("""
                            SELECT COUNT(*) FROM attempts a
                            JOIN assessments s ON s.id=(
                                SELECT MAX(x.id) FROM assessments x WHERE x.attempt_id=a.id)
                            WHERE a.stage='first' AND a.independent=1 AND s.correct IS NOT NULL
                              AND NOT EXISTS(
                                SELECT 1 FROM solution_reveals r WHERE r.challenge_id=a.challenge_id
                                      AND COALESCE(r.preserved_attempt_id,-1)!=a.id)
                        """).fetchone()[0]
                    }
                # Authoring-queue totals are management information, never public library entries.
                with database() as conn:
                    stats["under_review"]=conn.execute("""SELECT COUNT(*) FROM authoring_batch_items b
                        JOIN challenges c ON c.id=b.challenge_id
                        JOIN problem_packages p ON p.challenge_id=c.id
                        WHERE c.status='selected'""").fetchone()[0]
                stats["authored"]=stats["published"]+stats["under_review"]
                with sqlite3.connect(WEB_DB) as con:
                    stats["drafts"]=con.execute("SELECT COUNT(*) FROM ppc_drafts").fetchone()[0]
                return self._json(stats)
            return self._error(404,"Not found")
        except ValueError as exc:
            return self._error(400,str(exc))
        except (sqlite3.Error,OSError) as exc:
            self.log_message("GET error: %s",str(exc))
            return self._error(500,"An internal error occurred")

    def do_POST(self):
        if not self._valid_host():
            return self._error(403,"Localhost required.")
        origin=self.headers.get("Origin")
        if origin and origin not in ("http://127.0.0.1:"+str(self.server.server_port),
                                      "http://localhost:"+str(self.server.server_port)):
            return self._error(403,"Invalid request origin.")
        if (self.headers.get("X-ARDS-Session")!=TOKEN or
                not self.headers.get("Content-Type","").startswith("application/json")):
            return self._error(403,"Missing local session token or JSON content type.")
        try:
            count=int(self.headers.get("Content-Length","0"))
            if not 0<count<=MAX_BODY:
                return self._error(413,"Request body too large or empty.")
            body=json.loads(self.rfile.read(count).decode("utf-8"))
            path=urlparse(self.path).path
            if path.startswith("/api/drafts/"):
                external_id=path.rsplit("/",1)[-1]
                if not problem_detail(external_id):
                    return self._error(404,"Problem not found")
                return self._json(write_draft(external_id,body))
            if path.startswith("/api/reveal/"):
                external_id=path.rsplit("/",1)[-1]
                if not problem_detail(external_id):
                    return self._error(404,"Problem not found")
                if not isinstance(body,dict) or body!={"confirm":True}:
                    return self._error(400,"Confirm that revealing the reference PPC permanently excludes this problem from independent assessment.")
                return self._json(reveal_reference_ppc(external_id))
            if path.startswith("/api/submissions/"):
                external_id=path.rsplit("/",1)[-1]
                if not problem_detail(external_id):
                    return self._error(404,"Problem not found")
                return self._json(submit_ppc(external_id,body),201)
            return self._error(404,"Not found")
        except (ValueError,json.JSONDecodeError,UnicodeDecodeError) as exc:
            return self._error(400,str(exc))
        except sqlite3.Error as exc:
            self.log_message("POST SQL error: %s",str(exc))
            return self._error(500,"Could not save to database")


def main():
    global DB, WEB_DB
    parser=argparse.ArgumentParser(description="Local ARDS Studio — dedicated light website")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--host",default="127.0.0.1",choices=("127.0.0.1",))
    parser.add_argument("--db",type=Path,default=DB,help="Canonical ARDS database (useful for isolated UI tests)")
    parser.add_argument("--draft-db",type=Path,default=WEB_DB,help="Separate PPC draft database")
    args=parser.parse_args()
    DB=args.db.resolve(); WEB_DB=args.draft_db.resolve()
    initialize_site()
    if not DB.exists():
        parser.error("Canonical ARDS database missing")
    with ThreadingHTTPServer((args.host,args.port),Handler) as server:
        print(f"ARDS Studio: http://{args.host}:{server.server_port}",flush=True)
        print("Local-only · Light theme · Production archive retained",flush=True)
        server.serve_forever()


if __name__=="__main__":
    main()
