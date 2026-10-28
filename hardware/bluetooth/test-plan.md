# Bluetooth device evidence and acceptance

Every device boot reboots the operator's own Windows PC. Batch this with the next image test; use the default GPU-off entry, keep `/sound` and `swr0` disabled (S1), and preserve D23. No firmware-flash, Windows-partition mount, charging-limit or thermal-limit operation is part of this test.

## 1. Before boot (image owner/operator)

Integrate [image-request.md](image-request.md) and pass L0/L1. Provision the private Windows-observed address file **after DD-writing** the stick, at `BOOT:/EFI/sp11/bt-address`. Keep it out of all build artifacts. No additional baseline boot is needed: the helper reports its pre-change missing-option state before attempting configuration.

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
    -p Id -p ActiveState -p SubState -p Result -p ExecMainStatus
read_state journalctl -b --no-pager --no-hostname -o cat \
    -u bluetooth.service -u sp11-bt-address.service
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
| Helper says source invalid/missing | Correct local provisioning offline, then include the fix in the next planned boot. It deliberately supplies no fallback identity. |
| Daemon inactive/failed, with a normal configured hci0 | Investigate service/DBus failures independently. Capture state during the session, not only after shutdown. |

The main collector's M5 `units-state.txt` was unlabelled and taken at shutdown. It cannot replace the named service properties above. Share only masked component evidence; the full journal and boot stick remain private.

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
