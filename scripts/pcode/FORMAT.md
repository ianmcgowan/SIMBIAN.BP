# UniData UniBasic P-code object format

Reverse-engineered from UniData 8.3 (Build 2000) by differential compilation of
minimal-pair probes plus analysis of `_STACK` (4390-line real program).  No
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

| word | mnemonic | operands | meaning |
|------|----------|----------|---------|
| `0x00CB` | STMT | line:u16 | source-line marker; begins every statement |
| `0x0000` | HALT | — | zero padding / end |
| `0x000B` | RETURN | 0:u16 | RETURN from GOSUB / subroutine |
| `0x0010` | PUSH.C | cidx:u16 | push constant #cidx |
| `0x0011` | PUSH.C2 | cidx:u16 | push constant (string / concat context) |
| `0x0016` | NEG | 0:u16 | unary minus |
| `0x001A`..`0x001F` | CMP.* | — | `=` `#` `<=` `<` `>=` `>` (value context) |
| `0x0021` | EXPR.END | — | end of an expression |
| `0x002C` | PRINT | nitems:u16 | emit print list to the pushed channel |
| `0x0037` | FN.LEN | — | LEN() |
| `0x0042` | FN.OCONV | — | OCONV() |
| `0x0071` | INPUT | — | INPUT statement |
| `0x008F` | OPEN | mode:u16 | OPEN ... TO |
| `0x0091` | READ | mode:u16 | READ / READU / etc |
| `0x00A9` | CALL.NAME | argc:u16 | CALL: name is constant #0, argc arguments follow |
| `0x00B7` | CALL.GO | 0:u16 | invoke after pushing args |
| `0x00BE` | SUB.PROLOG | 3×u16 | subroutine entry (arg count in 3rd word) |
| `0x00E2` | FN.FIELD | — | FIELD() |
| `0x00E4` | BINOP | char:u16 | binary op; operand is the operator's ASCII code (`+ - * / :` `^`) |
| `0x0115` | STOP | 0:u16 | STOP |
| `0x0151` | CMP.VV | mode + words | compare var vs var (feeds a following CMP.*) |
| `0x0152` | EXPR | mode + words | evaluate expression into a variable slot |
| `0x0155` | ARG.BIND | 2×u16 | bind a subroutine parameter |
| `0x0159` | ASSIGN | mode,dst,src | simple assignment |
| `0x015A` | FOR.PREP | 2×u16 | FOR loop setup |
| `0x015B` | BRF | word:u16 | branch if false → word offset |
| `0x015C` | GOSUB | word:u16 | GOSUB → word offset |
| `0x015D` | GOTO | word:u16 | GOTO → word offset |
| `0x0163` | LOOP.BACK | word:u16 | LOOP/REPEAT back-edge |
| `0x0167` | FOR.NEXT | word:u16 | NEXT: test/increment → loop head |
| `0x01C6` | AND.SC | word:u16 | short-circuit AND branch |
| `0x01C8` | AND.MERGE | word:u16 | short-circuit merge point |
| `0x01CB` | CALL.PREP | 0:u16 | begin a CALL |
| `0x0004` | FOR.INIT | 3×u16 | FOR loop counter init |

### ASSIGN / EXPR operand modes (partially decoded)

The word after the opcode is a `mode` whose low byte selects the addressing
form and whose high byte carries per-operand var/const bits:

| mode low | context |
|---------:|---------|
| `0x12` | ASSIGN, source is a constant |
| `0x22` | ASSIGN source is a variable; or EXPR with all-constant operands |
| `0x32` | EXPR comparison, `var <cmp> const` |
| `0x42` | EXPR with an operator; high byte ≈ operand descriptor (`0x04` const+const, `0x06` var+const, `0x4a` var+var, `0x02` single var) |

For `ASSIGN`/`EXPR` the second word is the **destination variable slot** (for a
comparison EXPR it doubles as operand 1).  The exact operand-wiring for
multi-term expressions is **not fully recovered** — the decompiler renders these
with a `;* expr approx` marker.

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

* multi-term expression operand identity (which slot / which constant)
* dynamic-array assignment `A<n> = x` (`<-1>` append etc.)
* `FOR` loop bounds
* `BEGIN CASE`, `LOOP`/`WHILE` full structure (targets are recovered; keywords
  are approximate)
* header `+0x08`, `+0x0C` exact semantics
