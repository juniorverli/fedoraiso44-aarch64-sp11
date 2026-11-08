#!/usr/bin/env python3
"""A stand-in for qemu-system-aarch64 that mimics the serial output and the SP11LOGS writes
of a good L1 boot, to test image/tools/qemu_boot_test.py without emulating anything.
Used by image/tools/qemu_driver_selftest.sh (PATH points here). Not a QEMU."""
import os, re, socket, subprocess, sys, time, tty

args = sys.argv[1:]
mon = re.search(r"unix:([^,]+)", " ".join(args)).group(1)
logs = re.search(r"id=logs,format=raw,file=(\S+)", " ".join(args)).group(1)
srv = socket.socket(socket.AF_UNIX)
srv.bind(mon)
srv.listen(1)
srv.setblocking(False)

def out(s):
    sys.stdout.write(s)
    sys.stdout.flush()

out("UEFI firmware (fake)\r\n")
time.sleep(1)
MENU = ["SP11 debug", "SP11 live, install from the desktop (keeps Windows)", "VM test (no devicetree)"]
IDS = ["debug", "safe", "vmtest"]
for e in MENU[:8]:   # M15: one flat menu; a 24-row terminal shows the first eight lines, the rest appears while scrolling
    out(f"\x1b[1;1H  {e}\r\n")
tty.setraw(0)  # QEMU puts the terminal in raw mode for -serial stdio
os.set_blocking(0, False)
buf = b""
choice = 0
while True:
    try:
        d = os.read(0, 100)
    except BlockingIOError:
        d = b""
    buf += d
    n = buf.count(b"\x1b[B")
    if n and n < len(MENU):
        out(f"\x1b[1;1H  {MENU[n]}\r\n")   # scrolling draws the entry that comes into view
    if b"\r" in buf:
        choice = buf.split(b"\r")[0].count(b"\x1b[B")
        break
    time.sleep(0.2)
entry = IDS[(choice + 1) % len(MENU)]   # GRUB starts on the safe entry (index 1); Down count is relative to it
out(f"Booting entry {choice}\r\n")
out(f"[    0.000000] Kernel command line: root=live:CDLABEL=X debug sp11.entry={entry}\r\n")
time.sleep(1)
out("[  OK  ] Reached target multi-user.target - Multi-User System.\r\n")
out("[  OK  ] Started gdm.service - GNOME Display Manager.\r\n")
bid = "0123abcd-0123-4abc-8def-0123456789ab"
tmp = "/tmp/fakelogs"
os.makedirs(tmp, exist_ok=True)
files = {"COMPLETE": "now\n", "STATUS": "cycle: 1\ntarget: logs\n", "btf.txt": "btf: present\n", "gdm-status.txt": "x gdm.service\n   Active: active (running)\n",
         "dmesg.txt": "d\n", "journal.txt": "j\n", "cmdline.txt": f"root=live:CDLABEL=X debug loglevel=8 sp11.entry={entry}\n",
         "lscpu.txt": "l\n", "units-failed.txt": "  UNIT LOAD ACTIVE SUB\n0 loaded units listed.\n"}
subprocess.run(["mmd", "-i", logs, f"::{bid}"])
for n, c in files.items():
    open(f"{tmp}/{n}", "w").write(c)
    subprocess.run(["mcopy", "-o", "-i", logs, f"{tmp}/{n}", f"::{bid}/{n}"])
while True:
    try:
        c, _ = srv.accept()
        c.send(b"QEMU monitor (fake)\r\n(qemu) ")
        c.setblocking(True)
        data = c.recv(100)
        if b"system_powerdown" in data or b"quit" in data:
            out("[  OK  ] Reached target poweroff.target\r\n")
            sys.exit(0)
    except BlockingIOError:
        time.sleep(0.3)
