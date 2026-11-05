# cameras

## 1. Summary

Three cameras behind the Qualcomm CAMSS/Spectra ISP: front Sony IMX681 (Windows Hello RGB), rear OmniVision OV13858, IR STMicro VD55G0 with an IR illuminator, plus flash and privacy LED. Linux 7.3 has CAMSS support for this SoC and an OV13858 driver; this series adds camera DT and an IMX681 driver. Status: `testing` (rev25 safe logs two sensor-mode configurations through CPU SoftISP; the operator reports both cameras green and dark, and previously reported the rear upside down; lens attribution, image quality and physical indicator acceptance remain open). A vendor-data analysis found one concrete colour defect: the libcamera Software ISP clamps white-balance gains at 4.0 while the front module's own calibration needs up to 8.93× red and 4.28× blue. The rev25j image raises that ceiling per sensor from the calibrated ladder (`maxGains`). Quantified against the ten calibrated illuminants, the clamp binds in 2 of 10 for the front (worst 55% red shortfall) and 0 of 10 for the rear, so this is a partial fix and does not explain a rear cast; the per-frame `ColourGains` metadata decides the remaining cause. See [the AWB ceiling evidence](evidence/2026-11-04-awb-gain-ceiling.md).

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
| Rear OV13858 | RAW Bayer 10 bit; base modes report **GRBG**, private blob modes report **BGGR** | yes | Verified in source and blob data; actual capture TBD | `sources/linux/drivers/media/i2c/ov13858.c:1280-1284`; `evidence/2026-10-31-bayer-units-gain-crosscheck.md` |
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
| `qccamisp8380` | Qualcomm ISP kernel driver; package contains ICP firmware |
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
| `surfacecamavs8380` | Camera Device MFT and CamX user-mode package; its AWB/CCM consumers remain under investigation |
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
- Native coverage: **partial** (rev24 safe streams both RGB sensors; orientation, colour and LED acceptance remain open; IR excluded).
- Reference and review: `evidence/2026-10-30-camera-driver-reference.md` (Qualcomm camera-kernel cross-check, upstream coverage, review of the untrusted Sol patches).
- Native Spectra stack (downstream camera-kernel, own UAPI, CamX userspace, signed ICP firmware) is not usable on Linux; the path is upstream CAMSS plus libcamera Software ISP.

## 5. Gaps

The [rev25-menu evidence](evidence/2026-11-04-rev25-green-dark.md) supersedes the earlier front-only quality description: the operator reports both views green and dark. Its two e1 safe configurations strongly match front then rear modes, but lack camera IDs, active routes and saved images; the first `cam -l` in each safe boot also omitted the rear after a busy-link error. Keep the rev24 safe camera stack and RGB-only graph while measuring. The [rev24 reference comparison](evidence/2026-11-03-rev24-reference-comparison.md) is a lead, not proof of a colour or exposure fix.

| Gap | Planned answer |
|:--|:--|
| no CAMSS/CCI node in hamoa.dtsi; CSIPHY mapping too short in rev19 | Patch 0003 adds disabled nodes and fixes PHY and full-VFE sizes; corrected DTB compiled, schema validation pending |
| IMX681 driver | Patch 0016 and private register data produce a rev24 safe RGB stream; physical CFA, gain, timing and image quality remain unvalidated |
| C-PHY support for the front camera | Patches 0006–0010 and 0023 plus rev24 receiver candidates stream safely; active rates, error margins and posted-series reconciliation remain open |
| sensor power/reset/clock wiring from ACPI | Rear: patch 0005 (Windows sequence). Front and IR: after the IMX681 and VD55G0 drivers exist |
| privacy LED binding/arbitration | V4L2 core already controls the sensor privacy LED on stream; patch 0020 adds shared `led_classdev` user counting. Rev19 DT references the indicator for both sensors, but GPIO-to-camera mapping and visible streaming operation need independent cross-check and device test |
| RAW Bayer frames need an RGB stage (demosaic, AWB, CCM, gamma) | libcamera Software ISP with per-sensor tuning; Spectra hardware ISP later |
| VD55G0 has no matching driver | Keep unbound; add support only after model and register map are verified |
| CCI reset uses an uninitialized master 0 completion when only master 1 is enabled | Patch 0021 initializes every master completion; revision-15 safe boot reaches camera probe, race coverage remains |
| Unbound IR endpoint must stay outside RGB graph | Patch 0022 excludes IR; rev19 graph has both RGB sensor links. Keep IR excluded in rev20 |
| CSID-680 drop/crop and VFE-680 write mode | Rev24 carries candidates 0024/0025 and both sensors stream in safe; their individual effects and debug reset causality are not isolated. The 3844-to-3840 reference crop does not match our 3840-wide front modes |
| Reference standalone PHY depends on a generic-PHY refactor absent from v7.3 | Conditional port skeleton in rev24 evidence; legacy 0009 already programs C-PHY. Do not run both PHY owners on the same resources |
| Rear image reported upside down; no sensor rotation control in rev24 | Candidate [0026](patches/0026-candidate-arm64-dts-qcom-denali-rear-camera-rotation.patch) adds rear 180° DT metadata only; validate physical orientation and a separate userspace pixel transform if needed |
| Both views reported green and dark | Identify lenses and measure RAW dark/flat/red/blue, fixed-WB identity versus current CCM, actual exposure/gain and tone. The [private 2.5/3.5 AGC experiment](userspace/quality/libcamera-sp11-rev25-agc-experiment.patch) is a later isolated trial, not a proven fix |
| Collector sometimes discovers only front | The first `cam -l` in each new safe boot encountered a busy rear media link; serialize and record discovery, then identify cameras by full ID and physical occlusion |
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
| Q7 | Is rear correction 180° and is front upright without mirroring? | Rear Inference from operator report; front TBD | Asymmetric target in direct capture, Snapshot preview and saved frames; check propagation/double-rotation |
| Q8 | What causes the reported green on both, and are both physical lenses selected? | AWB/CCM, black and shading hypotheses; lens selection TBD | ID/occlusion test, private RAW dark/flat/red/blue targets and fixed-WB identity/current-CCM offline isolation |
| Q9 | Why are both views reported dark? | Scene/optics, exposure, gain, black, AGC and tone contributions TBD | Controlled scene, mode/timing, actual exposure/gain and RAW/processed signal/noise/clipping |

## 7. Acceptance

1. Front IMX681 first/default and rear OV13858 second in libcamera/portal; both deliver captured **RGB/YUV** frames with correct colours; RAW-only capture does not count
2. Privacy LED lights whenever any sensor streams
3. No camera oops; IR sensor excluded and IR illuminator and flash remain off (S2)

## 8. Requests

Priorities and delivery boundaries for rev25-menu:

1. **Coded now:** existing sensor drivers, per-sensor tuning generator, gamma/rear-black and front-helper patches, the private front AGC A/B candidate and rear metadata candidate 0026. None is a measured green/dark correction; keep the AGC trial deferred until baseline capture.
2. **Device measurement first:** physical lens/LED identification, active route and formats, paired RAW and processed dark/flat/red/blue captures, applied/read-back controls, tone and orientation, as in the [new test plan](test-plan.md).
3. **Private libcamera/tuning build if required:** add sensor-identified diagnostic capture and a safe fixed-control path; after measuring, trial a single per-sensor black, AWB or CCM change with matching private baseline and provenance. A rear-only processed 180° conversion is a separate candidate if the consumer needs it.
4. **New kernel/DTB if required:** 0026 provides rear mounting metadata only after physical confirmation; a real sensor flip or OV13858 selection rectangles needs independently verified registers/crops and review. Preserve rollback and BTF; no front rotation, double transform or speculative Bayer/gain change.

- **R36 (image/collector):** in both safe boots the first collector `cam -l` reported rear `csiphy1 -> csid0` busy and listed only front; its second invocation listed both. Prevent overlapping camera discovery where possible, run one recorded enumeration after competing initialization settles, and mark `EBUSY` or partial discovery explicitly. Log complete camera IDs and timestamps; do not turn an index or failed enumeration into a sensor assignment. Verify direct capture and Snapshot with per-lens occlusion. The current evidence does not identify the owner of the busy link.
- **R37 (image/libcamera):** provide an isolated private diagnostic that records camera ID, active route/mode/stride, request sequence, actual loaded tuning/IPA/helper hashes, frame CCM/gains, and requested, reported and independently timed applied exposure/gain. Allow paired RAW/processed capture and safe fixed controls, if supported, with the AGC loop suspended and the existing LED gate intact. Preserve missing-data markers. Trial fixed WB and identity versus current CCM offline on the same RAW before proposing sensor-specific tuning. Do not copy Windows coefficients into git or a public image.

- **R32 (kernel, rev25 orientation):** review and build candidate [0026](patches/0026-candidate-arm64-dts-qcom-denali-rear-camera-rotation.patch) on the verified rev24 stack, with BTF and DT schema/effective-DTB checks. It exposes rear 180° rotation metadata only; it is not an automatic pixel rotation. Keep rollback DTB, both sensors' existing routing and privacy LEDs, and no IR/flash. Verify both sensor controls and front/rear physical orientation with an asymmetric target before promotion.
- **R33 (image/userspace, rev25 quality):** provide the [rev25 test plan](test-plan.md) capture tools, actual package/IPA/helper/YAML/blob hashes, per-frame metadata and LED-observed RAW plus processed capture. If the rear consumer ignores rotation metadata, test a rear-only processed-frame 180° transform without double rotation; do not alter Bayer or front orientation. For fixed-exposure/gain measurements, first verify whether simple IPA exposes manual controls; if not, prepare an isolated diagnostic path that suspends the AGC loop, reports requested/applied controls and maintains the kernel LED gate. No raw sensor pokes or raised limits.
- **R34 (image/userspace, private rev25 AGC, deferred until measurements justify it):** build a separate Fedora 0.7.2 IPA with [per-sensor experiment patch](userspace/quality/libcamera-sp11-rev25-agc-experiment.patch), generate private paired front tuning with [prepare-rev25-agc.py](userspace/quality/prepare-rev25-agc.py), and A/B 2.5 versus 3.5 under the same patched IPA, scene and rev24 safe stack. Verify loaded path/hash and log target; keep rear at its original target, preserve original package/tuning and measure clipping, signal/noise, exposure and gain. Do not ship Windows-derived matrices in git or a public image. Calibrate AWB/CCM separately from RAW evidence.
- **R35 (GPU owner, rev24 handoff):** safe boot `f736d653` processed 30 frames for each sensor and the operator saw both streams; debug `e28d7229` still reset. The safe result is not proof of a debug root cause or of any one candidate's effect. Please continue your matched GPU-only/reset capture and share only the resulting reset discriminator; camera quality testing stays on safe. The local Orca runtime was not running, so this is a recorded handoff, not confirmation of delivery.

- **R29 (kernel, historical rev24 request; candidates included in rev24):** preserve rev23 as control. Review [0024 CSID](patches/0024-candidate-media-qcom-camss-csid-680-disable-unconfigured-drop-crop.patch) and [0025 VFE](patches/0025-candidate-media-qcom-camss-vfe-680-use-mipi-raw-mode.patch) as separate candidates after active clock/IRQ evidence; validate full/lite RDI, stride and buffers, run integrated BTF build and retain patch provenance. Neither is proven to fix the reset. Follow the conditional generic-PHY port skeleton in [rev24 evidence](evidence/2026-11-03-rev24-reference-comparison.md) if front-only evidence isolates the legacy path. Do not change 0023 rates/header fields speculatively or run overlapping MMIO providers.
- **R30 (kernel/image, private sensor timing):** retain the rev23 private front blob and its exact hash. Only after stable front reception and observed line loss/overflow, prepare the mode-specific 6752-to-8704 HTS/register experiment with VTS 3554 and all other sensor/PLL values unchanged as specified in [rev24 evidence](evidence/2026-11-03-rev24-reference-comparison.md); keep all Windows-derived mode/tuning data private and make it a separate boot. Gain inversion and digital-gain remapping remain unverified and must be measured, not copied.
- **R31 (image/userspace, rev24; AGC comparison superseded by per-sensor R34):** record actual Fedora 0.7.2 IPA/helper/tuning/renderer and gain/AE metadata; retain safe-only softpipe A/B and preserve WirePlumber core, service hardening and Mesa/LLVM versions. Use R34 for the later isolated per-sensor AGC comparison; calibrate private CCM/black/WB from RAW targets. Do not import the reference polling LED, broad restart watchdog or unverified JIT hardening override.

- **R25 (image, rev23):** include `/usr/libexec/sp11-camera-spectra-guard` and its shell/runtime dependencies in the initramfs whenever its modprobe install configuration is included, or safely defer and explicitly retrigger guarded module loading after switch-root. Test both CAMSS and Spectra DTs and verify the mutually exclusive stacks cannot claim the same resources. Rev22 safe early load failed with 127 but rootfs retry succeeded. Preserve BTF, S2 and LED gate. See [rev23 evidence](evidence/2026-11-03-rev23-final32-camera.md).
- **R26 (image/userspace and kernel, historical rev22 crash):** rev24 safe softpipe now streams both; retain the earlier llvmpipe coredump and package provenance for separate diagnosis; provide sensor-identified stream entry/return instrumentation, completed buffer metadata, active media routes and clocks/IRQ logs for the [rev23 matrix](test-plan.md). Coordinate GPU-only vs camera trials with GPU owner. Headless `cam` can still initialize EGL/llvmpipe. Do not claim the debug reset as camera-caused without the matched A/B.
- **R28 (sources/REA):** continue listed-function REA of rear sensor mode/control handling and catalogued ISP/ICP with forced languages, function addresses and evidence IDs; the new session confirms Windows platform LED reference counting and front configuration parsing but does not establish hardware CFA, gain or HDR. See [rev23 evidence](evidence/2026-11-03-rev23-final32-camera.md).
- **R27 (kernel/image):** retain existing 0013 per-mode GRBG built-in/BGGR blob handling, verify the integrated image exposes both and collect active mode and RAW colour-target evidence before changing CFA or regenerating blobs. Derive and independently cross-check OV13858 selection rectangles; do not fabricate them or alter 0023 without active evidence. Confirm actual IPA/helper/tuning hashes and measured exposure/gain, crop, black and tone data before quality changes.

- **R23 (image; enumeration completed in rev22):** the three-control IMX681 blob now permits both sensors to enumerate. Retain its provenance and verify the full installed hash and actual control ranges; assumed CCS registers and gain law still require physical validation. See [M16 evidence](evidence/2026-11-03-m16-camera-stream-quality.md) and [rev23 evidence](evidence/2026-11-03-rev23-final32-camera.md).
- **R24 (kernel/image/operator):** use the reset-resilient capture plan to distinguish camera stream start, completed buffers and GPU rendering, and obtain active clock/IRQ data before changing patch 0023. Derive OV13858 native/active and per-mode crop geometry before implementing `get_selection`; avoid fabricated rectangles. Preserve privacy LED and S2 gates.

- **R19 (kernel, rev21):** integrate `patches/0023-media-qcom-camss-use-hamoa-cphy-clock-votes.patch` after the complete rev20 camera series, without changing rev20 patch 0003. Preserve BTF, run the integrated build and verify exact patch provenance, D-PHY behavior and shared clock interactions. The local W=1 CAMSS object build passed; independent cross-check and device streaming remain open. See [clock evidence](evidence/2026-11-02-cphy-clock-fix.md).
- **R20 (sources):** pin Qualcomm Hamoa camera DT at `17bbb4b37bbc4fc5827b4667445a0c43967c0f48`, including the `hamoa-camera.dtsi` hash in the clock evidence; pin camera-driver `08171ddc9d6ad81c13e6f1b362248d4736b0e804` and the posted X1E C-PHY PHY/CAMSS series mboxes, including [PHY RFC v3](https://lists.openwall.net/linux-kernel/2026/10/16/2163), with provenance and hashes. Reconcile the posted revisions with patches 0006–0010 and 0023.
- **R21 (image):** verify the installed front IMX681 SoftISP sensor helper, IPA and matching tuning data and their actual package/runtime paths; report coverage and colour-validation gaps. Preserve the camera collector and logs. This request does not change the image in this session.
- **R22 (orchestrator):** arrange the protocol §5.1 independent cross-check of the Hamoa PHY/core/timer and CSID nominal votes, shared clock parents and CSID capture fields before promotion to `sw-ready`; keep physical LED wiring verification as the separate R11 gate.

- **R17 (kernel, rev20):** assemble series rev20 using the corrected `patches/0003-arm64-dts-qcom-hamoa-describe-disabled-camera-blocks.patch` (four PHYs at `0x2000`, both full VFEs at `0xf000`), plus camera series and RGB-only IR exclusion. Check all 17 compiled CAMSS resources, effective IR exclusion and `CHECK_DTBS`/schema validation in the integrated DTBs; publish those variants and retain BTF. The standalone v7.3 DTB compiles; normal make was blocked by missing `flex` and schema tooling was unavailable locally. See [register audit](evidence/2026-11-02-csiphy-mapping-oops.md).
- **R18 (image, rev20):** make IMX681 the first libcamera camera and portal default, OV13858 second; ship the front/rear SoftISP helpers and tuning, and verify actual enumeration, qcam/default portal preview and saved RGB/YUV capture on both, front first. Preserve read-only graph and kernel logs after stream attempts; include visible privacy LED on/off and no-oops checks in the device run. Keep IR excluded and flash/IR illuminator off (S2). See [test plan](test-plan.md).

- **R15 (sources and orchestrator):** pin and review the currently available standalone PHY/CAMSS series and the VD55G0 candidates and follow-ups listed in the [gap evidence](evidence/2026-11-02-upstream-windows-gap.md); complete the listed REA functions with forced catalog language. The REA MCP rejected this worker under approval policy `never`.

- **R13 (kernel, urgent):** apply `dtb-variants/x1-microsoft-denali-camera-no-ir.dtsi` after camera nodes to every camera-enabled CAMSS DT including m15-safe and inherited variants. It removes both IR graph ends and disables CCI0 bus 0 and the IR node. Keep both RGB endpoints enabled only when both sensor drivers and blobs are present; otherwise use the corrected rear-only variant. Confirm effective compiled DT statuses, endpoint phandles, `CONFIG_VIDEO_V4L2_SUBDEV_API`, and DT schema checks. Do not apply this CAMSS graph recipe blindly to the separate Spectra stack. Confirm patch 0021 and 0020 integration and run the shared LED KUnit suite when scheduled. See [M16 probe evidence](evidence/2026-11-02-m16-safe-camera-probe.md).
- **R14 (image):** retain private RGB register blobs and Fedora libcamera SoftISP, IPA, tools, PipeWire and Snapshot; verify the image carries both `userspace/quality/libcamera-sp11.patch` and `libcamera-sp11-imx681-helper.patch`, generated sensor tuning and matching runtime IPA. Report actual installed tuning/helper coverage and packaging provenance. Blob presence alone does not establish correct colour or camera operation. Preserve the camera collector.
- **R16 (image, rev19):** install `hardware/cameras/collector/cameras.sh` as `/etc/sp11-log-collector.d/cameras.sh` in the collector drop-in and confirm the next device bundle contains `extra-cameras.txt`. The drop-in has a 90-second total deadline: keep graph/format collection ahead of slower diagnostics and preserve its explicit timeout/incomplete markers. Its media graph and V4L2 format collection has a 55-second budget, with per-command timeouts, and records every media node, device enumeration, each `/dev/video*` format/size list, subdevice formats/capabilities and relevant dmesg lines. It is read-only and never streams, writes sensor registers, or operates IR/flash. See [rev18 black-preview evidence](evidence/2026-11-02-rev18-black-preview.md).

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

- 2026-11-04 (AWB ceiling): found that the Software ISP clamps red/blue white-balance gains at 4.0 while the front module's calibrated ladder reaches 8.93× red and 4.28× blue; added the `maxGains` tuning key through `libcamera-sp11-awb-fixed-gains.patch`, derived per-sensor ceilings in the generator (front 9.83/4.71, rear 4.07/4.00), and a structural check over the catalogued containers. Quantified: the stock ceiling clips 2 of 10 calibrated front illuminants (worst 55% red shortfall) and none on the rear; the derived ceiling clips none. Added `awb-report.sh` to the image so the applied gains can be read in one command on the device. No colour claim until the device report exists.

- 2026-11-04: traced rev25 safe sensor-mode configurations and transient rear enumeration failure; documented both reported green/dark views, measurement priorities, and separate metadata, userspace and device work.

- 2026-11-03: recorded rev24 safe dual RGB streams, corrected sensor/range attribution, prepared rear rotation metadata candidate and a private per-sensor AGC experiment, and requested rev25 measured quality/LED tests and GPU handoff.

- 2026-11-03: Rev22 safe configured front then WirePlumber SIGSEGV; mode-dependent Bayer and early guard retry clarified; rev23 A/B and LED-gated quality matrix added.

- 2026-11-03: analyzed three M16 boots; rear-only libcamera enumeration and missing front controls are established, but app mode, stream completion, reset cause and quality causes remain unproven; added front-blob and reset-resilient diagnostic proposals.

- 2026-11-02: prepared rev21 patch 0023 for C-PHY nominal clock votes and CSID header capture; W=1 ARM64 CAMSS objects pass with BTF options enabled, while cross-check, integrated build, active rates and device streaming remain open.

- 2026-11-02: fixed four CSIPHY and two full VFE mapping windows, audited all CAMSS resources, compiled a v7.3 Denali DTB and requested rev20 integration and front-first capture; device streaming and schema validation remain pending.

- 2026-11-02: audited rev19 RGB graph and privacy LED; reciprocal endpoints and local lane numbering permit notifier completion, but runtime graph and indicator wiring remain unverified; see [audit](evidence/2026-11-02-rev19-graph-led-audit.md).
- 2026-11-02: compared available upstream PHY and VD55G0 proposals with the legacy path, documented Windows inputs and REA targets, and corrected the streaming test; REA approval policy blocked new analysis.

- 2026-11-02: safe boot binds both RGB sensors; unbound IR endpoint likely prevents CAMSS completion and sensor links, so prepared RGB-only and rear-only DT exclusions and requested integration; streams and indicators remain unverified.
- 2026-11-02: rev18 OV13858 loads three modes but no graph/capture was recorded; expanded the read-only collector and test plan to distinguish notifier, route/format, PHY/CSID, sensor mode and SoftISP failures; no concrete defect chosen pending evidence.

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: RAW-to-RGB requirement recorded; OV13858 Bayer order verified.
- 2026-10-30: REA of the Windows camera stack: per-camera CCI, lanes, PHY, reset, clocks, supplies and power-up order recorded in `evidence/2026-10-30-rea-windows.md`; front is C-PHY (unsupported by CAMSS in 7.3).
- 2026-10-30: Qualcomm camera-kernel reference cross-check (CSIPHY v2.1.2, CSID 680 layout, CCI v2, C-PHY register sequence, ICP firmware names, Spectra not usable); Sol patches reviewed and replaced by five checked patches (binding, ov13858 OF power, hamoa DT, Denali LED, Denali rear camera), diagnostic DTB variant, test plan; status `designed`.
- 2026-10-31: patches 0013 and 0016 amended (per-mode bus code, verified IMX681 gain law, digital gain, line-length clock), IMX681 libcamera helper patch made real; see `evidence/2026-10-31-bayer-units-gain-crosscheck.md` section 7.
- 2026-11-01: confirmed V4L2 privacy LED arbitration is per-subdevice, added generic shared-classdev refcount patch 0020 and KUnit lifecycle coverage; enabled/disabled ARM64 object builds and module link pass, suite not runtime-executed; GPIO mapping remains unverified.
- 2026-11-01: identified CCI master-0 completion initialization defect for master-1-only probes; requested a recovery DT gate and a separate driver fix; M16 DIE attribution remains unproven.
- 2026-11-01: wrote CCI completion patch 0021; requested integration and a camera-enabled m15-safe test, retaining the DT gate as recovery fallback.

- 2026-11-03: compared the pinned rev24 front-camera reference, prepared separate CSID/VFE review candidates, documented conditional standalone PHY port and private timing/quality experiments; reset cause remains unproven.
