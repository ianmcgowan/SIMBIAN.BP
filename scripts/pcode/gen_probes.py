#!/usr/bin/env python3
"""Generate a corpus of minimal-pair UniBasic probes.

Every probe is exactly PAD lines long, padded with '*' comment lines, so that
the -Z2 line-number table is identical across a pair and only the code section
moves. Each entry is (name, [body lines]); diffing the compiled objects of two
related probes isolates the encoding of the one construct that differs.
"""
import os
import sys

PAD = 40
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'probes')

# ---- probe bodies -------------------------------------------------------
# Grouped by what each pair isolates. Keep bodies short; keep pairs minimal.
PROBES = {
 # baseline
 'B00_EMPTY':            [],
 'B01_STOP':             ['STOP'],
 'B02_END_ONLY':         [],

 # --- literals: strings ---
 'S01_PRINT_A4':         ["PRINT 'AAAA'"],
 'S02_PRINT_A5':         ["PRINT 'AAAAA'"],           # vs S01: +1 char
 'S03_PRINT_B4':         ["PRINT 'BBBB'"],            # vs S01: same len, diff bytes
 'S04_PRINT_A4_TWICE':   ["PRINT 'AAAA'", "PRINT 'AAAA'"],   # vs S01: repeat -> dedupe?
 'S05_PRINT_EMPTY':      ["PRINT ''"],
 'S06_PRINT_A4_A4B':     ["PRINT 'AAAA'", "PRINT 'AAAAB'"],  # distinct literals

 # --- literals: integers ---
 'N01_PRINT_0':          ['PRINT 0'],
 'N02_PRINT_1':          ['PRINT 1'],
 'N03_PRINT_2':          ['PRINT 2'],
 'N04_PRINT_127':        ['PRINT 127'],
 'N05_PRINT_128':        ['PRINT 128'],
 'N06_PRINT_255':        ['PRINT 255'],
 'N07_PRINT_256':        ['PRINT 256'],
 'N08_PRINT_65535':      ['PRINT 65535'],
 'N09_PRINT_65536':      ['PRINT 65536'],
 'N10_PRINT_NEG1':       ['PRINT -1'],
 'N11_PRINT_BIGNUM':     ['PRINT 16777216'],
 'N12_PRINT_FLOAT':      ['PRINT 1.5'],

 # --- assignment / variables ---
 'V01_ASSIGN_1':         ['A = 1'],
 'V02_ASSIGN_2':         ['A = 2'],                   # vs V01: rhs value
 'V03_ASSIGN_TWO_VARS':  ['A = 1', 'B = 1'],          # vs V01: +1 var, +1 stmt
 'V04_ASSIGN_SELF':      ['A = 1', 'B = A'],          # var-to-var load
 'V05_ASSIGN_STR':       ["A = 'AAAA'"],
 'V06_THREE_VARS':       ['A = 1', 'B = 2', 'C = 3'],
 'V07_ASSIGN_ADD':       ['A = 1', 'B = A + 1'],
 'V08_ASSIGN_SUB':       ['A = 1', 'B = A - 1'],
 'V09_ASSIGN_MUL':       ['A = 1', 'B = A * 2'],
 'V10_ASSIGN_DIV':       ['A = 1', 'B = A / 2'],
 'V11_ASSIGN_CAT':       ["A = 'X'", "B = A : 'Y'"],
 'V12_ASSIGN_ADDVAR':    ['A = 1', 'C = 2', 'B = A + C'],   # vs V07: operand is var not lit

 # --- comparison / boolean ---
 'C01_EQ':               ['A = 1', 'B = A = 1'],
 'C02_NE':               ['A = 1', 'B = A # 1'],
 'C03_LT':               ['A = 1', 'B = A < 1'],
 'C04_GT':               ['A = 1', 'B = A > 1'],
 'C05_LE':               ['A = 1', 'B = A <= 1'],
 'C06_GE':               ['A = 1', 'B = A >= 1'],
 'C07_AND':              ['A = 1', 'B = A AND 1'],
 'C08_OR':               ['A = 1', 'B = A OR 1'],

 # --- control flow ---
 'F01_IF_1LINE':         ['A = 1', "IF A = 1 THEN PRINT 'AAAA'"],
 'F02_IF_ELSE_1LINE':    ['A = 1', "IF A = 1 THEN PRINT 'AAAA' ELSE PRINT 'BBBB'"],
 'F03_IF_BLOCK':         ['A = 1', 'IF A = 1 THEN', "  PRINT 'AAAA'", 'END'],
 'F04_IF_NESTED':        ['A = 1', 'IF A = 1 THEN', '  IF A = 1 THEN',
                          "    PRINT 'AAAA'", '  END', 'END'],
 'F05_FOR_NEXT':         ['FOR I = 1 TO 3', "  PRINT 'AAAA'", 'NEXT I'],
 'F06_FOR_STEP':         ['FOR I = 1 TO 9 STEP 2', "  PRINT 'AAAA'", 'NEXT I'],
 'F07_LOOP_REPEAT':      ['A = 1', 'LOOP', '  A = A + 1',
                          'UNTIL A > 3', 'REPEAT'],
 'F08_LOOP_WHILE':       ['A = 1', 'LOOP', 'WHILE A < 3', '  A = A + 1', 'REPEAT'],
 'F09_GOTO':             ['GOTO SKIP', "PRINT 'AAAA'", 'SKIP:', "PRINT 'BBBB'"],
 'F10_GOSUB':            ['GOSUB SUB1', 'STOP', 'SUB1:', "PRINT 'AAAA'", 'RETURN'],
 'F11_GOSUB_TWICE':      ['GOSUB SUB1', 'GOSUB SUB1', 'STOP', 'SUB1:',
                          "PRINT 'AAAA'", 'RETURN'],
 'F12_BEGIN_CASE':       ['A = 1', 'BEGIN CASE', '  CASE A = 1', "    PRINT 'AAAA'",
                          '  CASE A = 2', "    PRINT 'BBBB'", 'END CASE'],

 # --- builtin functions ---
 'X01_LEN':              ["A = 'AAAA'", 'B = LEN(A)'],
 'X02_TRIM':             ["A = 'AAAA'", 'B = TRIM(A)'],
 'X03_OCONV':            ["A = 'AAAA'", "B = OCONV(A, 'MCU')"],
 'X04_ICONV':            ["A = 'AAAA'", "B = ICONV(A, 'MCU')"],
 'X05_FIELD':            ["A = 'A,B,C'", "B = FIELD(A, ',', 2)"],
 'X06_COUNT':            ["A = 'A,B,C'", "B = COUNT(A, ',')"],
 'X07_INDEX':            ["A = 'ABC'", "B = INDEX(A, 'B', 1)"],
 'X08_SUBSTR':           ["A = 'ABCDEF'", 'B = A[2,3]'],
 'X09_STR':              ["B = STR('A', 5)"],
 'X10_DQUOTE':           ["A = 'AAAA'", 'B = DQUOTE(A)'],

 # --- I/O ---
 'IO1_CRT':              ["CRT 'AAAA'"],
 'IO2_PRINT_ON':         ["PRINT ON 0 'AAAA'"],
 'IO3_INPUT':            ['INPUT A'],
 'IO4_OPEN_READ':        ["OPEN 'VOC' TO F ELSE STOP", "READ R FROM F, 'X' THEN NULL"],
 'IO5_WRITE':            ["OPEN 'VOC' TO F ELSE STOP", "R = 'X'", "WRITE R ON F, 'Y'"],
 'IO6_PRINT_NOLF':       ["PRINT 'AAAA':"],

 # --- subroutine shape (line 3 = SUBROUTINE header) ---
 'R01_SUB_NOARG':        ('SUBROUTINE R01.SUB', []),
 'R02_SUB_1ARG':         ('SUBROUTINE R02.SUB(A)', []),
 'R03_SUB_2ARG':         ('SUBROUTINE R03.SUB(A, B)', []),
 'R04_SUB_1ARG_USE':     ('SUBROUTINE R04.SUB(A)', ['A = 1']),
 'R05_CALL':             [' CALL R01.SUB'],
 'R06_CALL_1ARG':        [" CALL R02.SUB('AAAA')"],

 # --- @-variables & system ---
 'AT1_AM':               ['A = @AM'],
 'AT2_VM':               ['A = @VM'],
 'AT3_DATE':             ['A = DATE()'],
 'AT4_TIME':             ['A = TIME()'],
 'AT5_SYSTEM':           ['A = SYSTEM(2)'],

 # --- arrays ---
 'AR1_DIM':              ['DIM A(10)', 'A(1) = 1'],
 'AR2_MAT_ASSIGN':       ['DIM A(10)', 'MAT A = 0'],
 'AR3_DYNARR':           ["A = 'x'", 'A<2> = 1'],
 'AR4_DYNARR_VMS':       ["A = 'x'", 'A<2,3> = 1'],
 'M01_A_EQ_B':          ['A = 1', 'B = 1', 'X = A'],
 'M02_A_EQ_LIT':        ['X = 5'],
 'M03_A_PLUS_B':        ['A = 1', 'B = 1', 'X = A + B'],
 'M04_A_PLUS_LIT':      ['A = 1', 'X = A + 5'],
 'M05_LIT_PLUS_LIT':    ['X = 5 + 7'],
 'M06_A_PLUS_B_PLUS_C': ['A=1', 'B=1', 'C=1', 'X = A + B + C'],
 'M07_A_TIMES_B':       ['A = 1', 'B = 1', 'X = A * B'],
 'M08_PAREN':           ['A=1', 'B=1', 'C=1', 'X = (A + B) * C'],
 'M09_CAT3':            ["A='x'", "X = A : 'y' : 'z'"],
 'M10_CMP_IN_ASSIGN':   ['A = 1', 'X = A = 1'],
 'M11_FUNC_ASSIGN':     ["A = 'xx'", 'X = LEN(A)'],
 'M12_NESTED_FUNC':     ["A = 'x,y'", "X = LEN(FIELD(A, ',', 1))"],
 'G01_IF_A_EQ_1':       ['A = 1', 'IF A = 1 THEN', "  PRINT 'Y'", 'END'],
 'G02_IF_B_EQ_1':       ['B = 1', 'IF B = 1 THEN', "  PRINT 'Y'", 'END'],
 'G03_IF_A_EQ_2':       ['A = 1', 'IF A = 2 THEN', "  PRINT 'Y'", 'END'],
 'G04_IF_A_EQ_C':       ['A=1','C=1', 'IF A = C THEN', "  PRINT 'Y'", 'END'],
 'G05_IF_A_GT_C':       ['A=1','C=1', 'IF A > C THEN', "  PRINT 'Y'", 'END'],
}


def emit(name, spec):
    if isinstance(spec, tuple):
        header, body = spec
        lines = [f'* Probe {name}', '  $BASICTYPE "P"', header]
    else:
        body = spec
        lines = [f'* Probe {name}', '  $BASICTYPE "P"']
    lines += ['  ' + b if not b.startswith(('*', ' ')) else b for b in body]
    while len(lines) < PAD - 1:
        lines.append('*')
    lines.append('END')
    text = '\n'.join(lines) + '\n'
    for ln in lines:
        if len(ln) > 132:
            print(f'WARN {name}: line >132', file=sys.stderr)
    with open(os.path.join(OUT, name), 'w', newline='\n') as fh:
        fh.write(text)


def main():
    os.makedirs(OUT, exist_ok=True)
    # wipe old P-series probes from the first session, keep dir clean
    for f in os.listdir(OUT):
        if f.startswith(('P', 'B', 'S', 'N', 'V', 'C', 'F', 'X', 'I', 'R', 'A')):
            os.remove(os.path.join(OUT, f))
    for name, spec in PROBES.items():
        emit(name, spec)
    print(f'wrote {len(PROBES)} probes to {OUT} ({PAD} lines each)')


if __name__ == '__main__':
    main()
