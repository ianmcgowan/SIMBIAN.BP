#!/usr/bin/env python3
"""Dump the disassembly of the test-region (from the first non-preamble STMT)
for every object in a dir. Used by the *lab harnesses."""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ud import container, disasm
for fn in sorted(glob.glob(os.path.join(sys.argv[1], "_*"))):
    name = os.path.basename(fn)[1:]
    c = container.load(open(fn, "rb").read())
    ins = disasm.disassemble(c.code)
    print(f"\n=== {name}  consts={[ (i,k.render()) for i,k in enumerate(c.consts) if k.kind in (4,5)][:12]}")
    started = False
    for x in ins:
        if x.mnem == "STMT" and x.args and x.args[0] >= 10:
            started = True
        if not started:
            continue
        tgt = ""
        if x.mnem in ("GOTO","GOSUB","BRF","LOOP.BACK","FOR.NEXT","AND.SC","OR.SC") and x.args:
            tgt = f"  -> w{x.args[0]} (0x{x.args[0]*2:x})"
        print(f"  {x.word:4}/{x.off:04x}  {x.mnem:12} {x.args}{tgt}")
