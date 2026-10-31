#!/usr/bin/env python3
"""Run one Oreslang guest with a live output/time budget and emit exact UTF-8 bytes.

The existing bounded_process.run_bounded kills the child on output overflow
or timeout. This wrapper never creates the destination on child failure.
"""
import argparse
from pathlib import Path
import subprocess
import sys

from bounded_process import run_bounded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--max-total-bytes", type=int, default=1048576)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.timeout_seconds <= 0 or args.max_total_bytes <= 0:
        parser.error("command and positive budgets are required")
    if args.output.exists() or args.output.is_symlink():
        parser.error("output path must not exist")

    try:
        result = run_bounded(command, timeout=args.timeout_seconds,
                             max_bytes=args.max_total_bytes)
        if result.stderr:
            sys.stderr.write(result.stderr)
        if result.returncode != 0:
            raise RuntimeError(f"guest exited with status {result.returncode}")
        # Roundtripping valid UTF-8 does not modify any emitted byte. Invalid
        # UTF-8 is rejected, not silently decoded with replacement characters.
        data = result.stdout.encode("utf-8")
        if not data and not args.allow_empty:
            raise RuntimeError("guest emitted an empty artifact")
        with args.output.open("xb") as handle:
            handle.write(data)
    except (OSError, RuntimeError, subprocess.TimeoutExpired, UnicodeError) as exc:
        print(f"RPC guest emission: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
