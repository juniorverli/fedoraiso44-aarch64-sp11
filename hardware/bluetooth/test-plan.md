# Bluetooth device evidence and acceptance

Every device boot reboots the operator's own Windows PC. Batch this with the next image test; use the default GPU-off entry, keep `/sound` and `swr0` disabled (S1), and preserve D23. No firmware-flash, Windows-partition mount, charging-limit or thermal-limit operation is part of this test.

## 1. Before boot (image owner/operator)

Refresh the M8-integrated payload for M9 per [image-request.md](image-request.md) and pass L0/L1. Without an operator file the helper must now exit 0 and log a soft skip; that proves graceful handling, not working Bluetooth. For functional acceptance provision the private Windows-observed address file **after DD-writing** the stick, at `BOOT:/EFI/sp11/bt-address`. Keep it out of all build artifacts. No additional baseline boot is needed: the helper reports its pre-change missing-option state before attempting configuration.

## 2. Exact read-only collector commands

The image hook should run:

```bash
sudo /usr/libexec/sp11-bt-collect
```

It captures the following bounded commands, with exit status retained. To collect manually without the installed wrapper, use this complete read-only block. It masks all BD addresses, address-bearing BlueZ device paths, and controller Name/Alias before output; do not run the commands unfiltered into a shared transcript.

```bash
sudo bash <<'SH'
export LC_ALL=C
mask() {
    sed -E \
        -e 's/([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}/[BDADDR MASKED]/g' \
        -e 's/dev_([[:xdigit:]]{2}_){5}[[:xdigit:]]{2}/dev_MASKED/g' \
        -e 's/^([[:space:]]*(Name|Alias):).*/\1 [MASKED]/'
}
read_state() {
    printf '\n$'; printf ' %s' "$@"; printf '\n'
    timeout -k 1 8 "$@" </dev/null 2>&1 | mask
    printf 'collector command exit: %s\n' "${PIPESTATUS[0]}"
}
read_state btmgmt --timeout 6 info
read_state btmgmt --timeout 6 --index 0 info
read_state btmgmt --timeout 6 config
read_state btmgmt --timeout 6 --index 0 config
read_state bluetoothctl --timeout 6 show
read_state rfkill --output ID,TYPE,SOFT,HARD
read_state systemctl show bluetooth.service sp11-bt-address.service \
    -p Id -p ActiveState -p SubState -p Result -p ExecMainStatus \
    -p After -p Wants -p Requires -p BindsTo
read_state journalctl -b --no-pager --no-hostname -o cat \
    -u bluetooth.service -u sp11-bt-address.service
read_state find /usr/lib/firmware/qca -maxdepth 1 \
    '(' -name 'hmtnv20.*' -o -name 'hmtbtfw20.*' ')' -printf '%f -> %l\n'
SH
```

Interpretation:

| Observation | Conclusion / next evidence |
|:--|:--|
| Unconfigured index 0 and `missing options: public-address`, no BlueZ adapter | Confirms the leading address hypothesis. Firmware setup success alone did not configure it. |
| Helper logs `controller is missing public-address`, then `controller configured with operator address`; normal info and Adapter1 appear | Address provisioning succeeded in this same boot. The helper verifies the reported address privately. |
| Missing public-address is empty, hci0 is listed normally but GNOME cannot enable it | Address is not the current blocker; inspect rfkill and BlueZ state. |
| `SOFT=yes` or `HARD=yes` | Radio is blocked; report it. Use GNOME's normal radio control for operator-directed functional testing; the collector/helper never changes it. |
| No hci0 / another controller / setup query times out | Revisit probe/setup/index selection; do not set an arbitrary adapter address. |
| Helper logs `controller remains unconfigured; skipped`, `Result=success`, `ExecMainStatus=0` | Expected when no usable boot source or explicit file exists. It supplies no fallback identity; provision the private file offline for the next planned functional test. A oneshot can be inactive/dead after successful exit. |
| Existing explicit source invalid/unreadable, or query/update/readiness error | Preserve the error and correct provisioning or investigate management failure. These are still failures; the soft skip must not hide them. |
| Daemon inactive/failed, with a normal configured hci0 | Investigate service/DBus failures independently. Capture state during the session, not only after shutdown. |

The main collector's M5 `units-state.txt` was unlabelled and taken at shutdown. M8's named component snapshot also ran during shutdown: it confirms an unconfigured index/missing option but its inactive daemon and D-Bus abort do not describe the whole session. Run the read-only capture while GNOME is active in the already-planned M9 boot. Share only masked component evidence; the full journal and boot stick remain private.

## 3. Functional acceptance (operator interaction)

After the read-only capture, use GNOME Bluetooth controls to enable the radio if desired, pair a Bluetooth mouse, move/click it and verify reconnection after a disconnect. Pair a headset and record that its device/profile connects; keep internal speakers off throughout. Record mouse/headset roles, connection success, range/dropouts over at least five minutes and any Wi-Fi coexistence issue without copying device names or addresses.

Run the masked collector again after interaction. Its `bluetoothctl show` should report a controller and the intended Powered state; management info should list BR/EDR and LE support. Paired-device details remain local; summarize results rather than pasting unmasked `bluetoothctl devices` output.

On a second already-planned boot, keep the same private source and require helper success (or valid-controller no-op). The helper's exact-address comparison establishes it matches the supplied file without logging its value. Bond retention across reboots requires persistent `/var/lib/bluetooth`; a disposable live root may legitimately forget pairings. Status `pass` requires the orchestrator to accept this device evidence.

## 4. Conditional board-ID follow-up

Only if pairing/range still fails after address and rfkill are understood, have the kernel owner verify effective `CONFIG_DYNAMIC_DEBUG=y` (or equivalent module support), then ask the image/kernel owners to add this focused dynamic-debug selector to the next planned boot (a diagnostic image change, **not** a read-only collector command):

```text
btqca.dyndbg="func qca_read_fw_board_id +p"
```

Then add this exact read-only collector command:

```bash
sudo journalctl -k -b --no-pager --no-hostname -o cat |
    sed -nE '/qca_read_fw_board_id|Reading QCA board ID failed|QCA read board ID|QCA Wrong packet|QCA Downloading qca\/hmtnv/p' |
    sed -E 's/([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}/[BDADDR MASKED]/g'
```

Expected: `qca_read_fw_board_id: bid = ...` or a named read failure. A too-short reply can still return `-EILSEQ` silently (`sources/linux/drivers/bluetooth/btqca.c:224`); absence of a board-ID line does not prove ID zero. Do not enable all Bluetooth dynamic debug, which can expose addresses. Ask firmware/kernel owners for a separately checked NVM-selection experiment only after this evidence; generic Fedora NVM is retained for the address test.

## 5. Optional automatic-source evidence, read-only

These probes do not configure the controller or establish an address by themselves. Batch Linux metadata into the next existing boot; do not request a reboot solely for this. The output contains only fixed partition-type GUIDs and MTD counts, without device names, labels, UUIDs or serials:

```bash
lsblk --list --noheadings --output TYPE,PARTTYPE
python3 - <<'PY'
from pathlib import Path
p = Path('/sys/class/mtd')
nodes = [x for x in p.glob('mtd[0-9]*') if x.name[3:].isdigit()]
print('MTD class present:', p.is_dir())
print('MTD devices exposed:', len(nodes))
print('efivarfs path present:', Path('/sys/firmware/efi/efivars').is_dir())
PY
```

Look only for DPP partition type `f97b8793-3abf-4719-896b-7c3e9b85e104`. No match does not exclude firmware-owned provisioning. An efivarfs mount is not evidence of a Bluetooth variable; no BT variable name/GUID was identified in REA. Do not dump all variables, inspect flash, use write-capable vendor IOCTLs, or mount Windows. Finding a backing store is a request for source-owner analysis, not permission to read arbitrary partitions.

When the PC is already in Windows, the following PowerShell block checks only the fallback registry schema and NVM filename. All keys are opened read-only; neither the `BdAddr` data nor an instance path is output. It does not call a vendor IOCTL, enumerate nearby radios, or change registry/firmware/radio state. It may require an elevated terminal to read the device key:

```powershell
$root = $null
try {
    $root = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey(
        'SYSTEM\CurrentControlSet\Enum\ACPI\QCOM0C6B', $false)
    if ($null -eq $root) {
        'Bluetooth ACPI registry root absent'
    } else {
        $instances = @($root.GetSubKeyNames())
        'Bluetooth ACPI instances: ' + $instances.Count
        foreach ($instance in $instances) {
            $key = $null
            try {
                $key = $root.OpenSubKey($instance + '\Device Parameters', $false)
                if ($null -eq $key) {
                    'Device Parameters absent'
                    continue
                }
                if ($key.GetValueNames() -contains 'BdAddr') {
                    'BdAddr present; type: ' + $key.GetValueKind('BdAddr')
                } else {
                    'BdAddr absent'
                }
                $nvm = $key.GetValue('UserNvmFile', $null)
                if ($nvm -is [string] -and $nvm -match '^hmtnv[0-9a-f]+\.(bin|b[0-9a-f]+)$') {
                    'UserNvmFile: ' + $nvm
                } else {
                    'UserNvmFile absent or outside expected filename schema'
                }
            } catch {
                'Bluetooth registry metadata unreadable; details withheld'
            } finally {
                if ($null -ne $key) { $key.Dispose() }
            }
        }
    }
} catch {
    'Bluetooth ACPI registry metadata unreadable; details withheld'
} finally {
    if ($null -ne $root) { $root.Dispose() }
}
```

`BdAddr` is a four-byte registry/random fallback in the traced driver, not a full factory identity. Its presence does not prove it overrode DPP/OTP, and its absence does not prove DPP worked. Use the existing image-owner Windows radio-API collector if a fresh full operator address is needed; keep that result private and provision only the written stick.
