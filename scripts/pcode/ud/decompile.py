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

from . import container, disasm, expr

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
        """The p-code refers to variables by slot index; the -Z2 tail lists
        names with a monotonic first-seen counter (not the raw source line, but
        order-preserving).  Variable slots are allocated in first-appearance
        order too, so rank-zip the two: the k-th slot to appear in the stream
        gets the k-th -Z2 name by counter."""
        self.slot_name: dict[int, str] = {}
        entries = [n for n, _ in sorted(self.c.var_lines.items(),
                                        key=lambda kv: (kv[1], kv[0]))]
        order: list[int] = []
        seen = set()
        for x in self.ins:
            slots = []
            if x.opcode in (0x0152, 0x0151):
                dst, op1, op2 = disasm.expr_header(x.opcode, x.args)
                for spec in (op1, op2):
                    if spec and spec[1]:
                        slots.append(spec[0])
                if dst is not None:
                    slots.insert(0, dst)
            elif x.opcode == 0x0159 and len(x.args) >= 3:
                mode, d, s = x.args[0], x.args[1], x.args[2]
                slots.append(d)
                if (mode & 0xFF) in (0x22, 0x0122 & 0xFF):
                    slots.append(s)
            elif x.mnem == "PUSH.V" and x.args:
                slots.append(x.args[0])
            for s in slots:
                if s not in seen:
                    seen.add(s)
                    order.append(s)
        for i, slot in enumerate(order):
            if i < len(entries):
                self.slot_name[slot] = entries[i]

    # ------------------------------------------------------------- labels
    def _synth_labels(self):
        # AND.SC / OR.SC targets are intra-expression short-circuit jumps, not
        # statement labels -- naming them would split a compound condition.
        tg = set()
        for x in self.ins:
            if x.mnem in ("GOTO", "GOSUB", "BRF", "LOOP.BACK", "FOR.NEXT") and x.args:
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

        # concatenation:  PUSH.C2 <dst-slot>  ASSIGN mode=0x03xx op1 op2 [tokens]
        if m[:2] == ["PUSH.C2", "ASSIGN"] and (seq[1].args[0] >> 8) == 0x03:
            return self._render_concat(line, seq)

        # simple assignment: ASSIGN(mode, dst, src)
        if m[0] == "ASSIGN" and "BRF" not in m:
            return self._render_assign(line, seq)

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
        if m[0] in ("EXPR", "CMP.VV"):
            st = expr.evaluate(seq, 0, self)
            if st.dst is not None:
                return [Line(line, f"{self.var(st.dst)} = {st.text}")]
            return [Line(line, f"{self.var(0)} = {st.text}   ;* (no dst?)")]

        raw = " ".join(x.fmt().strip() for x in seq)
        return [Line(line, f"!! line {line}: {raw}")]

    def _render_concat(self, line, seq):
        dst = seq[0].args[0]
        a = seq[1]
        mode = a.args[0]
        op1, op2 = a.args[1], a.args[2] if len(a.args) > 2 else 0
        # mode low byte: 0x22 => op2 var, 0x12 => op2 const  (op1 always var)
        t1 = self.var(op1)
        t2 = self.var(op2) if (mode & 0x20) else self.const(op2)
        parts = [t1, t2]
        # trailing tokens can add more terms or wrap the result in a function
        fn = None
        for x in seq[2:]:
            if x.mnem in ("PUSH.V",):
                parts.append(self.var(x.args[0]))
            elif x.mnem in ("PUSH.C", "PUSH.C2"):
                parts.append(self.const(x.args[0]))
            elif x.mnem.startswith("FN."):
                fn = x.mnem[3:]
            elif x.mnem in ("EXPR.END", "PAD", "HALT"):
                break
        rhs = " : ".join(parts)
        if fn:
            rhs = f"{fn}({rhs})"
        return [Line(line, f"{self.var(dst)} = {rhs}")]

    def _render_assign(self, line, seq):
        mode, dst, src = seq[0].args[:3]
        # low nibble of the mode's low byte: 2 = const source, otherwise var
        rhs = self.const(src) if (mode & 0x0F) == 0x02 else self.var(src)
        # trailing tokens (rare): fold as an expression continuation
        if len(seq) > 1 and seq[1].mnem not in ("EXPR.END", "PAD", "HALT"):
            st = expr.evaluate(seq, 0, self)
            return [Line(line, f"{self.var(st.dst if st.dst is not None else dst)}"
                               f" = {st.text}")]
        return [Line(line, f"{self.var(dst)} = {rhs}")]

    def _render_if(self, line, seq):
        # collect the (possibly several, AND/OR-joined) expression runs before BRF
        parts = []
        joiner = None
        i = 0
        while i < len(seq):
            x = seq[i]
            if x.mnem in ("EXPR", "CMP.VV"):
                st = expr.evaluate(seq, i, self)
                parts.append(st.text)
                i += st.consumed
                continue
            if x.mnem == "AND.SC":
                joiner = "AND"
            elif x.mnem == "OR.SC":
                joiner = "OR"
            elif x.mnem == "BRF":
                break
            i += 1
        brf = next((x for x in seq if x.mnem == "BRF"), None)
        tgt = self.lbl(brf.args[0]) if brf else "?"
        cond = f" {joiner} ".join(parts) if parts else "?"
        return [Line(line, f"IF {cond} THEN GOTO {tgt}   ;* else fall through")]

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
