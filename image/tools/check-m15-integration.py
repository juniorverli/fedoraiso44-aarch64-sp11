#!/usr/bin/env python3
"""Validate the M15 integration of the finished component pieces in the installed root (sensors, audio, cameras, Spectra, volume buttons, CDSP variants).
No device value, blob, tuning, registry or quality data is read into the output; names and PASS/FAIL ids only.

Usage: check-m15-integration.py ROOT REPO BUILD_RECORD.json
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def check(root, repo, record):
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    pins = json.loads((repo / 'image/component-inputs/m15-integration.json').read_text())
    assert pins == record['m15_integration'], 'M15 integration input record differs from the build record'
    kver = record['kernel_nevra'].replace('kernel-core-', '')
    rpm = lambda *a: subprocess.run(['rpm', '--root', str(root), *a], capture_output=True, text=True)
    # ---- packages: sensors, Spectra, libcamera (local or stock, as recorded), audio helpers
    # out/ is shared by all worktrees and mounted at $SP11_OUT in the L0 container; in a worker
    # worktree the repo's out/ is a symlink to the main checkout and does not resolve there.
    out = Path(os.environ.get('SP11_OUT') or (repo / 'out'))
    for nevra in pins['local_rpms']['sensors'] + pins['local_rpms']['spectra']:
        r = rpm('-q', nevra)
        assert r.returncode == 0, f'package {nevra} missing'
    src = record['libcamera_source']
    assert src in ('local', 'stock'), 'libcamera source not recorded'
    for nevra in pins['local_rpms']['libcamera_local'] if src == 'local' else pins['local_rpms']['libcamera_stock']:
        assert rpm('-q', nevra).returncode == 0, f'libcamera package {nevra} missing'
    if src == 'local':
        assert 'sp11' in rpm('-q', '--qf', '%{release}', 'libcamera').stdout, 'libcamera is not the local build'
        lc = out / 'rpms-local/libcamera/libcamera-sp11-build.json'
        lrec = json.loads(lc.read_text())
        assert lrec['patches']['libcamera-sp11.patch'] == digest(repo / 'hardware/cameras/userspace/quality/libcamera-sp11.patch'), 'libcamera patch changed after the build'
        assert lrec['patches']['libcamera-sp11-imx681-helper.patch'] == digest(repo / 'hardware/cameras/userspace/quality/libcamera-sp11-imx681-helper.patch'), 'imx681 helper patch changed after the build'
    for pkg in pins['extra_packages'] + ['pipewire', 'wireplumber']:
        assert rpm('-q', pkg).returncode == 0, f'package {pkg} missing'
    # the local RPMs in the image are the files of out/rpms-local (hash recorded at build)
    for name, h in record['local_rpm_sha256'].items():
        cands = list((out / 'rpms-local').rglob(name)) + list((out / 'rpms').glob(name))
        assert cands and digest(cands[0]) == h, f'local RPM {name}: file differs from the build record'
    # ---- sensors: units, rules, permissions
    unit = (root / 'usr/lib/systemd/system/hexagonrpcd-sensors.service').read_text()
    assert re.search(r'^ExecStart=.*hexagonrpcd .*\s-s\b', unit, re.M) and 'User=hexagonrpcd' in unit and 'Group=fastrpc' in unit, 'hexagonrpcd-sensors.service lacks -s, User or Group'
    for u in pins['units']:
        assert (root / 'usr/lib/systemd/system' / u).is_file(), u
    assert (root / 'etc/systemd/system/multi-user.target.wants/hexagonrpcd-sensors.service').is_symlink(), 'hexagonrpcd-sensors.service not enabled'
    assert (root / 'etc/systemd/system/sleep.target.wants/hexagonrpcd-sensors-sleep.service').is_symlink(), 'hexagonrpcd-sensors-sleep.service not enabled'
    assert 'enable hexagonrpcd-sensors.service' in (root / 'usr/lib/systemd/system-preset/50-sp11-sensors.preset').read_text(), 'sensors preset'
    rule = (root / 'usr/lib/udev/rules.d/61-sp11-fastrpc-adsp.rules').read_text()
    assert 'MODE="0660"' in rule and 'GROUP="fastrpc"' in rule and 'fastrpc-adsp' in rule, 'ADSP node rule is not fastrpc 0660'
    # Only SP11-owned udev files are ours to police: the sensor RPMs ship
    # 61-sp11-fastrpc-adsp.rules and 81-sp11-iio-sensor-proxy-ssc.rules, and every other *sp11*
    # rule belongs to the image. Fedora's packaged 50-udev-default.rules legitimately contains 0666
    # and is not ours, so restrict the scan instead of weakening the 0666 assertion below.
    sp11_udev = []
    for d in ('usr/lib/udev', 'etc/udev'):
        for f in (root / d).rglob('*'):
            if f.is_file() and not f.is_symlink() and f.suffix in ('.rules', '.conf') and 'sp11' in f.name.lower():
                sp11_udev.append(f)
                # effective rule lines only: a comment such as "never 0666" is not a rule
                text = '\n'.join(l for l in f.read_text(errors='replace').splitlines()
                                 if not l.lstrip().startswith('#'))
                assert '0666' not in text, f'0666 in SP11 udev file {f.name}'
    assert sp11_udev, 'no SP11-owned udev rule found to check'
    for n in ('adsprpcd', 'adsprpcd_audiopd', 'cdsprpcd', 'sdsprpcd'):
        for d in ('etc/systemd/system', 'usr/lib/systemd/system'):
            p = root / d / f'{n}.service'
            assert not (p.is_symlink() and os.readlink(p) == '/dev/null'), f'{n}.service is masked'
    assert (root / 'usr/lib/systemd/system/adsprpcd.service').exists(), 'adsprpcd.service missing (fastrpc-services)'
    grp = [l for l in (root / 'etc/group').read_text().splitlines() if l.startswith('fastrpc:')]
    sys_conf = (root / 'usr/lib/sysusers.d/hexagonrpcd.conf').read_text() if (root / 'usr/lib/sysusers.d/hexagonrpcd.conf').is_file() else ''
    assert (grp and 'hexagonrpcd' in grp[0].split(':')[3].split(',')) or re.search(r'^m\s+hexagonrpcd\s+fastrpc', sys_conf, re.M), 'user hexagonrpcd is not a member of fastrpc'
    isp = (root / 'usr/libexec/iio-sensor-proxy').read_bytes()
    assert b'ssc-accel' in isp, 'iio-sensor-proxy has no SSC accelerometer driver'
    assert (root / 'etc/sp11-log-collector.d/sensors.sh').read_bytes() == (repo / 'hardware/sensors/userspace/collector/sensors.sh').read_bytes(), 'sensors collector differs from repository source'
    # ---- audio: route layer, UCM fix, gain, WirePlumber, dconf
    for rel, want in pins['audio_routes_overlay'].items():
        assert digest(root / rel) == want, f'audio route file {rel}'
    gain = (root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100/SP11-MicGain.conf').read_text()
    assert gain.count("VA_DEC0 Volume' 98") == 1 and gain.count("VA_DEC1 Volume' 98") == 1 and not re.search(r"Volume' (10[9]|1[1-9][0-9])\b", gain), 'capture gain step 98 (+14 dB) or cap 108'
    live = root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100'
    d28 = json.loads((repo / 'image/component-inputs/m28.json').read_text())
    assert d28 == record['m28_inputs'], 'D28 input record differs from the build record'
    hifi_file = live / 'Surface11-HiFi.conf'
    assert digest(hifi_file) == d28['installed_files']['usr/share/alsa/ucm2/Qualcomm/x1e80100/Surface11-HiFi.conf'], 'D28 HiFi pin'
    hifi = hifi_file.read_text()
    model = (live / 'MICROSOFT-Surface-Pro-11.conf').read_text()
    assert 'Surface11-HiFi.conf' in model, 'D28 HiFi verb not wired'
    for name, pcm in (('Speaker', 0), ('Mic', 1), ('HDMI0', 2), ('HDMI1', 3)):
        match = re.search(r'SectionDevice\."' + name + r'"\s*\{(.*?)(?=\nSectionDevice\.|\Z)', hifi, re.S)
        assert match, f'D28 {name} device missing'
        direction = 'Capture' if name == 'Mic' else 'Playback'
        assert f'{direction}PCM "hw:${{CardId}},{pcm}"' in match.group(1), f'D28 {name} PCM'
    for n in (0, 1):
        assert f'JackControl "DP{n} Jack"' in hifi, f'DP{n} jack'
        assert f'DISPLAY_PORT_RX_{n} Audio Mixer MultiMedia{n + 3}' in hifi, f'DP{n} mixer route'
    assert b'priority' in (root / 'usr/share/wireplumber/wireplumber.conf.d/52-sp11-audio-routes.conf').read_bytes(), 'WirePlumber priorities'
    assert (root / 'etc/dconf/db/distro.d/91-sp11-audio-routes').is_file() and (root / 'etc/dconf/db/distro').stat().st_size > 0, 'dconf route defaults'
    assert rpm('-q', 'alsa-ucm-utils').returncode == 0 and (root / 'usr/bin/alsaucm').exists(), 'alsaucm missing'
    # ---- cameras and Spectra collectors, volume tool, Spectra loader
    for rel, want in {**pins['collectors'], **pins['image_files']}.items():
        f = root / rel
        assert f.is_file() and digest(f) == want, f'{rel} differs from its pin'
    assert (root / 'etc/sp11-log-collector.d/cameras.sh').read_bytes() == (repo / 'hardware/cameras/collector/cameras.sh').read_bytes(), 'camera collector differs from repository source'
    for rel in ('usr/libexec/sp11/ec-sam/collect-volume-buttons.sh', 'usr/libexec/sp11/spectra-load'):
        assert (root / rel).stat().st_mode & 0o111, f'{rel} not executable'
        subprocess.run(['bash', '-n', str(root / rel)], check=True)
    for rel in ('etc/sp11-log-collector.d/cameras.sh', 'etc/sp11-log-collector.d/spectra.sh'):
        subprocess.run(['bash', '-n', str(root / rel)], check=True)
    code = '\n'.join(l for l in (root / 'etc/sp11-log-collector.d/cameras.sh').read_text().splitlines() if not l.lstrip().startswith('#'))
    assert 'i2cdetect' not in code, 'camera collector runs i2cdetect'
    for u in ('sp11-log-collector.service',):
        assert 'collect-volume-buttons' not in (root / 'usr/libexec/sp11-log-collector').read_text() and 'spectra-load' not in (root / 'usr/lib/systemd/system' / u).read_text(), 'the volume tool or the loader is run automatically'
    sp = (root / 'usr/lib/systemd/system/sp11-spectra-load.service').read_text()
    assert 'ConditionKernelCommandLine=sp11.entry=spectra' in sp and 'ConditionPathExistsGlob=/proc/device-tree/soc@0/qcom,cam-cpas*' in sp, 'Spectra loader is not entry/DT gated'
    st = (root / 'usr/libexec/sp11/spectra-load').read_text()
    assert 'marker spectra-load' in st and 'module_blacklist' in st and st.count('modprobe') >= 1 and 'camera_x1e80100' in st, 'Spectra loader logic'
    assert (root / 'etc/systemd/system/multi-user.target.wants/sp11-spectra-load.service').is_symlink(), 'Spectra loader not enabled'
    assert 'enable sp11-spectra-load.service' in (root / 'usr/lib/systemd/system-preset/80-sp11.preset').read_text(), 'Spectra loader not in the preset'
    # ---- Spectra module RPM: built for this kernel, guard, no firmware in the RPM
    ko = root / 'lib/modules' / kver / 'extra/camera_x1e80100.ko.xz'
    assert ko.is_file(), 'camera_x1e80100.ko.xz not installed for the image kernel'
    vm = subprocess.run(['modinfo', '-b', str(root), '-k', kver, '-F', 'vermagic', 'camera_x1e80100'], capture_output=True, text=True)
    assert vm.returncode == 0 and vm.stdout.split()[0] == kver, 'camera_x1e80100 vermagic differs from the image kernel'
    assert (root / 'usr/lib/modprobe.d/sp11-camera-spectra.conf').is_file() and (root / 'usr/libexec/sp11-camera-spectra-guard').stat().st_mode & 0o111, 'Spectra guard files'
    # ---- CDSP experiment: variants for the tri-state keep_proxy_pds
    cd = (root / 'usr/libexec/sp11/cdsp-experiment').read_text()
    for needle in ('keep_proxy_pds forced 0', 'keep_proxy_pds default', 'want_keep=-1', 'c1-00046.1', 'c1-00078'):
        assert needle in cd, f'CDSP experiment lacks {needle}'
    assert [l for l in re.findall(r'^desc\(\) \{.*$', cd, re.M)], 'desc() missing'
    for d in pins['cdsp_variants']:
        assert d.replace('keep_proxy_pds=', 'keep_proxy_pds=') in cd, f'variant text {d}'


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]), Path(sys.argv[2]), json.load(open(sys.argv[3])))
    except (AssertionError, OSError, KeyError, ValueError, IndexError, subprocess.CalledProcessError) as error:
        sys.exit(f'FAIL M15 integration: {error}')
    print('PASS M15 integration: sensors packages/units/rules, audio route layer, cameras and Spectra payloads, libcamera, volume tool, CDSP variants')
