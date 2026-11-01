#!/usr/bin/env python3
"""Private-mode firmware and data of the M14 image (S5, D25): staging, verification, and absence in a public image.

  private-m14.py stage  --fp out/firmware-private --root ROOT --repo REPO --record OUT.json [--sensors DIR]
  private-m14.py verify --fp out/firmware-private --root ROOT --record BUILD_RECORD.json [--initrd-list FILE]
  private-m14.py absent --root ROOT [--initrd-list FILE]

Contents (all Windows-derived or generated from Windows data, never in git, never in a public ISO):
  cameras   ov13858/imx681/vd55g0 register blobs -> /usr/lib/firmware/updates/ (verified with the owner's verify_blob and MANIFEST.json)
  cdsp46    the CDSP c1-00046.1 pair -> /usr/lib/firmware-sp11-cdsp46/qcom/x1e80100/microsoft/Denali/ and the initramfs (dracut conf)
  audio     closed-loop topology (replaces the public file of the same name), sp11cl, sp11cal -> /usr/lib/firmware/qcom/x1e80100/
  sensors   the staged sensor tree out/firmware-private/sensors (sp11-sensors-stage.sh) installed by sp11-sensors-install-private.sh with the seeded registry
            -> /usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/{sensors,socinfo}/ and /var/lib/hexagonrpcd/registry
  tuning    libcamera tuning YAMLs of the cameras owner -> /usr/share/libcamera/ipa/simple/ (hashes against libcamera-tuning.manifest.json)
  spectra   CAMERA_ICP.mbn (Qualcomm Linux package, both pins) -> /usr/lib/firmware/qcom/x1e80100/ and its licence
  quality   audio quality files sp11q.bin and sp11q-dyn.bin next to sp11cl; PipeWire microphone configs -> /etc/pipewire/pipewire.conf.d/; the speaker EQ is
            stored UNLOADED under /usr/share/sp11/pipewire-gated/; sp11q-spk.bin (GATED) is NEVER installed
  npu       the installer for the operator's own QAIRT download (no QAIRT is shipped)
Output: PASS/FAIL ids, file NAMES and counts only. No value of a blob, a registry or a configuration file is ever printed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
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
SENSORS_ROOT = "usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11"
REGISTRY = "var/lib/hexagonrpcd/registry"
SENSORS_FP = "sensors"
TUNING = {"ov13858": "ov13858.yaml", "imx681": "imx681.yaml"}
TUNING_DEST = "usr/share/libcamera/ipa/simple"
ICP_FP = "cameras/spectra/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn"
ICP_DEST = "usr/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn"
ICP_SHA = "4a75fd1ae5b47960698e3b5bd614a0484f05c068144f4e603332ab6e746ef4c8"
ICP_LIC_FP = "cameras/spectra/lib/firmware/LICENSE.qcom-2"
ICP_LIC_DEST = "usr/share/licenses/sp11-camera-icp/LICENSE.qcom-2"
QUALITY = (f"{CARD}-sp11q.bin", f"{CARD}-sp11q-dyn.bin")
QUALITY_GATED = f"{CARD}-sp11q-spk.bin"
PW = {"sp11-mic-quality.conf": "etc/pipewire/pipewire.conf.d/sp11-mic-quality.conf",
      "sp11-mic-echo-cancel.conf": "etc/pipewire/pipewire.conf.d/sp11-mic-echo-cancel.conf",
      "sp11-speaker-quality.conf": "usr/share/sp11/pipewire-gated/sp11-speaker-quality.conf"}
PW_FP = "audio/pipewire"
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


def sensors_counts(root, sfp):
    base = root / SENSORS_ROOT
    return {"config": sum(1 for p in (base / "sensors/config").rglob("*") if p.is_file()), "identity": sum(1 for p in (base / "socinfo").iterdir() if p.is_file()),
            "registry": sum(1 for p in (root / REGISTRY).rglob("*") if p.is_file()), "sns_reg_conf": (base / "sensors/sns_reg.conf").is_file(),
            "registry_link": os.readlink(base / "sensors/registry") if (base / "sensors/registry").is_symlink() else None,
            "stage_sums_sha256": sha(sfp / "SHA256SUMS")}


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
    # sensors: the owner's install script, registry route A (seed), then the tree is verified against the stage's SHA256SUMS
    sfp = fp / SENSORS_FP
    inst = repo / "hardware/sensors/userspace/sp11-sensors-install-private.sh"
    r = subprocess.run(["bash", str(inst), "--stage", str(sfp), "--root", str(root), "--registry", "seed"], capture_output=True, text=True)
    if r.returncode != 0:
        raise Fail("sp11-sensors-install-private.sh failed (" + (r.stderr.strip().splitlines() or ["no message"])[-1][:120] + ")")
    rec["sensors"] = sensors_counts(root, sfp)
    if rec["sensors"]["config"] != 70 or rec["sensors"]["identity"] != 6 or rec["sensors"]["registry"] != 293:
        raise Fail("sensor tree counts differ from the owner's evidence (70 config, 6 identity, 293 registry): " + json.dumps(rec["sensors"]))
    # libcamera tuning YAMLs (the owner's manifest holds their hashes)
    man = json.loads((fp / "cameras/libcamera/libcamera-tuning.manifest.json").read_text())
    for sensor, name in TUNING.items():
        src = fp / "cameras/libcamera" / name
        if man[sensor]["yaml_sha256"] != sha(src):
            raise Fail(f"libcamera tuning {name}: hash differs from libcamera-tuning.manifest.json")
        put(src, root / TUNING_DEST / name)
    rec["tuning"] = {n: sha(fp / "cameras/libcamera" / n) for n in TUNING.values()}
    # Spectra ICP firmware: both pins (tarball pin in the fetch script, file pin here)
    icp = fp / ICP_FP
    if not icp.is_file() or sha(icp) != ICP_SHA:
        raise Fail("CAMERA_ICP.mbn missing or its SHA-256 pin differs (hardware/cameras/spectra/rpm/fetch-camera-icp.sh)")
    put(icp, root / ICP_DEST)
    put(fp / ICP_LIC_FP, root / ICP_LIC_DEST)
    rec["spectra_icp"] = {"CAMERA_ICP.mbn": sha(icp), "LICENSE.qcom-2": sha(fp / ICP_LIC_FP)}
    # audio quality files: sp11q and sp11q-dyn next to sp11cl; sp11q-spk is GATED and never installed; PipeWire configs
    for name in QUALITY:
        src = fp / AUDIO_FP / name
        if not src.is_file():
            raise Fail(f"audio quality file {name} missing")
        put(src, root / AUDIO_DEST / name)
    rec["audio_quality"] = {n: sha(fp / AUDIO_FP / n) for n in QUALITY}
    for name, dest in PW.items():
        src = fp / PW_FP / name
        if not src.is_file():
            raise Fail(f"PipeWire quality config {name} missing")
        put(src, root / dest)
    rec["pipewire"] = {n: sha(fp / PW_FP / n) for n in PW}
    # npu installer (no QAIRT)
    put(repo / "hardware/npu/userspace/sp11-npu-install-private.sh", root / NPU, 0o755)
    rec["npu_installer_sha256"] = sha(repo / "hardware/npu/userspace/sp11-npu-install-private.sh")
    Path(a.record).write_text(json.dumps(rec, indent=1))
    print(f"private-m14: staged cameras={len(CAM)} cdsp46={len(CDSP_FILES)} audio={len(AUDIO)} quality={len(QUALITY)} pipewire={len(PW)} tuning={len(TUNING)} icp=1 "
          f"sensors config={rec['sensors']['config']} identity={rec['sensors']['identity']} registry={rec['sensors']['registry']} npu=1")


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
    # sensors: every installed file equals its line in the stage's SHA256SUMS (config, identity, registry seed), symlink, counts
    sfp = fp / SENSORS_FP
    sums = {}
    for line in (sfp / "SHA256SUMS").read_text().splitlines():
        h, _, name = line.partition("  ")
        sums[name.lstrip("./")] = h
    base = root / SENSORS_ROOT
    bad_s = []
    for name, h in sums.items():
        if name.startswith("registry-seed/"):
            dst = root / REGISTRY / name[len("registry-seed/"):]
        elif name.startswith("sensors/") or name.startswith("socinfo/"):
            dst = base / name
        else:
            continue
        if name == "sensors/registry" or not dst.is_file() or sha(dst) != h:
            bad_s.append(name)
    cnt = sensors_counts(root, sfp)
    chk("sensors: 70 config files, 6 identity files, sns_reg.conf, 293 registry seed files equal the private stage by hash", not bad_s and cnt["config"] == 70 and cnt["identity"] == 6
        and cnt["registry"] == 293 and cnt["sns_reg_conf"], f"{len(bad_s)} differ")
    chk("sensors: sensors/registry is a symlink to /var/lib/hexagonrpcd/registry", cnt["registry_link"] == "/var/lib/hexagonrpcd/registry")
    chk("record: sensor counts equal the installed ones", rec.get("sensors") == cnt)
    chk("tuning: libcamera YAMLs equal the private tree and the owner's manifest hashes, mode 0644", all(same(fp / "cameras/libcamera" / n, root / TUNING_DEST / n) for n in TUNING.values())
        and all(json.loads((fp / "cameras/libcamera/libcamera-tuning.manifest.json").read_text())[s]["yaml_sha256"] == sha(root / TUNING_DEST / n) for s, n in TUNING.items()))
    chk("spectra: CAMERA_ICP.mbn equals the private tree and the pin, licence installed", same(fp / ICP_FP, root / ICP_DEST) and sha(root / ICP_DEST) == ICP_SHA and same(fp / ICP_LIC_FP, root / ICP_LIC_DEST))
    chk("quality: sp11q and sp11q-dyn equal the private tree", all(same(fp / AUDIO_FP / n, root / AUDIO_DEST / n) for n in QUALITY))
    chk("quality: the GATED sp11q-spk.bin is NOT in the image", not (root / AUDIO_DEST / QUALITY_GATED).exists() and not list(root.glob("usr/lib/firmware/**/*sp11q-spk*")))
    chk("quality: PipeWire configs equal the private tree (microphone configs active, speaker EQ stored unloaded)", all(same(fp / PW_FP / n, root / d) for n, d in PW.items())
        and not (root / "etc/pipewire/pipewire.conf.d/sp11-speaker-quality.conf").exists())
    chk("record: tuning, ICP, quality and PipeWire hashes equal the installed ones", rec.get("tuning") == {n: sha(root / TUNING_DEST / n) for n in TUNING.values()}
        and rec.get("spectra_icp") == {"CAMERA_ICP.mbn": sha(root / ICP_DEST), "LICENSE.qcom-2": sha(root / ICP_LIC_DEST)}
        and rec.get("audio_quality") == {n: sha(root / AUDIO_DEST / n) for n in QUALITY} and rec.get("pipewire") == {n: sha(root / d) for n, d in PW.items()})
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

    here = ([CAM_DEST + "/" + n for n in CAM.values()] + [CDSP_ROOT, DRACUT, SENSORS, SENSORS_ROOT + "/socinfo", REGISTRY, NPU, ICP_DEST, ICP_LIC_DEST]
            + [TUNING_DEST + "/" + n for n in TUNING.values()] + list(PW.values()) + [AUDIO_DEST + "/" + n for n in list(AUDIO) + list(QUALITY) + [QUALITY_GATED] if not n.endswith("-tplg.bin")])
    present = [p for p in here if (root / p).exists()]
    chk("public image: no camera blob, tuning YAML, sensor configuration or registry, audio quality or PipeWire quality file, topology variant, CAMERA_ICP, CDSP alternate or NPU installer", not present, ",".join(present))
    t = root / AUDIO_DEST / f"{CARD}-tplg.bin"
    chk("public image: the topology is the public file", t.is_file() and sha(t) == PUBLIC_TPLG)
    if a.initrd_list:
        chk("public image: no alternate CDSP firmware in the initramfs", CDSP_ROOT not in Path(a.initrd_list).read_text())
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage"); s.add_argument("--fp", required=True); s.add_argument("--root", required=True); s.add_argument("--repo", required=True)
    s.add_argument("--record", required=True); s.add_argument("--sensors", default="")   # --sensors is ignored (the tree is out/firmware-private/sensors)
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
