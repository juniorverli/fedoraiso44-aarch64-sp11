# Wi-Fi test plan

Every device test reboots the operator's PC, so each ISO tests the items below in one boot, with the collector doing the reading. The device has no working input, so nothing here asks the operator to type. Collector output stays in `out/device-logs/`; never quote a MAC, a serial or an SSID from it (S5). The core collector's `lspci.txt` contains the endpoint's Device Serial Number line.

## Boot A: decide the rfkill problem (next ISO)

ISO contents: kernel DTB with patch 0001 (K1), `CONFIG_ATH12K_DEBUG=y` (K2), collector drop-ins `wifi.sh` and `wifi-unblock-probe.sh` (I1, I2), `sp11-rfkill-events.service` (I3), `options ath12k debug_mask=0x30` (I4). No firmware change.

Collector commands (all in `collector/wifi.sh`, output `extra-wifi.txt`, one snapshot per collector cycle):

| Section | Commands | Decides |
|:--|:--|:--|
| 1 | `lsmod`, `/sys/module/ath12k/parameters/*`, `/proc/config.gz` | modules loaded, `debug_mask` active, `CONFIG_ATH12K_DEBUG` |
| 2 | `1c08000.pcie`, `1c0e000.phy`, `wcn7850-pmu` driver and `waiting_for_supplier`; pwrctrl/pwrseq driver binding; `/sys/class/pwrseq`; `devices_deferred` filtered | chain bound, nothing stuck in defer |
| 3 | `lspci -nnk -d 17cb:`, `lspci -tv`, `/sys/bus/pci/devices/0004:*` speed, width, runtime status, `lspci -vv` root port and endpoint (`LnkCap`, `LnkSta`, `DevSta`, `UESta`, `CESta`), AER counters | PCIe link state and errors |
| 4 | `/sys/kernel/debug/gpio` and `pinmux-pins` for 116, 117, 146, 147, 148, 214; WCN and PHY regulators; `pm_genpd_summary`; `clk_summary` | patch 0001 effect (146/147/148 claimed), rails |
| 5 | `dmesg` filtered for ath12k, pwrctrl, pwrseq, mhi, qrtr, cfg80211, rfkill, firmware | board name tried, board API used, QMI/MHI errors, rfkill WMI event |
| 6 | `ls`, `sha256sum` of the public ath12k blobs; `rpm -q`; `dmidecode -t 248` | firmware version actually installed, SMBIOS variant |
| 7 | `rfkill list`, `/sys/class/rfkill/*`, `iw dev`, `iw reg get`, `iw phy`, `nmcli dev`, `nmcli radio`, `nmcli general`, NetworkManager and wpa_supplicant journal, `ethtool -i`, MAC hash and assignment type | who is blocking, NM state, regulatory domain, bands |
| 8 | once per boot at uptime >= 60 s: `iw dev wlP4p1s0 scan`, counts per band only | radio works (needs the radio unblocked; see the probe) |
| probe | at uptime >= 90 s: `rfkill unblock wifi`, `nmcli radio wifi on`, 8 s wait, `rfkill`, `nmcli dev`, scan counts, dmesg tail | whether a plain unblock makes Wi-Fi work |

Expected, in order of what each outcome means:

1. **Probe works** (`rfkill` shows `Soft blocked: yes` before, `no` after; `nmcli dev` goes from `unavailable` to `disconnected`; scan counts above 0): the hardware path is fine. Read the `rfkill event` journal lines to see who set the soft block and when (Q4). The fix is then a userspace or input-event issue: an image change (a unit that unblocks, or masking the offender), not a kernel patch.
2. **Probe does not unblock** (`rfkill` shows `Hard blocked: yes` or the state returns to blocked): read dmesg for `wmi tlv rfkill state change … radio_state` and `mac rfkill_pin 48` (Q5). `radio_state 0` confirms the firmware-GPIO hypothesis; next step is an ath12k patch that skips `ath12k_core_rfkill_config()` for this board (the Windows `_DSM` leaves the rfkill bit clear).
3. **No rfkill problem visible** (`soft` and `hard` both `no` at the first snapshot, NM still `unavailable`): read the NM and wpa_supplicant journal lines of section 7; suspect a supplicant or regulatory-domain error.

Also read in Boot A:

- `lspci`/pinctrl: 146, 147, 148 claimed by `1c08000.pcie`; link `Gen3 x2`; endpoint `0004:01:00.0` bound. If the link fails to train, the DTB with patch 0001 is the suspect: boot the previous DTB (M5) to compare.
- `board name` and `using board api` lines (needs `debug_mask`); `board_id 0xff`; no `failed to fetch board data`.
- `check-mac.sh extra-wifi.txt` on the host: MATCH (Q3).
- `Direct firmware load` failures for `ath12k/` in `firmware-failures.txt`: none.

## Boot B: functional (after Boot A fixed the rfkill problem)

1. `nmcli dev wifi list` count (no SSIDs in the log) per band; a connection to a known test AP is made by the operator's saved profile only if one is provisioned in the ISO (TBD with image); otherwise acceptance 3 waits for a working input device.
2. `iw dev wlP4p1s0 link`, `iw dev wlP4p1s0 station dump` (signal, bitrate; masked), `ip -br addr`.
3. Throughput: `iperf3 -c <host on the same AP>` 30 s down and up, once the lab host exists (TBD); compare with Windows on the same AP.
4. `iw reg set <CC>` then `iw reg get`; confirm channel list changes (`iw phy` frequencies).
5. Coexistence: Bluetooth scan and Wi-Fi scan together (bluetooth dossier).

## Boot C: board-data parity (only after A and B pass)

Stage the derived `board-2.bin` (F2). Expected in dmesg: `boot found match … qmi-board-id=255` and the payload from `bdwlan.elf`; `chip_id … board_id 0xff` unchanged; no QMI BDF error. Compare scan counts, RSSI at a fixed spot and throughput with Boot B. A firmware rejection (`qmi failed to load bdf file`) means revert to Fedora's file (remove the `updates/` file).

## Suspend (phase 4)

`rtcwake`/`systemctl suspend` then `ath12k` log: resume without `failed to power up hif during resume` and link back up; PERST# and WAKE# from patch 0001 are required for this.
