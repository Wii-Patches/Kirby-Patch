"""Build the Metafortress bypass for one release from the patches' own Riivolution list.

Kirby's Return to Dream Land is protected by Metafortress: any change to main.dol
crashes it, unless the protection's ~1,400 checks are switched off first.  Vague
Rant published those switches (src/metaknight/*.xml, as <memory> writes), and a
rewritten main.dol needs them.  A Gecko code or Riivolution patch changes memory
only after the game is running and does not.

The retail bytes the writes replace are not stored here: the feature carries a
SHA-1 of them instead, which the patcher checks before it patches.
"""
import hashlib
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ops import Feature, Patch

USA_DOL = None
ALL_DOLS = {}           # set by gen_prebuilt: every release's retail main.dol, by disc id
XML = {'SUKE01': 'kirby-metaknight-usa.xml', 'SUKP01': 'kirby-metaknight-eur_v1.1.xml', 'SUKJ01': 'kirby-metaknight-jpn.xml'}


def published(region):
    text = open(os.path.join(HERE, 'metaknight', XML[region])).read()
    return [(int(a, 16), bytes.fromhex(v)) for a, v in re.findall(r'offset="(0x[0-9A-Fa-f]+)" value="([0-9A-Fa-f]+)"', text)]


# Korea has no published list.  Its code is the other releases' code moved (and, in a few
# places, rebuilt), so the three published lists are carried over to it by src/reloc.py.
# 1388 sites come out the same from all three; the rest were checked by hand against the
# Korean code:
#   0x80658744  from the European list; the Korean code around it is the European build's, which
#               patches the rlwinm here where the USA/Japan lists patch the subf ten words on
#   0x80658754  that USA/Japan subf: dropped in favour of the line above
#   0x8069F448  European only: the Korean (and European) code has this check where the USA and
#               Japan builds have a different one, which Korea does not contain
#   0x80176474, 0x80668898   in two of the three lists, with the same instruction in Korea
KOR_DROP = {0x80658754}
SOURCES = (('SUKE01', 'USA'), ('SUKP01', 'EUR'), ('SUKJ01', 'JPN'))


def carried_over(region, dol):
    from reloc import Relocator
    votes = {}
    for rid, _name in SOURCES:
        ref = ALL_DOLS[rid]
        pub = dict(published(rid))
        placed = Relocator(ref, dol).relocate_all(sorted(pub))
        for a, t in placed.items():
            votes.setdefault(t, []).append(pub[a])
    out = []
    for t in sorted(votes):
        if t in KOR_DROP:
            continue
        vals = votes[t]
        out.append((t, max(vals, key=lambda v: (vals.count(v), -vals.index(v)))))     # majority, USA first on a tie
    return out


def build(region, dol):
    writes = carried_over(region, dol) if region == 'SUKK01' else published(region)
    if region == 'SUKK01':
        assert len(writes) == 1392, 'expected 1392 Korean sites, got %d' % len(writes)
    sha = hashlib.sha1()
    ops = []
    for addr, new in writes:
        cur = dol.read(addr, len(new))
        assert cur is not None, 'metaknight site 0x%08X is not in %s' % (addr, region)
        sha.update(cur)
        ops.append(Patch(addr, new, b''))
    return Feature('meta', 'Metafortress bypass', region, ops, static_only=True, orig_sha1=sha.hexdigest())
