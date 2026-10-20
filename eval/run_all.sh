#!/usr/bin/env bash
# Runs HumanEval for each tier in turn (switches the resident model). Must not run as root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ "$(id -u)" -ne 0 ] || { echo "do not run as root" >&2; exit 1; }
PROFILES=("$@")
[ "${#PROFILES[@]}" -gt 0 ] || PROFILES=(fast medium coder smart)
for p in "${PROFILES[@]}"; do
  "$ROOT/llm.sh" switch "$p"
  python3 "$ROOT/eval/run_humaneval.py" "$p"
done
echo "ALL DONE"
