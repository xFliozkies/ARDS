"""Versioned provenance and immutable artifact output for synthetic benchmarks."""
import hashlib
import platform
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT_SCHEMA="ppc-benchmark-v2"


def provenance():
    paths=sorted((ROOT/"scripts").glob("*.py"))+[ROOT/"tests"/"test_ppc3.py"]
    return {"report_schema":REPORT_SCHEMA,"canonical_encoding":"strict-json-v1",
            "python_version":platform.python_version(),
            "implementation":platform.python_implementation(),
            "source_sha256":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "scope":"Synthetic fixtures only; no live RACG draws or learner data"}


def write_immutable(folder, outputs):
    folder=Path(folder)
    # Check every existing file first, so a mismatch cannot create a mixed report.
    for name,blob in outputs.items():
        dest=folder/name
        if dest.exists() and dest.read_text(encoding="utf8")!=blob:
            raise FileExistsError("Preserved prior benchmark; incompatible rerun: "+str(dest))
    folder.mkdir(parents=True,exist_ok=True)
    for name,blob in outputs.items():
        dest=folder/name
        if not dest.exists():
            with dest.open("x",encoding="utf8") as stream:
                stream.write(blob)
