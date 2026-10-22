#!/usr/bin/env python3
"""Preview and reset local ARDS learning state.

Default: inspection only. --confirm-reset archives learner state unless
--no-backup is explicitly requested, in which case active data is discarded
without any new archive. Existing historical archives remain untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
DATA_FOLDERS=("data","audit","exports",".scoped-artifacts","reviewers")


def _files(root,folders):
    for name in folders:
        p=root/name
        if p.is_symlink():
            raise ValueError("Refusing symlink folder: "+str(p))
        if p.is_dir():
            for entry in p.rglob("*"):
                if entry.is_symlink():
                    raise ValueError("Refusing symlink inside reset scope: "+str(entry))


def _hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for b in iter(lambda:stream.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def _running_server(root):
    proc=Path("/proc")
    if not proc.is_dir():return False
    for path in proc.iterdir():
        if not path.name.isdigit():continue
        try:
            args=[x.decode("utf-8","replace") for x in (path/"cmdline").read_bytes().split(b"\0") if x]
            if any(a.endswith("website/server.py") for a in args):
                cwd=(path/"cwd").resolve()
                if cwd==root:
                    return True
        except (OSError,PermissionError):
            pass
    return False


def reset(root:Path,confirm=False,no_backup=False):
    root=root.resolve(strict=True)
    if not (root/"scripts/memory.py").is_file() or not (root/"website/server.py").is_file():
        raise ValueError("Not a supported ARDS workspace")
    db=root/"data/ards.db"
    if not db.is_file():
        raise ValueError("Canonical database absent. Refusing a misleading reset")
    if confirm and _running_server(root):
        raise ValueError("Stop the ARDS website before resetting its databases")
    _files(root,DATA_FOLDERS)
    counts={}
    with sqlite3.connect(db,timeout=20) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise ValueError("Canonical database failed integrity")
        if confirm:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        for table in ("challenges","attempts","assessments","authoring_batches",
                      "problem_packages","independent_reviews","releases","solution_reveals"):
            counts[table]=con.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
    website_db=root/"data/ards-studio.db"
    if website_db.is_file():
        with sqlite3.connect(website_db,timeout=20) as con:
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("Website draft database failed integrity")
            if confirm:
                con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            counts["ppc_drafts"]=con.execute("SELECT COUNT(*) FROM ppc_drafts").fetchone()[0]
    if not confirm:
        return {"mode":"preview","counts":counts,
                "message":"No changes made; run with --confirm-reset after approving full data removal"}
    if no_backup:
        # Explicitly irreversible: no archive, snapshot, copy, or rename.
        # Only the five runtime-data directories are deleted. Keep source,
        # tests, documentation, and previously existing external archives.
        import shutil
        for name in DATA_FOLDERS:
            path=root/name
            if path.exists():
                shutil.rmtree(path)
        for name in ("data","data/backups","data/validation","data/authoring",
                     "audit","exports",".scoped-artifacts","reviewers"):
            (root/name).mkdir(parents=True,exist_ok=True)
        sys.path[:0]=[str(root/"scripts"),str(root/"website")]
        import memory
        import server
        with memory.connect(root/"data/ards.db") as con:
            if con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]!=0:
                raise ValueError("New canonical database unexpectedly contains challenges")
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("Fresh canonical database failed integrity")
        server.initialize_site(root/"data/ards-studio.db")
        with sqlite3.connect(root/"data/ards-studio.db") as con:
            if con.execute("SELECT COUNT(*) FROM ppc_drafts").fetchone()[0]!=0:
                raise ValueError("Fresh website database unexpectedly contains PPC drafts")
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("Fresh website database failed integrity")
        stamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (root/"data/README.md").write_text(
            "# Fresh ARDS learning state\n\n"
            "Reset on "+stamp+" at the learner's request, with no new backup.\n"
            "Previous active learner data was discarded. Older external backups were not altered.\n"
            "Do not auto-import historical records.\n",encoding="utf-8")
        return {"mode":"reset","backup_created":False,"former_counts":counts,
                "current_challenges":0,"current_ppc_drafts":0}
    backup_root=root.parent/(root.name+"-reset-backups")
    backup_root.mkdir(mode=0o700,exist_ok=True)
    if backup_root.is_symlink():
        raise ValueError("Backup directory cannot be a symlink")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination=backup_root/stamp
    if destination.exists():
        raise FileExistsError("Backup timestamp collision. Retry in one second")
    destination.mkdir(mode=0o700)
    moved=[]
    try:
        for name in DATA_FOLDERS:
            if (root/name).exists():
                os.rename(root/name,destination/name)
                moved.append(name)
        for name in ("data","data/backups","data/validation","data/authoring",
                     "audit","exports",".scoped-artifacts","reviewers"):
            (root/name).mkdir(parents=True,exist_ok=True)
        sys.path[:0]=[str(root/"scripts"),str(root/"website")]
        import memory
        import server
        with memory.connect(root/"data/ards.db") as con:
            if con.execute("SELECT COUNT(*) FROM challenges").fetchone()[0]!=0:
                raise ValueError("New canonical database unexpectedly contains challenges")
            if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("Fresh canonical database failed integrity")
        server.initialize_site(root/"data/ards-studio.db")
        (root/"data/README.md").write_text(
            "# Fresh ARDS learning state\n\n"
            "Full reset completed at "+stamp+". Previous learner state is stored outside this project at:\n\n"
            +str(destination)+"\n\nDo not auto-import any archived records.\n",encoding="utf-8")
    except Exception:
        # Restore original directories if initialization fails. Never overwrite
        # an existing active file; preserve the backup even if rollback is partial.
        for name in reversed(moved):
            original=root/name
            if original.exists():
                import shutil
                shutil.rmtree(original)
            os.rename(destination/name,original)
        raise
    manifest={"created_at":datetime.now(timezone.utc).isoformat(),
              "former_counts":counts,"archived_paths":moved,"files":{}}
    for name in moved:
        for file in (destination/name).rglob("*"):
            if file.is_file():
                manifest["files"][str(file.relative_to(destination))]={
                    "size":file.stat().st_size,"sha256":_hash(file)}
    (destination/"MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    for name,meta in manifest["files"].items():
        f=destination/name
        if not f.is_file() or f.stat().st_size!=meta["size"] or _hash(f)!=meta["sha256"]:
            raise RuntimeError("Safety archive verification failed for "+name+
                               "; original data remains in "+str(destination))
    return {"mode":"reset","archive":str(destination),
            "verified_backup_files":len(manifest["files"]),"former_counts":counts,
            "current_challenges":0}


def main():
    p=argparse.ArgumentParser(description="Archive and reset ARDS learning data; preview by default")
    p.add_argument("--root",type=Path,default=ROOT,help="ARDS project root (for isolated testing)")
    p.add_argument("--confirm-reset",action="store_true",help="Explicitly reset all active learner state")
    p.add_argument("--no-backup",action="store_true",help="Discard active learner state without creating an archive (requires --confirm-reset)")
    args=p.parse_args()
    if args.no_backup and not args.confirm_reset:
        p.error("--no-backup requires --confirm-reset")
    result=reset(args.root,args.confirm_reset,args.no_backup)
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
