"""Shared pieces of the Kirby's Return to Dream Land builders."""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from ops import Hook, Patch

USA_DOL = None          # set by gen_prebuilt: the reference (USA) main.dol for the anchor search

STYLES = ('ba', 'yb')


def parse_gecko(text):
    """Gecko lines -> [('c2', site, words)] and [('w32', addr, word)]."""
    L = [l.split() for l in text.split('\n') if l.strip() and not l.startswith('#')]
    ops, i = [], 0
    while i < len(L):
        h = L[i]
        if h[0].startswith('C2'):
            n = int(h[1], 16)
            words = []
            for l in L[i + 1:i + 1 + n]:
                words += [int(x, 16) for x in l]
            ops.append(('c2', 0x80000000 | (int(h[0], 16) & 0x01FFFFFF), words))
            i += 1 + n
        elif h[0].startswith('04'):
            ops.append(('w32', 0x80000000 | (int(h[0], 16) & 0x01FFFFFF), int(h[1], 16)))
            i += 1
        else:
            raise SystemExit('unknown Gecko line %r' % h)
    return ops


def read_dol_word(dol, addr):
    return struct.unpack('>I', dol.read(addr, 4))[0]
