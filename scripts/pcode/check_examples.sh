#!/usr/bin/env bash
# Compile every examples/*.bp (u-mode).  With --stub, retry undefined-label
# failures after appending  <label>:\n  RETURN  stubs (written to a temp copy).
# Writes examples.compiles.txt / examples.fails.txt.
set -euo pipefail
ACCOUNT="${ACCOUNT:-/usr/ud83/demo}"
HERE="$(cd "$(dirname "$0")" && pwd)"
LAB="$HERE/lab"; STUB="${1:-}"
mkdir -p "$LAB"; rm -f "$LAB"/*
ok=0; fail=0; : > "$HERE/examples.compiles.txt"; : > "$HERE/examples.fails.txt"

try() { (cd "$ACCOUNT" && echo "BASIC PCLAB $1" | udt) 2>&1; }

for f in "$HERE"/examples/*.bp; do
  n="$(basename "$f" .bp)"; cp "$f" "$LAB/$n"
  out="$(try "$n")"
  if grep -q 'compilation finished' <<<"$out" && ! grep -q 'error:' <<<"$out"; then
    ok=$((ok+1)); echo "$n" >> "$HERE/examples.compiles.txt"; rm -f "$LAB/$n" "$LAB/_$n"; continue
  fi
  if [ "$STUB" = "--stub" ] && grep -q 'have not been defined' <<<"$out"; then
    labs="$(grep -A20 'have not been defined' <<<"$out" | sed -n '2,20p' \
            | grep -oE '^[A-Za-z][A-Za-z0-9._]*' || true)"
    { cat "$f"; echo; for L in $labs; do echo "$L:"; echo "  RETURN"; done; } > "$LAB/$n"
    out="$(try "$n")"
    if grep -q 'compilation finished' <<<"$out" && ! grep -q 'error:' <<<"$out"; then
      ok=$((ok+1)); echo "$n [stubbed]" >> "$HERE/examples.compiles.txt"
      rm -f "$LAB/$n" "$LAB/_$n"; continue
    fi
  fi
  fail=$((fail+1)); echo "$n" >> "$HERE/examples.fails.txt"; rm -f "$LAB/$n" "$LAB/_$n"
done
echo "$ok compile, $fail fail"
