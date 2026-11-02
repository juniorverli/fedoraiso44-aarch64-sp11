# cameras

## 1. Summary

Three cameras behind the Qualcomm CAMSS/Spectra ISP: front Sony IMX681 (Windows Hello RGB), rear OmniVision OV13858, IR STMicro VD55G0 with an IR illuminator, plus flash and privacy LED. Linux 7.3 has CAMSS support for this SoC and an OV13858 driver; this series adds camera DT and an IMX681 driver. Status: `testing` (M16 safe boot probes both RGB sensors, but the media graph lacks sensor links and no camera is usable yet).

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
| Front IMX681 | Windows mode data RAW10 RGGB; physical capture not yet checked | yes | Verified in module data and prior analysis; device output TBD | `evidence/2026-10-31-rea-bayer-poll-units.md` |
| IR VD55G0 | Windows mode data monochrome RAW10; no device capture | no demosaic | Verified in module data; device output TBD | `evidence/2026-10-31-rea-bayer-poll-units.md` |

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
| `qccamplatform8380` | Platform driver; privacy LED control |
| `surfacecamplatform_ext8380` | Board-specific platform configuration |
| `qccamisp8380` | TBD |
| `qccamisp_ext8380` | TBD |
| `qccammipicsi8380` | TBD |
| `qccammipicsi_ext8380` | TBD |
| `qccamjpege8380` | TBD |
| `qccamflash8380` | TBD |
| `qccamflash_ext8380` | TBD |
| `qccamsecureisp8380` | TBD |
| `qccamsecureisp_ext8380` | TBD |
| `surfacecamfrontsensor8380` | Front sensor kernel subdriver |
| `surfacecamfrontsensor_extension8380` | Front resources, mode data and tuning |
| `surfacecamrearsensor8380` | Rear sensor kernel subdriver |
| `surfacecamrearsensor_extension8380` | Rear resources, mode data and tuning |
| `surfacecamauxsensor8380` | Auxiliary sensor kernel subdriver |
| `surfacecamauxsensor_extension8380` | Auxiliary resources, mode data and tuning |
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

The current graded upstream and Windows comparison is in [2026-11-02 upstream gap](evidence/2026-11-02-upstream-windows-gap.md). Proceed with the RGB-only graph first; posted PHY API and VD55G0 work require pinning and review, and are not established prerequisites for this test.

| Gap | Planned answer |
|:--|:--|
| no CAMSS/CCI node in hamoa.dtsi | Patch 0003 (disabled nodes, `CHECK_DTBS` clean) |
| IMX681 driver | Patch 0016 and private register data bind; C-PHY, modes and image quality remain untested |
| C-PHY support for the front camera | Patches 0006–0010 implement a legacy-CSIPHY path; compare with the posted standalone PHY API series and validate on device |
| sensor power/reset/clock wiring from ACPI | Rear: patch 0005 (Windows sequence). Front and IR: after the IMX681 and VD55G0 drivers exist |
| privacy LED binding/arbitration | Patch 0020 adds shared `led_classdev` user counting in the V4L2 core; GPIO225 LED node remains disabled; exact GPIO-to-camera mapping remains inference pending independent cross-check (see `evidence/2026-11-01-shared-privacy-led.md`) |
| RAW Bayer frames need an RGB stage (demosaic, AWB, CCM, gamma) | libcamera Software ISP with per-sensor tuning; Spectra hardware ISP later |
| VD55G0 has no matching driver | Keep unbound; add support only after model and register map are verified |
| CCI reset uses an uninitialized master 0 completion when only master 1 is enabled | Patch 0021 initializes every master completion; revision-15 safe boot reaches camera probe, race coverage remains |
| Unbound IR endpoint likely stalls CAMSS async completion and prevents RGB sensor links | Exclude the IR graph from RGB DTs using `dtb-variants/x1-microsoft-denali-camera-no-ir.dtsi`; device validation pending |
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

- **R15 (sources and orchestrator):** pin and review the currently available standalone PHY/CAMSS series and the VD55G0 candidates and follow-ups listed in the [gap evidence](evidence/2026-11-02-upstream-windows-gap.md); complete the listed REA functions with forced catalog language. The REA MCP rejected this worker under approval policy `never`.

- **R13 (kernel, urgent):** apply `dtb-variants/x1-microsoft-denali-camera-no-ir.dtsi` after camera nodes to every camera-enabled CAMSS DT including m15-safe and inherited variants. It removes both IR graph ends and disables CCI0 bus 0 and the IR node. Keep both RGB endpoints enabled only when both sensor drivers and blobs are present; otherwise use the corrected rear-only variant. Confirm effective compiled DT statuses, endpoint phandles, `CONFIG_VIDEO_V4L2_SUBDEV_API`, and DT schema checks. Do not apply this CAMSS graph recipe blindly to the separate Spectra stack. Confirm patch 0021 and 0020 integration and run the shared LED KUnit suite when scheduled. See [M16 probe evidence](evidence/2026-11-02-m16-safe-camera-probe.md).
- **R14 (image):** retain private RGB register blobs and Fedora libcamera SoftISP, IPA, tools, PipeWire and Snapshot; verify the image carries both `userspace/quality/libcamera-sp11.patch` and `libcamera-sp11-imx681-helper.patch`, generated sensor tuning and matching runtime IPA. Report actual installed tuning/helper coverage and packaging provenance. Blob presence alone does not establish correct colour or camera operation. Preserve the camera collector.

- **R12 (kernel, historical):** patch 0021 was requested for integration and the revision-15 safe boot now reaches camera enumeration; confirm its exact build provenance and exercise IRQ/timeout races. Test enabled-child combinations and IRQ/timeout races. The camera-enabled safe boot result is now recorded in the M16 probe evidence; use R13 for the next graph fix. Keep the reviewable [m15-safe camera gate](m16-safe-camera-gate.diff) as the recovery fallback only if the fixed boot still dies; validate compiled effective statuses if using it. The main `m15.dts` inherits this gate; spectra has its own separate downstream stack. Historical camera-enabled debug variants can trigger the same CCI defect and need explicit warnings/gating. The fix does not validate the camera stack or privacy wiring. See [evidence and controlled test plan](evidence/2026-11-01-m16-safe-camera-die.md).

- R1 (kernel): add `hardware/cameras/patches/0001`-`0005` to `kernel/series` in this order (binding, driver, hamoa DT, Denali LED, Denali rear camera); all five apply on the current full series and the DT checks are clean. Confirm `CONFIG_VIDEO_QCOM_CAMSS`, `CONFIG_I2C_QCOM_CCI`, `CONFIG_VIDEO_OV13858`, `CONFIG_LEDS_GPIO`, `CONFIG_CLK_X1E80100_CAMCC` and `CONFIG_REGULATOR_QCOM_RPMH` in the Fedora-based config. Build `hardware/cameras/dtb-variants/x1p64100-microsoft-denali-cam-rear.dts` as a diagnostic variant (`scripts/kernel-dev.sh <id> variant`, tested with `--check`: clean). The driver patch 0002 has never been compiled.
- R2 (operator, next boot): run the collector in `test-plan.md`; no `i2cdetect`.
- R3 (sources): fetch the C-PHY series as mbox files (the earlier survey holds only HTML mirrors in `sources/windows/rea-evidence/camera-cphy/upstream/mirror`): `phy: qcom-mipi-csi2` C-PHY for X1E80100, CAMSS PHY-type tracking, the IMX681 C-PHY RFC and the OV13858 OF series; pin them in `sources/sources.toml`. Also pin `out/ref/camera-driver` (commit `08171dd`, GPL-2.0) as a reference input.
- R4 (image): libcamera with the Software ISP and a per-sensor tuning file for OV13858 (RAW to RGB); the tuning values are derived on the device from the Windows data, not committed (S5).
- R5 (orchestrator, REA slot later): the seven questions at the end of `evidence/2026-10-30-camera-driver-reference.md` (indicator GPIO resource per sensor and polarity, CSIPHY and pm8010 supply parents, PEP delay unit, CCI mapping and speed, IR address and lanes, IMX681 Bayer order and modes, IR emitter channel read-only).
- R6 (firmware): none for the CAMSS path (CAMSS needs no firmware). `CAMERA_ICP.mbn` is only for the unusable Spectra stack and is not staged.
- R8 (kernel, M15): patches 0013 (per-mode media bus code) and 0016 (gain law, digital gain, line-length clock) were amended in place on 2026-10-31; rebuild from the files, nothing else in `patches/` changed. The libcamera image patch set is `userspace/quality/libcamera-sp11.patch` then `libcamera-sp11-imx681-helper.patch`.
- R9 (image): `test-plan.md` and the OV13858 tuning must expect SBGGR10 for blob modes and SGRBG10 for built-in modes.
- R10 (kernel): integrate `patches/0020-media-v4l2-core-refcount-shared-privacy-leds.patch`; the KUnit suite compiled in enabled/disabled configurations but still needs runtime execution.
- R11 (orchestrator): independently cross-check camera-to-privacy-LED GPIO mapping before enabling camera DT nodes; patch 0020 intentionally contains no GPIO values.

## 9. Log

- 2026-11-02: compared available upstream PHY and VD55G0 proposals with the legacy path, documented Windows inputs and REA targets, and corrected the streaming test; REA approval policy blocked new analysis.

- 2026-11-02: safe boot binds both RGB sensors; unbound IR endpoint likely prevents CAMSS completion and sensor links, so prepared RGB-only and rear-only DT exclusions and requested integration; streams and indicators remain unverified.

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: RAW-to-RGB requirement recorded; OV13858 Bayer order verified.
- 2026-10-30: REA of the Windows camera stack: per-camera CCI, lanes, PHY, reset, clocks, supplies and power-up order recorded in `evidence/2026-10-30-rea-windows.md`; front is C-PHY (unsupported by CAMSS in 7.3).
- 2026-10-30: Qualcomm camera-kernel reference cross-check (CSIPHY v2.1.2, CSID 680 layout, CCI v2, C-PHY register sequence, ICP firmware names, Spectra not usable); Sol patches reviewed and replaced by five checked patches (binding, ov13858 OF power, hamoa DT, Denali LED, Denali rear camera), diagnostic DTB variant, test plan; status `designed`.
- 2026-10-31: patches 0013 and 0016 amended (per-mode bus code, verified IMX681 gain law, digital gain, line-length clock), IMX681 libcamera helper patch made real; see `evidence/2026-10-31-bayer-units-gain-crosscheck.md` section 7.
- 2026-11-01: confirmed V4L2 privacy LED arbitration is per-subdevice, added generic shared-classdev refcount patch 0020 and KUnit lifecycle coverage; enabled/disabled ARM64 object builds and module link pass, suite not runtime-executed; GPIO mapping remains unverified.
- 2026-11-01: identified CCI master-0 completion initialization defect for master-1-only probes; requested a recovery DT gate and a separate driver fix; M16 DIE attribution remains unproven.
- 2026-11-01: wrote CCI completion patch 0021; requested integration and a camera-enabled m15-safe test, retaining the DT gate as recovery fallback.
