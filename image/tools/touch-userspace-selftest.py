#!/usr/bin/env python3
"""S5 regression: only libinput names and masked iptsd messages leave the helper."""
import contextlib
import io
import runpy
import subprocess
import sys
from unittest.mock import patch

helper = runpy.run_path(sys.argv[1])
address = ':'.join(['12', '34', '56', '78', '9a', 'bc'])
serial = 'synthetic-private-identifier'
fixtures = [
    ('devices', f'Device: Touch {address}\nKernel: /dev/input/event9\nGroup: 7\nSeat: seat0\nSerial: {serial}\n',
     'Touch [masked-address]\n'),
    ('journal', f'connected {address} serial={serial}\n',
     'connected [masked-address] serial=[masked]\n'),
    ('devices', '', '<no device names>\n'),
]
for kind, raw, expected in fixtures:
    result = subprocess.CompletedProcess([], 0, stdout=raw, stderr=serial)
    with patch('subprocess.run', return_value=result) as call, contextlib.redirect_stdout(io.StringIO()) as output:
        assert helper['collect'](kind) == 0
    assert output.getvalue() == expected, output.getvalue()
    assert address not in output.getvalue() and serial not in output.getvalue()
    assert call.call_args.kwargs['timeout'] == 20
print('PASS: touch userspace collector names-only and identifier masking fixtures')
