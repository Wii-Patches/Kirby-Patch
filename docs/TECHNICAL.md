# Technical notes

How the patches work, where they hook, and how one set of data becomes a
patched `main.dol`, a Gecko code list and a Riivolution patch. For installing
and playing, see the [README](../README.md).

Addresses below are the **USA** `main.dol` (`SUKE01`) unless noted; the table at
the end lists the other releases.

## One data set, three outputs

Every patch is a list of operations on one release's `main.dol`:

| Operation | Static (`main.dol`) | Gecko | Riivolution |
| --- | --- | --- | --- |
| **Hook** — replace one instruction with a branch to a routine that runs the displaced instruction and branches back | branch + trampoline in the injected section | `C2` code | `<memory>` (branch + trampoline) |
| **Patch** — overwrite an instruction | in place | `04` code | `<memory>` |

`tools/prebuilt/<feature>_<disc id>.json` holds those operations, including the
retail instruction expected at every site. `tools/ops.py` turns them into each
format, `tools/patcher.py` applies them (and refuses a `main.dol` whose sites do
not match, so already-modified or foreign dumps are never touched), and
`tools/build.py` writes `codes/` and `riivolution/`. `tools/check.py` fails if
the committed files drift from the data; `tools/verify.py` checks the data
against real retail DOLs for every combination of options.

The features are `cc_ba` / `cc_yb` (Classic Controller, the two button styles),
`gc_ba` / `gc_yb` (GameCube controllers, built for the style they sit next to)
and `meta` (the Metafortress bypass, static-only).

**Hooks are self-contained.** A routine carries everything it needs and reaches
game code through absolute addresses, never a relative `bl` — a Gecko code
handler runs the routine from wherever it keeps it, so a relative branch to the
game would land in the wrong place. `tools/check.py` rejects any relative branch
that leaves its routine. The static build parks the routines in one new text
section at `0x80001820` (the Wii's boot-time scratch area, which this game never
touches: the game's own code starts at `0x80004000`). The GameCube hooks keep
a few words of state at `0x80005D40`, in zeroed padding inside the game's first
text section (it is the source image of the exception vectors and is never
executed or read).

## Metafortress

The game ships with a full symbol map for the Metafortress binary protection to
reference, and any change to `main.dol` trips it. Vague Rant's bypass
(`src/metaknight/*.xml`, ~1,400 one-word `<memory>` writes) switches off the
checks; a rewritten `main.dol` needs it, a Gecko code or Riivolution memory patch
(which changes memory only after the game is running) does not. The `meta`
feature carries those writes and a SHA-1 of the retail words they replace, which
the patcher verifies before patching.

## The idea: make every controller a Classic Controller

The game's `KPAD` library (SDK function names: `KPADiRead`, `read_kpad_button`,
`read_kpad_ext`, `read_kpad_acc`, `calc_acc_variable`) turns the Wii Remote's raw
samples into a status structure. There are three or so variants of KPAD in the
wild; this game has the newest: one `0x688`-byte struct per channel from
`0x8080D088`, a ring of 16 (or more) samples of `0x42` bytes at `+0x180`, the next
write slot at `+0x17A`, the number of queued samples at `+0x17B`, and the
extended ring (a pointer at `+0x5A0`, extra count at `+0x5A4`).

**The Classic Controller code** (Vague Rant, crediar) hooks four places:

| Hook | Site | What it does |
| --- | --- | --- |
| `read_kpad_button` | `0x8006B074` | `r4` = extension type, `r8` = Classic Controller buttons: sets the Wii Remote bits (held sideways) the game reads, in B/A or Y/B style; pretends to be a bare Wii Remote |
| `read_kpad_acc` | `0x8006B63C` | emulates a shake whenever the Wii Remote's shake bit (`0x80`, set for X / L / R) is held |
| `calc_acc_variable` | `0x8006C1B8` | pointer emulation from the right stick (it calls a game function, which is why the pointer code differs per release) |
| `read_kpad_ext` | `0x8006D120` | the left stick as a D-pad (the game moves with the D-pad) |
| `isExtConnected` / `isClassicValid` | `0x801ABD10`, `0x801ABD84` | two patches that disable the "extension not supported" error |

The two button styles differ in three words of the button table (the `ori` after
the A, B and Y tests), the Japanese release in the addresses of the two patches,
and the European release in all addresses and in the game function the pointer
code calls.

**The GameCube patch** makes a GameCube controller indistinguishable from a
Classic Controller to that code, in three hooks (`src/gcpad.c`, one blob each, with
the register-saving stubs in `src/hooks.S`):

| Hook | Site | What it does |
| --- | --- | --- |
| poll | `KPADiRead` entry (`0x8006E030`) | Drives the Serial Interface's own auto-polling for the four ports, re-probes a replugged pad, acknowledges latched errors, and frees `si::` if an unplugged pad leaves its busy flag stuck. Does its work once per ~8 ms, whichever channel gets there first |
| sample | `KPADiRead`, at the "samples queued?" check (`0x8006E1D4`, `lbz r0,0x17b(r21)`) | Writes the pad into KPAD's sample ring as Classic Controller samples (extension 2, format 8) |
| probe | `WPADProbe` entry (`0x80057530`) | Reports a Classic Controller while a pad is plugged into the matching port, so the game believes a controller is connected |

Port *n* feeds Wii Remote channel *n*; the game maps channels to players.

### Polling the pads

The game links the SI library but not PAD, so nothing ever polls a pad.
`gc_poll` does what `PADRead` would: writes the poll command `0x00400300` to the
port's `SIC<n>OUTBUF`, latches it through `SISR`, sets the port's enable bits in
`SIPOLL` and mirrors them into `si::`'s own shadow copy (it rewrites `SIPOLL`
from the shadow on every retrace). The Serial Interface lives at `0xCD006400`
on a Wii (not `0xCC…`); the result registers are hardware-written, so the
response is read, never faked. `SiTypes` (`0x8073FF48`), the busy flag
(`SiTypes-0x18`) and the shadow (`SiTypes-0x14`) are found in `SIGetType` by
the anchor search below. The approach is [Barrel Blast Patch](https://github.com/quatric/Barrel-Blast-Patch)'s,
hardware-tested there.

### The sample

`INBUF<n>H` holds the buttons and the control stick (`[31]` error, `[23]` a real
pad's answer), `INBUF<n>L` the C stick and the triggers. A sample is `0x42`
bytes:

| Offset | Value |
| --- | --- |
| `+0x28` | device: 2 = Classic Controller |
| `+0x29` | error: 0 |
| `+0x2A` | Classic Controller buttons (u16) |
| `+0x2C/+0x2E` | left stick x/y, signed 16-bit, (byte − 128) × 3 clamped to ±308 |
| `+0x30/+0x32` | right stick |
| `+0x40` | data format: 8 (Classic Controller + accelerometer + pointer data) |

KPAD's Classic Controller branch only accepts formats 6-8; it uses 60 and 308 as
the dead zone and full deflection of the left stick, so ±100 on a GameCube stick
lands near the full range.

Two samples are written per frame, as a Wii Remote delivers two or three per
read: the game's controller code reads the left stick from the second status entry
`KPADRead` returns. The older carries the previous frame's buttons, so press and
release edges still land in the newest entry. With a Wii Remote connected, its
own samples that carry no extension get the pad as theirs, and a real Nunchuk or
Classic Controller is never touched. With no Wii Remote, the ring is empty and
the hook fills it.

### The layout

The pad's buttons become Classic Controller buttons so that the Vague Rant code
turns them into the right Wii Remote bits:

| GameCube | Classic Controller (B/A style) | Result |
| --- | --- | --- |
| A | A | 2: jump |
| B | B | 1: inhale |
| X | X | shake |
| Y | − | − : drop the copy ability |
| L, R | ZL, ZR | A: guard |
| Z | HOME | HOME Menu |
| Start | + | + : pause |
| D-pad | D-pad | D-pad |
| Control stick | left stick | move (and D-pad emulation for menus) |
| C stick | right stick | pointer |

In the Y/B style the jump and inhale buttons are the Classic Controller's B and Y
instead (the pad's A and B still jump and inhale), which is why the GameCube
patch is built once per style.

## Other releases

The KPAD, WPAD and SI libraries are the same code in every release, moved. The
sites are found by masked-signature search against the USA build
(`src/anchors.py`, which ignores branch targets and address-sized immediates and
demands exactly one match); the data addresses are read back out of the matched
code, never guessed.

| | USA | Europe | Japan | Korea |
| --- | --- | --- | --- | --- |
| `KPADiRead` entry | `0x8006E030` | `0x8006E270` | `0x8006E030` | `0x8006E040` |
| samples-queued check | `0x8006E1D4` | `0x8006E414` | `0x8006E1D4` | `0x8006E1E4` |
| `WPADProbe` | `0x80057530` | `0x80057770` | `0x80057530` | `0x80057540` |
| `SIGetType` | `0x8002B890` | `0x8002B8A0` | `0x8002B890` | `0x8002B8A0` |
| `SiTypes` | `0x8073FF48` | `0x80741388` | `0x8073E0E8` | `0x80740A08` |
| WPAD control block table | `0x80806ED0` | `0x80808850` | `0x80804950` | `0x80807ED0` |
| KPAD channel 0 | `0x8080D088` | `0x8080EA08` | `0x8080AB08` | `0x8080E088` |
| `read_kpad_button` hook | `0x8006B074` | `0x8006B2B4` | `0x8006B074` | `0x8006B084` |

## Korea

Vague Rant published the Classic Controller code and the Metafortress bypass for the
USA, European and Japanese builds only. The Korean build is the same code moved a little,
so its sites are carried over (`src/reloc.py`):

- the Classic Controller hooks and the two extension-check patches by masked-signature search
  against the USA build (each lands on the same instruction; the pointer code's game function
  is `0x8004CCE0`);
- the ~1,400 Metafortress writes from all three published lists, each searched for by the code
  around it, trusted only if it moved by the same distance as a neighbouring site, or else
  found between its neighbours' placements by the shape of the check. The method was run the
  other way as a test: from two lists it reproduces the third's every site except a handful
  the third list does differently by hand. 1,388 Korean sites come out identical from all
  three lists; the other four were decided from the Korean code itself (see `src/gen_meta.py`).

That is the unverified part: a protection check the three lists never contained would not be
bypassed. The controls were verified in Dolphin like the other releases.

## How it was tested

Dolphin, with its GDB stub reading the KPAD struct while a test build writes the
pad's response (Dolphin's pipe input device did not deliver input): the pad is
seen as a Classic Controller on a channel with no Wii Remote, and every button
lands on the bit in the layout above. `tools/dolphin_test.py` is the harness;
`tools/verify.py` re-checks every site against retail DOLs for every combination
of options. Nothing here has been run on a console.
