#!/usr/bin/env python3
"""Private-mode firmware and data of the M14 image (S5, D25): staging, verification, and absence in a public image.

  private-m14.py stage  --fp out/firmware-private --root ROOT --repo REPO --record OUT.json [--sensors DIR]
  private-m14.py verify --fp out/firmware-private --root ROOT --record BUILD_RECORD.json [--initrd-list FILE]
  private-m14.py absent --root ROOT [--initrd-list FILE]

Contents (all Windows-derived or generated from Windows data, never in git, never in a public ISO):
  cameras   ov13858/imx681/vd55g0 register blobs -> /usr/lib/firmware/updates/ (verified with the owner's verify_blob and MANIFEST.json)
  cdsp46    the CDSP c1-00046.1 pair -> /usr/lib/firmware-sp11-cdsp46/qcom/x1e80100/microsoft/Denali/ and the initramfs (dracut conf)
  audio     closed-loop topology (replaces the public file of the same name), sp11cl, sp11cal -> /usr/lib/firmware/qcom/x1e80100/
  sensors   the staged sensor configuration (sp11-sensors-stage.sh) -> /usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/sensors/
  npu       the installer for the operator's own QAIRT download (no QAIRT is shipped)
Output: PASS/FAIL ids, file NAMES and counts only. No value of a blob, a registry or a configuration file is ever printed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

CAM = {"ov13858": "ov13858-mshw0491.bin", "imx681": "imx681-mshw0490.bin", "vd55g0": "vd55g0-mshw0492.bin"}
CAM_DEST = "usr/lib/firmware/updates"
CDSP_DIR = "qcom/x1e80100/microsoft/Denali"
CDSP_FILES = ("qccdsp8380.mbn", "cdsp_dtb.mbn")
CDSP_ROOT = "usr/lib/firmware-sp11-cdsp46"
CDSP_FP = "dsp-subsystems/cdsp-c1-00046.1-woa-200.0.49.0"
DRACUT = "etc/dracut.conf.d/93-sp11-cdsp46.conf"
AUDIO_FP = "audio/qcom/x1e80100"
AUDIO_DEST = "usr/lib/firmware/qcom/x1e80100"
CARD = "X1E80100-Microsoft-Surface-Pro-11"
AUDIO = {f"{CARD}-tplg.bin": None, f"{CARD}-sp11cl.bin": "2eb5a1144d7718422210fd634d2b29f3c318025d56959b501e2c7a7c501ab280", f"{CARD}-sp11cal.bin": None}
PUBLIC_TPLG = "b192044f01e97eabe7f6df9ae0d394086badb3c30124573210bc781093da8c03"
SENSORS = "usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/sensors"
NPU = "usr/libexec/sp11/sp11-npu-install-private"


class Fail(Exception):
    pass


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def put(src, dst, mode=0o644):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    os.chmod(dst, mode)
    if os.getuid() == 0:
        os.chown(dst, 0, 0)


def cmd_stage(a):
    fp, root, repo = Path(a.fp), Path(a.root), Path(a.repo)
    rec = {}
    # cameras: the owner's structural verification, then the manifest hash
    spec = importlib.util.spec_from_file_location("bcf", repo / "hardware/cameras/userspace/build-camera-firmware.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    manifest = json.loads((fp / "cameras/MANIFEST.json").read_text())
    want = {Path(b["output"]).name: b["output_sha256"] for b in manifest["blobs"]}
    for sensor, name in CAM.items():
        src = fp / "cameras" / name
        if name not in want or not src.is_file():
            raise Fail(f"camera blob {name} missing from the private tree or its manifest")
        if sha(src) != want[name]:
            raise Fail(f"camera blob {name}: hash differs from MANIFEST.json")
        try:
            mod.verify_blob(src.read_bytes())
        except AssertionError as e:
            raise Fail(f"camera blob {name}: the owner's verify_blob refused it ({e})")
        put(src, root / CAM_DEST / name)
    rec["cameras"] = {n: sha(fp / "cameras" / n) for n in CAM.values()}
    # CDSP alternate pair
    sums = {}
    for line in (fp / CDSP_FP / "SHA256SUMS").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1].lstrip("*")] = parts[0]
    for f in CDSP_FILES:
        src = fp / CDSP_FP / f
        if sums.get(f) != sha(src):
            raise Fail(f"CDSP alternate {f}: hash differs from SHA256SUMS")
        put(src, root / CDSP_ROOT / CDSP_DIR / f)
    (root / DRACUT).parent.mkdir(parents=True, exist_ok=True)
    (root / DRACUT).write_text("# M14 private: the alternate CDSP pair must be in the initramfs, because early PAS (D20) requests the firmware before the\n"
                               "# root file system exists. Selected with firmware_class.path=/usr/lib/firmware-sp11-cdsp46 (GRUB CDSP rotor).\n"
                               "install_items+=\" " + " ".join(f"/{CDSP_ROOT}/{CDSP_DIR}/{f}" for f in CDSP_FILES) + " \"\n")
    rec["cdsp46"] = {f: sha(fp / CDSP_FP / f) for f in CDSP_FILES}
    # audio
    for name, pin in AUDIO.items():
        src = fp / AUDIO_FP / name
        if not src.is_file():
            raise Fail(f"audio file {name} missing (run hardware/audio-speakers/userspace/build-topology/build-closedloop.sh)")
        if pin and sha(src) != pin:
            raise Fail(f"audio file {name}: hash differs from the audio-speakers evidence")
        if name.endswith("-tplg.bin") and sha(src) == PUBLIC_TPLG:
            raise Fail("the private topology equals the public one: the closed-loop file was not generated")
        put(src, root / AUDIO_DEST / name)
    rec["audio"] = {n: sha(fp / AUDIO_FP / n) for n in AUDIO}
    # sensors
    if a.sensors and Path(a.sensors).is_dir():
        n = 0
        for src in sorted(Path(a.sensors).rglob("*")):
            if src.is_file():
                put(src, root / SENSORS / src.relative_to(a.sensors))
                n += 1
        if n == 0:
            raise Fail("the staged sensor tree is empty")
        rec["sensors"] = {"files": n}
    else:
        rec["sensors"] = {"files": 0, "note": "not staged"}
    # npu installer (no QAIRT)
    put(repo / "hardware/npu/userspace/sp11-npu-install-private.sh", root / NPU, 0o755)
    rec["npu_installer_sha256"] = sha(repo / "hardware/npu/userspace/sp11-npu-install-private.sh")
    Path(a.record).write_text(json.dumps(rec, indent=1))
    print(f"private-m14: staged cameras={len(CAM)} cdsp46={len(CDSP_FILES)} audio={len(AUDIO)} sensors={rec['sensors']['files']} npu=1")


def cmd_verify(a):
    fp, root = Path(a.fp), Path(a.root)
    bad = []

    def chk(i, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + i + (": " + detail if (detail and not ok) else ""))
        if not ok:
            bad.append(i)

    def same(src, dst):
        return src.is_file() and dst.is_file() and sha(src) == sha(dst) and dst.stat().st_mode & 0o777 == 0o644 and dst.stat().st_uid == 0

    chk("cameras: three blobs equal the private tree, mode 0644, root", all(same(fp / "cameras" / n, root / CAM_DEST / n) for n in CAM.values()),
        ",".join(n for n in CAM.values() if not same(fp / "cameras" / n, root / CAM_DEST / n)))
    spec = importlib.util.spec_from_file_location("bcf", Path(__file__).resolve().parents[2] / "hardware/cameras/userspace/build-camera-firmware.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok = True
    for n in CAM.values():
        try:
            mod.verify_blob((root / CAM_DEST / n).read_bytes())
        except (AssertionError, OSError):
            ok = False
    chk("cameras: the owner's verify_blob accepts the installed blobs", ok)
    chk("cdsp46: pair equals the private tree and SHA256SUMS", all(same(fp / CDSP_FP / f, root / CDSP_ROOT / CDSP_DIR / f) for f in CDSP_FILES))
    dr = (root / DRACUT).read_text() if (root / DRACUT).is_file() else ""
    chk("cdsp46: dracut config installs both files", all(f"/{CDSP_ROOT}/{CDSP_DIR}/{f}" in dr for f in CDSP_FILES))
    if a.initrd_list:
        lst = Path(a.initrd_list).read_text()
        chk("cdsp46: both files are in the initramfs", all(f"{CDSP_ROOT}/{CDSP_DIR}/{f}" in lst for f in CDSP_FILES))
    chk("audio: closed-loop topology, sp11cl, sp11cal equal the private tree", all(same(fp / AUDIO_FP / n, root / AUDIO_DEST / n) for n in AUDIO))
    chk("audio: the topology differs from the public file", sha(root / AUDIO_DEST / f"{CARD}-tplg.bin") != PUBLIC_TPLG)
    chk("audio: sp11cl equals the evidence hash", sha(root / AUDIO_DEST / f"{CARD}-sp11cl.bin") == AUDIO[f"{CARD}-sp11cl.bin"])
    rec = json.loads(Path(a.record).read_text()).get("private_m14", {})
    chk("record: hashes of the private files equal the installed ones", rec.get("cameras") == {n: sha(root / CAM_DEST / n) for n in CAM.values()}
        and rec.get("cdsp46") == {f: sha(root / CDSP_ROOT / CDSP_DIR / f) for f in CDSP_FILES}
        and rec.get("audio") == {n: sha(root / AUDIO_DEST / n) for n in AUDIO})
    n = sum(1 for p in (root / SENSORS).rglob("*") if p.is_file()) if (root / SENSORS).is_dir() else 0
    chk("sensors: staged configuration installed", n > 0 and n == rec.get("sensors", {}).get("files"), f"{n} files")
    chk("npu: installer present, mode 0755, no QAIRT in the image", (root / NPU).is_file() and (root / NPU).stat().st_mode & 0o777 == 0o755
        and not any((root / p).exists() for p in ("opt/sp11-npu", "opt/qairt")))
    sys.exit(1 if bad else 0)


def cmd_absent(a):
    root = Path(a.root)
    bad = []

    def chk(i, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + i + (": " + detail if (detail and not ok) else ""))
        if not ok:
            bad.append(i)

    here = [CAM_DEST + "/" + n for n in CAM.values()] + [CDSP_ROOT, DRACUT, SENSORS, NPU] + [AUDIO_DEST + "/" + n for n in AUDIO if not n.endswith("-tplg.bin")]
    present = [p for p in here if (root / p).exists()]
    chk("public image: no camera blob, CDSP alternate, closed-loop speaker file, sensor configuration or NPU installer", not present, ",".join(present))
    t = root / AUDIO_DEST / f"{CARD}-tplg.bin"
    chk("public image: the topology is the public file", t.is_file() and sha(t) == PUBLIC_TPLG)
    if a.initrd_list:
        chk("public image: no alternate CDSP firmware in the initramfs", CDSP_ROOT not in Path(a.initrd_list).read_text())
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage"); s.add_argument("--fp", required=True); s.add_argument("--root", required=True); s.add_argument("--repo", required=True)
    s.add_argument("--record", required=True); s.add_argument("--sensors", default="")
    v = sub.add_parser("verify"); v.add_argument("--fp", required=True); v.add_argument("--root", required=True); v.add_argument("--record", required=True)
    v.add_argument("--initrd-list", default="")
    b = sub.add_parser("absent"); b.add_argument("--root", required=True); b.add_argument("--initrd-list", default="")
    a = ap.parse_args()
    try:
        {"stage": cmd_stage, "verify": cmd_verify, "absent": cmd_absent}[a.cmd](a)
    except Fail as e:
        print(f"FAIL private-m14: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
