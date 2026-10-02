#!/usr/bin/env python3
"""Command-line twin of the GUI: patch a .wbfs/.iso in place.

    python3 tools/patch_disc.py "Kirby's Return to Dream Land (USA) (En,Fr,Es).wbfs" --gc
    python3 tools/patch_disc.py game.wbfs --cc --style yb
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc
import patcher


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument('image')
    ap.add_argument('--cc', action='store_true', help='Classic Controller')
    ap.add_argument('--gc', action='store_true', help='GameCube controllers (ports 1-4); includes the Classic Controller code')
    ap.add_argument('--style', choices=patcher.STYLES, default='ba',
                    help=' / '.join('%s: %s' % kv for kv in patcher.STYLE_TITLES.items()))
    ap.add_argument('--ios', type=int, metavar='SLOT',
                    help='also make the disc ask for this IOS slot')
    a = ap.parse_args()
    if not (a.cc or a.gc):
        a.cc = a.gc = True
    ok = []
    disc.run_patch(a.image, print, lambda good, msg: ok.append(good), patcher.plan(a.cc, a.gc, a.style), a.ios)
    sys.exit(0 if ok and ok[0] else 1)


if __name__ == '__main__':
    main()
