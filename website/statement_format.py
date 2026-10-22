"""CodeChef-style public problem statement model; no private PPC data."""
from __future__ import annotations
import re
import json

FIELDS = {"description","input_format","output_format","constraints","samples","notes"}
FENCE = re.compile(r"^\s*\x60{3,}")
HEADER = re.compile(r"^#{2,4}\s+(.+?)\s*$")
SAMPLE_HEADER = re.compile(r"^(?:\*\*)?\s*(?:Example|Sample)\s*(\d+)\s*:?\s*(?:\*\*)?\s*$", re.I)
SAMPLE_FIELD = re.compile(r"^(?:\*\*)?\s*(Input|Output|Explanation)\s*:?\s*(?:\*\*)?\s*$", re.I)
SECTION = {
    "input":"input_format","input format":"input_format",
    "output":"output_format","output format":"output_format",
    "constraint":"constraints","constraints":"constraints",
    "example":"examples","examples":"examples","samples":"examples",
    "sample":"examples","your task":"notes","notes":"notes","explanation":"notes"
}

def validate(data):
    if not isinstance(data,dict) or set(data)-FIELDS:
        raise ValueError("Unknown or invalid public statement fields")
    if not isinstance(data.get("description"),str) or not data["description"].strip():
        raise ValueError("Statement description is required")
    for k in ("input_format","output_format","notes"):
        if k in data and not isinstance(data[k],str):
            raise ValueError(k+" must be Markdown")
    for k in ("constraints","samples"):
        if k in data and not isinstance(data[k],list):
            raise ValueError(k+" must be a list")
    if any(not isinstance(c,str) or not c.strip() for c in data.get("constraints",[])):
        raise ValueError("Constraints must be nonempty text")
    for sample in data.get("samples",[]):
        if (not isinstance(sample,dict) or set(sample)-{"input","output","explanation"} or
            any(not isinstance(sample.get(k),str) or not sample[k].strip() for k in ("input","output")) or
            not isinstance(sample.get("explanation",""),str)):
            raise ValueError("Samples require verbatim nonempty input/output")
    # Keep legacy explanation/note fields parseable for archival compatibility,
    # but never send them in a student-visible payload. The mathematical rules
    # needed to solve a new task belong in the specification itself.
    return {"description":data["description"],
            "input_format":data.get("input_format",""),
            "output_format":data.get("output_format",""),
            "constraints":data.get("constraints",[]),
            "samples":[{"input":s["input"],"output":s["output"]} for s in data.get("samples",[])],
            "format":"ards-codechef-v1"}

def sections(text):
    chunks={"description":[]}
    key="description"
    in_fence=False
    for line in text.replace("\r","").splitlines():
        if not in_fence:
            m=HEADER.match(line)
            if m and m.group(1).strip().lower().rstrip(":") in SECTION:
                key=SECTION[m.group(1).strip().lower().rstrip(":")]
                chunks.setdefault(key,[])
                continue
        if FENCE.match(line):
            in_fence=not in_fence
        if key=="description" and line.startswith("# "):
            continue
        chunks.setdefault(key,[]).append(line)
    return {k:"\n".join(v).strip() for k,v in chunks.items()}

def constraints(text):
    return [re.sub(r"^\s*(?:[-*+]\s+|\d+\.\s+)","",line).strip()
            for line in text.splitlines()
            if re.sub(r"^\s*(?:[-*+]\s+|\d+\.\s+)","",line).strip()]

def examples(text):
    result=[]
    group=None
    section=None
    fenced=False
    for line in text.splitlines():
        if not fenced:
            m=SAMPLE_HEADER.match(line.strip())
            if m:
                if group:result.append(group)
                group={"input":[],"output":[],"explanation":[]};section=None
                continue
            m=SAMPLE_FIELD.match(line.strip())
            if m:
                if group is None:group={"input":[],"output":[],"explanation":[]}
                section=m.group(1).lower()
                continue
        if FENCE.match(line):
            fenced=not fenced
            continue
        if group is not None and section:
            group[section].append(line)
    if group:result.append(group)
    return [{"input":"\n".join(g["input"]).strip(),
             "output":"\n".join(g["output"]).strip(),
             "explanation":"\n".join(g["explanation"]).strip()}
            for g in result if "\n".join(g["input"]).strip() and "\n".join(g["output"]).strip()]

def strip_fence(raw):
    lines=raw.strip().splitlines()
    if lines and FENCE.match(lines[0]):lines.pop(0)
    if lines and FENCE.match(lines[-1]):lines.pop()
    return "\n".join(lines).strip()

def inline_legacy(raw):
    m=re.search(r"(?im)^\s*Example input\s*:\s*$",raw)
    intro,example=(raw[:m.start()].strip(),raw[m.start():]) if m else (raw,"")
    parsed=[]
    e=re.search(r"(?ims)^Example input\s*:\s*(.*?)\s*^Example output\s*:\s*(.*?)(?=^\s*Give an algorithm|\Z)",example)
    if e:
        parsed=[{"input":strip_fence(e.group(1)),"output":strip_fence(e.group(2))}]
    match=re.search(r"(?i)\bConstraints?\s*:\s*([^\n]*?)(?:\.(?:\s|$)|$)",intro)
    limits=[]
    if match:
        buf="";depth=0
        for char in match.group(1)+",":
            if char in "[({":depth+=1
            if char in "])}":depth=max(0,depth-1)
            if char=="," and not depth:
                if buf.strip():limits.append(buf.strip())
                buf=""
            else:buf+=char
        intro=intro[:match.start()]+intro[match.end():]
    intro=re.sub(r"(?im)^\s*Input is represented as JSON in the example;[^\n]*","",intro)
    intro=re.sub(r"(?im)^\s*Give an algorithm, justify correctness[^\n]*","",intro)
    return intro.strip(),limits,parsed

def normalize_legacy_samples(items):
    # Historical author packages may store sample inputs/outputs as typed JSON.
    # Never guess their meaning; serialize them faithfully for display.
    result=[]
    for item in items or []:
        if not isinstance(item,dict) or "input" not in item or "output" not in item:
            continue
        def show(value):
            return value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,separators=(",",":"))
        result.append({"input":show(item["input"]),"output":show(item["output"]),
                       "explanation":show(item.get("explanation",""))})
    return result


def format_statement(raw,package=None):
    package=package or {}
    if "statement_display" in package:
        return validate(package["statement_display"])
    blocks=sections(raw)
    if not any(k in blocks for k in ("input_format","output_format","constraints","examples")):
        intro,limits,samples=inline_legacy(raw)
        return validate({"description":intro or raw,"constraints":limits,
                         "samples":normalize_legacy_samples(package.get("samples")) or samples})
    samples=examples(blocks.get("examples","")) or normalize_legacy_samples(package.get("samples"))
    return validate({"description":blocks.get("description") or raw,
                     "input_format":blocks.get("input_format",""),
                     "output_format":blocks.get("output_format",""),
                     "constraints":constraints(blocks.get("constraints","")),
                     "samples":samples,"notes":blocks.get("notes","")})

def public_markdown(view):
    """Produce a safe text-only public statement from the sanitized fields.

    Historical source statements and archived explanations are never modified.
    The public API uses this when a versioned publication has an explicit
    structured display, preventing old Note/sample-explanation prose from
    leaking through the raw statement fallback.
    """
    parts=[view["description"]]
    for name,key in (("Input Format","input_format"),("Output Format","output_format")):
        if view.get(key):
            parts.extend(("## "+name,view[key]))
    if view.get("constraints"):
        parts.extend(("## Constraints","\n".join("- "+x for x in view["constraints"])))
    for i,sample in enumerate(view.get("samples",[]),1):
        parts.append("## Sample "+str(i))
        for name in ("input","output"):
            raw=sample[name]
            fence="`"*max(3,1+max([len(m.group(0)) for m in re.finditer(r"`+",raw)] or [0]))
            parts.append(name.title()+":\n"+fence+"text\n"+raw+"\n"+fence)
    return "\n\n".join(parts)
