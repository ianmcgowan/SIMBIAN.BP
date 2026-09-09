"""Reconstruct block structure (IF/FOR/LOOP) from the flat instruction list.

Produces a tree of Block nodes that decompile.py renders with indentation.
Anything that does not match a known shape falls back to a Linear block whose
statements are decompiled one by one (with explicit labels), so correctness
never depends on structure recovery succeeding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import disasm


@dataclass
class Block:
    kind: str                      # "linear" | "if" | "for" | "loop"
    insns: list = field(default_factory=list)   # for linear: the instructions
    head: object = None            # first instruction (EXPR/FOR.INIT/...)
    cond_insns: list = field(default_factory=list)
    then_body: list = field(default_factory=list)   # list[Block]
    else_body: list = field(default_factory=list)
    children: list = field(default_factory=list)     # for/loop body: list[Block]
    meta: dict = field(default_factory=dict)


def _idx_by_off(insns):
    return {x.off: i for i, x in enumerate(insns)}


def build(insns, lo=0, hi=None, depth=0):
    """Return list[Block] covering insns[lo:hi] (indices)."""
    if hi is None:
        hi = len(insns)
    if depth > 10:
        # runaway nesting -- almost certainly a mis-paired block; keep it flat
        return [Block("linear", insns=insns[lo:hi])]
    off2i = _idx_by_off(insns)
    out: list[Block] = []
    i = lo
    linear: list = []

    def flush_linear():
        nonlocal linear
        if linear:
            out.append(Block("linear", insns=linear))
            linear = []

    while i < hi:
        x = insns[i]

        # ---- IF: <cond run> ... BRF t -------------------------------
        if x.mnem in ("EXPR", "CMP.VV", "PUSH.V", "PUSH.C") and _is_if_head(insns, i, hi):
            j, brf = _find_brf(insns, i, hi)
            if brf is not None:
                t1 = brf.args[0] * 2
                cond = insns[i:j + 1]
                then_lo = j + 1
                # THEN body ends either at a GOTO t2 just before t1, or at t1
                end_i = off2i.get(t1, hi)
                then_hi = end_i
                else_lo = else_hi = None
                if end_i - 1 >= then_lo and insns[end_i - 1].mnem == "GOTO":
                    t2 = insns[end_i - 1].args[0] * 2
                    if t2 > t1:
                        then_hi = end_i - 1
                        else_lo = end_i
                        else_hi = off2i.get(t2, hi)
                b = Block("if", cond_insns=cond)
                b.then_body = build(insns, then_lo, then_hi, depth + 1)
                if else_lo is not None:
                    b.else_body = build(insns, else_lo, else_hi, depth + 1)
                    i = else_hi
                else:
                    i = then_hi
                    # skip a trailing no-op GOTO t1
                    if i < hi and insns[i].mnem == "GOTO" and insns[i].args[0] * 2 == t1:
                        i += 1
                flush_linear()
                out.append(b)
                continue

        # ---- FOR: FOR.INIT ... FOR.NEXT/OP_0164 ----------------------
        if x.mnem == "FOR.INIT":
            fb, ni = _build_for(insns, i, hi, off2i, depth)
            if fb is not None:
                flush_linear()
                out.append(fb)
                i = ni
                continue

        # ---- LOOP ... REPEAT --------------------------------------
        if x.mnem == "STMT" and _loop_span(insns, i, hi) is not None:
            lb, ni = _build_loop2(insns, i, hi, off2i, depth)
            if lb is not None:
                flush_linear()
                out.append(lb)
                i = ni
                continue

        linear.append(x)
        i += 1

    flush_linear()
    return out


_IO = {"OPEN", "READ", "READU", "WRITE", "READV", "WRITEV", "DELETE",
       "MATREAD", "MATWRITE"}


def _is_if_head(insns, i, hi):
    # a BRF within a short window, before any STMT / FOR / LOOP / I-O boundary
    for k in range(i, min(i + 14, hi)):
        m = insns[k].mnem
        if m == "BRF":
            return True
        if m in _IO:
            return False        # a READ/WRITE/OPEN ... THEN/ELSE, not an IF
        if m in ("FOR.INIT", "LOOP.BACK", "AND.SC", "OR.SC"):
            continue
        if m == "STMT" and k > i:
            return False
    return False


def _find_brf(insns, i, hi):
    for k in range(i, min(i + 16, hi)):
        if insns[k].mnem == "BRF":
            return k, insns[k]
    return i, None


def _starts_loop(insns, i, hi):
    for k in range(i + 1, min(i + 60, hi)):
        if insns[k].mnem == "LOOP.BACK":
            return True
        if insns[k].mnem == "FOR.INIT":
            return False
    return False


def _build_for(insns, i, hi, off2i, depth):
    head = insns[i]
    # find FOR.NEXT (0x0167) or OP_0164 loop-control after the header
    ctrl = None
    for k in range(i + 1, min(i + 8, hi)):
        if insns[k].mnem == "FOR.NEXT" or insns[k].opcode == 0x0164:
            ctrl = insns[k]
            ctrl_i = k
            break
    if ctrl is None:
        return None, i + 1
    # the loop bottom is the GOTO whose target is the loop-control instruction
    back_i = None
    for k in range(ctrl_i + 1, hi):
        if insns[k].mnem == "GOTO" and insns[k].args and insns[k].args[0] * 2 == ctrl.off:
            back_i = k
            break
        if insns[k].mnem in ("RETURN", "SUB.PROLOG"):
            break
    if back_i is None:
        return None, i + 1
    # body = from first STMT after the header cluster to back_i
    body_lo = ctrl_i + 1
    while body_lo < back_i and insns[body_lo].mnem != "STMT":
        body_lo += 1
    b = Block("for", head=head)
    b.meta["loopvar"] = head.args[1] if len(head.args) > 1 else None
    # start ref from FOR.PREP
    for k in range(i + 1, ctrl_i):
        if insns[k].mnem == "FOR.PREP" and len(insns[k].args) > 1:
            b.meta["start_mode"] = insns[k].args[0]
            b.meta["start_ref"] = insns[k].args[1]
    # limit / step: PUSH.C / PUSH.V between ctrl and body_lo
    pushes = [insns[k] for k in range(ctrl_i + 1, body_lo)
              if insns[k].mnem in ("PUSH.C", "PUSH.V")]
    b.meta["pushes"] = pushes
    b.children = build(insns, body_lo, back_i, depth + 1)
    end = back_i + 1
    # swallow the compiler's post-loop bookkeeping (a lone PUSH.C2 + padding)
    while end < hi and insns[end].mnem in ("PUSH.C2", "PUSH.C", "PAD", "HALT"):
        end += 1
    return b, end


def _loop_span(insns, i, hi):
    """If insns[i] (a STMT) is the head of a LOOP, return the index of the
    GOTO that closes it (a GOTO whose target is this STMT's offset), else None."""
    top = insns[i].off
    seen_back = False
    for k in range(i + 1, min(i + 400, hi)):
        m = insns[k].mnem
        if m == "LOOP.BACK":
            seen_back = True
        if m == "GOTO" and insns[k].args and insns[k].args[0] * 2 == top:
            return k if seen_back else None
        if m in ("SUB.PROLOG",):
            return None
    return None


def _build_loop2(insns, i, hi, off2i, depth):
    end_goto = _loop_span(insns, i, hi)
    if end_goto is None:
        return None, i + 1
    lb_i = next((k for k in range(i + 1, end_goto)
                 if insns[k].mnem == "LOOP.BACK"), None)
    b = Block("loop", head=insns[i])
    # body = statements from i+1 up to LOOP.BACK; the tail (LOOP.BACK..GOTO) is
    # the exit test -- keep it for the caller to render as UNTIL/WHILE.
    body_hi = lb_i if lb_i is not None else end_goto
    b.children = build(insns, i + 1, body_hi, depth + 1)
    b.cond_insns = insns[(lb_i + 1) if lb_i is not None else body_hi:end_goto]
    end = end_goto + 1
    while end < hi and insns[end].mnem in ("PUSH.C", "PUSH.C2", "PAD", "HALT"):
        end += 1
    return b, end


def _build_loop(insns, i, hi, off2i, depth):
    # i is the STMT that opens the LOOP; find LOOP.BACK
    lb_i = None
    for k in range(i + 1, hi):
        if insns[k].mnem == "LOOP.BACK":
            lb_i = k
            break
    if lb_i is None:
        return None, i + 1
    # condition/tail junk runs from LOOP.BACK to the back GOTO
    back_i = None
    for k in range(lb_i + 1, hi):
        if insns[k].mnem == "GOTO":
            back_i = k
            break
    end_i = (back_i + 1) if back_i is not None else lb_i + 1
    b = Block("loop", head=insns[i])
    b.cond_insns = insns[lb_i + 1:back_i] if back_i else []
    b.children = build(insns, i + 1, lb_i, depth + 1)
    return b, end_i
