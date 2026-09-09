#!/usr/bin/env bash
# Compile every probe twice -- with and without -Z2 -- and collect the objects.
#
# The two builds of the same source are the single most useful pair in the whole
# corpus: whatever -Z2 adds IS the debug/line-number section, cleanly separated
# from the p-code itself.
#
#   ./run_probes.sh                       # uses the defaults below
#   ACCOUNT=/usr/ud83/demo ./run_probes.sh
set -euo pipefail

ACCOUNT="${ACCOUNT:-/usr/ud83/demo}"
BPFILE="${BPFILE:-SIMBIAN.BP}"
PROBES="$(cd "$(dirname "$0")/probes" && pwd)"
OUT="${OUT:-$(cd "$(dirname "$0")" && pwd)/objects}"

command -v udt >/dev/null || { echo "udt not on PATH" >&2; exit 1; }
[ -d "$ACCOUNT/$BPFILE" ] || { echo "no $ACCOUNT/$BPFILE" >&2; exit 1; }

mkdir -p "$OUT/z2" "$OUT/noz2"

for src in "$PROBES"/P*; do
  name="$(basename "$src")"
  cp "$src" "$ACCOUNT/$BPFILE/$name"

  for mode in z2 noz2; do
    [ "$mode" = z2 ] && flag="-Z2" || flag=""
    rm -f "$ACCOUNT/$BPFILE/_$name"
    ( cd "$ACCOUNT" && echo "BASIC $BPFILE $name $flag" | udt ) >"$OUT/$mode/$name.log" 2>&1
    if [ -f "$ACCOUNT/$BPFILE/_$name" ]; then
      cp "$ACCOUNT/$BPFILE/_$name" "$OUT/$mode/_$name"
      printf '%-22s %-5s %8s bytes\n' "$name" "$mode" \
        "$(wc -c <"$OUT/$mode/_$name")"
    else
      printf '%-22s %-5s FAILED (see %s)\n' "$name" "$mode" "$OUT/$mode/$name.log"
    fi
  done
done

echo
echo "objects in $OUT"
echo "next: pcode_diff.py $OUT/z2/_P00_EMPTY $OUT/z2/_P01_PRINT_STR4"
