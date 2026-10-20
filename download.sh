#!/usr/bin/env bash
# Usage: ./download.sh <fast|medium|smart|long> [...]     (long uses the medium weights)
# Downloads pinned weights from manifest.json into models/: resumable, retries, checks free
# disk first, verifies the full SHA-256, and skips files that are already verified.
# Set HF_TOKEN if Hugging Face rate-limits you.
set -euo pipefail
[ "$(id -u)" -ne 0 ] || { echo "error: do not run with sudo" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")" && pwd)"
[ $# -gt 0 ] || { echo "usage: $0 <fast|medium|smart|long> [...]" >&2; exit 1; }
mkdir -p "$ROOT/models"

gb() { awk -v b="$1" 'BEGIN{printf "%.1f GB", b/1e9}'; }
size() { stat -f %z "$1" 2>/dev/null || echo 0; }

for P in "$@"; do
  INFO=$(python3 - "$ROOT/manifest.json" "$P" <<'PY'
import json, sys
m = json.load(open(sys.argv[1])); p = sys.argv[2]
if not isinstance(m.get(p), dict): sys.exit(f"error: unknown profile '{p}' (fast|medium|smart|long)")
e = m[m[p].get("same_file_as", p)]
print(e["repo"], e["revision"], e["file"], e["sha256"], e["bytes"])
PY
  ) || exit 1
  read -r REPO REV FILE SHA BYTES <<<"$INFO"
  OUT="$ROOT/models/$FILE"; STAMP="$ROOT/models/.$FILE.sha256"

  if [ "$(size "$OUT")" = "$BYTES" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$SHA" ]; then
    echo "$P: $FILE already downloaded and verified"; continue
  fi
  rm -f "$STAMP"
  HAVE=$(size "$OUT")
  if [ "$HAVE" -gt "$BYTES" ]; then echo "$P: removing oversized partial file"; rm -f "$OUT"; HAVE=0; fi
  if [ "$HAVE" -lt "$BYTES" ]; then
    NEED=$((BYTES - HAVE)); FREE=$(( $(df -k "$ROOT/models" | awk 'NR==2{print $4}') * 1024 ))
    if [ $((NEED + 5000000000)) -gt "$FREE" ]; then
      echo "error: $P needs $(gb $NEED) more disk (+5 GB headroom); only $(gb $FREE) free" >&2; exit 1
    fi
    echo "$P: downloading $FILE ($(gb $BYTES), $(gb $HAVE) already present) from huggingface.co/$REPO"
    PROGRESS=(-sS); [ -t 2 ] && PROGRESS=(--progress-bar)
    AUTH=(); [ -n "${HF_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $HF_TOKEN")
    curl -L --fail --retry 10 --retry-delay 5 --retry-all-errors -C - "${PROGRESS[@]}" ${AUTH[@]+"${AUTH[@]}"} \
      -o "$OUT" "https://huggingface.co/$REPO/resolve/$REV/$FILE"
  fi
  echo "$P: verifying SHA-256 (about a minute per 50 GB)..."
  GOT=$(shasum -a 256 "$OUT" | cut -d' ' -f1)
  if [ "$GOT" != "$SHA" ]; then
    mv "$OUT" "$OUT.bad"
    echo "error: $P checksum mismatch (moved to models/$FILE.bad); re-run to download again" >&2; exit 1
  fi
  echo "$SHA" >"$STAMP"
  echo "$P: OK ($FILE)"
done
