# Project Context: UniData / UniBasic Application

This repository contains general UniData utilities. All backend logic is written in UniBasic. Follow these operational constraints,
structural rules, and compilation pipelines strictly.

---

## 1. Environment & Architecture Overview

* **Platform:** Rocket Software UniData (MultiValue database).
* **Data Model:** Non-relational, MultiValue (Attribute, Value, SubValue marks apply).
* **The VOC File:** Every file, paragraph, sentence, and cataloged program must have a pointer entry in the local `VOC` file.
* **File Structure:** Source code resides in directory-type files (e.g., `BP` or `SRC`).
* Data files use a dictionary (`DICT filename`) and a data payload component (`DATA filename`).

---

## 2. Coding Standards & Constraints

* **Syntax Case:** UniBasic keywords, system variables, and built-in functions MUST be written in UPPERCASE (e.g., `OPEN`, `READ`,
`WRITE`, `LOOP`, `REMOVE`, `CRT`).

* **Source Editing:** Source files are treated as standard Unix/Windows text files when edited externally, but must maintain
standard UniBasic line-structure conventions.

* **Program Structure:** Each program must have a clear entry point and follow a modular design, with subroutines and functions
defined for reusable logic.

* **Empty Lines:** Empty lines are not allowed in source files. Use comments `*\n` to separate logical sections instead.

---

## 3. Toolchain & Commands (How to Compile and Run)

When executing tasks or generating deployment scripts, use the following UniData commands.  We can assume that the `udt`
command-line tool is available for executing UniData commands from the shell and that a pointer has been created in the `VOC` file
for the source file (e.g., `SIMBIAN.BP`).

## Compilation To compile a UniBasic program, cd to where the Unidata account resides and use the `BASIC` command specifying the
source file and the record/program name, -Z2 flag to include debug symbols:

```bash
cd /usr/ud83/demo && echo "BASIC SIMBIAN.BP MYPROGRAM -Z2" | udt
```

## Cataloging
To catalog a UniBasic program, use the `CATALOG` command. This step is necessary to make the program directly executable:

```bash
cd /usr/ud83/demo && echo "CATALOG SIMBIAN.BP MYPROGRAM DIRECT" | udt
```

## Running

To run a compiled UniBasic program, use the `RUN` command:

```bash
cd /usr/ud83/demo && echo "RUN SIMBIAN.BP MYPROGRAM" | udt
```

---
