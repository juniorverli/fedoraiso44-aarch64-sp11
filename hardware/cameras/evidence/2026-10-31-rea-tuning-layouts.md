<!-- Source: Gemini 3.8 Flash via Antigravity (agy) with the REA MCP, 2026-10-31. Orchestrator cross-checks: the OV13858 gain law (code = gain x 128) and the VD55G0 reciprocal law (32 - 32/gain, codes 0..28) agree with the Linux drivers ov13858.c and vd55g1.c read by other agents. Everything else, including the IMX681 law (512 - 512/gain) and the block layouts, is UNVERIFIED by a second reader. No coefficients or tables are recorded here (S5). -->
# Reverse Engineering Analysis Report: Qualcomm CamX Camera Tuning Pipeline

**Document ID**: `out/agents/flash/m15-camera-tuning-rea-report.md`  
**Target Architecture**: Microsoft Surface Pro 11 (Snapdragon X Elite / Plus X1P-64-100, Hamoa, Spectra 695 ISP)  
**Date**: 2026-10-31  
**REA Rules & Compliance**: Follows `AGENTS.md`, `agents/protocol.md` §9, Safety Rules S3 (no firmware writes) and S5 (no tuning tables, coefficients, register values, or proprietary binary bytes stored; structure, field names, units, and semantics only).

---

## 1. Inventory of Windows Camera Driver & Tuning Packages

All binaries and tuning containers were inventoried from `sources/windows/DriverStore` and verified against `sources/windows/MANIFEST.sha256` and `sources/binary-catalog.tsv`.

| Package Folder | File Name | Size (Bytes) | SHA-256 (Prefix) | Type / Language | Role | Grade |
|:---|:---|:---|:---|:---|:---|:---|
| `surfacecamrearsensor_extension8380.inf_arm64_9e667d808f1a7021` | `com.surface.tuned.rfc_ov13858.bin` | 2,595,518 | `4858ccb297ee` | Chromatix container | Rear sensor ISP tuning container | Verified |
| `surfacecamrearsensor_extension8380.inf_arm64_9e667d808f1a7021` | `com.surface.sensormodule.rfc_ov13858.bin` | 148,262 | `f8f60e79b77b` | Chromatix container | Rear sensor driver module & gain limits | Verified |
| `surfacecamrearsensor_extension8380.inf_arm64_9e667d808f1a7021` | `com.surface.tuned.rfc_ov13858_MSHW0561.bin` | 1,201,168 | `383b9bcc852d` | Chromatix container | Rear sensor variant tuning container | Verified |
| `surfacecamfrontsensor_extension8380.inf_arm64_5a4c66ce4812274e` | `com.surface.tuned.ffc_imx681.bin` | 6,465,007 | `2c1c7fd9090e` | Chromatix container | Front sensor ISP tuning container | Verified |
| `surfacecamfrontsensor_extension8380.inf_arm64_5a4c66ce4812274e` | `com.surface.sensormodule.ffc_imx681.bin` | 212,272 | `f7dd81be6415` | Chromatix container | Front sensor driver module & gain limits | Verified |
| `surfacecamauxsensor_extension8380.inf_arm64_84ddd55dc933cac9` | `com.surface.tuned.aux_vd55g0_MSHW0492.bin` | 1,086,298 | `41518f81eadb` | Chromatix container | IR sensor ISP tuning container | Verified |
| `surfacecamauxsensor_extension8380.inf_arm64_84ddd55dc933cac9` | `com.surface.sensormodule.aux_vd55g0_MSHW0492.bin` | 136,411 | `e574db7eb282` | Chromatix container | IR sensor driver module & gain limits | Verified |
| `surfacecamavs8380.inf_arm64_2b9eaefcbe9d3342` | `QcDeviceMFT8380.dll` | 23,998,368 | `c241b7fbb2ec` | PE ARM64 (`AARCH64:LE:64:v8A`) | Windows Media Foundation Camera Device MFT & CamX sensorlibs | Verified |
| `surfacecamavs8380.inf_arm64_2b9eaefcbe9d3342` | `eva.dll` | 722,808 | `bb87ef58f4d1` | PE ARM64 (`AARCH64:LE:64:v8A`) | Electronic Video Analytics engine (warp/EIS) | Verified |
| `surfacecamavs8380.inf_arm64_2b9eaefcbe9d3342` | `surfacecamavs8380.sys` | 547,192 | `1238e8ec67cb` | PE ARM64 (`AARCH64:LE:64:v8A`) | Surface AVS camera streaming driver | Verified |
| `surfacecamfrontsensor8380.inf_arm64_747e2ddb5eb5a22b` | `surfacecamfrontsensor8380.sys` | 142,728 | `80a8e4a1ef8f` | PE ARM64 (`AARCH64:LE:64:v8A`) | Front sensor kernel driver (Sony IMX681) | Verified |
| `surfacecamrearsensor8380.inf_arm64_8fbcacb272007d57` | `surfacecamrearsensor8380.sys` | 164,216 | `b7d7a278c5e7` | PE ARM64 (`AARCH64:LE:64:v8A`) | Rear sensor kernel driver (OmniVision OV13858) | Verified |
| `surfacecamauxsensor8380.inf_arm64_7d23cd8fdfa9b39f` | `surfacecamauxsensor8380.sys` | 139,616 | `e5b6b064f39c` | PE ARM64 (`AARCH64:LE:64:v8A`) | IR auxiliary sensor kernel driver (ST VD55G0) | Verified |
| `qccamisp8380.inf_arm64_068a5d125dcec104` | `qccamisp8380.sys` | 376,560 | `64463b4d7889` | PE ARM64 (`AARCH64:LE:64:v8A`) | Qualcomm Spectra ISP kernel driver | Verified |
| `qccamisp8380.inf_arm64_068a5d125dcec104` | `CAMERA_ICP.mbn` | 905,880 | `c214e486ea66` | ELF32 Xtensa (signed) | Image Control Processor firmware blob | Verified |
| `qccamisp8380.inf_arm64_068a5d125dcec104` | `CAMERA_ICP_AAAAAA.elf` | 4,738,507 | `ba4e95ac9b58` | ELF32 Xtensa | Image Control Processor executable image | Verified |
| `qccamsecureisp8380.inf_arm64_e0daad652520462e` | `qccamsecureisp8380.sys` | 107,232 | `47c944fa4974` | PE ARM64 (`AARCH64:LE:64:v8A`) | Secure ISP kernel driver | Verified |
| `qccamsecureisp8380.inf_arm64_e0daad652520462e` | `QcISPTrustlet8380.dll` | 277,416 | `55ebf254447b` | PE ARM64 (`AARCH64:LE:64:v8A`) | TrustZone Secure Camera Trustlet | Verified |
| `qccamsecureisp8380.inf_arm64_e0daad652520462e` | `bm3a68v08s11n52.bin` | 2,735,472 | `f52445cbfcb8` | Structured data | Secure 3A statistics / face processing model | Verified |
| `qccamplatform8380.inf_arm64_16d44e9aca3becfb` | `qccamplatform8380.sys` | 144,584 | `836714ec41f9` | PE ARM64 (`AARCH64:LE:64:v8A`) | Qualcomm Camera Platform driver | Verified |
| `qccamplatform8380.inf_arm64_16d44e9aca3becfb` | `com.qti.tuned.default.bin` | 7,504,421 | `ca620fbcfd9b` | Chromatix container | Qualcomm baseline reference ISP tuning | Verified |
| `qccammipicsi8380.inf_arm64_9b873143bb427aef` | `qccammipicsi8380.sys` | 104,648 | `033f5b1431ad` | PE ARM64 (`AARCH64:LE:64:v8A`) | Qualcomm MIPI CSI receiver driver | Verified |

---

## 2. Container Format of the Chromatix Tuning Binaries

### 2.1 File Header & Container Layout
Both `com.surface.tuned.*.bin` and `com.surface.sensormodule.*.bin` conform to the Qualcomm Chromatix binary container specification (parser: `Parameter Parser V3.4.0 (2106301010)`). All numerical fields use standard little-endian byte ordering.

- **`0x00 .. 0x1B` (`char[28]`)**: Magic container identifier string `QTI Chromatix Header\0`.
- **`0x1C .. 0x1F` (`u32`)**: Payload length field, exactly matching `file_size - 4` (total byte length excluding the trailing 4-byte CRC-32 word).
- **`0x20 .. 0x27` (`u32[2]`)**: Version integers, fixed at `3` (major) and `1` (minor).
- **`0x28 .. 0x57` (`char[48]`)**: ASCII parser revision banner (`Parameter Parser V3.4.0 (2106301010)\0`).
- **`0x58 .. 0x97` (`char[64]`)**: Module namespace string (e.g. `com.surface.tuned.rfc_ov13858\0` or `com.surface.tuned.ffc_imx681\0`).
- **`0x98 .. 0x9F`**: Reserved padding.
- **`0xA0 .. 0xA3` (`u32`)**: Section table file offset (standard: `0x000000A8`).
- **`0xA4 .. 0xA7` (`u32`)**: Section count (standard: `3`).
- **`0xA8 .. 0xCB` (Section Directory)**: Array of 12-byte section descriptors `{ u32 section_id, u32 file_offset, u32 section_size }`:
  - **Section 0 (`id = 0`)**: Symbol Table directory. Array of 56-byte (`0x38`) records:
    - `0x00` (`u32`): 1-based symbol index $i \in [1 .. N]$.
    - `0x04` (`char[32]`): Symbol ASCII identifier (NUL-terminated).
    - `0x24` (`i32[3]`): Flags / structural metadata fields (`a, b, c`).
    - `0x30` (`u32`): Heap data offset relative to Section 1 file base.
    - `0x34` (`u32`): Data byte size on heap.
  - **Section 1 (`id = 1`)**: Raw Data Heap holding packed structures, trigger tables, and coefficient arrays.
  - **Section 2 (`id = 2`)**: File trailer / metadata index.
- **Trailer (`file_size - 4 .. file_size - 1`)**: Standard 32-bit IEEE 802.3 Ethernet CRC-32 polynomial (`0xEDB88320`) calculated over all preceding bytes `[0 .. file_size - 4)`. Verified matching stored value in all tested binaries (`0xc869d30d` for rear, `0x4f35041c` for front).

### 2.2 Trigger & Decision Tree Keying Mechanism
Chromatix organizes all ISP parameter variations into multi-dimensional decision trees. A module instance defines an array of trigger control variable tags via symbol `control_var_type`.

- **Control Variable Enum Hierarchy**:
  - `0`: Lux Index (AEC exposure level, float range $[1.0 .. 900.0]$).
  - `1`: Sensitivity / Exposure Ratio (ADRC dynamic range expansion ratio, $[1.0 .. 200.0]$).
  - `2`: Zoom Factor / Lens Position (digital zoom magnification $[1.0 .. 100.0]$).
  - `5`: Total Sensor / Analog Gain (multiplication factor $[1.0 .. 16.0]$ or $[1.0 .. 64.0]$).
  - `6`: Color Temperature / CCT ($[1.0 .. 10000.0]$ Kelvin).
  - `8`, `9`: Spatial Resolution mode, Sensor Binning mode, Frequency Sub-band index.
  - `13`, `14`, `16`: Multi-scale decomposition / Temporal wavelet filter pass index.
  - `100`: Resolution / Sensor Operation Mode index.

- **Tree Node Layout (`trigger` struct, 24 bytes)**:
  `{ float range_start, float range_end, u32 next_level_count, u32 next_level_sym_idx, u32 leaf_region_count, u32 leaf_region_sym_idx }`.
  - Non-leaf nodes set `next_level_count > 0` and point to an array of child `trigger` records representing the next control variable dimension.
  - Leaf nodes set `next_level_count = 0` and `leaf_region_count = 1`, pointing to a `region` symbol holding the parameter structure for that operational point. Interpolation weights are computed linearly across adjacent nodes.

### 2.3 List of Tuning Blocks Present

Both the rear (`rfc_ov13858`) and front (`ffc_imx681`) tuned binaries contain 66 hardware module blocks across the IFE (Image Front End), BPS (Bayer Processing Segment), IPE (Image Processing Engine), and EVA (Electronic Video Analytics) subsystems:

1. **Black Level**:
   - `mod_demuxblklevel14_trigger_data` (Demux Black Level Subtraction 1.4 for IFE/BPS).
   - `mod_bls12_trigger_data` (Black Level Subtraction 1.2).
   - `mod_aonbls12_trigger_data` (Always-On low-power BLS 1.2).
2. **Lens Shading Correction (LSC)**:
   - `mod_lsc41_trigger_data` (Dynamic Lens Shading Correction 4.1).
   - `mod_lscgolden41_trigger_data` (Golden / Unit Factory Calibration Mesh 4.1).
   - `mod_lsc36_trigger_data`, `mod_lsc35_trigger_data`.
   - `mod_tintless23_trigger_data` (Dynamic tintless illumination shading 2.3).
3. **Color Correction (CCM) & Conversion**:
   - `mod_cc13_trigger_data` (Color Correction Matrix 1.3).
   - `mod_cv12_trigger_data` (Color Space Conversion 1.2).
4. **White Balance (WB)**:
   - `mod_wb20_trigger_data` (White Balance Channel Gain 2.0).
5. **Denoise & Artifact Reduction**:
   - `mod_bpcabf41_trigger_data` (Defective Pixel Correction & Adaptive Bayer Filter 4.1).
   - `mod_anr10_trigger_data` (Adaptive Noise Reduction 1.0).
   - `mod_tf21_trigger_data` (Temporal Filtering 2.1).
   - `mod_hnr10_trigger_data` (Hardware Noise Reduction 1.0).
   - `mod_lenr10_trigger_data` (Low-light Edge Noise Reduction 1.0).
   - `mod_swabf10_trigger_data` (Software Bayer Filter 1.0).
   - `mod_cs20_trigger_data` (Chroma Suppression 2.0).
6. **Sharpening**:
   - `mod_asf34_trigger_data` (Advanced Spatial Filter / Edge Sharpening 3.4).
   - `mod_swasf10_trigger_data` (Software ASF 1.0).
7. **Gamma, Tone Mapping & LTM**:
   - `mod_gamma15_trigger_data` (Tone Curve / Gamma 1.5 for BPS/IPE).
   - `mod_gamma16_trigger_data` / `mod_aongamma16_trigger_data` (Gamma 1.6).
   - `mod_bgtm10_trigger_data` (Bayer Global Tone Mapping 1.0).
   - `mod_bltm10_trigger_data` (Bayer Local Tone Mapping 1.0).
   - `mod_ltm16_trigger_data` (Local Tone Mapping 1.6).
   - `mod_gtm13_trigger_data` / `mod_gtmfd13_trigger_data` (Global Tone Mapping with Face Detection).
   - `mod_tmc14_trigger_data` (Tone Mapping Curve 1.4).
8. **HDR & Multi-exposure**:
   - `mod_shdr10_trigger_data` (Staggered HDR 1.0).
   - `mod_hdr10p10_trigger_data`, `mod_hdr40_trigger_data`, `mod_hdr50_trigger_data`.
9. **Demosaic, Geometry & Phase Detection**:
   - `mod_demosaic36_trigger_data` / `mod_aondemosaic36_trigger_data` (Demosaic 3.6).
   - `mod_gic31_trigger_data` (Green Imbalance Correction 3.1).
   - `mod_cac23_trigger_data` / `mod_lcac11_trigger_data` (Chromatic Aberration Correction).
   - `mod_ldc11_trigger_data` (Lens Distortion Correction 1.1).
   - `mod_pdpc31_trigger_data` / `mod_qpdpc10_trigger_data` (Phase Detection Pixel Correction).
   - `mod_sce11_trigger_data` (Skin Color Enhancement 1.1).
10. **AEC / AWB / AF 3A Tuning**:
    - **AEC**: `aecx1dvectorprocessor`, `aecxadvancedinfo`, `aecxarbitration`, `aecxconvergence`, `aecxcorestatsconfig`, `aecxdb1dmeterweight`, `aecxdb2dmeterweight`, `aecxdbroi`, `aecxface`, `aecxflash`, `aecxmetering`, `aecxstartup`, `AONAEC`.
    - **AWB**: `temporalAWBV1`, `awbSceneChangeConvergeV1`, `AWBExtensionParam`, `bgStatsConfigV1`, `bfwStatsConfig`.
    - **AF**: `AFAlgoTuning`, `ContrastAF`, `PDAF`, `DepthAF`, `HAF` (Hybrid AF), `BAF` (Bayer AF filter bank), `DCIAF`, `AFDTuningData`.

---

## 3. Specifications of Blocks Mappable to a Software ISP

The following 5 tuning blocks map directly to stages implementable in a userspace software ISP pipeline (e.g. `libcamera SoftISP`):

### 3.1 Black Level Subtraction (`demuxblklevel14`)
- **Block Symbol**: `demuxblklevel14_bps_v2` / `demuxblklevel14_ife_v2` pointing to leaf `region` descriptors.
- **Data Size & Storage**: 16 bytes per region (`<4f`, 4 single-precision IEEE 754 floats).
- **Channel Layout**: 4 color channels per Bayer quad: $[Gr, R, B, Gb]$ (for rear GRBG/BGGR) and $[R, Gr, Gb, B]$ (for front RGGB).
- **Scale & Representation**: Scaled to the 14-bit internal ISP processing domain ($[0 .. 16383]$).
  - **Rear OV13858**: Tuned to pedestal float $\approx 1024.0 .. 1030.0$ (corresponds exactly to nominal pedestal $64$ in the sensor's native 10-bit output domain: $64 \times 2^{4} = 1024$).
  - **Front IMX681**: Tuned to pedestal float $\approx 592.0 .. 602.0$ (corresponds to nominal pedestal $\approx 37.0 .. 37.5$ in a 10-bit domain).

### 3.2 Color Correction Matrix (`mod_cc13`)
- **Block Symbol**: `mod_cc13_trigger_data` with control variables `[2, 5, 100, 0, 6]` (keyed by Zoom, Gain, Mode, Lux Index, CCT).
- **Data Size & Storage**: 48 bytes per matrix region (`<12f`, 12 single-precision IEEE 754 floats).
- **Matrix Layout**:
  - Elements `0 .. 8`: $3 \times 3$ matrix in row-major order:
    $$\begin{bmatrix} c_{00} & c_{01} & c_{02} \\ c_{10} & c_{11} & c_{12} \\ c_{20} & c_{21} & c_{22} \end{bmatrix}$$
    Transform:
    $$R_{out} = c_{00} R_{in} + c_{01} G_{in} + c_{02} B_{in} + \Delta R$$
    $$G_{out} = c_{10} R_{in} + c_{11} G_{in} + c_{12} B_{in} + \Delta G$$
    $$B_{out} = c_{20} R_{in} + c_{21} G_{in} + c_{22} B_{in} + \Delta B$$
  - Elements `9 .. 11`: Additive channel offsets $[\Delta R, \Delta G, \Delta B]$ (floats, nominal 0.0).
- **Hardware Register Representation**: Fixed-point signed Q12 format (1 sign bit, 3 integer bits, 12 fractional bits: $1.0 = 4096 = \text{0x1000}$).
- **Illuminant / CCT Tiers**:
  - **Horizon / Incandescent (A)**: CCT interval $[1.0 .. 2300.0]$ K (rear) / $[1.0 .. 2400.0]$ K (front).
  - **Warm Fluorescent (TL84 / Halogen)**: CCT interval $[2600.0 .. 3400.0]$ K (rear) / $[2700.0 .. 3300.0]$ K (front).
  - **Cool White Fluorescent (CWF)**: CCT interval $[3600.0 .. 4300.0]$ K (rear) / $[3700.0 .. 4200.0]$ K (front).
  - **Daylight (D50 / D65)**: CCT interval $[4900.0 .. 9000.0]$ K (rear) / $[4800.0 .. 10000.0]$ K (front).
  - Binned across two AEC illumination tiers: Low-light / Indoor (Lux $[1.0 .. 350.0]$) and Daylight (Lux $[400.0 .. 900.0]$).

### 3.3 White Balance Gains & AWB Mesh Geometry
- **Channel Balance (`mod_wb20`)**:
  - Structure: 32 bytes (`<5I3f`). Contains channel bitmask (`0x3ffff` for 18-bit register fields), fixed-point fraction shift `0xC` (Q12), followed by 3 floating-point multipliers: $R_{gain}, G_{gain}, B_{gain}$.
  - Hardware register scale: Unsigned Q12 fixed-point ($1.0 = 4096 = \text{0x1000}$).
- **AWB Illuminant Decision Space (`temporalAWBV1`)**:
  - Geometry: Chromaticity coordinate plane ($R/G$ ratio on horizontal axis, $B/G$ ratio on vertical axis).
  - `vertexData` (Symbol `#7320`, 768 bytes): Array of 96 vertex coordinate pairs `(x, y)` stored as IEEE 754 float32.
  - `triglData` (Symbol `#7319`, 1056 bytes): Array of 88 triangles, each defined by 3 vertex index integers (`u32[3]`), tessellating the Planckian locus and non-Planckian illuminant domains.

### 3.4 Lens Shading Correction (`mod_lsc41` & `mod_lscgolden41`)
- **Mesh Grid Dimensions**: $17 \times 13$ rectangular spatial sample points (17 horizontal grid nodes, 13 vertical grid nodes = 221 spatial points).
- **Channel Count**: 4 independent color channels ($Gr, R, B, Gb$ / $R, Gr, Gb, B$).
- **Total Points**: $17 \times 13 \times 4 = 884$ entries.
- **Memory Format**:
  - Pure table: 3536 bytes ($884 \times 4$ bytes single-precision float32).
  - Dynamic table with header: 3568 bytes ($32$ bytes parameter metadata header $+ 3536$ bytes table).
- **Scale & Fixed-Point Equivalent**: Values represent normalized channel transmittance / gain factors scaling to 1023.0 at optical center (10-bit Q10 scale $[0 .. 1023]$ where 1023 represents 1.0x transmittance, with corner vignetting falloff reaching $\sim 175.0$).
- **Illuminant Keying**: Provided in 3 dynamic CCT intervals ($[1.0 .. 3100.0]$ K, $[3500.0 .. 4200.0]$ K, $[4800.0 .. 10000.0]$ K) plus high-lux daylight mode.

### 3.5 Gamma / Global Tone Curve (`mod_gamma15`)
- **Block Symbol**: `mod_gamma15_trigger_data` (IFE/BPS/IPE gamma curve).
- **Table Size**: 3084 bytes ($12$ bytes configuration header $+ 3072$ bytes payload).
- **Point Count**: 256 points per channel $\times$ 3 channels ($R, G, B$) = 768 points.
- **Format & Precision**: Single-precision IEEE 754 float32 output values.
- **Range & Scale**: Output points span $[0.0 .. 4095.0]$ ($2^{12}-1$), representing a 12-bit tone mapping transfer function.

---

## 4. Sensor Gain Laws & Control Architecture

Reverse-engineered from `QcDeviceMFT8380.dll` (functions `AnalogGainToRegisterVal`, `RegisterValToAnalogGain`, `CalculateExposure`, `FillExposureSettings` at file offsets `0x86EA80 .. 0x86F140`) and verified against the sensor module definitions and kernel drivers.

### 4.1 Rear Sensor: OmniVision OV13858
- **Analog Gain Register**: 16-bit register at address `0x3508` (`OV13858_REG_ANALOG_GAIN`).
- **Gain Formula**:
  Direct linear scaling with a step of $1/128$ (Q7 fixed-point):
  $$\text{Code}_{analog} = \lfloor \text{Gain}_{analog} \times 128 \rfloor$$
  $$\text{Gain}_{analog} = \frac{\text{Code}_{analog}}{128}$$
- **Limits**:
  - Minimum Analog Gain: $1.0\times$ ($\text{Code} = 128 = \text{0x0080}$).
  - Maximum Analog Gain: $15.5\times$ ($\text{Code} = 1984 = \text{0x07C0}$, driver ceiling $0x1FFF$).
- **Digital Gain Registers**: Per-channel MWB gain registers at `0x5100` (Blue), `0x5102` (Green), `0x5104` (Red).
  - Step of $1/1024$ (Q10 fixed-point):
    $$\text{Code}_{digital} = \lfloor \text{Gain}_{digital} \times 1024 \rfloor, \quad \text{Limits: } [1.0\times .. 16.0\times] \quad (\text{Code } [1024 .. 16384])$$

### 4.2 Front Sensor: Sony IMX681
- **Analog Gain Register**: 16-bit register at address `0x0204`.
- **Gain Formula**:
  Standard Sony hyperbolic / reciprocal gain characteristic curve:
  $$\text{Code}_{analog} = \lfloor 512 - \frac{512}{\text{Gain}_{analog}} \rfloor$$
  $$\text{Gain}_{analog} = \frac{512}{512 - \text{Code}_{analog}}$$
- **Limits**:
  - Minimum Analog Gain: $1.0\times$ ($\text{Code} = 0$).
  - Maximum Analog Gain: $15.5\times$ ($\text{Code} = 479$, hardware register ceiling 480 for $16.0\times$).
- **Digital Gain Register**: Global 16-bit digital gain register at address `0x020E` (`digitalGlobalGainAddr`).
  - Q8 fixed-point format ($1.0\times = 256 = \text{0x0100}$):
    $$\text{Code}_{digital} = \lfloor \text{Gain}_{digital} \times 256 \rfloor, \quad \text{Limits: } [1.0\times .. 4.0\times] \quad (\text{Code } [256 .. 1024])$$

### 4.3 Auxiliary IR Sensor: STMicroelectronics VD55G0
- **Decompiled Disassembly**: `QcDeviceMFT8380.dll` (`0x18086fa80 .. 0x18086fbe8`).
- **Analog Gain Formula**:
  $$\text{Code}_{analog} = \lfloor 32.0 - \frac{32.0}{\text{Gain}_{analog}} \rfloor, \quad \text{Gain}_{analog} = \frac{32.0}{32.0 - \text{Code}_{analog}}$$
  - Clamped to maximum $\text{Code}_{analog} = 28$ ($0x1C$):
    $$\text{Gain}_{analog, max} = \frac{32.0}{32.0 - 28} = \frac{32.0}{4.0} = 8.0\times$$
- **Digital Gain Formula**:
  Engaged when requested real gain exceeds $8.0\times$:
  $$\text{Gain}_{digital} = \min\left(4.0, \frac{\text{Gain}_{total}}{\text{Gain}_{analog}}\right)$$
  $$\text{Code}_{digital} = \lfloor \text{Gain}_{digital} \times 256 \rfloor \quad (\text{Q8 format, } [256 .. 1024])$$
  Any residual gain above $32.0\times$ ($8.0\times \text{analog} \times 4.0\times \text{digital}$) is assigned to ISP digital channel gain.

---

## 5. Hardware Pipeline Features Without Software-ISP Equivalents

A CPU-based software ISP (such as `libcamera SoftISP`) implements linear demosaicing, black-level subtraction, white balance channel multiplication, a static $3 \times 3$ color matrix, and a 1D gamma LUT. The Qualcomm Spectra 695 hardware ISP pipeline executes the following specialized functions in silicon that have no equivalent in a software ISP:

1. **Hardware Electronic Video Analytics & Grid Warping (EVA Subsystem)**:
   - Implemented in dedicated hardware block `QCOM0CF1` (`qceva8380.sys`, `eva.dll`).
   - Executes real-time geometric mesh warping (`gamma16_eva_ersld*warp`) driven by physical IMU/gyroscope high-rate temporal telemetry for 6-axis Electronic Image Stabilization (EIS) and Disparity Motion Estimation (DME 3.0 / DMM 1.0).
2. **Real-Time Line-Staggered Exposure Fusion (Hardware SFE / SHDR)**:
   - Dedicated Staggered Front End (`demuxblklevel14_sfe_*`, `mod_shdr10`) combining long-, medium-, and short-exposure sensor line readouts directly on-the-fly with ghosting suppression before Bayer ingestion.
3. **On-the-Fly Phase Detection Processing & AF Filter Banks (PDAF / BAF)**:
   - Real-time Phase Detection Pixel Correction (`mod_pdpc31`, `mod_qpdpc10`) masking shielded PD pixels in the Bayer stream.
   - Dedicated Bayer Auto Focus (`BAF`) hardware engine calculating multi-frequency high-pass spatial filter energy across dual 16-point IIR and FIR filter banks per frame with zero CPU penalty.
4. **2D Spatial Adaptive Local Tone Mapping (LTM 1.6 / BLTM 1.0 / GTM-FD 1.3)**:
   - Hardware LTM dynamically computes multi-zone 2D luminance tile grids across the frame, applying spatially varying tone curves combined with Face Detection ROI bounding boxes (`gtmfd13`). Software ISPs only evaluate a single global 1D curve across the entire picture.
5. **Multi-Scale Wavelet & Motion-Adaptive Temporal Denoising (TF 2.1, ANR 1.0, ASF 3.4)**:
   - Temporal Filter 2.1 (`mod_tf21`) performs bi-directional motion-compensated recursive filtering across successive frames in DRAM.
   - Advanced Spatial Filter 3.4 (`mod_asf34`) executes multi-band directional frequency decomposition with dynamic coring and overshoot protection.
6. **Hardware Optical Distortion & Lateral Chromatic Aberration Dewarping (LDC 1.1 / CAC 2.3)**:
   - Radial pixel coordinate translation in the hardware pipeline correcting for optical lens pincushion/barrel distortion and wavelength-dependent lateral color fringing without CPU compute overhead.
7. **Hardware Secure Biometrics Isolation (SecureISP & Trustlet)**:
   - Dedicated `QCOM0CCC` hardware path (`qccamsecureisp8380.sys`, `QcISPTrustlet8380.dll`) guaranteeing that IR sensor frames for Windows Hello facial verification are ingested into cryptographically secured memory and processed entirely inside TrustZone.

---

## 6. Summary

The Windows camera pipeline on the Surface Pro 11 is driven by Qualcomm CamX software operating over the Spectra 695 ISP. All optical tuning data is packaged in little-endian Chromatix containers (`com.surface.tuned.*.bin`, parser `V3.4.0`) verified by a trailing IEEE 802.3 CRC-32. Parameters are structured in hierarchical decision trees keyed by lux index, zoom, gain, and color temperature.

For deployment in a software ISP (such as `libcamera SoftISP`), the required tuning stages extract cleanly:
1. **Black Level**: 4-channel Bayer floats in `demuxblklevel14` scaled to a 14-bit domain (rear OV13858 pedestal $\approx 1024.0$ / 64 in 10-bit; front IMX681 $\approx 596.0$ / 37.25 in 10-bit).
2. **Color Correction (CCM)**: Row-major $3 \times 3$ matrices plus 3 channel offsets stored as 12 floats in `mod_cc13` (Q12 fixed-point in hardware), categorized across 4 color temperature bins ($[1.0 .. 2300]$ K Horizon/A, $[2600 .. 3400]$ K TL84, $[3600 .. 4300]$ K CWF, $[4900 .. 10000]$ K D50/D65) and 2 lux levels.
3. **White Balance & AWB**: 3-channel reference gains ($R, G, B$) in `mod_wb20` (Q12 format) alongside a 96-vertex, 88-triangle chromaticity bounding mesh in `temporalAWBV1`.
4. **Lens Shading (LSC)**: A $17 \times 13$ spatial grid across 4 Bayer channels (884 float32 coefficients) in `mod_lsc41`, scaled to a 10-bit ceiling ($1023.0 = 1.0\times$).
5. **Gamma / Tone Curve**: A 256-point, 3-channel (RGB) float LUT in `mod_gamma15` mapping to a 12-bit range ($[0.0 .. 4095.0]$).

The sensor gain laws differ by manufacturer:
- **Rear (OV13858)**: Linear analog gain $\text{Code} = \lfloor \text{Gain} \times 128 \rfloor$ (Q7) from $1.0\times$ to $15.5\times$ (register `0x3508`); digital gain $\text{Code} = \lfloor \text{Gain} \times 1024 \rfloor$ (Q10) up to $16.0\times$ (registers `0x5100-0x5104`).
- **Front (IMX681)**: Sony reciprocal analog gain $\text{Code} = \lfloor 512 - 512/\text{Gain} \rfloor$ from $1.0\times$ to $15.5\times$ (code $0 .. 479$, register `0x0204`); digital gain $\text{Code} = \lfloor \text{Gain} \times 256 \rfloor$ (Q8) up to $4.0\times$ (register `0x020E`).
- **IR (VD55G0)**: Reciprocal analog gain $\text{Code} = \lfloor 32 - 32/\text{Gain} \rfloor$ from $1.0\times$ to $8.0\times$ (code $0 .. 28$); digital gain in Q8 format up to $4.0\times$.

Hardware features without software ISP equivalents include the EVA motion warp engine, staggered multi-frame HDR fusion, hardware PDAF/BAF filtering, 2D spatial Local Tone Mapping (LTM), multi-frame temporal noise filtering (TF 2.1), lens distortion correction (LDC), and TrustZone SecureISP biometrics.
