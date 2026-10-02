"""Build the Classic Controller feature (Vague Rant and crediar's button remapping, both styles).

The code is theirs, written for the USA build (src/vr_usa_ba.txt, B/A style).  The
Y/B style differs from it in three words of the button table, the Japanese build
in the two extension-check patches, and the European build in its addresses
(and the address of the one game function the pointer code calls).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_common as g
from layout import CC_BASE, CC_END
from ops import Feature, Hook, Patch

USA_DOL = None

# the remapping hook at 0x8006B074 (0x8006B2B4 in Europe) tests the Classic Controller's A, B and Y
# (andi. r0,r8,0x10 / 0x40 / 0x20) and sets a Wii Remote button for each; in Y/B style
# A -> minus (0x1000), B -> 2 (0x100, jump), Y -> 1 (0x200, inhale)
STYLE_TESTS = {0x71000010: 0x1000, 0x71000040: 0x100, 0x71000020: 0x200}

# per release: how to carry the USA code over
#   sites     USA hook address -> this release's
#   func      the game function (USA 0x8004CCD0) the pointer code calls, as an absolute address
#   ext       the two extension-check patches (isExtConnected / isClassicValid): (address, word)
USA = dict(sites={}, func=0x8004CCD0, ext=[(0x801ABD10, 0x60000000), (0x801ABD84, 0x38600000)])
REL = {
    'SUKE01': USA,
    'SUKJ01': dict(sites={}, func=0x8004CCD0, ext=[(0x801AACC4, 0x60000000), (0x801AAD38, 0x38600000)]),
    'SUKP01': dict(sites={0x8006B63C: 0x8006B87C, 0x8006C1B8: 0x8006C3F8, 0x8006D120: 0x8006D360, 0x8006B074: 0x8006B2B4},
                   func=0x8004CF10, ext=[(0x801AC620, 0x60000000), (0x801AC694, 0x38600000)]),
}
BUTTON_HOOK = 0x8006B074


def build(region, dol, style):
    r = REL[region]
    usa = g.parse_gecko(open(os.path.join(HERE, 'vr_usa_ba.txt')).read())
    ops, cur = [], CC_BASE
    note = {0x8006B63C: 'KPAD read_kpad_acc: shake',
            0x8006C1B8: 'KPAD calc_acc_variable: pointer from the right stick',
            0x8006D120: 'KPAD read_kpad_ext: left stick as D-Pad',
            BUTTON_HOOK: 'KPAD read_kpad_button: Classic Controller button layout'}
    for kind, addr, data in usa:
        if kind == 'w32':
            continue
        words = list(data)
        if addr == BUTTON_HOOK and style == 'yb':
            swapped = 0
            for j in range(len(words) - 2):
                # "andi. r0,r8,<button>; beq- +8; ori r6,r6,<Wii button>" for the A, B and Y tests
                if words[j] in STYLE_TESTS and words[j + 1] == 0x41820008 and words[j + 2] >> 16 == 0x60C6:
                    words[j + 2] = 0x60C60000 | STYLE_TESTS[words[j]]
                    swapped += 1
            assert swapped == 3, 'expected to restyle the A, B and Y entries'
        if r['func'] != 0x8004CCD0:
            words = [r['func'] if w == 0x8004CCD0 else w for w in words]
        site = r['sites'].get(addr, addr)
        assert words[-1] == 0, 'C2 code must end with the branch-back slot'
        ops.append(Hook(site, g.read_dol_word(dol, site), words, cur, note=note[addr]))
        cur += (len(words) * 4 + 15) & ~15
    for addr, word in r['ext']:
        import struct
        ops.append(Patch(addr, struct.pack('>I', word), dol.read(addr, 4),
                         note='disable the "extension not supported" error'))
    if cur > CC_END:
        raise SystemExit('cc code overflows its window: 0x%X > 0x%X' % (cur, CC_END))
    title = 'Classic Controller (%s style)' % ('B/A' if style == 'ba' else 'Y/B')
    return Feature('cc_' + style, title, region, ops)
