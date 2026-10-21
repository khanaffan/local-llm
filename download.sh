#!/usr/bin/env bash
# Usage: ./download.sh <fast|lite|medium|coder|smart|long|max> [...]     (long uses the medium weights)
# Downloads pinned weights from manifest.json into models/: resumable, retries, checks free
# disk first, verifies the full SHA-256, and skips files that are already verified.
# Set HF_TOKEN if Hugging Face rate-limits you.
set -euo pipefail
[ "$(id -u)" -ne 0 ] || { echo "error: do not run with sudo" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")" && pwd)"
[ $# -gt 0 ] || { echo "usage: $0 <fast|lite|medium|coder|smart|long|max> [...]" >&2; exit 1; }
mkdir -p "$ROOT/models"

gb() { awk -v b="$1" 'BEGIN{printf "%.1f GB", b/1e9}'; }
size() { stat -f %z "$1" 2>/dev/null || echo 0; }

PROFILES="fast|lite|medium|coder|smart|long|max"
for P in "$@"; do
  INFO=$(python3 - "$ROOT/manifest.json" "$P" "$PROFILES" <<'PY'
import json, sys
m = json.load(open(sys.argv[1])); p = sys.argv[2]
if not isinstance(m.get(p), dict): sys.exit(f"error: unknown profile '{p}' ({sys.argv[3]})")
e = m[m[p].get("same_file_as", p)]
for f in e["files"]: print(e["repo"], e["revision"], f["file"], f["sha256"], f["bytes"])
PY
  ) || exit 1
  # Check total remaining disk need for every shard of this profile up front.
  NEED=0
  while read -r REPO REV FILE SHA BYTES; do
    NEED=$((NEED + BYTES - $(size "$ROOT/models/$(basename "$FILE")")))
  done <<<"$INFO"
  FREE=$(( $(df -k "$ROOT/models" | awk 'NR==2{print $4}') * 1024 ))
  if [ $((NEED + 5000000000)) -gt "$FREE" ]; then
    echo "error: $P needs $(gb $NEED) more disk (+5 GB headroom); only $(gb $FREE) free" >&2; exit 1
  fi

  while read -r REPO REV FILE SHA BYTES; do
    NAME=$(basename "$FILE"); OUT="$ROOT/models/$NAME"; STAMP="$ROOT/models/.$NAME.sha256"
    if [ "$(size "$OUT")" = "$BYTES" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$SHA" ]; then
      echo "$P: $NAME already downloaded and verified"; continue
    fi
    rm -f "$STAMP"
    HAVE=$(size "$OUT")
    if [ "$HAVE" -gt "$BYTES" ]; then echo "$P: removing oversized partial file"; rm -f "$OUT"; HAVE=0; fi
    if [ "$HAVE" -lt "$BYTES" ]; then
      echo "$P: downloading $NAME ($(gb $BYTES), $(gb $HAVE) already present) from huggingface.co/$REPO"
      PROGRESS=(-sS); [ -t 2 ] && PROGRESS=(--progress-bar)
      AUTH=(); [ -n "${HF_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $HF_TOKEN")
      # Fresh curl processes resume from the latest size; internal retries can roll back progress.
      for ATTEMPT in $(seq 1 11); do
        if curl -L --fail -C - "${PROGRESS[@]}" ${AUTH[@]+"${AUTH[@]}"} \
          -o "$OUT" "https://huggingface.co/$REPO/resolve/$REV/$FILE" </dev/null; then
          break
        else
          STATUS=$?
          [ "$ATTEMPT" -lt 11 ] || { echo "error: $P download failed after $ATTEMPT attempts; re-run to resume" >&2; exit "$STATUS"; }
          echo "$P: download attempt $ATTEMPT failed (curl $STATUS); resuming from $(gb "$(size "$OUT")") in 5 seconds" >&2
          sleep 5
        fi
      done
    fi
    echo "$P: verifying SHA-256 of $NAME (about a minute per 50 GB)..."
    GOT=$(shasum -a 256 "$OUT" | cut -d' ' -f1)
    if [ "$GOT" != "$SHA" ]; then
      mv "$OUT" "$OUT.bad"
      echo "error: $P checksum mismatch (moved to models/$NAME.bad); re-run to download again" >&2; exit 1
    fi
    echo "$SHA" >"$STAMP"
    echo "$P: OK ($NAME)"
  done <<<"$INFO"
done
