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

from . import container, disasm, expr, structure

def _g(lst, i):
    return lst[i] if 0 <= i < len(lst) else "?"


@dataclass
class Line:
    src_line: int
    text: str
    indent: int = 0


class Decompiler:
    def __init__(self, c: container.Container):
        self.c = c
        self.ins = disasm.collapse_halts(disasm.disassemble(c.code))
        self.labels = dict(c.labels)
        self._synth_labels()
        self._map_slots()

    # -------------------------------------------------------- slot -> name
    def _map_slots(self):
        """Recover slot -> name.

        The -Z2 tail lists each variable with a counter that is source line +
        a fixed offset (verified: `A` on source line 3 lists as 10).  We record,
        per slot, the source line of its first appearance in the stream, then
        match slots to -Z2 names by nearest line -- more robust to gaps (params,
        COMMON) than a plain rank-zip."""
        self.slot_name: dict[int, str] = {}
        z = sorted(self.c.var_lines.items(), key=lambda kv: kv[1])
        if not z:
            return
        # slot -> first source line seen
        first_line: dict[int, int] = {}
        cur = 0
        for x in self.ins:
            if x.mnem in ("STMT", "STMT2") and x.args:
                cur = x.args[0]
                continue
            slots = []
            if x.opcode in (0x0152, 0x0151):
                dst, op1, op2 = disasm.expr_header(x.opcode, x.args)
                if dst is not None:
                    slots.append(dst)
                for spec in (op1, op2):
                    if spec and spec[1]:
                        slots.append(spec[0])
            elif x.opcode == 0x0159 and len(x.args) >= 3:
                slots.append(x.args[1])
                if (x.args[0] & 0xF0) == 0x20:
                    slots.append(x.args[2])
            elif x.mnem == "PUSH.V" and x.args:
                slots.append(x.args[0])
            for s in slots:
                first_line.setdefault(s, cur)

        # estimate the counter->line offset from the earliest of each
        off = z[0][1] - min(first_line.values(), default=z[0][1])
        names = [(n, ctr - off) for n, ctr in z]
        used = set()
        for slot in sorted(first_line, key=lambda s: (first_line[s], s)):
            want = first_line[slot]
            best, bd = None, 1 << 30
            for n, ln in names:
                if n in used:
                    continue
                d = abs(ln - want)
                if d < bd:
                    best, bd = n, d
            if best is not None:
                self.slot_name[slot] = best
                used.add(best)

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
    def run(self, structured=True) -> list[Line]:
        out: list[Line] = []
        if self.c.is_subroutine:
            name = self.c.consts[0].s if self.c.consts else "SUB"
            args = ", ".join(f"ARG{k + 1}" for k in range(self.c.argc))
            out.append(Line(1, f"SUBROUTINE {name}({args})"))

        self._cur = 0
        self._seen_lbl: set[int] = set()
        if structured:
            try:
                blocks = structure.build(self.ins)
                for b in blocks:
                    self._emit_block(b, 0, out)
            except Exception:  # noqa: BLE001  -- never let structure crash output
                out = out[:1] if self.c.is_subroutine else []
                self._emit_linear(self.ins, 0, out)
        else:
            self._emit_linear(self.ins, 0, out)

        if not self.c.is_subroutine:
            out.append(Line(0, "END", 0))
        return out

    # ------------------------------------------------------------- blocks
    def _emit_block(self, b, depth, out):
        if b.kind == "linear":
            self._emit_linear(b.insns, depth, out)
        elif b.kind == "if":
            self._emit_if_block(b, depth, out)
        elif b.kind == "for":
            self._emit_for_block(b, depth, out)
        elif b.kind == "loop":
            self._emit_loop_block(b, depth, out)

    def _emit_if_block(self, b, depth, out):
        cond = self._condition_text(b.cond_insns)
        line = self._line_of(b.cond_insns)
        out.append(Line(line, f"IF {cond} THEN", depth))
        for c in b.then_body:
            self._emit_block(c, depth + 1, out)
        if b.else_body:
            out.append(Line(line, "END ELSE", depth))
            for c in b.else_body:
                self._emit_block(c, depth + 1, out)
        out.append(Line(line, "END", depth))

    def _emit_for_block(self, b, depth, out):
        v = self.var(b.meta.get("loopvar")) if b.meta.get("loopvar") is not None else "I"
        sm = b.meta.get("start_mode", 0)
        sr = b.meta.get("start_ref", 0)
        start = self.var(sr) if (sm & 0x0F) != 0x01 else self.const(sr)
        pushes = b.meta.get("pushes", [])

        def pv(ins):
            return (self.const(ins.args[0]) if ins.mnem == "PUSH.C"
                    else self.var(ins.args[0]))
        limit = pv(pushes[0]) if pushes else "?"
        step = f" STEP {pv(pushes[1])}" if len(pushes) > 1 else ""
        line = b.head.word and self._nearest_line(b.head.off)
        out.append(Line(line, f"FOR {v} = {start} TO {limit}{step}", depth))
        for c in b.children:
            self._emit_block(c, depth + 1, out)
        next_line = out[-1].src_line if out and out[-1].src_line else line
        out.append(Line(next_line, f"NEXT {v}", depth))

    def _emit_loop_block(self, b, depth, out):
        line = self._nearest_line(b.head.off)
        out.append(Line(line, "LOOP", depth))
        for c in b.children:
            self._emit_block(c, depth + 1, out)
        cond = self._condition_text(b.cond_insns) if b.cond_insns else ""
        out.append(Line(line, f"REPEAT   ;* until {cond}" if cond else "REPEAT", depth))

    def _condition_text(self, cond_insns):
        return self._cond_from(cond_insns)

    def _cond_from(self, seq):
        """Render a boolean condition from the instructions up to (not incl) BRF.
        A small stack machine: EXPR runs push their result, PUSH.* push an
        operand, CMP.* / BINOP pop 2, NEG / NOT pop 1, AND.SC / OR.SC combine
        the last two clauses."""
        stack: list[str] = []
        i = 0
        while i < len(seq):
            x = seq[i]
            m = x.mnem
            if m == "BRF":
                break
            if m in ("EXPR", "CMP.VV"):
                st = expr.evaluate(seq, i, self)
                stack.append(st.text)
                i += max(st.consumed, 1)
                continue
            if m == "PUSH.V":
                stack.append(self.var(x.args[0]))
            elif m in ("PUSH.C", "PUSH.C2"):
                stack.append(self.const(x.args[0]))
            elif m.startswith("CMP."):
                ch = disasm.CMP_TEXT.get(x.opcode & 0xFF, "?")
                b = stack.pop() if stack else "?"
                a = stack.pop() if stack else "?"
                stack.append(f"{a} {ch} {b}")
            elif m == "BINOP":
                ch = disasm.BINOP_CHARS.get(x.args[0], "?")
                b = stack.pop() if stack else "?"
                a = stack.pop() if stack else "?"
                stack.append(f"({a} {ch} {b})")
            elif m == "NOT":
                stack.append(f"NOT({stack.pop()})" if stack else "?")
            elif m == "NEG":
                stack.append(f"-{stack.pop()}" if stack else "?")
            elif m == "EXTRACT":
                b = stack.pop() if stack else "?"
                a = stack.pop() if stack else "?"
                stack.append(f"{a}<{b}>")
            elif m in expr._FUNC_ARITY:
                k = expr._FUNC_ARITY[m]
                a = [stack.pop() if stack else "?" for _ in range(k)][::-1]
                stack.append(f"{expr._FUNC_NAME.get(m, m)}({', '.join(a)})")
            elif m in ("AND.SC", "AND.MERGE"):
                if len(stack) >= 2:
                    b, a = stack.pop(), stack.pop()
                    stack.append(f"{a} AND {b}")
            elif m in ("OR.SC", "OR.MERGE"):
                if len(stack) >= 2:
                    b, a = stack.pop(), stack.pop()
                    stack.append(f"{a} OR {b}")
            i += 1
        cond = stack[-1] if stack else "?"
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1]
        return cond

    def _line_of(self, insns):
        for x in insns:
            ln = self._nearest_line(x.off)
            if ln:
                return ln
        return self._cur

    def _nearest_line(self, off):
        best = 0
        for x in self.ins:
            if x.off > off:
                break
            if x.mnem in ("STMT", "STMT2") and x.args:
                best = x.args[0]
        return best

    def _emit_linear(self, insns, depth, out):
        pend: list = []
        pend_line = self._cur

        def flush():
            nonlocal pend
            if pend:
                for ln in self._render(pend_line, pend):
                    ln.indent = max(ln.indent, depth)
                    out.append(ln)
                pend = []

        for x in insns:
            if x.off in self.labels and x.off not in self._seen_lbl:
                flush()
                out.append(Line(self._cur, f"{self.labels[x.off]}:", depth))
                self._seen_lbl.add(x.off)
            if x.mnem in ("STMT", "STMT2"):
                flush()
                self._cur = pend_line = x.args[0] if x.args else self._cur
                continue
            if x.mnem in ("PAD", "HALT"):
                continue
            pend.append(x)
        flush()

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

        # split a compound source line (X = 1 ; Y = 2 ; ...) into its statements
        splits = self._split_compound(seq)
        if len(splits) > 1:
            outl = []
            for s in splits:
                outl += self._render(line, s)
            return outl

        # file I/O:  EXPR(operands) ... {OPEN|READ|WRITE|...}
        io = next((x for x in seq if x.mnem in (
            "OPEN", "READ", "READU", "WRITE", "READV", "WRITEV",
            "DELETE", "MATREAD", "MATWRITE")), None)
        if io is not None:
            return self._render_io(line, seq, io)

        # compound assignment:  EXPR(dst, val)  OPADD <op char>
        if "OPADD" in m and m[0] == "EXPR":
            op = next(x for x in seq if x.mnem == "OPADD")
            ch = disasm.BINOP_CHARS.get(op.args[0], "?")
            dst, o1, o2 = disasm.expr_header(seq[0].opcode, seq[0].args)
            tgt = self.var(dst) if dst is not None else "?"
            rhs = (self.var(o2[0]) if o2 and o2[1] else self.const(o2[0])) if o2 else "?"
            return [Line(line, f"{tgt} = {tgt} {ch} {rhs}")]

        # dynamic-array replace:  EXPR dst sub.. [PUSH.C ..]  REPLACE n
        if "REPLACE" in m:
            return self._render_dynarr(line, seq)

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

    def _render_dynarr(self, line, seq):
        """EXPR (dst, sub1[, sub2])  [NEG]  [PUSH.C ...]*  REPLACE <nsubs>
        The n subscripts then the value are drawn, in order, from the EXPR
        inline operands followed by the PUSH.C stream."""
        rep = next(x for x in seq if x.mnem == "REPLACE")
        nsubs = rep.args[0] if rep.args else 1
        head = seq[0]
        dst, op1, op2 = disasm.expr_header(head.opcode, head.args)
        vals = []
        if op1:
            vals.append(self.var(op1[0]) if op1[1] else self.const(op1[0]))
        if op2:
            vals.append(self.var(op2[0]) if op2[1] else self.const(op2[0]))
        neg = any(x.mnem == "NEG" for x in seq[:seq.index(rep)])
        for x in seq:
            if x.mnem in ("PUSH.C", "PUSH.C2"):
                vals.append(self.const(x.args[0]))
            elif x.mnem == "PUSH.V":
                vals.append(self.var(x.args[0]))
        subs = vals[:nsubs]
        value = vals[nsubs] if len(vals) > nsubs else "?"
        if neg and subs:
            subs[0] = f"-{subs[0]}"
        tgt = self.var(dst) if dst is not None else "?"
        return [Line(line, f"{tgt}<{', '.join(subs)}> = {value}")]

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

    def _split_compound(self, seq):
        """Break a run at each point a new top-level statement clearly begins
        (an ASSIGN or a fresh EXPR-with-dst right after a completed one)."""
        out, cur = [], []
        for x in seq:
            if cur and x.mnem == "ASSIGN" and cur[-1].mnem in (
                    "ASSIGN", "PAD", "HALT", "EXPR.END"):
                out.append(cur)
                cur = []
            cur.append(x)
        if cur:
            out.append(cur)
        return out if len(out) > 1 else [seq]

    def _render_io(self, line, seq, io):
        exprs = [x for x in seq if x.mnem in ("EXPR", "CMP.VV")]
        refs = []
        for e in exprs:
            dst, o1, o2 = disasm.expr_header(e.opcode, e.args)
            for r in (dst, o1, o2):
                if r is None:
                    continue
                if isinstance(r, tuple):
                    refs.append(self.var(r[0]) if r[1] else self.const(r[0]))
                else:
                    refs.append(self.var(r))
        v = io.mnem
        # refs order is (var/expr, file, key[, field]) for most; (file, var) for OPEN
        if v == "OPEN":
            e = exprs[0] if exprs else None
            if e is not None and len(e.args) >= 3:
                txt = f"OPEN {self.const(e.args[1])} TO {self.var(e.args[2])}"
            else:
                txt = "OPEN ?"
        elif v in ("READ", "READU"):
            txt = f"{v} {_g(refs,0)} FROM {_g(refs,1)}, {_g(refs,2)}"
        elif v == "WRITE":
            txt = f"WRITE {_g(refs,0)} ON {_g(refs,1)}, {_g(refs,2)}"
        elif v == "READV":
            txt = f"READV {_g(refs,0)} FROM {_g(refs,1)}, {_g(refs,2)}, {_g(refs,3)}"
        elif v == "WRITEV":
            txt = f"WRITEV {_g(refs,0)} ON {_g(refs,1)}, {_g(refs,2)}, {_g(refs,3)}"
        elif v == "DELETE":
            txt = f"DELETE {_g(refs,0)}, {_g(refs,1)}"
        elif v in ("MATREAD", "MATWRITE"):
            kw = "FROM" if v == "MATREAD" else "ON"
            txt = f"{v} {_g(refs,0)} {kw} {_g(refs,1)}, {_g(refs,2)}"
        else:
            txt = v
        # a trailing BRF marks a THEN/ELSE clause
        brf = next((x for x in seq if x.mnem == "BRF"), None)
        if brf is not None:
            txt += f"   ;* THEN/ELSE at {self.lbl(brf.args[0])}"
        return [Line(line, txt)]

    def _render_assign(self, line, seq):
        mode, dst, src = seq[0].args[:3]
        # mode low byte: 0x12 => constant source, 0x22 => variable source
        rhs = self.const(src) if (mode & 0xF0) == 0x10 else self.var(src)
        # trailing tokens (rare): fold as an expression continuation
        if len(seq) > 1 and seq[1].mnem not in ("EXPR.END", "PAD", "HALT"):
            st = expr.evaluate(seq, 0, self)
            return [Line(line, f"{self.var(st.dst if st.dst is not None else dst)}"
                               f" = {st.text}")]
        return [Line(line, f"{self.var(dst)} = {rhs}")]

    def _render_if(self, line, seq):
        brf = next((x for x in seq if x.mnem == "BRF"), None)
        tgt = self.lbl(brf.args[0]) if brf else "?"
        cond = self._cond_from(seq)
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
        pr = next(x for x in seq if x.mnem == "PRINT")
        pri = seq.index(pr)
        # everything before PRINT is  PUSH <channel>  (a numeric selector)
        chan = next((x.args[0] for x in seq[:pri]
                     if x.mnem in ("PUSH.C", "PUSH.C2")), None)
        verb = "PRINT"
        if chan is not None and 0 <= chan < len(self.c.consts):
            k = self.c.consts[chan]
            if k.kind == 5 and k.s == "-2":
                verb = "CRT"
            elif k.kind == 5 and k.s not in ("-1", "0", ""):
                verb = f"PRINT ON {k.s}"

        # after PRINT: the item stream -- a small stack machine, one entry per
        # print item (PRINT's operand is the item count).
        stack: list[str] = []
        for x in seq[pri + 1:]:
            m = x.mnem
            if m == "PUSH.V":
                stack.append(self.var(x.args[0]))
            elif m in ("PUSH.C", "PUSH.C2"):
                stack.append(self.const(x.args[0]))
            elif m in ("EXPR", "CMP.VV"):
                _d, o1, o2 = disasm.expr_header(x.opcode, x.args)
                for o in (o1, o2):
                    if o is not None:
                        v = (self.var(o[0]) if (o[1] or x.opcode == 0x0151)
                             else self.const(o[0]))
                        stack.append(v)
            elif m == "BINOP" and len(stack) >= 2:
                ch = disasm.BINOP_CHARS.get(x.args[0], "?")
                b, a = stack.pop(), stack.pop()
                stack.append(f"{a} {ch} {b}")
            elif m.startswith("CMP.") and len(stack) >= 2:
                ch = disasm.CMP_TEXT.get(x.opcode & 0xFF, "?")
                b, a = stack.pop(), stack.pop()
                stack.append(f"{a} {ch} {b}")
            elif m == "ASSIGN" and (x.args[0] >> 8) == 0x03:
                mode, a, b = x.args[:3]
                tb = self.var(b) if (mode & 0x20) else self.const(b)
                stack.append(f"{self.const(a)} : {tb}")
            elif m == "NEG" and stack:
                stack.append(f"-{stack.pop()}")
            elif m.startswith("FN.") and m in expr._FUNC_ARITY:
                k = expr._FUNC_ARITY[m]
                a = [stack.pop() if stack else "?" for _ in range(k)][::-1]
                stack.append(f"{expr._FUNC_NAME.get(m, m)}({', '.join(a)})")
        body = ", ".join(stack) if stack else '""'
        return [Line(line, f"{verb} {body}")]

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
    import re
    d = Decompiler(c)
    lines = d.run()

    # drop synthetic L_dddd labels no surviving statement jumps to
    referenced = set()
    for l in lines:
        for mo in re.finditer(r"\b(L_\d{4}|[A-Z][A-Z0-9.]*)\b(?=\s*$|\s*;)", l.text):
            pass
    referenced = set(re.findall(r"(?:GOTO|GOSUB)\s+([A-Za-z_][\w.]*)",
                                "\n".join(l.text for l in lines)))
    lines = [l for l in lines
             if not (l.text.endswith(":") and l.text[:-1].startswith("L_")
                     and l.text[:-1] not in referenced)]

    w = max((len(str(l.src_line)) for l in lines if l.src_line), default=3)
    buf = []
    for l in lines:
        tag = f"{l.src_line:>{w}}" if l.src_line else " " * w
        pad = "  " * (min(l.indent, 12) + 1)
        if l.text.endswith(":") or l.text.startswith("SUBROUTINE"):
            pad = "  " * min(l.indent, 12)
        buf.append(f"{tag} | {pad}{l.text}")
    return "\n".join(buf)
