#!/usr/bin/env python3
"""Record M8 touch and M9 Wi-Fi/USB-C changes in release RPM payloads (Fedora container)."""
import hashlib
import json
import lzma
from pathlib import Path
import re
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise SystemExit(message)


checks, kver, rpmdir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
milestone = sys.argv[4] if len(sys.argv) > 4 else 'm8'
require(milestone in ('m8', 'm9', 'm10'), 'Expected m8, m9 or m10')
root = checks / 'root/lib/modules' / kver
payloads = {}
for rpm in sorted(rpmdir.glob(f'kernel-*{kver}.rpm')):
    if rpm.name.startswith(('kernel-core-', 'kernel-modules-', 'kernel-modules-core-',
                            'kernel-modules-extra-', 'kernel-modules-internal-')):
        payloads[rpm.name] = subprocess.run(['rpm', '-qlp', str(rpm)], check=True,
                                           capture_output=True, text=True).stdout.splitlines()

records = {}
names = ['spi-hid', 'spi-hid-of', 'spi-hid-acpi', 'spi-geni-qcom', 'gpi',
         'fixed', 'hid-multitouch', 'uinput']
if milestone in ('m9', 'm10'):
    names += ['ath12k', 'ps883x', 'pmic_glink_altmode']
if milestone == 'm10':
    names += ['qcom_glink']
diagnostics = {
    'pmic_glink_altmode': [
        b'request: cmd=%#x arg=%u acknowledged\n',
        b'apply: port=%u orientation=%u mux=%u svid=%04x switch_ret=%d\n',
        b'notify: port=%u orientation=%u mux=%u svid=%04x\n'],
    'ps883x': [
        b'assert reset and disable supplies\n',
        b'configure: conn_status=%02x/%02x/%02x reset=%u in_reset=%u\n',
        b'orientation: %u -> %u in_reset=%u\n',
        b'set: mode=%lu svid=%04x orientation=%u in_reset=%u ret=%d\n'],
    'qcom_glink': [
        b'sp11-glink: tx VERSION ', b'sp11-glink: tx OPEN ', b'sp11-glink: tx OPEN_ACK ']}
for name in names:
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
    if name == 'ath12k':
        for compatible in (b'microsoft,denali', b'microsoft,romulus13', b'microsoft,romulus15'):
            require(compatible + b'\0' in data, 'Packaged ath12k lacks Surface rfkill match')
        elf = checks / 'ath12k.ko'
        elf.write_bytes(data)
        symbols = subprocess.run(['readelf', '-sW', str(elf)], check=True,
                                 capture_output=True, text=True).stdout
        require('ath12k_core_broken_rfkill_table' in symbols,
                'Packaged ath12k lacks the broken-rfkill table')
        disassembly = subprocess.run(['objdump', '-dr', str(elf)], check=True,
                                    capture_output=True, text=True).stdout
        require(re.search(r'R_AARCH64_CALL26\s+of_machine_compatible_match\b', disassembly),
                'Packaged ath12k lacks the machine-compatible rfkill test call')
        (checks / 'ath12k.disassembly.txt').write_text(disassembly)
        (checks / 'ath12k.symbols.txt').write_text(symbols)
    if name in diagnostics:
        for message in diagnostics[name]:
            require(message in data, f'{name}: missing diagnostic {message!r}')
    records[name] = dict(path=installed, rpm=owners[0], aliases=aliases,
                         module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),
                         elf_sha256=hashlib.sha256(data).hexdigest())
    if name in diagnostics:
        records[name]['diagnostic_strings'] = [m.decode().rstrip() for m in diagnostics[name]]
    if name == 'ath12k':
        records[name]['surface_broken_rfkill_table'] = True
        records[name]['machine_compatible_match_call'] = True
        records[name]['disassembly_sha256'] = hashlib.sha256(disassembly.encode()).hexdigest()

dtb = root / 'dtb/qcom/x1p64100-microsoft-denali.dtb'
record = dict(packaged_dtb_sha256=hashlib.sha256(dtb.read_bytes()).hexdigest(),
              dt_validate=dict(exit_code=0, diagnostic_lines=0),
              s1_effective_status=json.loads((checks / 'packaged.safety.json').read_text()),
              wiring=json.loads((checks / 'packaged.wiring.json').read_text()),
              touch_modules={name: records[name] for name in names[:8]},
              qspi_protocol_guard=True, gpi_qspi_tre_path=True,
              rfc0014_removed=True)
if milestone in ('m9', 'm10'):
    record['new_modules'] = {name: records[name] for name in names[8:]}
    record['cma_dma32'] = record['wiring']['cma_dma32']
(checks / f'{milestone}.json').write_text(json.dumps(record, indent=2) + '\n')
print(f'{milestone.upper()} packaged DTB schema/S1/GPU/wiring and RPM payloads: PASS')
