# Linux 7.3 chain, firmware and the M5 boot (2026-10-28)

Kernel tree `sources/linux` at `v7.3` (`c03c1a14507dfaf8b856c2608f9ac216021fc222`). Device logs: `out/device-logs/m5-20261028/3f0e2cc1-a043-4c6c-9a72-0835089648d7/` (debug entry, GPU off, 234 s) and `.../0ee2fa1a-6346-400d-97e0-2589cc9b5275/` (gpu entry). Addresses are never quoted here (S5).

## 1. The chain, UART to HCI

| Step | Where | Grade |
|:--|:--|:--|
| ACPI `\_SB.BTH0` (`QCOM0C6B`) uses UART `\_SB.UR15` plus GPIO 0x74 = 116 (BT_EN) | `sources/windows/live-inventory/acpi/dsdt.dsl:68612-68650` | Verified |
| `UR15` = `QUP_1_SE_6,4W`, MMIO `0x00A98000`, interrupt `0x346` (SPI 806), 115200 initial, hardware flow control | `dsdt.dsl:51564-51600`, BTH0 `_CRS` | Verified |
| DT `uart14: serial@a98000` (`qcom,geni-uart`, SPI 806, `GCC_QUPV3_WRAP1_S6_CLK`) in the `geniqup@ac0000` wrapper `qupv3_1`; pins gpio56-59 `qup1_se6` | `hamoa.dtsi:2013-2036`, `:1492`, `:6698-6720` | Verified; matches the ACPI base and IRQ |
| Denali enables `&qupv3_1` and `&uart14`, adds the `bluetooth` child (`qcom,wcn7850-bt`, `max-speed = <3200000>`, seven PMU supplies, no `enable-gpios`, no `firmware-name`, no `local-bd-address`) | `x1-microsoft-denali.dtsi:1030-1032`, `:1244-1260` | Verified |
| WCN power: switch gpio214 `vreg_wcn_3p3`, `vreg_wcn_0p95`, `vreg_wcn_1p9`, PMU node `wcn7850-pmu` with `bt-enable` gpio116 and `wlan-enable` gpio117 | `x1-microsoft-denali.dtsi:273-307`, `:351-364`, `:1140-1146` | Verified; shared with Wi-Fi |
| `qcom_geni_serial` probe, `qcom,geni-uart` | `drivers/tty/serial/qcom_geni_serial.c:1880`, `:2203` | Verified |
| serial core registers the serdev controller; the `bluetooth` child becomes `serial0-0`-style serdev device | `drivers/tty/serdev/serdev-ttyport.c:265-291` | Verified |
| `qca_serdev_probe`: no `enable-gpios`, so `devm_pwrseq_get(dev, "bluetooth")`; on any error (including `-EPROBE_DEFER`) the pointer is set to NULL and the legacy regulator path is used | `drivers/bluetooth/hci_qca.c:2398`, `:2459-2474` | Verified |
| `pwrseq_get` returns `-EPROBE_DEFER` while no provider matched | `drivers/power/sequencing/core.c:671-696` | Verified |
| `pwrseq-qcom-wcn`: `qcom,wcn7850-pmu` data, match by the consumer `vddaon-supply` leading into the PMU `regulators` node, `bluetooth` target enables vregs, clock and BT gpio, 50 ms power-up delay | `drivers/power/sequencing/pwrseq-qcom-wcn.c:186-190`, `:257-258`, `:387-402`, `:404-440` | Verified |
| `qca_setup` then `qca_uart_setup` | `hci_qca.c:1911`, `btqca.c:749` | Verified |

## 2. Firmware names btqca builds for WCN7850

- Controller version from the chip: `0x02000200`; `rom_ver = ((soc_ver & 0xf00) >> 4) | (soc_ver & 0xf) = 0x20` (`btqca.c:772-780`). Verified by the M5 log (`QCA controller version 0x02000200`).
- Rampatch: `qca/hmtbtfw%02x.tlv` = `qca/hmtbtfw20.tlv` (`btqca.c:825-827`); a `firmware-name` second item overrides it (`:783-784`).
- Board ID: read after the rampatch for QCA2066 and WCN7850 (`btqca.c:862-863`, `qca_read_fw_board_id` `:193-235`). A failed read leaves the ID at 0, silently when the reply is shorter than 3 bytes.
- NVM: `qca_get_nvm_name_by_board("hmtnv", rom_ver 0x20, bid)` (`btqca.c:715-747`, call `:919-922`): ID 0 or 0xffff gives `qca/hmtnv20.bin`; any other gives `qca/hmtnv20.b<bid as %02x>` (for 0x3b: `qca/hmtnv20.b3b`).
- `firmware-name` first item with a dot is used as `qca/<name>` as is (`btqca.c:867-870`); without a dot it is a stem and the board suffix is added.
- A missing NVM file with an extension is retried once with the extension replaced by `.bin` (`qca_get_alt_nvm_file` `btqca.c:270-286`, retry `:565-575`). A missing rampatch has no fallback.
- Fedora `atheros-firmware-20261019-1.fc44` (in the M5 ISO, `linux-firmware` 20261019) ships `qca/hmtbtfw20.tlv.xz` (sha256 of the xz `9668138d...`), `hmtnv20.bin.xz`, `hmtnv20.b10f.xz`, `hmtnv20.b112.xz` (link to b10f), `hmtnv20.b201.xz`, `hmtnv20.b202.xz`. No `b3b`, `b105`, `b107`, `b108`. Source: `dnf repoquery -l atheros-firmware` and the RPM payload in the f44 container, 2026-10-28. The kernel has `CONFIG_FW_LOADER_COMPRESS_XZ=y` (`kernel/config/sp11.config`) and Fedora's config has ZSTD too.

## 3. What the M5 boot shows (debug entry `3f0e2cc1`)

`dmesg.txt`, UTC 18:16 (masked, only decisive lines):

- `a98000.serial: ttyHS1 ... is a MSM` (line 582): the GENI UART probed, no `Invalid proto` error was logged. Inference: firmware had left the engine usable; the actor that programmed it is not established by this log.
- `pwrseq-qcom_wcn wcn7850-pmu: supply vddio1p2 not found, using dummy regulator` (line 1008): the Denali PMU node has no `vddio1p2`. Inference: not the immediate setup blocker, because setup later completes; this does not validate all supply behavior.
- `Bluetooth: HCI UART protocol QCA registered` (2087), `hci0: setting up wcn7850` (2090), `QCA Product ID 0x00000019`, `SOC Version 0x40170200`, `ROM Version 0x00000200`, `Patch Version 0x000043fb`, `controller version 0x02000200` (2092-2096).
- `QCA Downloading qca/hmtbtfw20.tlv` (2097), then `QCA Downloading qca/hmtnv20.bin` (2133) **only once**: no `b<id>` request preceded it, so the controller reported board ID 0 or 0xffff (or a reply btqca discarded silently). The generic Fedora NVM loaded.
- `QCA FW build version: BTFW.HAMILTON.2.0.1-00349-WOS_PATCHZ-2`, `QCA setup on UART is completed`, `HFP non-HCI data transport is supported`, `AOSP extensions version v0.98` (2138-2142). The second boot (`0ee2fa1a`) is identical.
- `bnep` loads at 25.5 s (2134-2136), so userspace BlueZ was already running when hci0 finished setup (inference: BNEP is loaded by bluetoothd).
- `firmware-failures.txt` is empty; `units-failed.txt` is empty. Modules `hci_uart`, `btqca`, `bluetooth`, `pwrseq_qcom_wcn` are loaded from the real root (nothing is needed in the initramfs).

Correction after Codex continuation (D24): the journal **does** contain service and rfkill evidence. Verified: `journal.txt:64053` identifies Bluetooth daemon 5.87; `:65030-65033` starts `bluetooth.service` successfully at 28.69 s; `:65506` initializes management interface 1.23; `:65518` reports READY=1. At shutdown `:159159-159189` terminates it normally and `:159818-159825` records exit 0/SUCCESS. The missing daemon in the shutdown process snapshot is not a failure. `:62138-62140` shows Bluetooth rfkill creation and saved state 0 (soft-unblocked at creation; see below), so rfkill must also be collected explicitly. No management configuration/address capture is present.

`units-state.txt` contains six **unlabelled** lines (four `inactive`, `deactivating`, `graphical.target`); it does not name Bluetooth and cannot diagnose its service. `units-failed.txt` is empty, but this alone never proves an adapter exists. `pkgs.txt:116` pins `bluez-5.87+1.git8750129efca8-1.fc44.aarch64`.

Systemd saves `event->soft` directly; 0 means initially **soft-unblocked**, not blocked ([systemd v259 `src/rfkill/rfkill.c:138-145`](https://raw.githubusercontent.com/systemd/systemd/v259/src/rfkill/rfkill.c)). This does not establish the later soft/hard state in GNOME. The collector therefore reads both without unblocking anything. The AOSP lines also occur for unconfigured controllers (`hci_sync.c:5383-5385`). Firmware setup and a healthy daemon do not prove address validity. **Missing public address remains a Hypothesis**, with later rfkill state still TBD; the next batched collector and helper journal resolve both.

SHA-256 of the private inputs (no raw content copied):

| File in GPU-off boot directory | SHA-256 |
|:--|:--|
| `dmesg.txt` | `2afe5df265e037dddb773bfba792a3b3ef53f9b6df869e66c1afed2489940382` |
| `journal.txt` | `28fd8fdf72a86c2d02313e826479c8eed4b241e08b878eea42e7e490a34e9901` |
| `units-state.txt` | `356de7decdf979bcd1f8f4612720e3c5d6c8b6b20d835f3f91b0aec7962a7c44` |
| `pkgs.txt` | `1169526393f456b5a42f752f9903089336792ec25f1e10b185004da50a25df79` |

## 4. The address path in 7.3

- `qca_check_bdaddr` reads the controller address; if it equals the address tag in the loaded NVM it sets `HCI_QUIRK_USE_BDADDR_PROPERTY` (`btqca.c:683-711`). The checked Windows generic/`b3b` and Fedora generic/`b10f` NVM files carry tag 2 with the same 6-byte default (`[NVM default masked]`; all four contain 95 tags, re-parsed 2026-10-28 using the layout in `btqca.h:134-145`).
- `hci_dev_setup_sync` then looks for `local-bd-address` on the parent (`hci_sync.c:3745-3760`, `:5256-5320`). None in the DT, so **if the default-address quirk is set**, the controller is flagged `HCI_UNCONFIGURED`. The quirk was not captured in M5.
- Unconfigured controllers are left out of `MGMT_OP_READ_INDEX_LIST` (`net/bluetooth/mgmt.c:443`); `hci_power_on` powers them off again (`hci_core.c:907-935`). BlueZ at the exact Fedora package commit uses this list and normal index-added events, with no unconfigured-controller provisioning in `src/adapter.c:10466-10474` ([upstream source](https://raw.githubusercontent.com/bluez/bluez/8750129efca8/src/adapter.c)). Thus an unconfigured hci0 does not become an `org.bluez.Adapter1` for GNOME (Verified source chain; applicability to this boot remains Hypothesis).
- `btmgmt public-addr` maps to `set_public_address` (`mgmt.c:8376-8426`): rejected when powered, all-zero, or unsupported; it stores the address in host RAM, clears `HCI_UNCONFIGURED` if `is_configured()` (`mgmt.c:606-618`), and re-queues `power_on`, which writes the address with `qca_set_bdaddr` (`btqca.c:1005-1025`, `hci_sync.c:5358`). `HCI_QUIRK_NON_PERSISTENT_SETUP` re-runs the firmware download on that power-on (`hci_qca.c:2557`).
- `mgmt` rejects commands while the index is in `HCI_SETUP`, so a boot unit must retry `btmgmt config` for a few seconds (`sources/linux/net/bluetooth/hci_sock.c:1694-1707`; the helper retries six bounded queries and checks the reply fields, not merely the exit code).
