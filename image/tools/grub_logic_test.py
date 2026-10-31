#!/usr/bin/env python3
"""Run the GRUB environment logic of the M14 main entry in QEMU (edk2, real grubaa64.efi) and judge it.

Usage (inside the container of scripts/image-container.sh):
  grub_logic_test.py --iso ISO --work DIR --report JSON [--esp-offset-bytes N]

What it does: copies the ISO (writable), and for each case writes an environment block into the ESP file
EFI/BOOT/grubenv (GPT partition 2 of the copy), boots QEMU, lets GRUB time out into the first menu line (the main
entry), reads the serial console for the three `SP11:` echo lines the entry prints, stops QEMU as soon as they are
in (the kernel is not needed), and reads the block back with mtools. A case passes when the DTB name, the CDSP
variant and the block written by GRUB's save_env are exactly the expected ones. Nothing here touches the host.
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

BLOCK = 1024
HEADER = "# GRUB Environment Block\n"


def envblock(variables):
    body = HEADER + "".join(f"{k}={v}\n" for k, v in variables.items())
    assert len(body) <= BLOCK
    return (body + "#" * (BLOCK - len(body))).encode()


def parse_block(data):
    out = {}
    for line in data.decode(errors="replace").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v
    return out


# name: (preset block or None for "no block file", expected DTB, expected used variant, expected variables after GRUB, expected markers)
CASES = [
    ("empty block", {}, "m14", 0, {"sp11_gpu_state": "", "sp11_cdsp_variant": "1"}, "previous boot: none"),
    ("state ok, SAM counter kept", {"sp11_gpu_state": "ok", "sp11_cdsp_variant": "1", "sp11_sam_counter": "5"}, "m14", 1,
     {"sp11_gpu_state": "ok", "sp11_cdsp_variant": "2", "sp11_sam_counter": "5"}, "previous boot: none"),
    ("state testing (previous boot died)", {"sp11_gpu_state": "testing", "sp11_cdsp_variant": "2"}, "m14-safe", 2,
     {"sp11_gpu_state": "failed", "sp11_cdsp_variant": "3"}, "previous boot: died"),
    ("state failed stays failed", {"sp11_gpu_state": "failed", "sp11_cdsp_variant": "3"}, "m14-safe", 3,
     {"sp11_gpu_state": "failed", "sp11_cdsp_variant": "0"}, "previous boot: none"),
    ("garbage variant counts as 0", {"sp11_gpu_state": "ok", "sp11_cdsp_variant": "9"}, "m14", 0,
     {"sp11_gpu_state": "ok", "sp11_cdsp_variant": "1"}, "previous boot: none"),
    ("garbage state boots the GPU DTB", {"sp11_gpu_state": "banana"}, "m14", 0,
     {"sp11_gpu_state": "banana", "sp11_cdsp_variant": "1"}, "previous boot: none"),
]
DESC = {0: "fw=c1-00078 keep_proxy_pds=0", 1: "fw=c1-00046.1 keep_proxy_pds=0", 2: "fw=c1-00078 keep_proxy_pds=1", 3: "fw=c1-00046.1 keep_proxy_pds=1"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--cases", default="", help="comma separated case numbers (default all)")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    iso = os.path.join(a.work, "iso-rw.img")
    shutil.copyfile(a.iso, iso)
    gpt = subprocess.run(["sgdisk", "-i", "2", iso], capture_output=True, text=True).stdout
    m = re.search(r"First sector: (\d+)", gpt)
    if not m:
        print("no GPT partition 2", flush=True)
        return 2
    esp = f"{iso}@@{int(m.group(1)) * 512}"
    res = {"iso": a.iso, "cases": []}
    sel = [int(x) for x in a.cases.split(",") if x] or list(range(len(CASES)))
    ok_all = True

    def check(name, ok, detail=""):
        nonlocal ok_all
        ok_all &= bool(ok)
        res["cases"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + (": " + detail if detail else ""), flush=True)

    # the shipped block must exist, be exactly one block and look like one
    r = subprocess.run(["mtype", "-i", esp, "::EFI/BOOT/grubenv"], capture_output=True)
    shipped = r.stdout
    check("ESP carries EFI/BOOT/grubenv as one 1024-byte environment block", r.returncode == 0 and len(shipped) == BLOCK and shipped.startswith(HEADER.encode()),
          f"{len(shipped)} bytes")
    for n in sel:
        name, preset, dtb, used, after, prev = CASES[n]
        blk = os.path.join(a.work, "grubenv.preset")
        open(blk, "wb").write(envblock(preset))
        subprocess.run(["mcopy", "-o", "-i", esp, blk, "::EFI/BOOT/grubenv"], check=True)
        vars_img = os.path.join(a.work, "vars.raw")
        shutil.copy("/usr/share/edk2/aarch64/vars-template-pflash.raw", vars_img)
        log = os.path.join(a.work, f"serial-{n}.log")
        cmd = ["qemu-system-aarch64", "-machine", "virt,gic-version=3", "-accel", "tcg,thread=multi", "-cpu", "neoverse-n1", "-smp", "4", "-m", "3072",
               "-drive", "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/edk2/aarch64/QEMU_EFI-silent-pflash.raw",
               "-drive", f"if=pflash,format=raw,unit=1,file={vars_img}",
               "-device", "qemu-xhci,id=xhci",
               "-drive", f"if=none,id=iso,format=raw,readonly=off,file={iso}",
               "-device", "usb-storage,bus=xhci.0,drive=iso,bootindex=1",
               "-device", "virtio-gpu-pci", "-device", "usb-kbd,bus=xhci.0",
               "-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot"]
        t0 = time.time()
        child = pexpect.spawn(cmd[0], cmd[1:], timeout=60, maxread=65536, encoding=None)
        child.logfile_read = open(log, "wb")
        buf = b""
        got = None
        try:
            while time.time() - t0 < a.timeout:
                try:
                    buf += child.read_nonblocking(65536, timeout=5)
                except pexpect.TIMEOUT:
                    pass
                except pexpect.EOF:
                    break
                if re.search(rb"SP11: CDSP variant \d: [^\r\n]+[\r\n]", buf):
                    got = buf
                    time.sleep(6)   # let GRUB finish the sleep and start loading the kernel; save_env is long done
                    break
        finally:
            if child.isalive():
                child.terminate(force=True)
            child.logfile_read.close()
        text = (got or buf).decode(errors="replace")
        d = re.search(r"devicetree x1p64100-microsoft-denali-(\S+?)\.dtb", text)
        v = re.search(r"SP11: CDSP variant (\d): ([^\r\n]*)", text)
        p = re.search(r"\(previous boot: (\w+)\)", text)
        env = parse_block(subprocess.run(["mtype", "-i", esp, "::EFI/BOOT/grubenv"], capture_output=True).stdout)
        check(f"[{name}] main entry chose DTB {dtb}", bool(d) and d[1] == dtb, f"{d[1] if d else 'no echo'} after {int(time.time() - t0)} s")
        check(f"[{name}] CDSP variant {used} ({DESC[used]})", bool(v) and int(v[1]) == used and v[2].strip() == DESC[used], f"{v[1] + ': ' + v[2].strip() if v else 'no echo'}")
        check(f"[{name}] {prev}", bool(p) and f"previous boot: {p[1]}" == prev, p[1] if p else "no echo")
        check(f"[{name}] block after GRUB save_env", all(env.get(k) == x for k, x in after.items()), ", ".join(f"{k}={env.get(k)}" for k in after))
    # restore the shipped block in the copy only (the ISO itself was never touched)
    res["ok"] = ok_all
    json.dump(res, open(a.report, "w"), indent=1)
    print("GRUB logic", "PASS" if ok_all else "FAIL", flush=True)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
