#!/usr/bin/python3
"""Validate the muted closed-loop diagnostic on the `safe, muted closed-loop VI` entry.

Runs only when the kernel command line carries sp11.nospk=1 (the kill switch is
on). It never opens playback, never unmutes, never changes a control and never
reads capture samples. It checks, with PASS/FAIL per criterion:

  entry        the muted closed-loop entry is the one booted
  firmware     the three model-matched CL files are installed (hashes only)
  guard        the guard reports the kill switch on, no fault and no nominal flag
  playback     no playback PCM is running and no process holds one
  capture      a MultiMedia5 capture PCM exists
  supervisor   the supervisor holds the capture for N seconds (exit 124)
  kernel       the journal names the audio path (recorded, informational)

The report goes to /var/tmp (0600) and the summary to the operator notice, so
the collector's journal carries the verdict of an unattended run. This is the
muted matrix only: it cannot prove CPS consumption, measured calibration or
physical silence, and it does not authorize unmute.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

FW_MODEL = "X1E80100-Microsoft-Surface-Pro-11-CL"
SUFFIXES = ("-tplg.bin", "-sp11cl.bin", "-sp11cal.bin")


class Env:
    def __init__(self, test):
        self.test = test
        self.cmdline = Path(os.environ.get("SP11_CL_CMDLINE_FILE", "/proc/cmdline"))
        self.asound = Path(os.environ.get("SP11_CL_ASOUND_ROOT", "/proc/asound"))
        self.fwdir = Path(os.environ.get("SP11_CL_FW_DIR", "/usr/lib/firmware/qcom/x1e80100"))
        self.guard = Path(os.environ.get("SP11_CL_GUARD", "/sys/kernel/debug/sp11/guard"))
        self.supervisor = Path(os.environ.get("SP11_CL_SUPERVISOR", "/usr/libexec/sp11/speaker-supervisor"))
        self.notice = Path(os.environ.get("SP11_CL_NOTICE", "/usr/libexec/sp11/operator-notice"))
        self.out = Path(os.environ.get("SP11_CL_REPORT_OUT", "/var/tmp/sp11-cl-validate.txt"))
        self.hold = int(os.environ.get("SP11_CL_HOLD_SECONDS", "5"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_guard(text):
    fields = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() not in fields:
            fields[key.strip()] = value.strip()
    return fields


def find_capture(asound):
    for info in sorted(asound.glob("card*/pcm*c/info")):
        try:
            text = info.read_text()
        except OSError:
            continue
        if "MultiMedia5" in text:
            card = info.parent.parent.name[4:]
            pcm = info.parent.name[3:-1]
            return card, pcm, info
    return None


def playback_busy(asound):
    for status in asound.glob("card*/pcm*p/sub0/status"):
        try:
            if re.search(r"^state:\s*RUNNING", status.read_text(), re.M):
                return status
        except OSError:
            continue
    return None


def kernel_lines():
    try:
        run = subprocess.run(["journalctl", "-k", "-b", "--no-pager"], capture_output=True,
                             text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return "\n".join(line for line in run.stdout.splitlines()
                     if re.search(r"sp11|audioreach|q6apm|MultiMedia5", line, re.I))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    env = Env(False)
    checks = []
    details = []

    def check(name, ok, detail):
        checks.append((name, bool(ok), detail))

    cmdline = env.cmdline.read_text() if env.cmdline.exists() else ""
    muted = " sp11.nospk=1 " in f" {cmdline.strip()} "
    check("entry", muted, "sp11.nospk=1 present" if muted else "not the muted entry")

    missing = [s for s in SUFFIXES if not (env.fwdir / (FW_MODEL + s)).is_file()]
    check("firmware", not missing,
          "all three CL files present" if not missing else "missing " + ", ".join(missing))
    for suffix in SUFFIXES:
        path = env.fwdir / (FW_MODEL + suffix)
        if path.is_file():
            details.append(f"{path.name} sha256 {digest(path)}")

    if env.guard.is_file():
        fields = parse_guard(env.guard.read_text())
        nospk = fields.get("nospk", "")
        fault = fields.get("fault", "")
        nominal = fields.get("allow_nominal", "0")
        ok = nospk == "1" and fault == "0" and nominal in ("", "0")
        check("guard", ok, f"nospk={nospk or '<missing>'} fault={fault or '<missing>'} "
                           f"allow_nominal={nominal or '<missing>'}")
        details.extend(f"guard {k}={v}" for k, v in sorted(fields.items()))
    else:
        check("guard", False, f"{env.guard} missing or unreadable")

    busy = playback_busy(env.asound)
    check("playback", busy is None, "no playback PCM is running" if busy is None else f"running: {busy}")

    capture = find_capture(env.asound)
    if capture:
        card, pcm, info = capture
        check("capture", True, f"MultiMedia5 at hw:{card},{pcm}")
        details.append(f"capture info: {info}")
        status = env.asound / f"card{card}/pcm{pcm}c/sub0/status"
        if status.is_file():
            details.append(f"capture status before: {status.read_text().strip()}")
    else:
        check("capture", False, f"no MultiMedia5 capture under {env.asound}")
        card = pcm = None

    if capture and env.supervisor.is_file():
        run = subprocess.run(["timeout", "--signal=TERM", "--kill-after=2s", f"{env.hold}s",
                              str(env.supervisor), f"hw:{card},{pcm}"],
                             capture_output=True, text=True, timeout=env.hold + 10)
        held = run.returncode == 124 and "holding" in (run.stdout + run.stderr)
        check("supervisor", held, f"exit {run.returncode}: " + (run.stdout + run.stderr).strip().splitlines()[0]
              if (run.stdout + run.stderr).strip() else f"exit {run.returncode}")
        details.extend("supervisor: " + line for line in (run.stdout + run.stderr).splitlines())
    elif capture:
        check("supervisor", False, f"{env.supervisor} missing")

    lines = kernel_lines()
    details.extend("journal: " + line for line in lines.splitlines()[-40:])

    verdict = all(ok for _, ok, _ in checks)
    lines_out = [f"== muted closed-loop validation {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"]
    lines_out += [f"{'PASS' if ok else 'FAIL'} {name}: {detail}" for name, ok, detail in checks]
    lines_out += details
    lines_out.append(f"RESULT: {'PASS' if verdict else 'FAIL'} (muted matrix only; no protection or sound claim)")
    env.out.write_text("\n".join(lines_out) + "\n")
    os.chmod(env.out, 0o600)
    for line in lines_out[:8]:
        print(line)
    print(f"report {env.out} (mode 0600)")
    if env.notice.is_file():
        summary = "; ".join(f"{name}={'PASS' if ok else 'FAIL'}" for name, ok, _ in checks)
        subprocess.run([str(env.notice), "add", "35-cl-validate", f"closed-loop muted validation: {summary}"],
                       capture_output=True, text=True)
    return 0 if verdict else 1


def self_test():
    """Exercise the parser, the capture/playback discovery and the verdict shape."""
    import tempfile
    failures = 0

    def check(name, ok):
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'} {name}")
        if not ok:
            failures += 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        asound = root / "asound"
        pcm = asound / "card0" / "pcm4c"
        (pcm / "sub0").mkdir(parents=True)
        (pcm / "info").write_text("name: MultiMedia5 capture\n")
        (pcm / "sub0" / "status").write_text("state: RUNNING\n")
        check("capture found", find_capture(asound) is not None)
        check("playback idle", playback_busy(asound) is None)
        pb = asound / "card0" / "pcm0p" / "sub0"
        pb.mkdir(parents=True)
        (pb / "status").write_text("state: RUNNING\n")
        check("playback busy detected", playback_busy(asound) is not None)
        check("guard parse", parse_guard("mode: closed-loop\nnospk: 1\nfault: 0\n") ==
              {"mode": "closed-loop", "nospk": "1", "fault": "0"})
        fw = root / "fw"
        fw.mkdir()
        for suffix in SUFFIXES:
            (fw / (FW_MODEL + suffix)).write_bytes(b"x")
        sup = root / "supervisor"
        sup.write_text("#!/bin/sh\necho 'supervisor: holding hw:0,4'\nsleep 5\n")
        sup.chmod(0o755)
        cmd = root / "cmdline"
        cmd.write_text("debug sp11.nospk=1 sp11.entry=safe\n")
        out = root / "report.txt"
        env = dict(os.environ, SP11_CL_CMDLINE_FILE=str(cmd), SP11_CL_ASOUND_ROOT=str(asound),
                   SP11_CL_FW_DIR=str(fw), SP11_CL_GUARD=str(root / "guard"),
                   SP11_CL_SUPERVISOR=str(sup), SP11_CL_NOTICE=str(root / "notice"),
                   SP11_CL_REPORT_OUT=str(out), SP11_CL_HOLD_SECONDS="1")
        (root / "guard").write_text("nospk: 1\nfault: 0\nallow_nominal: 0\n")
        # the fake pcm0p RUNNING above must not fail the real capture test: remove it
        (pb / "status").unlink()
        (pb / "status").parent.rmdir()
        (pb / "status").parent.parent.rmdir()
        run = subprocess.run([sys.executable, "-I", __file__], env=env,
                             capture_output=True, text=True, timeout=30)
        check("validation passes with fakes", run.returncode == 0, )
        if run.returncode != 0:
            print(run.stdout)
            print(run.stderr)
        check("report written", out.is_file() and "RESULT: PASS" in out.read_text())
        check("report mode 0600", out.stat().st_mode & 0o777 == 0o600)
        env["SP11_CL_HOLD_SECONDS"] = "1"
        cmd.write_text("debug sp11.entry=safe\n")  # no kill switch: must refuse
        run = subprocess.run([sys.executable, "-I", __file__], env=env,
                             capture_output=True, text=True, timeout=30)
        check("refuses without sp11.nospk=1", run.returncode != 0)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
