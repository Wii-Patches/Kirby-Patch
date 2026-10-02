"""Load the prebuilt feature definitions (tools/prebuilt/<feature>_<region>.json)."""
import json
import os
import struct
import sys

from ops import Blob, Feature, Hook, Patch

if os.environ.get('KIRBY_PREBUILT'):                  # development: a build with test hooks
    PREBUILT = os.environ['KIRBY_PREBUILT']
elif getattr(sys, 'frozen', False):
    PREBUILT = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'prebuilt')
else:
    PREBUILT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prebuilt')

# meta   Metafortress bypass (only a rewritten main.dol needs it)
# cc_*   Classic Controller support, in the two button styles (Vague Rant, crediar)
# gc_*   GameCube controllers (ports 1-4) fed to the Classic Controller code
FEATURES = ('meta', 'cc_ba', 'cc_yb', 'gc_ba', 'gc_yb')
TITLES = {
    'meta': 'Metafortress bypass',
    'cc_ba': 'Classic Controller (B/A style)',
    'cc_yb': 'Classic Controller (Y/B style)',
    'gc_ba': 'GameCube controllers (B/A style)',
    'gc_yb': 'GameCube controllers (Y/B style)',
}


def dump(feature):
    ops = []
    for op in feature.ops:
        if isinstance(op, Patch):
            ops.append(dict(t='patch', addr=op.addr, new=op.new.hex(), orig=op.orig.hex(), note=op.note))
        elif isinstance(op, Blob):
            ops.append(dict(t='blob', addr=op.addr, data=op.data.hex(), note=op.note))
        elif isinstance(op, Hook):
            ops.append(dict(t='hook', site=op.site, orig=op.orig, payload=op.payload, tramp=op.tramp, note=op.note))
    d = dict(feature=feature.name, title=feature.title, region=feature.region, ops=ops)
    if feature.static_only:
        d['static_only'] = True
    if feature.orig_sha1:
        d['orig_sha1'] = feature.orig_sha1
    return d


def load_dict(j):
    ops = []
    for o in j['ops']:
        if o['t'] == 'patch':
            ops.append(Patch(o['addr'], bytes.fromhex(o['new']), bytes.fromhex(o['orig']), o.get('note', '')))
        elif o['t'] == 'blob':
            ops.append(Blob(o['addr'], bytes.fromhex(o['data']), o.get('note', '')))
        elif o['t'] == 'hook':
            ops.append(Hook(o['site'], o['orig'], o['payload'], o['tramp'], o.get('note', '')))
    return Feature(j['feature'], j['title'], j['region'], ops, j.get('static_only', False), j.get('orig_sha1', ''))


def load(name, region):
    with open(os.path.join(PREBUILT, '%s_%s.json' % (name, region))) as f:
        return load_dict(json.load(f))


def available(name, region):
    return os.path.exists(os.path.join(PREBUILT, '%s_%s.json' % (name, region)))
