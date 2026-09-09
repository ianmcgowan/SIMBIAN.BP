"""Linear-sweep disassembler for the UniData p-code stream.

The stream is a sequence of 16-bit little-endian words.  The first word of an
instruction is the opcode; most opcodes take a fixed number of 16-bit operand
words.  Operand counts below were recovered from differential compilation of
minimal-pair probes (scripts/pcode/probes/, see ../FORMAT.md for the worked
examples).  Anything not in the table is decoded as opcode + one operand and
tagged '?', and the sweep resynchronises on the next 0x00CB statement marker.

Jump operands (GOTO/GOSUB/branch/loop) are word offsets from the start of the
code segment: multiply by 2 for a byte offset.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

STMT = 0x00CB          # statement marker; operand = source line number
HALT = 0x0000

# opcode -> (mnemonic, operand_word_count, kind)
# kind is a hint for the decompiler: 'stmt','push','store','expr','call',
# 'jump','cmp','binop','func','ret','sub','misc'
OPCODES: dict[int, tuple[str, int, str]] = {
    0x00CB: ("STMT",        1, "stmt"),      # operand = source line number
    0x0000: ("HALT",        0, "misc"),
    0x0004: ("FOR.INIT",    3, "misc"),
    0x000B: ("RETURN",      1, "ret"),
    0x0010: ("PUSH.C",      1, "push"),     # push constant #arg
    0x0011: ("PUSH.C2",     1, "push"),     # push constant (string/concat context)
    0x0016: ("NEG",         1, "unop"),
    0x001A: ("CMP.EQ",      0, "cmp"),
    0x001B: ("CMP.NE",      0, "cmp"),
    0x001C: ("CMP.LE",      0, "cmp"),
    0x001D: ("CMP.LT",      0, "cmp"),
    0x001E: ("CMP.GE",      0, "cmp"),
    0x001F: ("CMP.GT",      0, "cmp"),
    0x0021: ("EXPR.END",    0, "misc"),
    0x002C: ("PRINT",       1, "io"),       # arg = item count
    0x0037: ("FN.LEN",      0, "func"),
    0x0042: ("FN.OCONV",    0, "func"),
    0x0066: ("FN.OCONV2",   0, "func"),
    0x0071: ("INPUT",       0, "io"),
    0x008F: ("OPEN",        1, "io"),
    0x0091: ("READ",        1, "io"),
    0x00A9: ("CALL.NAME",   1, "call"),     # arg = const # of subroutine name
    0x00B7: ("CALL.GO",     1, "call"),
    0x00BE: ("SUB.PROLOG",  3, "sub"),
    0x00E2: ("FN.FIELD",    0, "func"),
    0x00E4: ("BINOP",       1, "binop"),    # arg = operator char code
    0x0115: ("STOP",        1, "misc"),
    0x0151: ("CMP.VV",     -1, "expr"),     # var <cmp> var : mode + greedy operands
    0x0152: ("EXPR",       -1, "expr"),     # (mode, dst, greedy operand words)
    0x0155: ("ARG.BIND",    2, "sub"),
    0x0159: ("ASSIGN",      3, "store"),    # (mode, dst-var, src)
    0x015A: ("FOR.PREP",    2, "misc"),
    0x015B: ("BRF",         1, "jump"),     # branch if false -> word arg
    0x015C: ("GOSUB",       1, "jump"),
    0x015D: ("GOTO",        1, "jump"),
    0x0163: ("LOOP.BACK",   1, "jump"),
    0x0167: ("FOR.NEXT",    1, "jump"),
    0x01C6: ("AND.SC",      1, "jump"),     # short-circuit AND
    0x01C8: ("AND.MERGE",   1, "misc"),
    0x01CB: ("CALL.PREP",   1, "call"),
}

# operator char codes carried by BINOP (0x00E4)
BINOP_CHARS = {
    0x2B: "+", 0x2D: "-", 0x2A: "*", 0x2F: "/", 0x3A: ":",
    0x3C: "<", 0x3E: ">", 0x3D: "=", 0x23: "#",
    0x5E: "^",
}

CMP_TEXT = {
    0x1A: "=", 0x1B: "#", 0x1C: "<=", 0x1D: "<", 0x1E: ">=", 0x1F: ">",
}


@dataclass
class Insn:
    off: int            # byte offset in code segment
    word: int           # first word offset
    opcode: int
    mnem: str
    args: list[int]
    size: int           # total bytes consumed
    known: bool

    def fmt(self) -> str:
        a = " ".join(str(x) for x in self.args)
        tag = "" if self.known else "  ?"
        return f"{self.mnem:<11} {a}{tag}"


# bytes that, as a low byte with hi==0, terminate a greedy operand run
# (operator opcodes, EXPR.END, statement marker, RETURN, NEG, PRINT, func ids)
_EXPR_STOP = {0xE4, 0x37, 0x42, 0xE2, 0x66, 0x71, 0x8F, 0x91, 0x21, 0xCB,
              0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x16, 0x0B, 0x2C, 0x10, 0x11}


def _read_word(code: bytes, off: int) -> int:
    return struct.unpack_from("<H", code, off)[0]


def disassemble(code: bytes) -> list[Insn]:
    out: list[Insn] = []
    off = 0
    n = len(code)
    while off + 2 <= n:
        opcode = _read_word(code, off)
        spec = OPCODES.get(opcode)
        if spec is None:
            mnem, nargs, known = f"OP_{opcode:04X}", 1, False
        else:
            mnem, nargs, _kind = spec
            known = True
        args = []
        p = off + 2
        if nargs == -1:
            # greedy: mode word, then consume words until the next byte begins a
            # known operator / terminator / control opcode.
            if p + 2 <= n:
                args.append(_read_word(code, p)); p += 2      # mode
            zrun = 0
            while p + 2 <= n:
                lo, hi = code[p], code[p + 1]
                if hi == 0x00 and lo in _EXPR_STOP:
                    break
                if hi == 0x01 and lo in (0x5B, 0x5C, 0x5D, 0x51, 0x52, 0x59):
                    break
                w = _read_word(code, p)
                zrun = zrun + 1 if w == 0 else 0
                if zrun >= 3:            # 3+ zero words = inter-statement padding
                    args = args[:-2]
                    p -= 4
                    break
                args.append(w); p += 2
                if len(args) > 12:
                    break
        else:
            for _ in range(nargs):
                if p + 2 > n:
                    break
                args.append(_read_word(code, p))
                p += 2
        size = p - off
        out.append(Insn(off, off // 2, opcode, mnem, args, size, known))
        off = p
    return out


def collapse_halts(insns: list[Insn]) -> list[Insn]:
    """Fold consecutive HALT words into a single pseudo-instruction so listings
    and the decompiler are not swamped by inter-statement zero padding."""
    out: list[Insn] = []
    i = 0
    while i < len(insns):
        if insns[i].opcode == HALT:
            j = i
            while j < len(insns) and insns[j].opcode == HALT:
                j += 1
            span = insns[j - 1].off + insns[j - 1].size - insns[i].off
            out.append(Insn(insns[i].off, insns[i].word, HALT, "PAD",
                            [j - i], span, True))
            i = j
        else:
            out.append(insns[i])
            i += 1
    return out


def kind_of(opcode: int) -> str:
    spec = OPCODES.get(opcode)
    return spec[2] if spec else "?"


# expose the opcode set for the container's label sanity check
def known_opcodes() -> set[int]:
    return set(OPCODES)
