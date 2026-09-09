#!/usr/bin/env python3
"""Structural recon on a UniData UniBasic P-code object file.

Makes no assumptions about the format. Every pass is a generic probe that
narrows down where the sections are; the --source option turns the matching
UniBasic source into a Rosetta stone for the constant and symbol tables.

  ./pcode_recon.py _STACK --source STACK
"""
import argparse
import collections
import hashlib
import math
import re
import struct
import sys

PRINTABLE = set(range(0x20, 0x7F)) | {0x09}


def hexdump(buf, base=0, width=16, limit=None):
    out = []
    data = buf[:limit] if limit else buf
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hexpart = ' '.join(f'{b:02x}' for b in chunk).ljust(width * 3 - 1)
        txt = ''.join(chr(b) if b in PRINTABLE and b != 0x09 else '.' for b in chunk)
        out.append(f'{base + off:08x}  {hexpart}  |{txt}|')
    return '\n'.join(out)


def entropy(chunk):
    if not chunk:
        return 0.0
    counts = collections.Counter(chunk)
    n = len(chunk)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def banner(title):
    print(f'\n{"=" * 74}\n== {title}\n{"=" * 74}')


# --------------------------------------------------------------------------
# Pass 1: header, and which header words look like offsets into the file.
# --------------------------------------------------------------------------
def pass_header(buf, hdr_bytes, unaligned=False):
    banner(f'HEADER (first {hdr_bytes} bytes)')
    print(hexdump(buf, limit=hdr_bytes))

    banner('HEADER WORDS THAT LOOK LIKE FILE OFFSETS / SIZES')
    print('A container format stores its section table up front. Any word that\n'
          'lands inside the file is a candidate section pointer; a run of them\n'
          'in increasing order is almost certainly the section table.\n')
    size = len(buf)
    fmts = [('u16le', '<H', 2), ('u16be', '>H', 2), ('u32le', '<I', 4), ('u32be', '>I', 4)]
    hits = collections.defaultdict(list)
    for name, fmt, width in fmts:
        step = 1 if unaligned else width
        for off in range(0, min(hdr_bytes, size - width) + 1, step):
            (val,) = struct.unpack_from(fmt, buf, off)
            if val == size:
                hits[name].append((off, val, 'EXACT FILE SIZE'))
            elif 0 < val < size and (width == 4 or val > 0x20):
                hits[name].append((off, val, 'in-range'))
    for name, _, _ in fmts:
        rows = hits[name]
        if not rows:
            continue
        print(f'-- {name} --')
        for off, val, note in rows[:40]:
            flag = ' <<<' if note == 'EXACT FILE SIZE' else ''
            print(f'   +0x{off:03x}  {val:>10}  0x{val:08x}  {note}{flag}')
        if len(rows) > 40:
            print(f'   ... {len(rows) - 40} more')
        # An increasing run of in-range values is the strongest signal there is.
        vals = [v for _, v, _ in rows]
        run, best = [], []
        for i, v in enumerate(vals):
            if run and v > run[-1]:
                run.append(v)
            else:
                run = [v]
            if len(run) > len(best):
                best = list(run)
        if len(best) >= 3:
            print(f'   ** increasing run of {len(best)}: {best[:12]} -> candidate section table')
        print()


# --------------------------------------------------------------------------
# Pass 2: strings, and how they are delimited (counted vs NUL-terminated).
# --------------------------------------------------------------------------
def find_strings(buf, minlen):
    out, start = [], None
    for i, b in enumerate(buf):
        if b in PRINTABLE:
            if start is None:
                start = i
        else:
            if start is not None and i - start >= minlen:
                out.append((start, buf[start:i].decode('ascii', 'replace')))
            start = None
    if start is not None and len(buf) - start >= minlen:
        out.append((start, buf[start:].decode('ascii', 'replace')))
    return out


def pass_strings(buf, minlen, show):
    banner(f'STRINGS (min length {minlen})')
    strings = find_strings(buf, minlen)
    print(f'{len(strings)} runs found. First {show}:\n')
    for off, s in strings[:show]:
        prev1 = buf[off - 1] if off else None
        prev2 = struct.unpack_from('<H', buf, off - 2)[0] if off >= 2 else None
        tag = ''
        if prev1 == len(s):
            tag = '  [prev byte == len -> 1-byte counted string]'
        elif prev2 == len(s):
            tag = '  [prev u16le == len -> 2-byte counted string]'
        elif off + len(s) < len(buf) and buf[off + len(s)] == 0:
            tag = '  [NUL-terminated]'
        print(f'  0x{off:06x} ({len(s):3d}) {s[:70]!r}{tag}')
    if len(strings) > show:
        print(f'  ... {len(strings) - show} more')

    banner('STRING REGION EXTENT')
    if strings:
        lo, hi = strings[0][0], strings[-1][0] + len(strings[-1][1])
        span = hi - lo
        covered = sum(len(s) for _, s in strings)
        print(f'first string 0x{lo:06x}, last ends 0x{hi:06x}, span {span} bytes')
        print(f'{covered} of those {span} bytes are string data ({100 * covered / span:.1f}%)')
        print('A dense span is a literal pool; strings scattered thinly across the\n'
              'whole file mean literals are inlined in the instruction stream.')
    return strings


# --------------------------------------------------------------------------
# Pass 3: the source as a Rosetta stone.
# --------------------------------------------------------------------------
def source_literals(src):
    # UniBasic quotes with ' " and \ .
    lits = []
    for m in re.finditer(r"'([^'\n]*)'|\"([^\"\n]*)\"|\\([^\\\n]*)\\", src):
        val = next(g for g in m.groups() if g is not None)
        if len(val) >= 4:
            lits.append(val)
    return lits


def source_identifiers(src):
    body = '\n'.join(ln for ln in src.splitlines() if not ln.lstrip().startswith('*'))
    ids = set(re.findall(r'\b([A-Z][A-Z0-9]*(?:\.[A-Z0-9]+)+)\b', body))
    return sorted(i for i in ids if len(i) >= 4)


def pass_source(buf, src, show):
    banner('CONSTANT TABLE — source literals located in the object')
    lits = source_literals(src)
    uniq, seen = [], set()
    for l in lits:
        if l not in seen:
            seen.add(l)
            uniq.append(l)
    found, missing = [], []
    for lit in uniq:
        off = buf.find(lit.encode('latin-1', 'replace'))
        (found if off >= 0 else missing).append((lit, off))
    print(f'{len(found)}/{len(uniq)} distinct source literals found verbatim in the object.\n')
    for lit, off in found[:show]:
        print(f'  0x{off:06x}  {lit[:64]!r}')
    if len(found) > show:
        print(f'  ... {len(found) - show} more')
    if missing:
        print(f'\n{len(missing)} NOT found verbatim (first 10) — if many are missing the\n'
              'literal pool is encoded/compressed rather than stored raw:')
        for lit, _ in missing[:10]:
            print(f'    {lit[:64]!r}')

    if len(found) >= 3:
        offs = [o for _, o in found]
        inorder = sum(1 for a, b in zip(offs, offs[1:]) if b > a)
        print(f'\nSource order vs object order: {inorder}/{len(offs) - 1} pairs increasing '
              f'({100 * inorder / (len(offs) - 1):.0f}%).')
        print('High percentage => literals are emitted in first-use order, so the\n'
              'pool is append-as-encountered and its bounds are '
              f'0x{min(offs):06x}..0x{max(offs):06x}.')

    banner('SYMBOL TABLE — source identifiers located in the object (-Z2 debug info)')
    ids = source_identifiers(src)
    sym = [(i, buf.find(i.encode())) for i in ids]
    hit = [(i, o) for i, o in sym if o >= 0]
    print(f'{len(hit)}/{len(ids)} dotted identifiers found.\n')
    for name, off in sorted(hit, key=lambda x: x[1])[:show]:
        print(f'  0x{off:06x}  {name}')
    if len(hit) > show:
        print(f'  ... {len(hit) - show} more')
    if len(hit) >= 3:
        offs = sorted(o for _, o in hit)
        print(f'\nIdentifiers span 0x{offs[0]:06x}..0x{offs[-1]:06x}.')
        gaps = [b - a for a, b in zip(offs, offs[1:])]
        common = collections.Counter(gaps).most_common(5)
        print(f'Most common offset gaps: {common}')
        print('A dominant repeated gap means fixed-stride symbol records; the stride\n'
              'minus the name length is the size of the per-symbol metadata.')


# --------------------------------------------------------------------------
# Pass 4: the line-number table. -Z2 has to map p-code back to source lines.
# --------------------------------------------------------------------------
def pass_linetable(buf, maxline, minrun):
    banner(f'LINE NUMBER TABLE — monotonic runs in [1, {maxline}]')
    print('With -Z2 the compiler must store a source-line map. Look for long\n'
          'non-decreasing runs of small integers bounded by the source line count.\n')
    for name, fmt, width in [('u16le', '<H', 2), ('u16be', '>H', 2),
                             ('u32le', '<I', 4), ('u32be', '>I', 4)]:
        best, best_start = [], None
        # A table need not sit on the scan grid, so try every start phase.
        for phase in range(width):
            run_start, run = None, []
            for off in range(phase, len(buf) - width + 1, width):
                (v,) = struct.unpack_from(fmt, buf, off)
                if 1 <= v <= maxline and (not run or v >= run[-1]):
                    if not run:
                        run_start = off
                    run.append(v)
                else:
                    if len(run) > len(best):
                        best, best_start = list(run), run_start
                    run = []
            if len(run) > len(best):
                best, best_start = list(run), run_start
        if len(best) >= minrun:
            print(f'-- {name}: longest run {len(best)} values at 0x{best_start:06x} '
                  f'({best[0]}..{best[-1]})')
            print(f'   head: {best[:16]}')
            print(f'   tail: {best[-16:]}\n')
        else:
            print(f'-- {name}: nothing longer than {len(best)} (below threshold)\n')


# --------------------------------------------------------------------------
# Pass 5: where is the code? Entropy map + histogram of non-text bytes.
# --------------------------------------------------------------------------
def pass_layout(buf, blocks):
    banner('SECTION MAP — entropy and printable-ratio per block')
    print('code = mid entropy, low printable. literals = low entropy, high printable.\n')
    step = max(1, len(buf) // blocks)
    print(f'{"offset":>10} {"entropy":>8} {"printable":>10}  profile')
    for off in range(0, len(buf), step):
        chunk = buf[off:off + step]
        e = entropy(chunk)
        p = sum(1 for b in chunk if b in PRINTABLE) / len(chunk)
        bar = '#' * int(e * 4)
        kind = 'TEXT' if p > 0.85 else ('code?' if 3.0 < e < 6.5 else '')
        print(f'0x{off:08x} {e:8.2f} {p:9.1%}  {bar:<32} {kind}')

    banner('BYTE HISTOGRAM OF NON-PRINTABLE BYTES (opcode candidates)')
    counts = collections.Counter(b for b in buf if b not in PRINTABLE)
    total = sum(counts.values())
    print(f'{total} non-printable bytes, {len(counts)} distinct values.\n')
    print('Most frequent — in a bytecode stream the top values are the common\n'
          'opcodes (load/store/call) or the padding byte.\n')
    for val, n in counts.most_common(24):
        print(f'  0x{val:02x} {n:>8}  {100 * n / total:5.2f}%  {"*" * int(60 * n / counts.most_common(1)[0][1])}')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('objfile')
    ap.add_argument('--source', help='matching UniBasic source, used as a Rosetta stone')
    ap.add_argument('--header-bytes', type=int, default=128)
    ap.add_argument('--unaligned', action='store_true',
                    help='scan header words at every byte offset, not just aligned ones')
    ap.add_argument('--min-str', type=int, default=4)
    ap.add_argument('--show', type=int, default=40, help='rows per list')
    ap.add_argument('--blocks', type=int, default=48, help='blocks in the section map')
    args = ap.parse_args()

    with open(args.objfile, 'rb') as fh:
        buf = fh.read()

    banner(f'{args.objfile}')
    print(f'size   {len(buf)} bytes (0x{len(buf):x})')
    print(f'sha256 {hashlib.sha256(buf).hexdigest()}')

    pass_header(buf, args.header_bytes, args.unaligned)
    pass_strings(buf, args.min_str, args.show)

    maxline = 65535
    if args.source:
        with open(args.source, 'r', errors='replace') as fh:
            src = fh.read()
        maxline = max(16, src.count('\n') + 1)
        pass_source(buf, src, args.show)

    pass_linetable(buf, maxline, minrun=12)
    pass_layout(buf, args.blocks)

    banner('DONE')
    print('Next: compile a probe pair that differs by one statement and run\n'
          'pcode_diff.py on the two objects to read off individual opcodes.')


if __name__ == '__main__':
    sys.exit(main())
