#!/usr/bin/env python3
"""Decompile a UniData UniBasic P-code object to approximate UniBasic source.

    ./pdec.py path/to/_PROGRAM
    ./pdec.py _PROGRAM --src PROGRAM     # show the real source beside it

Output columns:  <source-line> | <recovered statement>
Lines beginning `!!` are statements the decoder could not lift; the raw
mnemonics are shown so nothing is silently dropped.
"""
import argparse, sys, difflib
from ud import container, disasm, decompile

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("obj")
    ap.add_argument("--src", help="matching source, printed side by side")
    ap.add_argument("--stats", action="store_true", help="recovery stats only")
    a = ap.parse_args()
    c = container.load(open(a.obj, "rb").read())
    container.register_opcodes(disasm.known_opcodes())
    c = container.load(open(a.obj, "rb").read())
    text = decompile.decompile_text(c)

    if a.stats:
        tot = text.count("\n") + 1
        bad = sum(1 for l in text.splitlines() if "| !!" in l or "|   !!" in l)
        print(f"{a.obj}: {tot} lines, {tot-bad} recovered, {bad} unlifted "
              f"({100*(tot-bad)//max(tot,1)}%)")
        return
    print(text)
    if a.src:
        print("\n=== real source ===")
        for i, ln in enumerate(open(a.src, errors="replace").read().splitlines(), 1):
            if ln.strip() and not ln.strip().startswith("*"):
                print(f"{i:>4} | {ln}")

if __name__ == "__main__":
    sys.exit(main())
