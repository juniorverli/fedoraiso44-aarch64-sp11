# cameras

## 1. Summary

Three cameras behind the Qualcomm CAMSS/Spectra ISP: front Sony IMX681 (Windows Hello RGB), rear OmniVision OV13858, IR STMicro VD55G0 with an IR illuminator, plus flash and privacy LED. Linux 7.3 has CAMSS support code for this SoC and two of the three sensor drivers, but no CAMSS node in the DT. Status: `survey`.

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
- Nothing in the DT.
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| no CAMSS/CCI node in hamoa.dtsi | TBD |
| no IMX681 driver | TBD |
| C-PHY support for the front camera? | TBD |
| sensor power/reset/clock wiring from ACPI | TBD |
| privacy LED binding | TBD |
| RAW Bayer frames need an RGB stage (demosaic, AWB, CCM, gamma) | libcamera Software ISP with per-sensor tuning; Spectra hardware ISP later |
| VD55G0 support in `vd55g1.c` unknown | Check chip ID handling; patch if the register map matches |
| IR illuminator safety (risk S2) | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | CSI PHY per sensor, lanes, D-PHY or C-PHY, I2C/CCI bus and address | TBD | ACPI `_CRS`/`_DSD` of each sensor; `surfacecam*sensor8380.sys` REA |
| Q2 | Power, reset and clock sequence per sensor | TBD | Sensor extension `.bin` files and REA of the sensor drivers |
| Q3 | Is there an upstream CAMSS node for X1E80100 on the list? | TBD | lore linux-arm-msm |
| Q4 | IMX681 register set | TBD | REA of `surfacecamfrontsensor8380.sys` |
| Q5 | Privacy LED wiring (must be on whenever a sensor streams) | TBD | Flash device `QCOM0C27` resources; `cam_indicator_en` (GPIO 225) in DT |
| Q6 | IR illuminator current, timeout, eye-safety class | TBD | REA of `qccamflash8380.sys`; keep disabled (risk S2) |

## 7. Acceptance

1. Rear and front cameras deliver **RGB/YUV** frames (after demosaic) to a libcamera app (`cam`, `qcam`, GNOME Snapshot) with correct colours; RAW-only capture does not count
2. Privacy LED lights whenever any sensor streams
3. IR stays disabled until S2 is cleared

## 8. Requests

- R1 (kernel, operator): none can be written yet. A camera DT/driver patch is blocked: `hamoa.dtsi` has no `camss`/`cci`/CSIPHY nodes in v7.3, CAMSS rejects C-PHY (front IMX681), no IMX681 driver, `ov13858.c` has no OF match, regulators or reset GPIO. Recommended first target: rear OV13858 (D-PHY, 4 lanes, cci0 bus 1, csiphy1).
- R2 (operator, next boot): run the read-only collector in `evidence/2026-10-30-rea-windows.md`; no `i2cdetect` without confirmation.
- R3 (sources): upstream lore check of the CAMSS X1E DT and C-PHY series (no network this session).

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: RAW-to-RGB requirement recorded; OV13858 Bayer order verified.
- 2026-10-30: REA of the Windows camera stack: per-camera CCI, lanes, PHY, reset, clocks, supplies and power-up order recorded in `evidence/2026-10-30-rea-windows.md`; front is C-PHY (unsupported by CAMSS in 7.3).
