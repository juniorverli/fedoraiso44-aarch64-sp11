#!/usr/bin/env python3
"""Exercise D28 private and public runtime gate cases without building an ISO."""
import importlib.util
import sys
from pathlib import Path
import re

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    'check_d28_build_gate', Path(__file__).with_name('check-d28-build-gate.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

base = {
    'source_commit': module.SOURCE,
    'topology_sha256': module.TOPOLOGY,
}
fields = module.RUNTIME_FIELDS
for mode, fields_record, expected in (
    ('private', {}, True),
    ('private', {k: False for k in fields}, True),
    ('public', {k: True for k in fields}, True),
    ('public', {}, False),
    ('public', {**{k: True for k in fields}, 'kernel_d28_guard': False}, False),
):
    record = {**base, **fields_record}
    try:
        module.check(record, mode)
        result = True
    except AssertionError:
        result = False
    assert result is expected, f'{mode} gate result {result}, expected {expected}: {record}'

for field in ('source_commit', 'topology_sha256'):
    record = dict(base)
    record.pop(field)
    try:
        module.check(record, 'private')
    except AssertionError:
        pass
    else:
        raise AssertionError(f'private gate accepted missing {field}')

topology_pin = {'source_commit': module.SOURCE, 'sha256': module.TOPOLOGY}
for runtime in (None, base, {**base, **{key: False for key in fields}},
                {**base, **{key: True for key in fields}}):
    built = module.build_record(runtime, topology_pin, 'private')
    assert built == {'status': 'unvalidated', 'source_commit': module.SOURCE,
                     'topology_sha256': module.TOPOLOGY}, built
assert module.build_record({**base, **{key: True for key in fields}},
                           topology_pin, 'public') == {**base, **{key: True for key in fields}}

payload_spec = importlib.util.spec_from_file_location(
    'check_m11_payload', Path(__file__).with_name('check-m11-payload.py'))
payload = importlib.util.module_from_spec(payload_spec)
payload_spec.loader.exec_module(payload)
decoded_capture = """SectionPCMCapabilities {
    'MultiMedia2 Capture' {
        formats 'S16_LE'
        rate_min 48000
        rate_max 48000
        channels_min 1
        channels_max 2
    }
}"""
payload.check_mic_capture_caps(decoded_capture)
for changed in ('channels_max 1', 'rate_min 44100', "formats 'S32_LE'"):
    try:
        payload.check_mic_capture_caps(decoded_capture.replace(
            'channels_max 2' if changed.startswith('channels_max') else
            'rate_min 48000' if changed.startswith('rate_min') else
            "formats 'S16_LE'", changed))
    except AssertionError:
        pass
    else:
        raise AssertionError(f'topology capture checker accepted {changed}')

print('PASS D28 gate and record cases: private absent/false runtime fields accepted and serialized as unvalidated; public missing/false rejected; both modes require source and topology pins')
