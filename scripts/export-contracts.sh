#!/usr/bin/env bash
# Export four complete native Oreslang RPC generated contracts byte-for-byte.
# Requires a clean compiler checkout pinned by SOURCE_REF. This creates a NEW
# output directory only after all four entries have compiled and completed.
set -euo pipefail
umask 077
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ $# -ne 1 ]]; then
  echo "usage: bash scripts/export-contracts.sh NEW_OUTPUT_DIRECTORY" >&2
  exit 64
fi
output="$1"
if [[ -e "$output" || -L "$output" ]]; then
  echo "RPC export destination already exists: $output" >&2
  exit 65
fi
parent="$(dirname "$output")"
leaf="$(basename "$output")"
if [[ ! -d "$parent" || -L "$parent" || "$leaf" = . || "$leaf" = .. ]]; then
  echo "RPC export needs an existing, non-symlink destination parent" >&2
  exit 65
fi
parent="$(cd "$parent" && pwd -P)"
output="$parent/$leaf"
compiler="${ORESLANG_COMPILER:-oreslang-compiler}"
# test.sh verifies the declared source SHA, clean checkout, check-before-run,
# and guest transcript. The compiler binary must be independently attested
# to have been built from that exact checkout; these guards alone cannot prove it.
bash "$repo_root/scripts/test.sh" >/dev/null
stage="$(mktemp -d "$parent/.rpc-export.XXXXXXXX")"
cleanup() { if [[ -n "${stage:-}" && -d "$stage" ]]; then rm -rf -- "$stage"; fi; }
trap cleanup EXIT
cd "$repo_root"
for entry in json_schema protobuf messagepack typespec; do
  source="tests/export_${entry}.ores"
  case "$entry" in
    json_schema) output_name=contracts.schema.json ;;
    protobuf) output_name=contracts.proto ;;
    messagepack) output_name=contracts.mpackdef ;;
    typespec) output_name=contracts.tsp ;;
  esac
  "$compiler" --check --platform=server "$repo_root/$source"
  "$compiler" --platform=server "$repo_root/$source" > "$stage/$output_name"
  if [[ ! -s "$stage/$output_name" ]]; then
    echo "RPC guest emitted an empty $output_name" >&2
    exit 1
  fi
  # This caps publishable output; guest runtime memory is a separate gate.
  size_bytes="$(wc -c < "$stage/$output_name")"
  if (( size_bytes > 1048576 )); then
    echo "RPC guest artifact exceeds 1 MiB limit: $output_name" >&2
    exit 1
  fi
done
if [[ -e "$output" || -L "$output" ]]; then
  echo "RPC export destination appeared during generation: $output" >&2
  exit 65
fi
mv -- "$stage" "$output"
stage=""
echo "RPC contract artifacts exported to $output"
