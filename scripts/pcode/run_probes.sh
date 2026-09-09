#!/usr/bin/env bash
# Compile every probe in probes/ twice (with and without -Z2) via the PCLAB
# directory file, and collect the objects under objects/{z2,noz2}/.
#
#   ./run_probes.sh
#   ACCOUNT=/usr/ud83/demo LAB=PCLAB ./run_probes.sh
set -euo pipefail

ACCOUNT="${ACCOUNT:-/usr/ud83/demo}"
LAB="${LAB:-PCLAB}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROBES="$HERE/probes"
LABDIR="$HERE/lab"
OUT="${OUT:-$HERE/objects}"

command -v udt >/dev/null || { echo "udt not on PATH" >&2; exit 1; }
[ -d "$LABDIR" ] || { echo "no lab dir $LABDIR" >&2; exit 1; }

mkdir -p "$OUT/z2" "$OUT/noz2"
rm -f "$LABDIR"/* "$OUT"/z2/* "$OUT"/noz2/*

n=0
for src in "$PROBES"/*; do
  name="$(basename "$src")"
  cp "$src" "$LABDIR/$name"
  for mode in z2 noz2; do
    [ "$mode" = z2 ] && flag="-Z2" || flag=""
    rm -f "$LABDIR/_$name"
    ( cd "$ACCOUNT" && echo "BASIC $LAB $name $flag" | udt ) \
        >"$OUT/$mode/$name.log" 2>&1
    if [ -f "$LABDIR/_$name" ]; then
      cp "$LABDIR/_$name" "$OUT/$mode/_$name"
    else
      echo "FAIL $name $mode" ; grep -iE 'error|warn' "$OUT/$mode/$name.log" | head -3
    fi
  done
  n=$((n+1))
done
# tidy the lab dir so the working tree stays clean
rm -f "$LABDIR"/*
echo "compiled $n probes -> $OUT/{z2,noz2}"
ls "$OUT/z2" | grep -c '^_' | xargs echo "z2 objects:"
