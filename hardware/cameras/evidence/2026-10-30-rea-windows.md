# Cameras: Windows camera stack REA and Linux 7.3 gap map

Date: 2026-10-30. Static analysis only. No kernel build, no device access, no
firmware writes (S3). The IR illuminator and flash were read, never driven (S2).

Grades: **Verified** (read from data or code at the cited place), **Inference**
(derived, reasoning given), **Unknown**.

## Standing rule: RAW Bayer in, RGB needs an ISP stage

The RGB sensors (OV13858 rear, IMX681 front) output RAW Bayer, not RGB. CAMSS
on Linux only receives and writes RAW (the X1E80100 VFE uses `vfe_ops_680`, RDI
only). A usable colour picture needs demosaic, black level, white balance,
colour matrix and gamma after capture: libcamera Software ISP (the simple
pipeline handler) first, Spectra BPS/IPE hardware ISP never on Linux 7.3. The IR
VD55G0 is monochrome: no demosaic, raw passthrough (Y8/Y10) is the usable
format. A camera counts as working only when an app gets RGB or YUV frames with
correct colours.

## Inputs and binary classification

Hashes checked against `sources/binary-catalog.tsv`. REA opened one binary in
this session: `surfacecamfrontsensor8380.sys`, sha256 `80a8e4a1...46f03`, match,
language `AARCH64:LE:64:v8A`, closed with `close_binary`. The remaining facts
come from data files (read with plain scripts, not disassembled) and from the
earlier REA of the same binaries (`sources/windows/rea-evidence/camera*/`,
evidence ids recorded there).

| Format | Files | Architecture | Treatment |
|:--|:--|:--|:--|
| PE native driver | `qccamplatform8380.sys`, `qccamisp8380.sys`, `qccammipicsi8380.sys`, `qccamflash8380.sys`, `surfacecam{front,rear,aux}sensor8380.sys`, `qccamjpege8380.sys` | ARM64, `AARCH64:LE:64:v8A` | Ghidra |
| ELF32 Xtensa, Qualcomm signed MBN | `CAMERA_ICP.mbn`, `CAMERA_ICP_AAAAAA.elf` (ICP firmware) | Xtensa, `Xtensa:LE:32:default` | static headers only, no writes |
| PEP resource data, magic `AeoB` | `CAM{S,F,I,P}_RES_*.bin`, `CAMP_{PCFG,PERF,PRLD}_*.bin`, `SCFG_*.bin`, `C?MD.bin`, `C?PD.bin`, `C?PF.bin`, `CIPA/CIPF/IRP*/IRS*.bin` | none (data) | never disassembled; decoded with a parser (tag 3 container, tag 1 string, tag 0 u64) |
| QTI Chromatix container, header `QTI Chromatix Header` | `com.surface.sensormodule.*.bin` (sensor driver data: register tables, probe, lanes), `com.surface.tuned.*.bin`, `com.qti.tuned.default.bin`, `com.qti.sensormodule.tpg.bin` | none (data) | never disassembled |
| INF (UTF-16) and `.cat` (PKCS#7) | all packages | none | read as text |

## Camera inventory (DT-useful facts)

SKU of this unit: rear `MSHW0491`, front `MSHW0490`, IR `MSHW0492`, platform
`MSHW0495`. Files for `MSHW047x/054x/056x` (other SKUs, including an OV02C10
front variant) do not apply. The sensor ACPI devices `\_SB.CAMS/CAMF/CAMI` have
no `_CRS`; I2C, lanes and power data live in the extension-INF data files.

| | Rear | Front | IR (Windows Hello) |
|:--|:--|:--|:--|
| ACPI | `OVTID858`, `_UID 0x15` | `SONY0681`, `_UID 0x1A` | `SMO55F0`, `_UID 0x1C` |
| Sensor name in module data | `ov13858` | `imx681` | `vd55g0` |
| Sensor name Verified | yes (module data, this session) | yes | yes |
| CCI controller / bus | cci0 bus 1 (TLMM 103/104) | cci1 bus 1 (TLMM 235/236) | cci0 bus 0 (TLMM 101/102) |
| CCI grade | Verified in Windows platform data; Linux mapping Inference (high) | same | same |
| I2C address, 8-bit Windows | 0x20 | 0x20 | 0xC0 |
| I2C address, 7-bit | 0x10 | 0x10 | 0x60 |
| 7-bit grade | Inference (shift of 8-bit); VD55 binding text says fixed 0x10, so conflict | Inference | Inference, conflicts with binding |
| Probe register (word) | 0x300B = 0xD855 | 0x0004 = 0x0AFF | 0x0000 = 0x3047 |
| Reset TLMM | 110, active low | 237, active low | 109, active low |
| Reset grade | Verified pin; polarity Inference (low during power-up, high after) | same | same |
| MCLK | `cam_cc_mclk1_clk` 19.2 MHz (TLMM 97) | `cam_cc_mclk4_clk` 19.2 MHz (TLMM 100, `cam_aon`) | `cam_cc_mclk0_clk` 19.2 MHz (TLMM 96) |
| MCLK pin mapping | Inference | Inference | Inference |
| Supplies (PMIC M = pm8010, Inference) | M-LDO6 1.8 V, M-LDO1 1.2 V, M-LDO5 2.8 V; B-LDO16 2.9 V | M-LDO3 1.8 V; B-LDO7 2.8 V | M-LDO4 1.8 V, M-LDO2 1.15 V, M-LDO7 2.8 V |
| CSIPHY | 1 | 2 | 0 |
| PHY type and lanes | D-PHY, 4 lanes, `laneAssign` 0x3210 | **C-PHY, 1 trio**, `laneAssign` 0 | D-PHY, 1 lane, `laneAssign` 0 |
| Link rate | 1185.6 Mbit/s per lane | 2.4 Gsym/s per trio | 840 Mbit/s |
| Output, mode 0 | RAW10 Bayer, 4076x2806, 30 fps | RAW10 Bayer, 3840x2640, 30 fps | RAW10 monochrome, 644x604, 60 fps |
| Needs RGB stage | yes (Bayer) | yes (Bayer) | no (mono) |
| Other devices | DW9800 VCM (8-bit 0x18), M24C64 EEPROM (8-bit 0xA0) | GT24P128F EEPROM (8-bit 0xA0) | PMIC flash LED via `\_SB.FLSH`, 700 mA: do not drive (S2) |
| Privacy LED | TLMM 105, active high | TLMM 225 | TLMM 225 |

Verified in this session by reading the data files: sensor names, `laneAssign`
(0x3210, 0, 0), `isComboMode` 0, TLMM reset pins, MCLK clock names and 19.2 MHz,
every regulator name and voltage, CCI/MCLK TLMM pin lists (101-104, 235, 236,
96, 97, 100) and the CCI clock at 37.5 MHz. The front sensor driver strings
confirm that the driver logs `I2cMasterIndex`, `I2cSlaveAddr`, `laneMask`,
`laneAssign`, `CSIPHY3Phase`, `comboMode`, `laneCount`, `settleTimeNS` and
`dataRate`, and loads `com.qti.sensormodule.tpg.bin`. I2C master index, CSIPHY id
and the 8-bit addresses come from the earlier REA (platform entries decoded
from `qccamplatform8380.sys` and the `PCFG` data); I did not re-decompile them
this session. The IMX681 C-PHY claim rests on register `0x0111 = 3` and a
trio-based PHY table in `qccammipicsi8380.sys` (earlier REA).

### Power-up sequences (PEP resource data, order as stored)

Common first steps for every sensor: vote `rail_mmcx`, enable `gcc_camera_xo_clk`,
`gcc_camera_ahb_clk`, `cam_cc_gdsc_clk`, `cam_cc_titan_top_gdsc`, set
`cam_cc_cpas_ahb_clk` to 80 MHz. Delay unit is Unknown (milliseconds assumed).

| Sensor | Power up (in order) | Power down |
|:--|:--|:--|
| Rear | reset low; M-LDO6 1.8 V; M-LDO1 1.2 V; M-LDO5 2.8 V; delay 1; B-LDO16 2.9 V; MCLK1 19.2 MHz; reset high; delay 10 | reset low; delay 1; MCLK off; LDO16, 5, 1, 6 off |
| Front | MCLK4 19.2 MHz; M-LDO3 1.8 V; B-LDO7 2.8 V; delay 1; reset high; delay 10 | reset low; delay 1; MCLK off; B-LDO7 off; M-LDO3 off |
| IR | reset low; delay 1; MCLK0 19.2 MHz; delay 2; M-LDO4 1.8 V; M-LDO2 1.15 V; delay 1; M-LDO7 2.8 V; delay 1; reset high; delay 1 | reset low; delay 5; M-LDO7 off; delay 1; LDO2, LDO4 off; MCLK off |

Note the front sensor starts MCLK before its supplies and the IR sensor starts
MCLK before the rails; a Linux driver that sets power in a different order may
still work, but the Windows order is the only known-good one.

## What the Windows ISP stack uses

| Item | Fact | Grade |
|:--|:--|:--|
| ISP | Qualcomm Spectra 695 (`ACPI\QCOM0C25`), IFE/BPS/IPE pipelines driven by CAMX (Camera Core `CamZ`) | Verified (device name, INF) |
| ICP firmware | `CAMERA_ICP.mbn`, ELF32 Xtensa, signed; loaded by `qccamisp8380.sys`; no Linux driver | Verified (catalog) |
| Tuning per sensor | `com.surface.tuned.rfc_ov13858.bin`, `ffc_imx681.bin`, `aux_vd55g0_MSHW0492.bin` (plus `_vd55g1`), default `com.qti.tuned.default.bin`; selected by `SCFG_*` | Verified |
| Sensor driver data | `com.surface.sensormodule.<rfc/ffc/aux>_*.bin` (registers, modes, probe, lanes, gain limits) | Verified |
| Tuning modules inside | black level (IFE and BPS), `bls12`, `cc13` (IPE), `gamma15_ipe`, `lsc41` (IFE/BPS), AWB reference points, AEC tables | Verified (earlier decode) |
| Other ISP data | `C2MD/C2PD/CIPA/CIPF/IRP1-3/IRS1-3.bin` in `qccamisp_ext8380` are PEP/performance data, not tuning | Inference (AeoB container) |
| IR | tuning is an RGB template; only black level and AEC are IR-specific; no illuminator setting | Verified (earlier decode) |

## Linux 7.3 status (read from `sources/linux`, tag v7.3)

| Item | State | Grade |
|:--|:--|:--|
| CAMSS driver | `qcom,x1e80100-camss` compatible, 4 integrated CSIPHY (`csiphy_ops_3ph_1_0`), CSID, VFE (`vfe_ops_680`, RDI only) present | Verified |
| CAMSS binding | `qcom,x1e80100-camss.yaml` present, allows `bus-type` CPHY and DPHY | Verified |
| C-PHY in CAMSS | rejected: `camss.c` "currently only D-PHY is supported" returns `-EINVAL` | Verified |
| CCI | `qcom,x1e80100-cci` in `i2c-qcom-cci` and its binding | Verified |
| camcc | `camcc` node in `hamoa.dtsi`, `clk/qcom/camcc-x1e80100` | Verified |
| DT nodes | no `camss`, no `cci`, no CSIPHY in `hamoa.dtsi`; no camera node in `x1-microsoft-denali.dtsi` | Verified |
| Standalone CSIPHY PHY driver | none in `drivers/phy/qualcomm` | Verified |
| Pinctrl | functions `cci_i2c`, `cam_mclk`, `cam_aon` exist in `pinctrl-x1e80100.c` | Verified |
| Denali DT | `cam_indicator_en` (gpio225) state only, no consumer; no pm8010 LDO or `vreg_l7b/l16b` regulator nodes for cameras | Verified (pm8010 PMIC node exists in `hamoa-pmics.dtsi`) |
| OV13858 driver | `ov13858.c`: ACPI id `OVTID858` matches Windows HID, **no OF match table**, no regulator or reset GPIO handling, only 19.2 MHz clock, only `SGRBG10_1X10`, mode 4224x3136 | Verified |
| IMX681 driver | none in 7.3 (the only IMX in tree: 111 208 214 219 258 274 283 290 296 319 334 335 355 412 415 471 678) | Verified |
| VD55G0 | `vd55g1.c` model ids `S5G1`/`S5G3` only (vd55g1, vd55g4, vd65g4); Windows reads 0x3047 at 0x0000; VD55G0 not listed | Verified (absence); register compatibility Unknown |
| OV02C10 | driver exists (`ovti,ov02c10`, ACPI `OVTI02C1`); only the other-SKU front variant uses it, not this unit | Verified |
| Bryan O'Donoghue X1E series | CAMSS code for X1E80100 is merged; the DT enablement (camss/cci/csiphy nodes) and the C-PHY work are not in 7.3 | Verified for what is in the tree; series status on lore Unknown (no network check this session) |
| libcamera | Fedora-native; simple pipeline handler and Software ISP, `ov13858` helper present in the earlier libcamera 0.7.2 check; IMX681 and VD55G0 helpers absent | Inference (earlier project reading, not re-checked) |

## Work sequence to RGB, per camera

Common: (1) DT: `cci0`, `cci1`, `camss`, pinctrl states, regulators (pm8010
LDOs, PM8550 `l7b`, `l16b`); (2) Fedora config: `CONFIG_VIDEO_QCOM_CAMSS`,
`CONFIG_I2C_QCOM_CCI`, sensor modules; (3) RAW capture through
`media-ctl`/`v4l2-ctl` on the CAMSS RDI node; (4) libcamera simple pipeline
handler plus Software ISP with a tuning YAML; (5) privacy LED wiring.

| Camera | Steps | Missing |
|:--|:--|:--|
| Rear OV13858 (best first target, D-PHY 4 lane, driver exists) | DT sensor node on cci0 bus 1 at 0x10, csiphy1 port, 4 lanes, 19.2 MHz clock, reset TLMM 110, supplies; OF match plus regulator/reset/clock handling in `ov13858.c` (or ACPI-less probe); RAW; Software ISP with tuning derived from `com.surface.tuned.rfc_ov13858.bin` (data-only, generate on the device, no Windows bytes in git) | DT camss/cci/pm8010 nodes; driver power handling; Windows mode 1185.6 Mbit/s vs driver 1080 Mbit/s |
| IR VD55G0 (mono) | DT on cci0 bus 0 at 0x60, csiphy0, 1 lane D-PHY, reset TLMM 109; extend `vd55g1.c` or add a VD55G0 variant after chip-id read; raw Y10 passthrough; illuminator stays off (S2) | VD55G0 support, address conflict with binding text, S2 clearance |
| Front IMX681 | needs C-PHY in CAMSS and a new IMX681 driver (C-PHY, `0x0111 = 3`, 2.4 Gsym/s, register tables exist as derived data outside git) | C-PHY CSIPHY support, IMX681 driver, Bayer order, libcamera helper |

## Safe now versus needs hardware

Safe now (static): everything in this file; a DT patch is **not** written: the
7-bit addresses, pm8010 identity, delay units and MCLK pin mapping are
Inference, and the front camera needs unavailable C-PHY support. A minimal DT
patch (camss/cci/csiphy nodes plus rear sensor) would also depend on
`hamoa.dtsi` content that 7.3 lacks, so it is not "fully established".

Needs hardware evidence. Read-only collector for the next boot (no
`i2cdetect` on unknown buses without confirmation; no writes):

```
dmesg | grep -i -E 'camss|cci|csiphy|camcc|ov13858|vd55|imx|v4l2|media'
ls /sys/bus/i2c/devices /sys/bus/acpi/devices | grep -i -E 'OVTI|SONY|SMO|QCOM0C'
for d in /sys/bus/acpi/devices/{OVTID858,SONY0681,SMO55F0}:*; do echo "$d"; cat "$d"/{status,path,modalias} 2>/dev/null; done
ls /sys/class/video4linux /dev/media* 2>/dev/null
cat /sys/kernel/debug/gpio | grep -E 'gpio(96|97|100|101|102|103|104|105|109|110|225|235|236|237)'
cat /sys/kernel/debug/pinctrl/*/pinmux-pins | grep -E 'gpio(96|97|100|101|102|103|104|235|236)\b'
cat /sys/kernel/debug/regulator/regulator_summary | grep -i -E 'l[0-9]+[bm]|camera'
ls /sys/class/leds | grep -i -E 'cam|privacy'
```

An `i2cdetect` on the CCI buses needs explicit confirmation because the buses
carry an EEPROM and an actuator; prefer a probe through the sensor driver
reading the chip id (`0x300A` for OV13858).

## Unknowns

- 7-bit I2C addresses on hardware (inference only).
- Delay units in the PEP data; reset polarity as seen by Linux.
- pm8010 identity of PMIC M and the 1.15 V and 2.9 V grid mismatch.
- Which PMIC flash channel drives the IR LED.
- VD55G0 register compatibility with `vd55g1.c`.
- Status of the upstream CAMSS DT and C-PHY series (lore not queried).
