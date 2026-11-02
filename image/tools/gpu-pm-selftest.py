#!/usr/bin/env python3
"""Exercise GPU PM helpers against fake files; never touches host sysfs."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'image/overlay'
with tempfile.TemporaryDirectory(prefix='sp11-gpu-pm-') as directory:
    tmp = Path(directory)
    sysfs = tmp / 'devices'
    cmdline = tmp / 'cmdline'
    kmsg = tmp / 'kmsg'
    kmsg.touch()
    bindir = tmp / 'bin'
    bindir.mkdir()
    sleep = bindir / 'sleep'
    sleep.write_text('#!/bin/sh\nprintf x >> "$SP11_SLEEP_MARKER"\nexit 0\n')
    sleep.chmod(0o755)
    sleep_marker = tmp / 'sleep-marker'
    env = dict(os.environ, PATH=f'{bindir}:' + os.environ['PATH'], SP11_SLEEP_MARKER=str(sleep_marker))
    gpu = sysfs / '3d00000.gpu/power/control'
    gmu = sysfs / '3d6a000.gmu/power/control'
    runtime = gmu.parent / 'runtime_status'
    for path, value in ((gpu, 'auto\n'), (gmu, 'auto\n'), (runtime, 'suspended\n')):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    helpers = []
    for name in ('sp11-gpu-pm-early', 'sp11-gpu-no-runtime-pm'):
        source = (root / 'usr/libexec' / name).read_text()
        source = source.replace('/proc/cmdline', str(cmdline)).replace('/sys/bus/platform/devices', str(sysfs))
        source = source.replace('> /dev/kmsg', '>> ' + str(kmsg)).replace('tee /dev/kmsg', 'tee -a ' + str(kmsg))
        helper = tmp / name
        helper.write_text(source)
        helpers.append(helper)
    def run(helper, *args):
        kmsg.write_text('')
        return subprocess.run(['bash', str(helper), *args], env=env, capture_output=True, text=True, timeout=5)
    cmdline.write_text('sp11.entry=safe\n')
    for helper, args in ((helpers[0], ('3d00000.gpu',)), (helpers[0], ('3d6a000.gmu',)), (helpers[1], ())):
        assert run(helper, *args).returncode == 0
        assert gpu.read_text() == gmu.read_text() == 'auto\n' and not kmsg.read_text()
    cmdline.write_text('sp11.entry=debug sp11.gpu_pin=0\n')
    for helper, args in ((helpers[0], ('3d00000.gpu',)), (helpers[0], ('3d6a000.gmu',)), (helpers[1], ())):
        assert run(helper, *args).returncode == 0
        assert kmsg.read_text() == '<6>sp11-gpu-pin: skipped by sp11.gpu_pin=0\n'
        assert gpu.read_text() == gmu.read_text() == 'auto\n'
    cmdline.write_text('sp11.entry=debug\n')
    for helper, args in ((helpers[0], ('3d00000.gpu',)), (helpers[1], ())):
        gpu.write_text('auto\n')
        assert run(helper, *args).returncode == 0
        assert gpu.read_text() == 'on\n' and gmu.read_text() == 'auto\n'
        assert f'path={gpu} written=on readback=on' in kmsg.read_text()
        assert f'path={gmu} read=auto' in kmsg.read_text()
        assert f'path={runtime} read=suspended' in kmsg.read_text()
    gpu.write_text('auto\n')
    assert run(helpers[0], '3d6a000.gmu').returncode == 0
    assert gpu.read_text() == gmu.read_text() == 'auto\n'
    assert f'path={runtime} read=suspended' in kmsg.read_text()
    assert run(helpers[0], 'other').returncode != 0
    gmu.unlink()
    runtime.unlink()
    assert run(helpers[1]).returncode == 0
    assert f'path={gmu} read=READ_FAILED' in kmsg.read_text()
    assert not sleep_marker.exists(), 'service waited for the missing GMU'
    gpu.unlink()
    gpu.symlink_to('/dev/full')
    for helper, args in ((helpers[0], ('3d00000.gpu',)), (helpers[1], ())):
        assert run(helper, *args).returncode != 0
        assert 'readback=WRITE_FAILED' in kmsg.read_text()
print('GPU PM helper fake-sysfs tests passed')
