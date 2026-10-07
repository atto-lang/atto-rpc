#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
expected_ref="$(tr -d '[:space:]' < "$repo_root/SOURCE_REF")"
if [[ ! "$expected_ref" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_REF must contain a full lowercase Git commit SHA" >&2
  exit 65
fi
compiler="${ORESLANG_COMPILER:-oreslang-compiler}"

if ! command -v "$compiler" >/dev/null 2>&1 && [[ ! -x "$compiler" ]]; then
  echo "oreslang compiler not found: $compiler" >&2
  echo "set ORESLANG_COMPILER to an executable built from SOURCE_REF=$expected_ref" >&2
  exit 69
fi

if [[ -n "${ORESLANG_SOURCE_DIR:-}" ]]; then
  if [[ "$(git -C "$ORESLANG_SOURCE_DIR" rev-parse --show-toplevel)" != "$(cd "$ORESLANG_SOURCE_DIR" && pwd -P)" ]]; then
    echo "ORESLANG_SOURCE_DIR must be its own Git checkout" >&2
    exit 65
  fi
  if [[ -n "$(git -C "$ORESLANG_SOURCE_DIR" status --porcelain --untracked-files=all)" ]]; then
    echo "compiler source checkout must be clean" >&2
    exit 65
  fi
  actual_ref="$(git -C "$ORESLANG_SOURCE_DIR" rev-parse HEAD)"
  if [[ "$actual_ref" != "$expected_ref" ]]; then
    echo "ORESLANG_SOURCE_DIR is at $actual_ref" >&2
    echo "expected SOURCE_REF $expected_ref" >&2
    exit 65
  fi
fi

entry="$repo_root/tests/rpc_semantics.ores"
actual="$(mktemp "${TMPDIR:-/tmp}/oreslang-rpc.XXXXXX")"
trap 'rm -f "$actual"' EXIT

cd "$repo_root"

"$compiler" --check --platform=server "$entry"
"$compiler" --platform=server "$entry" > "$actual"

diff -u "$repo_root/tests/expected.txt" "$actual"
echo "rpc semantics: PASS"
