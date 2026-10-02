"""Apply the selected patches to one main.dol."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features
from dol import Dol
from ops import apply_static
from regions import REGIONS, DOL_SIZES

STYLES = ('ba', 'yb')
STYLE_TITLES = {'ba': 'B/A style (A jumps, B inhales)', 'yb': 'Y/B style (B jumps, Y inhales)'}


def plan(cc, gc, style='ba'):
    """Feature names for a selection.  The GameCube controller is read through the
    Classic Controller code, so choosing it installs that code as well."""
    if style not in STYLES:
        raise ValueError('unknown button style %r' % style)
    names = []
    if cc or gc:
        names.append('cc_' + style)
    if gc:
        names.append('gc_' + style)
    return names


def detect_region(dol):
    """Which release this main.dol is, from its own bytes (None if unknown)."""
    for region in REGIONS:
        f = features.load('meta', region)
        if not f.check_pristine(dol) or f.is_applied(dol):
            return region
    return None


def status(dol, region):
    """{feature: 'clean' | 'patched' | 'mismatch'} for each feature on this DOL."""
    out = {}
    for name in features.FEATURES:
        if not features.available(name, region):
            continue
        f = features.load(name, region)
        if f.is_applied(dol):
            out[name] = 'patched'
        elif not f.check_pristine(dol):
            out[name] = 'clean'
        else:
            out[name] = 'mismatch'
    return out


def needed(dol, region, which):
    """What still has to be added to `dol` for the features in `which` (the
    Metafortress bypass comes along whenever anything does).  Raises when the
    DOL is modified in a way that conflicts, e.g. the other button style."""
    have = status(dol, region)
    if have.get('meta') == 'mismatch':
        raise ValueError('this main.dol is not an unmodified retail %s -- already modified by something '
                         'else, or not a clean dump. Not patching it.' % REGIONS[region]['label'])
    for name in which:
        if have.get(name) == 'mismatch':
            raise ValueError('%s does not fit this main.dol: it is already modified (the other button '
                             'style, or another patch). Start from a clean disc image.' % features.TITLES[name])
    todo = [n for n in which if have.get(n) == 'clean']
    if todo and have.get('meta') == 'clean':
        todo.insert(0, 'meta')
    return todo


def patch(dol, region, which):
    """Patch `dol` (a dol.Dol) in place with the features named in `which`."""
    feats = [features.load(n, region) for n in features.FEATURES if n in which]
    if not feats:
        raise ValueError('nothing selected')
    apply_static(dol, feats)
    return [f.title for f in feats]


def patch_file(src, dst, region, which):
    dol = Dol(src)
    todo = needed(dol, region, which)
    done = patch(dol, region, todo)
    dol.save(dst)
    return done


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description="Patch a Kirby's Return to Dream Land main.dol")
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--region', choices=sorted(REGIONS), help='default: detect')
    ap.add_argument('--cc', action='store_true', help='Classic Controller')
    ap.add_argument('--gc', action='store_true', help='GameCube controllers')
    ap.add_argument('--style', choices=STYLES, default='ba', help=' / '.join(STYLE_TITLES.values()))
    a = ap.parse_args()
    d = Dol(a.src)
    reg = a.region or detect_region(d)
    if not reg:
        sys.exit('could not identify this main.dol; pass --region')
    if not (a.cc or a.gc):
        a.cc = a.gc = True
    print(reg, REGIONS[reg]['label'], '->', ', '.join(patch_file(a.src, a.dst, reg, plan(a.cc, a.gc, a.style))))
