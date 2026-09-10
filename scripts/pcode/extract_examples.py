#!/usr/bin/env python3
"""Extract UniBasic code examples from the UniData UniBasic Commands Reference.

Prerequisite:
    pdftotext -layout UniData_UniBasicCommandsRefGuide_V821.pdf /tmp/ubcmd_layout.txt
(or point UBCMD_TXT at that file).  Then:  python3 extract_examples.py

One example per file in examples/<COMMAND>_<nn>.bp.  Indentation in the PDF
alternates by page, so blocks are found by content: prose sentences separate
code blocks, a new subsection heading ends the Examples section, page numbers
and chapter banners are transparent.  Many examples are fragments (the guide
shows snippets, not whole programs) so not all compile standalone.
"""
import os, re

SRC = os.environ.get("UBCMD_TXT", "/tmp/ubcmd_layout.txt")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
START = 1624

HEAD = re.compile(r"^([$@!]?[A-Za-z][\w.]{0,30}(?:/[A-Za-z]+)*|\{\})\s*$")
PAGE = re.compile(r"^\s*\d{1,4}\s*$")
CHAP = re.compile(r"^\s*Chapter \d")
ENDSEC = re.compile(r"^\s*(Syntax|Synonyms?|Parameters?|Related commands?|"
                    r"Description|Remarks?|Emphasis|International|"
                    r"Return codes?|Examples?)\s*$")
PROSE = re.compile(
    r"^\s*(The |In the |In this |This |That |These |For (the|more|example)|"
    r"Assume|Suppose|Note:|Tip:|When |Where |If (you|the|expr|space)|You can|"
    r"Because |After |Before |Here |Consider |Given |Upon |With |As |To )")
SENTENCE = re.compile(r"[a-z]\s+\w+.*[a-z]\.\s*$")   # ...ends a lowercase sentence
KW = (r"PRINT|CRT|DISPLAY|INPUT|IF|FOR|NEXT|LOOP|REPEAT|WHILE|UNTIL|GOSUB|GOTO|"
      r"RETURN|CALL|SUBROUTINE|FUNCTION|OPENSEQ|OPEN|READU|READL|READV|READ|"
      r"READNEXT|WRITEU|WRITEV|WRITESEQ|WRITE|DELETE|LOCK|UNLOCK|MATREAD|"
      r"MATWRITE|MATPARSE|MATBUILD|MAT|DIM|COMMON|EQUATE|EQU|BEGIN CASE|CASE|"
      r"END CASE|END|ON|STOP|ABORT|CLEARSELECT|CLEARFILE|CLEARDATA|CLEAR|NULL|"
      r"LET|SELECT|CONVERT|PROMPT|ECHO|HUSH|PAGE|HEADING|FOOTING|SLEEP|RQM|"
      r"NAP|PRECISION|SEND|GETLIST|GET|CLOSE|FLUSH|BSCAN|DEFFUN|PROGRAM|"
      r"MAINPROGRAM|REM|LOCATE|FINDSTR|FIND|INS|DEL|SWAP|EXECUTE|PERFORM|"
      r"CHAIN|ENTER|BREAK|CONTINUE|RELEASE")
KWRE = re.compile(r"^\s*(?:" + KW + r")\b")
ASSIGN = re.compile(r"^\s*[A-Za-z@][\w.$]*\s*(?:<[^\n>]*>)?\s*(?:=|:=|\+=|-=)(?!=)")
LABEL = re.compile(r"^\s*(?=[A-Z0-9_.]{2,}:)[A-Za-z][\w.$]*:\s*(\*.*)?$")
COMMENT = re.compile(r"^\s*[*!]")
CODE_TAIL = re.compile(r'^\s*("|:|[<>=+*/-]|@\(|\)|\}|[A-Za-z][\w.$]* *(=|:=|\+=|"|<))')
CONT = re.compile(r"^\s*(THEN|ELSE|END|NEXT|REPEAT|UNTIL|WHILE|CASE|BEGIN|DO|"
                  r"AND|OR|ON ERROR|LOCKED|THEN NULL|ELSE NULL)\b")
ELLIPSIS = re.compile(r"^[\s.]*$")

DOCLINE = re.compile(
    r"\b(is a synonym|for (further|more) information|on page \d|"
    r"the following table|evaluates? to|command (enables?|does|produces?)|"
    r"statement (does|produces?)|returns? the|specifies?|"
    r"^\s*\w+ (is|are|command|statement|function|enables?|causes?) )", re.I)
LOOKSPROSE = re.compile(r"^[A-Za-z].*\b(the|is|are|of|to|in|that|this|which|"
                        r"when|returns?|command|statement)\b.*[a-z]\.?\s*$")

def codey(l):
    if COMMENT.match(l):
        return True                       # * / ! comments may hold anything
    if DOCLINE.search(l):
        return False
    if not (KWRE.match(l) or ASSIGN.match(l) or LABEL.match(l) or CONT.match(l)):
        return False
    # a keyword/assignment followed by an English sentence is doc prose
    words = l.split()
    lc = sum(1 for w in words if w[:1].islower())
    if len(words) >= 6 and lc >= 4 and l.rstrip().endswith((".", ":")) \
       and not ASSIGN.match(l):
        return False
    return True

def slug(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "CMD"

L = open(SRC, errors="replace").read().split("\n")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    os.remove(os.path.join(OUT, f))

def nnb(k):
    while k < len(L) and not L[k].strip():
        k += 1
    return L[k].strip() if k < len(L) else ""

cmd, in_ex = "MISC", False
block, blanks = [], 0
seen, count = {}, 0

def flush():
    global block, count
    b, block = block, []
    lines = [x for x in b if not ELLIPSIS.match(x)]
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and lines[0].strip() and not codey(lines[0]) \
            and not CODE_TAIL.match(lines[0]):
        lines.pop(0)
    while lines and lines[-1].strip() and not codey(lines[-1]) \
            and not CODE_TAIL.match(lines[-1]):
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    code = [x for x in lines if x.strip()]
    if len(code) < 1:
        return
    nc = sum(1 for x in code if codey(x))
    if nc < max(1, round(len(code) * 0.55)):
        return
    if any(SENTENCE.search(x) and not codey(x) for x in code):
        return
    ind = min(len(x) - len(x.lstrip()) for x in code)
    body = "\n".join((x[ind:] if x.strip() else "") for x in lines).strip("\n")
    body = re.sub(r"[ \t]+$", "", body, flags=re.M)
    if len(body) < 5:
        return
    if "\n" not in body and not (KWRE.match(body) or "PRINT" in body):
        return
    i = seen.get(cmd, 0) + 1
    seen[cmd] = i
    open(os.path.join(OUT, f"{slug(cmd)}_{i:02d}.bp"), "w",
         newline="\n").write(body + "\n")
    count += 1

for idx in range(START, len(L)):
    l = L[idx].rstrip("\n")
    s = l.strip()

    if CHAP.match(l) or PAGE.match(l) or re.match(r"^\s{40,}\S+\s*$", l):
        if block:
            blanks = 0
        continue

    if HEAD.match(l) and not ENDSEC.match(l) and s not in (
            "Parameters", "Examples", "Example", "Syntax", "Synonyms",
            "Synonym", "Description", "Remarks", "Note", "Tip",
            "Related", "Emphasis", "International"):
        nb = nnb(idx + 1)
        m2 = re.match(r"^The UniBasic\s+([$@]?[A-Za-z][\w./]*)", nb)
        if m2 or re.match(r"^(Use the |Use \w|\{\})", nb):
            flush()
            cmd = (m2.group(1) if m2 else s).rstrip(".")
            in_ex = False
            continue

    if re.match(r"^\s*Examples?\s*$", l):
        flush(); in_ex = True; blanks = 0
        continue

    if not in_ex:
        continue

    if not s:
        if block:
            blanks += 1
            if blanks >= 3:
                flush()
            else:
                block.append("")
        continue
    blanks = 0

    if ENDSEC.match(l) or re.match(r"^\s*Related commands?\s*$", l):
        flush(); in_ex = False
        continue

    cl = re.sub(r"^(\s*)\.\s+", r"\1", l)
    # split a keyword glued to trailing prose across a PDF column break
    mg = re.match(r"^(\s*(?:END(?:\s+ELSE)?|REPEAT|RETURN|NEXT\s+\w+))"
                  r"([A-Z][a-z].{6,})$", cl)
    if mg:
        cl = mg.group(1)
    if codey(cl):
        block.append(cl)
    elif block and CODE_TAIL.match(cl):
        block.append(cl)
    else:
        flush()

flush()
print(f"{count} examples from {len(seen)} commands -> {OUT}")
