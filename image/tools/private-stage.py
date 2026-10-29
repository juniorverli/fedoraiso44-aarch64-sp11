#!/usr/bin/env python3
"""Private build mode of the SP11 image generator (operator-owned device, never redistributed).

  private-stage.py stage  --mac-conf F --board F --out DIR [--board-sha256 HEX]
  private-stage.py verify --root R --mac-conf F [--board F] [--record JSON] [--owner-root]
  private-stage.py leaks  --mac-conf F PATH...
  private-stage.py repo-clean --mac-conf F --repo DIR

Policy: address values and Windows-derived board bytes may exist only inside the staging tree
(removed after use) and inside the ISO root file system. This tool never prints an address; it
reports names of checks, file paths and SHA-256 prefixes. Exit status 0 only when all pass.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

SENTINELS = {"000000000000", "FFFFFFFFFFFF", "000000005AAD"}
BOARD_MAGIC = b"QCA-ATH12K-BOARD\0"
NM_CONF = "etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf"
LINK = "etc/systemd/network/10-sp11-wifi.link"
BT = "etc/sp11/bt-address"
BOARD = "usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin"
# ath12k binds as ath12k_wifi7_pci on 7.3 (wifi README, section 4)
DRIVER_GLOB = "ath12k*"


class Fail(Exception):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_macs(conf: Path) -> dict:
    """Return {'WIFI_MAC': 'AA:BB:..', 'BT_MAC': ...}; raise Fail without echoing a value."""
    try:
        text = conf.read_text()
    except OSError as e:
        raise Fail(f"cannot read MAC source {conf}: {e.strerror}")
    out = {}
    for key in ("WIFI_MAC", "BT_MAC"):
        vals = [l.split("=", 1)[1].strip().strip("\"'") for l in text.splitlines() if l.startswith(key + "=")]
        if len(vals) != 1:
            raise Fail(f"{conf} must hold exactly one {key}= line")
        v = vals[0].replace("-", ":").upper()
        if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", v):
            raise Fail(f"{key} in {conf} is not a six-byte colon/dash address")
        if v.replace(":", "") in SENTINELS:
            raise Fail(f"{key} in {conf} is a sentinel, not a device identity")
        if int(v[:2], 16) & 1:
            raise Fail(f"{key} in {conf} is a multicast address")
        out[key] = v
    return out


def mac_patterns(macs: dict):
    forms = []
    for v in macs.values():
        c = v.replace(":", "")
        forms += [v, v.replace(":", "-"), c]
    return [f.encode() for f in set(forms)] + [f.lower().encode() for f in set(forms)]


def contains_mac(data: bytes, macs: dict) -> bool:
    low = data.lower()
    return any(p.lower() in low for p in mac_patterns(macs))


def check_board(path: Path, want: str = "") -> bytes:
    try:
        data = path.read_bytes()
    except OSError as e:
        raise Fail(f"derived Wi-Fi board file missing: {path} ({e.strerror}). "
                   "Build it first: hardware/wifi/README.md request F2 (wifi-board2.py build)")
    if not data.startswith(BOARD_MAGIC):
        raise Fail(f"{path} is not an ath12k board-2.bin (magic mismatch)")
    if len(data) < 1024:
        raise Fail(f"{path} is implausibly small ({len(data)} bytes)")
    if want and sha(data) != want.lower():
        raise Fail(f"{path} SHA-256 differs from the pinned value")
    return data


def write(root: Path, rel: str, data: bytes, mode: int):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(p, mode)


def cmd_stage(a):
    macs = read_macs(Path(a.mac_conf))
    board = check_board(Path(a.board), a.board_sha256 or "")
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, mode=0o700)
    root = out / "root"
    wifi, bt = macs["WIFI_MAC"], macs["BT_MAC"]
    # format of /usr/libexec/sp11-bt-address: one upper-case colon address, optional newline
    write(root, BT, (bt + "\n").encode(), 0o600)
    # Fedora-native: NetworkManager owns the station address; the .link makes it
    # persistent from the first udev event (and for tools outside NetworkManager).
    write(root, NM_CONF, (
        "# SP11 private build: operator device address. Do not share this image.\n"
        "[device-sp11-wifi-mac]\n"
        f"match-device=driver:{DRIVER_GLOB}\n"
        "wifi.scan-rand-mac-address=no\n"
        "\n[connection-sp11-wifi-mac]\n"
        f"match-device=driver:{DRIVER_GLOB}\n"
        f"wifi.cloned-mac-address={wifi}\n").encode(), 0o600)
    write(root, LINK, (
        "# SP11 private build: operator device address. Do not share this image.\n"
        "[Match]\n"
        f"Driver={DRIVER_GLOB}\n"
        "Type=wlan\n\n"
        "[Link]\n"
        f"MACAddress={wifi}\n").encode(), 0o600)
    write(root, BOARD, board, 0o644)
    rec = {"private": True,
           "wifi_mac": {"present": True, "sha256_8": sha(wifi.encode())[:8]},
           "bt_mac": {"present": True, "sha256_8": sha(bt.encode())[:8]},
           "wifi_board2": {"present": True, "size": len(board), "sha256": sha(board),
                           "install_path": "/" + BOARD},
           "installed": ["/" + BT, "/" + NM_CONF, "/" + LINK, "/" + BOARD]}
    Path(a.out, "private-record.json").write_text(json.dumps(rec, indent=1) + "\n")
    print("private stage ready: bt-address, NetworkManager conf, .link, board-2.bin; values withheld")


def cmd_verify(a):
    macs = read_macs(Path(a.mac_conf))
    root = Path(a.root)
    bad = []

    def chk(name, ok):
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            bad.append(name)

    def st(rel):
        try:
            return os.lstat(root / rel)
        except OSError:
            return None

    def meta(rel, mode):
        s = st(rel)
        ok = s is not None and stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode) == mode
        if ok and a.owner_root:
            ok = s.st_uid == 0 and s.st_gid == 0
        return ok

    def text(rel):
        try:
            return (root / rel).read_bytes()
        except OSError:
            return b""

    bt = text(BT)
    chk("bt-address: exists, regular, mode 0600" + (", root-owned" if a.owner_root else ""), meta(BT, 0o600))
    chk("bt-address: one upper-case colon address plus newline (format of sp11-bt-address)",
        re.fullmatch(rb"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}\n", bt) is not None)
    chk("bt-address: value equals BT_MAC of the source (hash compare)",
        sha(bt.strip()) == sha(macs["BT_MAC"].encode()))
    nm = text(NM_CONF)
    chk("NetworkManager conf: mode 0600", meta(NM_CONF, 0o600))
    m = re.findall(rb"^wifi\.cloned-mac-address=(.*)$", nm, re.M)
    chk("NetworkManager conf: single cloned-mac-address equal to WIFI_MAC (hash compare)",
        len(m) == 1 and sha(m[0]) == sha(macs["WIFI_MAC"].encode()))
    chk("NetworkManager conf: scan-rand-mac-address=no, driver match", b"wifi.scan-rand-mac-address=no" in nm
        and re.search(rb"^match-device=driver:ath12k", nm, re.M) is not None)
    lk = text(LINK)
    m = re.findall(rb"^MACAddress=(.*)$", lk, re.M)
    chk(".link: mode 0600, [Match] Driver=ath12k*, MACAddress equals WIFI_MAC (hash compare)",
        meta(LINK, 0o600) and b"[Match]" in lk and re.search(rb"^Driver=ath12k", lk, re.M) is not None
        and len(m) == 1 and sha(m[0]) == sha(macs["WIFI_MAC"].encode()))
    chk("board-2.bin: regular file mode 0644, ath12k board magic",
        meta(BOARD, 0o644) and text(BOARD).startswith(BOARD_MAGIC))
    if a.board:
        try:
            want = Path(a.board).read_bytes()
        except OSError:
            want = None
        chk("board-2.bin: bytes equal the local derived file", want is not None and text(BOARD) == want)
    fed = root / "usr/lib/firmware/ath12k/WCN7850/hw2.0"
    chk("Fedora packaged board-2.bin.xz left intact (override wins through updates/)",
        (fed / "board-2.bin.xz").is_file() or (fed / "board-2.bin").is_file())
    chk("no override in the Fedora path itself", not (fed / "board-2.bin").exists())
    if a.record:
        raw = Path(a.record).read_bytes()
        rec = json.loads(raw)
        p = rec.get("private") or {}
        chk("build record: private section present, hashes only",
            isinstance(p, dict) and p.get("wifi_mac", {}).get("present") is True and
            p.get("bt_mac", {}).get("present") is True and
            p.get("wifi_board2", {}).get("sha256") == sha(text(BOARD)))
        chk("build record: no address value in any form", not contains_mac(raw, macs))
    sys.exit(1 if bad else 0)


def scan_paths(paths, macs):
    hits = []
    for p in map(Path, paths):
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file() and not f.is_symlink()] if p.is_dir() else []
        for f in files:
            try:
                if contains_mac(f.read_bytes(), macs):
                    hits.append(str(f))
            except OSError:
                pass
    return hits


def cmd_leaks(a):
    macs = read_macs(Path(a.mac_conf))
    hits = scan_paths(a.paths, macs)
    for h in hits:
        print("LEAK " + h)
    print(f"{'FAIL' if hits else 'PASS'} leaks: {len(hits)} file(s) hold an address value")
    sys.exit(1 if hits else 0)


def cmd_repo_clean(a):
    macs = read_macs(Path(a.mac_conf))
    repo = Path(a.repo)
    # Plain walk (a worktree's .git file may point outside the container): everything except .git,
    # the out/ link and symlinks, i.e. a superset of the tracked files.
    files = []
    for d, dirs, names in os.walk(repo):
        dirs[:] = [x for x in dirs if x != ".git" and not (Path(d) == repo and x == "out") and not Path(d, x).is_symlink()]
        files += [Path(d, n) for n in names if not Path(d, n).is_symlink()]
    hits = scan_paths(files, macs)
    names = files
    for h in hits:
        print("LEAK " + h)
    print(f"{'FAIL' if hits else 'PASS'} repo-clean: {len(names)} tracked/untracked files, {len(hits)} with an address value")
    sys.exit(1 if hits else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--mac-conf", required=True)
    s.add_argument("--board", required=True)
    s.add_argument("--board-sha256")
    s.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--root", required=True)
    v.add_argument("--mac-conf", required=True)
    v.add_argument("--board")
    v.add_argument("--record")
    v.add_argument("--owner-root", action="store_true")
    l = sub.add_parser("leaks")
    l.add_argument("--mac-conf", required=True)
    l.add_argument("paths", nargs="+")
    r = sub.add_parser("repo-clean")
    r.add_argument("--mac-conf", required=True)
    r.add_argument("--repo", required=True)
    a = ap.parse_args()
    try:
        {"stage": cmd_stage, "verify": cmd_verify, "leaks": cmd_leaks, "repo-clean": cmd_repo_clean}[a.cmd](a)
    except Fail as e:
        print(f"private-stage: REFUSED: {e}", file=sys.stderr)
        sys.exit(6)


if __name__ == "__main__":
    main()
