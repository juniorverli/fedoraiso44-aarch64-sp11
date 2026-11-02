#!/usr/bin/env python3
"""Exercise post-session capture with fake devices; never records host audio."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
with tempfile.TemporaryDirectory(prefix='sp11-post-session-') as directory:
    tmp = Path(directory)
    binary = tmp / 'bin'
    binary.mkdir()
    runtime = tmp / 'runtime'
    runtime.mkdir()
    for name, code in {
        'sleep': 'exit 0',
        'wpctl': '''case "$1" in
 inspect) printf 'id 77, type PipeWire:Interface:Node\\n    node.name = "alsa_input.platform-sound.mic"\\n' ;;
 get-volume) printf 'Volume: 0.75 [MUTED]\\n' ;;
 *) printf "wpctl %s\\n" "$*" ;;
esac''',
        'amixer': '''printf "numid=1,name='SpkrLeft PA Volume'\\n  : values=6\\nnumid=2,name='unrelated'\\n  : values=42\\n"''',
        'alsaucm': 'printf "ucm %s\\n" "$*"',
        'arecord': '''if [ "$CAPTURE_MODE" = zero ]; then exit 0; fi
python3 -c 'import sys; sys.stdout.buffer.write(bytes([0, 64, 0, 224])*48000)'
[ "$CAPTURE_MODE" != fail ] || exit 7''',
    }.items():
        path = binary / name
        path.write_text('#!/bin/sh\n' + code + '\n')
        path.chmod(0o755)
    script = tmp / 'collect'
    script.write_text(source.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin',
                                     f'PATH={binary}:/usr/sbin:/usr/bin:/sbin:/bin')
                      .replace('/dev/video*', str(tmp / 'video*'))
                      .replace('/dev/media*', str(tmp / 'media*')))
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime))
    for mode in ('ok', 'fail', 'zero'):
        env['CAPTURE_MODE'] = mode
        completed = subprocess.run(['bash', str(script)], env=env, timeout=30)
        assert completed.returncode == (0 if mode == 'ok' else 1), mode
        result = (runtime / 'sp11-post-session.txt').read_text()
        for value in ('wpctl inspect @DEFAULT_AUDIO_SINK@', 'wpctl inspect @DEFAULT_AUDIO_SOURCE@',
                      'node.name = "alsa_input.platform-sound.mic"', 'Volume: 0.75 [MUTED]',
                      'SpkrLeft PA Volume', 'ucm -c hw:0 dump text', '=== video nodes',
                      '=== capture hw:0,1:', '=== capture default:'):
            assert value in result, value
        if mode != 'zero':
            for value in ('channel=left samples=48000 rms=0.50000000 peak=0.50000000',
                          'channel=right samples=48000 rms=0.25000000 peak=0.25000000'):
                assert result.count(value) == 2, value
        if mode == 'ok':
            assert result.count('arecord_exit=0 analysis_exit=0') == 2
        elif mode == 'fail':
            assert result.count('arecord_exit=7 analysis_exit=0') == 2
        else:
            assert result.count('ERROR: zero samples') == 2
        assert 'unrelated' not in result
        assert sorted(p.name for p in runtime.iterdir()) == ['sp11-post-session.txt']
print('post-session capture fixtures passed')
