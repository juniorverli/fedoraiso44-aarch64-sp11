<!-- Source: Gemini 3.8 Flash via Antigravity (agy) with the REA MCP, 2026-10-31. Orchestrator spot-check: the Bayer mapping (module code 0 -> BGGR, 3 -> RGGB, 4 -> MONOCHROME) was re-derived by the orchestrator from the jump table in the Windows camera DLL and matches. Everything else is UNVERIFIED by a second reader. Windows thermal numbers are Windows POLICY for comparison only: no Linux limit is ever raised (S6). -->
# 2. Priority B: Sensors Subsystem & ADSP Registry

### 2.1 ADSP Sensor Registry Architecture
Under Windows, sensor hardware is driven remotely by the Hexagon ADSP (`qcadsp8380.mbn`, SHA-256 `921870a839ee`). Communication with the host OS occurs via FastRPC (`qcSensors.dll`, UMDF driver bound to `MSHW048A` and `MSHW048B`).
- **Path Mapping:** `qcSensors.dll` provides a FastRPC filesystem bridge. It intercepts ADSP remote file requests directed at Linux/Android sysfs paths and redirects them to the Windows DriverStore package `surfacepro_snscfgcrd8380.inf_arm64_f5d7e051fecc22c3`:
  - `\vendor\etc\sensors\config\*` $\rightarrow$ package JSON configuration files and calibration blobs.
  - `\sys\devices\soc0\*` $\rightarrow$ static platform identification files (`hw_platform="CRD"`, `soc_id="615"`, `platform_version="3.1"`, `platform_subtype="Unknown"`, `platform_subtype_id="65536"`, `revision="0"`).

### 2.2 Format & Structure of Configuration Files
1. **Registry Manifest (`sns_reg_config`):** Plain text key-value configuration directing the ADSP sensor initialization engine:
   - `version=1`
   - `file=input=json.lst`
   - `file=config=/vendor/etc/sensors/config`
   - `file=output=/persist/sensors/registry/registry`
   - Maps platform sysfs files to sensor registry variables.
2. **Master File List (`json.lst`):** Newline-delimited text listing all 65 active JSON configuration files.
3. **QTI Sensors Configuration (QTI SSC JSON Schema):**
   - Top-level object contains:
     - `"config"`: Target hardware filter (`"hw_platform": ["CRD"]`, `"soc_id": ["555", "635", "615", "616"]`).
     - Named sensor device block (e.g., `lsm6dsv_0_platform`, `ak0991x_0_platform`, `tcs3430_0_platform`, `sns_device_orient_platform`).
   - Child sections:
     - `.config`: Bus interface (`bus_type`, `bus_instance`, `slave_config`, `min_bus_speed_khz`, `max_bus_speed_khz`, `dri_irq_num`, `irq_trigger_type`, `num_rail`).
     - `.orient`: Axis orientation mapping (`x`, `y`, `z` direction strings).
     - `.placement`: Spatial translation/rotation matrix (12 integer parameters `0`..`11`).
     - `.fac_cal`: Factory calibration offsets and correction matrices.
   - Property Encoding: Every attribute is typed: `{ "type": "int"|"flt"|"str", "ver": "<version>", "data": "<value_string>" }`.

### 2.3 Required Sensor Configurations by Component
- **Accelerometer & Gyroscope (ST LSM6DSV, SPI/I3C on Bus 2):**
  - Primary display sensor: `8380_crd_lsm6dsv_display.json`, `lsm6dsv_0.json`, `lsm6dsv_0_16g.json`.
  - Secondary keyboard sensor: `8380_crd_lsm6dsv_keyboard.json`, `lsm6dsv_1.json`, `lsm6dsv_1_16g.json`.
  - Calibration: `sns_surface_calibration_accel.json`, `sns_surface_calibration_gyro.json`, `sns_gyro_cal.json`.
- **Magnetometer / Compass (AKM AK0991x, I2C on Bus 2):**
  - Display sensor: `8380_crd_ak991x_display.json`, `ak991x_dri_0.json`.
  - Secondary sensor: `8380_crd_ak991x_keyboard.json`, `ak991x_dri_1.json`.
  - Calibration: `sns_mag_cal.json`.
- **Ambient Light & Color (AMS TCS3430):**
  - Sensor config: `8380_crd_tcs3430_0.json`.
  - Factory & color calibration: `golden_color_calibration.bin`, `sns_surface_color.json`.
- **Device Orientation & Motion:**
  - Sensor orientation: `sns_device_orient.json`.
  - Sensor fusion algorithms: `sns_rotv.json` (rotation vector), `sns_geomag_rv.json` (geomagnetic rotation vector), `sns_fmv.json`, `sns_smd.json`, `sns_amd.json`.
- **Framework & Dynamic Loading:**
  - `sns_reg_config`, `json.lst`, `8380_dynamic_sensors.json`, `default_sensors.json`, and the 6 platform identification files.

### 2.4 Autonomous ADSP Registry Generation
- **Verified Finding:** Decompilation and string analysis of the ADSP firmware binary `qcadsp8380.mbn` (SHA-256 `921870a839ee`) reveals that Qualcomm's embedded sensor registry parser (`sns_registry_parser.c`, `sns_reg_util.c`, `sns_registry_sensor.c`) is compiled **directly into the ADSP image**.
- **Resolution of Reference Uncertainty:** The external `oemconfig.so` library is **not required**. When `/persist/sensors/registry/registry` is empty or missing, the ADSP's internal parser executes upon FastRPC initialization, reads `sns_reg_config` and `json.lst` via FastRPC file I/O, evaluates the platform filter matching `soc_id="615"` and `hw_platform="CRD"`, and automatically populates the binary registry database under `/persist/sensors/registry/registry`.

---

