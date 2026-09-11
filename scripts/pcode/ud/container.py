"""Parse the UniData UniBasic P-code object container ($BASICTYPE "P").

Layout, recovered empirically (see ../FORMAT.md):

    offset  size            section
    0x00    32              header
    0x20    hdr.pool_len     string/constant pool  (NUL-terminated strings)
    ...     hdr.n_const*16   constant descriptor table (16-byte records)
    ...     hdr.code_len     p-code instruction stream
    EOF-hdr.dbg_len          -Z2 debug tail (name\\0number\\0 pairs), optional

Header fields (little-endian):

    +0x00 u16  magic      always 0x013f
    +0x02 u16  argc       0xffff for a main program, else SUBROUTINE arg count
    +0x04 u16  fmt        always 0x0070 on 8.x  (format/version marker)
    +0x06 u16  flags      bit0|bit1 set (=3) when compiled -Z2, else 0
    +0x10 u16  n_const    number of 16-byte constant-table records
    +0x14 u32  pool_len   length of the string pool
    +0x18 u32  dbg_len    length of the -Z2 debug tail (0 if none)
    +0x1c u32  code_len   length of the p-code segment

Constant record (16 bytes):
    +0x00 u16  kind       4 = literal, 5 = sentinel/first row
    +0x02 u16  length     byte length of the literal in the pool
    +0x04 u32  pool_off   offset of the literal within the string pool
    +0x08 u32  aux        usually 0; small index on kind-5
    +0x0c u32  reserved   0

Everything the compiler knows about a literal's *type* is discarded: numbers,
strings, @AM, dates -- all are just bytes in the pool. The VM coerces at
runtime.  A decompiler therefore re-quotes anything that is not a bare number.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field


@dataclass
class Const:
    index: int
    kind: int            # 4 = string literal, 5 = integer literal, 6 = decimal literal
    text: bytes
    pool_off: int
    aux: int             # kind 5: the integer value (0xffffffff == -1); kind 6: 0

    @property
    def s(self) -> str:
        return self.text.decode("latin-1")

    @property
    def numeric(self) -> bool:
        return self.kind in (5, 6)

    def render(self) -> str:
        """How this literal should appear in decompiled source."""
        if self.kind in (5, 6):
            return self.s or "0"
        return "'" + self.s.replace("'", "''") + "'"


@dataclass
class Container:
    raw: bytes
    magic: int
    mode: str            # 'p' ($BASICTYPE "P") or 'u' (default) -- header byte +0x04
    argc: int            # 0xffff => main program
    flags: int
    n_const: int
    pool_len: int
    dbg_len: int
    code_len: int
    pool: bytes
    consts: list[Const]
    code: bytes
    code_file_off: int
    # -Z2 debug tail
    var_lines: dict[str, int] = field(default_factory=dict)   # VARNAME -> first source line
    labels: dict[int, str] = field(default_factory=dict)      # byte offset in code -> LABEL
    label_words: dict[str, int] = field(default_factory=dict)  # LABEL -> word offset

    @property
    def is_subroutine(self) -> bool:
        return self.argc != 0xFFFF

    @property
    def has_debug(self) -> bool:
        return bool(self.flags & 2)


def _parse_debug_tail(blob: bytes):
    """The tail is a flat run of NUL-terminated fields, logically name/value
    pairs.  Two kinds are interleaved:

        VARNAME \\0 <decimal first-line>   \\0
        L<LABEL> \\0 <decimal WORD offset> \\0     (L is a literal prefix marker)

    We tell them apart structurally: a label entry's name starts with 'L' and
    its value, taken as a word offset, lands on an even byte inside the code.
    But the cleaner signal is simply that variable first-lines are small and
    label offsets index the (large) code segment.  We keep both and let the
    caller decide; ambiguous 'L...' names (a real variable called LEFT) are
    disambiguated by whether the code actually has an instruction boundary at
    that offset.
    """
    fields = blob.split(b"\x00")
    # drop trailing empty from a final NUL
    while fields and fields[-1] == b"":
        fields.pop()
    pairs = []
    it = iter(range(0, len(fields) - 1, 2))
    for i in it:
        name = fields[i]
        val = fields[i + 1]
        if not val.isdigit():
            # desync (a name contained a NUL we mis-split, or odd tail) -- skip one
            continue
        pairs.append((name.decode("latin-1"), int(val)))
    return pairs


def load(data: bytes) -> Container:
    if len(data) < 32:
        raise ValueError("too small to be a p-code object")
    magic = struct.unpack_from("<H", data, 0)[0]
    if magic != 0x013F:
        raise ValueError(f"bad magic 0x{magic:04x} (expected 0x013f)")

    mode = chr(data[0x04]) if data[0x04] in (0x70, 0x75) else "u"  # 'p' / 'u'
    argc = struct.unpack_from("<H", data, 0x02)[0]
    flags = struct.unpack_from("<H", data, 0x06)[0]
    n_const = struct.unpack_from("<H", data, 0x10)[0]
    pool_len = struct.unpack_from("<I", data, 0x14)[0]
    dbg_len = struct.unpack_from("<I", data, 0x18)[0]
    code_len = struct.unpack_from("<I", data, 0x1C)[0]

    pool_off = 0x20
    pool = data[pool_off:pool_off + pool_len]

    ct_off = pool_off + pool_len
    consts: list[Const] = []
    for i in range(n_const):
        rec = data[ct_off + i * 16: ct_off + i * 16 + 16]
        if len(rec) < 16:
            break
        kind, length = struct.unpack_from("<HH", rec, 0)
        p_off, aux = struct.unpack_from("<II", rec, 4)
        text = b""
        if kind in (4, 5, 6) and p_off + length <= len(pool):
            text = pool[p_off:p_off + length]
        consts.append(Const(i, kind, text, p_off, aux))

    code_off = ct_off + n_const * 16
    code = data[code_off:code_off + code_len]

    c = Container(
        raw=data, magic=magic, mode=mode, argc=argc, flags=flags, n_const=n_const,
        pool_len=pool_len, dbg_len=dbg_len, code_len=code_len,
        pool=pool, consts=consts, code=code, code_file_off=code_off,
    )

    if dbg_len and len(data) >= dbg_len:
        tail = data[len(data) - dbg_len:]
        pairs = _parse_debug_tail(tail)
        # First pass: the largest STMT line number bounds "this is a source
        # line" vs "this is a code offset".
        max_line = 0
        p = 0
        while p + 4 <= len(code):
            if code[p] == 0xCB and code[p + 1] == 0x00:
                max_line = max(max_line, int.from_bytes(code[p + 2:p + 4], "little"))
            p += 2
        for name, num in pairs:
            # A label entry: 'L'-prefixed name, and its value read as a word
            # offset lands on a STMT marker and is past the last source line
            # (so it cannot be mistaken for a variable's first-seen line).
            off = num * 2
            on_stmt = (0 <= off < code_len - 2
                       and code[off] == 0xCB and code[off + 1] == 0x00)
            # On a small object a name starting 'L' that lands on a STMT is a
            # label.  On a large one that is too noisy (many L-named variables
            # whose first-seen line collides with a STMT offset), so require the
            # value to be unambiguously a code offset (past the last source
            # line).  Branch targets always get a synthetic L_<word> name, so a
            # missed label only costs a nicer name, never correctness.
            is_label = (
                name.startswith("L") and len(name) > 2 and on_stmt
                and (code_len < 4000 or num > max_line)
            )
            if is_label:
                lbl = name[1:]
                c.labels[off] = lbl
                c.label_words[lbl] = num
            else:
                c.var_lines[name] = num
    return c


def _looks_like_boundary(code: bytes, off: int) -> bool:
    """A label always sits on a statement marker (0x00cb) or a word boundary at
    the very start/end.  Cheap sanity check to keep a variable named 'LEFT'
    from being read as a label."""
    if off < 0 or off >= len(code):
        return False
    if off % 2:
        return False
    if off == 0:
        return True
    op = struct.unpack_from("<H", code, off)[0] if off + 2 <= len(code) else -1
    return op == 0x00CB or op in _KNOWN_OPCODE_SET


# Filled in by disasm module import; kept here so load() can use it without a
# circular import at module load time.
_KNOWN_OPCODE_SET: set[int] = set()


def register_opcodes(opcodes) -> None:
    _KNOWN_OPCODE_SET.clear()
    _KNOWN_OPCODE_SET.update(opcodes)
