#!/usr/bin/env bash
# Usage: eval/agents_smoke.sh [profile] [agent...]   (agents: copilot opencode claude codex qwen aider)
# Gives each agent the same small bug-fix task in a scratch dir, then checks the result independently.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
P="${1:-fast}"; shift || true
AGENTS=("${@:-copilot opencode claude codex qwen aider}"); AGENTS=(${AGENTS[*]})
TASK="calc.py has a bug: test_calc.py fails. Fix calc.py only (do not edit the test), then run: python3 test_calc.py"
for a in "${AGENTS[@]}"; do
  d=$(mktemp -d /tmp/agent-smoke-$a.XXXX)
  printf 'def mean(xs):\n    return sum(xs) / (len(xs) + 1)\n' >"$d/calc.py"
  printf 'from calc import mean\nassert mean([2, 4, 6]) == 4\nassert mean([5]) == 5\nprint("PASS")\n' >"$d/test_calc.py"
  cp "$d/test_calc.py" "$d/.orig_test"
  cd "$d"
  t=$(date +%s)
  case $a in
    copilot)  "$ROOT/bin/copilot-local" "$P" -p "$TASK" --allow-all-tools --no-ask-user ;;
    opencode) "$ROOT/bin/opencode-local" "$P" run "$TASK" ;;
    claude)   "$ROOT/bin/claude-local" "$P" -p "$TASK" --dangerously-skip-permissions ;;
    codex)    "$ROOT/bin/codex-local" "$P" exec --skip-git-repo-check -s workspace-write "$TASK" ;;
    qwen)     "$ROOT/bin/qwen-local" "$P" --yolo "$TASK" ;;
    aider)    "$ROOT/bin/aider-local" "$P" --yes-always --no-git --no-pretty --message "$TASK" calc.py ;;
  esac >"$d/agent.log" 2>&1
  rc=$?; secs=$(( $(date +%s) - t ))
  if python3 test_calc.py >/dev/null 2>&1 && cmp -s test_calc.py .orig_test; then r=PASS; else r=FAIL; fi
  echo "$a [$P]: $r (agent exit $rc, ${secs}s) log: $d/agent.log"
  cd "$ROOT"
done
