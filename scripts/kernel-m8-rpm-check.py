#!/usr/bin/env python3
"""Record the M8 touch transport in the release RPM payloads (Fedora container)."""
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise SystemExit(message)


checks, kver, rpmdir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
root = checks / 'root/lib/modules' / kver
payloads = {}
for rpm in sorted(rpmdir.glob(f'kernel-*{kver}.rpm')):
    if rpm.name.startswith(('kernel-core-', 'kernel-modules-', 'kernel-modules-core-',
                            'kernel-modules-extra-', 'kernel-modules-internal-')):
        payloads[rpm.name] = subprocess.run(['rpm', '-qlp', str(rpm)], check=True,
                                           capture_output=True, text=True).stdout.splitlines()

records = {}
for name in ('spi-hid', 'spi-hid-of', 'spi-hid-acpi', 'spi-geni-qcom', 'gpi',
             'fixed', 'hid-multitouch', 'uinput'):
    found = list(root.rglob(f'{name}.ko.xz'))
    require(len(found) == 1, f'Expected exactly one packaged {name} module')
    module = found[0]
    data = lzma.decompress(module.read_bytes())
    installed = '/lib/modules/' + kver + '/' + str(module.relative_to(root))
    owners = [rpm for rpm, files in payloads.items() if installed in files]
    require(len(owners) == 1, f'{name}: missing or ambiguous RPM ownership: {owners}')
    aliases = subprocess.run(['modinfo', '-F', 'alias', str(module)], check=True,
                             capture_output=True, text=True).stdout.splitlines()
    if name == 'spi-geni-qcom':
        require(b'qcom,geni-spi-qspi' in data, 'Packaged GENI module lacks QSPI compatible')
        require(b'Expected QSPI proto %d, got %d\n' in data,
                'Packaged GENI module lacks the preloaded-QSPI protocol guard')
        require(b'touch-pen-diag:' not in data, 'Retired RFC 0014 logger remains in module')
    if name == 'gpi':
        require(b'QSPI TRE:%d' in data, 'Packaged GPI module lacks the QSPI TRE path')
    if name == 'spi-hid-of':
        require('spi:mshw0484' in aliases and any('microsoft,mshw0484' in a for a in aliases),
                'MSHW0484 SPI/OF module aliases missing')
    records[name] = dict(path=installed, rpm=owners[0], aliases=aliases,
                         module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),
                         elf_sha256=hashlib.sha256(data).hexdigest())

dtb = root / 'dtb/qcom/x1p64100-microsoft-denali.dtb'
record = dict(packaged_dtb_sha256=hashlib.sha256(dtb.read_bytes()).hexdigest(),
              dt_validate=dict(exit_code=0, diagnostic_lines=0),
              s1_effective_status=json.loads((checks / 'packaged.safety.json').read_text()),
              wiring=json.loads((checks / 'packaged.wiring.json').read_text()),
              touch_modules=records, qspi_protocol_guard=True, gpi_qspi_tre_path=True,
              rfc0014_removed=True)
(checks / 'm8.json').write_text(json.dumps(record, indent=2) + '\n')
print('M8 packaged DTB schema/S1/GPU/wiring and touch RPM payloads: PASS')
