#!/usr/bin/env python3
"""Exercise post-session capture with fake devices; never records host audio."""
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
        'wpctl': 'printf "wpctl %s\\n" "$*"',
        'amixer': '''printf "numid=1,name='SpkrLeft PA Volume'\\n  : values=6\\nnumid=2,name='unrelated'\\n  : values=42\\n"''',
        'alsaucm': 'printf "ucm %s\\n" "$*"',
        'arecord': "python3 -c 'import sys; sys.stdout.buffer.write(bytes([0, 64, 0, 192])*48000)'",
    }.items():
        path = binary / name
        path.write_text('#!/bin/sh\n' + code + '\n')
        path.chmod(0o755)
    script = tmp / 'collect'
    script.write_text(source.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin',
                                     f'PATH={binary}:/usr/sbin:/usr/bin:/sbin:/bin')
                      .replace('/dev/video*', str(tmp / 'video*'))
                      .replace('/dev/media*', str(tmp / 'media*')))
    env = {'XDG_RUNTIME_DIR': str(runtime)}
    subprocess.run(['bash', str(script)], env=env, check=True, timeout=30)
    result = (runtime / 'sp11-post-session.txt').read_text()
    for value in ('wpctl inspect @DEFAULT_AUDIO_SINK@', 'wpctl inspect @DEFAULT_AUDIO_SOURCE@',
                  'SpkrLeft PA Volume', 'ucm -c hw:0 dump text',
                  'samples=96000 rms=0.50000000 peak=0.50000000', '=== video nodes'):
        assert value in result, value
    assert 'unrelated' not in result
    assert sorted(p.name for p in runtime.iterdir()) == ['sp11-post-session.txt']
print('post-session capture fixture passed')
