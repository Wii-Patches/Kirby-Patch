#!/usr/bin/env python3
"""Check the patch data against real, retail main.dol files.

    KIRBY_DOLS=<dir with SUKE01.dol SUKP01.dol SUKJ01.dol> python3 tools/verify.py

For every release and every sensible selection (Classic Controller / GameCube, either style):
  * every site holds the retail bytes before patching
  * after patching, every hook site is a branch into the injected section whose
    trampoline runs back to site+4, and every in-place patch carries its new bytes
  * patching in steps (one feature at a time) gives the same file as all at once
  * nothing outside the intended sites changed
  * the other button style is refused on an already patched main.dol
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import features
import patcher
from dol import Dol
from ops import Hook
from regions import REGIONS, DOL_SIZES

fail = []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        fail.append(msg)


def retail(region):
    base = os.environ.get('KIRBY_DOLS')
    p = os.path.join(base or '.', region + '.dol')
    if not os.path.exists(p):
        sys.exit('set KIRBY_DOLS to a directory holding %s.dol' % region)
    return p


SELECTIONS = [(True, False, 'ba'), (True, False, 'yb'), (False, True, 'ba'), (False, True, 'yb'),
              (True, True, 'ba'), (True, True, 'yb')]


def main():
    for region in REGIONS:
        print(region, REGIONS[region]['label'])
        path = retail(region)
        check(os.path.getsize(path) == DOL_SIZES[region], 'retail size')
        d0 = Dol(path)
        check(patcher.detect_region(d0) == region, 'detected as %s' % region)
        for name in features.FEATURES:
            f = features.load(name, region)
            check(not f.check_pristine(d0), '%s: every site holds the retail bytes' % name)

        for cc, gc, style in SELECTIONS:
            which = patcher.plan(cc, gc, style)
            label = '+'.join(which)
            d = Dol(path)
            todo = patcher.needed(d, region, which)
            check(todo[0] == 'meta' and sorted(todo[1:]) == sorted(which), 'plan %s needs meta + %s' % (label, label))
            patcher.patch(d, region, todo)
            touched = []
            for name in todo:
                f = features.load(name, region)
                check(f.is_applied(d), '%s applied (%s)' % (name, label))
                for op in f.ops:
                    if isinstance(op, Hook):
                        site = struct.unpack('>I', d.read(op.site, 4))[0]
                        tgt = (site & 0x03FFFFFC)
                        tgt = tgt - 0x04000000 if tgt & 0x02000000 else tgt
                        check((site >> 26) == 18 and not site & 3 and (op.site + tgt) == op.tramp,
                              '%s: 0x%08X branches to 0x%08X' % (name, op.site, op.tramp))
                touched += [(a, len(b)) for a, b in f.writes()]
            # nothing else changed
            for off, va, size, idx in d0.secs:
                a = bytes(d0.data[off:off + size])
                b = d.read(va, size)
                stray = [va + i for i in range(size) if a[i] != b[i] and not any(t <= va + i < t + n for t, n in touched)]
                if stray:
                    check(False, '%s: unexpected change at 0x%08X' % (label, stray[0]))
            # stepwise == all at once
            step = Dol(path)
            for name in todo:
                patcher.patch(step, region, [name])
            same = all(step.read(va, sz) == d.read(va, sz) for _o, va, sz, _i in d.secs) and len(step.secs) == len(d.secs)
            check(same, 'stepwise == together for %s' % label)
            # asking again changes nothing; the other style is refused
            check(patcher.needed(d, region, which) == [], 'nothing left to add after %s' % label)
            other = patcher.plan(cc, gc, 'yb' if style == 'ba' else 'ba')
            try:
                patcher.needed(d, region, other)
                check(False, 'the other style is refused on a patched main.dol (%s)' % label)
            except ValueError:
                check(True, 'the other style is refused on a patched main.dol (%s)' % label)
    print('\nFAILED: %d' % len(fail) if fail else '\nALL VERIFIED')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
