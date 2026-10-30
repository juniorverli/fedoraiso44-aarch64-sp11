#!/usr/bin/env python3
"""Validate installed M11 payloads, speaker exclusion and activation policy. No values printed."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def check(root, repo, record, release):
    pins = json.loads((repo / 'image/component-inputs/m11.json').read_text())
    assert pins == record['m11_inputs'], 'M11 input record differs'
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    for rel, want in pins['audio_overlay'].items():
        assert digest(root / rel) == want, rel
    ucm = root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100'
    profiles = [p for p in ucm.glob('*.conf') if 'Surface11' in p.name or 'Surface-Pro-11' in p.name]
    assert {p.name for p in profiles} == {'Surface11-HiFi.conf', 'MICROSOFT-Surface-Pro-11.conf'}, 'unexpected Surface UCM'
    for p in profiles:
        active = '\n'.join(l for l in p.read_text().splitlines() if not l.lstrip().startswith('#'))
        assert not re.search(r'WSA|Speaker|PlaybackPCM|WsaInit|SpeakerSeq', active), p.name
    assert 'SectionDevice."Mic"' in (ucm / 'Surface11-HiFi.conf').read_text(), 'capture device absent'
    topology = root / 'usr/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin'
    assert digest(topology) == pins['topology']['sha256'] and topology.stat().st_size == pins['topology']['size'], 'topology'
    assert 'system-db:distro' in (root / 'etc/dconf/profile/user').read_text(), 'distro policy not active'
    assert (root / 'etc/dconf/db/distro').stat().st_size > 0, 'compiled dconf database missing'
    value = subprocess.run(['chroot', str(root), 'dconf', 'read', '/org/gnome/desktop/sound/allow-volume-above-100-percent'], capture_output=True, text=True, check=True)
    assert value.stdout.strip() == 'false', 'compiled GNOME volume value'
    writable = subprocess.run(['chroot', str(root), 'gsettings', 'writable', 'org.gnome.desktop.sound', 'allow-volume-above-100-percent'], capture_output=True, text=True, check=True)
    assert writable.stdout.strip() == 'false', 'GNOME volume lock inactive'
    assert digest(root / 'etc/sp11-log-collector.d/ec-sam.sh') == pins['ec_sam_collector']['sha256'], 'SAM collector'
    for name, target in [('shutdown', 'sysinit'), ('rebind', 'multi-user')]:
        unit = f'sp11-ssam-{name}.service'
        path = root / 'usr/lib/systemd/system' / unit
        assert path.read_bytes() == (repo / 'image/overlay/usr/lib/systemd/system' / unit).read_bytes(), unit
        assert (root / f'etc/systemd/system/{target}.target.wants' / unit).readlink() == Path('/usr/lib/systemd/system') / unit, unit
        assert f'enable {unit}' in (root / 'usr/lib/systemd/system-preset/80-sp11.preset').read_text(), unit
        script = root / f'usr/libexec/sp11/ec-sam/ssam-{ "unbind" if name == "shutdown" else name}.sh'
        assert script.stat().st_mode & 0o111 and script.read_bytes() == (repo / 'image/overlay' / script.relative_to(root)).read_bytes(), script.name
    rebind = (root / 'usr/lib/systemd/system/sp11-ssam-rebind.service').read_text()
    assert 'ConditionKernelCommandLine=sp11.ssam_rebind' in rebind, 'rebind not opt-in'
    shutdown = (root / 'usr/lib/systemd/system/sp11-ssam-shutdown.service').read_text()
    assert 'ConditionKernelCommandLine=sp11.ssam_shutdown' in shutdown, 'shutdown unit not opt-in'
    assert 'Before=sp11-log-collector.service' in shutdown and 'After=sp11-log-collector.service' not in shutdown, 'shutdown ordering'
    assert all('sp11.ssam_shutdown' not in e['linux_args'] for e in record['grub_entries']), 'automatic shutdown unbind in menu'
    assert all('sp11.ssam_rebind' not in e['linux_args'] for e in record['grub_entries']), 'automatic rebind in menu'
    dsp = (root / 'etc/sp11-log-collector.d/dsp-subsystems.sh').read_text()
    assert 'for f in trace0 resource_table' in dsp and 'timeout 5 head -c 262144' in dsp, 'remoteproc bounded reads absent'
    # Kernel worker checked the compiled ceilings/reset values. Require those same
    # module bytes in this root, tied to the release record hash checked by L0 4.12.
    modules = release['m11']['new_modules']
    assert modules['snd-soc-x1e80100']['mix_volume_controls'] == 4, 'MIX caps evidence'
    assert modules['snd-soc-wsa884x']['pa_mixer_value'] == 6, 'PA reset evidence'
    for name, module in modules.items():
        assert digest(root / module['path'].lstrip('/')) == module['module_sha256'], name


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]), Path(sys.argv[2]), json.load(open(sys.argv[3])), json.load(open(sys.argv[4])))
    except (AssertionError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'FAIL M11 payload: {error}')
    print('PASS M11 payload: microphone UCM, volume policy, topology, SAM and DSP integration')
