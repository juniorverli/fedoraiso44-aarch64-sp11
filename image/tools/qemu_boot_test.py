#!/usr/bin/env python3
"""L1 driver: boot an SP11 ISO in QEMU (virt, TCG, edk2) and judge the result.

Called by scripts/image-test-qemu.sh inside the Fedora 44 container. It starts QEMU with the
serial console on a pty, waits for the GRUB menu, selects "VM test (no devicetree)", watches
the boot, waits until the collector has written logs to the SP11LOGS disk, shuts the VM down
and reads the logs back with mtools. Exit status 0 = pass.

Pass (image/README.md "L1 emulated boot"): GRUB menu lists all entries; GDM started;
/sys/kernel/btf/vmlinux exists; the collector wrote a complete <boot-id>/ to SP11LOGS;
no unit failed except the allow-list (image/l1-allowed-failed-units.txt).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

import pexpect

ENTRIES = [
    "SP11 debug",
    "SP11 debug + DRM trace",
    "SP11 debug nomodeset",
    "SP11 debug, stop in initramfs",
    "VM test (no devicetree)",
]
FATAL = [
    (rb"Kernel panic - not syncing", "kernel panic"),
    (rb"[Ee]mergency mode", "emergency mode"),
    (rb"Dropping to debug shell", "dracut debug shell"),
    # not the bare unit name: systemd debug (kernel arg "debug") lists dracut-emergency.service at every boot
    (rb"Starting dracut-emergency\.service|Starting Dracut Emergency Shell|Generating \"/run/initramfs/rdsosreport\.txt\"", "dracut emergency"),
    (rb"Warning: .*could not boot", "dracut: could not boot"),
]


def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def mtools_listing(img, path=""):
    r = sh("mdir", "-i", img, "-b", f"::{path}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def mtools_cat(img, path):
    r = subprocess.run(["mtype", "-i", img, f"::{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def read_log(img, bootdir, name):
    """Read name or name.gz from <bootdir>/ of the SP11LOGS image."""
    import gzip
    data = mtools_cat(img, f"{bootdir}/{name}")
    if data is None:
        gz = subprocess.run(["mtype", "-i", img, f"::{bootdir}/{name}.gz"], capture_output=True)
        if gz.returncode == 0:
            try:
                return gzip.decompress(gz.stdout).decode(errors="replace")
            except Exception:
                return None
        return None
    return data.decode(errors="replace")


def find_bootdir(img):
    for entry in mtools_listing(img):
        e = entry.replace("::", "", 1).strip("/")
        if re.fullmatch(r"[0-9a-f-]{36}", e):
            if mtools_cat(img, f"{e}/COMPLETE") is not None:
                return e
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", required=True)
    ap.add_argument("--logs", required=True, help="raw FAT image labelled SP11LOGS")
    ap.add_argument("--work", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--cpu", default="neoverse-n1")
    ap.add_argument("--smp", default="8")
    ap.add_argument("--mem", default="4096")
    ap.add_argument("--timeout-min", type=int, default=150)
    ap.add_argument("--stall-min", type=int, default=25)
    ap.add_argument("--poll-sec", type=int, default=120)
    ap.add_argument("--allow", default="")
    ap.add_argument("--entry", default="VM test (no devicetree)")
    a = ap.parse_args()

    os.makedirs(a.work, exist_ok=True)
    serial_log = os.path.join(a.work, "serial.log")
    vars_img = os.path.join(a.work, "vars.raw")
    shutil.copy("/usr/share/edk2/aarch64/vars-template-pflash.raw", vars_img)
    mon = os.path.join(a.work, "monitor.sock")
    if os.path.exists(mon):
        os.unlink(mon)

    res = {"checks": [], "iso": a.iso, "cpu": a.cpu, "smp": a.smp, "mem_mb": a.mem}

    def check(name, ok, detail=""):
        res["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + (": " + detail if detail else ""), flush=True)

    cmd = [
        "qemu-system-aarch64",
        "-machine", "virt,gic-version=3",
        "-accel", "tcg,thread=multi",
        "-cpu", a.cpu, "-smp", a.smp, "-m", a.mem,
        "-drive", "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/edk2/aarch64/QEMU_EFI-silent-pflash.raw",
        "-drive", f"if=pflash,format=raw,unit=1,file={vars_img}",
        "-device", "qemu-xhci,id=xhci",
        "-drive", f"if=none,id=iso,format=raw,readonly=on,file={a.iso}",
        "-device", "usb-storage,bus=xhci.0,drive=iso,bootindex=1",
        "-drive", f"if=none,id=logs,format=raw,file={a.logs}",
        "-device", "usb-storage,bus=xhci.0,drive=logs",
        "-device", "virtio-gpu-pci",
        "-device", "usb-kbd,bus=xhci.0",
        "-netdev", "user,id=n0", "-device", "virtio-net-pci,netdev=n0",
        "-device", "virtio-rng-pci",
        "-display", "none", "-serial", "stdio",
        "-monitor", f"unix:{mon},server=on,wait=off",
        "-no-reboot",
    ]
    print("QEMU:", " ".join(cmd), flush=True)
    start = time.time()
    deadline = start + a.timeout_min * 60
    logf = open(serial_log, "wb")
    child = pexpect.spawn(cmd[0], cmd[1:], timeout=60, maxread=65536, encoding=None)
    child.logfile_read = logf

    state = {"menu": False, "selected": False, "cmdline": False, "gdm": False, "target": False,
             "fatal": None, "stall": False}
    buf_all = b""
    last_data = time.time()
    poll_t = 0
    bootdir = None
    ok_logs = False

    patterns = [pexpect.TIMEOUT, pexpect.EOF]
    try:
        while time.time() < deadline:
            try:
                chunk = child.read_nonblocking(65536, timeout=5)
                buf_all += chunk
                buf_all = buf_all[-400000:]
                last_data = time.time()
            except pexpect.TIMEOUT:
                pass
            except pexpect.EOF:
                print("QEMU exited", flush=True)
                break
            now = time.time()
            if not state["menu"] and all(e.encode() in buf_all for e in ENTRIES):
                state["menu"] = True
                print(f"[{int(now - start)}s] GRUB menu with all {len(ENTRIES)} entries on the serial console", flush=True)
            if state["menu"] and not state["selected"] and a.entry.encode() in buf_all:
                time.sleep(2)
                idx = ENTRIES.index(a.entry)
                for _ in range(idx):
                    child.send(b"\x1b[B")
                    time.sleep(0.5)
                time.sleep(1)
                child.send(b"\r")
                state["selected"] = True
                buf_all = b""
                print(f"[{int(now - start)}s] selected '{a.entry}' ({idx} x Down, Enter)", flush=True)
            if state["selected"]:
                if re.search(rb"sp11\.entry=vmtest", buf_all):
                    state["cmdline"] = True
                if re.search(rb"Started .*(GNOME Display Manager|gdm)|gdm\.service", buf_all) and re.search(rb"(OK|Started).*(GNOME Display Manager|gdm)", buf_all):
                    state["gdm"] = True
                if re.search(rb"Reached target .*(Multi-User|Graphical)", buf_all):
                    state["target"] = True
                for pat, label in FATAL:
                    if re.search(pat, buf_all):
                        state["fatal"] = label
            if state["fatal"]:
                print(f"[{int(now - start)}s] FATAL on the serial console: {state['fatal']}", flush=True)
                break
            if now - last_data > a.stall_min * 60:
                state["stall"] = True
                print(f"no serial output for {a.stall_min} min, giving up", flush=True)
                break
            # poll the logs disk (read-only mtools) once the system is far enough
            if state["selected"] and now - poll_t > a.poll_sec:
                poll_t = now
                bd = find_bootdir(a.logs)
                if bd:
                    btf = read_log(a.logs, bd, "btf.txt") or ""
                    gdm = read_log(a.logs, bd, "gdm-status.txt") or ""
                    if "btf: present" in btf and "Active: active (running)" in gdm:
                        bootdir = bd
                        print(f"[{int(now - start)}s] collector logs show BTF present and GDM running", flush=True)
                        break
        else:
            print("timeout", flush=True)
    finally:
        pass

    res["serial_seconds"] = int(time.time() - start)
    # graceful power-off so the collector writes its last snapshot, then a hard stop
    if child.isalive():
        try:
            import socket
            s = socket.socket(socket.AF_UNIX)
            s.settimeout(15)
            s.connect(mon)
            s.recv(4096)
            s.send(b"system_powerdown\n")
            print("system_powerdown sent", flush=True)
            t0 = time.time()
            while child.isalive() and time.time() - t0 < 600:
                try:
                    child.read_nonblocking(65536, timeout=5)
                except pexpect.TIMEOUT:
                    pass
                except pexpect.EOF:
                    break
            if child.isalive():
                s.send(b"quit\n")
                time.sleep(3)
        except Exception as e:
            print("monitor error:", e, flush=True)
        if child.isalive():
            child.terminate(force=True)
    logf.close()

    # ------------------------------------------------------------ verdict ----
    check("GRUB menu shows all entries", state["menu"])
    check(f"entry '{a.entry}' selected and booted (sp11.entry=vmtest on the kernel command line)", state["cmdline"])
    bd = find_bootdir(a.logs)
    check("collector wrote a complete <boot-id>/ to SP11LOGS (COMPLETE marker)", bd is not None, bd or "no complete boot directory")
    if bd:
        files = mtools_listing(a.logs, bd)
        res["log_files"] = files
        btf = read_log(a.logs, bd, "btf.txt") or ""
        check("/sys/kernel/btf/vmlinux exists (btf.txt)", "btf: present" in btf, btf.strip().splitlines()[0] if btf else "btf.txt missing")
        gdm = read_log(a.logs, bd, "gdm-status.txt") or ""
        gdm_ok = state["gdm"] or "Active: active (running)" in gdm
        check("GDM started (serial 'Started ... GNOME Display Manager' or gdm.service active in the logs)", gdm_ok,
              "serial" if state["gdm"] else ("logs" if gdm_ok else (gdm.strip().splitlines()[2] if len(gdm.strip().splitlines()) > 2 else "no gdm status")))
        for need in ("dmesg.txt", "journal.txt", "cmdline.txt", "lscpu.txt", "STATUS"):
            check(f"collector file {need}", any(f.lstrip('/').split('/')[-1] in (need, need + ".gz") for f in files))
        failed = read_log(a.logs, bd, "units-failed.txt") or ""
        units = re.findall(r"^[\s●*x]*(\S+\.(?:service|socket|mount|timer|target|path|automount))\s", failed, re.M)
        allow = set()
        if a.allow and os.path.exists(a.allow):
            allow = {l.strip() for l in open(a.allow) if l.strip() and not l.startswith("#")}
        bad = [u for u in units if u not in allow]
        res["failed_units"] = units
        check("no failed unit outside the allow-list", not bad, ", ".join(bad) if bad else f"{len(units)} failed, all allowed" if units else "none failed")
        # copy the logs next to the report for the operator
        dst = os.path.join(a.work, "collected")
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst)
        subprocess.run(["mcopy", "-i", a.logs, "-s", "-n", f"::{bd}", dst], capture_output=True)
        cmdline = read_log(a.logs, bd, "cmdline.txt") or ""
        check("kernel command line in the logs has no quiet/rhgb and has debug", not re.search(r"\b(quiet|rhgb)\b", cmdline) and "debug" in cmdline, cmdline.strip())
    else:
        check("/sys/kernel/btf/vmlinux exists (btf.txt)", False, "no logs")
        check("GDM started", state["gdm"], "serial only" if state["gdm"] else "no evidence")
    if state["fatal"]:
        check("no fatal boot message", False, state["fatal"])
    if state["stall"]:
        check("console kept printing", False, f"silent for {a.stall_min} min")
    res["state"] = state
    res["ok"] = all(c["ok"] for c in res["checks"])
    json.dump(res, open(a.report, "w"), indent=1)
    print("L1", "PASS" if res["ok"] else "FAIL", flush=True)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
