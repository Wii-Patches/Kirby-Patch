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
XML = {'SUKE01': 'kirby-metaknight-usa.xml', 'SUKP01': 'kirby-metaknight-eur_v1.1.xml', 'SUKJ01': 'kirby-metaknight-jpn.xml'}


def build(region, dol):
    text = open(os.path.join(HERE, 'metaknight', XML[region])).read()
    writes = [(int(a, 16), bytes.fromhex(v)) for a, v in re.findall(r'offset="(0x[0-9A-Fa-f]+)" value="([0-9A-Fa-f]+)"', text)]
    sha = hashlib.sha1()
    ops = []
    for addr, new in writes:
        cur = dol.read(addr, len(new))
        assert cur is not None, 'metaknight site 0x%08X is not in %s' % (addr, region)
        sha.update(cur)
        ops.append(Patch(addr, new, b''))
    return Feature('meta', 'Metafortress bypass', region, ops, static_only=True, orig_sha1=sha.hexdigest())
