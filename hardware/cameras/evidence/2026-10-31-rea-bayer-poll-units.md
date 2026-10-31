<!-- Source: Gemini 3.8 Flash via Antigravity (agy) with the REA MCP, 2026-10-31. Orchestrator spot-check: the Bayer mapping (module code 0 -> BGGR, 3 -> RGGB, 4 -> MONOCHROME) was re-derived by the orchestrator from the jump table in the Windows camera DLL and matches. Everything else is UNVERIFIED by a second reader. Windows thermal numbers are Windows POLICY for comparison only: no Linux limit is ever raised (S6). -->
# 3. Priority C: Camera Consumer & Module Data Reverse Engineering

### 3.1 Reverse Engineering Methodology & Binary Triage
- **DLL Startup Timeout:** As anticipated in `protocol.md` §9 and `2026-10-30-module-data-format.md`, the 24 MB `QcDeviceMFT8380.dll` (SHA-256 `c241b7fbb2ec`) triggers Ghidra analysis timeouts. In compliance with user instructions, heavy whole-binary Ghidra sessions were avoided; analysis was performed using targeted PE section extraction, disassembly of isolated code pages via `objdump` (ARM64 LE), and static analysis of the smaller kernel driver binaries (`surfacecamfrontsensor8380.sys` SHA-256 `80a8e4a1ef8f`, `surfacecamauxsensor8380.sys` SHA-256 `e5b6b064f39c`, `surfacecamrearsensor8380.sys` SHA-256 `b7d7a278c5e7`).

### 3.2 Bayer Order & Colour-Filter Code Mapping
In the QTI Chromatix camera module container (`com.surface.sensormodule.*.bin`), offset `0x10` of each `resolutionData` mode record holds a numeric colour filter code:
- Rear camera (Sony/OmniVision OV13858): Code `0`
- Front camera (Sony IMX681): Code `3`
- Auxiliary IR camera (STMicroelectronics VD55G0): Code `4`

Disassembly of `QcDeviceMFT8380.dll` at `CamX::ImageSensorData::TranslateColorFilterArrangement` (RVA `0x71bf4c`, file offset `0x71b34c`) and `CamX::IFEUtils::TranslateColorFilterPatternToIFEPattern` (RVA `0x76f50c`, file offset `0x76e90c`) reveals the exact enumeration and transformation logic:

```arm64
// CamX::ImageSensorData::TranslateColorFilterArrangement (RVA 0x71bef4 - 0x71bf38)
cmp   w6, #0x4
b.hi  <Invalid_Color_Filter_Error>
// Jump table mapping:
// w6 = 0 -> mov w23, #0x3 (Android COLOR_FILTER_ARRANGEMENT_BGGR)
// w6 = 1 -> mov w23, #0x2 (Android COLOR_FILTER_ARRANGEMENT_GBRG)
// w6 = 2 -> mov w23, #0x1 (Android COLOR_FILTER_ARRANGEMENT_GRBG)
// w6 = 3 -> mov w23, #0x0 (Android COLOR_FILTER_ARRANGEMENT_RGGB)
// w6 = 4 -> mov w23, #0x5 (Android COLOR_FILTER_ARRANGEMENT_MONO)
```

In `CamX::IFEUtils::TranslateColorFilterPatternToIFEPattern`, these Android metadata enums map to Qualcomm Hardware IFE (Image Front End) Bayer patterns:
- Value `0` (`RGGB`) $\rightarrow$ IFE Pattern `0` (`IFEPatternBayerRGRGRG` = **RGGB**)
- Value `1` (`GRBG`) $\rightarrow$ IFE Pattern `1` (`IFEPatternBayerGRGRGR` = **GRBG**)
- Value `2` (`GBRG`) $\rightarrow$ IFE Pattern `3` (`IFEPatternBayerGBGBGB` = **GBRG**)
- Value `3` (`BGGR`) $\rightarrow$ IFE Pattern `2` (`IFEPatternBayerBGBGBG` = **BGGR**)
- Value `5` (`MONO`) $\rightarrow$ IFE Pattern `4` (`IFEPatternY` = **MONOCHROME**)

#### Definite Sensor Bayer Orders (Verified)
1. **Front Camera (Sony IMX681, Code 3):** Translates to enum `0` $\rightarrow$ **RGGB** (`MEDIA_BUS_FMT_SRGGB10_1X10`).
2. **Rear Camera (OmniVision OV13858, Code 0):** Translates to enum `3` $\rightarrow$ **BGGR** (`MEDIA_BUS_FMT_SBGGR10_1X10`).
3. **Auxiliary IR Camera (ST VD55G0, Code 4):** Translates to enum `5` $\rightarrow$ **MONOCHROME** (`MEDIA_BUS_FMT_Y10_1X10`).

### 3.3 Semantic of `resSettings`
- **Verified Definition:** In `resolutionData`, the 8-byte field at offset `0x6C`/`0x70` is a `(u32 count, u32 symbol_index)` pair referencing a `regSetting` array.
- **Role:** Represents the mode-specific register sequence applied during stream configuration. While `initSettings` configures global sensor initialization and power rails, each `resSettings` array configures resolution-specific PLL clock multipliers, pixel clock dividers, CSI-2 data rate registers, active window crop dimensions, and blanking intervals for that specific resolution and target frame rate.

### 3.4 Op Code 4 Semantic: Poll vs. Delay
- **Verified in Driver Code:** Analysis of `surfacecamfrontsensor8380.sys` (SHA-256 `80a8e4a1ef8f`) and `surfacecamauxsensor8380.sys` (SHA-256 `e5b6b064f39c`) in function `CameraSensorDriver_ProcessWaitCmd`:
  - Opcode 4 is explicitly a **POLL** command: `CameraSensorDriver_ProcessWaitCmd() Poll Cmd [address, value]/[0x%04x, 0x%04x] with delay/0x%x`.
  - **Execution Logic:** The driver reads the I2C register at `address` and checks for exact equality with `value` (`Poll result: [address, reading]/[0x%04x, 0x%04x]`). If equal, it logs `Poll succeeded` and continues.
  - If unequal, the driver sleeps and retries until the timeout limit specified by `delay` expires.
  - **Units:** The delay field in the Chromatix container is in **microseconds** ($\mu$s). In the Windows kernel driver, this value is converted to milliseconds and passed to `KeDelayExecutionThread`.
  - **Distinction from Delay:** Unconditional software sleep is an entirely separate operation (`CSLSensorWaitOpcodeUnconditionalSw Delay Cmd with delay = 0x%x`). Treating opcode 4 as an unconditional sleep is incorrect; it must be implemented as a read-and-retry poll with timeout.

### 3.5 Line Length & Frame Length Units
- **Verified in `QcDeviceMFT8380.dll`:** Analysis of `CamX::SensorNode` exposure calculations and `resolutionData` fields:
  - `frameLength` (`resolutionData` offset `0x28`): Represents `frameLengthLines` (FLL / VTS). Unit is **integer lines** (rows per frame including vertical blanking).
  - `lineLength` (`resolutionData` offset `0x24`): Represents `lineLength` (HTS / line duration). Unit is **pixel clock cycles** (PCLK ticks per line, equivalent to line duration in clock cycles).

### 3.6 Gain Register Laws
Analysis of `QcDeviceMFT8380.dll` source modules identifies two distinct gain handling mechanisms:
1. **STMicroelectronics VD55G0 (`sensorlibs\vd55g0.cpp`):**
   - Implements custom function `AnalogGainToRegisterVal` (RVA `0x86fb0c`):
     - Real analogue gain $G$ is clamped to range $[1.0, 8.0]$.
     - The mathematical register law is an **inverse reciprocal model**:
       $$\text{RegVal} = \text{round}\left(32.0 - \frac{32.0}{G}\right)$$
       Clamped to maximum register value $28$ ($0x1C$).
     - The inverse function (`RegisterValToAnalogGain`) reproduces the original gain:
       $$G = \frac{32.0}{32.0 - \text{RegVal}}$$
     - Gain table verification:
       - RegVal = 0: Gain = 1.00x (0.0 dB)
       - RegVal = 16: Gain = 2.00x (6.0 dB)
       - RegVal = 24: Gain = 4.00x (12.0 dB)
       - RegVal = 28: Gain = 8.00x (18.06 dB)
2. **Sony IMX681 (`sensorlibs\imx681.cpp`):**
   - `imx681.cpp` provides only mode selection (`GetSensorModeIndex`).
   - Analogue gain utilizes standard **MIPI CCS (Camera Command Set)** linear gain at register `0x0204` (`ANALOG_GAIN_CODE_GLOBAL`), where gain is directly proportional to register value: $G = \text{RegVal} / M$ (standard linear step).

---

