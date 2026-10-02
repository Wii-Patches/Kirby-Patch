"""Find the Kirby's Return to Dream Land addresses the GameCube-pad patch needs in any release.

Everything is written once against the USA main.dol (SUKE01); the European and
Japanese builds carry the same compiled code at other addresses.  A function is
located by matching a window of USA instructions against the target DOL with the
relocatable bits (branch displacements, address halves, small-data offsets)
masked out, and it must match exactly once.  Data addresses are then read back
from the matched code (the lis + addi that references them), never guessed.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from dol import Dol


def mask(w):
    op = w >> 26
    if op == 18:                                   # b / bl: keep opcode, AA, LK
        return w & 0xFC000003
    if op == 16:                                   # bc: keep everything but the displacement
        return w & 0xFFFF0003
    if op in (14, 15, 24, 25, 26, 27, 28, 29):     # addi / lis / ori / oris / xori / andi
        return w & 0xFFFF0000
    if 32 <= op <= 55:                             # loads / stores: drop the displacement
        return w & 0xFFFF0000
    return w


def words(d, va, n):
    b = d.read(va, n * 4)
    return list(struct.unpack('>%dI' % n, b)) if b and len(b) == n * 4 else None


class Finder:
    def __init__(self, ref, tgt):
        self.ref, self.tgt = ref, tgt
        o, a, s, _ = [x for x in tgt.secs if x[3] == 1][0]
        self.tw = struct.unpack('>%dI' % (s // 4), tgt.data[o:o + s])
        self.tbase = a
        self.tm = [mask(w) for w in self.tw]

    def locate(self, ref_va, n=24):
        """The target's address of the code at ref_va; must match exactly once."""
        rm = [mask(w) for w in words(self.ref, ref_va, n)]
        first, hits = rm[0], []
        for i in range(len(self.tm) - n):
            if self.tm[i] == first and self.tm[i:i + n] == rm:
                hits.append(self.tbase + i * 4)
        if len(hits) != 1:
            raise SystemExit('anchor %08X: %d matches in %s' % (ref_va, len(hits), self.tgt.path))
        return hits[0]

    def pair(self, ref_va, ref_target, n=40, span=64):
        """The target's value for the address the lis + addi pair near ref_va loads
        (ref_target in the USA build)."""
        t_va = self.locate(ref_va, n)
        rw, tw = words(self.ref, ref_va, span), words(self.tgt, t_va, span)

        def imm(w):
            v = w & 0xFFFF
            return v - 0x10000 if v & 0x8000 else v

        for i in range(span):
            w = rw[i]
            if w >> 26 != 15:
                continue
            reg = (w >> 21) & 31
            for j in range(i + 1, min(span, i + 16)):
                w2 = rw[j]
                if w2 >> 26 == 14 and (w2 >> 16) & 31 == reg:
                    if (((w & 0xFFFF) << 16) + imm(w2)) & 0xFFFFFFFF == ref_target:
                        t, t2 = tw[i], tw[j]
                        assert t >> 26 == 15 and t2 >> 26 == 14
                        return (((t & 0xFFFF) << 16) + imm(t2)) & 0xFFFFFFFF
        raise SystemExit('no lis/addi pair for %08X near %08X' % (ref_target, ref_va))


# USA addresses
KPAD_READ = 0x8006E030          # KPADiRead: stwu r1,-576(r1)
SAMPLE_OFF = 0x8006E1D4 - KPAD_READ  # lbz r0,0x17b(r21): the "any sample queued?" check
WPAD_PROBE = 0x80057530         # WPADProbe(chan, &type): stwu r1,-16(r1)
SI_GET_TYPE = 0x8002B890
OS_DISABLE = 0x800219C0
OS_RESTORE = 0x80021A00
SI_TYPES = 0x8073FF48           # si:: per-port device type cache (lis/addi in SIGetType)
KPAD0 = 0x8080D088             # channel 0's KPAD struct (0x688 bytes per channel); only for testing
WPAD_TBL = 0x80806ED0           # WPAD's per-channel control block pointers (lis/addi in WPADProbe)


def resolve(ref, tgt):
    f = Finder(ref, tgt)
    r = dict(KPADiRead=f.locate(KPAD_READ, 40), WPADProbe=f.locate(WPAD_PROBE, 20),
             SIGetType=f.locate(SI_GET_TYPE, 40), OSDisableInterrupts=f.locate(OS_DISABLE, 6),
             OSRestoreInterrupts=f.locate(OS_RESTORE, 6))
    r['SampleCheck'] = r['KPADiRead'] + SAMPLE_OFF
    r['SiTypes'] = f.pair(SI_GET_TYPE, SI_TYPES)
    r['SiBusy'] = r['SiTypes'] - 0x18
    r['SiShadow'] = r['SiBusy'] + 4
    r['WpadTbl'] = f.pair(WPAD_PROBE, WPAD_TBL, 20)
    r['Kpad0'] = f.pair(KPAD_READ, KPAD0, 40, 64)
    return r


if __name__ == '__main__':
    ref = Dol(sys.argv[1])
    for p in sys.argv[2:]:
        print(os.path.basename(p), {k: '%08X' % v for k, v in resolve(ref, Dol(p)).items()})
