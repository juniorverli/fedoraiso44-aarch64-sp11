# Cameras: Qualcomm CamX userspace for hamoa, and how the Surface sensors plug in

Date: 2026-10-31. Goal: the original Windows image quality through the Spectra hardware ISP with Qualcomm's CamX userspace on
Linux. Scope: find the real packages, inventory them, compare their data format with the Windows Surface files, design the
pipeline. No execution of any Qualcomm binary, no disassembly (see section 1.3), no REA, no device access.
Structure only: no register, tuning value or I2C address is quoted (S5). Nothing from the Qualcomm package or from Windows is in
git; the packages are under `out/ref/camx-hamoa/` (ignored), the converter output goes to `out/firmware-private/cameras/camx/`.

Grades: **Verified** (read from data, a listing or a script), **Inference** (reasoning given), **Unknown**.

## 1. The packages

### 1.1 Location and checksums (Verified)

Host: `https://qartifactory-edge.qualcomm.com/artifactory/qsc_releases/software/chip/component/camx.qclinux.0.0/<release>/<flavour>/`.
Anonymous download, no login. The URL pattern comes from `debian/watch` of `qualcomm-linux/pkg-camx-hamoa` (branch
`qcom/ubuntu/resolute`, `cfc5f58`), whose README names the folder; the release listing is read with the Artifactory storage API
(`.../artifactory/api/storage/qsc_releases/...`): 100 release folders, newest `261029` (only `prebuilt_trixie`), newest complete
`261026` with `prebuilt_resolute`, `prebuilt_trixie`, `prebuilt_rpm`, `prebuilt_yocto_master`, `prebuilt_yocto_wrynose` and a
`notes.json`. The server's `X-Checksum-Sha256` header equals the local `sha256sum` for every file below.

| Flavour (release `261026`) | File | Size | sha256 |
|:--|:--|:--|:--|
| `prebuilt_resolute` (Ubuntu 26.04, glibc 2.43) | `camx-hamoa_1.0.56_arm64.tar.gz` | 241958792 | `b6627f33abc9ba72e51208c04c1b75c193b1f3d2020a4333a474218f9147a16e` |
| `prebuilt_trixie` (Debian 13, glibc 2.38) | `camx-hamoa_1.0.56_arm64.tar.gz` | 337162431 | `0534d91be1582e815e10104fce19408d69064b4a383321d6ba9c6d00f2588fc4` |
| `prebuilt_yocto_master` | `camx-hamoa_1.0.56_armv8-2a.tar.gz` (libs, no sensor data) | 58306810 | `3d52d35a389c3bde2b5303da646e0df9af9dab8252ad40bf46bababa814e43dd` |
| `prebuilt_yocto_master` | `camxcommon-hamoa_1.0.56_armv8-2a.tar.gz` | 553749 | `689f8103629afc8b16259216d5d069e21d5b4f995fa1773e3a316484cbd39323` |
| `prebuilt_resolute`, `prebuilt_trixie`, `prebuilt_rpm` | `camx-headers_1.1.1_arm64.tar.gz` | 222711 | `30cb702b1b37651d3492dc38e4a8c306de7e25ea0f017de11915ef17411122fd` |
| `prebuilt_resolute`, `prebuilt_trixie` | `camxfirmware_1.0.27_arm64.tar.gz` (hamoa, purwa, others) | 928439 | `1f054c4700a3d936924f94a1fa3bbd7a51e15df8d86de9ea332c5d2533d04437` |

Copies: `out/ref/camx-hamoa/dl/` plus `SHA256SUMS.txt`; extracted to `pkg/` (resolute), `trixie/`, `yocto/`, `hdr/`, `fw/`.
Version `1.0.56` is the Debian changelog of the `camx` source (26 Oct 2026; "Add Nord platform support ... sensor driver updates and
URM support"). The Debian packages inside are `camx-hamoa`, `libcamx-hamoa1`, `libcamx-hamoa-dev`, `camx-hamoa-dev`,
`camx-entitled-headers-dev`, `libcamx-dev`. The RPM flavour exists only for Kodiak (`camx-kodiak-1.0.51_1.el10.aarch64.tar.gz`):
`qualcomm-linux/pkg-rpm-camx-kodiak` (branch `c10s`, spec `camx-kodiak.spec`) is the template for a hamoa RPM. No hamoa RPM exists.

Related repositories (Verified, cloned shallow, read): `qualcomm-linux/pkg-camx-hamoa`, `pkg-camx-dev`, `pkg-camx-firmware-hamoa`,
`pkg-qti-camera-service` (source of `qualcomm/camera-service`, `b3d1bfc`), `pkg-urm` (source `qualcomm/userspace-resource-manager`),
`pkg-gst-plugins-imsdk` (source `qualcomm/gst-plugins-imsdk`, `67189ab`), `camx-metadata`, `pkg-rpm-camx-kodiak`,
`pkg-rpm-camx-dev`, `pkg-rpm-camera-service` (`qcom-camera-server.spec`), `pkg-rpm-qcom-fastcv-binaries`. The CamX source itself is not published.

### 1.2 Licence (Verified: `usr/share/doc/camx-hamoa/copyright`, text of "Qualcomm-Nologin-Binaries")

- Grants a nonexclusive, limited licence to install and use the Materials and to reproduce and redistribute the "Redistributable
  Binary Code" (1.1).
- Redistribution (1.2): binary format only; may operate only with platforms that incorporate Qualcomm chipsets; the licence `.txt`
  must travel with it; no use of Qualcomm names, logos or trademarks; notices stay.
- 1.3: no sublicensing, transfer or disclosure to third parties "except as expressly permitted"; **no reverse engineering,
  reverse assembly, decompilation of any portion in object or executable form**; no placing the Materials under third-party (open
  source) licence terms; modifications and derivative works belong to Qualcomm.
- Warranty disclaimed; liability capped at US$50; Qualcomm may terminate at any time; California law.
- Other packages: `camx-headers`, `camx-metadata`, `camera-service`, `gst-plugins-imsdk` are BSD-3-Clause-Clear; `userspace-resource-manager`
  BSD-3-Clause; `qcom-fastcv-binaries` is Qualcomm-Nologin-Binaries; the downstream kernel driver is GPL-2.0-only.

Answer for "private image only, never public, never git": **allowed.** Installing and using the binaries on the operator's own
Snapdragon X Plus device is covered by 1.1(i), and the Surface Pro 11 has a Qualcomm chipset. They stay out of git, out of the
kernel fork and out of every public place (S5). A public image would be allowed in binary form only with the licence text and on
Qualcomm platforms, but that needs a separate decision and is out of scope.

### 1.3 Method limit (Inference, to stay inside 1.3)

Analysis here used only: package listings, ELF dynamic section and version needs (`readelf`), exported dynamic symbols of the tiny
sensor libraries (`nm -D`), printable strings (`strings`) and the data files. No disassembly or decompilation of any Qualcomm
library. Consequence: items that only code could answer (hash function, trailer checksum, library search directory) stay Unknown.
Reverse-engineering the `.bin` container from its sample files is a legal grey zone under 1.3; the operator decides before that is attempted.

## 2. Inventory of `camx-hamoa` 1.0.56 (resolute; trixie has the same data files, identical sha256 for all 13 `.bin`)

| Part | Content (Verified) |
|:--|:--|
| HAL | `hw/camera.qcom.hamoa.so` (60.6 MB), `hw/camera.qcom.so` (46.7 MB), `hw/com.qti.chi.override.so`, `hw/com.qti.chi.offline.so`. `camera.qcom.hamoa.so` is the platform part (IFE/BPS/IPE nodes, CSL), `camera.qcom.so` the platform-independent HAL3 core (sensor modules, slots, parsers). Loaded as an Android camera HAL module (`camera3.h`, `camera_common.h` in `libcamx-dev`). |
| CHI | `com.qti.chiusecaseselector.so` (use cases are code, no XML or BIN file), `chicustomization.so`, `com.qti.feature2.*.so` (28), `com.qti.settings.hamoa.so` (settings tables, FD configs), `com.qti.stats.common.so`, 22 nodes and stats in `camera/components/` (`com.qti.stats.aec/awb/af/afd/asd/haf/pdlib`, `node.swregistration/stich/remosaic/imgproc/...`, `eisv3`) |
| ISP hardware programming | Code, not data: `libisphwsetting.so`, `libcamxifestriping.so`, `libipebpsstriping{,170,480}.so`, `libcamxsensorconfig`, IQ module libs. There are **no IFE/IPE/BPS hardware-configuration `.bin` files and no usecase XML/BIN** in the package; the settings schema is `camx-hamoa-dev/.../g_camxsettings.xml` (10318 lines). |
| Sensor drivers (libraries) | `camera/com.qti.sensor.*.so`: `ov13858`, `ov13858_rhodes`, `ov13b10`, `ov08x`, `ov9282`, `og0va1b`, `imx577`, `cmk_imx577`, `imx688`, `imx858`, `rpi_imx219`, `leopard_ox08d10`, `max9296a_ar0231`, `max9296a_ox03f10`, `max96724_ox03f10`, `max96724_ox08d10`. Each is 67792 bytes. **No `imx681`, no `vd55g0`.** |
| Sensor modules (data) | `com.qti.sensormodule.{hamoa_cmk_imx577_csi1, og0va1b, ov08x, shinetech_imx688, qti_tpg0_iqx, qti_tpg1_iqx, qti_tpg2_iqx}.bin`; none for OV13858, IMX681, VD55G0 |
| Tuned data | `com.qti.tuned.{default, hamoa_imx577, hamoa_shinetech_imx688, shinetech_og0va1b, shinetech_ov08x}.bin` |
| SoC map | `com.qti.sensorsocmap.socid_map.bin` (schema `camxsocidbinmap.xsd`): maps an SoC id to a list of bin names; the entries are QCS9100, QCS8300, QCS9075, QCS8275, QCS615 only (all IoT/automotive). No hamoa entry. |
| Test app | `libexec/camx-hamoa/nativehaltest` (1.65 MB): drives the HAL3 module; strings show RAW10 and RAW12 streams, `.raw` and `.yuv` dumps, preview and snapshot templates, EIS and HDR vendor tags. Needs `libcamera_hardware`, `libcamera_metadata`, `libcamxexternalformatutils`. |
| DSP | `share/hexagon-dsp/x1e80100/Qualcomm/Hamoa-IoT-EVK/dsp/cdsp/*.so` (`libhme_dsp_skel`), reached through `libcdsprpc` (fastrpc). |
| Dev | static archives (`libcamxcore.a`, `libcamxsensorconfig.a`, `libcamxcsl.a`, ...), 173 entitled headers under `include/camx/lemans/` (note the directory name: the headers are the lemans build; `camxcsl*defs.h`, `camxsensorproperty.h`, `camxcslsensordefs.h`, `camxpacketbuilder.h`) and `camx-v2` camera HAL headers. **`camxsensordriver.h` (the sensor driver data and library API structs) is not shipped.** |
| Firmware | `camxfirmware_1.0.27`: `usr/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn` (hamoa; purwa is a link to it), also glymur and sa8775p. Same hash as in `2026-10-31-spectra-port.md` section 6. |

### 2.1 Kernel interface it uses (Verified: strings, headers, `2026-10-31-spectra-port.md` section 2.3)

The HAL talks to the Spectra downstream UAPI: `/dev/media%d` and `/dev/%s` nodes opened by name, `CAM_QUERY_CAP`, the
`VIDIOC_CAM_CONTROL` op codes, V4L2 event subscription (`VIDIOC_SUBSCRIBE_EVENT`, `VIDIOC_DQEVENT`) for CRM events, KMD packet building
(`camxpacketbuilder.h`, `camxcsl*defs.h`). The sensor is probed through the kernel sensor node (`CSLImageSensorProbe`,
`CSLHwInternalProbeSensorHW`): the HAL sends the module's slave info and power sequences to the kernel. The out-of-tree module built in
`2026-10-31-spectra-port.md` (`camera_x1e80100.ko`) is the intended kernel half; its sysfs module path contains "camera", which is what
`check-camx-overlay.sh` of the camera service tests. It also reads `/sys/devices/soc0/soc_id` (SoC id; the value on the X1P64100 and what
CamX does with an id it does not know is Unknown).

### 2.2 Dependencies and Fedora 44 aarch64 (Verified: `readelf -d/-V` over every ELF, Fedora 44 container `dnf repoquery`)

| Need | resolute build | trixie build | Fedora 44 aarch64 |
|:--|:--|:--|:--|
| glibc | up to GLIBC_2.43 | up to GLIBC_2.38 | 2.43 (`glibc-2.43-9.fc44`): both fine |
| libstdc++ | GLIBCXX_3.4.32, CXXABI_1.3.15 | same | 16.2.1: fine |
| libcdsprpc.so.1 | yes | yes | `fastrpc` 1.0.8: provided |
| libglib-2.0.so.0, libz.so.1 | yes | yes | provided |
| libxml2 | `libxml2.so.16` | `libxml2.so.2` | repository has 2.12.10 (`.so.2`): trixie build only |
| libprotobuf | `libprotobuf.so.32` | `libprotobuf.so.32` | repository has 3.19.6 (`.so.30`): **missing**, needs a compat build of protobuf 3.21 (soname 32). Only `camera.qcom.so` needs it. |
| opencv | `libopencv_core.so.410`, `libopencv_imgproc.so.410` (stats AEC core, AWB, HAF) | same | repository has 4.13.0: **missing**, needs a compat build of OpenCV 4.10 |
| `libUrmClient.so.1` | yes (`camera.qcom.so`) | yes | **missing**: build `qualcomm/userspace-resource-manager` (BSD-3-Clause, cmake, libyaml, libsystemd; `liburm1` SONAME) |
| `libfastcvopt1` | `Depends` of the Debian package | same | Qualcomm binary `qcom-fastcv-binaries` (rpm spec exists, Nologin licence); needed at install by the Debian metadata, runtime need Unknown |
| RUNPATH | `/usr/lib/aarch64-linux-gnu/camx/hamoa` and `/hw` (absolute, Debian multiarch) | same | works if the files are installed under that exact path, or patched |

Inference: the **trixie flavour is the one to use on Fedora 44** (glibc and libxml2 match). Three private compat libraries are
the remaining runtime gap: protobuf 3.21 (`.so.32`), OpenCV 4.10 (`.so.410`) and URM. All three are open source and
build from source. The Qualcomm RPM layout (`pkg-rpm-camx-kodiak.spec`, Fedora-native) installs the payload in `%{_libdir}/camx/<platform>`,
leaves `/usr/lib/camx` as a symlink, and puts tuning data in `%{_datadir}/camx`.

## 3. File naming and the sensor "slot" data

### 3.1 Naming is data driven, not hard-coded (Verified: embedded protobuf descriptor in `camera.qcom.so`, XSD in the bins)

The task brief assumed `com.qti.sensormodule.<name>.bin` and `com.qti.tuned.<name>.bin` are looked up by a fixed convention. The HAL
has three mechanisms:

1. **Slot configuration** `slots.proto` (descriptor embedded in the HAL):

   ```
   message SensorConfig { string version = 1; repeated SensorSlot slots = 2; }
   message SensorSlot   { int32 index = 1; string name = 2; string sensorbin = 3; string sensordtoverlay = 4;
                          string tuningbinary = 5; int32 position = 6; int32 mountAngle = 7; }
   ```

   The HAL converts an XML description of the slots to `/var/cache/camera/camera_config.pb` (`GenerateProtoBufFile`, "xml file not
   modified hence no need to regen pb file", `Xml File : %s not found!`) and loads the `.pb` (`InitializeUsingProtoBuf`, log line "Index:
   Name: Sensor Bin: Tuning Bin: position: Mount Angle:"). So a slot names its sensor module file (`sensorbin`), its tuning file
   (`tuningbinary`), the DT overlay (`sensordtoverlay`), the physical position and the mount angle. The XML element names and its
   directory are Unknown (they are code); the `.pb` can be written directly because the descriptor is known. This is the "sensor slot"
   data of the brief: there is no separate usecase or slot XML in the package.
2. **SoC map** (`com.qti.sensorsocmap.socid_map.bin`, "Initialize Using SensorBinSocIdMap"): SoC id to a list of bin names.
   Not populated for hamoa. Duplicate tags are logged ("Duplicate entry found in the socid map xml with tag").
3. **Tag match**: the log says "No Bin File found with this tag: [%s]" and "Duplicate bin file found with this tag"; the header of a
   V7 bin carries a tag and a creator ("BinaryTag: %s, Created By: %s"). The module's `sensorName` must match the probed sensor
   ("Cannot match sensor: %s and module.").

Where the HAL looks for the bins is Unknown (strings show `/usr/lib/camera`, `/usr/lib/camera/components` and
`/var/cache/camera`; the package installs under `/usr/lib/aarch64-linux-gnu/camx/hamoa/camera/`; Qualcomm's service units set
`LD_LIBRARY_PATH=/usr/lib/camera/components/:/usr/lib/camera/`). Hypothesis: an installed symlink `/usr/lib/camera` to the `camera`
directory of the package, as the RPM spec does with `/usr/lib/camx`. A first run with `nativehaltest` and `strace -e openat` answers it.
Override settings file: name `camxoverridesettings.txt`, directory Unknown (probably `/var/cache/camera/` or `/etc/camera/`; the
HAL mentions `/etc/camera/ChromatixBinaryParameterSet*.bin` as a debug input).

Windows analogue (Verified: `qccamplatform8380` and the extension packages): the per-device data on Windows are the `AeoB` blobs
`SCFG_*`, `CAMF/CAMS/CAMI_RES_*` (sensor slave and resource data) next to the module and tuned files. Their job is split on Linux
between the DT (resources, `qcom,cam-sensor`), the module bin (slave info, power, init, modes) and the slot file.

## 4. Windows files against the Linux package files (Verified by the converter report and throwaway scripts on all files)

| | Windows (`com.surface.*`, and Windows `com.qti.tuned.default`) | Linux package (`com.qti.*`) |
|:--|:--|:--|
| Magic | `QTI Chromatix Header` | same |
| Parser banner | `Parameter Parser V3.4.0 (2106301010)` | `Parameter Parser V7.4.1 (8cca6579...)` (this string is also inside the HAL) |
| Container version words | 3, 1 | 7, 0 |
| `u32` at 0x1C | file size minus 4 | offset of the last section |
| Section table | 3 entries: 0 symbol table (0x38-byte records, name keyed), 1 data heap, 2 trailer (20 bytes; 9860 and 18700 bytes in the tuned files) | 5 entries in the order 0, 3, 2, 1, 4: 0 identity (96 or 128 bytes of hashes), 3 index table of `(offset, size, index)` triples, 2 module name (152 bytes) or a table (56 KB in tuned files), 1 data heap, 4 **definitions with the XSD embedded** (24039 bytes in the simple modules, 36633 in `imx688`, 640 KB in tuned files) |
| Names | ASCII, 32 bytes per symbol | 64-bit hashes of type and field names; the XSD text names (`camxsensordriver.xsd`) sit in section 4 |
| Checksum | zlib CRC-32 of all bytes before the last four; matches | an 8-byte trailer. It is **not** zlib CRC-32 and not CRC-64 (ECMA, ISO, Jones) or CRC-32C over any combination of the header and section boundaries (all standard init and xor variants tried on `qti_tpg0_iqx`). The HAL has both a 32-bit and a 64-bit "Binary file CRC validation failed" message. Unknown. |
| Validation by the reader | symbol offsets inside the heap | per-type name hash and per-type version against the HAL's compiled-in XSD ("binary name hash ... does not match source name hash", "binary version ... does not match source version"), structure byte counts and positions ("XSD structure modified"), CRC |
| Compression | none | refused (support ended with V5.1.0) |

Same data model, different byte format (Verified by names):

- Sensor module: 133 of the 143 Windows OV13858 symbol names (133/135 IMX681, 104/106 VD55G0) are field or type names in the Linux
  `imx688` module's XSD (943 tokens); the Linux simple modules have an older, smaller XSD (650 tokens: 104/143 covered). Windows-only
  names (actuator park and standby/uninit settings, DCC and PDAF map names, `AFSyncInfo` ...) are optional parts that a sensor can leave
  empty. The register-operation enumeration is identical (WRITE=0, WRITE_BURST, WRITE_SEQUENTIAL, READ=3, POLL=4), which confirms the Windows op codes
  of `2026-10-30-module-data-format.md` (op 4 is POLL). The power enumerators map one to one (MCLK, VANA, VDIG, VIO, VAF, VAF_PWDN,
  CUSTOM_REG1/2, RESET, STANDBY ...).
- Windows pixel format code 0, 3, 4 matches CamX `PixelFormat` (`camxsensorproperty.h`: BayerBGGR=0, GBRG, GRBG, RGGB=3, YUVFormatY=4), which supports the corrected Bayer orders (rear BGGR, front RGGB, IR mono).
- Tuned files: all 64 Windows `mod_*_trigger_data` IQ module families (`lsc41`, `cc13`, `wb20`, `anr10`, `tf21`, `asf34`, `ltm16`, `demosaic36`, `cac23`,
  `ldc11`, ...) exist in the Linux definitions, which have 66 to 69 (extras: `hme10`, `nrm10`, `lscgolden35`, `preference10`, `reserve*`). Windows 493
  distinct type names, 464 of them appear in the Linux definitions. The Windows Qualcomm baseline `com.qti.tuned.default.bin` is also V3.4.0, so
  the container version difference is a **Windows CamX build against Linux CamX build** difference, not a Surface specialty.
  Per-module field layouts are not compared (the V3 files carry no layout; the V7 definitions are hashed): Unknown whether every module
  version struct is byte compatible.

### 4.1 Fields a Linux module needs that the Windows module does not carry (Verified by symbol names)

Linux `slaveInfo`: `sensorLibName`, `slaveAddress`, `regAddrType`, `regDataType`, `sensorIdRegAddr`, `sensorId`, `sensorIdMask`, `moduleType`, GMSL
probe and register-bank lock blocks. The Windows module has `sensorName` and an **empty** `sensorSlaveAddress` and no ID registers. Sources for the
missing values: the I2C address from ACPI/`SCFG_*` (already known by the sensors worker), the chip id registers from the Linux drivers `ov13858.c`
and `vd55g1.c` (public), IMX681 unknown (no Linux driver, no Windows field). Present in both: `powerUpSequence` and `powerDownSequence` (Windows:
rear 6+6 steps, front 7+6, IR 8+6), `initSettings`, stream on/off, group hold, `resolutionInfo` with modes, exposure register addresses.
So the Windows module can fill the register sequences, modes, power order and exposure register map; it cannot fill the probe block alone.

## 5. What a sensor driver library is, and whether the HAL needs one per sensor

Verified: `com.qti.sensor.ov13858.so` exports exactly `GetSensorLibraryAPIs`, `CalculateExposure`, `FillExposureSettings` (`imx577` adds
`CalculateDigitalGain`); 67 KB each. The HAL loads it by the module's `sensorLibName` (`LoadSensorLibrary`, `GetSensorLibraryAPIs`). So the
library is **not** a register table: the slave info, init and mode sequences, power sequences and modes live in the module bin. The library
does the exposure maths (gain and line count to register values, digital gain split). The Windows modules store `realToRegGain` and
`regToRealGain` as 1-byte stubs, i.e. the same split: the maths is code, in the Windows case inside `QcDeviceMFT8380.dll` (CamX
`camximagesensormoduledata.cpp` path inside it).

- OV13858 (rear): Qualcomm ships `com.qti.sensor.ov13858.so` and `ov13858_rhodes.so`. Inference: reusable for the Surface module if
  its gain law matches (the Windows OV13858 gain is code = gain x 128, `2026-10-31-bayer-units-gain-crosscheck.md`; the Qualcomm library's law is Unknown without running it).
- IMX681 (front) and VD55G0 (IR): no library in the package. The function signatures and the exposure-info struct live in `camxsensordriver.h`,
  which is not published. VD55G0 uses a reciprocal gain law (`2026-10-31-rea-bayer-poll-units.md`). Own libraries are possible in principle (3 exported
  functions) but blocked on the struct layouts: Qualcomm's headers do not have them, and reading them from the closed library is excluded by 1.3.
  Unblock: ask Qualcomm for `camxsensordriver.h` (the `qualcomm-linux` issue trackers), or learn the layout from the Windows driver data
  (`exposureInfo` register addresses are in the module) plus a runtime trace of the OV13858 library called by `nativehaltest`.

## 6. Converter (`hardware/cameras/spectra/camx/convert-surface-module.py`)

Written and tested, **partial**. The layouts are compatible at the data-model level, not at the byte level, so a loadable Linux file cannot be produced yet.

- `--report` (default): structure-only comparison per sensor (section 4 numbers, field coverage, missing slave fields, power sequence types).
  Run: all three Windows modules parse, CRC-32 ok.
- `--emit DIR`: writes a neutral model (`<linux name>.camxmodel.json`: init, stream on/off, hold sequences, modes, power sequences, sensor name) to
  `out/firmware-private/cameras/camx/` (refuses a directory inside git unless ignored) and re-reads it as a round-trip check: digest of all
  sequences, mode records and power steps identical for `ov13858` (64158 bytes), `imx681` (92566), `vd55g0` (61516).
- `--emit-v7`: refused with the reasons below.

A real converter must (a) read the model, (b) fill the Linux fields of section 4.1, (c) serialise `SensorDriverData` against the V7 XSD in the
module's section 4 (taking the XSD and hashes of an existing Qualcomm bin as template: the output then contains Qualcomm Materials, private only),
(d) write the hashed identity section, the index triples and the heap, (e) compute the unknown trailer checksum, (f) name it as the slot file says, e.g.
`com.surface.sensormodule.ov13858.bin`, and list it in `camera_config.pb`. Blocked by: the name-hash function (not FNV-1/1a, MD5/SHA prefixes, djb2,
sdbm or MurmurHash64A of the plain type name, tried on `sensorDriverData`), the trailer checksum, the heap/triple encoding (only partly read), and the
HAL's own XSD version (each Linux module carries an XSD of a different age: 650 or 943 tokens; which one the HAL 1.0.56 accepts is Unknown).
The tuned files (`com.surface.tuned.*`, 2.6 to 6.5 MB) need the same re-serialisation for 493 type names, with per-module struct checks. The honest estimate is
a project of its own, and only a runtime test on the device can say whether a file is accepted.

## 7. Pipeline design

| Stage | Path | Needs | Open or blocked |
|:--|:--|:--|:--|
| A raw capture | Spectra kernel module, sensor nodes, own small UAPI tool (RDI path, no ISP) **or** `nativehaltest` with a RAW10 stream | kernel module (open), OV13858 module and library for nativehaltest; the own tool needs only the SRB blobs the sensors worker already builds | open for OV13858 via own tool; nativehaltest needs the V7 module (blocked) |
| B full ISP, Windows tuning | CamX HAL: IFE, BPS, IPE, 3A, with `com.surface.tuned.*` converted | V7 module and tuned writers (section 6), sensor libraries for IMX681 and VD55G0, ICP firmware (Qualcomm `CAMERA_ICP.mbn`), protobuf 3.21, OpenCV 4.10 and URM compat builds, the slot file, `camx-hamoa` private image install | everything on the Qualcomm side is binary and private; the writers and two sensor libraries are blocked as above |
| B' fallback | libcamera SoftISP with the Windows-derived tuning of the quality worker (already built) | nothing new | open |

Inference: stage A for OV13858 can be done without any Qualcomm userspace. Stage B for the **rear** camera is the shortest CamX path (library exists,
module and tuned writers needed, 2 of 4 blockers). Front and IR add the missing libraries. The expected quality gain of B over B' is the hardware
ISP tuning (BPS and IPE blocks, tintless, LTM, 3A); it cannot be measured before a frame comes out.

## 8. Image plan (private image only)

- Payload (Qualcomm layout adapted to Fedora, from `pkg-rpm-camx-kodiak`): `/usr/lib64/camx/hamoa/` for the libraries and `hw`, with a symlink
  `/usr/lib/camx` and, because the RUNPATH is absolute, either a symlink `/usr/lib/aarch64-linux-gnu/camx` to it or `patchelf` on the 4 binaries
  with a RUNPATH. Candidate `/usr/lib/camera` symlink to `camera` (Hypothesis, section 3).
- Data: Surface module and tuned bins and the slot XML in `/usr/share/camx/` (RPM convention) with the slot file written to `/var/cache/camera/`
  by the HAL; Qualcomm bins and Surface bins never in the repository. Firmware `qcom/x1e80100/CAMERA_ICP.mbn` through the firmware worker's manifest.
- Compat packages to build from source in `rpms-local`: protobuf 3.21 (soname 32, installed under a private directory to avoid replacing system protobuf),
  OpenCV 4.10 (private), `liburm` + `userspace-resource-manager`, plus the camera service below.
- systemd: the service unit exists in the source (`qmmf-server-cam-arch-v2.service`: `Restart=always`, `ExecStart=/usr/bin/qti-cam-server`,
  `Environment=LD_LIBRARY_PATH=/usr/lib/camera/components/:/usr/lib/camera/`), a `99-camera.rules` udev rule, `check-camx-overlay.sh` and `qti-cam-server.ini`
  (GKeyFile). Qualcomm's `qcom-camera-server.spec` (BSD-3-Clause-Clear, source tag 1.0.5) is the Fedora-native template: BuildRequires `protobuf-devel`,
  `abseil-cpp-devel`, `libcamx-devel`, glib2. The service has no hamoa config directory (`config/` has kalama, pineapple, qcs*, qrb*): a `config/hamoa`
  CMake file is needed, modelled on `qcs-common`. Do not enable the unit by default until the bridge works.
- Test order: kernel module loads, `nativehaltest` lists cameras, then a RAW dump.

## 9. How Linux applications would consume it

| Route | Status |
|:--|:--|
| `nativehaltest` | Qualcomm's bring-up tool; dumps `.raw`/`.yuv`; for validation only |
| `qti-cam-server` (QMMF) + client library `libqmmf_recorder_client` | Qualcomm's userspace API (not Android camera2), open source, builds with cmake, protobuf, glib; needs `libcamx-devel` headers |
| GStreamer `qtiqmmfsrc` (and `qticamsrc`) from `qualcomm/gst-plugins-imsdk` (`gst-plugin-qmmfsrc`) | BSD-3-Clause-Clear, GStreamer >= 1.16, needs the in-tree `gstreamer-qcom-oss-utils` and `-video` libs, `qmmf_camera_metadata`, `qmmf_recorder_client`, gbm. Builds on Fedora in principle (all open); the other plugins of the repo (QNN, SNPE, TFLite, Redis...) are skipped. Debian packaging splits it as `gstreamer1.0-plugins-imsdk-camsrc`. |
| PipeWire (`pipewire-v4l2`, libcamera SPA) | no bridge exists. A PipeWire video node would be a GStreamer `pipewiresink` pipeline fed by `qtiqmmfsrc`. Browsers and portals need a PipeWire camera node. |
| libcamera | no pipeline handler for the CamX ABI exists in the Qualcomm orgs; libcamera stays the open fallback (B'). |

## 10. Blockers, in order

1. Byte format V7.4.1: name-hash function, trailer checksum, heap and index encoding, and which XSD version the HAL accepts. Needs either the operator's decision on
   reverse engineering the data format or Qualcomm documentation.
2. Sensor libraries for IMX681 and VD55G0 (and confirmation that the OV13858 one fits): needs `camxsensordriver.h`.
3. Missing slave and probe fields for the three sensors (IMX681 chip id unknown).
4. Runtime compat libraries (protobuf 3.21, OpenCV 4.10, URM) and the `libfastcvopt1` question.
5. Kernel half: the module must probe, load the ICP firmware and satisfy CRM, which are the open items of `2026-10-31-spectra-port.md` section 3.3.
6. Unknown hamoa SoC id handling for X1P64100 and the module and override directories (answered by one device run).
7. S2: the IR illuminator and flash stay disabled; no CamX flash or IR path is enabled in any slot.

## Verified / Inference / Unknown

- Verified: package URLs, sizes, sha256 (also against the server headers), licence text and its terms, inventory of three flavours, SONAME and glibc needs, Fedora 44
  library availability, the slot protobuf schema, the V7 and V3 container layouts and the section/enum comparisons, the sensor library export names, the converter report and round trip.
- Inference: trixie build for Fedora; OV13858 library reuse; stage A without Qualcomm userspace; the `/usr/lib/camera` link.
- Unknown: name hash, trailer checksum, bin and override directories, slot XML schema, HAL behaviour for an unknown SoC id, IMX681 chip id, module struct compatibility of tuned data.
