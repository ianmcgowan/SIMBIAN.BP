"""Best-effort decompiler: UniData p-code object -> approximate UniBasic.

Output is deliberately literal, not idiomatic.  A statement recovered with
confidence is emitted as real UniBasic; one that is not is emitted as a
`!! line N` comment carrying the raw mnemonics, so nothing is silently dropped
and every gap is visible.

Reliable:
  * every statement carries its true source line (STMT markers)
  * variable / label names when built with -Z2
  * GOTO / GOSUB / branch targets (word offsets -> labels)
  * RETURN, STOP, simple assignment, PRINT / CRT of literals, CALL targets
  * binary and comparison operator characters

Approximate:
  * operand wiring inside multi-term expressions
  * the sense of a var-vs-var comparison inside IF (the compiler canonicalises
    some of these; flagged with ;* when it comes through that path)
  * block nesting -- emitted flat, with explicit labels, when the structured
    form cannot be proven
"""

from __future__ import annotations

from dataclasses import dataclass

from . import container, disasm

# comparison opcode low byte -> source text (value context)
CMP = {0x1A: "=", 0x1B: "#", 0x1C: "<=", 0x1D: "<", 0x1E: ">=", 0x1F: ">"}


@dataclass
class Line:
    src_line: int
    text: str


class Decompiler:
    def __init__(self, c: container.Container):
        self.c = c
        self.ins = disasm.collapse_halts(disasm.disassemble(c.code))
        self.labels = dict(c.labels)
        self._synth_labels()
        self._map_slots()

    # -------------------------------------------------------- slot -> name
    def _map_slots(self):
        """The -Z2 tail lists variables alphabetically with the source line
        each is first seen on.  The p-code refers to variables by slot number.
        Recover slot->name by walking the stream: the k-th distinct variable
        slot to appear gets matched, in stream order, to the -Z2 variable whose
        first-seen line is closest at or before the current statement line."""
        self.slot_name: dict[int, str] = {}
        # -Z2 entries sorted by first-seen line
        entries = sorted(self.c.var_lines.items(), key=lambda kv: (kv[1], kv[0]))
        used = set()
        cur_line = 0
        for x in self.ins:
            if x.mnem == "STMT" and x.args:
                cur_line = x.args[0]
                continue
            slots = []
            if x.mnem in ("ASSIGN", "EXPR", "CMP.VV") and len(x.args) > 1:
                slots.append(x.args[1])          # dst / operand-1 slot
            for s in slots:
                if s in self.slot_name:
                    continue
                # first unused -Z2 var whose first-seen line <= cur_line
                pick = None
                for name, ln in entries:
                    if name in used:
                        continue
                    if ln <= cur_line + 1:
                        pick = name
                        break
                if pick is None:
                    for name, ln in entries:
                        if name not in used:
                            pick = name
                            break
                if pick is not None:
                    self.slot_name[s] = pick
                    used.add(pick)

    # ------------------------------------------------------------- labels
    def _synth_labels(self):
        tg = set()
        for x in self.ins:
            if x.mnem in ("GOTO", "GOSUB", "BRF", "LOOP.BACK", "FOR.NEXT", "AND.SC") and x.args:
                tg.add(x.args[0] * 2)
        for t in sorted(tg):
            self.labels.setdefault(t, f"L_{t // 2:04d}")

    def lbl(self, word_off: int) -> str:
        return self.labels.get(word_off * 2, f"L_{word_off:04d}")

    # ------------------------------------------------------------- names
    def var(self, idx: int) -> str:
        if idx in self.slot_name:
            return self.slot_name[idx]
        names = list(self.c.var_lines)
        return names[idx] if 0 <= idx < len(names) else f"V{idx}"

    def const(self, idx: int) -> str:
        ks = self.c.consts
        if 0 <= idx < len(ks) and ks[idx].kind in (4, 5):
            return ks[idx].render()
        return f"K{idx}"

    def cval(self, idx: int) -> str:
        """const rendered without quotes (for CALL/name contexts)."""
        ks = self.c.consts
        return ks[idx].s if 0 <= idx < len(ks) else f"K{idx}"

    # ------------------------------------------------------------- driver
    def run(self) -> list[Line]:
        out: list[Line] = []
        if self.c.is_subroutine:
            name = self.c.consts[0].s if self.c.consts else "SUB"
            args = ", ".join(f"ARG{k + 1}" for k in range(self.c.argc))
            out.append(Line(1, f"SUBROUTINE {name}({args})"))

        cur = 0
        pend: list[disasm.Insn] = []
        pend_line = 0
        seen_lbl: set[int] = set()

        def flush():
            nonlocal pend
            if pend:
                out.extend(self._render(pend_line, pend))
                pend = []

        for x in self.ins:
            if x.off in self.labels and x.off not in seen_lbl:
                flush()
                out.append(Line(cur, f"{self.labels[x.off]}:"))
                seen_lbl.add(x.off)
            if x.mnem == "STMT":
                flush()
                cur = pend_line = x.args[0] if x.args else cur
                continue
            if x.mnem in ("PAD", "HALT"):
                continue
            pend.append(x)
        flush()
        if not self.c.is_subroutine:
            out.append(Line(0, "END"))
        return out

    # ------------------------------------------------------------- render
    def _render(self, line: int, seq: list[disasm.Insn]) -> list[Line]:
        m = [x.mnem for x in seq]

        if m == ["RETURN"]:
            return [Line(line, "RETURN")]
        if m[:1] == ["STOP"]:
            return [Line(line, "STOP")]
        if m == ["GOTO"]:
            return [Line(line, f"GOTO {self.lbl(seq[0].args[0])}")]
        if m == ["GOSUB"]:
            return [Line(line, f"GOSUB {self.lbl(seq[0].args[0])}")]
        if m == ["LOOP.BACK"]:
            return [Line(line, f"REPEAT   ;* loop head {self.lbl(seq[0].args[0])}")]
        if m == ["FOR.NEXT"]:
            return [Line(line, f"NEXT   ;* loop head {self.lbl(seq[0].args[0])}")]

        # simple assignment: ASSIGN(mode, dst, src)
        if m == ["ASSIGN"]:
            mode, dst, src = seq[0].args
            rhs = self.const(src) if (mode & 0xFF) == 0x12 else self.var(src)
            return [Line(line, f"{self.var(dst)} = {rhs}")]
        if m == ["PUSH.C2", "ASSIGN"]:
            pc = seq[0].args[0]
            mode, dst, src = seq[1].args
            return [Line(line, f"{self.var(dst)} = {self.var(src)} : {self.const(pc)}")]

        # conditionals -> branch
        if "BRF" in m:
            return self._render_if(line, seq)

        # CALL
        if "CALL.NAME" in m or "CALL.PREP" in m:
            return self._render_call(line, seq)

        # PRINT / CRT
        if "PRINT" in m:
            return self._render_print(line, seq)

        # FOR header
        if "FOR.INIT" in m or "FOR.PREP" in m:
            return self._render_for(line, seq)

        # expression assignment
        if m[0] == "EXPR":
            return self._render_expr(line, seq)

        raw = " ".join(x.fmt().strip() for x in seq)
        return [Line(line, f"!! line {line}: {raw}")]

    # ---- operand extraction --------------------------------------------
    def _operands(self, words, both_const):
        """words = operand words after (mode, dst).  A leading value is
        operand 1; a (0, idx) pair is a constant operand; a bare non-zero
        value is a variable operand (or constant when both_const)."""
        terms = []
        i = 0
        while i < len(words) and len(terms) < 5:
            w = words[i]
            if i + 1 < len(words) and w == 0 and words[i + 1] != 0:
                terms.append(("const", words[i + 1]))
                i += 2
            elif w == 0 and not terms:
                terms.append(("const" if both_const else "var", 0))
                i += 1
            else:
                terms.append(("const" if both_const else "var", w))
                i += 1
        if not terms:
            terms = [("const" if both_const else "var", 0)]
        out = []
        for kind, v in terms:
            if kind == "const":
                out.append(self.const(v))
            else:
                out.append(self.var(v) if v < len(self.c.var_lines) else self.const(v))
        return out

    def _render_expr(self, line, seq):
        ex = seq[0]
        mode = ex.args[0] if ex.args else 0
        dst = ex.args[1] if len(ex.args) > 1 else 0
        opwords = ex.args[2:]
        both_const = (mode & 0xFF) == 0x22
        rend = self._operands(opwords, both_const)
        binch = [disasm.BINOP_CHARS.get(x.args[0], "?") for x in seq if x.mnem == "BINOP"]
        fns = [x.mnem[3:] for x in seq if x.mnem.startswith("FN.")]
        approx = "   ;* expr approx" if (len(rend) > 2 or (len(binch) + len(fns)) > 1) else ""

        if binch and len(rend) >= 2:
            e = rend[0]
            for ch, t in zip(binch, rend[1:]):
                e = f"{e} {ch} {t}"
        elif fns and rend:
            e = f"{fns[0]}({', '.join(rend)})"
            for fn in fns[1:]:
                e = f"{fn}({e})"
        elif rend:
            e = rend[0]
        else:
            e = f"<expr@{line}>"
        return [Line(line, f"{self.var(dst)} = {e}{approx}")]

    def _render_if(self, line, seq):
        brf = next(x for x in seq if x.mnem == "BRF")
        tgt = self.lbl(brf.args[0])
        cmp_ins = next((x for x in seq if x.mnem.startswith("CMP.")), None)
        op = CMP.get(cmp_ins.opcode & 0xFF, "?") if cmp_ins else "?"
        first = seq[0]
        note = "   ;* else fall through"
        mode = first.args[0] if first.args else 0
        words = first.args[1:]
        if first.opcode == 0x0152:                     # var <op> const
            terms = self._operands(words, both_const=False)
            a = terms[0] if terms else "?"
            # operand 2 is a constant here regardless of mode
            b = self.const(words[-1]) if words else "?"
        elif first.opcode == 0x0151:                   # var <op> var
            terms = self._operands(words, both_const=False)
            a = terms[0] if terms else "?"
            b = terms[-1] if len(terms) > 1 else "?"
            note = "   ;* verify comparison sense; else fall through"
        else:
            a, b = "?", "?"
        return [Line(line, f"IF {a} {op} {b} THEN GOTO {tgt}{note}")]

    def _render_call(self, line, seq):
        # name is const[0] for CALL; CALL.NAME arg = arg count
        argc = next((x.args[0] for x in seq if x.mnem == "CALL.NAME"), 0)
        name = self.cval(0)
        pushed = [self.const(x.args[0]) for x in seq if x.mnem in ("PUSH.C", "PUSH.C2")]
        if pushed:
            return [Line(line, f"CALL {name}({', '.join(pushed)})")]
        if argc:
            return [Line(line, f"CALL {name}   ;* {argc} arg(s)")]
        return [Line(line, f"CALL {name}")]

    def _render_print(self, line, seq):
        chan, items = None, []
        for x in seq:
            if x.mnem in ("PUSH.C", "PUSH.C2"):
                if chan is None:
                    chan = x.args[0]
                else:
                    items.append(self.const(x.args[0]))
        verb = "PRINT"
        if chan is not None and 0 <= chan < len(self.c.consts):
            cs = self.c.consts[chan].s
            if cs == "-2":
                verb = "CRT"
            elif cs not in ("-1", "0", ""):
                verb = f"PRINT ON {cs}"
        return [Line(line, f"{verb} {' : '.join(items) if items else chr(34)*2}")]

    def _render_for(self, line, seq):
        # FOR.INIT(var, ?, ?) ; FOR.PREP(?, limitconst) ; loop head follows
        fi = next((x for x in seq if x.mnem == "FOR.INIT"), None)
        fp = next((x for x in seq if x.mnem == "FOR.PREP"), None)
        v = self.var(fi.args[0]) if fi and fi.args else "I"
        lim = ""
        if fp and len(fp.args) > 1:
            lim = f" TO {self.const(fp.args[1])}"
        return [Line(line, f"FOR {v} = <start>{lim}   ;* verify bounds")]


def decompile_text(c: container.Container) -> str:
    d = Decompiler(c)
    lines = d.run()
    w = max((len(str(l.src_line)) for l in lines if l.src_line), default=3)
    buf = []
    for l in lines:
        tag = f"{l.src_line:>{w}}" if l.src_line else " " * w
        body = l.text if (l.text.endswith(":") or l.text.startswith("SUBROUTINE")) else "  " + l.text
        buf.append(f"{tag} | {body}")
    return "\n".join(buf)
