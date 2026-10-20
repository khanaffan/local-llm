# Sourced by bin/*-local wrappers: `. _common.sh <profile>`.
# Refuses root, makes sure the profile's model is resident, and sets:
#   ROOT P ALIAS CTX LOCAL_LLM_API_KEY(exported) LOCAL_LLM_HOST LOCAL_LLM_V1 MAX_OUT MAX_PROMPT
[ "$(id -u)" -ne 0 ] || { echo "error: do not run with sudo; it creates root-owned files in your home directory" >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P="${1:-fast}"
case "$P" in fast|medium|coder|smart|long) ;; *) echo "unknown profile: $P (fast|medium|coder|smart|long)" >&2; exit 1 ;; esac

# switch unless this exact profile is already running (also restarts a crashed server)
"$ROOT/llm.sh" status 2>/dev/null | grep -qx "running: $P pid=[0-9]*" || "$ROOT/llm.sh" switch "$P"
# shellcheck disable=SC1090
. "$ROOT/profiles/$P.env"
# shellcheck disable=SC1090
[ ! -f "$ROOT/profiles/$P.local.env" ] || . "$ROOT/profiles/$P.local.env"

LOCAL_LLM_API_KEY="$(cat "$ROOT/run/api-key")"; export LOCAL_LLM_API_KEY
LOCAL_LLM_HOST=http://127.0.0.1:8080
LOCAL_LLM_V1="$LOCAL_LLM_HOST/v1"
# prompt + output must fit the server context (CTX)
MAX_OUT=8192
MAX_PROMPT=$((CTX - MAX_OUT))
