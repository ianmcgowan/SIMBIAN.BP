#!/usr/bin/env python3
import os
HERE=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(HERE,"src"); PAD=40
PRE=['  $BASICTYPE "P"','  F = 0','  REC = 0','  K = "key"']
C={
 "open_else":   ['  OPEN "VOC" TO F ELSE STOP'],
 "open_then":   ['  OPEN "VOC" TO F THEN NULL ELSE STOP'],
 "read_then":   ['  READ REC FROM F, K THEN NULL ELSE NULL'],
 "read_else":   ['  READ REC FROM F, K ELSE REC = ""'],
 "readv":       ['  READV X FROM F, K, 3 ELSE X = ""'],
 "readu":       ['  READU REC FROM F, K ELSE NULL'],
 "write":       ['  WRITE REC ON F, K'],
 "writev":      ['  WRITEV "x" ON F, K, 3'],
 "delete":      ['  DELETE F, K'],
 "locate":      ['  LOCATE "x" IN REC<1> BY "AR" SETTING P ELSE NULL'],
 "matread":     ['  DIM M(5)', '  MATREAD M FROM F, K ELSE NULL'],
 "matwrite":    ['  DIM M(5)', '  MATWRITE M ON F, K'],
 "loop_read":   ['  LOOP', '  WHILE 1', '    X = 1', '  REPEAT'],
 "input_at":    ['  INPUT X'],
 "if_read_1l":  ['  READ REC FROM F, K THEN X = 1 ELSE X = 2'],
 "compound":    ['  X = 1 ; Y = 2 ; Z = 3'],
 "on_gosub":    ['  ON X GOSUB 100, 200'],
 "pluseq":      ['  X = 0', '  X += 5'],
 "minuseq":     ['  X = 0', '  X -= 5'],
 "null_stmt":   ['  NULL'],
}
def w(n,l):
    b=list(PRE)
    while len(b)<9: b.append("*")
    b+=l
    while len(b)<PAD-1: b.append("*")
    b.append("END")
    open(os.path.join(OUT,n),"w",newline="\n").write("\n".join(b)+"\n")
os.makedirs(OUT,exist_ok=True)
for f in os.listdir(OUT): os.remove(os.path.join(OUT,f))
for n,l in C.items(): w(n,l)
print(f"wrote {len(C)}")
