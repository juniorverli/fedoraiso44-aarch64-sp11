# M5 device log: Wi-Fi, PCIe4, power sequencer

Source: `out/device-logs/m5-20261028/3f0e2cc1-a043-4c6c-9a72-0835089648d7/` (entry `debug`, GPU off, DTB `m5`, kernel `7.3.0-65.sp11.3.fc44`, uptime 234 s) and `0ee2fa1a-…/` (entry `gpu`, 33 s). Files read: `dmesg.txt`, `journal.txt`, `gpio.txt`, `pinctrl-pins.txt`, `regulator_summary.txt`, `lsmod.txt`, `genpd_summary.txt`, `cmdline.txt`. No address or serial is quoted; MAC-shaped strings were masked while reading (S5).

## Facts (Verified, device log)

| # | Fact | Where |
|:--|:--|:--|
| 1 | `qcom-pcie 1c08000.pcie` probes about 25 times with `supply vdda/vddpe-3v3 not found, using dummy regulator` and `host bridge … ranges`, then `PCIe Gen.3 x2 link up` at 23.37 s. The repeated probes are the `-EPROBE_DEFER` of `pci_pwrctrl_power_on_devices()` until `pci-pwrctrl-pwrseq` and `pwrseq-qcom-wcn` (modules, loaded from the root file system) are bound | `dmesg.txt` lines 556-2018 |
| 2 | Root port `0004:00:00.0 [17cb:0111]`, endpoint `0004:01:00.0 [17cb:1107] class 0x028000`, `PME# supported from D0 D3hot D3cold`, `ASPM: default states L1` | `dmesg.txt:2025-2036` |
| 3 | `pwrseq-qcom_wcn wcn7850-pmu: supply vddio1p2 not found, using dummy regulator` (the node does not list `vddio1p2-supply`; same on all boards with this node) | `dmesg.txt:1008` |
| 4 | `ath12k_wifi7_pci 0004:01:00.0: Wi-Fi 7 Hardware name: wcn7850 hw2.0`, `MSI vectors: 16`, `mhi mhi0: Power on setup success` | `dmesg.txt:2100-2105` |
| 5 | `qmi dma allocation failed (7274496 B type 1), will try later with small size`. Not an error: `ath12k_qmi_alloc_chunk()` sets `target_mem_delayed` and the host retries in smaller chunks (`qmi.c:2653-2666`); the firmware then reached ready. The CMA pool is 128 MiB (`dmesg.txt:10`) | `dmesg.txt:2125` |
| 6 | `chip_id 0x2 chip_family 0x4 board_id 0xff soc_id 0x40170200` | `dmesg.txt:2128` |
| 7 | `fw_version 0x1103006c fw_build_timestamp 2026-03-06 09:10 … WLAN.HMT.1.1.c7-00108-QCAHMTSWPL_V1.0_V2.0_SILICONZ_UPSTREAM-3` (Fedora firmware loaded, no firmware-load failure line) | `dmesg.txt:2129` |
| 8 | Netdev `wlP4p1s0` (renamed from `wlan0`) exists; so board data, regdb and the WMI ready event all succeeded | `dmesg.txt:2147` |
| 9 | NetworkManager: `rfkill1: found Wi-Fi radio killswitch (… ath12k_wifi7_pci)`, `rfkill: Wi-Fi hardware radio set enabled`, then `manager: rfkill: Wi-Fi disabled by radio killswitch; enabled by state file` (30.18 s) | `journal.txt:68191-68623` |
| 10 | After that the Wi-Fi device only gets `unmanaged -> unavailable` (30.18 s) and `unavailable -> unmanaged (unmanaged-quitting)` (234.98 s). No `disconnected`, no scan, no activation. `wpa_supplicant` is started only at 46.4 s (D-Bus activation) and reaches `Successfully initialized` | `journal.txt:68675`, `:165179`, `:117188` |
| 11 | Pinctrl: GPIO 116, 117 (`wcn7850-pmu`) and 214 (`regulator-wcn-3p3`) are claimed; **GPIO 146 (PERST#), 147 (CLKREQ#), 148 (WAKE#) are `UNCLAIMED`** | `pinctrl-pins.txt` |
| 12 | Regulators: `VREG_WCN_3P3` 3300 mV, `VREG_WCN_0P95` 950 mV, `VREG_WCN_1P9` 1900 mV, `vreg_l3e_1p2` 1200 mV, `vreg_l3i_0p8` 880 mV, all enabled; `gcc_pcie_4_gdsc` and `gcc_pcie_4_phy_gdsc` on | `regulator_summary.txt`, `genpd_summary.txt:48-50` |
| 13 | Modules loaded: `ath12k`, `ath12k_wifi7`, `mhi`, `qrtr_mhi`, `qrtr`, `qmi_helpers`, `pwrseq_qcom_wcn`, `pci_pwrctrl_pwrseq`, `mac80211`, `cfg80211`, `rfkill` | `lsmod.txt` |
| 14 | Bluetooth on the same package: `hci0: setting up wcn7850`, firmware `qca/hmtbtfw20.tlv`, NVM `qca/hmtnv20.bin` (generic; Windows records `hmtnv20.b3b`), setup completed | `dmesg.txt:2090-2111` |

## Conclusions

- **Inference (strong):** PCIe4, the PHY, the power sequencer, the firmware boot and the netdev all work in M5. The DT gap of finding 11 is real but did not stop the link: the firmware left PERST# deasserted. What stops Wi-Fi from being usable is the rfkill state (findings 9 and 10).
- **TBD:** who sets the soft block, and when. `rfkill list` was not collected. Candidates: (a) the rfkill core's global state, blocked by an input event (`KEY_RFKILL`/`SW_RFKILL_ALL`, the Surface HID devices appear at 23.4 s) before `ath12k` registers; (b) the firmware's own hardware-rfkill GPIO 48 configuration (`wifi7/hw.c:508`) reporting radio-off through `ath12k_rfkill_state_change_event()` (`wmi.c:9450`), which toggles the radio inside the firmware but not the cfg80211 switch that NetworkManager reads, so it would not explain finding 9 alone. The next boot decides (README Q4).
- Board data: `board_id 0xff` means Linux looked for `…subsystem-vendor=17cb,subsystem-device=1107,qmi-chip-id=2,qmi-board-id=255`. `atheros-firmware 20261019` (on the M5 ISO, `out/image-work/20261026T192029Z/out-build/Fedora.aarch64-44.packages:83`) has that entry; `20260309` does not (see `2026-10-28-windows-board-selection.md`).
