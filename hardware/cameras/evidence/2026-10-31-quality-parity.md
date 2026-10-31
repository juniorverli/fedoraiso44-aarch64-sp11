# Cameras: Windows image quality on Linux (libcamera Software ISP tuning)

Date: 2026-10-31. Static analysis of the Windows CamX tuned binaries plus a reading of libcamera v0.7.2
(`out/ref/libcamera`, tag commit `191e202178f02430b5942397c70d215cdd2056fa`). No REA call, no device access, no kernel build.
Structure only: no tuning value appears in this file or in anything the tools print (S5). The generator output is private.

Tools (all new files, `hardware/cameras/userspace/quality/`):

| File | Job |
|:--|:--|
| `build-libcamera-tuning.py` | Parses the tuned binaries as data, `--inventory` prints structure, otherwise emits `ov13858.yaml` and `imx681.yaml` (plus an LSC sidecar and a hash manifest) into `out/firmware-private/cameras/libcamera/`, mode 600; refuses a non-ignored directory inside git |
| `validate-tuning.sh`, `validate-tuning.cpp` | Loads a tuning file with libcamera's own `YamlParser` and runs the reads of `BlackLevel::init` and `Ccm::init` (`Interpolator<Matrix<float,3,3>>::readYaml`) inside the Fedora 44 container; prints counts and OK/FAIL |
| `libcamera-sp11.patch` | Two small libcamera changes (tuned default gamma, OV13858 black level); applies clean on v0.7.2 and the touched objects were rebuilt |
| `libcamera-sp11-imx681-helper.patch` | IMX681 `CameraSensorHelper` with the reciprocal gain law (2026-10-31; applies after `libcamera-sp11.patch` on v0.7.2) |

## What "original quality" can and cannot mean

The Windows picture is produced by the Qualcomm Spectra hardware ISP (IFE, BPS, IPE) running CamX with tuned parameters, plus Windows
Studio Effects on the NPU. Linux cannot use that ISP (needs the proprietary CamX userspace and signed ICP firmware, see
`2026-10-30-camera-driver-reference.md`). The achievable target is: **same black level, same colour rendering per illuminant (CCM),
similar tone curve, sensor-correct Bayer order**, from the Windows data, in libcamera's Software ISP. The following Windows features
have **no Linux equivalent** in 0.7.2 and the operator must expect the picture to differ there:

| Windows feature | Why it cannot be replicated |
|:--|:--|
| Lens shading correction (`lsc41`, 4 to 14 meshes per sensor by CCT) | The simple IPA has no LSC stage in 0.7.2 (`src/libcamera/software_isp/TODO.md` lists "Lense shading correction: WIP"). Vignetting and colour shading at the corners stay uncorrected. The mesh is saved in the private sidecar for a future stage |
| Hardware denoise: ANR10, TF21 (temporal filter), HNR10, LENR10, ABF in `bpcabf41`, `swabf10` | The Software ISP has no denoise ("Denoising: WIP"). Low light will be noisier and the AGC will not trade noise for exposure as Windows does |
| Sharpening ASF34, `swasf10`, `cs20`, `cv12`, `sce11` | None in the Software ISP |
| Multi-frame and temporal processing (`mf12`, `tf21`, `mrc10`, `nrm11`, `qll20`) | Not available; one frame in, one frame out |
| HDR (`hdr40`, `hdr50`, `hdr10p10`, `shdr10`, `hdrvideo10`, `remosaic10`, `qpdpc10` for the SFE) | No HDR path in the simple pipeline |
| Tone mapping GTM13, LTM16, `bgtm10`, `bltm10`, `tmc14` | Only a global power-law gamma and a contrast knob exist; the Windows 257 entry LUT is replaced by a fitted exponent |
| Defect and green imbalance: `bpcabf41`, `pdpc31`, `gic31`, `lcac11`, `cac23` | None |
| AWB: Windows uses reference points per illuminant (`refPtV1`, `referenceCCTs`, `custRefPtV1`, `temporalAWBV1`) and scene analysis | Software ISP AWB is grey-world with a fixed generic CCT estimate; no tuning input |
| AEC: 43 `aecx*` blocks (metering, convergence, flash, face) | Software ISP AGC is a histogram MSV loop with fixed constants; no tuning input |
| Per-lux CCM and per-lux tone curve | `Ccm` interpolates by CCT only; the lowest lux-index bin (normal light) is used |
| Autofocus (rear), face assist, auto scene detection, EIS/LDC (`ldc11`, `eis14`) | Out of scope for the Software ISP |
| Windows Studio Effects (background blur, eye contact, auto framing) | NPU and Windows-only; not part of the camera pipeline |

Honest summary: with the generated files the rear and front pictures get Windows black level and Windows colour matrices per colour
temperature and a Windows-like tone exponent. They will not match Windows for shading, noise, sharpness, dynamic range and white-balance
decisions. The colour result depends on libcamera's grey-world AWB, whose CCT estimate is generic (see Inference 6).

## Verified

| Fact | Evidence |
|:--|:--|
| The tuned files are QTI Chromatix containers like the sensor module files: same magic, header, 3 sections (symbol table, data heap, 20-byte or larger trailer), 0x38-byte symbol records, CRC-32 trailer valid. Symbol indices are unique 1..N but not in file order (the first record is not index 1); counts: rear 17731 symbols (493 names), front 58749 (493), IR 8276 (497). The module-data reader `parse-camera-module.py` rejects them only because it requires index order; the new reader does not | `com.surface.tuned.rfc_ov13858.bin` (2595518 bytes), `com.surface.tuned.ffc_imx681.bin` (6465007), `com.surface.tuned.aux_vd55g0_MSHW0492.bin` (1086298); sha256 prefixes `4858ccb297eeecbc`, `2c1c7fd9090e0bf3`, `41518f81eadb61e8`; `build-libcamera-tuning.py --inventory` |
| Inputs per sensor: the unsuffixed tuned file of each package (rear package `surfacecamrearsensor_extension8380`, front `surfacecamfrontsensor_extension8380`, IR `surfacecamauxsensor_extension8380`, file `..._MSHW0492`). Other tuned files in the packages (`rfc_ov13858_MSHW0561`, `ffc_ov02c10*`, `aux_vd55g1`, `aux_..._MSHW0472`, `com.qti.tuned.default.bin`) belong to other SKUs or sensors | file names against the module data evidence |
| Object model of a processing module: root object `<block>_<stage>_v2` (stage `bps`, `ife`, `ipe`, `sfe`, `sw`, `aon`, `ife_lite`) holding `(count, symbol)` pairs for `revision`, `control_var_type` (u32 codes) and `mod_<block>_trigger_data`; the trigger tree is `{f32 lo, f32 hi, u32 n_children, u32 children, u32 n_regions, u32 regions}` (24 bytes, nested one level per control variable); the leaf region holds the parameter block. 84 distinct processing modules per file | decoded by `build-libcamera-tuning.py`, structure checked on all three files |
| Block layouts that matter: `cc13_*` leaf = 48 bytes: 9 floats (3x3) + 3 int offsets (all zero); `demuxblklevel14_*` leaf = 16 bytes: 4 floats; `gamma15_*` leaf = 3084 bytes: 3 channels x 257 floats, channels equal, first entry 0, monotonic; `lsc41_*` leaf = 3568 bytes: 884 floats (4 x 221) + 8 words; `wb20_*` leaf = 32 bytes; `bls12_*` leaf = 20 bytes | decode and plausibility checks (pass/fail only) |
| CCM semantics: every kept matrix has all three row sums within 3 % of 1 (white preserving) and zero offsets. `cc13_bps` and `cc13_ife` are identity; the real CCM is `cc13_ipe_v2` | check in the generator, all kept leaves pass |
| Rear black level: the four `demuxblklevel14_ife_v2` floats are equal within 10 % and their mean is 16 times a plausible 10 bit black level (a 14 bit scale). `bls12_ife_v2` is all zero on the rear | generator note lines |
| Where the data sits for the rear: one `cc13_ipe_v2` (8 leaves = 4 CCT bands x 2 lux-index bins), one `demuxblklevel14_ife_v2` (1 leaf), `gamma15_ipe_v2` (4 variants of 3 lux bins), `lsc41_ife_v2` and `lsc41_bps_v2` (4 meshes) | `--inventory` |
| Front: 14 `cc13_ipe_v2` variants (4 non-identity, in 2 distinct matrix sets), 4 `demuxblklevel14_ife_v2`, 12 `gamma15_ipe_v2` variants, 3 `lsc41_ife_v2` variants of 5 meshes; modules repeat once per use case or mode | `--inventory` and a matrix comparison |
| IR VD55G0: one variant of each module but with 12 to 24 leaves (`bls12` 24, `demuxblklevel14` 24, `cc13_ipe` 12, `lsc41` 14); a colour CCM exists although the sensor is monochrome (shared template) | `--inventory` |
| libcamera 0.7.2 simple IPA algorithms: `BlackLevel`, `Awb`, `Ccm`, `Adjust`, `Agc`, in that order in `uncalibrated.yaml` | `src/ipa/simple/algorithms/*.cpp`, `src/ipa/simple/data/uncalibrated.yaml` |
| What the tuning file can carry: `BlackLevel: blackLevel` (int16, 16 bit scale, `>> 8` to 8 bit, one value for all channels: `blc.cpp`), `Ccm: ccms[{ct, ccm}]` (`ct` an integer parsed with `std::stoul`, 9 floats row major, linear interpolation by the AWB CCT, `ccm.cpp`, `libipa/interpolator.h:42-72`). `Awb`, `Agc` and `Adjust::init` read nothing from the tuning data | source |
| Gamma: `kDefaultGamma = 2.2` (`adjust.h:20`); the Gamma, Contrast and (with a CCM) Saturation controls are runtime knobs only. LSC, denoise and dead pixel correction are TODO items of the GPU path, not implemented | `adjust.cpp`, `software_isp/TODO.md` |
| AWB is grey-world on the stats histogram, red and blue gains capped at 4.0, CCT from a fixed 3x3 matrix and a polynomial (`libipa/colours.cpp:59-77`) | source |
| The IPA looks up `<sensor model>.yaml` then `uncalibrated.yaml` under `<ipa data dir>/simple/` (`software_isp.cpp:147-151`, `ipa_proxy.cpp:165-190`); `LIBCAMERA_IPA_CONFIG_PATH` adds a search directory | source |
| Camera sensor helpers in 0.7.2 include `ov13858` (`AnalogueGainLinear{1,0,0,128}`, gain = code / 128, matches the Linux driver default code 0x80 = 1.0x, `ov13858.c:68`) and `vd55g1`, `vd56g3`; none for `imx681` or `vd55g0`. The IPA warns and uses the control value as the gain when the helper is missing (`soft_simple.cpp:102-108, 227-249, 307, 326`) | `camera_sensor_helper.cpp:820-852` |
| The Software ISP debayer has no luma-only input: the CPU debayer macros cover the Bayer orders only; the monochrome IR stream is therefore not a Software ISP client | `debayer_cpu.cpp:156-261` |
| Generated files load: the libcamera YAML parser accepts both, `BlackLevel` reads, `Ccm` reads 4 entries per sensor and interpolates over 1500 to 12000 K. libcamera 0.7.2 built in the Fedora 44 container (`-Dpipelines=simple -Dipas=simple`), `libcamera-sp11.patch` applies clean on the tag and the three touched objects rebuild | `validate-tuning.sh` output |

## Inference

| # | Statement | Reasoning | What would change it |
|:--|:--|:--|:--|
| 1 | Control variable codes: in `cc13`, `gamma15` the control with 9 breakpoints almost all in the kelvin range is the colour temperature (code 6 in these modules); the control with 2 to 4 integer bins below 1100 is the AEC lux index (code 0, larger = darker in Qualcomm AEC). The generator keeps the lowest lux-index bin, i.e. normal light | breakpoint statistics only | REA of the enum (question C1) |
| 2 | Each CCT leaf applies over its `[lo, hi]` range with blending to the neighbour; the representative `ct` is the band centre (the upper edge for the open lowest band, the lower edge for an open highest one) | trigger tree shape; libcamera interpolates linearly between the `ct` points | REA of the trigger interpolation (C2) |
| 3 | The `demuxblklevel14` floats are black levels in a 14 bit scale for R, Gr, Gb, B; libcamera's 16 bit value is the channel mean times 4 | rear mean divided by 16 is a plausible 10 bit black level; IFE pads 10 bit data to 14 bit | REA (B1) or a dark RAW frame |
| 4 | The Windows CCM is row major with `out = M x in` on white balanced linear RGB after demosaic, which is what libcamera's `Ccm` does (`combinedMatrix = ccm * combinedMatrix`) | rows sum to 1 | REA of `cc13` consumer code (C3) |
| 5 | The 257 float `gamma15` LUT is a 10 bit output tone curve of a power-law shape with extra shaping (power-law fit rms below 0.05, not below 0.02); a fitted exponent reproduces mid-tones, not the shaping | fit statistics | REA (T1) |
| 6 | Colour parity is limited by libcamera's AWB: Windows CCMs were tuned against its own AWB gains and CCT definition, libcamera computes CCT with a generic matrix, so the bin picked can be off by an illuminant class even with correct matrices | `colours.cpp` is sensor independent | A test with a colour chart under known illuminants |
| 7 | Which of the repeated modules is the preview/video use case is not known; the generator uses the first non-identity `cc13_ipe_v2` variant in file order. For the rear there is only one, for the front the 4 non-identity variants form 2 distinct matrix sets | variants repeat per use case | REA of the use-case to module table (U1) |
| 8 | The IMX681 gain register is linear (MIPI CCS 0x0204); without a divisor the helper cannot be written | `2026-10-31-rea-bayer-poll-units.md` 3.6 | REA (G1) |
| 9 | The Linux ov13858 driver reports `SGRBG10` and the Windows module says BGGR; the colour fidelity needs the order the driver reports to match the real filter. This is a blob/driver matter (image worker, kernel worker), recorded here because a wrong order swaps red and blue before any CCM | `ov13858.c:1284` against `2026-10-31-rea-bayer-poll-units.md` 3.2 | RAW capture of a coloured target (test plan) |

## Unknown

| # | Question | Impact |
|:--|:--|:--|
| U1 | The block to use case table (preview, video, snapshot, binning modes) that selects between the repeated module variants (front `cc13_ipe` 14, `anr10` 32, `tf21` 33) | Front colour may differ by 2 CCM sets |
| U2 | `wb20` leaf layout (three ints, one non-float word, an int, three floats) and whether the three floats are default gains | Not used |
| U3 | `bls12` 20-byte leaf meaning (zero on the rear, non-zero on the front) | Black level may need a front correction |
| U4 | LSC mesh layout: 13 x 17 or 17 x 13, channel order, gain format (the values are above 1 at the corners, so a gain multiplier), meaning of the 8 trailing words (some look like power-of-two scales) | Needed only when a libcamera LSC stage exists |
| U5 | AWB reference point block (`refPtV1`, `referenceCCTs`) layout and units | Would allow a Linux-side AWB prior |
| U6 | Whether the IMX681 black level is on the same 14 bit scale as the rear (the front mean divided by 16 is not in the rear's range, divided by 8 it is: non-conclusive) | Black level of the front |

## REA questions for the Gemini analyst

Use `QcDeviceMFT8380.dll` (sha256 `c241b7fbb2ec...`, ARM64, Ghidra language forced from the catalog), the consumer path is `CamX` chromatix parsing and the IFE/BPS/IPE pipeline nodes (`CamX::IFENode`, `BPSNode`, `IPENode`, `chromatix` module data classes). For each answer give address, `evidence_id` and the grade.

| ID | Question |
|:--|:--|
| C1 | Enum behind `control_var_type`: values 0 to 18 and 100 (names and meaning: lux index, gain, CCT, exposure, DRC gain, HDR ratio, zoom, ...). Which value is the CCT and which the lux index in `cc13`, `gamma15`, `lsc41` |
| C2 | How the trigger tree is evaluated: do `lo`/`hi` of a leaf mark the full-weight range and the gap to the neighbour the blend zone? Is the blend linear in the control variable? What is the sentinel meaning of a lower bound below 1000 K in the first CCT band |
| C3 | `cc13` consumer (`CamX::IPECC` or the `cc13` setting code): matrix layout (row major R'=aR+bG+cB or column major), the meaning of the three int offsets, input and output scale, whether it runs on white balanced linear data before or after gamma and tone mapping, and the order of the IPE stages (ABF, demosaic, CC, GTM, gamma, LTM, ASF, TF) |
| C4 | Illuminant tags: does the CCM table carry a CCT or an illuminant enum per leaf, and is the CCT of a band the AWB estimate of the colour temperature after the AWB gains (same definition as `estimateCCT`) |
| B1 | `demuxblklevel14` and `bls12`: units (14 bit scale?), channel order (R, Gr, Gb, B?), how they combine with sensor optical black and with `bls12`, and why the front `bls12` is non-zero |
| B2 | Does Windows subtract black level before or after the LSC multiply, and is the pedestal re-added (output black level) |
| S1 | LSC `lsc41`: mesh dimensions and order (13 x 17 or 17 x 13), channel order, gain format (float multiplier or fixed point), meaning of the 8 trailing words, how `lscgolden41` (3536 bytes, the calibration reference) and the per-unit EEPROM calibration data combine with the tuned mesh (the rear module reads an EEPROM), how the CCT bands are interpolated |
| W1 | `wb20` leaf layout, and where the AWB gains come from at runtime (stats, `MWBGainV1`, `refPtV1`): layout and units of the AWB reference points (`refPtV1`, `referenceCCTs`, `custRefPtV1`), the R/G and B/G coordinates and the CCT assigned to each |
| G1 | IMX681 analogue gain: the `imx681.cpp` conversion (`AnalogueGainToRegisterVal` and inverse, or the CCS model constants `m0 c0 m1 c1`), register width, minimum and maximum code and gain; the same for the digital gain register 0x020e. Also the IMX681 exposure unit (lines of `lineLength`) |
| G2 | OV13858: confirm the Windows gain law equals `gain = code / 128` (Linux driver) and the maximum analogue gain used by AEC (code and gain) |
| T1 | `gamma15` leaf: 257 entry float LUT, output scale (10 bit?), input normalisation, the meaning of the 3 lux bins, whether the LUT already includes the sRGB-like encoding or is applied after GTM/LTM; the post-gamma contrast and saturation (`cs20`, `sce11`, `uvg10`) defaults |
| T2 | Which AEC controls are exported from the tuning to AGC targets: target luma, exposure table, max gain, gain-to-noise limit (`aecxconvergence`, `aecxdbconvbase`, `aecxdbconvconstraints`); a gain-to-noise model per sensor if one exists in the file (`anr10`, `tf21` gain-indexed leaves) |
| U1 | Use case to module variant: for each repeated module (`cc13_ipe`, `gamma15_ipe`, `anr10`, `tf21`, `asf34`, `hnr10`) which variant serves preview, video and snapshot at the modes of the module data file (rear 3 modes, front 6), and which variant a Windows Hello RGB stream uses |
| F1 | Anything the Windows ISP applies that the Software ISP cannot (so it can be listed in the dossier): in particular whether the default preview path runs ANR/TF, ASF, LTM and HDR at all, and the Windows Studio Effects order relative to the MFT |

## Mapping table (what is replayed, approximated, dropped)

| Windows block | libcamera element | Status |
|:--|:--|:--|
| `demuxblklevel14_ife_v2` (4 ch, 14 bit) | `BlackLevel.blackLevel` (16 bit, channel mean x 4) | Replayed, channels averaged (spread within 10 %), scale is Inference 3 |
| `cc13_ipe_v2` (CCM per CCT, lowest lux bin) | `Ccm.ccms[{ct, ccm}]`, 4 entries per sensor | Replayed exactly per band; band centre as `ct`; other lux bins and the use case choice are approximations (Inference 1, 2, 7) |
| `gamma15_ipe_v2` (257 float LUT) | `Adjust.gamma` (power-law fit), read only with `libcamera-sp11.patch` | Approximated |
| `lsc41_ife_v2`, `lscgolden41_ife_v2` | none (private sidecar `<sensor>.lsc-mesh.private.json`) | Dropped, kept for a future LSC stage |
| `wb20`, AWB reference points | none | Dropped (grey-world AWB) |
| `bpcabf41`, `anr10`, `tf21`, `hnr10`, `lenr10`, `asf34`, `cs20`, `cv12`, `sce11`, `uvg10` | none | Dropped |
| `gtm13`, `ltm16`, `bgtm10`, `bltm10`, `tmc14` | none | Dropped |
| `hdr*`, `shdr10`, `remosaic10`, `qpdpc10`, `mf12`, `mrc10` | none | Dropped |
| `aecx*` (AEC) | none | Dropped; sensor gain law from the helper |
| Gain law | `CameraSensorHelper` | OV13858: stock helper correct (patch adds black level); IMX681: template, blocked on G1 |

## Validation

The libcamera tree builds in the Fedora 44 image with
`dnf install meson ninja-build gcc-c++ libyaml-devel python3-jinja2 python3-ply python3-pyyaml openssl-devel libevent-devel libdrm-devel`
and `meson setup out/ref/libcamera-build out/ref/libcamera -Dpipelines=simple -Dipas=simple -Dcam=disabled -Dqcam=disabled -Dgstreamer=disabled -Dlc-compliance=disabled -Dpycamera=disabled -Dv4l2=disabled -Dtracing=disabled -Ddocumentation=disabled -Dtest=false -Dandroid=disabled -Dbuildtype=release`.
`validate-tuning.sh out/firmware-private/cameras/libcamera/*.yaml` then prints for each file `OK ... blackLevel=yes, ccm entries=4`.
The check proves the files parse and feed `BlackLevel` and `Ccm`; it does not prove the picture, which needs the device (test plan).

## Requests

- image: install `out/firmware-private/cameras/libcamera/{ov13858,imx681}.yaml` only in the private image mode as `/usr/share/libcamera/ipa/simple/<sensor>.yaml`, mode 644 inside the image, never in a public ISO; rerun `build-libcamera-tuning.py` on the build host (it needs `sources/windows`); the sidecar `*.lsc-mesh.private.json` and the manifest stay out of the image unless an LSC stage exists.
- image: build libcamera with `libcamera-sp11.patch` (Fedora spec patch, or a local rebuild in the private image build). Without the patch the files still work; the `gamma` key is then ignored (Software ISP gamma stays 2.2).
- image: the sensor model string must equal the file name. After the first boot with a camera, run `LIBCAMERA_LOG_LEVELS=IPAProxy:INFO,IPASoft:DEBUG cam -l` (or the Snapshot app from a terminal) and check the line `Using tuning file /usr/share/libcamera/ipa/simple/<name>.yaml`; if it falls back to `uncalibrated.yaml` the model string differs, rename the file.
- image: set `LIBCAMERA_SOFTISP_MODE=gpu` only after the GPU path is evidenced; the CPU path is the baseline.
- kernel: IMX681 driver (blocked) will name the sensor `imx681`; the OV13858 driver reports `SGRBG10` while Windows says BGGR (Inference 9): the RAW check in the test plan decides.
- orchestrator: send the REA question table above to the Gemini analyst; answers C1 to C4 and B1 decide the exact CCM and black level scale; G1 unblocks the IMX681 helper; S1 only matters if libcamera gets an LSC stage (upstream work or a local patch).
- orchestrator: a quality acceptance test belongs in `test-plan.md`: a colour chart (or a phone screen with a standard pattern) under daylight, warm indoor light and low light, compared against a Windows capture of the same scene from the Camera app, with the findings written as device evidence.
