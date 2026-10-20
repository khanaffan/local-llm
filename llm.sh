#!/usr/bin/env bash
# Usage: llm.sh {start|stop|status|switch} [fast|medium|coder|smart|long]
# One resident model at a time, bound to 127.0.0.1:8080.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST=127.0.0.1
PORT=8080
PIDFILE="$ROOT/run/server.pid"
PROFILEFILE="$ROOT/run/server.profile"
LOG="$ROOT/run/server.log"
KEYFILE="$ROOT/run/api-key"

die() { echo "error: $*" >&2; exit 1; }

# Running as root creates root-owned files/processes that break normal-user runs.
[ "$(id -u)" -ne 0 ] || die "do not run with sudo; nothing here needs root"

owned_pid() {
  [ -f "$PIDFILE" ] || return 1
  local pid; pid=$(cat "$PIDFILE")
  # verify the pid is still our llama-server, not a recycled pid
  ps -p "$pid" -o command= 2>/dev/null | grep -q "llama-server.*--port $PORT" || return 1
  echo "$pid"
}

health() {
  curl -fs -m 2 -H "Authorization: Bearer $(cat "$KEYFILE")" "http://$HOST:$PORT/v1/models" 2>/dev/null
}

load_profile() {
  local p="$1"
  [[ "$p" =~ ^(fast|medium|coder|smart|long)$ ]] || die "unknown profile '$p' (fast|medium|coder|smart|long)"
  # shellcheck disable=SC1090
  . "$ROOT/profiles/$p.env"
  # optional per-machine overrides (git-ignored), e.g. CTX=65536 on smaller Macs
  # shellcheck disable=SC1090
  [ ! -f "$ROOT/profiles/$p.local.env" ] || . "$ROOT/profiles/$p.local.env"
  [ -f "$ROOT/$MODEL_FILE" ] || die "model file missing: $MODEL_FILE (run: ./download.sh $p)"
}

cmd_stop() {
  local pid
  if pid=$(owned_pid); then
    kill "$pid"
    for _ in $(seq 1 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -0 "$pid" 2>/dev/null && die "process $pid did not exit"
    echo "stopped $pid"
  else
    echo "not running"
  fi
  rm -f "$PIDFILE" "$PROFILEFILE"
}

cmd_start() {
  local p="${1:-}"; [ -n "$p" ] || die "profile required"
  owned_pid >/dev/null && die "already running ($(cat "$PROFILEFILE")); use switch"
  lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1 && die "port $PORT is in use by another process"
  load_profile "$p"
  [ -f "$KEYFILE" ] || die "missing $KEYFILE"
  mkdir -p "$ROOT/run"
  local tmpl=(); [ -z "${CHAT_TEMPLATE:-}" ] || tmpl=(--chat-template-file "$ROOT/$CHAT_TEMPLATE")
  # shellcheck disable=SC2086
  nohup llama-server ${tmpl[@]+"${tmpl[@]}"} \
    -m "$ROOT/$MODEL_FILE" --alias "$ALIAS" \
    --host $HOST --port $PORT --api-key-file "$KEYFILE" \
    -c "$CTX" -np 1 -ngl all --flash-attn on --jinja \
    --cache-type-k "$CACHE_K" --cache-type-v "$CACHE_V" \
    --no-webui $EXTRA_ARGS >"$LOG" 2>&1 &
  echo $! >"$PIDFILE"
  echo "$p" >"$PROFILEFILE"
  for _ in $(seq 1 300); do
    kill -0 "$(cat "$PIDFILE")" 2>/dev/null || { tail -20 "$LOG" >&2; rm -f "$PIDFILE" "$PROFILEFILE"; die "server exited during load"; }
    if health | grep -q "\"$ALIAS\""; then echo "ready: $p ($ALIAS) at http://$HOST:$PORT/v1"; return 0; fi
    sleep 2
  done
  tail -20 "$LOG" >&2; die "timed out waiting for readiness"
}

cmd_status() {
  local pid
  if pid=$(owned_pid); then
    echo "running: $(cat "$PROFILEFILE") pid=$pid"
    health | python3 -c "import sys,json;print('models:',[m['id'] for m in json.load(sys.stdin)['data']])" || echo "not healthy"
  else
    echo "stopped"
  fi
}

cmd_switch() {
  local p="${1:-}"; [ -n "$p" ] || die "profile required"
  load_profile "$p"
  if owned_pid >/dev/null; then
    # refuse while a request is being processed
    if curl -fs -m 2 -H "Authorization: Bearer $(cat "$KEYFILE")" "http://$HOST:$PORT/slots" | grep -q '"is_processing": *true'; then
      die "active request in progress; retry when idle"
    fi
    cmd_stop
  fi
  cmd_start "$p"
}

case "${1:-}" in
  start) cmd_start "${2:-}" ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  switch) cmd_switch "${2:-}" ;;
  *) die "usage: $0 {start|stop|status|switch} [fast|medium|coder|smart|long]" ;;
esac
