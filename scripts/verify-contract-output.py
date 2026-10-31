#!/usr/bin/env python3
"""Validate *actual exported artifacts* of an Oreslang RPC guest execution.

Does not generate schemas and cannot substitute for native guest execution.
Requires external protoc and tsp to validate their languages.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ID = r"[A-Za-z_][A-Za-z0-9_]*"
WIRE_TYPE = rf"(?:{ID}|array<{ID}>)"
FIELD = re.compile(rf"  ([1-9][0-9]*) ({ID}): ({WIRE_TYPE}) (required|optional)$")
MESSAGE = re.compile(rf"message ({ID}) \{{$")
RPC = re.compile(rf"rpc ({ID})\.({ID})\(({ID})\) -> ({ID})(?: streaming=(server|client|bidi))?$")


class ContractError(ValueError):
    pass


def no_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def validate_json_schema(path):
    obj = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_pairs)
    if not isinstance(obj, dict) or obj.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ContractError("JSON Schema 2020-12 declaration missing")
    if not isinstance(obj.get("$id"), str) or not obj["$id"].startswith("https://"):
        raise ContractError("JSON Schema HTTPS ID missing")
    definitions = obj.get("$defs")
    if not isinstance(definitions, dict):
        raise ContractError("JSON Schema $defs must be an object")
    for name, model in definitions.items():
        if not re.fullmatch(ID, name) or not isinstance(model, dict):
            raise ContractError("bad JSON Schema message definition")
        props = model.get("properties")
        required = model.get("required")
        if model.get("type") != "object" or not isinstance(props, dict) or not isinstance(required, list):
            raise ContractError(f"invalid object contract: {name}")
        if len(required) != len(set(required)) or any(x not in props for x in required):
            raise ContractError(f"invalid required properties: {name}")
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ContractError("jsonschema dependency required for independent 2020-12 validation") from exc
    Draft202012Validator.check_schema(obj)
    return obj


def validate_msgpack_def(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if len(lines) < 2 or lines[0] != "mpackdef 1" or lines[1] != "encoding map-int-keys":
        raise ContractError("invalid MessagePack contract header")
    messages, in_message, field_nums, field_names, rpcs = set(), None, set(), set(), set()
    for line in lines[2:]:
        if not line:
            continue
        if in_message is not None:
            if line == "}":
                in_message = None
                continue
            field = FIELD.fullmatch(line)
            if field is None:
                raise ContractError(f"bad MessagePack field: {line!r}")
            num, name, type_name, mode = field.groups()
            n = int(num)
            if n > 536870911 or 19000 <= n <= 19999 or n in field_nums or name in field_names:
                raise ContractError("MessagePack field number/name violates protobuf identity")
            if type_name.startswith("array<") and mode == "required":
                raise ContractError("required+repeated field cannot round-trip")
            field_nums.add(n)
            field_names.add(name)
            continue
        message = MESSAGE.fullmatch(line)
        if message:
            in_message = message.group(1)
            if in_message in messages:
                raise ContractError("duplicate MessagePack message")
            messages.add(in_message)
            field_nums, field_names = set(), set()
            continue
        rpc = RPC.fullmatch(line)
        if rpc:
            key = (rpc.group(1), rpc.group(2))
            if key in rpcs:
                raise ContractError("duplicate MessagePack RPC")
            rpcs.add(key)
            continue
        raise ContractError(f"unexpected MessagePack contract line: {line!r}")
    if in_message is not None:
        raise ContractError("unterminated MessagePack message")
    return len(messages), len(rpcs)


def require_external(name):
    tool = shutil.which(name)
    if tool is None:
        raise ContractError(f"required independent validator {name!r} not installed")
    return tool


def validate_external(proto, typespec):
    # Run each validator on the exact artifact; no synthetic source substitution.
    protoc = require_external("protoc")
    tsp = require_external("tsp")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="ores-rpc-protoc-") as tmp:
        subprocess.run([protoc, f"--proto_path={Path(proto).parent.resolve()}", f"--descriptor_set_out={Path(tmp) / 'contract.pb'}", "--include_imports", Path(proto).name], check=True)
    subprocess.run([tsp, "compile", str(Path(typespec).resolve()), "--no-emit"], check=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json-schema", type=Path, required=True)
    p.add_argument("--protobuf", type=Path, required=True)
    p.add_argument("--messagepack", type=Path, required=True)
    p.add_argument("--typespec", type=Path, required=True)
    args = p.parse_args(argv)
    validate_json_schema(args.json_schema)
    validate_msgpack_def(args.messagepack)
    validate_external(args.protobuf, args.typespec)
    print("RPC external artifact verification: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ContractError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"RPC external artifact verification: FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
