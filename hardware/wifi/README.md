# wifi

## 1. Summary

Qualcomm WCN7850 (FastConnect 7800) Wi-Fi 7 on PCIe4 probes and loads firmware on M8, but a firmware rfkill OFF event hard-blocks the radio (`soft=0 hard=1`), preventing scans. M9 candidates backport the upstream Surface rfkill workaround, constrain the existing CMA pool below 4 GiB, and release the private Windows-derived board file; DT/schema and ath12k object compilation pass; status remains `designed` pending independent cross-check, integrated RPM/module linking and device validation.

See [M8 evidence and root cause](evidence/2026-10-29-m8-wifi.md), [ARM64 REA MCP policy evidence](evidence/2026-10-29-windows-rfkill.md), [local validation](evidence/2026-10-29-validation.md), and the [M9 test plan](test-plan.md).

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
| Firmware-side rfkill | the driver programs WCN GPIO 48, radio-on level 1, as hardware rfkill (`wifi7/hw.c:508-510`); the Surface ACPI `_DSM` function 2 returns 0x60 (rfkill bit 2 clear, 11be-disable bit 0 clear) | Verified (code, AML); M8 confirms OFF (`radio_state 1`) and hard block; patch 0002 skips unusable hardware rfkill setup | `dsdt.dsl:59196`, `acpi.h:59-60`, `acpi.c:385-388` |

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
9. **Config** (historical M5 release `.config` of `7.3.0-65.sp11.3.fc44`, `out/build/kernel/rpmbuild/BUILD/…/.config`): `ATH12K=m`, `ATH12K_AHB=y`, `MAC80211=m`, `CFG80211=m`, `PCIE_QCOM=y`, `HAVE_PWRCTRL=y`, `PCI_PWRCTRL=y`, `PCI_PWRCTRL_PWRSEQ=m`, `POWER_SEQUENCING=y`, `POWER_SEQUENCING_QCOM_WCN=m`, `PHY_QCOM_QMP_PCIE=m`, `QCOM_PD_MAPPER=m` (not needed by WCN7850; present), `QRTR=m`, `QRTR_MHI=m`, `MHI_BUS=m`, `QCOM_QMI_HELPERS=m`, `PINCTRL_X1E80100=y`, `CLK_X1E80100_GCC=y`, `CLK_X1E80100_TCSRCC=y`, `INTERCONNECT_QCOM_X1E80100=y`, `REGULATOR_QCOM_RPMH=y`, `REGULATOR_FIXED_VOLTAGE=y`, `RFKILL=m`, `RFKILL_INPUT=y`, `FW_LOADER_COMPRESS_XZ=y`. All dependencies were present. M5 lacked `ATH12K_DEBUG`; K2 is shipped in M8 (`debug_mask=48` with board and rfkill messages in the M8 log). The modules are in the image (`ath12k.ko.xz`, `ath12k_wifi7.ko.xz`, `pwrseq-qcom-wcn`, `pci-pwrctrl-pwrseq`, QMP PCIe PHY, `qrtr`, `qrtr-mhi`, `mhi`, `qmi_helpers`). The initramfs needs only the PHY (already there for NVMe); Wi-Fi modules load after switch-root.
10. **Native coverage:** `full` for the chain; the DT lacks PERST#, WAKE# and the `pcie4_default` consumer (device log fact 11). Patch below.

Patch set (`patches/`, base `v7.3`, kernel worktree `out/linux/wifi`, branch `w/wifi`; new changes remain uncommitted under D24):

| Patch | Content | Checks |
|:--|:--|:--|
| `0001-arm64-dts-qcom-denali-wire-pcie4-perst-wake.patch` | `&pcie4` gets `pinctrl-0 = <&pcie4_default>`; `&pcie4_port0` gets `reset-gpios = <&tlmm 146 …>` and `wake-gpios = <&tlmm 148 …>` | `scripts/kernel-dev.sh --check wifi dtbs`: DTB builds, dt-schema (`CHECK_DTBS`) clean, no new warning; `dtc` dump shows `reset-gpios = <… 0x92 0x01>`, `wake-gpios = <… 0x94 0x01>`; applies cleanly on top of display-lcd 0001-0003 (`git apply --check` in `out/linux/m3`); `checkpatch.pl --strict`: 0 warnings, 0 checks, 1 error "Missing Signed-off-by" (by project rule none is added) |
| `0002-wifi-ath12k-skip-broken-surface-rfkill.patch` | Upstream Surface workaround, hardware revision + board compatible match; skips programming the unusable hardware rfkill input | `checkpatch --strict --no-signoff` clean; complete ath12k directory compiles (BTF-enabled kernel); integrated RPM/module linking remains K3 |
| `0003-arm64-dts-qcom-denali-keep-cma-in-dma32.patch` | Constrains the existing reusable 128 MiB default CMA pool to the lower RAM window (2–4 GiB) | `checkpatch --strict --no-signoff` clean; LCD DTB and M8 boot variant build and dt-schema validates; inherited range and sound/GPU guards checked; runtime/cross-check pending |

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| M8 firmware hardware-rfkill OFF event, soft=0 hard=1 | Patch 0002, upstream `5949d1910f13c20f6ebcd26eec9e0c02cb4951aa`; does not require a DT property or userspace unblock |
| Initial QMI host-DDR coherent allocation fails (7274496 B) | Patch 0003: M8 CMA is above the 32-bit coherent mask; keep the existing pool below 4 GiB. Small-chunk recovery already succeeds, so this is separate from the scan blocker |
| Fedora generic id-255 board data differs from Windows `bdwlan.elf` | F2 released for the private M9 image as an operator-provided local file; preserve Fedora REGDB and all original entries |
| rfkill listener is ordered before NetworkManager; legacy unblock probe | I3 removes the ordering edge; I2 retires the mutating probe. The M8 listener start completed, so it was not an indefinite gate |
| SAR / TAS / regulatory power tables | UEFI variables/DPP remain unreadable offline (Q2). Do not claim parity with Windows SAR. Preserve Linux regulatory and thermal enforcement |
| PCIe4 reset/wake/pinctrl | Patch 0001 is present and the pins/link are verified in M8; independent wiring cross-check still belongs to the orchestrator |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Does the private Windows-derived BDF restore board-data parity? | Windows filename selection: Inference (strong), Linux id-255 lookup: Verified; DPP override TBD | F2 output hash and first-match payload checked locally; M9 reports override size, name match, board API 2, no BDF rejection |
| Q2 | Surface SAR / TAS tables | TBD | Read-only Windows evidence from Surface SAR UEFI variables/DPP; no BIOS SAR/TAS function in the captured WLAN `_DSM` |
| Q3 | Is the factory MAC in OTP? | TBD | M8 local comparison DIFFERENT with type 3 (userspace-set); a permanent-address hash is needed before deciding any userspace address policy |
| Q4 | Did userspace soft-block M8? | Resolved: no, Verified | Listener and sysfs show soft=0; hardware changes to hard=1 at 30.55 s |
| Q5 | Is the WCN hardware-rfkill input unusable on this board? | Verified OFF event and hard block; Inference (strong) causal setup mismatch | M9 patch 0002: hard=0 without a radio toggle, NM disconnected/connected and cached scan counts >0. `radio_state 1` is OFF, not 0 |
| Q6 | Can the first QMI host-memory allocation succeed? | Inference (strong): current CMA exceeds coherent mask | Cross-check patch 0003, then M9 CMA base/end below 4 GiB and QMI debug evidence with no large-allocation fallback warning |
| Q7 | SMBIOS board variant? | Resolved for M8: no type-248 entry reported, Verified | Exact no-variant board name matches; no DT calibration string is needed |
| Q8 | PCIe4 PERST#/WAKE# 146/148 wiring | Inference, M8 pin ownership/link Verified | Other-runtime cross-check under protocol 5.1; no new GPIO change in M9 |

## 7. Acceptance

1. `lspci -nnk` shows `0004:01:00.0 [17cb:1107]` bound to `ath12k_wifi7_pci`; link Gen3 x2 (PCIe4 PERST# and WAKE# claimed by the controller in `pinctrl-pins.txt`).
2. `rfkill list` shows the Wi-Fi radio `Soft blocked: no`, `Hard blocked: no` without user action; `nmcli dev` shows `wlP4p1s0 wifi disconnected` (or `connected`), not `unavailable`.
3. Read-only `iw dev wlP4p1s0 scan dump` (counts only, NetworkManager performs scanning) sees networks on 2.4 and 5 GHz, and 6 GHz where present; connects to a 2.4, a 5 and a 6 GHz network; throughput sane (`iperf3`, TBD target from Windows on the same AP).
4. `iw reg get` shows a country after one is set; no firmware, MHI or QMI error in the log.
5. The station address passes `tools/check-mac.sh` (MATCH), or the difference is explained.
6. Survives suspend in phase 4.

## 8. Requests

Owner: kernel

- **K1/K2 (shipped in M8).** Keep patch 0001 and `CONFIG_ATH12K_DEBUG=y`; M8 confirms pin ownership, link and debug messages.
- **K3 (M9).** Add `hardware/wifi/patches/0002-wifi-ath12k-skip-broken-surface-rfkill.patch` to `kernel/series`, then rebuild the kernel RPMs/modules. This changes `ath12k.ko`; shipping only a new DTB cannot fix the hard block. Upstream code is unchanged from `5949d1910f13c20f6ebcd26eec9e0c02cb4951aa` (source pin request SRC1 below). Preserve both BTF options.
- **K4 (M9).** Add `hardware/wifi/patches/0003-arm64-dts-qcom-denali-keep-cma-in-dma32.patch` to the series and every M9 device DTB, including the packaged LCD DTB and diagnostic variants. Existing reusable CMA remains 128 MiB; memblock places it within 2–4 GiB, avoiding reserved ranges. Keep the M8 DTB available for rollback. Do not increase DMA masks or thermal/charging limits.

Owner: firmware

- **F1 (shipped in M8).** Keep `atheros-firmware >= 20261019`, with Fedora `amss.bin`, `m3.bin`, and base `board-2.bin`; no `firmware-2.bin` addition is needed for API 1.
- **F2 (RELEASED for private M9).** Build/validate the local board override with the command below. The Windows input SHA-256 defaults to `b24438910ff0383d299798a997d3ef3484be624ac013aec2ce7939ec32900c4f`; decompressed Fedora input defaults to `6a98237c743d864773a547e81e23f0c6dc721dcd7331926bee7381e2152e00fd` (20261019). The tool prepends one id-255 match and retains all Fedora IEs/REGDB. Do not add the output to a repository, firmware package, public manifest, or published image. Hand it to image as an operator-provided file (I7), like the private Bluetooth address input.

```bash
python3 -I hardware/wifi/tools/wifi-board2.py build \
  --fedora out/image-work/l0-sp11-fedora44-aarch64-kiwi-m8-20261029T172500Z/root/usr/lib/firmware/ath12k/WCN7850/hw2.0/board-2.bin.xz \
  --windows sources/windows/DriverStore/qcwlanhmt8380.inf_arm64_f6c170edbe88d474/bdwlan.elf \
  --out out/firmware-private/wifi/ath12k/WCN7850/hw2.0/board-2.bin
```

Local output already built: 2520880 bytes, SHA-256 `74d0f9f9f6a601265367698a97bc58a5e7c6e28fe1c323c815feb3d5e3026891`.

Owner: image

- **I1 (M9 update).** Install the updated `hardware/wifi/collector/wifi.sh` as `/etc/sp11-log-collector.d/wifi.sh`. It reads the existing scan cache (`iw ... scan dump`), DMA masks, CMA counters, and unit state. No radio toggles, scan requests, or persistent changes. Preserve a copy during the first/session-active phase alongside the final `extra-wifi.txt`; M8's last snapshot was after NM stopped, so overwriting earlier samples loses functional scan evidence.
- **I2 (retire).** Do not install `wifi-unblock-probe.sh` for M9. A userspace unblock cannot clear the confirmed hardware block and would obscure validation of K3.
- **I3 (M9).** Remove `Before=NetworkManager.service` from `sp11-rfkill-events.service`. Keep `Type=simple`, `After=systemd-modules-load.service`, and journal output if retaining the listener. No `Requires=`, `Wants=`, `ExecStartPre=`, or oneshot wait from NetworkManager to the listener. M8's observed wait lasted only 0.41 s and NM did start, so do not describe this as the root cause. The listener records state changes, not the PID responsible for them.
- **I4 (M9 diagnostics).** Set `options ath12k debug_mask=0x70` (BOOT, MAC, QMI) before module load. QMI output exposes memory segment type/size and successful replies; retain private logs under `out/`, remove diagnostic mask after acceptance.
- **I5/I6.** Existing packages and post-switch-root Wi-Fi loading suffice; no Wi-Fi initramfs change. Keep speakers/GPU off as required by current decisions.
- **I7 (private input, M9).** Accept an optional absolute local path such as `--wifi-board2 <file>` / `SP11_WIFI_BOARD2=<file>` in the image builder, analogous to the private BD-address input. The supplied file above is ready. Copy it into `/usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin` in the private image root. Keep Fedora's packaged `.xz` file intact; `updates/` wins. Check file magic, exact output SHA-256/size above, and staged hash in L0; if explicitly supplied but invalid, fail the build. Omit it when not supplied. Do not add its bytes to the overlay/git, or publish an ISO/export containing it. Preserve the same private input for L0 reproducibility. Rollback: rebuild without the option, removing the updates override from a fresh root.
- **I8 (M9 L0).** Confirm both BTF symbols, K3's rebuilt ath12k module, K4's `alloc-ranges` in every shipped device DTB, no NetworkManager ordering edge to the listener, no legacy unblock probe, correct optional override placement/hash, Fedora base REGDB retained, and S1/D22/D23 guards unchanged.

Owner: sources

- **SRC1.** Pin official ath.git Surface rfkill change `5949d1910f13c20f6ebcd26eec9e0c02cb4951aa` in `sources/sources.toml` before integration. Retrieved patch: `https://git.kernel.org/pub/scm/linux/kernel/git/ath/ath.git/patch/?id=5949d1910f13c20f6ebcd26eec9e0c02cb4951aa`, local reference `out/rea/wifi/surface-rfkill-upstream.patch`, SHA-256 `015dc24386a3433945d8fbed29c156957a3054a3400ca8fc84d7d37fda60b5be`. No new Windows package is required.

Owner: orchestrator

- **O1.** Independent other-runtime cross-check for patch 0003's DMA reachability/window and the existing PCIe4 wiring (Q8) before `sw-ready`; also reproduce the M8 rfkill interpretation and Windows-policy evidence. This worker cannot assign a Claude cross-check itself.
- **O2.** Integrate K3/K4 and I1–I8, then one batched M9 boot. Collect exact read-only commands in `test-plan.md`; inspect rfkill, CMA/QMI and scan-cache results before acceptance. Leave status below `pass` until this unit's evidence meets acceptance.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: MAC source verified in ath12k (firmware/OTP); nothing to copy unless M2 shows a placeholder.
- 2026-10-28: full dependency chain mapped on 7.3 with file:line; Fedora firmware checked (`atheros-firmware`, 20261019 needed); Windows board selection verified by REA (`board_id 0xff` gives `bdwlan.elf`); DT gap found (PERST#, WAKE#, pinctrl), patch 0001 built and validated; M5 device log read: hardware up, Wi-Fi radio blocked in NetworkManager; collector drop-ins, MAC check and derived board-2 tool written.

- 2026-10-29: M8 full logs identify firmware hardware rfkill as the scan blocker (OFF=1, soft=0 hard=1); upstream workaround backported as 0002; lower-CMA candidate 0003; private F2 released/built; read-only M9 collector and image requests prepared; DT/schema and ath12k compile checks pass with BTF (D24, no git writes).
