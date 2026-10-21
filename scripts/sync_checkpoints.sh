#!/usr/bin/env bash
# Copy checkpoint files between machines and verify them with sha256.
#
# Usage:
#   bash scripts/sync_checkpoints.sh SRC_DIR DST_DIR FILE [FILE ...]
#
# SRC_DIR and DST_DIR are local paths or [user@]host:path. FILEs are names inside SRC_DIR.
# If both ends are remote (e.g. an H100 server and an RTX server that cannot see each other),
# run this on a machine that reaches both; files go through a temporary local staging dir.
#
# Example:
#   bash scripts/sync_checkpoints.sh <H100_HOST>:<RUN_DIR> <RTX_HOST>:<DATA_DIR>/ckpt \
#        model_step_000250.pt config.yaml
#
# DRY_RUN=1 shows what rsync would copy; nothing is copied or verified.
set -euo pipefail

[ $# -ge 3 ] || { sed -n '2,16p' "$0"; exit 1; }
SRC=$1; DST=$2; shift 2
FILES=("$@")
for f in "${FILES[@]}"; do
  [[ "$f" != */* ]] || { echo "FILE must be a name inside SRC_DIR, not a path: $f" >&2; exit 1; }
done

is_remote() { [[ "$1" == *:* ]]; }
path_of() { if is_remote "$1"; then echo "${1#*:}"; else echo "$1"; fi; }
q() { printf '%q' "$1"; }

# sha256sum on Linux, shasum on macOS; same output format
SHA='sha() { if command -v sha256sum >/dev/null; then sha256sum "$@"; else shasum -a 256 "$@"; fi; };'

# run a bash snippet locally or on the host of the given location (stdin is passed through)
run_at() {
  local loc=$1; shift
  if is_remote "$loc"; then ssh -o BatchMode=yes "${loc%%:*}" bash -c "$(q "$*")"; else bash -c "$*"; fi
}

RSYNC=(rsync -a --partial)
rsync --info=progress2 --version >/dev/null 2>&1 && RSYNC+=(--info=progress2)
DRY=${DRY_RUN:-0}
[ "$DRY" = 1 ] && RSYNC+=(--dry-run -v)

src_path=$(path_of "$SRC"); dst_path=$(path_of "$DST")
names=""; for f in "${FILES[@]}"; do names+=" $(q "$f")"; done

echo "== sha256 at source ($SRC)"
SUMS=$(run_at "$SRC" "$SHA cd $(q "$src_path") && sha$names")
echo "$SUMS"

src_list=(); for f in "${FILES[@]}"; do src_list+=("$SRC/$f"); done
[ "$DRY" = 1 ] || run_at "$DST" "mkdir -p $(q "$dst_path")"

if is_remote "$SRC" && is_remote "$DST"; then
  STAGE=$(mktemp -d "${TMPDIR:-/tmp}/ckpt_sync.XXXXXX")
  trap 'rm -rf "$STAGE"' EXIT
  echo "== $SRC -> local staging $STAGE"
  "${RSYNC[@]}" "${src_list[@]}" "$STAGE/"
  [ "$DRY" = 1 ] && { echo "(dry run: stopped after the first hop)"; exit 0; }
  echo "== staging -> $DST"
  "${RSYNC[@]}" "${FILES[@]/#/$STAGE/}" "$DST/"
else
  echo "== $SRC -> $DST"
  "${RSYNC[@]}" "${src_list[@]}" "$DST/"
  [ "$DRY" = 1 ] && { echo "(dry run: nothing copied)"; exit 0; }
fi

echo "== verify at destination ($DST)"
printf '%s\n' "$SUMS" | run_at "$DST" "$SHA cd $(q "$dst_path") && cat > SHA256SUMS.sync && sha -c SHA256SUMS.sync"
echo "OK: ${#FILES[@]} file(s) verified; checksums saved as SHA256SUMS.sync in $DST"
