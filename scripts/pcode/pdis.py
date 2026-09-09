#!/usr/bin/env python3
"""Disassemble a UniData UniBasic P-code object.

    ./pdis.py path/to/_PROGRAM              annotated listing
    ./pdis.py _PROGRAM --raw                also dump header + pool + const table
    ./pdis.py _PROGRAM --src PROGRAM        interleave the real source line text

The listing groups instructions under their STMT (source-line) marker and, when
the object was built with -Z2, prints label names at their offsets and the
first-seen source line of every variable.
"""

from __future__ import annotations

import argparse
import sys

from ud import container, disasm


def load(path):
    c = container.load(open(path, "rb").read())
    container.register_opcodes(disasm.known_opcodes())
    # reload so the label-vs-var heuristic can use the opcode set
    return container.load(open(path, "rb").read())


def dump_header(c: container.Container):
    print("== container ==")
    kind = "SUBROUTINE" if c.is_subroutine else "PROGRAM"
    print(f"  kind        {kind}" + (f" (argc={c.argc})" if c.is_subroutine else ""))
    print(f"  -Z2 debug   {'yes' if c.has_debug else 'no'}")
    print(f"  pool_len    {c.pool_len}")
    print(f"  n_const     {c.n_const}")
    print(f"  code_len    {c.code_len}")
    print(f"  dbg_len     {c.dbg_len}")
    print(f"  code @file   0x{c.code_file_off:x}")


def dump_pool(c: container.Container):
    print("\n== constant table ==")
    for k in c.consts:
        if k.kind == 4:
            v = k.s
            show = v if len(v) <= 60 else v[:57] + "..."
            print(f"  [{k.index:4}] len={k.length:<4} @pool+0x{k.pool_off:<5x} {show!r}")
        else:
            print(f"  [{k.index:4}] kind={k.kind} aux={k.aux}")


def const_repr(c: container.Container, idx: int) -> str:
    if 0 <= idx < len(c.consts) and c.consts[idx].kind == 4:
        return repr(c.consts[idx].s)
    return f"const#{idx}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("obj")
    ap.add_argument("--raw", action="store_true", help="also show header/pool/const table")
    ap.add_argument("--src", help="matching source file, to interleave line text")
    ap.add_argument("--start", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--end", type=lambda s: int(s, 0), default=None)
    args = ap.parse_args()

    c = load(args.obj)
    dump_header(c)
    if args.raw:
        dump_pool(c)

    srclines = None
    if args.src:
        srclines = open(args.src, errors="replace").read().splitlines()

    print("\n== code ==")
    insns = disasm.disassemble(c.code)
    cur_line = None
    for ins in insns:
        if args.start and ins.off < args.start:
            continue
        if args.end and ins.off >= args.end:
            break
        if ins.off in c.labels:
            print(f"  {c.labels[ins.off]}:")
        if ins.opcode == disasm.STMT:
            cur_line = ins.args[0] if ins.args else None
            txt = ""
            if srclines and cur_line and 1 <= cur_line <= len(srclines):
                txt = "   ; " + srclines[cur_line - 1].strip()
            print(f"\n  .line {cur_line}{txt}")
            continue
        extra = ""
        if ins.mnem in ("PUSH.C", "PUSH.C2", "CALL.NAME") and ins.args:
            extra = "   ; " + const_repr(c, ins.args[0])
        elif ins.mnem == "BINOP" and ins.args:
            ch = ins.args[0]
            extra = "   ; " + disasm.BINOP_CHARS.get(ch, f"chr({ch})")
        elif ins.mnem in ("GOTO", "GOSUB", "BRF", "LOOP.BACK", "FOR.NEXT", "AND.SC") and ins.args:
            tgt = ins.args[0] * 2
            lbl = c.labels.get(tgt, "")
            extra = f"   ; -> 0x{tgt:x} word {ins.args[0]}" + (f" ({lbl})" if lbl else "")
        print(f"    {ins.word:5}/0x{ins.off:04x}  {ins.fmt()}{extra}")

    if c.has_debug:
        print(f"\n== -Z2 labels ({len(c.labels)}) ==")
        for off in sorted(c.labels):
            print(f"  0x{off:04x} word {off // 2:<6} {c.labels[off]}")
        print(f"\n== -Z2 variables ({len(c.var_lines)}), first-seen line ==")
        for name in sorted(c.var_lines):
            print(f"  {name:<28} {c.var_lines[name]}")


if __name__ == "__main__":
    sys.exit(main())
