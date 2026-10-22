#!/usr/bin/env python3
"""RACG random challenge selection, preserving historical topic labels.

Draw a challenge: python3 scripts/racg.py
Review prior state: python3 scripts/racg.py --status
Preview without changing state: python3 scripts/racg.py --preview

A challenge selection is NOT a generated or verified problem statement.
"""
import argparse
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_STATE = BASE / "data" / "racg_state.json"
TOPIC_FILE = BASE / "references" / "topic_catalog.md"
HISTORY_FILE = BASE / "data" / "draws.jsonl"
N, M = 100, 6
# Each unit is a percentage point for a fresh-topic difficulty draw.
DIFFICULTY_WEIGHTS = (30, 25, 20, 12, 8, 5)
assert len(DIFFICULTY_WEIGHTS) == M and sum(DIFFICULTY_WEIGHTS) == 100


def difficulty_roll_size(min_level=1):
    """Total weight for the eligible levels [min_level, 6]."""
    if type(min_level) is not int or not 1 <= min_level <= M:
        raise ValueError("Invalid minimum difficulty")
    return sum(DIFFICULTY_WEIGHTS[min_level - 1:])


def difficulty_from_roll(y, min_level=1):
    """Map a one-based, uniformly sampled roll to an exact weighted level.

    For continuations, sampling only the eligible tail renormalizes weights
    without clamping, rounding, or discretization error.
    """
    total = difficulty_roll_size(min_level)
    if type(y) is not int or not 1 <= y <= total:
        raise ValueError("Difficulty roll outside eligible weight range")
    for level in range(min_level, M + 1):
        weight = DIFFICULTY_WEIGHTS[level - 1]
        if y <= weight:
            return level
        y -= weight
    raise AssertionError("Unreachable difficulty roll")




def catalog():
    topics = {}
    for number, name in re.findall(r"(?m)^(\d{1,3})\. (.+)$", TOPIC_FILE.read_text(encoding="utf8")):
        number = int(number)
        if number in topics:
            raise ValueError("Duplicate topic ID")
        topics[number] = name.strip()
    if set(topics) != set(range(1, N + 1)):
        raise ValueError("Expected exactly 100 topics numbered 1 to 100")
    return topics


def validate(previous):
    if previous is None:
        return None
    if not isinstance(previous, dict):
        raise ValueError("Previous state must be a JSON object")
    topic_id = previous.get("topic_id")
    difficulty = previous.get("difficulty")
    if type(topic_id) is not int or not 1 <= topic_id <= N:
        raise ValueError("Invalid previous topic_id")
    if type(difficulty) is not int or not 1 <= difficulty <= M:
        raise ValueError("Invalid previous difficulty")
    return previous


def draw(previous=None, randbelow=None, topics=None):
    """All raw rolls are independent; injected RNG is for deterministic tests only."""
    previous = validate(previous)
    if randbelow is None:
        randbelow = secrets.randbelow
    if topics is None:
        topics = catalog()

    O = randbelow(100) + 1
    continuing = O <= 15 and previous is not None
    if continuing:
        X = None
        topic_id = previous["topic_id"]
        # Preserve the actual former topic despite the legacy #86 catalog mismatch.
        topic_label = previous.get("topic_label") or topics[topic_id]
        historical_mismatch = topic_label != topics[topic_id]
    else:
        X = randbelow(N * 1000)
        topic_id = 1 + X % N
        topic_label = topics[topic_id]
        historical_mismatch = False

    # Sample Y uniformly from the integer weight units for eligible levels.
    # Fresh topics draw 1..100; continuations use the eligible tail only.
    min_level = previous["difficulty"] if continuing else 1
    Y = randbelow(difficulty_roll_size(min_level)) + 1
    difficulty = difficulty_from_roll(Y, min_level)

    P = randbelow(100) + 1
    return {
        "topic_id": topic_id,
        "topic_label": topic_label,
        "difficulty": difficulty,
        "continuation": continuing,
        "story": P <= 70,
        "presentation": "story" if P <= 70 else "direct",
        "historical_catalog_mismatch": historical_mismatch,
        "rolls": {"O": O, "X": X, "Y": Y, "P": P},
    }


def load_state(path):
    if not path.is_file():
        return None
    return validate(json.loads(path.read_text(encoding="utf8")))


def main():
    """Use the SQLite database as the source of truth; JSON files are mirrors."""
    import sys
    import memory

    parser = argparse.ArgumentParser(description="Randomized Algorithmic Challenge Generator (RACG)")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE,
                        help="Compatibility snapshot, not the authoritative store")
    parser.add_argument("--db", type=Path, default=memory.DEFAULT_DB,
                        help="Authoritative SQLite ARDS database")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="Show latest saved selection")
    group.add_argument("--preview", action="store_true",
                       help="Draw without saving and without altering the previous selection")
    args = parser.parse_args()

    with memory.connect(args.db) as con:
        previous = memory.latest_racg(con)
        if args.status:
            latest = con.execute("""
                SELECT external_id,status,topic_id,topic_label,difficulty,presentation,
                       continuation,roll_o,roll_x,roll_y,roll_p
                FROM challenges WHERE session_type='RACG'
                ORDER BY id DESC LIMIT 1
            """).fetchone()
            print(json.dumps(dict(latest) if latest else None, indent=2, ensure_ascii=False))
            return
        if args.preview:
            selected=draw(previous)
            print(json.dumps(dict(selected, preview_only=True),
                             indent=2, ensure_ascii=False))
            return
        try:
            selected=memory.record_random_selection(con,draw)
        except ValueError as exc:
            parser.error(str(exc))

    # Compatibility snapshots: best effort, database selection already committed.
    # Never silently roll again because snapshot publication failed.
    try:
        args.state.parent.mkdir(parents=True,exist_ok=True)
        data={key:value for key,value in selected.items()
              if key not in ("external_id","status")}
        tmp=args.state.with_name(args.state.name+".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n",encoding="utf8")
        tmp.replace(args.state)
        if args.db.resolve()==memory.DEFAULT_DB.resolve():
            record=dict(selected,selected_at=datetime.now(timezone.utc).isoformat())
            with HISTORY_FILE.open("a",encoding="utf8") as f:
                f.write(json.dumps(record,ensure_ascii=False)+"\n")
    except OSError as exc:
        print("Warning: selection is saved in SQLite, but compatibility snapshots could not "
              "be updated: "+str(exc),file=sys.stderr)
    print(json.dumps(selected, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
