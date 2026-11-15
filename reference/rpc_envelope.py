"""Transport-neutral RPC envelope v1 reference (host-only, no Atto guest)."""
import json
import re

MAX_FRAME_BYTES = 65536
MAX_CALL_ID = (1 << 53) - 1
_METHOD = re.compile(r"[a-z][a-z0-9_]{0,63}\\Z")


class EnvelopeError(ValueError):
    pass


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnvelopeError("duplicate JSON object key")
        result[key] = value
    return result


def _bad_constant(value):
    raise EnvelopeError("nonfinite JSON constant forbidden")


def validate_envelope(message):
    if type(message) is not dict or message.get("v") != 1 or type(message.get("v")) is not int:
        raise EnvelopeError("v must be integer 1")
    kind = message.get("kind")
    common = {"v", "kind"}
    if kind in ("request", "notification"):
        keys = common | {"method", "params"} | ({"id"} if kind == "request" else set())
        method = message.get("method")
        if type(method) is not str or not _METHOD.fullmatch(method):
            raise EnvelopeError("method must be a bounded snake_case name")
        if type(message.get("params")) not in (list, dict):
            raise EnvelopeError("params must be an object or array")
    elif kind in ("response", "error"):
        keys = common | {"id"} | ({"result"} if kind == "response" else {"error"})
        if kind == "error":
            err = message.get("error")
            if type(err) is not dict or set(err) != {"code", "message"}:
                raise EnvelopeError("error requires code and message")
            if type(err["code"]) is not str or not _METHOD.fullmatch(err["code"]):
                raise EnvelopeError("error code must be bounded snake_case")
            if type(err["message"]) is not str or len(err["message"]) > 1024:
                raise EnvelopeError("error message exceeds 1024 characters")
    else:
        raise EnvelopeError("unknown envelope kind")
    if set(message) != keys:
        raise EnvelopeError("missing or unexpected envelope fields")
    if kind != "notification":
        value = message["id"]
        if type(value) is not int or not (0 <= value <= MAX_CALL_ID):
            raise EnvelopeError("id must be a nonnegative JS-safe integer")
    return message


def decode_envelope(frame):
    if type(frame) is not bytes or len(frame) > MAX_FRAME_BYTES:
        raise EnvelopeError("frame must be at most 65536 bytes")
    try:
        message = json.loads(frame.decode("utf-8"), object_pairs_hook=_no_duplicates,
                             parse_constant=_bad_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise EnvelopeError("invalid UTF-8 JSON envelope") from exc
    return validate_envelope(message)


def encode_envelope(message):
    validate_envelope(message)
    try:
        encoded = json.dumps(message, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise EnvelopeError("unsupported JSON payload") from exc
    if len(encoded) > MAX_FRAME_BYTES:
        raise EnvelopeError("encoded envelope exceeds 65536 bytes")
    return encoded
