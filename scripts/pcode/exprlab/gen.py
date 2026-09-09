#!/usr/bin/env python3
"""Generate a matrix of expression probes to crack the EXPR/ASSIGN operand
encoding.  Each probe is a full 40-line program; a fixed preamble declares
P..T so slot indices are stable (P=0 Q=1 R=2 S=3 T=4), then line 20 is the
statement under test.  Everything before line 20 is identical across probes.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "src")
PAD = 40

PREAMBLE = [
    '  $BASICTYPE "P"',
    "  P = 7", "  Q = 8", "  R = 9", "  S = 10", "  T = 11",
]

# assignment cases: X = <expr>
CASES = {
    "vv_add": "P + Q", "vc_add": "P + 3", "cv_add": "3 + P", "cc_add": "3 + 4",
    "vv_sub": "P - Q", "vv_mul": "P * Q", "vv_div": "P / Q", "vv_cat": "P : Q",
    "vc_cat": "P : 'z'", "vv_pwr": "P ^ Q",
    "vv_eq": "P = Q", "vc_eq": "P = 3", "vv_lt": "P < Q", "vv_ne": "P # Q", "vv_gt": "P > Q", "vv_le": "P <= Q", "vv_ge": "P >= Q",
    "vvv_add": "P + Q + R", "vvv_sub": "P - Q - R", "vvc_add": "P + Q + 3",
    "cvv_add": "3 + P + Q", "vcv_add": "P + 3 + Q",
    "vvv_mix1": "P + Q * R", "vvv_mix2": "P * Q + R", "vvv_paren": "(P + Q) * R",
    "vvvv_add": "P + Q + R + S",
    "neg_v": "-P", "neg_c": "-3", "not_v": "NOT(P)",
    "fn1": "LEN(P)", "fn1c": "LEN('abcd')", "fn2": "OCONV(P, 'MCU')",
    "fn3": "FIELD(P, ',', 2)", "fn_nest": "LEN(TRIM(P))",
    "fn_arg_expr": "LEN(P : Q)", "fn_plus_v": "LEN(P) + Q", "v_plus_fn": "Q + LEN(P)",
    "substr": "P[2,3]", "extract": "P<2>", "extract2": "P<2,3>",
    "fn_trim": "TRIM(P)", "fn_upcase": "UPCASE(P)", "fn_count": "COUNT(P, ',')",
    "fn_index": "INDEX(P, 'x', 1)", "fn_num": "NUM(P)", "fn_seq": "SEQ(P)",
    "fn_dcount": "DCOUNT(P, @AM)", "fn_str": "STR('x', 5)", "fn_space": "SPACE(4)",
    "logical_and": "P AND Q", "logical_or": "P OR Q",
}

# IF-condition cases: the block guarded by the condition is `X = 1`
IF_CASES = {
    "if_vc_eq": "IF P = 3 THEN",
    "if_vv_eq": "IF P = Q THEN",
    "if_vv_gt": "IF P > Q THEN",
    "if_vv_lt": "IF P < Q THEN",
    "if_vv_ne": "IF P # Q THEN",
    "if_vv_ge": "IF P >= Q THEN",
    "if_and":   "IF P = 3 AND Q = 4 THEN",
    "if_or":    "IF P = 3 OR Q = 4 THEN",
    "if_expr":  "IF P + Q > 10 THEN",
}


def _write(name, lines):
    body = list(PREAMBLE)
    while len(body) < 19:
        body.append("*")
    body += lines
    while len(body) < PAD - 1:
        body.append("*")
    body.append("END")
    with open(os.path.join(OUT, name), "w", newline="\n") as fh:
        fh.write("\n".join(body) + "\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    for name, expr in CASES.items():
        _write(name, [f"  X = {expr}"])
    for name, head in IF_CASES.items():
        _write(name, [f"  {head}", "    X = 1", "  END"])
    print(f"wrote {len(CASES) + len(IF_CASES)} expr probes")


if __name__ == "__main__":
    main()
