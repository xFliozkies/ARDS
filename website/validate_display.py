#!/usr/bin/env python3
"""Validate solver-visible CodeChef-style ARDS fields before publishing.

Validates shape and formatting contracts, not mathematical correctness.
"""
from pathlib import Path
import argparse
import json
from statement_format import format_statement, validate

def validate_package(path):
    package=json.loads(Path(path).read_text(encoding="utf-8"))
    display=package.get("statement_display")
    if display is None:
        raise ValueError("A new package must include explicit statement_display; legacy parsing is read-only")
    # Freshly authored statements must put all solvability rules in their
    # description, input/output contract, and constraints. Historical packages
    # may still contain notes/explanations but the public adapter strips them.
    if not isinstance(display,dict):
        raise ValueError("statement_display must be an object")
    if "notes" in display:
        raise ValueError("New problem statements must not include a Note section; move essential rules into the specification")
    if any(isinstance(s,dict) and "explanation" in s for s in display.get("samples",[])):
        raise ValueError("New problem samples must contain only input and output, without explanations")
    clean=validate(display)
    if not clean["samples"]:
        raise ValueError("A published practice problem must include at least one verified sample")
    if not clean["constraints"]:
        raise ValueError("A new practice problem must state explicit constraints")
    if not clean["input_format"] or not clean["output_format"]:
        if package.get("judge_mode")=="stdin":
            raise ValueError("Program-judged problems require explicit input_format and output_format")
    # All sample fields must be genuinely specified; proof/oracle verification is a separate gate.
    return {
        "valid":True,"sample_count":len(clean["samples"]),
        "constraint_count":len(clean["constraints"]),
        "has_input_format":bool(clean["input_format"]),
        "has_output_format":bool(clean["output_format"]),
        "format":clean["format"],"mathematical_correctness_checked":False
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("package",type=Path,help="Authored public problem package JSON")
    args=parser.parse_args()
    try: print(json.dumps(validate_package(args.package),indent=2))
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as err:parser.error(str(err))
