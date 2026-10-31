#!/usr/bin/env python3
"""Validate the M13 additions of the installed root: collectors, GPU two-step, speaker UCM overlay switch, libcamera.

Usage: check-m13-payload.py ROOT REPO BUILD_RECORD.json     No device value is read or printed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def check(root, repo, record):
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    pins = json.loads((repo / 'image/component-inputs/m13.json').read_text())
    assert pins == record['m13_inputs'], 'M13 input record differs from the build record'
    ucm_store = root / 'usr/share/sp11/ucm-speakers/Qualcomm/x1e80100'
    ucm_live = root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100'
    for name, want in pins['speaker_ucm_overlay'].items():
        assert digest(ucm_store / name) == want, f'stored speaker UCM {name}'
    for name in ('Surface11-SpeakerSeq.conf', 'Surface11-WsaInit.conf'):
        assert not (ucm_live / name).exists(), f'speaker UCM {name} active in the default path (S1)'
    assert digest(ucm_live / 'Surface11-HiFi.conf') != pins['speaker_ucm_overlay']['Surface11-HiFi.conf'], 'speaker HiFi profile is active by default'
    assert digest(ucm_live / 'MICROSOFT-Surface-Pro-11.conf') != pins['speaker_ucm_overlay']['MICROSOFT-Surface-Pro-11.conf'], 'speaker card profile is active by default'
    unit = root / 'usr/lib/systemd/system/sp11-speaker-ucm.service'
    assert unit.read_bytes() == (repo / 'image/overlay/usr/lib/systemd/system/sp11-speaker-ucm.service').read_bytes(), 'speaker UCM unit'
    assert 'ConditionKernelCommandLine=sp11.entry=spk' in unit.read_text(), 'speaker UCM unit is not entry-gated'
    assert (root / 'etc/systemd/system/sysinit.target.wants/sp11-speaker-ucm.service').readlink() == Path('/usr/lib/systemd/system/sp11-speaker-ucm.service')
    script = root / 'usr/libexec/sp11/speaker-ucm-enable'
    assert script.stat().st_mode & 0o111 and script.read_bytes() == (repo / 'image/overlay/usr/libexec/sp11/speaker-ucm-enable').read_bytes(), 'speaker UCM script'
    assert "grep -qx 'sp11.entry=spk' " in script.read_text(), 'speaker UCM script has no entry gate'
    # GPU two-step: owner bytes plus the one recorded label change; entry-gated unit, never default
    gpu = pins['gpu_two_step']
    owner = (repo / 'hardware/gpu/collector/gpu-two-step.sh')
    assert digest(owner) == gpu['owner_script_sha256'], 'owner GPU script changed after the pin'
    installed = root / 'usr/libexec/sp11-gpu-two-step'
    assert digest(installed) == gpu['installed_script_sha256'] and installed.stat().st_mode & 0o111, 'installed GPU script'
    assert installed.read_text() == owner.read_text().replace('for lbl in SP11LOGS ANACONDA; do', 'for lbl in SP11LOGS ANACONDA BOOT; do'), 'GPU script differs from owner beyond the label'
    subprocess.run(['bash', '-n', str(installed)], check=True)
    gunit = root / 'usr/lib/systemd/system/sp11-gpu-two-step.service'
    assert digest(gunit) == gpu['unit_sha256'] == digest(repo / 'hardware/gpu/collector/sp11-gpu-two-step.service'), 'GPU unit bytes'
    assert 'ConditionKernelCommandLine=sp11.gpu_diag=1' in gunit.read_text(), 'GPU unit is not gated by sp11.gpu_diag=1'
    assert (root / 'etc/systemd/system/multi-user.target.wants/sp11-gpu-two-step.service').readlink() == Path('/usr/lib/systemd/system/sp11-gpu-two-step.service')
    preset = (root / 'usr/lib/systemd/system-preset/80-sp11.preset').read_text()
    for u in ('sp11-gpu-two-step.service', 'sp11-speaker-ucm.service'):
        assert f'enable {u}' in preset, f'preset lacks {u}'
    assert all('sp11.gpu_diag' not in e['linux_args'] for e in record['grub_entries'] if 'gpu' not in e['title'].lower()), 'gpu_diag outside the GPU entry'
    # collectors: image-owned drop-ins byte-identical to the repository, owner collectors unchanged
    dropins = root / 'etc/sp11-log-collector.d'
    for name in ('usb-typec.sh', 'bluetooth.sh', 'ssam-shutdown-mode.sh', 'cameras.sh', 'audio.sh'):
        assert (dropins / name).read_bytes() == (repo / 'image/overlay/etc/sp11-log-collector.d' / name).read_bytes(), name
        subprocess.run(['bash', '-n', str(dropins / name)], check=True)
    usb = (dropins / 'usb-typec.sh').read_text()
    for needle in ('portli', 'dynamic_debug/control', '/proc/cmdline', 'usb-pd-partner.txt', 'number_of_alternate_modes', 'systemctl is-active --quiet upower.service'):
        assert needle in usb, f'usb-typec drop-in lacks {needle}'
    assert 'upower -d' not in usb.replace('then upower -d', ''), 'unguarded upower query'
    cam = (dropins / 'cameras.sh').read_text()
    assert 'i2cdetect' not in ''.join(l for l in cam.splitlines() if not l.lstrip().startswith('#')), 'camera drop-in runs i2cdetect'
    for needle in ('media-ctl', 'cam_cc_mclk1', 'regulator_summary', 'ov13858'):
        assert needle in cam, f'camera drop-in lacks {needle}'
    aud = (dropins / 'audio.sh').read_text()
    for needle in ('arecord -l', 'wpctl status', 'amixer -c 0 contents'):
        assert needle in aud, f'audio drop-in lacks {needle}'
    code = '\n'.join(l for l in aud.splitlines() if not l.lstrip().startswith('#'))
    assert 'aplay -D' not in code and 'arecord -D' not in code and 'amixer -c 0 cset' not in code and ' cset ' not in code and 'sset' not in code, 'audio drop-in plays, records or writes a control'
    ssam = (dropins / 'ssam-shutdown-mode.sh').read_text()
    assert 'parameters/shutdown_mode' in ssam and 'shutdown mode' in ssam, 'SAM shutdown mode record'
    collector = (root / 'usr/libexec/sp11-log-collector').read_text()
    assert 'portsc|portli' in collector and 'dynamic_debug/control' in collector, 'debugfs allow-list lacks portli or dynamic_debug'
    assert 'dp_debug' not in collector.split('debugfs_allowed()')[1].split('dbgcat()')[0], 'dp_debug on the allow-list'
    dsp_owner = (repo / 'hardware/dsp-subsystems/collector/dsp-subsystems.sh').read_bytes()
    assert digest(repo / 'hardware/dsp-subsystems/collector/dsp-subsystems.sh') == pins['dsp_collector_sha256'], 'DSP owner collector changed after the pin'
    dsp = (dropins / 'dsp-subsystems.sh').read_bytes()
    assert dsp.startswith(dsp_owner), 'installed DSP collector does not start with the owner collector'
    for needle in (b'qcom_smp2p', b'power_domain_target', b'handover: proxy power domains', b'pm_genpd_summary'):
        assert needle in dsp, f'DSP collector lacks {needle.decode()}'
    assert digest(dropins / 'ec-sam.sh') == pins['ec_sam_collector_sha256'], 'ec-sam collector differs from the pinned owner file'
    # libcamera from Fedora (cameras R4)
    for pkg in pins['libcamera']['packages']:
        subprocess.run(['rpm', '--root', str(root), '-q', pkg], check=True, capture_output=True)
    assert (root / 'usr/bin/cam').exists(), 'cam missing'


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]), Path(sys.argv[2]), json.load(open(sys.argv[3])))
    except (AssertionError, OSError, KeyError, ValueError, IndexError, subprocess.CalledProcessError) as error:
        sys.exit(f'FAIL M13 payload: {error}')
    print('PASS M13 payload: collectors, GPU two-step, speaker UCM switch, libcamera')
