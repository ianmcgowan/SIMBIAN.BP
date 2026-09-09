#!/usr/bin/env bash
# compile every iolab/src program (noz2 is enough; we only want the code) and
# dump the p-code for the test line (line 20) via analyse.py
set -euo pipefail
ACCOUNT="${ACCOUNT:-/usr/ud83/demo}"
HERE="$(cd "$(dirname "$0")" && pwd)"
LAB="$(cd "$HERE/../lab" && pwd)"
OUT="$HERE/obj"
mkdir -p "$OUT"
rm -f "$OUT"/* "$LAB"/*
for src in "$HERE"/src/*; do
  name="$(basename "$src")"
  cp "$src" "$LAB/$name"
  ( cd "$ACCOUNT" && echo "BASIC PCLAB $name -Z2" | udt ) >/dev/null 2>&1 || true
  if [ -f "$LAB/_$name" ]; then
    cp "$LAB/_$name" "$OUT/_$name"
  else
    echo "FAIL $name"
  fi
done
rm -f "$LAB"/*
echo "compiled -> $OUT"
python3 "$HERE/../pdis_seg.py" "$OUT"
