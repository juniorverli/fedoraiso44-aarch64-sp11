#!/usr/bin/env python3
"""L1 driver: boot an SP11 ISO in QEMU (virt, TCG, edk2) and judge the result.

Called by scripts/image-test-qemu.sh inside the Fedora 44 container. It starts QEMU with the
serial console on a pty, waits for the GRUB menu, selects "VM test (no devicetree)", watches
the boot, waits until the collector has written logs to the SP11LOGS disk, shuts the VM down
and reads the logs back with mtools. Exit status 0 = pass.

Pass (image/README.md "L1 emulated boot"): GRUB menu lists the eleven flat entries (the VM test is the last line); GDM started;
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

ENTRIES = [   # M15: one flat static menu (M13 style); the VM entry is the LAST line, selected by counting Down keys
    "SP11 debug",
    "SP11 debug, safe (no GPU, no cameras)",
    "SP11 debug, no sound",
    "SP11 debug, touch off",
    "SP11 debug, speakers (gated)",
    "SP11 debug, USB + DSP trace",
    "SP11 debug, no early DSP",
    "SP11 debug, Wi-Fi unblock probe",
    "SP11 debug nomodeset",
    "SP11 debug, stop in initramfs",
    "VM test (no devicetree)",
]
# GRUB shows only the first entries of a long menu on a 24-row serial terminal; the rest appears while scrolling.
VISIBLE_AT_START = 8
LEGACY_ENTRIES = ["SP11 debug", "SP11 debug + DRM trace", "SP11 debug nomodeset", "SP11 debug, stop in initramfs", "VM test (no devicetree)"]
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


# directory of the boot-id directories on the FAT image: "" for the SP11LOGS disk, "EFI/sp11-logs" for the
# fallback on the embedded ESP (--esp-fallback; img is then "file@@offset" in mtools notation)
LOGROOT = ""


def _p(path):
    return "/".join(x for x in (LOGROOT, path.strip("/")) if x)


def mtools_listing(img, path=""):
    r = sh("mdir", "-i", img, "-b", f"::{_p(path)}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def mtools_cat(img, path):
    r = subprocess.run(["mtype", "-i", img, f"::{_p(path)}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def read_log(img, bootdir, name):
    """Read name or name.gz from <bootdir>/ of the SP11LOGS image."""
    import gzip
    data = mtools_cat(img, f"{bootdir}/{name}")
    if data is None:
        gz = subprocess.run(["mtype", "-i", img, f"::{_p(bootdir + '/' + name + '.gz')}"], capture_output=True)
        if gz.returncode == 0:
            try:
                return gzip.decompress(gz.stdout).decode(errors="replace")
            except Exception:
                return None
        return None
    return data.decode(errors="replace")


def touch_userspace_captures(iptsd, devices, touch, cmdline, journal):
    # journalctl returns ENODATA (exit 1) when a unit glob matches no instances.
    # QEMU has no SP11 touch controller. Accept that exact result only when the
    # captured DT and boot journal independently establish this VM-only case.
    no_instance = (
        iptsd.strip() == "<capture failed: exit 1>" and
        re.search(r"(?:^|\s)sp11.entry=vmtest(?:\s|$)", cmdline) and
        all(re.search(r"^" + re.escape(path) + r"\n  ABSENT$", touch, re.M)
            for path in ("/sys/firmware/devicetree/base/soc@0/geniqup@ac0000",
                         "/sys/firmware/devicetree/base/soc@0/geniqup@ac0000/spi@a88000")) and
        "systemd[1]" in journal and
        not re.search(r"iptsd@[^\s*]+\.service|iptsd\[\d+\]", journal))
    checked_journal = "<no iptsd instance in VM>" if no_instance else iptsd
    captures = checked_journal + devices
    ok = (bool(checked_journal.strip()) and bool(devices.strip()) and
          not any(bad in captures for bad in ("<capture unavailable>", "<capture failed:", "Kernel:", "Group:", "Seat:")) and
          not re.search(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])", captures))
    return bool(ok), ("no iptsd instance in VM: absent controller, valid boot journal, journalctl ENODATA" if no_instance else "")


def find_initrd_dir(img):
    """initrd-<boot-id>/ with a COMPLETE marker below /EFI/sp11-logs (the dracut capture hook)."""
    for entry in mtools_listing(img):
        e = entry.replace("::", "", 1).strip("/").split("/")[-1]
        if re.fullmatch(r"initrd-[0-9a-f-]{36}", e) and mtools_cat(img, f"{e}/COMPLETE") is not None:
            return e
    return None


def find_bootdir(img):
    for entry in mtools_listing(img):
        e = entry.replace("::", "", 1).strip("/").split("/")[-1]   # with LOGROOT, mdir -b prints the whole path
        if re.fullmatch(r"[0-9a-f-]{36}", e):
            if mtools_cat(img, f"{e}/COMPLETE") is not None:
                return e
    return None


def verify_log_target(image_ref, boot_image, esp_fallback, status):
    """Prove the capture's physical destination independently of STATUS ordering.

    A session collector starts with CYCLE=0 and may replace STATUS with its
    early snapshot after the main collector has published COMPLETE. Early
    STATUS has no target field. The mtools source still identifies the disk
    and partition from which the completed capture was actually read.
    """
    expected = "esp" if esp_fallback else "logs"
    metadata = re.search(r"^target: (\w+)", status, re.M)
    if metadata and metadata[1] != expected:
        return False, f"STATUS names unexpected target {metadata[1]}"
    image, separator, offset = image_ref.partition("@@")
    if esp_fallback:
        if (not separator or not offset.isdecimal() or LOGROOT != "EFI/sp11-logs"
                or os.path.realpath(image) != os.path.realpath(boot_image)):
            return False, "capture source is not the boot copy's ESP log directory"
        partition = sh("sgdisk", "-i", "2", boot_image)
        start = re.search(r"First sector: (\d+)", partition.stdout)
        if (partition.returncode or not start or int(offset) != int(start[1]) * 512
                or "C12A7328-F81F-11D2-BA4B-00A0C93EC93B" not in partition.stdout):
            return False, "capture offset/type does not match GPT partition 2 of the boot copy"
        label = sh("blkid", "-p", "-O", offset, "-s", "LABEL", "-o", "value", image)
        ok = label.returncode == 0 and label.stdout.strip() == "BOOT"
        return ok, "capture read from boot copy GPT partition 2, FAT label BOOT, /EFI/sp11-logs"
    if separator or LOGROOT:
        return False, "SP11LOGS capture source unexpectedly uses a partition offset/subdirectory"
    label = sh("blkid", "-p", "-s", "LABEL", "-o", "value", image)
    return label.returncode == 0 and label.stdout.strip() == "SP11LOGS", "capture read from FAT image labelled SP11LOGS"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", required=True)
    ap.add_argument("--logs", default="", help="raw FAT image labelled SP11LOGS (not with --esp-fallback)")
    ap.add_argument("--esp-fallback", action="store_true",
                    help="no SP11LOGS disk: the ISO is attached writable (a copy) and the collector must fall back to "
                         "/EFI/sp11-logs on the embedded ESP (label BOOT); implies --early")
    ap.add_argument("--early", action="store_true",
                    help="stop as soon as the collector has a complete <boot-id>/ with BTF present; no GDM, no unit checks")
    ap.add_argument("--decoy", default="", help="raw image of a fake Windows disk (image/tools/make-decoy-disk.sh), attached "
                    "writable; its md5sum must be unchanged after the run (risk S4)")
    ap.add_argument("--initrd-fail", action="store_true",
                    help="test of the dracut failure capture: edit the VM entry in GRUB so that root=live:CDLABEL= is wrong; implies "
                         "--esp-fallback; passes when /EFI/sp11-logs/initrd-<boot-id>/ is complete on the ESP")
    ap.add_argument("--legacy-menu", action="store_true", help="the ISO has the five-entry menu of before M3")
    ap.add_argument("--until-session", action="store_true",
                    help="do not stop at the first complete collector directory: wait until the logind session triggers "
                         "(sp11-log-collector-session-*.path) have written session-<name>-* files; implies --esp-fallback")
    ap.add_argument("--no-display-files", action="store_true", help="do not require the D19 display files (ISOs older than M3)")
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

    global LOGROOT, ENTRIES
    if a.legacy_menu:
        ENTRIES = LEGACY_ENTRIES
    os.makedirs(a.work, exist_ok=True)
    if a.initrd_fail or a.until_session:
        a.esp_fallback = True
    early = a.early or a.esp_fallback
    decoy_md5 = None
    if a.decoy:
        import hashlib
        decoy_md5 = hashlib.md5(open(a.decoy, "rb").read()).hexdigest()
        print(f"decoy disk {a.decoy} md5 before: {decoy_md5}", flush=True)
    iso_path, iso_ro = a.iso, "on"
    if a.esp_fallback:
        # a copy of the ISO the guest may write to; its GPT partition 2 is the embedded ESP
        iso_path = os.path.join(a.work, "iso-rw.img")
        shutil.copyfile(a.iso, iso_path)
        iso_ro = "off"
        r = sh("sgdisk", "-i", "2", iso_path)
        m = re.search(r"First sector: (\d+)", r.stdout)
        if not m:
            print("cannot read GPT partition 2 of the ISO copy:", r.stdout, r.stderr, flush=True)
            return 2
        a.logs = f"{iso_path}@@{int(m.group(1)) * 512}"
        LOGROOT = "EFI/sp11-logs"
    elif not a.logs:
        print("--logs is required without --esp-fallback", flush=True)
        return 2
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
        "-drive", f"if=none,id=iso,format=raw,readonly={iso_ro},file={iso_path}",
        "-device", "usb-storage,bus=xhci.0,drive=iso,bootindex=1",
    ] + ([] if a.esp_fallback else [
        "-drive", f"if=none,id=logs,format=raw,file={a.logs}",
        "-device", "usb-storage,bus=xhci.0,drive=logs",
    ]) + ([
        "-drive", f"if=none,id=decoy,format=raw,file={a.decoy}",
        "-device", "usb-storage,bus=xhci.0,drive=decoy",
    ] if a.decoy else []) + [
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
            first = ENTRIES[:VISIBLE_AT_START] if len(ENTRIES) > 12 or not a.legacy_menu else ENTRIES
            if not state["menu"] and all(e.encode() in buf_all for e in first):
                state["menu"] = True
                print(f"[{int(now - start)}s] GRUB menu with its first {len(first)} of {len(ENTRIES)} entries on the serial console", flush=True)
            if state["menu"] and not state["selected"]:
                time.sleep(2)
                seen = {e for e in ENTRIES if e.encode() in buf_all}
                if a.legacy_menu:
                    idx = ENTRIES.index(a.entry)
                else:
                    idx = ENTRIES.index(a.entry)   # flat menu: position = number of Down keys
                for _ in range(idx):
                    child.send(b"\x1b[B")
                    time.sleep(0.5)
                    try:
                        chunk = child.read_nonblocking(65536, timeout=1)
                        buf_all += chunk
                        seen |= {e for e in ENTRIES if e.encode() in buf_all}
                    except (pexpect.TIMEOUT, pexpect.EOF):
                        pass
                state["entries_seen"] = len(seen)
                time.sleep(1)
                if a.initrd_fail:
                    # GRUB editor: e, to the end of the linux line (Ctrl-E), a wrong root label last (the last root= wins),
                    # a short rd.retry and no interactive shell, Ctrl-X boots. This entry exists only in this test run.
                    child.send(b"e")
                    time.sleep(3)
                    # the editor starts on the "setparams" line; the entry body begins with an empty line, then "linux"
                    for _ in range(2):
                        child.send(b"\x1b[B")
                        time.sleep(1)
                    child.send(b"\x05")
                    time.sleep(1)
                    child.send(b" root=live:CDLABEL=SP11-NO-SUCH-LABEL rd.retry=12 rd.shell=0 rd.emergency=reboot")
                    time.sleep(2)
                    child.send(b"\x18")
                else:
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
                for pat, label in ([] if a.initrd_fail else FATAL):
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
            if state["selected"] and now - poll_t > (60 if early else a.poll_sec):
                poll_t = now
                if a.initrd_fail:
                    idir = find_initrd_dir(a.logs)
                    if idir:
                        print(f"[{int(now - start)}s] initramfs capture complete: {idir}", flush=True)
                        time.sleep(10)
                        break
                    continue
                bd = find_bootdir(a.logs)
                if bd:
                    btf = read_log(a.logs, bd, "btf.txt") or ""
                    gdm = read_log(a.logs, bd, "gdm-status.txt") or ""
                    if a.until_session:
                        names = [f.lstrip('/').split('/')[-1] for f in mtools_listing(a.logs, bd)]
                        if any(n.startswith("session-first-") for n in names) and any(n.startswith("session-user-") for n in names):
                            bootdir = bd
                            print(f"[{int(now - start)}s] both logind session snapshots are in the log directory", flush=True)
                            break
                        continue
                    if early and "btf: present" in btf:
                        bootdir = bd
                        print(f"[{int(now - start)}s] collector logs complete, BTF present (early stop)", flush=True)
                        break
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
            while child.isalive() and time.time() - t0 < (120 if early else 600):
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
    def decoy_check():
        if a.decoy:
            import hashlib
            after = hashlib.md5(open(a.decoy, "rb").read()).hexdigest()
            check("fake Windows disk is byte-identical after the run (md5sum before = after, risk S4)", after == decoy_md5,
                  f"md5 {after}" + ("" if after == decoy_md5 else f" (before {decoy_md5})"))

    def esp_clean_check():
        # M5 (D21): the ESP of the stick must not be left dirty (collector and hook mount it only per write). fsck.fat -n
        # reads only; it prints "Dirty bit is set" and exits 1 when the volume was not unmounted cleanly.
        if not a.esp_fallback:
            return
        img, _, off = a.logs.partition("@@")
        out = os.path.join(a.work, "esp-after.img")
        with open(img, "rb") as f, open(out, "wb") as o:
            f.seek(int(off))
            left = 64 * 1024 * 1024
            while left:
                c = f.read(min(left, 1 << 20))
                if not c:
                    break
                o.write(c)
                left -= len(c)
        r = subprocess.run(["fsck.fat", "-n", out], capture_output=True, text=True)
        txt = (r.stdout + r.stderr).strip().replace("\n", " | ")
        check("the ESP of the stick is clean after the run (fsck.fat -n: no dirty bit)", r.returncode == 0 and "irty" not in txt, txt[:300])
        os.unlink(out)

    check("GRUB menu shows its entries (the first screen, then the rest while scrolling to the selected entry)", state["menu"] and state.get("entries_seen", 0) >= min(len(ENTRIES) - 1, 8),
          f"{state.get('entries_seen', 0)} of {len(ENTRIES)} titles seen on the serial console")
    if a.initrd_fail:
        serial = open(serial_log, "rb").read()
        check("the edited entry booted with a wrong root label (SP11-NO-SUCH-LABEL on the kernel command line)", b"SP11-NO-SUCH-LABEL" in serial)
        check("dracut gave up on the root (initqueue timeout or emergency on the console)",
              bool(re.search(rb"initqueue: timeout|Could not boot|Warning: .*could not boot|Entering emergency|sp11-initrd-log: wrote", serial)))
        idir = find_initrd_dir(a.logs)
        check("initrd-<boot-id>/ with COMPLETE is on the ESP (/EFI/sp11-logs, label BOOT)", idir is not None, idir or "none")
        if idir:
            files = [f.lstrip('/').split('/')[-1] for f in mtools_listing(a.logs, idir)]
            res["initrd_files"] = files
            for pat in (r"journal-.*\.txt\.gz", r"dmesg-.*\.txt\.gz", r"rdsosreport-.*\.txt\.gz", r"state-.*\.txt\.gz", r"STATUS\..*", r"SEQ", r"COMPLETE"):
                check(f"initrd capture file {pat}", any(re.fullmatch(pat, f, re.I) for f in files))
            st = "".join((read_log(a.logs, idir, f.rstrip(".gz")) or "") for f in files if f.upper().startswith("STATUS."))
            check("the boot medium was found by the built-in ISO label (the cmdline label is wrong on purpose)", "built-in ISO label" in st, st.strip().replace("\n", " | ")[:300])
            rep = ""
            for f in files:
                if f.startswith("rdsosreport-"):
                    rep = read_log(a.logs, idir, f[:-3]) or ""
            check("rdsosreport.txt in the capture shows the wrong label on the command line", "SP11-NO-SUCH-LABEL" in rep)
            jr = ""
            for f in files:
                if f.startswith("journal-"):
                    jr = read_log(a.logs, idir, f[:-3]) or ""
            check("initramfs journal in the capture is not empty", len(jr) > 1000, f"{len(jr)} bytes")
        check("no real-root <boot-id>/ was written (the system never got past the initramfs)", find_bootdir(a.logs) is None)
        decoy_check()
        esp_clean_check()
        res["ok"] = all(c["ok"] for c in res["checks"])
        json.dump(res, open(a.report, "w"), indent=1)
        print("L1 (initramfs failure capture)", "PASS" if res["ok"] else "FAIL", flush=True)
        return 0 if res["ok"] else 1
    check(f"entry '{a.entry}' selected and booted (sp11.entry=vmtest on the kernel command line)", state["cmdline"])
    bd = find_bootdir(a.logs)
    check("collector wrote a complete <boot-id>/ to the log target (COMPLETE marker)", bd is not None, bd or "no complete boot directory")
    if bd:
        files = mtools_listing(a.logs, bd)
        res["log_files"] = files
        btf = read_log(a.logs, bd, "btf.txt") or ""
        check("/sys/kernel/btf/vmlinux exists (btf.txt)", "btf: present" in btf, btf.strip().splitlines()[0] if btf else "btf.txt missing")
        status = read_log(a.logs, bd, "STATUS") or ""
        target_ok, target_detail = verify_log_target(a.logs, iso_path, a.esp_fallback, status)
        check(f"collector wrote to the {'embedded ESP (/EFI/sp11-logs, label BOOT)' if a.esp_fallback else 'SP11LOGS disk'}",
              target_ok, target_detail)
        if a.until_session:
            check("the logind session triggers wrote session-first-* and session-user-* files",
                  any(f.lstrip('/').split('/')[-1].startswith("session-first-") for f in files) and any(f.lstrip('/').split('/')[-1].startswith("session-user-") for f in files),
                  ", ".join(sorted(f.lstrip('/').split('/')[-1] for f in files if "session-" in f)))
            for tag in ("first", "user"):
                lg = read_log(a.logs, bd, f"session-{tag}-loginctl.txt") or ""
                check(f"session-{tag}-loginctl.txt shows a session", "SESSION" in lg or "/run/systemd/sessions" in lg, lg.strip().splitlines()[0][:120] if lg.strip() else "empty")
        if not a.no_display_files:
            lf = {x.lstrip('/').split('/')[-1].removesuffix('.gz') for x in files}
            need = ["entry.txt", "devices_deferred.txt", "device_component.txt", "drm-class-ls.txt", "lsmod.txt", "fb-state.txt",
                    "clk-display.txt", "display-dmesg.txt", "drm-state.txt", "backlight.txt", "pinctrl-pmic.txt", "dpcd-tool.txt",
                    "regulator_summary.txt", "cmdline.txt"]
            miss = [n for n in need if n not in lf]
            check("D19 display files are in the log directory", not miss, ("missing: " + ", ".join(miss)) if miss else f"{len(need)} files")
            touch = read_log(a.logs, bd, "touch-pen.txt") or ""
            check("M8 touch helper captured kernel, DT, pinctrl and firmware sections",
                  all(section in touch for section in ("7.3.0-65.sp11.12.fc44.aarch64",
                      "=== live DT and platform driver state ===",
                      "=== pinctrl ownership and configuration ===",
                      "=== installed firmware package and file")))
            iptsd = read_log(a.logs, bd, "iptsd-journal.txt") or ""
            devices = read_log(a.logs, bd, "libinput-device-names.txt") or ""
            captures_ok, captures_detail = touch_userspace_captures(
                iptsd, devices, touch, read_log(a.logs, bd, "cmdline.txt") or "",
                read_log(a.logs, bd, "journal.txt") or "")
            check("M8 iptsd journal (or evidenced absent VM instance) and names-only captures",
                  captures_ok, captures_detail)
            modules = read_log(a.logs, bd, "lsmod.txt") or ""
            check("M8 live uinput and SPI-HID modules loaded",
                  all(re.search(r"^" + name + r"\s", modules, re.M)
                      for name in ("uinput", "spi_hid", "spi_hid_of")))
            ent = read_log(a.logs, bd, "entry.txt") or ""
            check("entry.txt names the booted entry (sp11.entry=vmtest)", "sp11.entry=vmtest" in ent, ent.strip().splitlines()[0] if ent.strip() else "empty")
        gdm = read_log(a.logs, bd, "gdm-status.txt") or ""
        gdm_ok = state["gdm"] or "Active: active (running)" in gdm
        if not early:
            check("GDM started (serial 'Started ... GNOME Display Manager' or gdm.service active in the logs)", gdm_ok,
                  "serial" if state["gdm"] else ("logs" if gdm_ok else (gdm.strip().splitlines()[2] if len(gdm.strip().splitlines()) > 2 else "no gdm status")))
        for need in ("dmesg.txt", "journal.txt", "cmdline.txt", "lscpu.txt", "STATUS"):
            check(f"collector file {need}", any(f.lstrip('/').split('/')[-1] in (need, need + ".gz") for f in files))
        failed = read_log(a.logs, bd, "units-failed.txt") or "" if not early else ""
        units = re.findall(r"^[\s●*x]*(\S+\.(?:service|socket|mount|timer|target|path|automount))\s", failed, re.M)
        allow = set()
        if a.allow and os.path.exists(a.allow):
            allow = {l.strip() for l in open(a.allow) if l.strip() and not l.startswith("#")}
        bad = [u for u in units if u not in allow]
        res["failed_units"] = units
        if not early: check("no failed unit outside the allow-list", not bad, ", ".join(bad) if bad else f"{len(units)} failed, all allowed" if units else "none failed")
        # copy the logs next to the report for the operator
        dst = os.path.join(a.work, "collected")
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst)
        subprocess.run(["mcopy", "-i", a.logs, "-s", "-n", f"::{_p(bd)}", dst], capture_output=True)
        cmdline = read_log(a.logs, bd, "cmdline.txt") or ""
        check("kernel command line in the logs has no quiet/rhgb and has debug", not re.search(r"\b(quiet|rhgb)\b", cmdline) and "debug" in cmdline, cmdline.strip())
    else:
        check("/sys/kernel/btf/vmlinux exists (btf.txt)", False, "no logs")
        if not early: check("GDM started", state["gdm"], "serial only" if state["gdm"] else "no evidence")
    if state["fatal"]:
        check("no fatal boot message", False, state["fatal"])
    if state["stall"]:
        check("console kept printing", False, f"silent for {a.stall_min} min")
    decoy_check()
    esp_clean_check()
    res["state"] = state
    res["ok"] = all(c["ok"] for c in res["checks"])
    json.dump(res, open(a.report, "w"), indent=1)
    print("L1", "PASS" if res["ok"] else "FAIL", flush=True)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
