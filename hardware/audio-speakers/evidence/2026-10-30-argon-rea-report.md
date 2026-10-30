<!-- Source: Gemini 4 Argon via Antigravity (agy) with the REA MCP, 2026-10-30. Orchestrator spot-check (not the whole report): acdb_cal_0D.acdb sha256 prefix a0a8635b matches; module id 0x070010e2, event 0x0800138c, MAX_RATED_TEMP 0x08001510 and Re 0x08001535 occur in the file; SpeakerCoolDownTimerInSec = 0xB4 (180 s) in surface_audiominiext8380.inf. Everything else is UNVERIFIED by a second reader. Per-unit calibration values are quoted for design only; S1 stays in force. -->
# Surface Pro 11 (`MSHW0486` / `REV_0D`) Audio & Speaker Protection Clean-Room REA Report

## 1. Executive Safety Verdict (`plan/risks.md` `S1`)

- **[Verified] Speakers MUST remain off until closed-loop DSP V/I speaker protection is active and evidenced.** On Windows, Surface Pro 11 (`SUBSYS_MSHW0486&REV_0D`, "Colchuck D") does **not** protect its two `4 Ω` micro-speakers with a static volume cap (`MaxEpVolume = 0.0 dBFS`, analog PA target gain `+16.50 dB`). Instead, it runs Qualcomm Aqstic **Speaker Protection v5 (`SPv5`)** on the Hexagon ADSP (`qcadsp8380.mbn`, `921870a8`), combining feedforward excursion/thermal modeling (`0x070010e2`), real-time 4-channel `8,000 Hz` / `32-bit` V/I sense feedback (`0x070010e3`), and 2-channel `24,000 Hz` / `32-bit` CPS Class-H feedback (`0x070010e4`) coupled over AudioReach inter-module control links (`0x08001061`).
- **[Verified] Upstream Linux 7.3 (`sources/linux/sound/soc/qcom/x1e80100.c:35-52`) and `out/ref/archiso-aarch64-sp11/README.md:26` rely solely on open-loop static gain caps** (`WSA_RX0/1 Digital Volume <= 81` = `-3.0 dB`; `SpkrLeft/Right PA Volume <= 6` = `0.0 dB`, ~`19.5 dB` below Windows's `+16.5 dB` PA + `0 dBFS` ceiling) and **lack functional closed-loop V/I feedback** (broken `wsa884x.c` TX ports, missing AudioReach IMCL links and calibration loader, wrong right-speaker SoundWire CPS port and reset GPIO in `x1-microsoft-denali.dtsi`, and 1S instead of 2S WSA8845 power/protection registers). Under `plan/risks.md` `S1`, a static volume cap is **not** speaker protection.
- **[Verified] Microphones are safe to enable immediately.** Surface Pro 11 has **2 digital PDM MEMS microphones** (`MicArray1`) on LPASS VA Macro `DMIC0`/`DMIC1` (`dmic01`, `VA_CODEC_DMA_TX_0`) powered by `1.8 V` `LDO1_B` (`vreg_l1b_1p8`), with **no 3.5 mm headset codec (`IsMBHCReq = 0`)** and zero physical thermal/excursion hazard.

---

## 2. Analyzed Windows Artifacts (File Names & Short SHA-256 Prefixes Only)

All binaries were checked against `sources/binary-catalog.tsv` before analysis; code binaries were inspected one at a time in MCP `rea` with SHA-256 verification and closed before opening the next; data blobs (`data`) were parsed structurally without disassembly.

| File Name | SHA-256 Prefix | Role on Surface Pro 11 (`SUBSYS_MSHW0486&REV_0D`) |
| :--- | :--- | :--- |
| `qcaucd8380.sys` | `bd0c8276` | **[Verified]** Audio Codec Driver (`AUCD\QCOM0C29`): programs LPASS WSA/VA macros, SoundWire masters, and WSA8845 registers/GPIOs. |
| `qcaucd8380.inf` | `b1466909` | **[Verified]** Base INF for `qcaucd8380.sys` (`SlaveConnectionType = 1` internal boost). |
| `surface_aucdext8380.inf` | `eae4bc6c` | **[Verified]** Surface extension INF for `MSHW0486`: sets `IsMBHCReq = 0`, `ExternalMicBiasNeeded = 1`, `NoofGPIOs = 2` (`WSA_EN`, `WSA2_EN`). |
| `ACDResources.bin` | `23c4beab` | **[Verified]** `PRM` power-resource definition for `AUCD` (`LDO15_B` `1.8 V` for WSA8845, `LDO1_B` `1.8 V` for DMICs, SoundWire/LPASS clocks). |
| `qcadcm8380.sys` | `37f76305` | **[Verified]** Audio DSP Calibration & Graph Manager (`ADSP\QCOM0C22`, GSL): loads ACDB v4, injects `SPv5` VI endpoint config & calibrated `R0/T0`, handles diagnostics/calibration events. |
| `qcadcm8380.inf` | `4d9443da` | **[Verified]** Base INF for `qcadcm8380.sys`: sets `SpkrProtVIInfo` (`SamplesPerSecond = 8000`, `BitsPerSample = 32`). |
| `surface_acsp8380.inf` | `df97a908` | **[Verified]** Surface calibration extension INF mapping `SUBSYS_MSHW0486&REV_0D` (`AudioCalibSettings\AcbdFilePath1`) to `REV_0D\acdb_cal_0D.acdb`. |
| `acdb_cal_0D.acdb` | `a0a8635b` | **[Verified]** Active ACDB v4 database (`REV_0D`) selected on this unit (`rev-selection.txt`, `41742f85`): holds all 172 AudioReach subgraphs and `SPv5` excursion/thermal/gain parameters. |
| `workspaceFile_0D.qwsp` | `11ed6932` | **[Verified]** Qualcomm AudioReach Workspace XML metadata companion to `acdb_cal_0D.acdb` (not loaded at runtime by `qcadcm8380.sys`). |
| `ADCMResources.bin` | `ed199332` | **[Verified]** `PRM` DSP/bus/clock resource votes for `qcadcm8380.sys`. |
| `qcaudminiport8380.sys` | `79b26804` | **[Verified]** WaveRT/PortCls miniport library: implements the `SpeakerCoolDownTimerInSec` (`180 s`) silence timer and factory/field `R0/T0` VI calibration state machine. |
| `qcaudminiport_Base8380.inf` | `3921ff04` | **[Verified]** Base INF for `qcaudminiport8380.sys`. |
| `surface_audiominiext8380.inf` | `5acd5091` | **[Verified]** Surface miniport extension INF (`REV_0D`): endpoint volumes, 2-mic array geometry, `SpeakerCoolDownTimerInSec = 180`, `IsSpeakerProtQuickCalib = 0`. |
| `AudioResourceConstraints_8380.xml` | `f7edceb8` | **[Verified]** Concurrency & resource constraints config for 8380 audio endpoints. |
| `qcasd8380.sys` | `10d6f600` | **[Verified]** ACX streaming endpoint driver (`ASD\...`) actively bound on Surface Pro 11 for Speaker, `MicArray1`, DisplayPort, and Sideband endpoints. |
| `qcasd8380.inf` | `334f211e` | **[Verified]** Base INF for `qcasd8380.sys`. |
| `surface_asdext8380.inf` | `30403fe6` | **[Verified]** Active Surface ACX extension INF (`REV_0D`): configures Speaker (`-12.0 .. 0.0 dBFS`), `MicArray1` (`+14.0 .. +24.0 dB`, 2-mic array), Dolby & Surface APO bindings. |
| `qcaudminiport_apo8380.inf` / `ProxyAPO.dll` | `e0fb5b93` / `1aeb4581` | **[Verified]** PortCls host proxy APO forwarding MFX/EFX/SFX effects to the ADSP graph. |
| `qcasd_apo8380.inf` / `AcxProxyAPO.dll` | `34fa3102` / `c44ac175` | **[Verified]** Active ACX host proxy APO forwarding effects to the ADSP graph. |
| `AUCD_DEV_0C29_SUBSYS_MSHW0486_REV_0D_ADCM_SUBSYS_MSHW0486.xml` | `985a6e6e` | **[Verified]** Dolby DAX3 speaker/endpoint tuning profile for `MSHW0486` `REV_0D`. |
| `SurfaceAPO_0D.json` | `4bff5c66` | **[Verified]** Surface host APO config for `REV_0D` (all 6 EQ stages disabled / `0 dB`). |
| `SurfaceIhvAudioFilterDriver.sys` / `.inf` | `d31267b8` / `9226ba43` | **[Verified]** Upper filter on `AUCD\QCOM0C29` strictly enforcing UEFI DFCI enterprise mic disablement (`MicEnableData` -> `InstallEndpoint`); zero speaker-protection role. |
| `qcadc8380.sys` / `.inf` | `79256eec` / `a9f0a5e5` | **[Verified]** Qualcomm PMIC VADC sensor driver (`ACPI\QCOM0C11`, `ADC1.bin`), unrelated to audio codecs. |
| `qcadsp8380.mbn` | `921870a8` | **[Verified]** Signed Hexagon ADSP firmware containing `capi_spv5`, `capi_vi_v5`, and `capi_cps_data_router`. |
| `adsp_dtbs.elf` | `544bd795` | **[Verified]** ADSP device-tree blob (`hamoa-adsp`, `swr0`/`swr1`/`swr2` LPASS SoundWire controller definitions). |
| `dsdt.dsl` | `8a7b849b` | **[Verified]** Surface Pro 11 ACPI DSDT (`ADSP` -> `ADCM` -> `AUCD`, GPIOs `204` & `205`, SoundWire IRQ `202`). |
| `reg-audio-dump.txt` / `rev-selection.txt` | `145ff751` / `41742f85` | **[Verified]** Live Windows registry dump confirming active `REV_0D` selection and `ASD` endpoints. |

---

## 3. Speaker Protection Design, Concrete Limits, Tuning Storage & WSA8845 Programming

### 3.1 DSP Speaker Protection Architecture (`SPv5` Closed-Loop FF + FB + CPS)

- **[Verified]** Windows runs **Qualcomm Aqstic Speaker Protection v5 (`SPv5`)** inside AudioReach **Device RX Subgraph `0xb0000001`** (`acdb_cal_0D.acdb`, `a0a8635b`; `qcadsp8380.mbn`, `921870a8`). Unlike open-loop limiters, `0xb0000001` runs four containers concurrently across one forward playback path and two real-time hardware feedback paths from the two WSA8845 amplifiers:
  1. **Forward RX Processing (`Container 0xe0000001`)**:
     - `SAL` (`0x07001010`, instance `0x4001`, peak limiter `0x0800101e` enabled) -> `DATA_LOGGING` (`0x07001013`, instance `0x402c`, tap `0x19b2`) -> **`SPEAKER_PROTECTION` (`0x070010e2`, `capi_spv5`, instance `0x4027`)** -> `SPLITTER` (`0x07001011`, instance `0x4002`) -> `MFC` (`0x0700101a`, instance `0x4003`) -> **`CODEC_DMA_SINK` (`0x07001023`, instance `0x4157`)** driving `LPAIF_WSA` `WSA_CODEC_DMA_RX_0` (`lpaif_type = 2`, `intf_index = 1`, `active_channels_mask = 0x3`) at **`48,000 Hz`, `16/24-bit`, 2 channels** (Left + Right).
  2. **Real-Time V/I Sense Feedback (`Container 0xe0000007`, FBSP)**:
     - **`CODEC_DMA_SOURCE` (`0x07001024`, instance `0x4026`)** capturing `LPAIF_WSA` `WSA_CODEC_DMA_TX_0` (`lpaif_type = 2`, `intf_index = 1`, `active_channels_mask = 0xf`) at **`8,000 Hz`, `32-bit`, 4 channels** (`[Vsense_L, Isense_L, Vsense_R, Isense_R]`) -> `MFC` (`0x0700101a`, instance `0x4025`) -> **`SPEAKER_PROTECTION_VI` (`0x070010e3`, `capi_vi_v5`, instance `0x4024`)**.
     - Linked to `SPEAKER_PROTECTION` (`0x4027`) via AudioReach **Inter-Module Control Link (`IMCL`, param `0x08001061`)**: `0x4024` control port `0x80000000` <-> `0x4027` control port `0x80000000` (intent `0x08001204`), streaming live voice-coil resistance `Re(t)`, estimated temperature `T(t)`, excursion adaptation, and fault flags.
  3. **Real-Time CPS / Class-H Feedback (`Containers 0xe0000005` & `0xe0000006`)**:
     - **`CODEC_DMA_SOURCE` (`0x07001024`, instance `0x402b`)** capturing `LPAIF_WSA` `WSA_CODEC_DMA_TX_2` (`lpaif_type = 2`, `intf_index = 3`, `active_channels_mask = 0x3`) at **`24,000 Hz`, `32-bit`, 2 channels** -> `MFC` (`0x0700101a`, instance `0x402a`) -> `0x07001098` (instance `0x4029`) -> **`CPS_DATA_ROUTER` (`0x070010e4`, `capi_cps_data_router`, instance `0x4028`)**.
     - Linked to `SPEAKER_PROTECTION` (`0x4027`) via **`IMCL` (`0x08001061`)**: `0x4028` control port `0x80000000` <-> `0x4027` control port `0x80000001` (intent `0x08001537`, dynamic Class-H / rail envelope tracking).

### 3.2 Concrete Speaker-Protection Parameters & Safe-Limit Numbers (`REV_0D`)

All values below are extracted from `acdb_cal_0D.acdb` (`a0a8635b`), `qcadcm8380.inf` (`4d9443da`), `qcadcm8380.sys` (`37f76305`), `qcaudminiport8380.sys` (`79b26804`), and `surface_audiominiext8380.inf` (`5acd5091`).

| Parameter / Limit | Param ID / Key | Value (Left / Ch 0) | Value (Right / Ch 1) | Grade & Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Speaker count & nominal load** | `num_ch`, `rload` | **2 speakers total** (`Ch 0` Left), **`4 Ω` class** | (`Ch 1` Right), **`4 Ω` class** | **[Verified]** `acdb_cal_0D.acdb` (`a0a8635b`), `qcaucd8380.sys` (`bd0c8276`). |
| **Nominal voice-coil DC resistance (`Re`)** | `0x08001535` (Q24 Ω on `0x4024`) | **`4.924 Ω`** | **`4.758 Ω`** | **[Verified]** Per-speaker asymmetric acoustic enclosure/trace tuning in `acdb_cal_0D.acdb` (`a0a8635b`). |
| **Valid calibrated `R0` acceptance window** | `0x080011f6` (Q25 Ω on `0x4024`) | **`3.00 Ω .. 6.25 Ω`** | **`3.00 Ω .. 6.25 Ω`** | **[Verified]** Out-of-range `R0` rejects calibration / flags open or shorted coil. |
| **Un-calibrated fallback `R0` / `T0`** | `0x080011f5` (Q24 Ω / Q6 °C) | **`3.200 Ω` @ `25.0 °C`** | **`3.200 Ω` @ `25.0 °C`** | **[Verified]** Conservative low-`R0` fallback (overestimates `T(t)` until calibrated `R0CalQ24`/`T0CalQ6` is loaded). |
| **Voice-coil temp coefficient (`alpha` / TCR)** | `0x080011f6` (Q22 `1/°C`, Q6 `Tref`) | **`0.00406 / °C`** @ **`30.0 °C`** | **`0.00406 / °C`** @ **`30.0 °C`** | **[Verified]** Copper/alloy voice-coil thermal slope used by `capi_vi_v5` (`qcadsp8380.mbn`, `921870a8`). |
| **Hard maximum rated coil temperature** | `0x08001510` (`MAX_RATED_TEMP`, Q6 °C) | **`110.0 °C`** | **`110.0 °C`** | **[Verified]** Hard limit on `0x4027`; exceeding triggers `0x0800138c` diagnostics event `condition = 4` (thermal overshoot). |
| **Thermal PI+D controller target ceiling** | `0x08001367` (Q6 °C on `0x4027`) | **`100.0 °C`** | **`100.0 °C`** | **[Verified]** Active gain-reduction setpoint (`10.0 °C` safety margin below `110.0 °C` max rated temp). |
| **Target analog PA / system gain** | `0x0800134a`, `0x08001258` (Q24 dB) | **`+16.50 dB`** (`G_16P5_DB`) | **`+16.50 dB`** (`G_16P5_DB`) | **[Verified]** Matches WSA8845 gain step `0x21` (`33 * 0.5 dB`); low-`Vbatt` backoff step **`-3.0 dB`**. |
| **Pilot tone & feature mask** | `0x080011e8` (`0x4027`) | **`-40 dB`**, `features = 0x1f` | **`-40 dB`**, `features = 0x1f` | **[Verified]** Sub-audible pilot tone keeps `Re(t)`/`T(t)` observable during quiet/zero-crossing passages. |
| **Pre-SPv5 `SAL` digital peak limiter** | `0x0800101e`, `0x08001020` (`0x4001`) | **`-0.087 dBFS`** (`enable = 1`) | **`-0.087 dBFS`** (`enable = 1`) | **[Verified]** Hard full-scale digital ceiling entering `0x4027`. |
| **Non-linear excursion model tables** | `0x08001532`, `0x08001368`, `0x08001534` | 636 B + 600 B + 576 B | Included in dual-ch payloads | **[Verified]** Full Thiele-Small + non-linear `Bl(x)` / `Kms(x)` excursion-limiting polynomials in `acdb_cal_0D.acdb` (`a0a8635b`). **[Unknown]** Exact `Xmax` in mm is encoded in the Q-scaled DSP state-space matrices inside `0x08001532`/`0x08001368`. |
| **RX playback hardware EP rate / width** | `WSA_CODEC_DMA_RX_0` (`0x4157`) | **`48,000 Hz`**, `16/24-bit`, 2 ch | (Shared stereo DMA) | **[Verified]** `acdb_cal_0D.acdb` (`a0a8635b`). |
| **VI sense feedback EP rate / width** | `WSA_CODEC_DMA_TX_0` (`0x4026`), `SpkrProtVIInfo` | **`8,000 Hz`**, **`32-bit`**, 4 ch (`V_L, I_L, V_R, I_R`) | (Shared 4-ch DMA) | **[Verified]** `qcadcm8380.inf` (`4d9443da`), `qcadcm8380.sys` (`37f76305`), `acdb_cal_0D.acdb` (`a0a8635b`). |
| **CPS Class-H feedback EP rate / width** | `WSA_CODEC_DMA_TX_2` (`0x402b`) | **`24,000 Hz`**, **`32-bit`**, 2 ch (`CPS_L, CPS_R`) | (Shared 2-ch DMA) | **[Verified]** `acdb_cal_0D.acdb` (`a0a8635b`). |
| **Cooldown silence timer for `R0/T0` cal** | `SpeakerCoolDownTimerInSec`, `IsSpeakerProtQuickCalib` | **`180 s`**, `QuickCalib = 0` | **`180 s`**, `QuickCalib = 0` | **[Verified]** `surface_audiominiext8380.inf` (`5acd5091`), `qcaudminiport8380.sys` (`79b26804`). |
| **DC fault & thermal overshoot shutdown** | `0x0800138c` (`EVENT_ID_SPv5_SPEAKER_DIAGNOSTICS`) | `cond = 3` (DC), `cond = 4` (Temp) | `cond = 3` (DC), `cond = 4` (Temp) | **[Verified]** `qcadcm8380.sys` (`37f76305`) registers `0x0800138c` on `0x4027` and tears down / flags speaker fault on trigger. |

### 3.3 Where Tuning & Per-Unit Calibration Data Live on Windows

1. **[Verified] Static Subgraphs & `SPv5` Tuning (`REV_0D\acdb_cal_0D.acdb`, `a0a8635b`)**:
   - Selected dynamically by `qcadcm8380.sys` (`37f76305`) matching ACPI `SUBSYS_MSHW0486` + board revision `REV_0D` against `HKR,AudioCalibSettings,AcbdFilePath1` in `surface_acsp8380.inf` (`df97a908`; confirmed in `rev-selection.txt`, `41742f85`).
   - `qcadcm8380.sys` (`37f76305`) also checks for optional runtime delta files `*.acdbdelta` alongside the `.acdb` path (`PersistData` flag).
2. **[Verified] VI Stream & Cooldown Registry Keys**:
   - `HKR,ADCM\SpkrProtVIInfo` (`qcadcm8380.inf`, `4d9443da`): `SamplesPerSecond = 8000`, `BitsPerSample = 32` — read by `SetSpkrProtEffectEpConfig` in `qcadcm8380.sys` (`37f76305`) to configure `WSA_CODEC_DMA_TX_0`.
   - `HKR,QCAUD\Feature\SpeakerProtection` (`surface_audiominiext8380.inf`, `5acd5091`): `SpeakerCoolDownTimerInSec = 180`, `IsSpeakerProtQuickCalib = 0`.
3. **[Verified] Per-Unit Voice-Coil Calibration (`R0CalQ24`, `T0CalQ6`, `UseCalibR0T0`)**:
   - Stored in the WDF driver persistent-state registry tree opened via `WdfDriverOpenPersistentStateRegistryKey` by `qcadcm8380.sys` (`37f76305`) under subkeys **`SpeakerProtectionInfo\0`** (Left) and **`SpeakerProtectionInfo\1`** (Right) as `DWORD` values **`R0CalQ24`** (calibrated DC resistance in Q24 Ω) and **`T0CalQ6`** (ambient calibration temperature in Q6 °C), gated by **`SpeakerProtectionInfo\UseCalibR0T0`**.
   - Note: `reg-audio-dump.txt` (`145ff751`) only exported `HKLM\SYSTEM\CurrentControlSet\Enum\...` and `Control\Class\{4d36e96c-...}`, not the WDF `DriverData` persistent-state hive where `SpeakerProtectionInfo\{0,1}` resides (**[Unknown]** exact per-unit factory `R0CalQ24` integers on this individual tablet without dumping `DriverData`, though `qcaudminiport8380.sys` `79b26804` automatically re-measures them after `180 s` of speaker cooldown via ADSP calibration mode and event `0x08001511` if absent).

### 3.4 WSA8845 Hardware Protections & Register Programming (`qcaucd8380.sys`, `bd0c8276`)

- **[Verified]** Surface Pro 11 runs its two **WSA8845** smart amplifiers in **internal-boost (`SlaveConnectionType = 1`), 2S battery-stack (`2S` stack bits `0x3501 & 0x3`), `4 Ω` nominal load** mode. `qcaucd8380.sys` (`bd0c8276`) programs the following safety-critical registers (compared directly against Linux 7.3 `sources/linux/sound/soc/codecs/wsa884x.c`):

| WSA8845 Register | Function / Protection Feature | Windows (`qcaucd8380.sys`, `bd0c8276`) | Linux 7.3 (`wsa884x.c`) | Safety Impact |
| :--- | :--- | :--- | :--- | :--- |
| `0x3040` (`TOP_CTRL1`) | Low-Vbat OCP threshold mode | **`0xd2`** (2S: disables 1S low-Vbat OCP shift) | **`0xd3`** (`0xd2` commented out at `wsa884x.c:1395-1398`!) | **[Verified]** Wrong 1S OCP threshold on 2S rail in Linux. |
| `0x304c` (`OCP_CTL`) | PA Over-Current Protection limit | **`0xf6`** (for `4 Ω` / `6 Ω` loads) | **`0xc6`** (reset default) | **[Verified]** Windows explicitly programs `0xf6` for `4 Ω` speakers. |
| `0x3091` (`CURRENT_LIMIT`) | Boost converter peak current limit | **`0xd4` init -> `0x44`** (internal boost; `0x30a5=0xf1`, `0x30aa=0xe3`) | **`0x44` init -> overwritten back to `0xd4`** on PMU (`wsa884x.c:967,1686`) | **[Verified]** Linux overwrites `0x44` with `0xd4` on stream power-up! |
| `0x3003` / `0x3004` (`BOP1`/`BOP2_PROG`) | Brown-Out Protection thresholds | `0x22` / **`0x44` (2S)** (`0x66` only for 1S) | `0x22` / **`0x66` (1S hardcoded, `wsa884x.c:1387`)** | **[Verified]** Linux uses 1S brown-out thresholds on a 2S battery. |
| `0x3005` / `0x3006` (`UVLO_PROG`/`1`) | Under-Voltage Lockout thresholds | **`0x33` (2S)** / `0x60` (`0x99` only for 1S) | **`0x99` (1S hardcoded, `wsa884x.c:1388`)** / `0x60` | **[Verified]** Linux uses 1S UVLO thresholds on a 2S battery. |
| `0x34b0` (`DRE_CTL_0`) & `0x34b9` | Dynamic Range Enhancement & min ramp gain | **`0xf0` (2S)** & `0x0e` (`G_0_DB`) | `0xf0` (`e7`->`f0`) & `0x0e` (`wsa884x.c:955,1372`) | **[Verified]** Matches on 2S `0xf0` after init. |
| `0x34d0` (`CLSH_CTL_0`) & `0x34d2` (`CLSH_V_HD_PA`) | Class-H controller & PA headroom | **`0x67` active (`0x00` idle)** & **`0x13` (2S)** | `0x67` & `0x13` (`wsa884x.c:960-961`) | **[Verified]** Matches 2S headroom `0x13`. |
| `0x3504` (`ANA_WO_CTL_0`) | 2S analog watch-out / rail protection | **`0x9d` (2S)** (`0x1d` only for 1S) | **`0x1d` (1S default, `wsa884x.c:995`)** | **[Verified]** Missing bit 7 (`2S` mode) in Linux. |
| `0x3020` (`VSENSE1`) | Voltage-sense ADC front-end attenuation | **`0x67` (`VSENSE_M21_DB`)** at `+16.5 dB` gain (`0x87` `-24 dB` only at `+21 dB`) | **`0x87` (`VSENSE_M24_DB` hardcoded, `wsa884x.c:1484`)** | **[Verified]** `3 dB` Vsense scaling error corrupts `Re = V/I` (`+41%` resistance error -> severe coil temp underestimation!) unless matched to `acdb_cal_0D.acdb`. |
| `0x3021` (`ISENSE2`) | Current-sense ADC front-end gain | **`0x27` (`ISENSE_12_DB`)** for `4 Ω` + `<= +18 dB` | **`0x27` (`ISENSE_12_DB`, `wsa884x.c:1489`)** | **[Verified]** Matches (`+12 dB`). |
| `0x30ba` (`CKWD_CTL_1`) & `0x348b` (`PDM_WD_CTL`) | Clock & PDM watchdogs | `0x1b -> 0x13` & **`0x01`** | `0x1b -> 0x13` & **`0x01`** (`wsa884x.c:810,948,1391`) | **[Verified]** Hardware clock/PDM loss auto-mute enabled in both. |
| `0x34c0` (`TAGC_CTL`) & `0x34c8` (`VAGC_CTL`) | Die over-temp AGC & Vbat AGC | **`0x15`** & **`0x01`** (enabled defaults) | **`0x15`** & **`0x01`** (`wsa884x.c:957,959`) | **[Verified]** Protects **amplifier silicon die** only — **does NOT protect the speaker voice coil**! |
| `0x38a6` (`OTP_REG_38`) & `0x38a8` (`OTP_REG_40`) | Trim / protection OTP overrides | **`0x08`** & **`0x20`** | **`0x00`** (never written) & **`0x20`** (`wsa884x.c:1390`) | **[Verified]** Linux omits `0x38a6 = 0x08`. |

---

## 4. Speaker & Microphone Topology + Device-Tree Hardware Facts

### 4.1 Endpoints Present on Surface Pro 11 (`MSHW0486` / `REV_0D`)

- **[Verified] No 3.5 mm jack / no WCD938x codec**: `surface_aucdext8380.inf` (`eae4bc6c`) sets `IsMBHCReq = 0` and `ExternalMicBiasNeeded = 1`; `reg-audio-dump.txt` (`145ff751`) enumerates only:
  1. **Internal Stereo Speakers** (`ASD\VEN_QCOM&DEV_0C22&SUBSYS_MSHW0486&REV_0D&UID_0`, 2x WSA8845 on `SWR_WSA` / `&swr0`).
  2. **Internal Dual DMIC Array (`MicArray1`)** (`UID_10`, 2x PDM DMICs on LPASS VA Macro `DMIC0`+`DMIC1` / `dmic01`).
  3. **DisplayPort Audio** (`UID_20`..`UID_22`) and **Bluetooth / USB Sideband Offload** (`UID_32`..`UID_35`).

### 4.2 Speakers — SoundWire Addresses, Port Mapping, Supplies & Dual Reset GPIOs

- **[Verified] Bus & Enumeration Addresses (`qcaucd8380.sys` `bd0c8276`, `adsp_dtbs.elf` `544bd795`, `dsdt.dsl` `8a7b849b`)**:
  - Controller: **`SWR_WSA` (`&swr0`, `0x6ad0000`)** on `lpass_tlmm` `gpio10` (`wsa_swr_clk`) and `gpio11` (`wsa_swr_data`), ACPI GSi `202` (`0xCA`), PDC wakeup on `tlmm 203` (`192 + 11`).
  - **Left Speaker (`speaker@0,0`)**: SoundWire EA **`sdw:0:0217:0204:00:00`** (`mfg = 0x0217`, `part = 0x0204`, `version = 0x00`, `unique_id = 0`).
  - **Right Speaker (`speaker@0,1`)**: SoundWire EA **`sdw:0:0217:0204:00:01`** (`unique_id = 1`).
- **[Verified] Power Supplies (`ACDResources.bin`, `23c4beab`)**:
  - `1.8 V` supply: **`LDO15_B` (`&vreg_l15b_1p8`)** (`1,800 mV`), plus `1.2 V` digital I/O rail (`&vreg_l12b_1p2`) and 2S battery VPH feeding WSA8845 internal boost.
- **[Verified] Exact SoundWire Port Mapping (`<DAC COMP BOOST PBR VISENSE CPS>`) (`qcaucd8380.sys`, `bd0c8276`)**:
  - WSA8845 slave ports:
    - Port `1` (`DAC`, RX sink): `ch_mask = 0x1` (1 ch, `2.4 MHz`)
    - Port `2` (`COMP`, RX sink): `ch_mask = 0xf` (4 ch, `600 kHz`)
    - Port `3` (`BOOST`, RX sink): `ch_mask = 0x3` (2 ch, `300 kHz`)
    - Port `4` (`PBR`, RX sink): `ch_mask = 0x1` (1 ch, `48 kHz`, unused in normal playback)
    - Port `5` (`VISENSE`, **TX source**): **`ch_mask = 0x3` (2 ch: V + I, `1.2 MHz`)**
    - Port `6` (`CPS`, **TX source**): **`ch_mask = 0x1` (1 ch, `24 kHz`)**
  - **Left Speaker (`unique_id = 0`) master ports**: **`<1 2 3 7 10 13>`**
  - **Right Speaker (`unique_id = 1`) master ports**: **`<4 5 6 7 11 14>`** (Note: upstream Linux 7.3 `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1106` erroneously has `<4 5 6 7 11 13>`, colliding Right CPS with Left CPS on master port `13`!).
- **[Verified] Two Separate Speaker Reset (`PD_N`) GPIOs (`dsdt.dsl` `8a7b849b`, `surface_aucdext8380.inf` `eae4bc6c`, `qcaucd8380.sys` `bd0c8276`, `pinctrl-x1e80100.c:1759-1781,1824`)**:
  - ACPI `\_SB.ADSP.ADCM.AUCD._CRS` (`dsdt.dsl`, `8a7b849b`) and `surface_aucdext8380.inf` (`eae4bc6c`, `NoofGPIOs = 2`: `WSA_EN`, `WSA2_EN`) provide **two** main-TLMM (`\_SB.GIO0` / `&tlmm`) pins: **`204` (`0xCC`)** and **`205` (`0xCD`)**. `qcaucd8380.sys` (`bd0c8276`) drives both `LOW`, enables `LDO15_B`, waits `2 ms`, and drives both `204` and `205` `HIGH` (`PD_N` active-low reset).
  - In `sources/linux/drivers/pinctrl/qcom/pinctrl-x1e80100.c:1759-1781,1824`, main-SoC `tlmm` pins `192..214` (23 `.egpio_func = 9` pingroups, with PDC wakeups at `193 = 192 + 1` `swr_tx_data0` and `203 = 192 + 11` `wsa_swr_data`) are the **1:1 eGPIO mirror (`+192` offset)** of `lpass_tlmm` pins `0..22` (`hamoa.dtsi:4647`). Therefore:
    - **`tlmm 204` = `lpass_tlmm 12`** (`WSA_EN`, speaker 1 reset)
    - **`tlmm 205` = `lpass_tlmm 13`** (`WSA2_EN`, speaker 2 reset)
  - Upstream Linux 7.3 `x1-microsoft-denali.dtsi:856-863,1089,1101` assigns `<&lpass_tlmm 12 GPIO_ACTIVE_LOW>` to **both** `left_spkr` and `right_spkr` and never configures `lpass_tlmm 13`! (**[Inference]** Which physical speaker is on `lpass_tlmm 12` vs `13` is indistinguishable when both power up together, so configuring `lpass_tlmm 12` on `left_spkr` and `lpass_tlmm 13` on `right_spkr` — and asserting both out of reset before `swr0` bus enumeration — matches Windows's simultaneous `204`+`205` power-up sequence).

### 4.3 Microphones — PDM/DMIC Configuration, Geometry & AudioReach Subgraphs

- **[Verified] Physical DMIC Count, Pins, Clock & Supply (`surface_asdext8380.inf` `30403fe6`, `qcaucd8380.sys` `bd0c8276`, `ACDResources.bin` `23c4beab`)**:
  - **2 digital PDM microphones** (`NumOfMics = 2`, horizontal front-facing subcardioid linear array: `MicArrayType = 0`, `MicType = 2`, `100..11,000 Hz`; Mic 0 Left at `Y = +20 mm`, Mic 1 Right at `Y = -20 mm`, `40 mm` spacing).
  - Connected to **LPASS VA Macro `DMIC0` + `DMIC1` (`dmic01`)** on `lpass_tlmm` **`gpio6` (`dmic1_clk`)** and **`gpio7` (`dmic1_data`)** (rising/falling stereo PDM pair on one clock/data pair), clocked at **`2.4 MHz`**, powered by **`LDO1_B` (`1.8 V`, `&vreg_l1b_1p8`)** — matching `x1-microsoft-denali.dtsi:865-871`.
- **[Verified] AudioReach Microphone Subgraphs (`acdb_cal_0D.acdb`, `a0a8635b`)**:
  - **Standard Record Device TX Subgraph `0xb0000006`** (`Container 0xe0000003`): `CODEC_DMA_SOURCE` (`0x07001024`, instance `0x4158`, `lpaif_type = 3` `LPAIF_VA`, `intf_index = 1` **`VA_CODEC_DMA_TX_0`**, `active_channels_mask = 0x3`) at **`48,000 Hz`, `16/24-bit`, 2 channels** -> `MFC` (`0x0700101a`, instance `0x400f`) -> `DATA_LOGGING` (`0x07001013`, instance `0x4010`), paired with Stream/PP TX subgraphs `0xb000003c..0xb0000043` (with `SMECNS_V2` `0x07001031` / Fluence / Gain).
  - **Low-Power Wake / Voice-Activation TX Subgraphs `0xb000009b` & `0xb00000e2`**: `VA_CODEC_DMA_TX_0` (`lpaif_type = 3`, `intf_index = 1`, `active_channels_mask = 0x3`) at **`16,000 Hz`, `16-bit`, 2 channels** feeding `DAM` (`0x0700108a`) and `SVA` (`0x07001040`).
- **[Verified] Module ID Naming Caveat (`audioreach.h:26-27` vs Windows ACDB)**:
  - Linux `sources/linux/sound/soc/qcom/qdsp6/audioreach.h:26-27` defines `MODULE_ID_MFC = 0x07001015` and `MODULE_ID_DATA_LOGGING = 0x0700101A`. In Windows `acdb_cal_0D.acdb` (`a0a8635b`), **`0x07001013` is `DATA_LOGGING`** (configured with `0x08001031` `PARAM_ID_DATA_LOGGING_CONFIG`) while **`0x0700101a` is `MFC`** (configured with `0x08001024`/`0x0800103a` media format). `qcadsp8380.mbn` (`921870a8`) contains both `0x07001015` and `0x0700101a`; Linux topologies must continue using `0x07001015` for `MODULE_ID_MFC` unless `audioreach.c` is updated.

---

## 5. Windows Default & Maximum Volume / Gain Ceilings

- **[Verified] Speaker Volume & Gain Ceilings (`surface_asdext8380.inf` `30403fe6`, `surface_audiominiext8380.inf` `5acd5091`, `acdb_cal_0D.acdb` `a0a8635b`, Dolby XML `985a6e6e`, `SurfaceAPO_0D.json` `4bff5c66`)**:
  - **Windows Endpoint Volume**: **`DefaultDeviceVolume = -12.0 dBFS`** (`-786,432` in `1/65536 dB`), **`MaxEpVolume = 0.0 dBFS`** (`0`), **`MinEpVolume = -75.0 dBFS`** (`-4,915,200`), **`EpVolumeSteppingDelta = 0.5 dB`** (`32,768`). Stream volume range is likewise **`-75.0 .. 0.0 dBFS`** (`0.5 dB` step). `EnableVolumeLimit` is **not** enabled.
  - **WSA8845 / `SPv5` Target Analog PA Gain**: **`+16.50 dB`** (`G_16P5_DB`, step `0x21`), with `-3.0 dB` low-`Vbatt` backoff and `-0.087 dBFS` `SAL` peak limiter.
  - **Host APOs**: `SurfaceAPO_0D.json` (`4bff5c66`) disables all 6 EQs (`0 dB`). Dolby DAX3 (`985a6e6e`) sets `pregain = postgain = system-gain = volume-leveler-out = peak-level = 0 dB` (`volmax-boost = +6.0 dB` peak-clamped to `0.0 dBFS`, with `audio-optimizer` bands `<= 0 dB` and `regulator-speaker-dist-enable = 1` attenuating `47..844 Hz` down to `-14.875 dB` under heavy drive).
- **[Verified] Microphone Volume & Gain Ceilings (`surface_asdext8380.inf` `30403fe6`, `surface_audiominiext8380.inf` `5acd5091`)**:
  - **Windows `MicArray1` Endpoint Volume**: **`DefaultDeviceVolume = +14.0 dB`** (`+917,504` in `1/65536 dB`), **`MaxEpVolume = +24.0 dB`** (`+1,572,864`), **`MinEpVolume = -85.0 dB`** (`-5,570,560`), **`0.5 dB` step** (`32,768`). (Keep LPASS VA macro hardware decimator digital volume near `0 dB` / moderate gain in ALSA UCM to avoid PDM clipping noted in `out/ref/archiso-aarch64-sp11/README.md:83-86`).

---

## 6. Comparison with Linux 7.3 & `archiso-aarch64-sp11`: Protections Present vs Missing

### 6.1 Protections Present Today in Linux 7.3

1. **[Verified] Open-Loop Static ALSA Gain Caps (`sources/linux/sound/soc/qcom/x1e80100.c:35-52`, `out/ref/archiso-aarch64-sp11/README.md:26`)**:
   - `x1e80100_snd_init()` calls `snd_soc_limit_volume()` to cap `WSA_RX0/1 Digital Volume` at `81` (**`-3.0 dB`**) and `SpkrLeft/Right PA Volume` at `6` (**`0.0 dB`**, vs Windows's `+16.5 dB` PA gain). Per `plan/risks.md` **`S1`**, this static ~`19.5 dB` attenuation is **not** speaker protection (blind to sustained sine waves, low-frequency resonance excursion, DC faults, ambient heating, and 2S rail voltage).
2. **[Verified] Silicon-Die Hardware Watchdogs & Thermal/Vbat AGC (`sources/linux/sound/soc/codecs/wsa884x.c:810,948,957,959,1391,1860`)**:
   - Clock/PDM watchdogs (`CKWD_CTL_1`, `PDM_WD_CTL`), die TSADC temperature readback, and silicon-die `TAGC_CTL` (`0x15`) / `VAGC_CTL` (`0x01`) exist, plus LPASS WSA macro VI-sense decimator routing (`sources/linux/sound/soc/codecs/lpass-wsa-macro.c:1452,1502-1508,2300-2303`) and `WSA_CODEC_DMA_TX_0` / `WSA_CODEC_DMA_TX_2` DAI definitions (`sources/linux/sound/soc/qcom/qdsp6/q6apm-lpass-dais.c:80-82`).

### 6.2 Protections Missing or Broken in Linux 7.3 (Required Before Enabling Speakers Under `S1`)

| Subsystem / File | Exact Linux 7.3 Location | Missing Feature or Bug Blocking Safe Speaker Enablement |
| :--- | :--- | :--- |
| **WSA884x SoundWire TX feedback ports** | `sources/linux/sound/soc/codecs/wsa884x.c:857-899,1844-1858,2082,2093` | **[Verified]** Registers all 6 ports (including TX `VISENSE` port 5 and `CPS` port 6) as `sink_ports` (`SDW_DATA_DIR_RX`) with `source_ports = 0`, no `.capture` DAI capability, and **swapped `ch_mask`s** (`VISENSE` `0x1` instead of `0x3`, `CPS` `0x3` instead of `0x1`). Zero V/I or CPS feedback can leave the codec! |
| **WSA884x 2S / 4 Ω / Vsense registers** | `sources/linux/sound/soc/codecs/wsa884x.c:967,995,1387-1398,1484,1686` | **[Verified]** Uses 1S `TOP_CTRL1=0xd3`, 1S `BOP2_PROG=0x66`, 1S `UVLO_PROG=0x99`, 1S `ANA_WO_CTL_0=0x1d`, default `OCP_CTL=0xc6` (vs `4 Ω` `0xf6`), overwrites `CURRENT_LIMIT` back to `0xd4` on PMU (vs `0x44`), omits `OTP_REG_38=0x08`, and hardcodes `VSENSE_M24_DB` (`0x87`) instead of gain-matched `VSENSE_M21_DB` (`0x67` at `+16.5 dB`). |
| **Denali DT SoundWire port map & 2nd reset GPIO** | `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:309-345,856-863,1089,1101,1106` | **[Verified]** (1) `right_spkr` `qcom,port-mapping` is `<4 5 6 7 11 13>` instead of **`<4 5 6 7 11 14>`**; (2) `right_spkr` shares `lpass_tlmm 12` instead of configuring **`lpass_tlmm 13`** (`tlmm 205`, `WSA2_EN`); (3) `sound` node lacks `WSA_CODEC_DMA_TX_0` (VI sense) and `WSA_CODEC_DMA_TX_2` (CPS) DAI links. |
| **AudioReach IMCL control links (`0x08001061`) & CPS (`0x070010e4`)** | `sources/linux/sound/soc/qcom/qdsp6/audioreach.c:551-588`, `audioreach.h:36-38` | **[Verified]** `audioreach_alloc_graph_pkt()` only emits data connections (`APM_PARAM_ID_MODULE_CONN` `0x08001004`) and **cannot emit IMCL control-port connections (`0x08001061`)**; `MODULE_ID_CPS_DATA_ROUTER` (`0x070010e4`) is absent. Without `0x08001061`, `SPEAKER_PROTECTION_VI` (`0x070010e3`) and `CPS` (`0x070010e4`) cannot feed `SPEAKER_PROTECTION` (`0x070010e2`). |
| **AudioReach `SPv5` calibration & fault events** | `sources/linux/sound/soc/qcom/qdsp6/audioreach.c:836-852,1375-1465,1489-1530` | **[Verified]** `audioreach_set_module_config()` (which sends `SND_SOC_AR_TPLG_MODULE_CFG_TYPE` blobs) is only called for `MODULE_ID_SMECNS_V2`, **never** for `0x070010e2` or `0x070010e3`. Linux sends only bare `PARAM_ID_SP_OP_MODE=0` and `PARAM_ID_SP_VI_OP_MODE_CFG` (with `r0_t0_selection={0,0}`), omitting Surface Pro 11 `REV_0D` excursion/thermal/gain/Re tables, `R0/T0` `180 s` calibration (`0x08001511`), and `EVENT_ID_SPv5_SPEAKER_DIAGNOSTICS` (`0x0800138c`) DC/thermal fault shutdown. |
