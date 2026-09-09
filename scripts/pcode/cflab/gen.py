#!/usr/bin/env python3
"""Control-flow probes: FOR/NEXT, IF blocks, LOOP/REPEAT, CASE, dynamic arrays."""
import os
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "src"); PAD = 40
PRE = ['  $BASICTYPE "P"', "  P = 7", "  Q = 8", "  R = 9"]
CASES = {
 "for_simple":  ["  FOR I = 1 TO 10", "    P = I", "  NEXT I"],
 "for_step":    ["  FOR I = 1 TO 10 STEP 2", "    P = I", "  NEXT I"],
 "for_vars":    ["  FOR I = P TO Q", "    R = I", "  NEXT I"],
 "for_nested":  ["  FOR I = 1 TO 3", "    FOR J = 1 TO 3", "      P = J", "    NEXT J", "  NEXT I"],
 "if_block":    ["  IF P = 1 THEN", "    Q = 2", "    R = 3", "  END"],
 "if_else":     ["  IF P = 1 THEN", "    Q = 2", "  END ELSE", "    Q = 3", "  END"],
 "if_1line":    ["  IF P = 1 THEN Q = 2"],
 "if_1line_el": ["  IF P = 1 THEN Q = 2 ELSE Q = 3"],
 "if_nested":   ["  IF P = 1 THEN", "    IF Q = 2 THEN", "      R = 3", "    END", "  END"],
 "loop_until":  ["  LOOP", "    P = P + 1", "  UNTIL P > 5", "  REPEAT"],
 "loop_while":  ["  LOOP", "  WHILE P < 5", "    P = P + 1", "  REPEAT"],
 "loop_mid":    ["  LOOP", "    P = P + 1", "  UNTIL P > 5 DO", "    Q = P", "  REPEAT"],
 "case_block":  ["  BEGIN CASE", "    CASE P = 1", "      Q = 1", "    CASE P = 2", "      Q = 2", "    CASE 1", "      Q = 9", "  END CASE"],
 "while_stmt":  ["  I = 0", "  P = 1", "  I += 1"],
 "dynarr_1":    ["  P = ''", "  P<1> = 5"],
 "dynarr_2":    ["  P = ''", "  P<2,3> = 5"],
 "dynarr_rd":   ["  P = ''", "  Q = P<2>"],
 "dynarr_ins":  ["  P = ''", "  P<-1> = 'x'"],
 "gosub_ret":   ["  GOSUB SUB1", "  STOP", "SUB1:", "  P = 1", "  RETURN"],
 "on_gosub":    ["  ON P GOSUB L1, L2", "  STOP", "L1:", "  P = 1", "  RETURN", "L2:", "  P = 2", "  RETURN"],
}
def w(name, lines):
    b = list(PRE)
    while len(b) < 9: b.append("*")
    b += lines
    while len(b) < PAD-1: b.append("*")
    b.append("END")
    open(os.path.join(OUT, name), "w", newline="\n").write("\n".join(b)+"\n")
def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
    for n, l in CASES.items(): w(n, l)
    print(f"wrote {len(CASES)}")
if __name__ == "__main__": main()
