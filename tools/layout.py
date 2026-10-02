"""Where the hook trampolines live in the injected low-memory section.

Every patch is a set of hooks: one instruction in the game is replaced by a
branch to a small self-contained routine that runs the displaced instruction
and branches back.  A Gecko code handler stores those routines itself (C2
codes); the patched DOL and the Riivolution patch need somewhere to put them,
so the patcher adds one text section at CAVE_BASE.

0x80001800-0x80003000 is the Wii's boot-time scratch area, which the game itself
never touches (the game's own code starts at 0x80004000).  The first 0x20 bytes
are skipped: the word at 0x80001800 is overwritten by the OS early on.  The
Classic Controller engine and the GameCube controller hooks each get a fixed
window; the two button styles share one (only one of them is ever installed).
The routines hold no variables of their own: the GameCube hooks keep their small
state in zeroed padding inside the game's own first text section (STATE in
src/gen_gc.py).
"""
CAVE_BASE = 0x80001820
CAVE_LIMIT = 0x80003000

CC_BASE = 0x80001820          # Classic Controller engine trampolines
CC_END = 0x80002200
GC_BASE = 0x80002200          # GameCube controller hook trampolines
GC_END = 0x80003000

WINDOWS = {'cc_ba': (CC_BASE, CC_END), 'cc_yb': (CC_BASE, CC_END),
           'gc_ba': (GC_BASE, GC_END), 'gc_yb': (GC_BASE, GC_END),
           'meta': (0, 0)}
