# UniData UniBasic P-code: format notes + disassembler + decompiler

Programs compiled with `$BASICTYPE "P"` (e.g. `SIMBIAN.BP/STACK`) produce a
portable **p-code** object (`_STACK`) rather than native code.  There is no
public spec.  This directory reverse-engineers the format and provides tools.

* **[FORMAT.md](FORMAT.md)** — the reverse-engineered container + bytecode spec.
* **`ud/`** — Python package: `container.py` (loader), `disasm.py` (opcode
  table + linear sweep), `decompile.py` (best-effort lifter).
* **`pdis.py`** — disassembler CLI.
* **`pdec.py`** — decompiler CLI.
* **`gen_probes.py` / `run_probes.sh` / `probes/`** — the differential-analysis
  harness: ~100 minimal-pair UniBasic programs, each exactly 40 lines so the
  `-Z2` line table never confounds a code change.  Compile a pair, diff the
  objects, read off the encoding of the one thing that differs.
* **`pcode_recon.py` / `pcode_diff.py`** — earlier generic structural probes,
  still useful on an unknown object.

## Usage

```bash
# regenerate + compile the probe corpus (needs udt + the PCLAB dir file)
python3 gen_probes.py
ACCOUNT=/usr/ud83/demo ./run_probes.sh

# disassemble
./pdis.py ../../SIMBIAN.BP/_STACK --src ../../SIMBIAN.BP/STACK | less

# decompile  (left column = true source line)
./pdec.py ../../SIMBIAN.BP/_STACK
./pdec.py objects/z2/_F10_GOSUB          # a probe
./pdec.py ../../SIMBIAN.BP/_STACK --stats
```

## What the decompiler recovers

Reliably: statement boundaries with **true source line numbers**; variable and
label **names** (from `-Z2`); `GOTO`/`GOSUB`/branch **targets**; `RETURN`,
`STOP`, simple assignment, `PRINT`/`CRT` of literals, `CALL` targets; binary and
comparison **operators**; all string/number **literals** (the pool is intact).

Approximately (flagged with `;*` in the output): operand identity inside
multi-term expressions, comparison sense for some `var <op> var` tests, block
nesting (emitted flat with explicit labels), `FOR` bounds, dynamic-array
assignment.  Statements that cannot be lifted are printed as `!! line N: <raw
mnemonics>` so nothing is dropped.

On `_STACK` (4390 source lines) ~90% of statements lift to a concrete line;
the rest are marked.  This is a "correct skeleton, ugly details" decompiler:
control flow, names, I/O, calls and literals come back; gnarly expressions you
reconstruct from context.

## Setup notes

`run_probes.sh` compiles through a directory file `PCLAB` pointing at `lab/`.
Create it once from a UniData shell:

```
BASIC BP MKVOC     ;* a 3-line program: OPEN 'VOC'; write DIR / <abs path> / D_VOC ; to 'PCLAB'
RUN   BP MKVOC
```

`lab/`, `objects/`, `work/` are git-ignored.
