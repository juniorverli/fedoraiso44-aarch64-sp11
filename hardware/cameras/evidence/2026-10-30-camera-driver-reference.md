# Cameras: Qualcomm camera-kernel reference, upstream v7.3 coverage and patch review

Date: 2026-10-30. Static analysis only. No kernel build, no device access, no REA call in this
session. The IR illuminator and the flash were not described or driven (S2).

Grades: **Verified** (read from data or code at the cited place), **Inference** (derived, the
reasoning is given), **Unknown**.

## Inputs

| Input | Identity |
|:--|:--|
| Qualcomm camera-kernel (GPL-2.0-only, downstream) | `out/ref/camera-driver`, `https://github.com/qualcomm-linux/camera-driver`, HEAD `08171dd` (branch `camera-kernel.qclinux.0.0`), `config/x1e80100-camera.mk` sets `CONFIG_X1E80100` |
| Linux | `sources/linux` tag `v7.3` plus the full current `kernel/series` in the scratch tree `out/linux/cameras` (branch `w/cameras`) |
| Windows ACPI | `sources/windows/live-inventory/acpi/dsdt.dsl` (device `CAMP`, line 62428) |
| Earlier REA | `sources/windows/rea-evidence/camera*/`, `evidence/2026-10-30-rea-windows.md` |

The reference has **no devicetree**: the `.dts` of the SoC is not in the repository. Everything
it says about X1E80100 comes from code, headers and the `x1e80100` target name. Where a fact
needs a per-SoC address or a rail it stays Unknown.

## Verified from the reference

| Fact | Evidence | Grade |
|:--|:--|:--|
| X1E80100 is Spectra "camera 6.9.5" with CPAS (Titan) 1.0.0: `CAM_CPAS_CAMERA_VERSION_695 = 0x00060905`, `CAM_CPAS_TITAN_695_V100 = 0x695100`, `.target_name = "x1e80100"` | `camera/drivers/cam_cpas/include/cam_cpas_api.h:110,212`, `cpas_top/cpastop_v695_100.h:1216` | Verified |
| The Windows device is the same silicon: `ACPI\QCOM0C25`, "Spectra 695" | `hardware/cameras/README.md`, INF | Verified |
| Probe compatible of the downstream stack is `qcom,camera_x1e80100` (not upstream CAMSS) | `camera/drivers/camera_main.c:357` | Verified |
| CSID of 695 reuses the 680 register description: `cam_ife_csid_695_reg_info` points at the `cam_ife_csid_680_*` tables | `cam_isp/isp_hw_mgr/isp_hw/ife_csid_hw/cam_ife_csid695.h:38-50` | Verified |
| Upstream CAMSS uses `csid_ops_680` and `vfe_ops_680` for X1E80100: same family | `sources/linux/drivers/media/platform/qcom/camss/camss.c` `csid_res_x1e80100`, `vfe_res_x1e80100` | Verified |
| CSID `CSI2_RX_CFG0`: bit 24 selects the PHY type (`lane_type`, D-PHY 0, C-PHY 1), bits 20.. the PHY number, bits 4.. the lane routing | `cam_ife_csid680.h:1161-1162`, `cam_isp.h:57-58`, `cam_ife_csid_hw_ver2.c:5782` | Verified |
| Upstream gen3/680 CSID code programs the PHY number and lane routing but never the PHY type bit; the gen2 file defines `CSI2_RX_CFG0_PHY_TYPE_SEL` (bit 24) | `camss-csid-gen3.c:100-130`, `camss-csid-gen2.c:57` | Verified |
| CSIPHY version of the SoC is **v2.1.2** (comment in upstream table: "4nm 2PH v 2.1.2"): the upstream X1E80100 lane table matches `csiphy_2ph_v2_1_2_reg` in 99 of 103 entries (differences: skew calibration and settle entries, programmed separately) and the common registers `0x1014/0x101c/0x1018` | `camss-csiphy-3ph-1-0.c:807-` against `cam_sensor_module/cam_csiphy/include/cam_csiphy_2_1_2_hwreg.h` (script comparison, this session) | Verified (register match); SoC to version mapping rests on the upstream comment (Inference for the attribution) |
| The Windows D-PHY table (`qccammipicsi8380.sys`, `camera-cphy/csiphy_tables.txt` `dphy`) equals the upstream X1E80100 lane table apart from the common and IRQ registers, the settle value and the skew entries | same script | Verified |
| The Windows C-PHY table above 2.5 Gsym/s contains all 105 entries of `csiphy_3ph_v2_1_2_reg` plus `datarate_212_2p5Gsps` (the other 16 Windows entries are common, reset and IRQ registers). The two lower Windows rate classes are not reproduced one-to-one by any single reference rate table (24 to 33 Windows entries without a counterpart, common registers included), so the rate-class deltas of the reference must be selected by rate, not copied | same script | Verified |
| CSIPHY lane enable register (`0x1014`, CTRL5): bit0 D0, bit1 C0, bit2 D1, bit3 C1, bit4 D2, bit5 C2, bit6 D3, bit7 clock. D-PHY lane n sets bit `2n`; a C-PHY trio n sets bit `2n+1`. Upstream writes `BIT(7) \| BIT(pos*2)`, the Windows D-PHY table patches `0xd5` (four lanes), the Windows C-PHY common table patches `0x2a` (three trios) | `cam_csiphy_dev.h:102-109`, `cam_csiphy_core.c:1010-1040`, `camss-csiphy-3ph-1-0.c:1163-1166`, `csiphy_tables.txt` | Verified |
| `laneAssign` `0x3210` (rear) is the identity routing: CAMSS `data-lanes = <0 1 2 3>` produces CTRL5 `0xd5` and CSID lane routing 0,1,2,3 | arithmetic on the facts above | Verified |
| C-PHY settle: Windows computes Msps = data rate / 2.28 / 1e6 and looks up a table; the reference states "2.28 bits/symbol" for every C-PHY rate row | `csiphy_tables.txt:4`, `cam_csiphy_2_1_2_hwreg.h` comments | Verified |
| Downstream CSIPHY has a per-lane D-PHY and a per-trio C-PHY register bank in the same block (`3ph` registers at `0x200/0x600/0xA00`, D-PHY at `0x000/0x400/0x800/0xC00/0xE00`), so one CSIPHY serves both PHY types | `cam_csiphy_2_1_2_hwreg.h` | Verified |
| CCI register layout is the msm8996 (v2) one: `HW_VERSION 0x0`, `RESET_CMD 0x4`, `Mn_SCL_CTL 0x100/0x200`, queues at `0x300+` | `cam_cci/cam_cci_hwreg.h:10-47` against `i2c-qcom-cci.c` | Verified |
| CCI hardware version 1.2.9 (`0x10020009`) has queues of 64 and 16 words and reads at most 14 bytes; other versions use 128 and 32. Upstream `msm8996-cci` data uses 64 and 16, which is safe for any version | `cam_cci_dev.h:44-47,61,86`, `cam_cci_soc.c:57` | Verified (the version of this SoC is Unknown) |
| The Qualcomm sensor stack stores the I2C address as 8 bit and the CCI client uses `addr >> 1`: Windows 0x20 is 7-bit 0x10, 0xC0 is 0x60 | `cam_sensor_core.c:938,977` | Verified for the convention; Inference that the Windows data uses it (same Qualcomm sensor-module schema); hardware probe decides |
| Delay unit of Qualcomm sensor power sequences is milliseconds (`msleep` above 20, otherwise `usleep_range(delay*1000, +1000)`) | `cam_sensor_utils/cam_sensor_util.c:2584-2588` | Verified for the downstream stack; Inference for the Windows PEP `DELAY` entries (not decoded) |
| ICP firmware lookup: `qcom/x1e80100/<fw_name>.mbn` (the target name comes from CPAS), then `<fw_name>.mbn` at the root, fallback `CAMERA_ICP` with `.mbn` or `.elf` | `common/cam_icp_util.c:62-125`, `common/cam_icp_util.h:16` | Verified |
| The Windows package `qccamisp8380` ships `CAMERA_ICP.mbn` (ELF32 Xtensa, Qualcomm signed, 905880 bytes, sha256 `c214e486...8c9a`) and `CAMERA_ICP_AAAAAA.elf`: the name the reference requests exists on the device | `sources/binary-catalog.tsv` | Verified (names); whether the signature and authentication chain accepts it under Linux: Unknown |

## Is Qualcomm's native Spectra stack usable on Linux?

No, not as a Fedora-native camera. The reference is a different driver, not CAMSS.

- It registers `video_register_device` for `cam-req-mgr-devnode`, but the interface is the private
  `VIDIOC_CAM_CONTROL` ioctl and the `cam_defs.h` structures (`cam_req_mgr_dev.c:372`,
  `include/uapi/camera/media/cam_defs.h:117`). It does not expose V4L2 capture nodes with buffers,
  so no V4L2 application and no libcamera pipeline handler can use it.
- The pipeline (IFE, BPS, IPE, CRE, OPE, sensor, flash, CDM, ICP, SMMU, SYNC) is driven by
  Qualcomm's proprietary CamX/CHI userspace and tuned by Qualcomm Chromatix data. That userspace is
  not available for Linux in any form we may ship (S5).
- The ISP needs ICP firmware (`CAMERA_ICP.mbn` or `.elf`, signed Xtensa) and the secure-ISP path
  (`QCOM0CCC`); both are Windows-package binaries that cannot enter git (S5).
- Linux 7.3 has no driver for it, and the downstream tree is an out-of-tree module for a vendor
  kernel.

The viable path is upstream CAMSS (V4L2, receives RAW through RDI) plus the libcamera Software ISP
(CPU/GPU demosaic, black level, white balance, CCM, gamma): **Fedora-native, RAW to RGB**. Spectra
BPS/IPE hardware processing is out of reach.

## RAW Bayer to RGB, formats and architectures

- Rear OV13858 and front IMX681 emit RAW Bayer (RAW10). An app counts as served only when it
  receives RGB or YUV frames with correct colours. CAMSS delivers RAW through RDI only
  (`camss-vfe-680.c:105`); even the PIX path never demosaics. libcamera Software ISP is the
  RGB stage; it needs a per-sensor tuning file (black level, colour matrix, lens shading). The
  Windows `com.surface.tuned.*.bin` values are a possible source, converted on the device (S5).
- IR VD55G0 is monochrome: no demosaic, RAW10 mono passthrough after black level and gamma.
- Binary classification (from `sources/binary-catalog.tsv`): ARM64 PE drivers (`AARCH64:LE:64:v8A`,
  Ghidra) for the camera `.sys` files; ELF32 Xtensa signed MBN for the ICP firmware (static
  headers only, no Ghidra language for an unreviewed disassembly); `AeoB` PEP resource files and
  `QTI Chromatix` containers are data and are never disassembled.

## What upstream v7.3 already has for Hamoa, and what the reference fills in

| Block | v7.3 state | Reference result |
|:--|:--|:--|
| CAMSS `qcom,x1e80100-camss` (CSIPHY 0, 1, 2, 4; CSID, VFE, VFE lite; TPG) | present, D-PHY only | CSIPHY v2.1.2 tables confirmed (above). The four-lane 2.5 Gbit/s D-PHY table fits the rear sensor (1185.6 Mbit/s) and a one-lane IR sensor |
| C-PHY | rejected in `camss.c` ("currently only D-PHY is supported", returns `-EINVAL`) | The reference holds the register sequence needed: `csiphy_3ph_v2_1_2_reg` plus the per-rate delta tables (`datarate_212_*`), trio lane enable, settle from Msps = rate/2.28, and CSID `CFG0` bit 24. All of its 105 entries for the 2.5 Gsym/s class are present in the Windows table |
| CCI `qcom,x1e80100-cci` | driver and binding present (`msm8996-cci` fallback, v2 data) | Layout matches; queue sizes are safe; bus speed and timing values are not in the reference |
| CAMCC | present (`camcc-x1e80100`), MCLK 19.2 MHz from TCXO | n/a |
| DT nodes | none in v7.3 | CCI0/CCI1 base and SPI from ACPI `CAMP` (`0x0ac15000` GSIV `0x1ec`, `0x0ac16000` GSIV `0x12f`, minus 32 gives SPI 460 and 271) |
| Standalone CSIPHY PHY driver | none in v7.3; the earlier survey (`rea-evidence/camera-cphy/upstream`, fetched 2026-10-18) holds `linux-next` `dphy.c`/`phy.h` and mirrored posts of a `phy: qcom-mipi-csi2` C-PHY series for X1E80100, a CAMSS "track PHY type" series and an IMX681 C-PHY RFC | not in v7.3; the series are a backport target (request R5) |

## Review of the four Sol patches (untrusted input)

| Sol patch | Result |
|:--|:--|
| 0001 hamoa camera blocks | **Survived, rewritten.** Content equals the binding example and agrees with ACPI for CCI addresses and SPI. Whitespace errors (space before tab) fixed; the commit message now states what is verified. `CHECK_DTBS=y` clean |
| 0002 denali recording indicators | **Rewritten.** The second LED on GPIO105 was dropped: its function is not established (GPIO105 is also a `cci_i2c` pin). GPIO225 stays as the single camera indicator, justified by the existing `cam_indicator_en` state and by the same use on x1e80100-microsoft-romulus, Dell XPS 13 and ASUS Zenbook A14, not by a Windows decode. Node stays disabled |
| 0003 binding ov13858 | **Survived, rewritten.** The `leds` and `led-names` re-declaration was removed (already in `video-interface-devices.yaml`), an example was added; `dt_binding_check` clean. Local candidate, no maintainer has accepted it |
| 0004 driver ov13858 | **Survived unchanged in code**, reviewed line by line (error unwinding, power order against the Windows sequence, ACPI untouched because the new callbacks return 0 without an OF node). Message extended: the OF clock rate is not set by `devm_v4l2_sensor_clk_get()` in v7.3 (`v4l2-common.c:833`), so the board needs `assigned-clock-rates`. **Not compiled** (no build allowed): `checkpatch --strict` is clean, `git apply --check` passes on the full series |

New: patch 0005 (Denali rear camera, disabled) and a diagnostic variant
`hardware/cameras/dtb-variants/x1p64100-microsoft-denali-cam-rear.dts`.
Order: binding, driver, hamoa DT, Denali LED, Denali rear camera.

## Privacy / recording indicator LED

- Mechanism (Verified in v7.3): a sensor node with `leds = <&led>; led-names = "privacy";` makes
  `v4l2_async_register_subdev_sensor()` call `led_get(dev, "privacy")`; the V4L2 core switches the
  LED to max brightness on `s_stream(1)` and off on stop (`v4l2-subdev.c:173-186,2732`). No driver
  change needed.
- Hardware: `CAMP` lists two `GpioIo` pins, `0x00E1` (225) and `0x0069` (105), exclusive, no
  function in the resource (`dsdt.dsl:62476-62487`). GPIO225 is the camera indicator (Inference,
  strong: `cam_indicator_en` state in the Denali DTS and the same pin on Surface Laptop 7). The
  function of GPIO105 and which sensor uses which pin: **Unknown** (the claim in the aborted worker
  note, "PRLD selects resource 0 for front and aux, resource 1 for rear", was not reproduced).
  `CAMP_PRLD_MSHW0495.bin` holds six values (`0x106`, `0x501`, then zeros), not decoded.
- It is not the IR emitter and not the flash: both belong to the PMIC flash device `QCOM0C27`
  (`FLSH`). They are not described in any patch (S2).

## Power-up semantics carried into the DT (rear OV13858)

| Item | Value | Grade |
|:--|:--|:--|
| PMIC "M" is the RPMh `pm8010` (`qcom,pmic-id = "m"`): the voltage classes of all seven Windows rails match `pm8010_vreg_data` (LDO1 and LDO2 NLDO 1.2 and 1.15 V; LDO3, 4, 6 PLDO LN 1.8 V; LDO5 and LDO7 PLDO 2.8 V) | `qcom-rpmh-regulator.c:1529-1537` against the PEP rails | Inference, strong (letter from the PEP resource name, classes match) |
| Rails: DOVDD M-LDO6 1.8 V, DVDD M-LDO1 1.2 V, AVDD M-LDO5 2.8 V, 1 ms, MCLK1 19.2 MHz, reset release, 10 ms | `evidence/2026-10-30-rea-windows.md` | Verified (data), delay unit Inference (ms) |
| Reset GPIO110, active low (assert = pin low during power-up) | same | pin Verified, polarity Inference |
| CSIPHY supplies `vdd-csiphy-0p8` and `vdd-csiphy-1p2` taken as `vreg_l2c_0p8` and `vreg_l1c_1p2` | convention of other Hamoa boards | Hypothesis: the Windows PEP data does not name them in the decoded part |
| Input supplies of the pm8010 LDOs | not described | Unknown |

## Still blocked

- Front IMX681: needs C-PHY in CAMSS (series above, to be backported and re-checked against the
  reference tables), an IMX681 driver, and the register tables, which are Windows-derived data and
  cannot enter git (S5): they must be derived on the device or taken from a licence-clean source.
- IR VD55G0: `vd55g1.c` does not list the chip; address conflict (0x60 against the binding text 0x10).
- Rear sensor mode: Windows 1185.6 Mbit/s per lane against the driver's 1080 and 540 Mbit/s modes.
- Everything that needs the device: see `hardware/cameras/test-plan.md`.

## Exact REA questions for later (not asked now)

1. `qccamplatform8380.sys`: for `CAMP_PRLD_MSHW0495.bin` (`0x106`, `0x501`), which GPIO resource
   (225 or 105) does each sensor's indicator use, with which polarity, and is GPIO105 an LED at all?
2. The CSIPHY and CSID rails: which PEP or ACPI entries power the CSIPHY 0.8 V and 1.2 V supplies,
   and which parent supplies feed pm8010 LDO1/2 (`vdd-l1-l2`), LDO3/4, LDO5, LDO6, LDO7?
3. The PEP `DELAY` handler: is the value in milliseconds or microseconds?
4. The CCI master index to physical controller and bus mapping, the bus clock (the 37.5 MHz CCI
   clock and the I2C speed mode per bus) and whether the IR address is 0xC0 (7-bit 0x60).
5. The CSIPHY index and `laneAssign`, `settleTimeNS` and `dataRate` fields per sensor, again for
   the IR and front paths, to confirm CSIPHY 0, 1, 2 and the C-PHY rate class.
6. IMX681: Bayer pattern and the exact mode list (for the libcamera helper and the driver).
7. `qccamflash8380.sys`: the PMIC flash channel of the IR emitter (read only, S2).
