#!/usr/bin/env python3
"""Run a patched Kirby disc in Dolphin with GameCube pads and no Wii Remote, and read the
game's KPAD state back over Dolphin's GDB stub.

  dolphin_test.py <image> <disc id> [boot seconds]

Needs a build with the test hook (DEBUG_FEED=1 KIRBY_DOLS=... KIRBY_PREBUILT=<dir> python3 tools/gen_prebuilt.py,
and the same KIRBY_PREBUILT when patching the disc): the pads' responses are then written by this script
to STATE+0x40+8*port over the GDB stub, because Dolphin's pipe input device did not deliver input.
Without the test hook the real SI path runs (pass --real): the pad is detected and idles.

Prints, for every pad button, the KPAD hold word the game ends up with.
"""
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gdbmem import Gdb

DOLPHIN = '/Applications/Dolphin.app'
PORT = 2177
STATE = 0x80005D40
KPAD0 = {'SUKE01': 0x8080D088, 'SUKP01': 0x8080EA08, 'SUKJ01': 0x8080AB08, 'SUKK01': 0x8080E088}
KPAD_STRIDE = 0x688

BTN = dict(A=0x01000000, B=0x02000000, X=0x04000000, Y=0x08000000, Start=0x10000000, Z=0x00100000, L=0x00400000,
           R=0x00200000, Up=0x00080000, Down=0x00040000, Left=0x00010000, Right=0x00020000)
NEUTRAL = (0x00808080, 0x80800000)


def prepare(user, ports=1, wiimote=False):
    shutil.rmtree(user, ignore_errors=True)
    for d in ('Config', 'GameSettings'):
        os.makedirs(os.path.join(user, d))
    dev = ''.join('SIDevice%d = %d\n' % (i, 6 if i < ports else 0) for i in range(4))
    open(os.path.join(user, 'Config', 'Dolphin.ini'), 'w').write(
        "[General]\nGDBPort = %d\n[Interface]\nConfirmStop = False\nUsePanicHandlers = False\n"
        "[Core]\nMMU = True\nCPUThread = False\nCPUCore = 4\nEnableDebugging = True\nEnableCheats = False\n"
        "WiimoteContinuousScanning = False\nWiimoteControllerInterface = False\n%s"
        "[Analytics]\nPermissionAsked = True\nEnabled = False\n" % (PORT, dev))
    open(os.path.join(user, 'Config', 'WiimoteNew.ini'), 'w').write("[Wiimote1]\nSource = %d\n" % (1 if wiimote else 0))


def launch(user, image, video):
    subprocess.check_call(['open', '-n', '-a', DOLPHIN, '--args', '-b', '-u', user, '-e', image, '-v', video])
    time.sleep(2)


def stop(user):
    out = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
    for ln in out.splitlines():
        if user in ln and 'Dolphin' in ln and 'dolphin_test' not in ln:
            os.kill(int(ln.split()[0]), 9)


def kpad(g, base):
    b = g.read_mem(base, 0x80)
    hold, trig, rel = struct.unpack('>III', b[0:12])
    return dict(hold=hold, trig=trig, rel=rel, dev=b[0x5C], err=b[0x5D], dpd=b[0x5E],
                pos=struct.unpack('>ff', b[0x20:0x28]), acc=struct.unpack('>f', b[0x68:0x6C])[0],
                ls=struct.unpack('>ff', b[0x6C:0x74]), rs=struct.unpack('>ff', b[0x74:0x7C]))


def main():
    real = '--real' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    image, rid = os.path.abspath(args[0]), args[1]
    boot = float(args[2]) if len(args) > 2 else 40
    ports = int(os.environ.get('PORTS', 1))
    user = os.path.abspath(os.environ.get('USERDIR', 'work/dolphin_user'))
    prepare(user, ports, wiimote=bool(os.environ.get('WIIMOTE')))
    launch(user, image, os.environ.get('VIDEO', 'Null'))
    g = None
    for _ in range(120):
        try:
            g = Gdb(port=PORT, timeout=30)
            break
        except OSError:
            time.sleep(1)
    g.cont()

    def feed(port, h, l):
        g.interrupt()
        g.cmd('M%x,8:%s' % (STATE + 0x40 + 8 * port, struct.pack('>II', h, l).hex()))
        g.cont()

    try:
        time.sleep(boot)
        if not real:
            for p in range(ports):
                feed(p, *NEUTRAL)
        time.sleep(2)
        for port in range(ports):
            base = KPAD0[rid] + port * KPAD_STRIDE
            print('--- port %d (channel %d) ---' % (port + 1, port))
            g.interrupt(); k = kpad(g, base); g.cont()
            print('idle   hold=%08X dev=%d err=%02X ls=(%.2f,%.2f)' % (k['hold'], k['dev'], k['err'], *k['ls']), flush=True)
            if real:
                continue
            for name, bit in BTN.items():
                feed(port, NEUTRAL[0] | bit, NEUTRAL[1])
                time.sleep(0.8)
                g.interrupt(); k = kpad(g, base); g.cont()
                print('%-6s hold=%08X trig=%08X dev=%d' % (name, k['hold'], k['trig'], k['dev']), flush=True)
                feed(port, *NEUTRAL)
                time.sleep(0.4)
            # sticks: main stick right/up, C stick right
            for name, h, l in (('stick R', 0x00FF8080 & 0x0000FFFF | 0x00800000 | 0xFF00 | 0x80, NEUTRAL[1]),
                               ('stick U', (NEUTRAL[0] & ~0xFF) | 0xFF, NEUTRAL[1]),
                               ('C-st R', NEUTRAL[0], 0xFF800000)):
                feed(port, h, l)
                time.sleep(0.8)
                g.interrupt(); k = kpad(g, base); g.cont()
                print('%-6s hold=%08X dev=%d ls=(%.2f,%.2f) rs=(%.2f,%.2f)' % (name, k['hold'], k['dev'], *k['ls'], *k['rs']), flush=True)
                feed(port, *NEUTRAL)
                time.sleep(0.4)
    finally:
        stop(user)


if __name__ == '__main__':
    main()
