#!/usr/bin/env python3
"""For each compiled expr probe, isolate the p-code of the test statement
(source line 20) and print it as raw words with the mode byte broken out, so
the operand encoding can be read off a single table."""
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from ud import container, disasm  # noqa: E402


def stmt_words(c, line):
    """words of the code stream for the statement marked with `line`."""
    ins = disasm.disassemble(c.code)
    out = []
    grab = False
    for x in ins:
        if x.mnem == "STMT":
            grab = (x.args and x.args[0] == line)
            continue
        if grab:
            if x.mnem in ("HALT",) and not out:
                continue
            out.append(x)
            if x.mnem in ("HALT", "STMT"):
                break
    return out


def raw_between(c, line):
    """raw byte slice from the STMT(line) marker to the next STMT/2+ zero run."""
    code = c.code
    p = 0
    start = None
    while p + 4 <= len(code):
        if code[p] == 0xCB and code[p + 1] == 0x00:
            ln = struct.unpack_from("<H", code, p + 2)[0]
            if start is not None:
                return code[start:p]
            if ln == line:
                start = p + 4
        p += 2
    return code[start:] if start is not None else b""


def show(name, c):
    blob = raw_between(c, 20)
    consts = [f"{i}:{k.render()}" for i, k in enumerate(c.consts) if k.kind in (4, 5)]
    words = [struct.unpack_from("<H", blob, i)[0] for i in range(0, len(blob) - 1, 2)]
    # trim trailing zeros
    while words and words[-1] == 0:
        words.pop()
    hexw = " ".join(f"{w:04x}" for w in words)
    # heuristic split: opcode, mode, then rest
    op = words[0] if words else 0
    mode = words[1] if len(words) > 1 else 0
    print(f"{name:14} op={op:04x} mode={mode:04x} "
          f"[lo={mode & 0xFF:02x} hi={mode >> 8:02x}]  {hexw}")
    if consts:
        print(f"{'':14} consts {consts}")


def main():
    for fn in sorted(glob.glob(os.path.join(HERE, "obj", "_*"))):
        name = os.path.basename(fn)[1:]
        try:
            c = container.load(open(fn, "rb").read())
        except Exception as e:  # noqa: BLE001
            print(f"{name:14} ERR {e}")
            continue
        show(name, c)


if __name__ == "__main__":
    main()
