#!/usr/bin/env bash
# Image collector helper: stdout only; no mounts, MMIO, module/probe or GPIO writes.
set -u

echo '=== kernel and GENI/SPI probe messages ==='
uname -r
journalctl -k -b --no-hostname --no-pager -o short-monotonic 2>&1 |
    grep -iE 'a88000|ac0000|geni|qupv3|qspi|spi.hid|firmware.*(spi|qup)|invalid proto' || :

echo '=== live DT and platform driver state ==='
python3 -B - <<'PY'
from pathlib import Path
import struct

root = Path('/sys/firmware/devicetree/base')
wrapper = root / 'soc@0/geniqup@ac0000'
engine = wrapper / 'spi@a88000'
for node in (wrapper, engine):
    print(node)
    if not node.is_dir():
        print('  ABSENT')
        continue
    for key in ('compatible', 'status', 'firmware-name', 'reg', 'clocks',
                'pinctrl-0', 'pinctrl-names', 'dmas', 'dma-names',
                'qcom,enable-gsi-dma'):
        path = node / key
        if not path.exists():
            print(f'  {key}: absent' + (' (enabled by default)' if key == 'status' else ''))
            continue
        data = path.read_bytes()
        if key in ('compatible', 'status', 'firmware-name', 'pinctrl-names', 'dma-names'):
            print(f'  {key}:', data.rstrip(b'\0').replace(b'\0', b', ').decode())
        elif data and len(data) % 4 == 0:
            print(f'  {key}:', ' '.join(f'{n:#x}' for n in struct.unpack(f'>{len(data)//4}I', data)))
        else:
            print(f'  {key}: present ({len(data)} bytes)')
for dev in sorted(Path('/sys/bus/platform/devices').glob('*a88000*')):
    print('platform:', dev.name)
    for key in ('driver', 'of_node'):
        path = dev / key
        print(f'  {key}:', path.resolve() if path.is_symlink() else 'unbound/absent')
    for key in ('power/runtime_status', 'power/runtime_active_time',
                'power/runtime_suspended_time', 'modalias'):
        path = dev / key
        try:
            print(f'  {key}:', path.read_text().strip())
        except OSError as error:
            print(f'  {key}:', error.strerror)
PY

echo '=== actual TLMM mux, direction, level, drive and pull ==='
if [[ -r /sys/kernel/debug/gpio ]]; then
    timeout 5 cat /sys/kernel/debug/gpio |
        grep -E 'gpiochip|gpio(40|41|42|43|48|49|50|51|64)([ :)]|$)' || :
else
    echo 'UNAVAILABLE: /sys/kernel/debug/gpio; collector must already mount debugfs'
fi

echo '=== pinctrl ownership and configuration ==='
for path in /sys/kernel/debug/pinctrl/*f100000*/*; do
    case ${path##*/} in
        pinmux-pins|pinconf-pins|pins)
            [[ -r $path ]] || continue
            echo "$path"
            timeout 5 cat "$path" |
                grep -E '(^pin (40|41|42|43|48|49|50|51|64) |gpio(40|41|42|43|48|49|50|51|64)([^0-9]|$))' || :
            ;;
    esac
done

echo '=== QUP clock state (observation, without resuming the device) ==='
if [[ -r /sys/kernel/debug/clk/clk_summary ]]; then
    timeout 5 cat /sys/kernel/debug/clk/clk_summary |
        grep -E 'enable_count|prepare_count|qupv3_wrap1|qupv3_wrap_1|qup_core' || :
else
    echo 'UNAVAILABLE: clk_summary'
fi

echo '=== probe deferrals ==='
if [[ -r /sys/kernel/debug/devices_deferred ]]; then
    timeout 5 cat /sys/kernel/debug/devices_deferred |
        grep -iE 'a88000|ac0000|spi|geni|qup' || :
fi

echo '=== installed firmware package and file (presence is not a loaded-state test) ==='
rpm -q qcom-firmware linux-firmware 2>&1 || :
python3 -B - <<'PY'
from pathlib import Path
import hashlib
import lzma
import struct

base = Path('/usr/lib/firmware/qcom/x1e80100/qupv3fw.elf')
for path in (base, Path(str(base) + '.xz'), Path(str(base) + '.zst')):
    if not path.is_file():
        continue
    packed = path.read_bytes()
    print(path, 'file_sha256=' + hashlib.sha256(packed).hexdigest())
    if path.suffix == '.zst':
        print('zstd payload not decoded by this dependency-free helper')
        continue
    data = lzma.decompress(packed) if path.suffix == '.xz' else packed
    print('payload_sha256=' + hashlib.sha256(data).hexdigest())
    if len(data) < 52 or data[:6] != b'\x7fELF\x01\x01':
        print('unexpected ELF format')
        continue
    offset = struct.unpack_from('<I', data, 28)[0]
    size, count = struct.unpack_from('<HH', data, 42)
    if size != 32 or offset + size * count > len(data):
        print('invalid ELF program-header bounds')
        continue
    for index in range(count):
        kind, start, _, _, length, _, _, _ = struct.unpack_from('<8I', data, offset + index * size)
        if kind != 1 or length < 28 or start + length > len(data):
            continue
        if data[start:start + 4] != b'SEFW':
            continue
        version, core = struct.unpack_from('<II', data, start + 4)
        protocol, revision = struct.unpack_from('<HH', data, start + 12)
        print(f'SEFW segment={index} offset={start:#x} version={version} '
              f'core={core:#x} protocol={protocol} firmware={revision:#x}')
    break
else:
    print('qupv3fw.elf: absent')
PY
