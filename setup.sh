#!/usr/bin/env bash
# One-step installer for a fresh clone (Apple Silicon macOS).
#
#   ./setup.sh                      interactive: checks your Mac, recommends models, asks
#   ./setup.sh --recommended        download every model that fits your RAM, no questions
#   ./setup.sh --models fast,medium download exactly these (fast|lite|medium|coder|smart|long|max|all|none)
#   options: --no-agents  skip installing coding agents into tools/
#            --no-test    skip the final test chat
#
# Safe to re-run: finished steps and verified downloads are skipped. Never run with sudo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
gb()   { awk -v b="$1" 'BEGIN{printf "%.0f GB", b/1e9}'; }
prof() { ( . "profiles/$1.env"; eval "echo \"\$$2\"" ); }   # prof <profile> <VAR>

MODELS=""; MODE=ask; AGENTS=1; TEST=1
while [ $# -gt 0 ]; do
  case "$1" in
    --recommended) MODE=recommended ;;
    --models) shift; MODE=list; MODELS="$(echo "${1:-}" | tr ',' ' ')" ;;
    --models=*) MODE=list; MODELS="$(echo "${1#*=}" | tr ',' ' ')" ;;
    --no-agents) AGENTS=0 ;;
    --no-test) TEST=0 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
  shift
done
[ "$(id -u)" -ne 0 ] || die "do not run with sudo; nothing here needs root"

# ---------------------------------------------------------------- 1. this machine
say "Checking this Mac"
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || die "requires Apple Silicon macOS (Metal)"
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
FREE=$(( $(df -k "$ROOT" | awk 'NR==2{print $4}') * 1024 ))
echo "  $(sysctl -n machdep.cpu.brand_string), ${RAM_GB} GB RAM, $(gb $FREE) free disk, macOS $(sw_vers -productVersion)"

# ---------------------------------------------------------------- 2. prerequisites
say "Installing prerequisites (Homebrew packages)"
command -v brew >/dev/null || die "Homebrew is required. Install it from https://brew.sh, then re-run ./setup.sh"
python3 -c 'import sys; assert sys.version_info >= (3, 8)' 2>/dev/null \
  || die "python3 not found; run: xcode-select --install"
need=""
command -v llama-server >/dev/null || need="$need llama.cpp"
if [ "$AGENTS" = 1 ]; then
  command -v npm >/dev/null || need="$need node"
  command -v uv >/dev/null || need="$need uv"
fi
if [ -n "$need" ]; then echo "  brew install$need"; brew install $need; else echo "  all present"; fi
echo "  llama.cpp $(llama-server --version 2>&1 | grep -m1 -o 'version: .*' || echo '?')"

# ---------------------------------------------------------------- 3. local API key
mkdir -p run
if [ ! -s run/api-key ]; then (umask 077; openssl rand -hex 32 >run/api-key); echo "  created run/api-key"; fi
chmod 600 run/api-key

# ---------------------------------------------------------------- 4. coding agents
if [ "$AGENTS" = 1 ]; then
  say "Installing coding agents into tools/ (pinned versions; nothing global)"
  npm ci --prefix tools --no-fund --no-audit --loglevel=error
  if [ ! -x tools/bin/aider ]; then
    UV_TOOL_DIR="$ROOT/tools/uv" UV_TOOL_BIN_DIR="$ROOT/tools/bin" \
      uv tool install --quiet --python 3.12 aider-chat==0.86.2
  fi
  echo "  OpenCode, Claude Code, Codex, Qwen Code, Aider installed"
  command -v copilot >/dev/null \
    || echo "  GitHub Copilot CLI not found (optional, for bin/copilot-local): brew install copilot-cli"
fi

# ---------------------------------------------------------------- 5. choose models
say "Models"
RECOMMENDED=""
printf '  %-7s %-9s %-8s %s\n' PROFILE DOWNLOAD MIN_RAM DESCRIPTION
for p in fast lite medium coder smart long max; do
  bytes=$(python3 -c "import json;m=json.load(open('manifest.json'));print(sum(f['bytes'] for f in m[m['$p'].get('same_file_as','$p')]['files']))")
  min=$(prof $p MIN_RAM_GB)
  dl="$(gb $bytes)"; [ $p = long ] && dl="(=medium)"
  fit="ok"; [ "$RAM_GB" -ge "$min" ] || fit="too big for ${RAM_GB} GB"
  [ "$fit" = ok ] && [ $p != long ] && [ $p != max ] && RECOMMENDED="$RECOMMENDED $p"
  printf '  %-7s %-9s %-8s %s [%s]\n' $p "$dl" "${min} GB" "$(prof $p DESC)" "$fit"
done
RECOMMENDED="${RECOMMENDED# }"
# lite is the fallback coding model for Macs too small for medium; skip it when medium fits.
case " $RECOMMENDED " in *" medium "*) RECOMMENDED="$(echo " $RECOMMENDED " | sed 's/ lite / /;s/^ //;s/ $//')" ;; esac
[ -n "$RECOMMENDED" ] || warn "this Mac has less RAM than any profile needs; fast may still run with a lower CTX (profiles/fast.local.env)"

case "$MODE" in
  recommended) MODELS="$RECOMMENDED" ;;
  ask)
    if [ -t 0 ]; then
      printf '\n  Which models to download? [%s] (names, "all", or "none"): ' "${RECOMMENDED:-fast}"
      read -r MODELS; MODELS="$(echo "${MODELS:-${RECOMMENDED:-fast}}" | tr ',' ' ')"
    else
      MODELS="$RECOMMENDED"
    fi ;;
esac
[ "$MODELS" = all ] && MODELS="fast lite medium coder smart"
[ "$MODELS" = none ] && MODELS=""
for p in $MODELS; do
  case $p in fast|lite|medium|coder|smart|long|max) ;; *) die "unknown model '$p' (fast|lite|medium|coder|smart|long|max|all|none)";; esac
  [ "$p" != max ] || warn "max is experimental: on 128 GB, raise the GPU limit before loading (see README); excluded from all/recommended"
  [ "$RAM_GB" -ge "$(prof $p MIN_RAM_GB)" ] || warn "$p is recommended for >= $(prof $p MIN_RAM_GB) GB RAM; it may swap or fail to load"
done

# ---------------------------------------------------------------- 6. download
if [ -n "$MODELS" ]; then
  say "Downloading: $MODELS  (resumable: if interrupted, just re-run)"
  ./download.sh $MODELS
else
  echo "  skipping downloads (later: ./download.sh <profile>)"
fi

# ---------------------------------------------------------------- 7. test
FIRST=""
for p in fast lite medium coder smart long max; do
  f=$(prof $p MODEL_FILE); [ -f "$f" ] && [ -f "models/.$(basename "$f").sha256" ] && { FIRST=$p; break; }
done
if [ "$TEST" = 1 ] && [ -n "$FIRST" ]; then
  say "Testing: loading '$FIRST' and sending one chat request"
  ./llm.sh switch "$FIRST"
  REPLY=$(curl -fsS -m 300 http://127.0.0.1:8080/v1/chat/completions \
    -H "Authorization: Bearer $(cat run/api-key)" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$(prof $FIRST ALIAS)\",\"max_tokens\":300,\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: local LLM ready\"}]}" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["choices"][0]["message"]["content"].strip())') \
    || { ./llm.sh stop >/dev/null; die "test request failed; see run/server.log"; }
  echo "  model replied: $REPLY"
  ./llm.sh stop >/dev/null
fi

# ---------------------------------------------------------------- done
say "Done"
cat <<TXT
  Start an agent (it loads the model automatically):
    bin/copilot-local ${FIRST:-fast}      bin/claude-local ${FIRST:-fast}    bin/codex-local ${FIRST:-fast}
    bin/opencode-local ${FIRST:-fast}     bin/qwen-local ${FIRST:-fast}      bin/aider-local ${FIRST:-fast}
  Or run the server for any OpenAI/Anthropic-compatible client:
    ./llm.sh switch ${FIRST:-fast}   ->  http://127.0.0.1:8080/v1   key: run/api-key
  More models later: ./download.sh medium smart
TXT
