# Reverse-engineering the UniData UniBasic P-code object format

`$BASICTYPE "P"` at the top of `STACK` and `STACK.EXT.COMM` selects Rocket's
portable p-code back end, so `_STACK` is a bytecode image rather than native
code. There is no published specification for it — searching turns up UniVerse
*hashed data file* internals (the `0xACEF` magic) and general MV file layout,
but nothing on the compiled BASIC object. Don't be misled by `ACEF`: that
belongs to data files, not to object code.

So the format has to be recovered empirically. This directory is the harness
for doing that.

## Why differential compilation

Staring at one 150 KB object gets you the string table and not much else. The
leverage comes from compiling programs that differ by *exactly one thing* and
diffing the objects — the bytes that move are the encoding of that one thing.

Two properties of this compiler make that unusually clean:

* We have the full source for a large real program (`STACK`, 4390 lines), so
  literals and variable names act as a Rosetta stone for locating the constant
  and symbol tables.
* `-Z2` is optional. Compiling identical source with and without it and diffing
  isolates the entire debug/line-number apparatus from the p-code proper. That
  is the first pair to run.

Every probe in `probes/` is **exactly 12 lines**, padded with `*` comments.
That matters: `-Z2` embeds a source-line table, so a pair differing in line
count would differ in the line table *and* the code, masking the thing you are
isolating. Keeping the line count fixed makes each pair a true single-variable
experiment. Preserve that if you add probes.

## Order of attack

1. **`_P01` with `-Z2` vs without.** Everything `-Z2` adds is debug info.
   Establishes the boundary between code and symbols, and usually reveals the
   section table because the section offsets shift by a known amount.
2. **`_P00_EMPTY` vs `_P01_PRINT_STR4`.** The smallest possible non-empty
   program. The inserted bytes are one complete `PRINT` statement: opcode,
   operand encoding, statement terminator.
3. **`_P01` vs `_P02`** (4-char vs 5-char literal). One extra byte tells you
   whether strings are counted or terminated and where the length lives.
4. **`_P04` vs `_P05`** (`PRINT 1` vs `PRINT 2`). Same-size diff — a single
   operand byte changes. That is the immediate-value encoding.
5. **`_P04` vs `_P06`** (`1` vs `1000`). If the object grows, integers are
   variable-width; if not, they are fixed-width.
6. **`_P07` vs `_P08`** (one vs two variables). The delta is one whole symbol
   table record — its size, and whether a count field in the header ticks up.
7. **`_P09` / `_P10` / `_P11`.** Branch, loop, and call. Jumps are the payoff:
   comparing the encoded target against the known byte offset of the label tells
   you whether addresses are absolute or relative and how wide they are.
8. **`_P12` vs `_P13`** (0-arg vs 2-arg `SUBROUTINE`). Finds the argument-count
   field in the header.

Only then point the recon tool at `_STACK` — by that stage you know what you're
looking at, and a real program exercises constructs the probes don't.

## Tools

```bash
# Compile the whole corpus, both ways (needs udt and the UniData account)
ACCOUNT=/usr/ud83/demo ./run_probes.sh

# Structural recon on a single object; --source turns the source into a key
./pcode_recon.py objects/z2/_STACK --source ../../SIMBIAN.BP/STACK

# The workhorse: what changed between two probes
./pcode_diff.py objects/z2/_P00_EMPTY objects/z2/_P01_PRINT_STR4
./pcode_diff.py objects/z2/_P01_PRINT_STR4 objects/noz2/_P01_PRINT_STR4
```

Once `pcode_recon.py` tells you where the code section starts, pass that to the
diff tool as `--body-start 0x<offset>`. Header words change on every recompile,
and skipping them turns a smeared diff into a clean "N bytes inserted here".

`pcode_recon.py` passes, in order: header hexdump; header words that are valid
file offsets (an increasing run of them is the section table); string extraction
with counted-vs-terminated detection; source literals located in the object;
source identifiers located in the object, with the gap histogram that reveals
symbol-record stride; monotonic small-integer runs bounded by the source line
count (the `-Z2` line table); and an entropy/printable map plus opcode histogram
to locate the code section.

## Getting an object file into a clone

`.gitignore` has `_*`, so compiled objects never reach a fresh clone — including
CI and remote sessions. To hand one over deliberately:

```bash
git add -f SIMBIAN.BP/_STACK          # or
base64 SIMBIAN.BP/_STACK > /tmp/_STACK.b64
```

A probe object is a few hundred bytes and pastes inline as a hexdump; `_STACK`
does not.
