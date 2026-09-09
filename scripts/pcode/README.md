# UniData UniBasic P-code: format notes + disassembler + decompiler

Programs compiled with `$BASICTYPE "P"` (e.g. `SIMBIAN.BP/STACK`) produce a
portable **p-code** object (`_STACK`) rather than native code.  There is no
public spec.  This directory reverse-engineers the format and provides tools.

* **[FORMAT.md](FORMAT.md)** — the reverse-engineered container + bytecode spec
  (header, pools, ~55 opcodes, the expression stack machine, the -Z2 tail).
* **`ud/`** — Python package:
  * `container.py` — loader (header, string pool, constant table, -Z2 tail)
  * `disasm.py` — opcode table + linear-sweep disassembler
  * `expr.py` — folds an expression instruction run into a precedence-aware tree
  * `structure.py` — reconstructs IF / FOR / LOOP block nesting
  * `decompile.py` — emits approximate UniBasic
* **`pdis.py`** — disassembler CLI.
* **`pdec.py`** — decompiler CLI.
* **`try.sh`** — compile a snippet and round-trip it in one shot.
* **probe harnesses** — differential analysis: compile minimal-pair programs,
  diff the objects, read off the encoding.
  * `probes/` + `gen_probes.py` + `run_probes.sh` — the general corpus
  * `exprlab/` — the expression matrix (operands, operators, functions, nesting)
  * `cflab/` — control-flow shapes (IF/FOR/LOOP/CASE/dynamic arrays)
  * `pcode_recon.py` / `pcode_diff.py` — generic structural probes for an
    unknown object

## Usage

```bash
cd scripts/pcode

# decompile  (left column = true source line; `!!` = statement not lifted)
./pdec.py ../../SIMBIAN.BP/_STACK
./pdec.py ../../SIMBIAN.BP/_STACK --stats
./pdec.py cflab/obj/_if_nested            # a probe

# disassemble
./pdis.py ../../SIMBIAN.BP/_STACK --src ../../SIMBIAN.BP/STACK | less

# try a fresh snippet end to end
./try.sh <<'EOF'
  FOR I = 1 TO 10
    IF I = 5 THEN PRINT 'five'
  NEXT I
EOF

# rebuild + recompile a probe corpus (needs udt + the PCLAB dir file)
python3 exprlab/gen.py && ACCOUNT=/usr/ud83/demo bash exprlab/run.sh
python3 exprlab/check.py                  # 53-54 / 54 decompile exactly
```

## What the decompiler recovers

**Reliably:** statement boundaries with true source line numbers; variable and
label names (from -Z2); GOTO / GOSUB / branch targets; `RETURN`, `STOP`,
`CALL`; all string / number literals; assignment; **full expressions** —
arithmetic, comparison, concatenation, `LEN/OCONV/ICONV/FIELD/COUNT/INDEX/TRIM/
NUM/SEQ/UPCASE/STR/SPACE/DCOUNT/SUBSTR`, nesting and precedence; `PRINT` / `CRT`;
`IF … THEN … [END ELSE …] END` with nesting; `FOR v = a TO b [STEP s] … NEXT`;
`LOOP … REPEAT` with a trailing `UNTIL`; `AND`/`OR` conditions; bare-variable
and `NOT(…)` conditions; dynamic-array `A<s1[,s2]> = v` and `A<s>` reads.

**Approximate / flagged:** `BEGIN CASE` (emitted as an IF/ELSE chain);
`LOOP` with a leading `WHILE`; `ON GOSUB`/`ON GOTO` and a few rare opcodes
(printed as `!! line N` with raw mnemonics — nothing is dropped);
compound source lines; big-object `-Z2` label names (GOSUB targets show as
`L_<word>`).

On `_STACK` (4390 source lines) ~99% of statements lift to a concrete line,
most of them now real UniBasic.  See FORMAT.md "Known gaps" for what remains.

## Lab setup

`run_probes.sh` / `exprlab/run.sh` / `cflab/run.sh` compile through a directory
file `PCLAB` pointing at `lab/`.  Create it once from a UniData shell:

```
BASIC BP MKVOC     ;* 3-line program: OPEN 'VOC'; write "DIR"/<abs path>/"D_VOC" to 'PCLAB'
RUN   BP MKVOC
```

`lab/`, `objects/`, `*/obj/`, `work/` are git-ignored.
