"""Carry USA addresses over to another release of the game by masked-signature search.

A site is found by taking the instructions around it in the reference (USA) main.dol,
masking the bits that change when code moves (branch displacements, address-sized
immediates, small-data offsets), and searching the target for the same window.  The
window grows until it matches exactly once.
"""
import struct

from anchors import mask


class Relocator:
    def __init__(self, ref, tgt):
        self.ref, self.tgt = ref, tgt
        self.rt = self._text(ref)
        self.tt = self._text(tgt)

    @staticmethod
    def _text(d):
        out = []
        for o, a, s, i in d.secs:
            if i < 7:
                w = struct.unpack('>%dI' % (s // 4), d.data[o:o + s])
                out.append((a, b''.join(struct.pack('>I', mask(x)) for x in w)))
        return out

    def _window(self, addr, before, after):
        for a, blob in self.rt:
            if a <= addr - 4 * before and addr + 4 * after < a + len(blob):
                i = (addr - a) // 4
                return blob[(i - before) * 4:(i + after) * 4]
        return None

    def _search(self, pat):
        hits = []
        for a, blob in self.tt:
            i = blob.find(pat)
            while i != -1:
                if i % 4 == 0:
                    hits.append(a + i)
                i = blob.find(pat, i + 1)
        return hits

    def locate(self, addr, sizes=(6, 12, 24, 48, 96)):
        """The target's address of the instruction at `addr` in the reference."""
        for n in sizes:
            for before, after in ((n, n), (2 * n, 1), (1, 2 * n), (n, 0 + 1), (0, n), (3 * n, 1), (1, 3 * n)):
                pat = self._window(addr, before, after)
                if pat is None:
                    continue
                hits = self._search(pat)
                if len(hits) == 1:
                    return hits[0] + 4 * before
        raise SystemExit('no unique match for 0x%08X in %s' % (addr, self.tgt.path))

    def same_insn(self, ref_addr, tgt_addr):
        """The instruction at the two addresses agrees once relocatable bits are masked."""
        a, b = self.ref.read(ref_addr, 4), self.tgt.read(tgt_addr, 4)
        return a is not None and b is not None and mask(struct.unpack('>I', a)[0]) == mask(struct.unpack('>I', b)[0])

    def _bounded(self, addr, lo, hi, ctx=3):
        """Search for `addr`'s instruction and its `ctx` neighbours either side, between two target addresses."""
        pat = self._window(addr, ctx, ctx + 1)
        if pat is None:
            return None
        hits = [h + 4 * ctx for h in self._search(pat) if lo <= h + 4 * ctx <= hi]
        return hits[0] if len(hits) == 1 else None

    def relocate_all(self, addrs):
        """{ref address: target address} for the addresses that exist in the target.

        Code moves as whole blocks, so the distance a site moved by is shared with its
        neighbours.  A site found by its own context is trusted only if it moved by the same
        distance as the nearest trusted site on one side or the other (a coincidental match
        elsewhere does not); a site that cannot be found is looked for between its
        neighbours' placements.  Whatever is left is returned unplaced (absent from the dict)
        and listed by the caller: it is either missing from the target, or needs a person."""
        import bisect
        addrs = sorted(addrs)
        raw = {}
        for a in addrs:
            try:
                t = self.locate(a)
            except SystemExit:
                continue
            if self.same_insn(a, t):
                raw[a] = t
        # trusted: the shift equals a neighbour's shift (neighbours among the raw hits)
        keys = sorted(raw)
        trusted = {}
        for i, a in enumerate(keys):
            d = raw[a] - a
            near = [raw[k] - k for k in keys[max(0, i - 2):i] + keys[i + 1:i + 3]]
            if d in near:
                trusted[a] = raw[a]
        found = dict(trusted)
        tk = sorted(trusted)
        for a in addrs:
            if a in found:
                continue
            i = bisect.bisect(tk, a)
            lo = trusted[tk[i - 1]] if i else 0
            hi = trusted[tk[i]] if i < len(tk) else 0xFFFFFFFF
            t = self._bounded(a, lo, hi)
            if t is None or not self.same_insn(a, t):
                t = self._check_between(a, lo, hi, set(found.values()))
            if t is not None:
                found[a] = t
        return found

    @staticmethod
    def _w(d, a):
        b = d.read(a, 4)
        return struct.unpack('>I', b)[0] if b else 0

    def _check_shape(self, d, a):
        """(branch word, compare word, defining word) when `a` is a conditional branch right after
        `cmpwi crN,rX,0` (or cmplwi) of a value that the instruction before it computed -- the
        shape of the protection's integrity checks."""
        br, cmp_, dfn = self._w(d, a), self._w(d, a - 4), self._w(d, a - 8)
        if br >> 26 != 16 or (cmp_ >> 26) not in (10, 11) or cmp_ & 0xFFFF:
            return None
        ra = (cmp_ >> 16) & 31
        if (dfn >> 26) != 31 or ((dfn >> 21) & 31) == ra and False:
            return None
        if (dfn >> 26) == 31 and ((dfn >> 16) & 31) == ra or (dfn >> 26) == 31 and ((dfn >> 21) & 31) == ra:
            return br, cmp_, dfn
        return None

    def _check_between(self, addr, lo, hi, taken):
        """The one not-yet-placed integrity check between two placed sites that looks like `addr`."""
        want = self._check_shape(self.ref, addr)
        if want is None:
            return None
        key = (want[0] & 0xFFE30003, want[2] >> 26 and (want[2] >> 1) & 0x3FF)
        cands = []
        for x in range(lo + 4, min(hi, lo + 0x20000), 4):
            if x in taken:
                continue
            got = self._check_shape(self.tgt, x)
            if got and (got[0] & 0xFFE30003, (got[2] >> 1) & 0x3FF) == key:
                cands.append(x)
        return cands[0] if len(cands) == 1 else None
