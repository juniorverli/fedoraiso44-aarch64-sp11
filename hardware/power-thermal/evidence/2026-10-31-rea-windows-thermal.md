<!-- Source: Gemini 3.8 Flash via Antigravity (agy) with the REA MCP, 2026-10-31. Orchestrator spot-check: the Bayer mapping (module code 0 -> BGGR, 3 -> RGGB, 4 -> MONOCHROME) was re-derived by the orchestrator from the jump table in the Windows camera DLL and matches. Everything else is UNVERIFIED by a second reader. Windows thermal numbers are Windows POLICY for comparison only: no Linux limit is ever raised (S6). -->
# 1. Priority A: Thermal Stack Architecture & Policies

### 1.1 Sensor-to-Thermal-Zone Mapping
Under Windows 11 on Snapdragon X Elite/Plus, thermal management is split across three distinct subsystems: Qualcomm on-die TSENS (managed by `qcpep8380.sys`), PMIC/board thermistors (managed by `qcadc8380.sys` and `qcpep8380.sys`), and Microsoft Surface System Management Framework (SMF, managed by `SurfaceThermalPolicy.sys` and `SurfaceSmfClient.sys`).

| ACPI Thermal Zone | ACPI HID / UID | Driver Service | Physical Sensor Input | Live Telemetry (`tz-samples.txt`) | Grade |
|:---|:---|:---|:---|:---|:---|
| `\_SB.TZ0`, `\_SB.TZ1` | `QCOM0C58` (UID 0, 1) | `qcpep` | On-die TSENS CPU cluster core sensors | 3388 dK (65.65 °C) | Verified |
| `\_SB.TZ2`, `\_SB.TZ3` | `QCOM0C59` (UID 0, 1) | `qcpep` | On-die TSENS SoC top/bottom macro sensors | 3400 dK (66.85 °C) | Verified |
| `\_SB.TZ4`, `\_SB.TZ5` | `QCOM0D01` (UID 0, 1) | `qcpep` | On-die TSENS CPUSS cluster hotspot | 3421 dK (68.95 °C) | Verified |
| `\_SB.TZ6` | `QCOM0C91` (UID 0) | `qcpep` | On-die TSENS GPU core macro sensor (`gpuss`) | 3299 dK (56.75 °C) | Verified |
| `\_SB.TZ11` | `QCOM0CBF` (UID 1) | `qcpep` | On-die TSENS Compute Subsystem / Core Switch (`CSW0`) | 3299 dK (56.75 °C) | Verified |
| `\_SB.TZ99` | `QCOM0C5A` (UID 100) | `qcpep` | Aggregate SoC thermal ceiling (max of on-die TSENS) | 3421 dK (68.95 °C) | Verified |
| `\_SB.TZ31` | `QCOM0C5E` (UID 0) | `qcpep` + `qcADC` | Board thermistor `SYS_THERM1` on PMIC J (pm8550ve_9) | Sentinel 2552 dK (-17.95 °C) | Verified |
| `\_SB.TZ32` | `QCOM0C5F` (UID 0) | `qcpep` + `qcADC` | Board thermistor `SYS_THERM2` on PMIC K (smb2360_1) | Sentinel 2552 dK (-17.95 °C) | Verified |
| `\_SB.TZ33` | `QCOM0C60` (UID 0) | `qcpep` + `qcADC` | Board thermistor `SYS_THERM3` on PMIC D (pmc8380_3) | Sentinel 2330 dK (-40.15 °C) | Verified |
| `\_SB.TZ34` | `QCOM0C61` (UID 0) | `qcpep` + `qcADC` | Board thermistor `SYS_THERM4` on PMIC E (pmc8380_4) | Sentinel 2330 dK (-40.15 °C) | Verified |
| `\_SB.TZ35` | `QCOM0C62` (UID 0) | `qcpep` + `qcADC` | Board thermistor `SYS_THERM5` on PMIC F (`MSKN`, `MJCT`, `MBJ0`) | Sentinel 2330 dK (-40.15 °C) | Verified |
| `\_SB.TZ36` | `QCOM0C63` (UID 0) | `qcpep` + `qcADC` | Board thermistor `SYS_THERM6` on PMIC G (`MBS1` skin) | Sentinel 2330 dK (-40.15 °C) | Verified |
| `\_SB.TZ37` | `QCOM0C64` (UID 0) | `qcpep` + `qcADC` | Board thermistor `SYS_THERM7` on PMIC H (`MBS2` skin) | Sentinel 2330 dK (-40.15 °C) | Verified |
| `\_SB.TZ01`..`TZ08` | `MSHW0188` (UID 1..8) | `SurfaceSmfClient` | Surface SAM EC real temperature sensors (`RTS1`..`RTS8`) | RTS2: 54.75 °C, RTS3: 53.85 °C, RTS4: 44.95 °C, RTS5: 40.85 °C | Verified |
| `\_SB.TZ09`..`TZ0C` | `MSHW0188` (UID 9..12) | `SurfaceSmfClient` | Surface SMF virtual temperature models (`VTS1`..`VTS4`) | VTS1: 43.35 °C, VTS2: 40.65 °C, VTS3: 41.05 °C | Verified |
| `\TPOL` | `MSHW0187` (UID 1) | `SurfaceThermalPolicy` | Aggregates `\_SB.TZ2` and `\_SB.TZ6` to drive SMF policy | 0 dK (control device) | Verified |

- **Citations:** 
  - `sources/windows/live-inventory/acpi/dsdt.dsl` (lines 66128-68400)
  - `sources/windows/live-inventory/acpi/ssdt.dsl` (lines 774-1420)
  - `sources/windows/live-inventory/thermal/thermal-query.txt` (sections `qcpep`, `qcADC`, `SurfaceThermalPolicy`, `SurfaceSmfClient`)
  - `sources/windows/DriverStore/qcadc8380.inf_arm64_66c3245fc751d6b1/ADC1.bin` (SHA-256 `85bbc3ff5b73`, AeoB container mapping `SYS_THERM1..7`, `XO_THERM`, `PMIC_THERM` across PMIC SIDs D, E, F, G, H, J, K)

### 1.2 Windows Thermal Trip Points & Hysteresis (Windows Policy)
All thresholds listed below represent active Windows ACPI policy and are documented strictly for Linux safety lower-bound verification (S6).

| Zone | Bound Devices (`_TZD`) | Passive Trip (`_PSV`) | Critical Trip (`_CRT`) | Hysteresis / Algorithm (`_TC1`, `_TC2`) | Sampling Period (`_TSP`) | Grade |
|:---|:---|:---|:---|:---|:---|:---|
| `TZ1`, `TZ3`, `TZ5` | `\_SB.PEP0` | 3780 dK (104.85 °C) | None | `_TC1` = 0, `_TC2` = 1 | 5.0 s (TZ1), 0.1 s (TZ3/5) | Verified |
| `TZ6` | `\_SB.GPU0` | 3680 dK (94.85 °C) | None | `_TC1` = 1, `_TC2` = 2 | Not serialized (on demand) | Verified |
| `TZ11` | `\_SB.CSW0` | 3780 dK (104.85 °C) | None | `_TC1` = 0, `_TC2` = 1 | Dynamic | Verified |
| `TZ99` | 12 CPUs, `PEP0`, `GPU0`, `WLTM`, `PMBM`, `CSW0` | 3780 dK (104.85 °C) | 3880 dK (114.85 °C) | `_TC1` = 4, `_TC2` = 3 | 1.0 s | Verified |
| `TZ31` | `\_SB.PEP0`, `\_SB.GPU0` | 3630 dK (89.85 °C) | 3830 dK (109.85 °C) | `_TC1` = 0, `_TC2` = 20 | 3.0 s | Verified |
| `TZ32` | 12 CPUs | Dynamic via PEP | 3880 dK (114.85 °C) | `_TC1` = 0, `_TC2` = 1 | Dynamic via PEP | Verified |
| `TZ33` | `\_SB.GPU0` | Dynamic via PEP | 3830 dK (109.85 °C) | `_TC1` = 3, `_TC2` = 2 | Dynamic via PEP | Verified |
| `TZ35` | `MSKN`, `MJCT`, `MBJ0` (Skin) | 3680 dK (94.85 °C) | 3880 dK (114.85 °C) | `_TC1` = 0, `_TC2` = 20 | Dynamic via PEP | Verified |
| `TZ36` | `MBS1` (Skin secondary 1) | 3680 dK (94.85 °C) | 3880 dK (114.85 °C) | `_TC1` = 0, `_TC2` = 20 | Dynamic via PEP | Verified |
| `TZ37` | `MBS2` (Skin secondary 2) | 3680 dK (94.85 °C) | 3880 dK (114.85 °C) | `_TC1` = 0, `_TC2` = 20 | Dynamic via PEP | Verified |
| `FAN0` | `_DEP \_SB.SSH` | No ACPI trips | No ACPI trips | No ACPI control (`_STA` only) | Autonomous in SAM EC | Verified |

- **Hysteresis Analysis:** In standard ACPI step-wise thermal formula: $\Delta P = \_TC1 \times (T - T_{\text{target}}) + \_TC2 \times (T - T_{\text{prev}})$. The coefficients `_TC1 = 0`, `_TC2 = 1` or `_TC2 = 20` on skin sensors indicate that throttling reaction is heavily damped by rate-of-change ($\Delta T$), preventing rapid hunting and oscillation.

### 1.3 Throttling Policies: CPU Core Parking, DCVS, and GPU/NPU
Throttling under Windows is governed by Qualcomm PEP (`qcpep8380.sys`, SHA-256 `e5bdeb8c0fb8`) via ACPI devices `QCOM0CF2` through `QCOM0CFC`. PEP configures structured limits in `LimitsConfig` (`AeoB` containers):

1. **CPU Core Parking (`QCOM0CF2`, `CCPC`):**
   - **Trigger:** Engaged as the SoC temperature approaches the passive trip (104.85 °C).
   - **Throttling Steps:** First threshold at 80% (0x50) system performance rating. Under progressive thermal stress, limits step down to 50% (0x32) and 25% (0x19), parking up to 8 of the 12 CPU cores (leaving 4 active cores on Cluster 0).
2. **CPU Dynamic Clock and Voltage Scaling (`QCOM0CF3` `CCDC`, `QCOM0CF4..6` `CDC0..2`):**
   - **Cluster Frequency Limits:** Discrete per-cluster ceiling limits for Cluster 0, Cluster 1, and Cluster 2.
   - **Thresholds:** Frequency cap begins at 80% ceiling limit when TSENS reaches 104.85 °C, with step reductions down to OPP step 6, step 5, and step 3 (minimum safe frequency floor).
3. **GPU Throttling Policy (`QCOM0CF7`, `CGLC`):**
   - **Trigger:** Initiates when `TZ6` reaches 94.85 °C (3680 dK) or `TZ33` approaches critical.
   - **Two-Tier Mitigation:**
     - Level 1: Immediate cap to 80% maximum clock.
     - Level 2: Secondary clamp to 50% maximum clock with 1000 ms filtering window.
4. **NPU / NSP Throttling Policy (`QCOM0CF8`, `CNLC`):**
   - **Two-Tier Mitigation:** Symmetrical to GPU throttling (Level 1 cap at 80%, Level 2 clamp at 50% with 1000 ms evaluation window).

### 1.4 Battery Current Limits & Battery-Health Options
Hardware fuel-gauge battery current limiting is implemented by Qualcomm FGBCL (`qcfgbcl8380.sys`, SHA-256 `0145fdaa91fb` and `qcfgbclext8380.inf`):
- **BCL Capabilities:** Capability flag `7` (monitoring active on `vph_pwr`, fuel-gauge voltage `VBATT`, and fuel-gauge current `IBATT`).
- **Peak Current Protection (OCP):** `OCPCurrent` = 17,000 mA (17.0 A peak).
- **Throttling Triggers:**
  - `IBATTHi` = 85% of OCPCurrent (14.45 A): triggers Level 1 system power throttling notification.
  - `IBATTTooHi` = 88% of OCPCurrent (14.96 A): triggers Level 2 emergency throttling notification.
- **Polling Intervals:** Standard timer 600 s; shifts to high-frequency polling (60 s) when battery state-of-charge drops below `FasterTimerPercent` = 20%.
- **Battery Health & Charge Capping:**
  - In Windows user-space, `SurfaceMLService.exe` monitors battery telemetry and triggers `StateBatteryChargeLimitEnabled`.
  - The actual charging termination ceiling (e.g., 80% Smart Charging or 50% Kiosk Battery Limit) is executed inside Surface UEFI and the SAM EC firmware.
  - No writable ACPI control method or driver register is exposed to the host OS to set arbitrary charge limits; the OS only communicates operational states to the EC.

---

