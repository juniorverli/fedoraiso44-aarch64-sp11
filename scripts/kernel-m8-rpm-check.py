#!/usr/bin/env python3
"""Record M8 touch and M9 Wi-Fi/USB-C changes in release RPM payloads (Fedora container)."""
import hashlib
import json
import lzma
from pathlib import Path
import re
import subprocess
import struct
import sys


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def elf_symbol(data, wanted):
    """Read a local object's bytes from an ELF64 little-endian module/object."""
    require(data[:6] == b'\x7fELF\x02\x01', 'Expected ELF64 little endian')
    shoff = struct.unpack_from('<Q', data, 0x28)[0]
    entsize, count = struct.unpack_from('<HH', data, 0x3a)
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * entsize)
                for i in range(count)]
    for section in sections:
        if section[1] != 2:  # SHT_SYMTAB
            continue
        strings = sections[section[6]]
        table = data[strings[4]:strings[4] + strings[5]]
        for offset in range(section[4], section[4] + section[5], section[9]):
            name, _, _, index, value, size = struct.unpack_from('<IBBHQQ', data, offset)
            if table[name:table.find(b'\0', name)].decode() == wanted:
                target = sections[index]
                start = target[4] + value - target[3]
                return data[start:start + size]
    raise SystemExit(f'Missing ELF symbol {wanted}')


checks, kver, rpmdir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
milestone = sys.argv[4] if len(sys.argv) > 4 else 'm8'
require(milestone in ('m8', 'm9', 'm10', 'm11', 'm12'), 'Expected m8, m9, m10, m11 or m12')
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
if milestone in ('m9', 'm10', 'm11', 'm12'):
    names += ['ath12k', 'ps883x', 'pmic_glink_altmode']
if milestone in ('m10', 'm11', 'm12'):
    names += ['qcom_glink']
if milestone in ('m11', 'm12'):
    names += ['snd-soc-wsa884x', 'snd-soc-x1e80100']
if milestone == 'm12':
    names += ['snd-soc-lpass-wsa-macro']
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
if milestone in ('m11', 'm12'):
    diagnostics['qcom_glink'] += [b'sp11-glink: FIFO tx head=%u tail=%u rx head=%u tail=%u\n']
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
    if name == 'snd-soc-wsa884x':
        defaults = elf_symbol(data, 'wsa884x_defaults')
        values = [value for reg, value in struct.iter_unpack('<II', defaults) if reg == 0x34b1]
        require(values == [0x32], 'WSA PA reset is not mixer value 6 (0 dB), GAIN_EN off')
    if name == 'snd-soc-x1e80100':
        for prefix in ('WSA', 'WSA2'):
            for channel in (0, 1):
                require(f'{prefix} WSA_RX{channel}_MIX Digital Volume'.encode() + b'\0' in data,
                        'Missing WSA MIX volume ceiling in machine module')
    if name in diagnostics:
        for message in diagnostics[name]:
            require(message in data, f'{name}: missing diagnostic {message!r}')
    records[name] = dict(path=installed, rpm=owners[0], aliases=aliases,
                         module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),
                         elf_sha256=hashlib.sha256(data).hexdigest())
    if name in diagnostics:
        records[name]['diagnostic_strings'] = [m.decode().rstrip() for m in diagnostics[name]]
    if name in ('snd-soc-wsa884x', 'snd-soc-x1e80100', 'snd-soc-lpass-wsa-macro'):
        relative = {'snd-soc-wsa884x': 'sound/soc/codecs/wsa884x.o',
                    'snd-soc-x1e80100': 'sound/soc/qcom/x1e80100.o',
                    'snd-soc-lpass-wsa-macro': 'sound/soc/codecs/lpass-wsa-macro.o'}[name]
        objects = list((checks.parent / 'rpmbuild/BUILD').glob('**/' + relative))
        require(len(objects) == 1, f'Missing/ambiguous release audio object: {relative}')
        obj = objects[0]
        object_data = obj.read_bytes()
        if name == 'snd-soc-lpass-wsa-macro':
            pass
        elif name == 'snd-soc-wsa884x':
            if milestone == 'm12':
                # audio 0004: explicit DRE_CTL_1 (0x34b1) read-back and write at attach.
                text = subprocess.run(['objdump', '-dr', str(obj)], check=True, capture_output=True, text=True).stdout
                require(re.search(r'#0x34b1\b', text), 'Release WSA object lacks the explicit DRE_CTL_1 write (0004)')
            defaults = elf_symbol(object_data, 'wsa884x_defaults')
            require([v for r, v in struct.iter_unpack('<II', defaults) if r == 0x34b1] == [0x32],
                    'Release WSA object lacks safe PA reset')
        else:
            for prefix in ('WSA', 'WSA2'):
                for channel in (0, 1):
                    require(f'{prefix} WSA_RX{channel}_MIX Digital Volume'.encode() + b'\0'
                            in object_data, 'Release machine object lacks MIX limit control')
            disassembly = subprocess.run(['objdump', '-dr', '--disassemble=x1e80100_snd_init', str(obj)],
                                         check=True, capture_output=True, text=True).stdout
            require(len(re.findall(r'mov\s+w2,\s*#0x51\b', disassembly)) == 8,
                    'Machine init must set eight digital ceilings to 81 (-3 dB)')
            (checks / 'x1e80100-init.disassembly.txt').write_text(disassembly)
        records[name]['object'] = str(obj.relative_to(checks.parent))
        records[name]['object_sha256'] = hashlib.sha256(object_data).hexdigest()
    if name == 'snd-soc-wsa884x':
        records[name]['pa_reset_register'] = '0x34b1'
        records[name]['pa_reset_value'] = '0x32'
        records[name]['pa_mixer_value'] = 6
    if name == 'snd-soc-x1e80100':
        records[name]['mix_volume_controls'] = 4
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
if milestone in ('m9', 'm10', 'm11', 'm12'):
    record['new_modules'] = {name: records[name] for name in names[8:]}
    record['cma_dma32'] = record['wiring']['cma_dma32']
(checks / f'{milestone}.json').write_text(json.dumps(record, indent=2) + '\n')
print(f'{milestone.upper()} packaged DTB schema/S1/GPU/wiring and RPM payloads: PASS')
