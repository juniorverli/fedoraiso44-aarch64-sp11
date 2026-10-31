#!/usr/bin/env python3
"""Validate the M15 additions of the installed root: collectors, GPU two-step with the image hooks, rotors, speaker first-test tooling,
microphone UCM fix, power-thermal, FastRPC packages. No device value is read or printed.

Usage: check-m15-payload.py ROOT REPO BUILD_RECORD.json
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def check(root, repo, record):
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    pins = json.loads((repo / 'image/component-inputs/m15.json').read_text())
    assert pins == record['m15_inputs'], 'M15 input record differs from the build record'
    ucm_store = root / 'usr/share/sp11/ucm-speakers/Qualcomm/x1e80100'
    ucm_live = root / 'usr/share/alsa/ucm2/Qualcomm/x1e80100'
    for name, want in pins['speaker_ucm_overlay'].items():
        assert digest(ucm_store / name) == want, f'stored speaker UCM {name}'
    for name in ('Surface11-SpeakerSeq.conf', 'Surface11-WsaInit.conf'):
        assert not (ucm_live / name).exists(), f'speaker UCM {name} active in the default path (S1)'
    assert digest(ucm_live / 'Surface11-HiFi.conf') != pins['speaker_ucm_overlay']['Surface11-HiFi.conf'], 'speaker HiFi profile is active by default'
    assert digest(ucm_live / 'MICROSOFT-Surface-Pro-11.conf') != pins['speaker_ucm_overlay']['MICROSOFT-Surface-Pro-11.conf'], 'speaker card profile is active by default'
    # microphone UCM fix: the driver file with the Surface Pro 11 branch, nothing else added
    for rel, want in pins['ucm_fix'].items():
        assert digest(root / rel) == want, f'UCM fix {rel}'
    fix = (ucm_live / 'x1e80100.conf').read_text()
    assert 'If.SURFACEPro11' in fix and fix.count('MICROSOFT-Surface-Pro-11.conf') == 1, 'UCM fix lacks the Surface Pro 11 branch'
    assert not re.search(r'Surface11-(SpeakerSeq|WsaInit)', fix), 'UCM driver file names a speaker sequence'
    unit = root / 'usr/lib/systemd/system/sp11-speaker-ucm.service'
    assert unit.read_bytes() == (repo / 'image/overlay/usr/lib/systemd/system/sp11-speaker-ucm.service').read_bytes(), 'speaker UCM unit'
    assert 'ConditionKernelCommandLine=sp11.entry=spk' in unit.read_text(), 'speaker UCM unit is not entry-gated'
    assert (root / 'etc/systemd/system/sysinit.target.wants/sp11-speaker-ucm.service').readlink() == Path('/usr/lib/systemd/system/sp11-speaker-ucm.service')
    script = root / 'usr/libexec/sp11/speaker-ucm-enable'
    assert script.stat().st_mode & 0o111 and script.read_bytes() == (repo / 'image/overlay/usr/libexec/sp11/speaker-ucm-enable').read_bytes(), 'speaker UCM script'
    assert "grep -qx 'sp11.entry=spk' " in script.read_text(), 'speaker UCM script has no entry gate'
    # speaker first-test tooling: present everywhere, manual, gated by the entry and its arguments, with the policy limits
    for name in ('speaker-supervisor', 'speaker-first-test'):
        f = root / 'usr/libexec/sp11' / name
        assert f.stat().st_mode & 0o111 and f.read_bytes() == (repo / 'image/overlay/usr/libexec/sp11' / name).read_bytes(), name
    ft = (root / 'usr/libexec/sp11/speaker-first-test').read_text()
    for needle in ('sp11.entry=spk', 'sp11.allow_nominal=1', 'sp11.nospk', 'at most 10', 'sleep 180', 'speaker-supervisor hw:0,4', 'latched'):
        assert needle in ft, f'first-test script lacks {needle}'
    subprocess.run(['bash', '-n', str(root / 'usr/libexec/sp11/speaker-first-test')], check=True)
    sup = (root / 'usr/libexec/sp11/speaker-supervisor').read_text()
    assert 'snd_pcm_start' in sup and '.read' not in sup.replace('readi', 'X') and 'snd_pcm_readi' not in sup, 'supervisor reads the capture or never starts it'
    for u in ('sp11-speaker-first-test.service',):
        assert not (root / 'usr/lib/systemd/system' / u).exists(), 'the first test must never be a unit'
    # GPU two-step: owner unit byte for byte, installed script = owner + the three image changes, nothing else
    gpu = pins['gpu_two_step']
    owner = repo / 'hardware/gpu/collector/gpu-two-step.sh'
    assert digest(owner) == gpu['owner_script_sha256'], 'owner GPU script changed after the pin'
    hooks = repo / 'image/component-inputs/gpu-state-hooks.sh'
    assert digest(hooks) == gpu['hooks_sha256'], 'GPU hook file changed after the pin'
    installed = root / 'usr/libexec/sp11-gpu-two-step'
    assert digest(installed) == gpu['installed_script_sha256'] and installed.stat().st_mode & 0o111, 'installed GPU script'
    text = installed.read_text()
    assert hooks.read_text() + '\n' in text, 'hook functions are not in the installed GPU script'
    back = text.replace(hooks.read_text() + '\n', '')
    for line in ('sp11_gpu_hook_report\n', '[ "$limit" -ge 1 ] && sp11_gpu_hook_arm\n', '[ "$limit" -ge 2 ] && sp11_gpu_hook_ok\n'):
        assert back.count(line) == 1, f'call line missing or duplicated: {line.strip()}'
        back = back.replace(line, '')
    back, n = re.subn(r'^if sp11_gpu_hook_skip; then sp11_gpu_note [^\n]*; mark SKIP_GPU_TEST; mark DONE; flush; exit 0; fi\n', '', back, flags=re.M)
    assert n == 1, 'skip line missing'
    assert back.replace('for lbl in SP11LOGS ANACONDA BOOT; do', 'for lbl in SP11LOGS ANACONDA; do') == owner.read_text(), 'GPU script differs from the owner beyond the recorded image changes'
    subprocess.run(['bash', '-n', str(installed)], check=True)
    # state order in the script: armed before step 1, ok only after both ends, skip before the follower
    assert text.index('sp11_gpu_hook_arm\n') < text.index('step1 || true'), 'arm is not before step 1'
    assert 'sync -f' in hooks.read_text() or '$SP11_ESPENV" set sp11_gpu_state=testing' in hooks.read_text()
    gunit = root / 'usr/lib/systemd/system/sp11-gpu-two-step.service'
    assert digest(gunit) == gpu['unit_sha256'] == digest(repo / 'hardware/gpu/collector/sp11-gpu-two-step.service'), 'GPU unit bytes'
    assert 'ConditionKernelCommandLine=sp11.gpu_diag=1' in gunit.read_text(), 'GPU unit is not gated by sp11.gpu_diag=1'
    drop = root / 'usr/lib/systemd/system/sp11-gpu-two-step.service.d/10-sp11-image.conf'
    assert drop.read_bytes() == (repo / 'image/overlay/usr/lib/systemd/system/sp11-gpu-two-step.service.d/10-sp11-image.conf').read_bytes() and 'Before=gdm.service' in drop.read_text(), 'GPU drop-in'
    assert not (root / 'etc/systemd/system/multi-user.target.wants/sp11-gpu-two-step.service').exists(), 'GPU two-step is enabled (M15: installed disabled)'
    preset = (root / 'usr/lib/systemd/system-preset/80-sp11.preset').read_text()
    assert 'disable sp11-gpu-two-step.service' in preset and 'enable sp11-gpu-two-step.service' not in preset, 'preset does not disable the GPU two-step'
    for u in ('sp11-speaker-ucm.service', 'sp11-sam-mode-rotor.service', 'sp11-cdsp-experiment.service', 'sp11-cpufreq-cap.service',
              'sp11-identity-switch.service', 'sp11-wifi-identity.service', 'sp11-identity-bt-pre.service',
              'sp11-suspend-policy.service', 'sp11-wakeup-policy.service', 'sp11-suspend-diag.service', 'sp11-thermal-sample.service'):
        assert f'enable {u}' in preset, f'preset lacks {u}'
    assert not any('sp11.gpu_diag' in (e['linux_args'] or '') or 'sp11.gpu_dtb' in (e['linux_args'] or '') for e in record['grub_entries']), 'GPU argument in the M15 menu'
    assert not any('denali-m1' in str(e) for e in record['grub_entries']) and len(record['grub_entries']) == 11, 'M15 menu is 11 flat entries'
    assert not any(re.search(r'cdsp_variant|firmware_class|keep_proxy_pds|surface_aggregator|sp11\.identity|cpufreq', e['linux_args'] or '') for e in record['grub_entries']), 'experiment argument on a static line'
    assert all('sp11.allow_nominal' not in e['linux_args'] for e in record['grub_entries'] if 'speakers' not in e['title']), 'allow_nominal outside the speaker entry'
    # rotors, notices, helper
    for name in ('sam-mode-rotor', 'cdsp-experiment', 'cpufreq-cap', 'identity-switch', 'operator-notice', 'gpu-retry'):
        f = root / 'usr/libexec/sp11' / name
        assert f.stat().st_mode & 0o111 and f.read_bytes() == (repo / 'image/overlay/usr/libexec/sp11' / name).read_bytes(), name
        subprocess.run(['bash', '-n', str(f)], check=True)
    assert not (root / 'usr/libexec/sp11-esp-env').exists() and not (root / 'usr/libexec/sp11/cdsp-variant').exists(), 'GRUB environment helpers still installed'
    helper = root / 'usr/libexec/sp11-boot-state'
    assert helper.stat().st_mode & 0o111 and helper.read_bytes() == (repo / 'image/overlay/usr/libexec/sp11-boot-state').read_bytes(), 'sp11-boot-state'
    subprocess.run(['bash', '-n', str(helper)], check=True)
    h = helper.read_text()
    for needle in ('disk_has_windows', 'find_boot_disk', 'SP11LOGS', 'LABEL', 'pkname', 'S4', 'sp11/state', 'marker'):
        assert needle in h, f'sp11-boot-state lacks {needle}'
    assert 'grubenv' not in h.replace('menu1 failed', '') .replace('no GRUB environment block', ''), 'sp11-boot-state touches a grubenv'
    order = [l.strip() for l in (root / 'usr/share/sp11/sam-mode-order').read_text().splitlines() if l.strip() and not l.startswith('#')]
    assert order == ['silent', 'clean', 'quiet', 'default'], f'SAM rotor order {order}'
    for u, target in (('sp11-sam-mode-rotor.service', 'sysinit'), ('sp11-identity-switch.service', 'sysinit'),
                      ('sp11-cdsp-experiment.service', 'multi-user'), ('sp11-cpufreq-cap.service', 'multi-user')):
        p = root / 'usr/lib/systemd/system' / u
        assert p.read_bytes() == (repo / 'image/overlay/usr/lib/systemd/system' / u).read_bytes(), u
        assert (root / f'etc/systemd/system/{target}.target.wants' / u).readlink() == Path('/usr/lib/systemd/system') / u, u
    for u in ('sp11-sam-mode-rotor.service', 'sp11-identity-switch.service'):
        t = (root / 'usr/lib/systemd/system' / u).read_text()
        assert 'DefaultDependencies=no' in t and 'Before=' in t and 'sp11-log-collector.service' in t, f'{u} ordering'
    assert 'ConditionKernelCommandLine=sp11.entry=debug' in (root / 'usr/lib/systemd/system/sp11-cdsp-experiment.service').read_text(), 'CDSP experiment is not main-entry gated'
    assert 'ConditionPathExists=/usr/share/sp11/image-mode' in (root / 'usr/lib/systemd/system/sp11-identity-switch.service').read_text(), 'identity switch not private-gated'
    assert (root / 'etc/modules-load.d/sp11-cpufreq.conf').read_text().split('\n')[-2] == 'scmi_cpufreq' and 'scmi_cpufreq' in (repo / 'image/overlay/etc/modules-load.d/sp11-cpufreq.conf').read_text(), 'modules-load.d scmi_cpufreq'
    # touch: profile B default, A by marker; owner files byte for byte, image-owned selector
    for src, dst in (('hardware/touch-pen/userspace/iptsd-sp11.conf', 'usr/share/sp11/touch/iptsd-sp11.conf'),
                     ('hardware/touch-pen/userspace/10-sp11-touch-conf.conf', 'usr/lib/systemd/system/iptsd@.service.d/10-sp11-touch-conf.conf'),
                     ('hardware/touch-pen/collector/sp11-touch-tap-diag', 'usr/libexec/sp11-touch-tap-diag')):
        assert (root / dst).read_bytes() == (repo / src).read_bytes(), f'{dst} differs from {src}'
    sel = root / 'usr/libexec/sp11-touch-conf-select'
    assert sel.stat().st_mode & 0o111 and sel.read_bytes() == (repo / 'image/overlay/usr/libexec/sp11-touch-conf-select').read_bytes(), 'touch selector'
    assert 'marker touch-conf-A' in sel.read_text() and 'grubenv' not in sel.read_text().replace('GRUB environment', '') and 'esp-env' not in sel.read_text(), 'selector must use the marker file only'
    assert (root / 'usr/libexec/sp11-touch-tap-diag').stat().st_mode & 0o111, 'tap diag not executable'
    tc = (root / 'etc/sp11-log-collector.d/touch-conf.sh').read_text()
    assert 'sp11-touch-tap-diag' in tc and not any(l.strip().startswith(('/usr/libexec/sp11-touch-tap-diag', 'timeout')) and 'tap-diag' in l and 'echo' not in l for l in tc.splitlines()), 'collector runs the tap diagnostic'
    assert 'ActivationThreshold = 20' in (root / 'usr/share/sp11/touch/iptsd-sp11.conf').read_text(), 'profile B values'
    # identity experiment of the wifi and bluetooth workers: owner files byte for byte
    for src, dst in (('hardware/wifi/collector/identity.sh', 'etc/sp11-log-collector.d/wifi-identity.sh'), ('hardware/wifi/userspace/sp11-wifi-identity', 'usr/libexec/sp11-wifi-identity'),
                     ('hardware/wifi/userspace/sp11-wifi-identity.service', 'usr/lib/systemd/system/sp11-wifi-identity.service'),
                     ('hardware/bluetooth/collector/identity.sh', 'etc/sp11-log-collector.d/bluetooth-identity.sh'), ('hardware/bluetooth/collector/sp11-identity-bt', 'usr/libexec/sp11-identity-bt'),
                     ('hardware/bluetooth/collector/sp11-identity-bt-pre.service', 'usr/lib/systemd/system/sp11-identity-bt-pre.service')):
        assert (root / dst).read_bytes() == (repo / src).read_bytes(), f'{dst} differs from {src}'
    assert (root / 'etc/systemd/system/sys-subsystem-bluetooth-devices-hci0.device.wants/sp11-identity-bt-pre.service').is_symlink(), 'bt pre unit not wanted by hci0'
    assert (root / 'etc/xdg/autostart/sp11-operator-notice.desktop').is_file(), 'desktop notification autostart'
    sam = (root / 'usr/libexec/sp11/sam-mode-rotor').read_text()
    for needle in ('shutdown_mode', 'sp11_sam_counter', 'sp11-boot-state', 'SAM shutdown mode for this boot:', 'add 10-sam'):
        assert needle in sam, f'SAM rotor lacks {needle}'
    cd = (root / 'usr/libexec/sp11/cdsp-experiment').read_text()
    for needle in ('sp11_cdsp_counter', 'keep_proxy_pds', 'FULL POWER-OFF', 'NOT a reboot', 'firmware-sp11-cdsp46', 'twrite "$cd_dir/state" stop', 'twrite "$cd_dir/state" start', 'mkdir "$RUN/cdsp-experiment.lock"', 'sp11.entry', 'WAIT_STATE', 'firmware_class/parameters/path'):
        assert needle in cd, f'CDSP experiment lacks {needle}'
    cf = (root / 'usr/libexec/sp11/cpufreq-cap').read_text()
    for needle in ('enable-cpufreq-cap', 'schedutil', 'scaling_max_freq', 'scaling_available_frequencies', 'never performance'):
        assert needle in cf, f'cpufreq cap lacks {needle}'
    assert 'printf performance' not in cf and 'printf ondemand' not in cf, 'cpufreq cap sets a forbidden governor'
    on = (root / 'usr/libexec/sp11/operator-notice').read_text()
    for needle in ('notify-send', 'logger -t sp11-notice', '/usr/share/sp11/operator-notice.txt', 'motd.d'):
        assert needle in on, f'operator-notice lacks {needle}'
    # collectors: image-owned drop-ins byte-identical to the repository, owner collectors unchanged
    dropins = root / 'etc/sp11-log-collector.d'
    for name in ('usb-typec.sh', 'bluetooth.sh', 'ssam-shutdown-mode.sh', 'cameras.sh', 'audio.sh', 'rotors.sh', 'touch-conf.sh'):
        assert (dropins / name).read_bytes() == (repo / 'image/overlay/etc/sp11-log-collector.d' / name).read_bytes(), name
        subprocess.run(['bash', '-n', str(dropins / name)], check=True)
    pt = repo / 'hardware/power-thermal/collector/power-thermal.sh'
    assert digest(pt) == pins['power_thermal']['collector_sha256'] and digest(dropins / 'power-thermal.sh') == digest(pt), 'power-thermal collector'
    subprocess.run(['bash', '-n', str(dropins / 'power-thermal.sh')], check=True)
    for rel, want in pins['power_thermal']['overlay'].items():
        assert digest(root / rel) == want, f'power-thermal overlay {rel}'
    for u in ('sp11-suspend-diag.service', 'sp11-suspend-policy.service', 'sp11-wakeup-policy.service', 'sp11-thermal-sample.service'):
        assert 'ConditionKernelCommandLine=sp11.' in (root / 'usr/lib/systemd/system' / u).read_text(), f'{u} is not opt-in'
    assert all('sp11.suspend_diag' not in e['linux_args'] for e in record['grub_entries']), 'suspend_diag in the menu'
    hook = (root / 'usr/lib/systemd/system-sleep/sp11-suspend').read_text()
    assert 'sp11-cpuidle-guard disable' in hook and 'sp11-cpuidle-guard enable' in hook, 'default-on s2idle guard missing'
    assert (root / 'usr/lib/systemd/system-sleep/sp11-suspend').stat().st_mode & 0o111, 'sleep hook not executable'
    usb = (dropins / 'usb-typec.sh').read_text()
    for needle in ('portli', 'dynamic_debug/control', '/proc/cmdline', 'usb-pd-partner.txt', 'number_of_alternate_modes', 'systemctl is-active --quiet upower.service'):
        assert needle in usb, f'usb-typec drop-in lacks {needle}'
    cam = (dropins / 'cameras.sh').read_text()
    assert 'i2cdetect' not in ''.join(l for l in cam.splitlines() if not l.lstrip().startswith('#')), 'camera drop-in runs i2cdetect'
    for needle in ('media-ctl', 'cam_cc_mclk1', 'regulator_summary', 'ov13858'):
        assert needle in cam, f'camera drop-in lacks {needle}'
    aud = (dropins / 'audio.sh').read_text()
    for needle in ('arecord -l', 'wpctl status', 'amixer -c 0 contents', 'alsaucm -c hw:0 list _verbs', '/sys/kernel/debug/sp11/guard', '/proc/asound/pcm'):
        assert needle in aud, f'audio drop-in lacks {needle}'
    code = '\n'.join(l for l in aud.splitlines() if not l.lstrip().startswith('#'))
    assert 'aplay -D' not in code and 'arecord -D' not in code and 'amixer -c 0 cset' not in code and ' cset ' not in code and 'sset' not in code and 'set _verb' not in code, 'audio drop-in plays, records or writes a control'
    rot = (dropins / 'rotors.sh').read_text()
    for needle in ('/run/sp11/sam-mode', '/run/sp11/cdsp-experiment', '/run/sp11/gpu-test', '/run/sp11/cpufreq-cap', '/run/sp11/identity-switch', 'scmi', 'cpufreq', 'sp11-boot-state list'):
        assert needle in rot, f'rotors drop-in lacks {needle}'
    ssam = (dropins / 'ssam-shutdown-mode.sh').read_text()
    assert 'parameters/shutdown_mode' in ssam and 'shutdown mode' in ssam, 'SAM shutdown mode record'
    collector = (root / 'usr/libexec/sp11-log-collector').read_text()
    assert 'portsc|portli' in collector and 'dynamic_debug/control' in collector, 'debugfs allow-list lacks portli or dynamic_debug'
    assert 'dp_debug' not in collector.split('debugfs_allowed()')[1].split('dbgcat()')[0], 'dp_debug on the allow-list'
    dsp_owner = (repo / 'hardware/dsp-subsystems/collector/dsp-subsystems.sh').read_bytes()
    assert digest(repo / 'hardware/dsp-subsystems/collector/dsp-subsystems.sh') == pins['dsp_collector_sha256'], 'DSP owner collector changed after the pin'
    dsp = (dropins / 'dsp-subsystems.sh').read_bytes()
    assert dsp.startswith(dsp_owner), 'installed DSP collector does not start with the owner collector'
    assert digest(dropins / 'ec-sam.sh') == pins['ec_sam_collector_sha256'], 'ec-sam collector differs from the pinned owner file'
    # packages: libcamera, FastRPC (D12: Fedora's udev rule, root:fastrpc 0640, never 0666)
    for pkg in pins['libcamera']['packages'] + pins['fastrpc']['packages'] + ['libnotify']:
        subprocess.run(['rpm', '--root', str(root), '-q', pkg], check=True, capture_output=True)
    assert (root / 'usr/bin/cam').exists(), 'cam missing'
    rules = (root / 'usr/lib/udev/rules.d/60-fastrpc.rules').read_text()
    assert 'GROUP="fastrpc"' in rules and 'MODE="0640"' in rules, 'FastRPC rule is not group fastrpc 0640'
    for d in ('usr/lib/udev/rules.d', 'etc/udev/rules.d'):
        for r in (root / d).glob('*'):
            if r.is_file():
                assert not ('fastrpc' in r.read_text() and 'MODE="0666"' in r.read_text()), f'{r.name}: world-writable FastRPC node'
    assert 'fastrpc' in (root / 'usr/lib/sysusers.d/fastrpc.conf').read_text(), 'no fastrpc group definition'
    assert not (root / 'opt/qairt').exists() and not (root / 'usr/bin/hexagonrpcd').exists(), 'QAIRT or a local hexagonrpcd build in the image'


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]), Path(sys.argv[2]), json.load(open(sys.argv[3])))
    except (AssertionError, OSError, KeyError, ValueError, IndexError, subprocess.CalledProcessError) as error:
        sys.exit(f'FAIL M15 payload: {error}')
    print('PASS M15 payload: collectors, GPU two-step with hooks, rotors, speaker first-test tooling, UCM fix, power-thermal, FastRPC, libcamera')
