# UniData UniBasic P-code object format

Reverse-engineered from UniData 8.3 (Build 2000) by differential compilation of
minimal-pair probes plus analysis of `_STACK` (4390-line real program); ~68 opcodes mapped.  No
vendor documentation was used or exists publicly.  Everything here is empirical
and may be incomplete; the tools degrade gracefully where it is.

A program compiled with `$BASICTYPE "P"` (`BASIC file prog`, optionally `-Z2`)
produces an object record named `_prog` in the same directory file.

## File layout

```
offset                     section
0x00                       header (32 bytes, little-endian)
0x20                       string / constant pool      (header.pool_len bytes)
0x20 + pool_len            constant descriptor table    (header.n_const * 16)
   "   + n_const*16        p-code instruction stream    (header.code_len bytes)
EOF - header.dbg_len       -Z2 debug tail               (header.dbg_len bytes)
```

All multi-byte integers are little-endian.

### Header (32 bytes)

| off | type | meaning |
|----:|------|---------|
| 0x00 | u16 | magic, always `0x013F` |
| 0x02 | u16 | `0xFFFF` for a main program; otherwise the SUBROUTINE argument count |
| 0x04 | u16 | format marker, `0x0070` on 8.3 |
| 0x06 | u16 | flags: `& 2` set when compiled `-Z2` (debug tail present) |
| 0x08 | u32 | 0 (unknown / unused in everything observed) |
| 0x0C | u16 | 1 when the program has variables, else 0 (approx) |
| 0x10 | u16 | `n_const` — number of 16-byte constant records |
| 0x12 | u16 | 1 |
| 0x14 | u32 | `pool_len` — byte length of the string pool |
| 0x18 | u32 | `dbg_len` — byte length of the -Z2 debug tail (0 if none) |
| 0x1C | u32 | `code_len` — byte length of the p-code segment |

### String / constant pool

A blob of NUL-terminated byte strings, appended in first-use order, padded with
NULs to a multiple of 16.  **Every literal is stored as text** — numbers,
strings, `@AM`, dates, `-1`.  Type is not recorded here; the VM coerces at
runtime.

### Constant descriptor table

`n_const` records of 16 bytes:

| off | type | meaning |
|----:|------|---------|
| 0x00 | u16 | `kind`: 4 = string literal, 5 = numeric literal |
| 0x02 | u16 | `length` — byte length of the literal in the pool |
| 0x04 | u32 | `pool_off` — offset of the literal within the pool |
| 0x08 | u32 | `aux` — for kind 5, the numeric value (`0xFFFFFFFF` == -1); else 0 |
| 0x0C | u32 | 0 |

The p-code refers to a constant by its **record index** (0-based).  Index 0 is
frequently the output-channel marker: `"-1"` = PRINT (terminal), `"-2"` = CRT.

### -Z2 debug tail

A flat run of NUL-terminated fields, logically `name\0value\0` pairs:

* **variable**: `NAME \0 <decimal first-seen source line> \0`, sorted
  alphabetically.  Does **not** encode the compiler's variable slot numbers;
  recover slot→name by joining first-seen line against the stream (the
  decompiler does this).
* **label**: `L<NAME> \0 <decimal WORD offset> \0` — the leading `L` is a
  marker, not part of the name.  Multiply the value by 2 for a byte offset into
  the code segment.  A variable whose name genuinely starts with `L` is
  disambiguated by whether the value lands on an instruction boundary.

There is **no source-line → offset table** in `-Z2`; that information is instead
inline in the code stream as STMT markers (below), present with or without
`-Z2`.

## P-code instruction stream

A sequence of 16-bit words.  The first word of an instruction is the opcode;
operands are further 16-bit words.  Most opcodes have a fixed operand count;
`EXPR`/`CMP.VV` are variable and are parsed by consuming words until the next
operator/terminator opcode byte.

**Jump operands are word offsets** from the start of the code segment
(`byte = word * 2`).

### Opcodes identified

Recovered from the probe corpora (`probes/`, `exprlab/`, `cflab/`).  Jump
operands are **word** offsets from the code-segment start (byte = word*2).

| word | mnemonic | operand words | meaning |
|------|----------|:---:|---------|
| `0x0000` | HALT | 0 | zero padding / end of segment |
| `0x0004` | FOR.INIT | 3 | FOR counter init (flag, loopvar slot, 0) |
| `0x000B` | RETURN | 1 | RETURN |
| `0x000F` | FN.SUBSTR | 0 | A[start,len] |
| `0x0010` | PUSH.C | 1 | push constant #arg |
| `0x0011` | PUSH.C2 | 1 | push constant (string ctx) |
| `0x0016` | NEG | 0 | unary minus |
| `0x001A` | CMP.EQ | 0 | = (value and IF context alike) |
| `0x001B` | CMP.NE | 0 | # |
| `0x001C` | CMP.GT | 0 | > |
| `0x001D` | CMP.LT | 0 | < |
| `0x001E` | CMP.GE | 0 | >= |
| `0x001F` | CMP.LE | 0 | <= |
| `0x0021` | EXPR.END | 0 | end of an expression |
| `0x0022` | OPADD | 1 | compound assign X op= v; arg = operator ASCII |
| `0x002C` | PRINT | 1 | emit print list; arg = item count |
| `0x002D` | EXTRACT | 0 | A<f,v,s> dynamic-array read |
| `0x002E` | NOT | 0 | logical NOT |
| `0x0030` | FN.COUNT | 0 | COUNT() |
| `0x0035` | FN.STR | 0 | STR() |
| `0x0036` | FN.SPACE | 0 | SPACE() |
| `0x0037` | FN.LEN | 0 | LEN() |
| `0x003C` | FN.INDEX | 0 | INDEX() |
| `0x0042` | FN.OCONV | 0 | OCONV() |
| `0x0046` | FN.CHAR | 0 | CHAR() |
| `0x0049` | FN.SEQ | 0 | SEQ() |
| `0x004A` | FN.ABS | 0 | ABS() |
| `0x004E` | FN.INT | 0 | INT() |
| `0x004F` | FN.NUM | 0 | NUM() |
| `0x0055` | FN.DATE | 0 | DATE() |
| `0x0056` | FN.TIME | 0 | TIME() |
| `0x0066` | FN.ICONV | 0 | ICONV() |
| `0x0071` | INPUT | 0 | INPUT statement |
| `0x008A` | REPLACE | 1 | A<..> = v dynamic-array store; arg = subscript count |
| `0x008D` | MATREAD | 1 | MATREAD .. FROM |
| `0x008E` | MATWRITE | 1 | MATWRITE .. ON |
| `0x008F` | OPEN | 1 | OPEN <file> TO <var> [.. ELSE] |
| `0x0091` | READ | 1 | READ .. FROM .. [THEN/ELSE] |
| `0x0092` | WRITE | 1 | WRITE .. ON .. |
| `0x0093` | READV | 1 | READV .. FROM .., field |
| `0x0094` | WRITEV | 1 | WRITEV .. ON .., field |
| `0x0095` | DELETE | 1 | DELETE <file>, <key> |
| `0x00A9` | CALL.NAME | 1 | CALL: name is const #0, arg = number of arguments |
| `0x00B7` | CALL.GO | 1 | invoke after args pushed |
| `0x00BE` | SUB.PROLOG | 3 | subroutine entry; arg count in 3rd word |
| `0x00CB` | STMT | 1 | statement marker; operand = source line |
| `0x00D0` | FN.UPCASE | 0 | UPCASE() |
| `0x00E2` | FN.FIELD | 0 | FIELD() |
| `0x00E4` | BINOP | 1 | binary op; arg = operator ASCII code |
| `0x0115` | STOP | 1 | STOP |
| `0x011C` | FN.TRIM | 1 | TRIM(); arg = variant |
| `0x0142` | PUSH.V | 1 | push variable slot #arg |
| `0x0151` | CMP.VV | var | var <cmp> var: mode + inline operands |
| `0x0152` | EXPR | var | evaluate expression: mode + [dst] + 1-2 inline operands + token stream |
| `0x0155` | ARG.BIND | 2 | bind a subroutine parameter |
| `0x0159` | ASSIGN | 3 | simple assignment (mode, dst, src) |
| `0x015A` | FOR.PREP | 2 | FOR setup (start mode, start ref) |
| `0x015B` | BRF | 1 | branch if false -> word offset |
| `0x015C` | GOSUB | 1 | GOSUB -> word offset |
| `0x015D` | GOTO | 1 | GOTO -> word offset |
| `0x0163` | LOOP.BACK | 1 | LOOP bottom marker |
| `0x0167` | FOR.NEXT | 1 | NEXT: test / step / branch |
| `0x01A9` | FN.DCOUNT | 1 | DCOUNT() |
| `0x01C6` | AND.SC | 1 | short-circuit AND (branch if false) |
| `0x01C7` | OR.SC | 1 | short-circuit OR (branch if true) |
| `0x01C8` | AND.MERGE | 0 | AND merge point |
| `0x01C9` | OR.MERGE | 0 | OR merge point |
| `0x01CB` | CALL.PREP | 1 | begin a CALL |

### ASSIGN / EXPR / CMP.VV operand modes

Both `EXPR` (0x0152) and `CMP.VV` (0x0151) begin with a `mode` word, then an
optional `dst` variable slot, then the first one or two operands inline; the
rest of the expression follows as ordinary instructions (a stack machine --
see `ud/expr.py`).

* `dst` present when opcode is 0x0152 and mode low byte is **not** 0x12/0x32
  (those two are the no-result *condition* forms).
* operand count: 2 when it is a condition or mode high byte >= 0x04, else 1.
* **op1 is a variable** when mode low byte is 0x42 or 0x32; a constant for
  0x22 / 0x12.  (For 0x0151 both inline operands are always variables.)
* **op2 is a variable** when `mode & 0x4000`, else a constant.

Simple `ASSIGN` (0x0159) is `(mode, dst, src)`: mode low byte 0x12 = constant
source, 0x22 = variable source.  Concatenation compiles to `PUSH.C2 <dst>`
followed by `ASSIGN` with mode high byte 0x03.

Expression token stream (after the inline operands, until `EXPR.END`):
`PUSH.V` / `PUSH.C` push; `0x0142` pushes a continuation variable; `BINOP`
and `CMP.*` pop 2; `NEG` / `NOT` pop 1; `FN.*` pop their arity; `EXTRACT`
pops 2.  Operands and operators are emitted in an order that already respects
UniBasic precedence ( `:` < `+ -` < `* /` < `^` ).

### Statement shape

```
STMT <line>
<statement body ...>
[0x0000 padding to the next even/aligned boundary]
```

`PRINT X` compiles to: `PUSH.C <channel>` · `PRINT <nitems>` · `PUSH.C <item>` ·
padding.  A trailing `01 00` in the pad means "no newline" (`PRINT X:`).

`IF cond THEN body` compiles to: evaluate `cond` · `CMP.*` · `BRF past-body` ·
`body` · `GOTO past-body`.  For `var <op> var` the compiler sometimes
canonicalises the comparison (e.g. emits `<=` for a source `>`); the decompiler
flags this.

## Known gaps

* `BEGIN CASE` renders as an `IF / END ELSE` chain (correct, not idiomatic)
* `LOOP` with a leading `WHILE` (test before the body) is not yet structured
* `ON GOSUB` / `ON GOTO` (0x0166) and a handful of rarer opcodes still print
  as `!! line N` with raw mnemonics
* compound source lines (several statements on one line) can mis-group
* big-object `-Z2` label names: STACK's label table uses an offset convention
  the small probes do not exercise, so its GOSUB targets show as `L_<word>`
* header `+0x08`, `+0x0C` exact semantics
