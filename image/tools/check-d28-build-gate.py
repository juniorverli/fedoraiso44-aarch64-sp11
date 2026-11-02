#!/usr/bin/env python3
"""Check the D28 evidence gate for a public or private image build."""
import json
from pathlib import Path
import sys

SOURCE = '993a17dcb672357998a463a73f120064d6c74f4f'
TOPOLOGY = 'b192044f01e97eabe7f6df9ae0d394086badb3c30124573210bc781093da8c03'
RUNTIME_FIELDS = (
    'device_dmi_match', 'alsaucm_profile_resolved', 'initial_mute_confirmed',
    'pipewire_ceiling_enforced', 'speaker_off_fallback_mic_dp',
    'kernel_d28_guard', 'closed_loop_fail_closed',
)


def check(record, mode):
    assert record.get('source_commit') == SOURCE, 'source_commit pin missing or wrong'
    assert record.get('topology_sha256') == TOPOLOGY, 'topology_sha256 pin missing or wrong'
    if mode == 'public':
        assert all(record.get(key) is True for key in RUNTIME_FIELDS), \
            'public build requires all seven D28 runtime fields to be true'
    elif mode != 'private':
        raise AssertionError('mode must be public or private')


def build_record(runtime_record, topology_pin, mode):
    if mode != 'private':
        return runtime_record
    runtime_record = runtime_record or {}
    return {
        'status': 'unvalidated',
        'source_commit': runtime_record.get('source_commit', topology_pin['source_commit']),
        'topology_sha256': runtime_record.get('topology_sha256', topology_pin['sha256']),
    }


if __name__ == '__main__':
    try:
        check(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
    except (AssertionError, IndexError, OSError, ValueError) as error:
        sys.exit(f'FAIL D28 build gate: {error}')
    print(f'PASS D28 {sys.argv[2]} build gate')
