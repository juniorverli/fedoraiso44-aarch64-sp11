#!/usr/bin/env python3
"""Exercise sink discovery, mute verification and startup levels without audio hardware."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
with tempfile.TemporaryDirectory(prefix='sp11-audio-safety-') as directory:
    root = Path(directory)
    binary = root / 'bin'
    binary.mkdir()
    log = root / 'commands'
    cmdline = root / 'cmdline'
    dump = root / 'dump'
    inspect = root / 'inspect'
    (binary / 'pw-dump').write_text('#!/bin/sh\ncat "$FIXTURE_DUMP"\n')
    (binary / 'wpctl').write_text('''#!/bin/sh
printf '%s\n' "$*" >> "$FIXTURE_LOG"
case "$1" in
 inspect) cat "$FIXTURE_INSPECT" ;;
 get-volume) printf 'Volume: 0.00 %s\n' "$FIXTURE_MUTE" ;;
esac
''')
    (binary / 'sleep').write_text('#!/bin/sh\nexit 0\n')
    for path in binary.iterdir():
        path.chmod(0o755)
    script = root / 'helper'
    script.write_text(source.replace('/proc/cmdline', str(cmdline)).replace('seq 1 300', 'seq 1 2'))
    env = dict(os.environ, PATH=f'{binary}:/usr/bin:/bin', FIXTURE_DUMP=str(dump),
               FIXTURE_INSPECT=str(inspect), FIXTURE_LOG=str(log), FIXTURE_MUTE='[MUTED]')
    # A realistic PipeWire device association, a node-name match, and an unrelated sink.
    dump.write_text(json.dumps([
        {'id': 42, 'type': 'PipeWire:Interface:Device', 'info': {'props': {'device.name': 'alsa_card.platform-sound'}}},
        {'id': 58, 'type': 'PipeWire:Interface:Node', 'info': {'props': {'media.class': 'Audio/Sink', 'node.name': 'alsa_output.card.speaker', 'device.id': 42}}},
        {'id': 59, 'type': 'PipeWire:Interface:Node', 'info': {'props': {'media.class': 'Audio/Sink', 'node.name': 'alsa_output.platform-sound.hdmi'}}},
        {'id': 60, 'type': 'PipeWire:Interface:Node', 'info': {'props': {'media.class': 'Audio/Sink', 'node.name': 'alsa_output.usb-headset'}}},
    ]))
    inspect.write_text('id 71, type PipeWire:Interface:Node\n    node.name = "alsa_output.platform-sound.stereo"\n')
    for marker, level in [('', '100%'), ('sp11.audio_first_test=1', '5%')]:
        cmdline.write_text('root=live ' + marker + '\n')
        log.write_text('')
        subprocess.run(['bash', str(script)], env=env, check=True, timeout=10)
        assert log.read_text().splitlines() == [f'{action} {id} {arg}'.rstrip() for id in (58, 59)
            for action, arg in [('set-mute', '1'), ('get-volume', ''), ('set-volume', level)]]
    dump.write_text('[]')
    log.write_text('')
    subprocess.run(['bash', str(script)], env=env, check=True, timeout=10)
    assert log.read_text().splitlines() == ['inspect @DEFAULT_AUDIO_SINK@', 'set-mute 71 1', 'get-volume 71', 'set-volume 71 5%']
    inspect.write_text('id 71, type PipeWire:Interface:Node\n    node.name = "alsa_output.usb-headset"\n')
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and 'no built-in sink' in result.stderr
    inspect.write_text('id 71, type PipeWire:Interface:Node\n    node.name = "alsa_output.platform-sound.stereo"\n')
    env['FIXTURE_MUTE'] = ''
    log.write_text('')
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0 and 'did not report muted' in result.stderr
    assert 'set-volume' not in log.read_text()
print('audio safety selection and mute fixtures passed')
