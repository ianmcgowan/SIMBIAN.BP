#!/usr/bin/env python3
"""Differential analysis of two UniBasic P-code objects.

Compile two programs that differ by exactly one thing, diff the objects, and
the bytes that changed ARE the encoding of that one thing. This is the only
reliable way to decode an undocumented bytecode.

  ./pcode_diff.py _P01_PRINT_ONE _P03_PRINT_TWICE
  ./pcode_diff.py _P01_Z2 _P01_NOZ2      # isolates the -Z2 debug sections
"""
import argparse
import collections
import struct
import sys

PRINTABLE = set(range(0x20, 0x7F))


def hexdump(buf, base=0, width=16):
    out = []
    for off in range(0, len(buf), width):
        chunk = buf[off:off + width]
        hexpart = ' '.join(f'{b:02x}' for b in chunk).ljust(width * 3 - 1)
        txt = ''.join(chr(b) if b in PRINTABLE else '.' for b in chunk)
        out.append(f'{base + off:08x}  {hexpart}  |{txt}|')
    return '\n'.join(out)


def banner(t):
    print(f'\n{"=" * 74}\n== {t}\n{"=" * 74}')


def common_prefix(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def common_suffix(a, b, limit):
    i = 0
    while i < limit and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1
    return i


def pass_header_delta(a, b, hdr_bytes):
    banner('HEADER FIELD DELTAS')
    delta_size = len(b) - len(a)
    print(f'A is {len(a)} bytes, B is {len(b)} bytes, delta {delta_size:+d}\n')
    print('Any header word whose delta equals the file-size delta is a total-size\n'
          'or section-length field. A word that changes by +1 is a count field\n'
          '(statements, symbols, literals). Unchanged words are magic/version.\n')
    rows = []
    for name, fmt, width in [('u16le', '<H', 2), ('u16be', '>H', 2),
                             ('u32le', '<I', 4), ('u32be', '>I', 4)]:
        for off in range(0, min(hdr_bytes, len(a) - width, len(b) - width) + 1, width):
            (va,) = struct.unpack_from(fmt, a, off)
            (vb,) = struct.unpack_from(fmt, b, off)
            if va != vb:
                d = vb - va
                note = ''
                if d == delta_size:
                    note = ' <<< equals file-size delta (length field)'
                elif d in (1, -1):
                    note = ' <<< +/-1 (count field)'
                rows.append((name, off, va, vb, d, note))
    if not rows:
        print('  no header word changed in that range')
        return
    print(f'  {"enc":<6} {"off":>6} {"A":>12} {"B":>12} {"delta":>10}')
    for name, off, va, vb, d, note in rows:
        print(f'  {name:<6} +0x{off:03x} {va:>12} {vb:>12} {d:>+10}{note}')


def pass_edit(a, b, context, body_start=0):
    banner(f'EDIT LOCATION (alignment starts at 0x{body_start:x})')
    if body_start:
        print('Header words change on every recompile, so alignment skips the header.\n'
              'Set --body-start to the code-section offset for a clean read.\n')
    a, b = a[body_start:], b[body_start:]
    p = common_prefix(a, b)
    s = common_suffix(a, b, min(len(a), len(b)) - p)
    mid_a = a[p:len(a) - s]
    mid_b = b[p:len(b) - s]
    abs_p = p + body_start
    print(f'identical prefix : {p} bytes (0x{body_start:08x}..0x{abs_p:08x})')
    print(f'identical suffix : {s} bytes')
    print(f'A differs over   : {len(mid_a)} bytes at 0x{abs_p:06x}')
    print(f'B differs over   : {len(mid_b)} bytes at 0x{abs_p:06x}')

    if not mid_a and mid_b:
        print(f'\n>>> PURE INSERTION of {len(mid_b)} bytes at 0x{abs_p:06x}.')
        print(f'    {" ".join(f"{v:02x}" for v in mid_b)}')
        print('    These bytes are the complete encoding of whatever you added.')
    elif mid_a and not mid_b:
        print(f'\n>>> PURE DELETION of {len(mid_a)} bytes at 0x{abs_p:06x}.')
        print(f'    {" ".join(f"{v:02x}" for v in mid_a)}')
    elif len(mid_a) == len(mid_b):
        print(f'\n>>> IN-PLACE REPLACEMENT, {len(mid_a)} bytes, same width.')
        print('    Same-width change => you altered an operand, not the opcode.')

    lo = max(0, p - context)
    banner(f'A  around 0x{abs_p:06x}')
    print(hexdump(a[lo:p + len(mid_a) + context], base=lo + body_start))
    banner(f'B  around 0x{abs_p:06x}')
    print(hexdump(b[lo:p + len(mid_b) + context], base=lo + body_start))

    if mid_a and len(mid_a) == len(mid_b):
        banner('BYTE-LEVEL OPERAND DIFF')
        for i, (x, y) in enumerate(zip(mid_a, mid_b)):
            if x != y:
                print(f'  0x{abs_p + i:06x}  {x:02x} -> {y:02x}   ({x} -> {y}, delta {y - x:+d})')


def pass_scatter(a, b):
    """When both files are the same size, list every differing byte."""
    if len(a) != len(b):
        return
    diffs = [i for i in range(len(a)) if a[i] != b[i]]
    banner(f'SAME-SIZE DIFF — {len(diffs)} differing bytes')
    if not diffs:
        print('  files are identical')
        return
    # Group into contiguous-ish clusters so the shape is readable.
    clusters, cur = [], [diffs[0]]
    for i in diffs[1:]:
        if i - cur[-1] <= 8:
            cur.append(i)
        else:
            clusters.append(cur)
            cur = [i]
    clusters.append(cur)
    print(f'{len(clusters)} cluster(s):\n')
    for c in clusters[:30]:
        lo, hi = c[0], c[-1] + 1
        print(f'  0x{lo:06x}..0x{hi:06x} ({hi - lo} bytes)')
        print(f'    A: {" ".join(f"{v:02x}" for v in a[lo:hi])}')
        print(f'    B: {" ".join(f"{v:02x}" for v in b[lo:hi])}')
    if len(clusters) > 30:
        print(f'  ... {len(clusters) - 30} more clusters')


def pass_histogram_delta(a, b):
    banner('OPCODE FREQUENCY DELTA')
    print('Byte values that got more common are the opcodes your added construct\n'
          'emits. Useful when the edit is not a clean single insertion.\n')
    ca, cb = collections.Counter(a), collections.Counter(b)
    deltas = {v: cb.get(v, 0) - ca.get(v, 0) for v in set(ca) | set(cb)}
    ranked = sorted(deltas.items(), key=lambda kv: -abs(kv[1]))
    shown = [(v, d) for v, d in ranked if d][:20]
    if not shown:
        print('  no change in byte frequencies')
        return
    for val, d in shown:
        ch = chr(val) if val in PRINTABLE else '.'
        print(f'  0x{val:02x} {ch!r:>5}  {d:>+6}')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('obj_a')
    ap.add_argument('obj_b')
    ap.add_argument('--header-bytes', type=int, default=128)
    ap.add_argument('--context', type=int, default=64)
    ap.add_argument('--body-start', type=lambda v: int(v, 0), default=0,
                    help='skip this many bytes (the header) before aligning; accepts 0x hex')
    args = ap.parse_args()

    a = open(args.obj_a, 'rb').read()
    b = open(args.obj_b, 'rb').read()

    banner(f'A = {args.obj_a}   B = {args.obj_b}')
    if a == b:
        print('Files are byte-identical — your two probes compiled to the same object.')
        return 0

    pass_header_delta(a, b, args.header_bytes)
    pass_edit(a, b, args.context, args.body_start)
    pass_scatter(a, b)
    pass_histogram_delta(a, b)
    return 0


if __name__ == '__main__':
    sys.exit(main())
