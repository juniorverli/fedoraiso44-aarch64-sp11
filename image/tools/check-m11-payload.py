#!/usr/bin/env python3
"""Validate D28 public audio payload, selection policy and software safety."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_mic_capture_caps(graph_text):
    match = re.search(r'SectionPCMCapabilities\s*\{(.*?)\n\}', graph_text, re.S)
    assert match, 'topology has no PCM capabilities section'
    capture = re.search(
        r"'MultiMedia2 Capture'\s*\{([^}]*)\}", match.group(1), re.S)
    assert capture, 'topology has no MultiMedia2 Capture capabilities'
    section = capture.group(1)
    assert re.search(r"formats\s+'S16_LE'", section) and \
           re.search(r'rate_min\s+48000', section) and \
           re.search(r'rate_max\s+48000', section) and \
           re.search(r'channels_min\s+1', section) and \
           re.search(r'channels_max\s+2', section), \
        'D28 topology Mic capture must be S16_LE/48kHz/min 1/max 2 channels'


def check_global_safety(confdir):
    defaults = []
    for path in sorted(confdir.glob('*.conf')):
        text = re.sub(r'(?m)#.*$', '', path.read_text())
        assert not re.search(r'\bapi\.acp\.max-volume\s*=', text), 'unsupported max-volume property'
        for block in re.findall(r'wireplumber\.settings\s*=\s*\{([^{}]*)\}', text, re.S):
            defaults.extend((path.name, float(value)) for value in re.findall(
                r'device\.routes\.default-sink-volume\s*=\s*([0-9.]+)', block))
    assert ('51-sp11-audio-safety.conf', 0.05) in defaults, 'expected earlier fallback missing'
    assert defaults[-1:] == [('55-sp11-global-safety.conf', 0.0)], 'global sink default must end at 0.0; 0.05 must not win'

def check(root, repo, record, release):
    pin = json.loads((repo / 'image/component-inputs/m28.json').read_text())
    assert pin == record['m28_inputs'], 'D28 input record differs'
    assert pin['software_policy']['volume_ceiling_percent'] == 100, 'desktop maximum must be 100 percent'
    runtime = record.get('d28_runtime_validation')
    assert runtime and runtime.get('source_commit') == pin['topology']['source_commit']
    assert runtime.get('topology_sha256') == pin['topology']['sha256']
    runtime_keys = ('device_dmi_match', 'alsaucm_profile_resolved', 'initial_mute_confirmed', 'pipewire_ceiling_enforced', 'speaker_off_fallback_mic_dp', 'kernel_d28_guard', 'closed_loop_fail_closed')
    if record.get('private'):
        assert runtime.get('status') == 'unvalidated', 'private D28 runtime state must be explicit'
        assert set(runtime) == {'status', 'source_commit', 'topology_sha256'}, 'private build record must not imply runtime validation'
        assert record.get('distribution', '').find('never share') >= 0
    else:
        assert all(runtime.get(key) is True for key in runtime_keys), 'public build requires full D28 runtime validation'
    for rel, want in pin['installed_files'].items():
        assert digest(root / rel) == want, rel
    ucm = root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100'
    canonical = repo / 'image/component-inputs/d28/audio'
    other_copy = repo / 'hardware/audio-speakers/userspace/overlay-d28/usr/share/alsa/ucm2/Qualcomm/x1e80100'
    if other_copy.exists():
        for path in other_copy.glob('*.conf'):
            assert (canonical / path.name).read_bytes() == path.read_bytes(), f'stale audio owner UCM copy: {path.name}'
    model = (ucm / 'MICROSOFT-Surface-Pro-11.conf').read_text()
    hifi = (ucm / 'Surface11-HiFi.conf').read_text()
    assert 'SectionDevice."Speaker"' in hifi and 'SectionDevice."Mic"' in hifi, 'Speaker/Mic routes'
    assert all(f'PlaybackPCM "hw:${{CardId}},{n}"' in hifi for n in (0, 2, 3)), 'Speaker/DP PCMs'
    assert 'CapturePCM "hw:${CardId},1"' in hifi, 'Mic PCM'
    assert 'CaptureChannels 2' in hifi, 'Mic must expose the fixed two-channel DMIC array without downmix'
    assert 'Surface11-WsaInit.conf' in model and 'Surface11-SpeakerSeq.conf' in hifi
    assert '/lib/card-init.conf' in model and '/lib/ctl-remap.conf' in model
    assert '/codecs/wsa884x/two-speakers/init.conf' in model
    for include in (
        '/codecs/wsa884x/two-speakers/DefaultEnableSeq.conf',
        '/codecs/qcom-lpass/wsa-macro/Wsa1SpeakerEnableSeq.conf',
        '/codecs/qcom-lpass/wsa-macro/Wsa1SpeakerDisableSeq.conf',
        '/codecs/qcom-lpass/va-macro/DMIC0EnableSeq.conf',
        '/codecs/qcom-lpass/va-macro/DMIC0DisableSeq.conf',
        '/codecs/qcom-lpass/va-macro/DMIC1EnableSeq.conf',
        '/codecs/qcom-lpass/va-macro/DMIC1DisableSeq.conf',
    ):
        assert include in hifi, f'package UCM include missing: {include}'
    wsa_init = (ucm / 'Surface11-WsaInit.conf').read_text()
    speaker_seq = (ucm / 'Surface11-SpeakerSeq.conf').read_text()
    for control in ('WSA_RX0', 'WSA_RX1', 'WSA_RX0_MIX', 'WSA_RX1_MIX'):
        assert f"WSA {control} Digital Volume' 72\"" in wsa_init, control
    default_enable = (root / 'usr/share/alsa/ucm2/codecs/wsa884x/two-speakers/DefaultEnableSeq.conf').read_text()
    for sequence in (wsa_init, default_enable):
        commands = "\n".join(line for line in sequence.splitlines() if not line.lstrip().startswith("#"))
        assert not re.search(r"\bcset\b[^\n]*PA Volume", commands), 'unexpected PA gain in init/default'
    enable, disable = speaker_seq.split('DisableSequence', 1)
    for control in ('SpkrLeft PA Volume', 'SpkrRight PA Volume'):
        assert enable.count(f"cset \"name='{control}' 6\"") == 1, control
    for control in ('SpkrLeft PA Volume', 'SpkrRight PA Volume'):
        assert f"cset \"name='{control}' 0\"" in disable, control
    writes = re.findall(r"cset\s+\"name='(?:SpkrLeft PA Volume|SpkrRight PA Volume|Speakers Volume)'\s+(\d+)\"", speaker_seq)
    assert len(writes) == 4 and all(int(v) <= 6 for v in writes), 'PA gain exceeds kernel cap'
    assert 'Speakers Volume' not in enable, 'userspace remap alias must not be a UCM cset'
    driver = (ucm / 'x1e80100.conf').read_text()
    assert 'Microsoft Corporation.*Surface.*Microsoft Surface Pro( with 5G)?, 11th Edition' in driver
    assert 'SP11-Audio.conf' not in driver, 'driver still includes the later replacement verb'
    assert not (ucm / 'SP11-Audio.conf').exists(), 'stale replacement verb is present'
    link = root / 'usr/share/alsa/ucm2/conf.d/x1e80100/x1e80100.conf'
    assert link.is_symlink() and link.resolve() == (ucm / 'x1e80100.conf').resolve(), 'driver-level UCM link'
    topology = root / 'usr/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin'
    assert digest(topology) == pin['topology']['sha256'] and topology.stat().st_size == pin['topology']['size']
    assert pin['topology']['source_commit'] == '993a17dcb672357998a463a73f120064d6c74f4f'
    with tempfile.TemporaryDirectory(prefix='sp11-d28-topology-') as tmp:
        graph = Path(tmp) / 'topology.conf'
        subprocess.run(['alsatplg', f'--decode={topology}', f'--output={graph}'], check=True, capture_output=True)
        graph_text = graph.read_text()
    check_mic_capture_caps(graph_text)
    assert not re.search(r'SP_VI|VI Feedback|\bCPS\b|070010e[234]|0800138c', graph_text, re.I), 'public graph contains SP/VI/CPS or diagnostics strings'
    safety = root / 'usr/libexec/sp11-audio-safety'
    safety_text = safety.read_text()
    mute = 'wpctl set-mute "$id" 1'
    volume = 'wpctl set-volume "$id" 100%'
    assert safety.stat().st_mode & 0o111 and mute in safety_text and volume in safety_text and '--limit' not in safety_text
    assert safety_text.index(mute) < safety_text.index(volume), 'mute must precede volume'
    assert all(token in safety_text for token in ('pw-dump', 'wpctl inspect @DEFAULT_AUDIO_SINK@',
               'wpctl get-volume "$id"', 'sp11.audio_first_test=1', 'wpctl set-volume "$id" 5%',
               'seq 1 300', 'exit 1')), 'sink discovery, mute readback or first-test policy missing'
    subprocess.run([sys.executable, '-I', str(repo / 'image/tools/audio-safety-selftest.py'), str(safety)],
                   check=True, capture_output=True)
    confdir = root / 'usr/share/wireplumber/wireplumber.conf.d'
    ceiling_text = (confdir / '53-sp11-audio-ceiling.conf').read_text()
    assert 'api.acp.disable-pro-audio = true' in ceiling_text
    assert 'device.routes.default-sink-volume = 0.0' in ceiling_text, 'fresh sink default must be 0.0'
    check_global_safety(confdir)
    unit = root / 'usr/lib/systemd/user/sp11-audio-safety.service'
    assert 'Before=graphical-session.target' in unit.read_text() and 'Type=oneshot' in unit.read_text()
    user_wants = root / 'etc/systemd/user/graphical-session-pre.target.wants/sp11-audio-safety.service'
    assert user_wants.is_symlink() and user_wants.readlink() == Path('/usr/lib/systemd/user/sp11-audio-safety.service')
    assert 'system-db:distro' in (root / 'etc/dconf/profile/user').read_text()
    assert (root / 'etc/dconf/db/distro').stat().st_size > 0
    value = subprocess.run(['chroot', str(root), 'dconf', 'read', '/org/gnome/desktop/sound/allow-volume-above-100-percent'], capture_output=True, text=True, check=True)
    assert value.stdout.strip() == 'false'
    writable = subprocess.run(['chroot', str(root), 'gsettings', 'writable', 'org.gnome.desktop.sound', 'allow-volume-above-100-percent'], capture_output=True, text=True, check=True)
    assert writable.stdout.strip() == 'false'
    assert digest(root / 'etc/sp11-log-collector.d/ec-sam.sh') == json.loads((repo / 'image/component-inputs/m11.json').read_text())['ec_sam_collector']['sha256'], 'SAM collector'
    for name, target in [('shutdown', 'sysinit'), ('rebind', 'multi-user')]:
        unit_name = f'sp11-ssam-{name}.service'
        path = root / 'usr/lib/systemd/system' / unit_name
        assert path.read_bytes() == (repo / 'image/overlay/usr/lib/systemd/system' / unit_name).read_bytes(), unit_name
        assert (root / f'etc/systemd/system/{target}.target.wants' / unit_name).readlink() == Path('/usr/lib/systemd/system') / unit_name, unit_name
        assert f'enable {unit_name}' in (root / 'usr/lib/systemd/system-preset/80-sp11.preset').read_text(), unit_name
        script = root / f'usr/libexec/sp11/ec-sam/ssam-{"unbind" if name == "shutdown" else name}.sh'
        assert script.stat().st_mode & 0o111 and script.read_bytes() == (repo / 'image/overlay' / script.relative_to(root)).read_bytes(), script.name
    rebind = (root / 'usr/lib/systemd/system/sp11-ssam-rebind.service').read_text()
    assert 'ConditionKernelCommandLine=sp11.ssam_rebind' in rebind, 'rebind not opt-in'
    shutdown = (root / 'usr/lib/systemd/system/sp11-ssam-shutdown.service').read_text()
    assert 'ConditionKernelCommandLine=sp11.ssam_shutdown' in shutdown, 'shutdown not opt-in'
    assert 'Before=sp11-log-collector.service' in shutdown and 'After=sp11-log-collector.service' not in shutdown, 'shutdown ordering'
    assert all('sp11.ssam_shutdown' not in entry['linux_args'] for entry in record['grub_entries']), 'automatic shutdown unbind in menu'
    assert all('sp11.ssam_rebind' not in entry['linux_args'] for entry in record['grub_entries']), 'automatic rebind in menu'
    dsp = (root / 'etc/sp11-log-collector.d/dsp-subsystems.sh').read_text()
    assert 'for f in trace0 resource_table' in dsp and 'timeout 5 head -c 262144' in dsp, 'remoteproc bounded reads absent'
    modules = next(v['new_modules'] for k in ('m16', 'm15', 'm14', 'm13')
                   for v in [release.get(k)] if v and 'new_modules' in v)
    assert modules['snd-soc-x1e80100']['mix_volume_controls'] == 4, 'MIX caps evidence'
    assert modules['snd-soc-wsa884x']['pa_mixer_value'] == 6, 'PA reset evidence'
    for name, module in modules.items():
        assert digest(root / module['path'].lstrip('/')) == module['module_sha256'], name
    assert not (root / 'usr/lib/systemd/system/sp11-speaker-ucm.service').exists(), 'obsolete UCM selector service'


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]), Path(sys.argv[2]), json.load(open(sys.argv[3])), json.load(open(sys.argv[4])))
    except (AssertionError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'FAIL D28 public audio payload: {error}')
    print('PASS D28 public audio: topology pin, DMI-selected Speaker/Mic/DP routes, kernel caps, UCM level, initial mute')
