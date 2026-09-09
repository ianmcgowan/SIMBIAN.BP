#!/usr/bin/env bash
# Compile one UniBasic source with $BASICTYPE "P" and immediately round-trip it
# through the disassembler and decompiler.
#
#   ./try.sh myprog.bp            # a file
#   ./try.sh                      # reads source from stdin
#   ./try.sh myprog.bp --dis      # also show the disassembly
set -euo pipefail
ACCOUNT="${ACCOUNT:-/usr/ud83/demo}"
HERE="$(cd "$(dirname "$0")" && pwd)"
LAB="$HERE/lab"
NAME="TRY_$$"
src="${1:-/dev/stdin}"
[ "${1:-}" = "--dis" ] && { src=/dev/stdin; DIS=1; }
[ "${2:-}" = "--dis" ] && DIS=1

# ensure the compiler directive is present
tmp="$(cat "$src")"
case "$tmp" in
  *'$BASICTYPE'*) : ;;
  *) tmp='  $BASICTYPE "P"'$'\n'"$tmp" ;;
esac
printf '%s\n' "$tmp" > "$LAB/$NAME"

( cd "$ACCOUNT" && echo "BASIC PCLAB $NAME -Z2" | udt ) | grep -iE 'compil|error|warn' || true
echo "──────────── decompiled ────────────"
python3 "$HERE/pdec.py" "$LAB/_$NAME"
if [ "${DIS:-}" = 1 ]; then
  echo "──────────── disassembly ────────────"
  python3 "$HERE/pdis.py" "$LAB/_$NAME" --src "$LAB/$NAME"
fi
rm -f "$LAB/$NAME" "$LAB/_$NAME"
