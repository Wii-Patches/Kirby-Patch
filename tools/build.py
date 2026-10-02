#!/usr/bin/env python3
"""Emit the Gecko code lists and Riivolution XML from the prebuilt features.

    python3 tools/build.py            # writes codes/<ID>.ini, codes/<ID>.txt, riivolution/<ID>.xml

The patched-DOL path (tools/patcher.py, the GUI) uses the very same operations, so the
install methods cannot disagree.  The Metafortress bypass is only for a rewritten
main.dol: a Gecko code or a Riivolution memory patch changes memory after the game
has started and does not trip the protection.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import features
from regions import REGIONS

ROOT = os.path.join(HERE, '..')

CREDIT = {
    'cc_ba': 'Vague Rant, crediar',
    'cc_yb': 'Vague Rant, crediar',
    'gc_ba': 'quatric',
    'gc_yb': 'quatric',
}
BLURB = {
    'cc_ba': ['Classic Controller support, B/A style: A jumps, B inhales, Y drops the copy ability, X/L/R shake,',
              'ZL/ZR guard. The right stick is the pointer, the left stick moves.'],
    'cc_yb': ['Classic Controller support, Y/B style: B jumps, Y inhales, A drops the copy ability, X/L/R shake,',
              'ZL/ZR guard. The right stick is the pointer, the left stick moves.'],
    'gc_ba': ['GameCube controllers in ports 1-4, no Wii Remote needed: A jumps, B inhales, Y drops the copy',
              'ability, X shakes, L/R guard, Z is HOME. Needs "Classic Controller (B/A style)" enabled too.'],
    'gc_yb': ['GameCube controllers in ports 1-4, no Wii Remote needed, with the same layout as the B/A style',
              'one (A jumps, B inhales). Needs "Classic Controller (Y/B style)" enabled too.'],
}
# which Gecko/Riivolution features exist (the Metafortress bypass is static-only)
OUTPUT = tuple(n for n in features.FEATURES if n != 'meta')


def gecko_ini(region):
    lines = ['[Gecko]']
    for name in OUTPUT:
        if not features.available(name, region):
            continue
        f = features.load(name, region)
        lines.append('$%s' % f.title)
        lines.append('*By %s' % CREDIT[name])
        lines.append('*%s (%s)' % (REGIONS[region]['label'], region))
        lines += ['*' + b for b in BLURB[name]]
        lines += f.gecko_lines()
    return '\n'.join(lines) + '\n'


CHOICES = (
    ('Classic Controller (B/A style)', ('cc_ba',)),
    ('Classic Controller (Y/B style)', ('cc_yb',)),
    ('Classic Controller + GameCube controllers (B/A style)', ('cc_ba', 'gc_ba')),
    ('Classic Controller + GameCube controllers (Y/B style)', ('cc_yb', 'gc_yb')),
)


def riivolution_xml(region):
    r = REGIONS[region]
    out = ['<!-- %s: patches by quatric; Classic Controller code by Vague Rant and crediar -->' % r['label'],
           '<wiidisc version="1" root="/">',
           '  <id game="%s" version="%d" />' % (region, r['version']),
           '  <options>',
           '    <section name="%s">' % r['label'],
           '      <option name="Controllers" default="3">']
    for title, ids in CHOICES:
        out.append('        <choice name="%s">%s</choice>' % (title, ''.join('<patch id="%s" />' % i for i in ids)))
    out += ['      </option>', '    </section>', '  </options>']
    for name in OUTPUT:
        if not features.available(name, region):
            continue
        f = features.load(name, region)
        out.append('  <patch id="%s">' % name)
        out += ['    ' + e for e in f.memory_elements()]
        out.append('  </patch>')
    out.append('</wiidisc>')
    return '\n'.join(out) + '\n'


def main():
    for d in ('codes', 'riivolution'):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)
    for region in REGIONS:
        ini = gecko_ini(region)
        with open(os.path.join(ROOT, 'codes', region + '.ini'), 'w') as fh:
            fh.write(ini)
        # same codes in the plain cheat-file layout loaders read (no [Gecko] header)
        with open(os.path.join(ROOT, 'codes', region + '.txt'), 'w') as fh:
            fh.write(ini.split('\n', 1)[1])
        with open(os.path.join(ROOT, 'riivolution', region + '.xml'), 'w') as fh:
            fh.write(riivolution_xml(region))
        print(region, REGIONS[region]['label'])


if __name__ == '__main__':
    main()
