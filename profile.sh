# Shared profile resolver; callers set ROOT before sourcing this file.
resolve_profile() {
  local name="$1"
  case "$name" in
    fast|lite|medium|coder|smart|long|max)
      PROFILE_DIR="$ROOT/profiles"
      PROFILE_MANIFEST="$ROOT/manifest.json"
      ;;
    cand-*)
      [[ "$name" =~ ^cand-[a-z0-9]+(-[a-z0-9]+)*$ ]] || {
        echo "error: invalid candidate name '$name'" >&2; return 1;
      }
      PROFILE_DIR="$ROOT/candidates/profiles"
      PROFILE_MANIFEST="$ROOT/candidates/manifest.json"
      ;;
    *) echo "error: unknown profile '$name'" >&2; return 1 ;;
  esac
  [ -f "$PROFILE_DIR/$name.env" ] || {
    echo "error: profile file missing: $PROFILE_DIR/$name.env" >&2; return 1;
  }
}
