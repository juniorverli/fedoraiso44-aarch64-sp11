#!/usr/bin/env python3
"""Exercise GPU PM helpers against fake files; never touches host sysfs."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='sp11-gpu-pm-') as directory:
    tmp = Path(directory)
    sysfs = tmp / 'devices'
    cmdline = tmp / 'cmdline'
    kmsg = tmp / 'kmsg'
    kmsg.touch()
    bindir = tmp / 'bin'
    bindir.mkdir()
    sleep = bindir / 'sleep'
    sleep.write_text('#!/bin/sh\nexit 0\n')
    sleep.chmod(0o755)
    env = dict(os.environ, PATH=f'{bindir}:' + os.environ['PATH'])
    controls = [sysfs / name / 'power/control' for name in ('3d00000.gpu', '3d6a000.gmu')]
    for control in controls:
        control.parent.mkdir(parents=True)
        control.write_text('auto\n')
    helpers = []
    for name in ('sp11-gpu-pm-early', 'sp11-gpu-no-runtime-pm'):
        source = (root / 'image/overlay/usr/libexec' / name).read_text()
        source = source.replace('/proc/cmdline', str(cmdline)).replace('/dev/kmsg', str(kmsg))
        source = source.replace('/sys/bus/platform/devices', str(sysfs))
        helper = tmp / name
        helper.write_text(source)
        helpers.append(helper)
    def run(helper, *args):
        return subprocess.run(['bash', str(helper), *args], env=env, capture_output=True, text=True)
    cmdline.write_text('sp11.entry=safe\n')
    assert run(helpers[0], '3d00000.gpu').returncode == 0
    assert run(helpers[1]).returncode == 0
    assert all(p.read_text() == 'auto\n' for p in controls) and not kmsg.read_text()
    cmdline.write_text('sp11.entry=debug\n')
    for control in controls:
        assert run(helpers[0], control.parents[1].name).returncode == 0
        assert control.read_text() == 'on\n'
        assert f'path={control} written=on readback=on' in kmsg.read_text()
    assert run(helpers[0], 'other').returncode != 0
    for control in controls:
        control.write_text('auto\n')
    assert run(helpers[1]).returncode == 0
    assert all(p.read_text() == 'on\n' for p in controls)
    controls[1].unlink()
    controls[1].parent.rmdir()
    assert run(helpers[1]).returncode != 0
    assert 'readback=WRITE_FAILED' in kmsg.read_text()
    controls[1].parent.mkdir()
    controls[1].symlink_to('/dev/null')
    assert run(helpers[0], '3d6a000.gmu').returncode != 0
    assert run(helpers[1]).returncode != 0
    assert 'readback=' in kmsg.read_text()
print('GPU PM helper fake-sysfs tests passed')
