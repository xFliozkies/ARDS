"""Bounded, unambiguous JSON at certificate and package trust boundaries.

Canonical encoding v1 retains the encoding of existing valid artifacts. It
rejects duplicate members, non-finite numbers, cycles and non-JSON Python types.
Limits are process-independent input/work limits, not mathematical rejection.
"""
import json
import math
import hashlib
from pathlib import Path

MAX_BYTES = 16 * 1024 * 1024
MAX_NODES = 200000
MAX_DEPTH = 256


class ResourceLimitError(ValueError):
    pass


def validate(value, *, max_nodes=MAX_NODES, max_bytes=MAX_BYTES, max_depth=MAX_DEPTH):
    stack = [(value, 0, False)]
    active = set()
    count = size = 0
    while stack:
        node, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(node))
            continue
        count += 1
        if count > max_nodes or depth > max_depth:
            raise ResourceLimitError("JSON node/depth budget exceeded")
        if type(node) in (dict, list):
            if id(node) in active:
                raise ValueError("cyclic JSON value")
            active.add(id(node))
            stack.append((node, depth, True))
            size += 2
            if len(node) > max_nodes - count:
                raise ResourceLimitError("JSON container budget exceeded")
            if type(node) is dict:
                for k, v in node.items():
                    if type(k) is not str:
                        raise ValueError("JSON object keys must be strings")
                    stack.extend(((k, depth + 1, False), (v, depth + 1, False)))
            else:
                stack.extend((v, depth + 1, False) for v in node)
        elif type(node) is str:
            if len(node) > max_bytes:
                raise ResourceLimitError("JSON string budget exceeded")
            size += len(node.encode("utf8")) + 2
        elif node is None or type(node) in (bool, int, float):
            if type(node) is float and not math.isfinite(node):
                raise ValueError("non-finite numbers are not JSON")
            size += len(str(node))
        else:
            raise ValueError("unsupported JSON value type")
        if size > max_bytes:
            raise ResourceLimitError("JSON byte budget exceeded")
    return count


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member: " + key[:80])
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonstandard JSON number: " + value)


def loads(blob, **limits):
    maximum = limits.get("max_bytes", MAX_BYTES)
    if len(blob) > maximum:
        raise ResourceLimitError("JSON file byte budget exceeded")
    if isinstance(blob, str) and len(blob.encode("utf8")) > maximum:
        raise ResourceLimitError("JSON file byte budget exceeded")
    try:
        value = json.loads(blob, object_pairs_hook=_object, parse_constant=_constant)
    except RecursionError as exc:
        raise ResourceLimitError("JSON parser depth budget exceeded") from exc
    validate(value, **limits)
    return value


def load(path, **limits):
    return load_with_digest(path, **limits)[0]


def load_with_digest(path, **limits):
    maximum = limits.get("max_bytes", MAX_BYTES)
    with Path(path).open("rb") as stream:
        blob = stream.read(maximum + 1)
    return loads(blob, **limits), hashlib.sha256(blob).hexdigest()


def canonical(value):
    validate(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)
