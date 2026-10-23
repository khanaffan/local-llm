# Sourced by bin/*-local wrappers: `. _common.sh <profile>`.
# Refuses root, makes sure the profile's model is resident, and sets:
#   ROOT P ALIAS CTX LOCAL_LLM_API_KEY(exported) LOCAL_LLM_HOST LOCAL_LLM_V1 MAX_OUT MAX_PROMPT
# Remote mode: LOCAL_LLM_REMOTE=user@host [LOCAL_LLM_REMOTE_DIR=local-llm] uses the server there.
[ "$(id -u)" -ne 0 ] || { echo "error: do not run with sudo; it creates root-owned files in your home directory" >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P="${1:-fast}"
. "$ROOT/profile.sh"
resolve_profile "$P"
PROFILE_REL="${PROFILE_DIR#"$ROOT"/}"

LOCAL_LLM_HOST=http://127.0.0.1:8080

# shellcheck disable=SC1090
. "$PROFILE_DIR/$P.env"
# shellcheck disable=SC1090
[ ! -f "$PROFILE_DIR/$P.local.env" ] || . "$PROFILE_DIR/$P.local.env"

if [ "${LOCAL_LLM_PRESTARTED:-0}" = 1 ]; then
  # Sandboxed benchmark agents cannot inspect/manage another process with ps.
  # Require the exact model to be healthy; never start or switch a server in this mode.
  LOCAL_LLM_API_KEY="$(cat "$ROOT/run/api-key")"; export LOCAL_LLM_API_KEY
  curl -fs -m 5 -H "Authorization: Bearer $LOCAL_LLM_API_KEY" "$LOCAL_LLM_HOST/v1/models" \
    | python3 -c 'import json,sys; sys.exit(0 if sys.argv[1] in [m["id"] for m in json.load(sys.stdin)["data"]] else 1)' "$ALIAS" \
    || { echo "error: prestarted server is not serving '$ALIAS'" >&2; exit 1; }
elif [ -n "${LOCAL_LLM_REMOTE:-}" ]; then
  # Remote mode: the server runs on LOCAL_LLM_REMOTE (user@host) and is reached through an
  # SSH tunnel on 127.0.0.1:8080. One ssh call switches the model there and returns the
  # server's API key and its CTX (which may differ from ours via its *.local.env).
  RDIR="${LOCAL_LLM_REMOTE_DIR:-local-llm}"
  OUT="$(ssh "$LOCAL_LLM_REMOTE" "export PATH=/opt/homebrew/bin:/usr/local/bin:\$PATH && cd $(printf %q "$RDIR") && {
      ./llm.sh status 2>/dev/null | grep -x 'running: $P pid=[0-9]*' >/dev/null || ./llm.sh switch $P >&2
    } && . $PROFILE_REL/$P.env && { [ ! -f $PROFILE_REL/$P.local.env ] || . $PROFILE_REL/$P.local.env; } &&
    echo \"CTX=\$CTX\" && echo \"KEY=\$(cat run/api-key)\"")" \
    || { echo "error: remote switch to '$P' on $LOCAL_LLM_REMOTE failed" >&2; exit 1; }
  CTX="$(printf '%s\n' "$OUT" | sed -n 's/^CTX=//p' | tail -1)"
  LOCAL_LLM_API_KEY="$(printf '%s\n' "$OUT" | sed -n 's/^KEY=//p' | tail -1)"
  [ -n "$CTX" ] && [ -n "$LOCAL_LLM_API_KEY" ] || { echo "error: unexpected reply from $LOCAL_LLM_REMOTE" >&2; exit 1; }
  export LOCAL_LLM_API_KEY
  # open the tunnel in the background unless something already listens on 8080
  if ! nc -z 127.0.0.1 8080 2>/dev/null; then
    ssh -f -N -o ExitOnForwardFailure=yes -L 8080:127.0.0.1:8080 "$LOCAL_LLM_REMOTE" \
      || { echo "error: could not open SSH tunnel to $LOCAL_LLM_REMOTE" >&2; exit 1; }
  fi
  curl -fs -m 5 -H "Authorization: Bearer $LOCAL_LLM_API_KEY" "$LOCAL_LLM_HOST/v1/models" | grep -q "\"$ALIAS\"" \
    || { echo "error: $LOCAL_LLM_HOST is not serving '$ALIAS' (port 8080 taken by something else?)" >&2; exit 1; }
else
  # switch unless this exact profile is already running (also restarts a crashed server);
  # grep without -q so `status` never gets SIGPIPE, which pipefail would treat as "not running"
  "$ROOT/llm.sh" status 2>/dev/null | grep -x "running: $P pid=[0-9]*" >/dev/null || "$ROOT/llm.sh" switch "$P"
  LOCAL_LLM_API_KEY="$(cat "$ROOT/run/api-key")"; export LOCAL_LLM_API_KEY
fi
LOCAL_LLM_V1="$LOCAL_LLM_HOST/v1"
LOCAL_LLM_RUN_DIR="${LOCAL_LLM_RUN_DIR:-$ROOT/run}"
# prompt + output must fit the server context (CTX)
MAX_OUT=8192
MAX_PROMPT=$((CTX - MAX_OUT))
