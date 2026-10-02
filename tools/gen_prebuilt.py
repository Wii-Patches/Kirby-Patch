#!/usr/bin/env python3
"""Regenerate tools/prebuilt/*.json from src/ (needs devkitPPC and the retail DOLs).

    KIRBY_DOLS=/path/with/SUKE01.dol,SUKP01.dol,SUKJ01.dol  python3 tools/gen_prebuilt.py [meta|cc_ba|cc_yb|gc_ba|gc_yb ...]

Each retail DOL can instead be given as KIRBY_DOL_<ID>.  The JSON is what the
patcher ships and reads; end users do not need devkitPPC or any game files here.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
from dol import Dol
from features import FEATURES, PREBUILT, dump
from regions import REGIONS


def dol_for(region):
    env = os.environ.get('KIRBY_DOL_' + region)
    if env:
        return Dol(env)
    base = os.environ.get('KIRBY_DOLS')
    if base:
        p = os.path.join(base, region + '.dol')
        if os.path.exists(p):
            return Dol(p)
    sys.exit('set KIRBY_DOLS=<dir with %s.dol> or KIRBY_DOL_%s=<path>' % (region, region))


def builder(name):
    """(module, extra args) that build feature `name`."""
    if name == 'meta':
        return __import__('gen_meta'), ()
    kind, style = name.split('_')
    return __import__('gen_' + kind), (style,)


def main(argv):
    which = argv or list(FEATURES)
    os.makedirs(PREBUILT, exist_ok=True)
    for name in which:
        mod, extra = builder(name)
        mod.USA_DOL = dol_for('SUKE01')
        if hasattr(mod, 'ALL_DOLS'):
            mod.ALL_DOLS = {r: dol_for(r) for r in REGIONS}
        for region in REGIONS:
            f = mod.build(region, dol_for(region), *extra)
            path = os.path.join(PREBUILT, '%s_%s.json' % (name, region))
            with open(path, 'w') as fh:
                json.dump(dump(f), fh, indent=1)
                fh.write('\n')
            print('%-6s %s  %d ops -> %s' % (name, region, len(f.ops), os.path.relpath(path)))


if __name__ == '__main__':
    main(sys.argv[1:])
