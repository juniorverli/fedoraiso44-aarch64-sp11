# cameras

## 1. Summary

Three cameras behind the Qualcomm CAMSS/Spectra ISP: front Sony IMX681 (Windows Hello RGB), rear OmniVision OV13858, IR STMicro VD55G0 with an IR illuminator, plus flash and privacy LED. Linux 7.3 has CAMSS support code for this SoC and two of the three sensor drivers, but no CAMSS node in the DT. Status: `designed` (rear path staged as disabled DT plus driver patches, front blocked on C-PHY and a driver).

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_SONY&DEV_0681&SUBSYS_MSHW0490` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_OVTI&DEV_D858&SUBSYS_MSHW0491` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_SMO&DEV_55F0&SUBSYS_MSHW0492` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C32&SUBSYS_MSHW0495 (platform)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C25 (ISP)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C98 (MIPI CSI)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C27 (flash)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C33 (JPEG)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CCC (SecureISP)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CF1 (EVA)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

### Image pipeline: the sensors deliver RAW, RGB must be produced at the end

The RGB sensors output **RAW Bayer** frames (one colour sample per pixel behind a colour filter array), not RGB. CAMSS on Linux only receives and writes these RAW frames to memory; it does not demosaic. A usable colour picture needs a processing stage after capture that does at least: **demosaic (Bayer to RGB)**, black-level subtraction, white balance, colour correction matrix, gamma, and then conversion to the format apps consume (RGB or YUV/NV12).

| Sensor | Output from the sensor | Needs RGB stage | Grade | Source |
|:--|:--|:--|:--|:--|
| Rear OV13858 | RAW Bayer 10 bit, order **GRBG** only (`MEDIA_BUS_FMT_SGRBG10_1X10`) | yes | Verified | `sources/linux/drivers/media/i2c/ov13858.c:1280-1284` |
| Front IMX681 | RAW Bayer; bit depth and order TBD (no Linux driver) | yes | Inference (RGB Bayer sensor) / TBD (order) | REA of `surfacecamfrontsensor8380.sys` |
| IR VD55G0 | monochrome (Y8/Y10), no colour filter | no demosaic; only black level and gamma | Inference | `vd55g1.c` handles a mono variant (`vd55g1_mbus_formats_mono`); whether it supports VD55G0 at all is TBD (no `vd55g0` string in 7.3) |

Where the RGB stage can run on Linux:

1. **libcamera Software ISP** (CPU/GPU), the realistic first path. Needs a tuning file per sensor (black level, CCM, lens shading). The Windows tuning blobs (`com.surface.tuned.*.bin` in the `surfacecam*_extension8380` packages) are a possible source of these values, after REA of their format.
2. **Spectra hardware ISP (IFE/BPS/IPE)** via the ICP firmware `CAMERA_ICP.mbn` (Xtensa). No upstream Linux driver; long-term only.

A camera counts as working only when an app receives **RGB/YUV** frames with correct colours, not when CAMSS delivers RAW.

Why CAMSS cannot do the RGB stage on this SoC (Verified, 2026-10-24):

- X1E80100 VFEs (`vfe0`, `vfe1`, `vfe_lite0`, `vfe_lite1`) all use `vfe_ops_680` (`sources/linux/drivers/media/platform/qcom/camss/camss.c`, `vfe_res_x1e80100`), and `camss-vfe-680.c:105` states: "This macro only works because RDI is all we support right now." RDI is the raw dump interface that bypasses the processing pipeline.
- Even on the old SoCs where Linux drives the VFE PIX path (MSM8916, MSM8996; kernel documentation `media/v4l-drivers/qcom_camss`, v4.20), PIX only converts packed YUV 4:2:2 to NV12/NV16, crops and downscales up to 16x. It never demosaics Bayer. So the RGB stage is always outside CAMSS: libcamera Software ISP now, Spectra BPS/IPE (no Linux driver) later.

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qccamplatform8380` | TBD |
| `surfacecamplatform_ext8380` | TBD |
| `qccamisp8380` | TBD |
| `qccamisp_ext8380` | TBD |
| `qccammipicsi8380` | TBD |
| `qccammipicsi_ext8380` | TBD |
| `qccamjpege8380` | TBD |
| `qccamflash8380` | TBD |
| `qccamflash_ext8380` | TBD |
| `qccamsecureisp8380` | TBD |
| `qccamsecureisp_ext8380` | TBD |
| `surfacecamfrontsensor8380` | TBD |
| `surfacecamfrontsensor_extension8380` | TBD |
| `surfacecamrearsensor8380` | TBD |
| `surfacecamrearsensor_extension8380` | TBD |
| `surfacecamauxsensor8380` | TBD |
| `surfacecamauxsensor_extension8380` | TBD |
| `surfacecamavs8380` | TBD |
| `surfacecamavspro_ext8380` | TBD |
| `qceva8380` | TBD |
| `qceva_ext8380` | TBD |
| `mep_camera_component` | TBD |

## 4. Linux 7.3

- Driver: `media/platform/qcom/camss (x1e80100 tables)`
- Driver: `clk/qcom/camcc-x1e80100`
- Driver: `i2c-qcom-cci`
- Driver: `media/i2c/ov13858`
- Driver: `media/i2c/vd55g1`
- Driver: `userspace: libcamera SoftISP`
- Nothing in the DT of v7.3; the series adds disabled `cci0`, `cci1`, `camss`, the pm8010 regulators, the rear sensor and the camera indicator LED (`patches/0001`-`0005`).
- Native coverage: **partial** (rear: designed, untested; front and IR: blocked).
- Reference and review: `evidence/2026-10-30-camera-driver-reference.md` (Qualcomm camera-kernel cross-check, upstream coverage, review of the untrusted Sol patches).
- Native Spectra stack (downstream camera-kernel, own UAPI, CamX userspace, signed ICP firmware) is not usable on Linux; the path is upstream CAMSS plus libcamera Software ISP.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| no CAMSS/CCI node in hamoa.dtsi | Patch 0003 (disabled nodes, `CHECK_DTBS` clean) |
| no IMX681 driver | New driver needed (C-PHY, register tables derived on the device, not in git, S5) |
| C-PHY support for the front camera | Not in v7.3. Backport the posted `phy: qcom-mipi-csi2` C-PHY and CAMSS PHY-type series (request R5); CSIPHY v2.1.2 C-PHY tables and CSID `CFG0` bit 24 are confirmed by the camera-kernel reference |
| sensor power/reset/clock wiring from ACPI | Rear: patch 0005 (Windows sequence). Front and IR: after the IMX681 and VD55G0 drivers exist |
| privacy LED binding | `leds`/`led-names = "privacy"` through the V4L2 core; GPIO225 LED node in patch 0004 (disabled); GPIO105 function Unknown (REA question 1) |
| RAW Bayer frames need an RGB stage (demosaic, AWB, CCM, gamma) | libcamera Software ISP with per-sensor tuning; Spectra hardware ISP later |
| VD55G0 support in `vd55g1.c` unknown | Check chip ID handling; patch if the register map matches |
| IR illuminator safety (risk S2) | Never described in any DT; stays off |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | CSI PHY per sensor, lanes, D-PHY or C-PHY, I2C/CCI bus and address | Partly Verified (see `evidence/2026-10-30-rea-windows.md` and the reference file); 7-bit addresses Inference | ACPI `_CRS`/`_DSD` of each sensor; `surfacecam*sensor8380.sys` REA |
| Q2 | Power, reset and clock sequence per sensor | TBD | Sensor extension `.bin` files and REA of the sensor drivers |
| Q3 | Is there an upstream CAMSS node for X1E80100 on the list? | Unknown | lore linux-arm-msm; the series is not needed, patch 0003 carries the node |
| Q4 | IMX681 register set | TBD | REA of `surfacecamfrontsensor8380.sys` |
| Q5 | Privacy LED wiring (must be on whenever a sensor streams) | GPIO225 Inference (strong); GPIO105 Unknown | Flash device `QCOM0C27` resources; `cam_indicator_en` (GPIO 225) in DT |
| Q6 | IR illuminator current, timeout, eye-safety class | TBD | REA of `qccamflash8380.sys`; keep disabled (risk S2) |

## 7. Acceptance

1. Rear and front cameras deliver **RGB/YUV** frames (after demosaic) to a libcamera app (`cam`, `qcam`, GNOME Snapshot) with correct colours; RAW-only capture does not count
2. Privacy LED lights whenever any sensor streams
3. IR stays disabled until S2 is cleared

## 8. Requests

- R1 (kernel): add `hardware/cameras/patches/0001`-`0005` to `kernel/series` in this order (binding, driver, hamoa DT, Denali LED, Denali rear camera); all five apply on the current full series and the DT checks are clean. Confirm `CONFIG_VIDEO_QCOM_CAMSS`, `CONFIG_I2C_QCOM_CCI`, `CONFIG_VIDEO_OV13858`, `CONFIG_LEDS_GPIO`, `CONFIG_CLK_X1E80100_CAMCC` and `CONFIG_REGULATOR_QCOM_RPMH` in the Fedora-based config. Build `hardware/cameras/dtb-variants/x1p64100-microsoft-denali-cam-rear.dts` as a diagnostic variant (`scripts/kernel-dev.sh <id> variant`, tested with `--check`: clean). The driver patch 0002 has never been compiled.
- R2 (operator, next boot): run the collector in `test-plan.md`; no `i2cdetect`.
- R3 (sources): fetch the C-PHY series as mbox files (the earlier survey holds only HTML mirrors in `sources/windows/rea-evidence/camera-cphy/upstream/mirror`): `phy: qcom-mipi-csi2` C-PHY for X1E80100, CAMSS PHY-type tracking, the IMX681 C-PHY RFC and the OV13858 OF series; pin them in `sources/sources.toml`. Also pin `out/ref/camera-driver` (commit `08171dd`, GPL-2.0) as a reference input.
- R4 (image): libcamera with the Software ISP and a per-sensor tuning file for OV13858 (RAW to RGB); the tuning values are derived on the device from the Windows data, not committed (S5).
- R5 (orchestrator, REA slot later): the seven questions at the end of `evidence/2026-10-30-camera-driver-reference.md` (indicator GPIO resource per sensor and polarity, CSIPHY and pm8010 supply parents, PEP delay unit, CCI mapping and speed, IR address and lanes, IMX681 Bayer order and modes, IR emitter channel read-only).
- R6 (firmware): none for the CAMSS path (CAMSS needs no firmware). `CAMERA_ICP.mbn` is only for the unusable Spectra stack and is not staged.
- R8 (kernel, M15): patches 0013 (per-mode media bus code) and 0016 (gain law, digital gain, line-length clock) were amended in place on 2026-10-31; rebuild from the files, nothing else in `patches/` changed. The libcamera image patch set is `userspace/quality/libcamera-sp11.patch` then `libcamera-sp11-imx681-helper.patch`.
- R9 (image): `test-plan.md` and the OV13858 tuning must expect SBGGR10 for blob modes and SGRBG10 for built-in modes.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: RAW-to-RGB requirement recorded; OV13858 Bayer order verified.
- 2026-10-30: REA of the Windows camera stack: per-camera CCI, lanes, PHY, reset, clocks, supplies and power-up order recorded in `evidence/2026-10-30-rea-windows.md`; front is C-PHY (unsupported by CAMSS in 7.3).
- 2026-10-30: Qualcomm camera-kernel reference cross-check (CSIPHY v2.1.2, CSID 680 layout, CCI v2, C-PHY register sequence, ICP firmware names, Spectra not usable); Sol patches reviewed and replaced by five checked patches (binding, ov13858 OF power, hamoa DT, Denali LED, Denali rear camera), diagnostic DTB variant, test plan; status `designed`.
- 2026-10-31: patches 0013 and 0016 amended (per-mode bus code, verified IMX681 gain law, digital gain, line-length clock), IMX681 libcamera helper patch made real; see `evidence/2026-10-31-bayer-units-gain-crosscheck.md` section 7.
