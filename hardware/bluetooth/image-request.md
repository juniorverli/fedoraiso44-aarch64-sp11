# Image request: configure WCN7850 from a local boot-time address file

Owner: image worker. Status: requested, not integrated. Worker implementation and rationale are in [README.md](README.md) and [address design](evidence/2026-10-28-address-design.md). This request changes userspace only; keep the M5 sound/GPU defaults and D23 policy.

## Payload and activation

Use existing Fedora image overlay conventions; no new package format or kernel patch is required.

| Component source | Image destination | Mode |
|:--|:--|:--|
| `hardware/bluetooth/userspace/sp11-bt-address` | `/usr/libexec/sp11-bt-address` | 0755 |
| `hardware/bluetooth/userspace/sp11-bt-address.service` | `/usr/lib/systemd/system/sp11-bt-address.service` | 0644 |
| `hardware/bluetooth/userspace/sp11-bt-collect` | `/usr/libexec/sp11-bt-collect` | 0755 |

Ensure Fedora `bluez` (provides both `btmgmt` and `bluetoothctl`), `util-linux` (findmnt/blkid/mount/rfkill), bash, coreutils, grep and sed are installed. Retain Fedora's Bluetooth service/preset policy. Add `enable sp11-bt-address.service` to the existing SP11 preset: first-boot `preset-all` must preserve `sys-subsystem-bluetooth-devices-hci0.device.wants/sp11-bt-address.service`. The supplied unit is pulled in by hci0 creation, bounded to 90 seconds, independent of bluetoothd startup. It validates WCN7850 compatibility and handles asynchronous firmware setup. If another adapter occupies hci0 it declines to change it and logs that fact; extend index selection only with evidence, not by changing every radio.

Install `/etc/sp11-log-collector.d/bluetooth.sh` with this single command (the existing collector sources hooks into `extra-bluetooth.txt`):

```bash
timeout -k 1 80 /usr/libexec/sp11-bt-collect
```

The commands only read state. Addresses and BlueZ device-path addresses are masked, as are controller Name/Alias. Keep their original exit/status text so missing/unconfigured hci0 differs from tool/daemon failure. The main `journal.txt` remains private; Bluetooth's shareable component evidence should use this masked capture.

## Address stays out of the image

Do **not** read `BT_MAC` during a build; do not stage `/etc/sp11/bt-address`, `EFI/sp11/bt-address`, registry exports or `sp11-mac.conf` in any rootfs, RPM, ISO, DTB or intermediate archive. L0 must check both rootfs and embedded ESP for absence of those address inputs. Helpers contain only syntax/sentinel checks, never a unit identity. Leave Fedora firmware unchanged for the first test.

After the operator DD-writes the ISO, the operator supplies a plain text file at `BOOT:/EFI/sp11/bt-address`: exactly the Windows-observed Bluetooth address in colon notation, optional final newline/CRLF. This personalizes only that local stick after the distributable image is complete. No address should be pasted into a shell command, task message or git file.

The existing private capture `sources/windows/live-inventory/sp11-mac.conf` can be the source. The following **offline provisioning example** is for the operator/image owner after the correct USB ESP is already mounted; `/path/to/usb-esp` is a placeholder to replace after checking the boot stick. This writes only a local file; it is not a device collector and must never be run by the ISO build:

```bash
python3 - sources/windows/live-inventory/sp11-mac.conf /path/to/usb-esp/EFI/sp11/bt-address <<'PY'
import os
from pathlib import Path
import re
import sys
source, target = map(Path, sys.argv[1:])
values = [line.split('=', 1)[1].strip() for line in source.read_text().splitlines()
          if line.startswith('BT_MAC=')]
if len(values) != 1 or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', values[0]):
    raise SystemExit('private capture has no single valid BT_MAC')
value = values[0].upper()
if value.replace(':', '') in ('000000000000', 'FFFFFFFFFFFF', '000000005AAD'):
    raise SystemExit('private capture contains an unusable sentinel')
target.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(value + '\n')
print('local boot-stick Bluetooth file provisioned; value withheld')
PY
```

Do not mount the Windows partition to obtain this file. If a new Windows capture is needed, obtain a targeted read-only export while Windows is running, then convert it locally; no exact registry address key/type is established yet. On installed Fedora, the operator may instead provision root-owned mode 0600 `/etc/sp11/bt-address` locally after installation. It must not be generated into the installation media.

## L0/L1 and next L3

1. Verify payload, dependencies, unit syntax, preset and resulting wants symlink; run the component's Fedora checks. Confirm normal Fedora Bluetooth startup remains intact.
2. Check the unpersonalized rootfs and ESP contain no address file/capture; ensure no raw-address logging or derived-address fallback was added.
3. L1 without WCN7850 must not fail a boot because of this service. With a fake boot-ISO/FAT sibling setup, validate only the actual boot disk's ESP is selected and read-only, an unrelated `BOOT` partition is ignored, and the private mount is cleaned up. Unit tests cover these decisions with mocked utilities; real FAT/systemd activation remains an image-level check.
4. In the next already-planned GPU-off/speakers-off device boot, include the private file, collect the helper's missing-option/success messages and `extra-bluetooth.txt`, then follow [test-plan.md](test-plan.md). Do not schedule an extra reboot merely to get baseline status: the helper logs the pre-change missing option in the same boot.
5. If the helper reports no file, invalid query, another controller or an unexpected option, preserve that evidence. Do not invent an address, force power-off/unblock, replace NVM or enable audio as a fallback.
