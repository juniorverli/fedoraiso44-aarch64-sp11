#!/usr/bin/env python3
"""Check that missing guard fields and nominal/degraded cases are visible."""
import subprocess
import tempfile
from pathlib import Path

report = Path(__file__).resolve().parents[2] / "closed-loop/guard-report"
base = '''open_allowed: yes
allowed: no
reason: graph is down
mode: closed-loop
caps_ready: 1
nospk: 0
fault: 0 (-, 0x00000000)
loaded: 1
graph_up: 0
sp_enabled: 0
vi_streams: 0
cps_required: 0
cps_streams: 0
cal_mask: 0x0
cal_nominal: 1
allow_nominal: 1
diagnostics_degraded: 1
degraded_fault: 1
cal_graph_matches_vi: 0
vi_ambiguous: 0
'''
with tempfile.TemporaryDirectory(prefix="sp11-report-") as tmp:
    fixture = Path(tmp) / "guard"
    fixture.write_text(base)
    run = subprocess.run([str(report), str(fixture)], capture_output=True, text=True)
    assert run.returncode == 0
    assert "nominal policy: UNMET" in run.stdout
    assert "VI stream callback: UNMET" in run.stdout
    assert "CPS stream callback: NOT REQUIRED BY LOADED GUARD STATE" in run.stdout
    assert "diagnostics registration and event coverage: UNVERIFIED" in run.stdout
    assert "does not authorize unmute" in run.stdout
    fixture.write_text(base.replace("cal_graph_matches_vi: 0\n", ""))
    run = subprocess.run([str(report), str(fixture)], capture_output=True, text=True)
    assert run.returncode == 2 and "calibration matches running VI graph: UNKNOWN" in run.stdout
    fixture.write_text(base + "allowed: yes\n")
    run = subprocess.run([str(report), str(fixture)], capture_output=True, text=True)
    assert run.returncode == 2 and "duplicate guard field" in run.stderr
print("PASS: guard report exposes nominal/degraded, missing and duplicate state without enabling anything")
