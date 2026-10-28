# wifi

## 1. Summary

Qualcomm WCN7850 (FastConnect 7800) Wi-Fi 7 on PCIe4, driven by `ath12k` through `pwrseq-qcom-wcn`. On the M5 ISO the hardware already comes up (PCIe Gen3 x2 link, firmware ready, netdev `wlP4p1s0`), but NetworkManager reports `Wi-Fi disabled by radio killswitch` and never scans; the cause of that block is not yet known. Status: `designed` (one DT patch builds and validates; nothing here has been run on the device).

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `PCI\VEN_17CB&DEV_1107&SUBSYS_110717CB&REV_01`, location PCI segment 4 bus 1 | Verified | `sources/windows/live-inventory/wlan/registry-wcn7850.txt` |
| Windows device | `ACPI\QCOM0CD5` (WLAN thermal mitigation), `ACPI\QCOM0CFC` (WLAN limits policy) | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Linux device | `0004:01:00.0 [17cb:1107]` class 0x028000 behind root port `0004:00:00.0 [17cb:0111]`, link Gen3 x2 | Verified | M5 device log, `evidence/2026-10-28-m5-device-log.md` facts 1-2 |
| Chip report | `chip_id 0x2 chip_family 0x4 board_id 0xff soc_id 0x40170200`, firmware `WLAN.HMT.1.1.c7-00108` | Verified | same, facts 6-7 |
| PCIe4 PERST# | TLMM 146 (`\_SB.QPPX` GpioIo index 4 of 3..7 = 143, 146, 149, 152, 155 for PCI3..PCI7) | Verified (ACPI list), Inference (that the entry is PERST# of PCI4) | `sources/windows/live-inventory/acpi/dsdt.dsl:56779-56870`; same pins as `x1-crd.dtsi:1268` |
| PCIe4 WAKE# | TLMM 148 | Inference (CRD, Surface Laptop 7 `x1e80100-microsoft-romulus.dtsi:1129`); Windows names the wake line `GIO0` pin `0x0240` (`dsdt.dsl:59121`), a different numbering | |
| PCIe4 CLKREQ# | TLMM 147, function `pcie4_clk` | Inference (`pcie4_default`, `x1-microsoft-denali.dtsi:1147`) | |
| WCN enable pins | WLAN_EN TLMM 117, BT_EN TLMM 116, 3.3 V switch TLMM 214 | Verified (claimed by `wcn7850-pmu`, `regulator-wcn-3p3` in the device log, `pinctrl-pins.txt`) | `x1-microsoft-denali.dtsi:273-283`, `:351-364` |
| Rails | `VREG_WCN_3P3` 3.3 V, `VREG_WCN_0P95`, `VREG_WCN_1P9` (fixed, from 3P3), `vreg_l15b_1p8` (VDDIO), PHY `vreg_l3i_0p8` 880 mV and `vreg_l3e_1p2` 1.2 V | Verified (device log, `regulator_summary.txt`) | `x1-microsoft-denali.dtsi:273-306`, `:942-945` |
| Firmware-side rfkill | the driver programs WCN GPIO 48, radio-on level 1, as hardware rfkill (`wifi7/hw.c:508-510`); the Surface ACPI `_DSM` function 2 returns 0x60 (rfkill bit 2 clear, 11be-disable bit 0 clear) | Verified (code, AML); whether the firmware reports radio-off because of it: TBD | `dsdt.dsl:59196`, `acpi.h:59-60`, `acpi.c:385-388` |

### MAC address

- ath12k takes the MAC address from the firmware's WMI ready event, i.e. from the chip's own OTP (`sources/linux/drivers/net/wireless/ath/ath12k/wmi.c:7066`). It reads no DT or nvmem property (no `of_get_mac_address` in `drivers/net/wireless/ath/ath12k/`). Grade: Verified (source).
- So nothing has to be copied for Wi-Fi, provided the OTP holds the factory address. The collector prints only a hash prefix of the station address (`mac_sha256_16`) and its assignment type; `hardware/wifi/tools/check-mac.sh <extra-wifi.txt>` compares the hash with `WIFI_MAC` in `sources/windows/live-inventory/sp11-mac.conf` locally and prints MATCH or DIFFERENT, never an address.
- NetworkManager sets a random MAC for scanning (`device (wlP4p1s0): set-hw-addr: set MAC address … (scanning)`, journal line 68678). That is NetworkManager's `22-wifi-mac-addr.conf` default and is not a hardware address.
- Only if the hash differs, or the type is not `0` (permanent), set the address from userspace on the ISO (NetworkManager `cloned-mac-address`), never in the shared DTB.

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcwlanhmt8380` (1.0.4374.1300, 07/14/2025, active `oem116.inf`) | NDIS miniport `qcwlanhmt8380.sys` (service `qcwlan`) for the WCN7850; binds through the generic `PCI\VEN_17CB&DEV_1107` line to `QcWlan_BERYLLIUM`. Carries: firmware `wlanfw20.mbn` (Linux `amss.bin`), `phy_ucode20.elf` (Linux `m3.bin`; byte-identical to Fedora 20260309 `m3.bin`), board data `bdwlan.elf` plus ten `bdwlan[01].eNN` files selected by QMI board id, `regdb.bin`, `Data20.msc` (firmware log-string dictionary, not needed), `qdss_trace_config_v*.cfg` (debug), and 14 `bdwlan_wcn785x_2p0_ncm*` OEM files for other subsystem IDs. See `evidence/2026-10-28-windows-board-selection.md` |
| `qcwlanhmt_ext8380` (1.0.4374.1300) | Extension INF for `ACPI\QCOM0CD5` "Qualcomm Wlan Thermal Mitigation Device": registry `QMIDeviceName=wlan_tmd`, `QMIInstanceID=0x10`; its commented MapTable maps performance percent to mitigation level (30 to 3, 60 to 2, 99 to 1, 100 to 0). Linux counterpart: the ath12k thermal cooling device (`thermal.c`), policy belongs to `power-thermal` |
| `surfacesarmanager` (3.1193.4.0) | UMDF "Surface Radio Monitor": SAR policy (trigger/action tables read from UEFI variables, motion-SAR sensor on the ADSP) and the actuator calls into the WLAN and Bluetooth drivers. The UEFI variables are not readable from the dump (`live-inventory/sar/sar-phase2-readonly.txt`), no DPP partition on the disk. Not reproducible on Linux now (Q2) |
| `surfaceradiotelemetrydriver` (1.10.4.0) | UMDF telemetry (ETW provider, consent), no radio function |

## 4. Linux 7.3

Dependency chain, in probe order (all `sources/linux/...`):

1. **PCIe4 controller** `qcom,pcie-x1e80100`: node `arch/arm64/boot/dts/qcom/hamoa.dtsi:3695-3797` (2 lanes, `linux,pci-domain = 4`, root port `pcie4_port0` at `:3786`), driver table `drivers/pci/controller/dwc/pcie-qcom.c:2493`. `qcom_pcie_host_init()` (`:1385-1432`): `perst_assert`, clocks/resets (`ops->init`), PHY power on, `pci_pwrctrl_create_devices`, `pci_pwrctrl_power_on_devices`, then `perst_deassert`. PERST# is taken from `reset-gpios` of the root port node (`qcom_pcie_parse_perst()`, `:1957-2018`); without that property the port has an empty PERST# list and Linux never toggles the line. Board: `x1-microsoft-denali.dtsi:937-939` (`&pcie4`, only `status`), `:948-963`.
2. **PCIe4 PHY** `qcom,x1e80100-qmp-gen3x2-pcie-phy`: node `hamoa.dtsi:3799-3836`, driver `drivers/phy/qualcomm/phy-qcom-qmp-pcie.c:6493` (module `phy-qcom-qmp-pcie`). Supplies `vreg_l3i_0p8` and `vreg_l3e_1p2` (`x1-microsoft-denali.dtsi:941-946`), same as `x1-crd.dtsi:1272-1277`.
3. **WCN7850 power sequencer** `qcom,wcn7850-pmu`: node `x1-microsoft-denali.dtsi:351-408` (rails `vreg_pmu_*` ldo0-ldo9, `wlan-enable-gpios` 117, `bt-enable-gpios` 116, pinctrl `wcn_wlan_bt_en` at `:1140`), fixed regulators `:273-306` (3.3 V switch on TLMM 214, pinctrl `wcn_sw_en` at `:1214`). Driver `drivers/power/sequencing/pwrseq-qcom-wcn.c` (match `:562`, probe `:457`, WCN7850 data `:387-402`: 50 ms power-up delay, regulators `vdd vddio vddio1p2 vddaon vdddig vddrfa1p2 vddrfa1p8`). `vddio1p2` is not in the node, so it is a dummy regulator (device log fact 3; the Surface Laptop 7 node is identical).
4. **PCI power control** `pci-pwrctrl-pwrseq` binds the DT child `wifi@0` (`pci17cb,1107`, `x1-microsoft-denali.dtsi:949-962`, nine `vdd*-supply` from the `vreg_pmu_*` rails) and requests the `wlan` target (`drivers/pci/pwrctrl/pci-pwrctrl-pwrseq.c:122`). Until it is bound, `pci_pwrctrl_power_on_devices()` returns `-EPROBE_DEFER` (`drivers/pci/pwrctrl/core.c:276`), so the controller defers and retries; both pwrctrl and pwrseq are modules loaded from the root file system, which is why `pcie4` probes about 25 times in the M5 log. Harmless; nothing has to be in the initramfs.
5. **ath12k PCI probe** `drivers/net/wireless/ath/ath12k/wifi7/pci.c` (id table `:36`, WCN7850 branch `:134`, probe `:91`), MHI boot (`mhi.c`), QMI over QRTR-MHI (`qmi.c`: target capability `:2886-2965`, BDF `:3078-3130`, calls `:3806-3819`).
6. **Firmware requests** (`ab->hw_params->fw.dir = "WCN7850/hw2.0"`, `wifi7/hw.c:454`): `amss.bin` (`mhi.c:238`), `m3.bin` (`qmi.c:3213`), `board-2.bin` then `board.bin` (`core.c:524-580`), regdb from `board-2.bin` (`core.c:583-625`). `board_size` 256 KiB.
7. **Board name** (`core.c:221-263`): `bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=1107,qmi-chip-id=2,qmi-board-id=<id>`; `<id>` is 255 (`0xff`) on this unit. The `variant=` suffix comes only from SMBIOS type 0xF8 or an ACPI string (`core.c:696-790`, `acpi.c:487`). `qcom,calibration-variant` and `qcom,ath12k-calibration-variant` are not read by ath12k 7.3 and are not allowed by the `pci17cb,1107` binding (`Documentation/devicetree/bindings/net/wireless/qcom,ath12k.yaml`, `additionalProperties: false`): **no DT string is needed or possible**.
8. **Firmware in Fedora** (checked 2026-10-28 in the `fedora:44` container, aarch64): `atheros-firmware` 20260309-1.fc44 and 20261019-1.fc44 (updates) ship `ath12k/WCN7850/hw2.0/{amss.bin,m3.bin,board-2.bin}.xz` and `ncm865/`; no `board.bin`. Only 20261019 has the board name for id 255. The M5 ISO has 20261019.
9. **Config** (release `.config` of `7.3.0-65.sp11.3.fc44`, `out/build/kernel/rpmbuild/BUILD/…/.config`): `ATH12K=m`, `ATH12K_AHB=y`, `MAC80211=m`, `CFG80211=m`, `PCIE_QCOM=y`, `HAVE_PWRCTRL=y`, `PCI_PWRCTRL=y`, `PCI_PWRCTRL_PWRSEQ=m`, `POWER_SEQUENCING=y`, `POWER_SEQUENCING_QCOM_WCN=m`, `PHY_QCOM_QMP_PCIE=m`, `QCOM_PD_MAPPER=m` (not needed by WCN7850; present), `QRTR=m`, `QRTR_MHI=m`, `MHI_BUS=m`, `QCOM_QMI_HELPERS=m`, `PINCTRL_X1E80100=y`, `CLK_X1E80100_GCC=y`, `CLK_X1E80100_TCSRCC=y`, `INTERCONNECT_QCOM_X1E80100=y`, `REGULATOR_QCOM_RPMH=y`, `REGULATOR_FIXED_VOLTAGE=y`, `RFKILL=m`, `RFKILL_INPUT=y`, `FW_LOADER_COMPRESS_XZ=y`. All present. Missing: `ATH12K_DEBUG` (not set; without it `ath12k.debug_mask` prints nothing, including the board name tried): request K2. The modules are in the image (`ath12k.ko.xz`, `ath12k_wifi7.ko.xz`, `pwrseq-qcom-wcn`, `pci-pwrctrl-pwrseq`, QMP PCIe PHY, `qrtr`, `qrtr-mhi`, `mhi`, `qmi_helpers`). The initramfs needs only the PHY (already there for NVMe); Wi-Fi modules load after switch-root.
10. **Native coverage:** `full` for the chain; the DT lacks PERST#, WAKE# and the `pcie4_default` consumer (device log fact 11). Patch below.

Patch set (`patches/`, base `v7.3`, kernel worktree `out/linux/wifi`, branch `w/wifi`):

| Patch | Content | Checks |
|:--|:--|:--|
| `0001-arm64-dts-qcom-denali-wire-pcie4-perst-wake.patch` | `&pcie4` gets `pinctrl-0 = <&pcie4_default>`; `&pcie4_port0` gets `reset-gpios = <&tlmm 146 …>` and `wake-gpios = <&tlmm 148 …>` | `scripts/kernel-dev.sh --check wifi dtbs`: DTB builds, dt-schema (`CHECK_DTBS`) clean, no new warning; `dtc` dump shows `reset-gpios = <… 0x92 0x01>`, `wake-gpios = <… 0x94 0x01>`; applies cleanly on top of display-lcd 0001-0003 (`git apply --check` in `out/linux/m3`); `checkpatch.pl --strict`: 0 warnings, 0 checks, 1 error "Missing Signed-off-by" (by project rule none is added) |

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Wi-Fi shows `disabled by radio killswitch` and never scans (device log facts 9-10) | Find the blocker with the collector (`rfkill list`, `/sys/class/rfkill`, rfkill event log, `ath12k.debug_mask`) and the unblock probe (Q4). Fix depends on the finding: userspace (rfkill state), or an ath12k change for the firmware rfkill GPIO (Q5) |
| PERST#, WAKE#, `pcie4_default` not described | Patch 0001 (K1). Needed for a defined power-up sequence, recovery and suspend; the link already trained in M5 without it |
| Board data: Linux uses Fedora's generic id-255 entry, Windows loads `bdwlan.elf` | Derived `board-2.bin` (`tools/wifi-board2.py`), held until basic connectivity works (F2). `atheros-firmware` must stay at 20261019 or later (F1) |
| `qmi dma allocation failed … will try later with small size` | Benign fallback (Verified in `qmi.c:2653-2666`); watch for `memory allocation failure` in the next log |
| SAR / TAS / regulatory power tables | Not reproducible now: tables are in UEFI variables and DPP, unreadable offline (Q2). Linux enforces the regdb CTL limits only. The board data CTL tables and `wireless-regdb` bound the power (Inference); do not call the result "within Windows SAR limits" |
| Thermal mitigation (`wlan_tmd`) | `power-thermal` dossier; ath12k registers its own cooling device |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which board data does ath12k use here, and is it what Windows uses? | Linux: Verified (id 255, Fedora generic entry `d4f92e9f11bc…`). Windows: Inference (strong) `bdwlan.elf` from board id 0xff in the REA'd name builder; DPP override TBD | Windows side: a DPP read on the Windows PC (operator); Linux side: `dmesg` with `debug_mask=0x30` prints the name and "using board api" |
| Q2 | SAR and regulatory power tables | TBD | `surfacesarmanager` tables are UEFI variables (needs an elevated read on Windows, read-only); ACPI has no BIOS-SAR/TAS function (`WLN._DSM` implements only 0, 2, 7: `dsdt.dsl:59169-59200`) |
| Q3 | Is the factory MAC in the OTP? | TBD | `tools/check-mac.sh` on the first collector output |
| Q4 | What soft-blocks the Wi-Fi radio before NetworkManager starts? | TBD | `rfkill list` and `/sys/class/rfkill/*/{soft,hard}` at the first snapshot; `rfkill event` log from boot; `wifi-unblock-probe` result |
| Q5 | Does the firmware report radio-off because the host configures hardware rfkill on WCN GPIO 48? | Hypothesis | dmesg with `debug_mask=0x30`: `mac rfkill_pin 48 …` and `wmi tlv rfkill state change … radio_state N`. If `radio_state 0`: ath12k change to skip `ath12k_core_rfkill_config()` on this board, as the Windows `_DSM` does (rfkill bit clear) |
| Q6 | Does the firmware allocate its host memory without CMA trouble (`qmi dma allocation failed`)? | Inference (benign) | next log has no `memory allocation failure` |
| Q7 | Does SMBIOS type 0xF8 carry a BDF variant on this unit? | Hypothesis (no) | `dmidecode -t 248` (collector section 6) |
| Q8 | Are GPIOs 146 and 148 the PERST# and WAKE# of PCIe4 on this board? | Inference | cross-check (protocol 5.1) and the next log: pinctrl shows 146/147/148 claimed by `1c08000.pcie`, link up after a PERST# cycle |

## 7. Acceptance

1. `lspci -nnk` shows `0004:01:00.0 [17cb:1107]` bound to `ath12k_wifi7_pci`; link Gen3 x2 (PCIe4 PERST# and WAKE# claimed by the controller in `pinctrl-pins.txt`).
2. `rfkill list` shows the Wi-Fi radio `Soft blocked: no`, `Hard blocked: no` without user action; `nmcli dev` shows `wlP4p1s0 wifi disconnected` (or `connected`), not `unavailable`.
3. `iw dev wlP4p1s0 scan` (counts only) sees networks on 2.4 and 5 GHz, and 6 GHz where present; connects to a 2.4, a 5 and a 6 GHz network; throughput sane (`iperf3`, TBD target from Windows on the same AP).
4. `iw reg get` shows a country after one is set; no firmware, MHI or QMI error in the log.
5. The station address passes `tools/check-mac.sh` (MATCH), or the difference is explained.
6. Survives suspend in phase 4.

## 8. Requests

Owner: kernel

- **K1.** Add `hardware/wifi/patches/0001-arm64-dts-qcom-denali-wire-pcie4-perst-wake.patch` to `kernel/series` and to the DTB variant used by the default entry (`m5` and its successors). Only the DTB changes; no rebuild of modules. Risk: if PCIe4 stops training, the previous behaviour is the DTB without this patch.
- **K2.** `CONFIG_ATH12K_DEBUG=y` in `kernel/config/sp11.config` (the symbol exists, `drivers/net/wireless/ath/ath12k/Kconfig`; without it `debug_mask` is inert). No other symbol is missing.

Owner: firmware

- **F1.** Add a `[[package]]` entry for `atheros-firmware` (it ships the ath12k files; `qcom-firmware` does not): `atheros-firmware-0:20261019-1.fc44.noarch`, RPM SHA-256 `5149e96e0377a7d3a9e1dea254d39fa5a46fd4903df839b3971de8ccfb75ed38`; `20260309-1.fc44` `30c7a6ea398216302b218c096ddb2fc233e1c690746b98cd4432d13438bfbdef`. Minimum 20261019 (board id 255 for `17cb:1107`). Digests of the decompressed files are in `evidence/2026-10-28-windows-board-selection.md`. Add `[[blob]]` rows (origin `linux-firmware`, `component = "wifi"`) for `ath12k/WCN7850/hw2.0/amss.bin`, `m3.bin`, `board-2.bin`.
- **F2 (held, do not stage yet).** Derived board file: `python3 -I hardware/wifi/tools/wifi-board2.py build --fedora <board-2.bin.xz of 20261019> --windows sources/windows/DriverStore/qcwlanhmt8380.inf_arm64_f6c170edbe88d474/bdwlan.elf --sha256 b24438910ff0383d299798a997d3ef3484be624ac013aec2ce7939ec32900c4f --out out/firmware-root/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin`. `updates/` takes precedence over `/usr/lib/firmware`, so no file of the Fedora package is replaced. The output holds a Windows blob: it stays in `out/` (S5, never git). I will release it after the rfkill problem is solved, so that one change is tested per boot.

Owner: image

- **I1.** Install `hardware/wifi/collector/wifi.sh` as `/etc/sp11-log-collector.d/wifi.sh` (read-only except one scan, which only counts BSSs; masks MACs).
- **I2.** For the rfkill test ISO only: install `hardware/wifi/collector/wifi-unblock-probe.sh` as `/etc/sp11-log-collector.d/wifi-unblock-probe.sh`. It changes the rfkill soft-block flag and the NetworkManager radio switch, once, 90 s after boot (nothing persistent, no firmware, S3/S4 untouched).
- **I3.** A tiny unit `sp11-rfkill-events.service` (`ExecStart=/usr/bin/rfkill event`, `StandardOutput=journal`, `WantedBy=multi-user.target`, started before NetworkManager) so the journal records who blocks the radio and when.
- **I4.** With K2: `/etc/modprobe.d/50-sp11-ath12k.conf` containing `options ath12k debug_mask=0x30` (BOOT and MAC messages: board name tried, board API used, rfkill configuration and events). Revert after Q4/Q5 are answered.
- **I5.** Packages: nothing new (`iw`, `pciutils`, `dmidecode`, `NetworkManager-wifi`, `wpa_supplicant`, `wireless-regdb`, `atheros-firmware`, `ethtool`, util-linux `rfkill` are in the M5 package list). Keep `atheros-firmware` at 20261019 or later.
- **I6.** Initramfs: no change.

Owner: orchestrator

- **O1.** Start the cross-check for PCIe4 PERST#/WAKE# (TLMM 146/148, Q8) on the other runtime (protocol 5.1) before this reaches `sw-ready`.
- **O2.** After the next boot copy the device logs to `out/device-logs/` again; read `extra-wifi.txt` and run `hardware/wifi/tools/check-mac.sh` on it locally.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: MAC source verified in ath12k (firmware/OTP); nothing to copy unless M2 shows a placeholder.
- 2026-10-28: full dependency chain mapped on 7.3 with file:line; Fedora firmware checked (`atheros-firmware`, 20261019 needed); Windows board selection verified by REA (`board_id 0xff` gives `bdwlan.elf`); DT gap found (PERST#, WAKE#, pinctrl), patch 0001 built and validated; M5 device log read: hardware up, Wi-Fi radio blocked in NetworkManager; collector drop-ins, MAC check and derived board-2 tool written.
