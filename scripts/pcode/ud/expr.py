"""Fold an EXPR / CMP.VV instruction run back into a source expression.

The p-code expression form is a small stack machine:

    EXPR  mode [dst] op1 [op2]      -- pushes the 1-2 inline operands
    <token>*                        -- until EXPR.END (0x0021) or a branch
    EXPR.END

Tokens: PUSH.V / PUSH.C push an operand; BINOP and CMP.* pop 2 push 1; NEG /
NOT pop 1; FN.* pop their arity.  The value left on the stack is the result.

We build a tiny expression tree so redundant parentheses can be dropped:
same-precedence left-associative chains (a + b + c) render without parens.
"""

from __future__ import annotations

from . import disasm

_FUNC_ARITY = {
    "FN.LEN": 1, "FN.TRIM": 1, "FN.NUM": 1, "FN.SEQ": 1, "FN.UPCASE": 1,
    "FN.SPACE": 1, "FN.INT": 1, "FN.ABS": 1, "FN.CHAR": 1,
    "FN.DATE": 0, "FN.TIME": 0, "FN.COL1": 0, "FN.COL2": 0,
    "FN.ACOS": 1, "FN.ASIN": 1, "FN.ATAN": 1, "FN.SIN": 1, "FN.TAN": 1, "FN.COS": 1,
    "FN.SQRT": 1, "FN.EXP": 1, "FN.BITNOT": 1, "FN.SUM": 1,
    "FN.OCONV": 2, "FN.ICONV": 2, "FN.COUNT": 2, "FN.DCOUNT": 2, "FN.STR": 2,
    "FN.BITAND": 2, "FN.BITOR": 2, "FN.BITXOR": 2,
    "FN.FIELD": 3, "FN.INDEX": 3, "FN.SUBSTR": 3,
}
_FUNC_NAME = {k: (k[3:] if k != "FN.SUBSTR" else "SUBSTR") for k in _FUNC_ARITY}

# operator precedence (higher binds tighter); UniBasic: :  then + -  then * /  then ^
_PREC = {":": 1, "+": 2, "-": 2, "*": 3, "/": 3, "MOD": 3, "^": 4,
         "=": 0, "#": 0, "<": 0, ">": 0, "<=": 0, ">=": 0}


class Node:
    __slots__ = ("kind", "op", "kids", "text")

    def __init__(self, kind, op=None, kids=(), text=None):
        self.kind = kind          # "leaf" | "bin" | "un" | "call"
        self.op = op
        self.kids = list(kids)
        self.text = text

    def render(self, parent_prec=-1):
        if self.kind == "leaf":
            return self.text
        if self.kind == "un":
            return f"{self.op}{self.kids[0].render(99)}"
        if self.kind == "call":
            if self.op == "SUBSTR" and len(self.kids) == 3:
                a, b, c = (k.render(0) for k in self.kids)
                return f"{a}[{b}, {c}]"
            inner = ", ".join(k.render(0) for k in self.kids)
            return f"{self.op}({inner})"
        # binary
        p = _PREC.get(self.op, 0)
        left = self.kids[0].render(p)
        right = self.kids[1].render(p + 1)   # right child needs parens at equal prec
        s = f"{left} {self.op} {right}"
        return f"({s})" if p < parent_prec else s


class ExprState:
    def __init__(self, node, dst, consumed):
        self.node = node
        self.dst = dst
        self.consumed = consumed

    @property
    def text(self):
        return self.node.render() if self.node else "?"


_STOP = {"EXPR.END", "STMT", "STMT2", "BRF", "GOTO", "GOSUB", "PAD", "HALT",
         "AND.SC", "OR.SC", "AND.MERGE", "OR.MERGE"}


def evaluate(insns, start, names) -> ExprState:
    head = insns[start]
    dst, op1, op2 = disasm.expr_header(head.opcode, head.args)
    if head.opcode == 0x0151:            # CMP.VV: both inline operands are vars
        if op1:
            op1 = (op1[0], True)
        if op2:
            op2 = (op2[0], True)
    stack: list[Node] = []

    def leaf(spec):
        idx, is_var = spec
        return Node("leaf", text=(names.var(idx) if is_var else names.const(idx)))

    if op1 is not None:
        stack.append(leaf(op1))
    if op2 is not None:
        stack.append(leaf(op2))

    i = start + 1
    n = len(insns)
    while i < n:
        x = insns[i]
        m = x.mnem
        if m in _STOP:
            break
        if m == "PUSH.V":
            stack.append(Node("leaf", text=names.var(x.args[0]) if x.args else "?"))
        elif m in ("PUSH.C", "PUSH.C2"):
            stack.append(Node("leaf", text=names.const(x.args[0]) if x.args else "?"))
        elif m == "PUSH.AM":
            stack.append(Node("leaf", text="@AM"))
        elif m == "PUSH.VM":
            stack.append(Node("leaf", text="@VM"))
        elif m == "PUSH.SVM":
            stack.append(Node("leaf", text="@SVM"))
        elif m == "BINOP":
            ch = disasm.BINOP_CHARS.get(x.args[0], "?") if x.args else "?"
            b = stack.pop() if stack else Node("leaf", text="?")
            a = stack.pop() if stack else Node("leaf", text="?")
            stack.append(Node("bin", ch, (a, b)))
        elif m.startswith("CMP."):
            ch = disasm.CMP_TEXT.get(x.opcode & 0xFF, "?")
            b = stack.pop() if stack else Node("leaf", text="?")
            a = stack.pop() if stack else Node("leaf", text="?")
            stack.append(Node("bin", ch, (a, b)))
        elif m == "NEG":
            stack.append(Node("un", "-", (stack.pop() if stack else Node("leaf", text="?"),)))
        elif m == "NOT":
            stack.append(Node("call", "NOT", (stack.pop() if stack else Node("leaf", text="?"),)))
        elif m == "EXTRACT":
            b = stack.pop() if stack else Node("leaf", text="?")
            a = stack.pop() if stack else Node("leaf", text="?")
            stack.append(Node("leaf", text=f"{a.render(0)}<{b.render(0)}>"))
        elif m == "FOR.PREP" and len(x.args) > 1:
            # in an expression stream this is "concat constant #arg1"
            a = stack.pop() if stack else Node("leaf", text="?")
            stack.append(Node("bin", ":", (a, Node("leaf", text=names.const(x.args[1])))))
        elif m == "ASSIGN" and (x.args[0] >> 8) == 0x03:
            mode, oa, ob = x.args[:3]
            ta = names.var(oa)                              # op1 is always a var
            tb = names.var(ob) if (mode & 0x20) else names.const(ob)
            stack.append(Node("bin", ":", (Node("leaf", text=ta), Node("leaf", text=tb))))
        elif m in ("PUSH.C0", "EXPR", "CMP.VV"):
            _d, _o1, _o2 = disasm.expr_header(x.opcode, x.args)
            for o in (_o1, _o2):
                if o is not None:
                    v = names.var(o[0]) if (o[1] or x.opcode == 0x0151) else names.const(o[0])
                    stack.append(Node("leaf", text=v))
        elif m in _FUNC_ARITY:
            k = _FUNC_ARITY[m]
            kids = [stack.pop() if stack else Node("leaf", text="?") for _ in range(k)][::-1]
            stack.append(Node("call", _FUNC_NAME.get(m, m), kids))
        else:
            break
        i += 1

    node = stack[-1] if stack else None
    return ExprState(node, dst, i - start)
