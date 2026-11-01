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
    for nevra in pins['local_rpms']['sensors'] + pins['local_rpms']['spectra']:
        r = rpm('-q', nevra)
        assert r.returncode == 0, f'package {nevra} missing'
    src = record['libcamera_source']
    assert src in ('local', 'stock'), 'libcamera source not recorded'
    for nevra in pins['local_rpms']['libcamera_local'] if src == 'local' else pins['local_rpms']['libcamera_stock']:
        assert rpm('-q', nevra).returncode == 0, f'libcamera package {nevra} missing'
    if src == 'local':
        assert 'sp11' in rpm('-q', '--qf', '%{release}', 'libcamera').stdout, 'libcamera is not the local build'
        lc = repo / 'out/rpms-local/libcamera/libcamera-sp11-build.json'
        lrec = json.loads(lc.read_text())
        assert lrec['patches']['libcamera-sp11.patch'] == digest(repo / 'hardware/cameras/userspace/quality/libcamera-sp11.patch'), 'libcamera patch changed after the build'
        assert lrec['patches']['libcamera-sp11-imx681-helper.patch'] == digest(repo / 'hardware/cameras/userspace/quality/libcamera-sp11-imx681-helper.patch'), 'imx681 helper patch changed after the build'
    for pkg in pins['extra_packages'] + ['pipewire', 'wireplumber']:
        assert rpm('-q', pkg).returncode == 0, f'package {pkg} missing'
    # the local RPMs in the image are the files of out/rpms-local (hash recorded at build)
    for name, h in record['local_rpm_sha256'].items():
        cands = list((repo / 'out/rpms-local').rglob(name)) + list((repo / 'out/rpms').glob(name))
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
    for d in ('usr/lib/udev', 'etc/udev'):
        for f in (root / d).rglob('*'):
            if f.is_file() and not f.is_symlink() and f.suffix in ('.rules', '.conf'):
                assert '0666' not in f.read_text(errors='replace'), f'0666 in udev file {f.name}'
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
    assert (root / 'etc/sp11-log-collector.d/sensors.sh').is_file(), 'sensors collector drop-in missing'
    # ---- audio: route layer, UCM fix, gain, WirePlumber, dconf
    for rel, want in pins['audio_routes_overlay'].items():
        assert digest(root / rel) == want, f'audio route file {rel}'
    gain = (root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100/SP11-MicGain.conf').read_text()
    assert gain.count("VA_DEC0 Volume' 98") == 1 and gain.count("VA_DEC1 Volume' 98") == 1 and not re.search(r"Volume' (10[9]|1[1-9][0-9])\b", gain), 'capture gain step 98 (+14 dB) or cap 108'
    live = root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100'
    routes = '\n'.join(l for f in ('SP11-Routes.conf', 'SP11-Audio.conf', 'SP11-HiFi.conf', 'SP11-DP0.conf', 'SP11-DP1.conf') for l in (live / f).read_text().splitlines() if not l.lstrip().startswith('#'))
    assert 'HDMI0' in routes and 'HDMI1' in routes, 'DisplayPort HDMI0/HDMI1 devices'
    assert not re.search(r'WSA|SpeakerSeq|WsaInit', routes.replace('Surface11-HiFi', '')), 'route layer names a speaker sequence directly'
    assert 'SP11-Audio' in (live / 'x1e80100.conf').read_text() or 'SP11-Audio' in routes, 'SP11-Audio not wired'
    assert b'priority' in (root / 'usr/share/wireplumber/wireplumber.conf.d/52-sp11-audio-routes.conf').read_bytes(), 'WirePlumber priorities'
    assert (root / 'etc/dconf/db/distro.d/91-sp11-audio-routes').is_file() and (root / 'etc/dconf/db/distro').stat().st_size > 0, 'dconf route defaults'
    assert rpm('-q', 'alsa-ucm-utils').returncode == 0 and (root / 'usr/bin/alsaucm').exists(), 'alsaucm missing'
    # ---- cameras and Spectra collectors, volume tool, Spectra loader
    for rel, want in {**pins['collectors'], **pins['image_files']}.items():
        f = root / rel
        assert f.is_file() and digest(f) == want, f'{rel} differs from its pin'
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
