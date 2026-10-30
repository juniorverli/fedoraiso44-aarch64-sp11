# Cameras: front IMX681, IR VD55G0, rear follow-ups and the RGB stage (patches 0011 to 0019)

Date: 2026-10-30. Static work plus compiles of the touched objects, `dt_binding_check`, `CHECK_DTBS` and a host test of the
blob parser. No device access, no REA call (the REA MCP is reserved for the audio agent), nothing booted. The IR illuminator
and the flash were not described, driven or read (S2). No Windows byte is in git (S5): the register blobs live under
`out/firmware-private/cameras/` and are installed only by the private image mode (D25).

Grades: **Verified** (read from code or data, or reproduced by a script, cited), **Inference** (derived, reasoning given),
**Unknown** (what would answer it is given).

## Inputs

| Input | Identity |
|:--|:--|
| Linux | `v7.3` + the full current `kernel/series` (38 patches) + cameras 0001-0010, scratch tree `out/linux/cameras-fts`, branch `w/cameras-fts`, tag `base-cam10` |
| Build | `out/build/dev-cameras-fts` (arm64 defconfig tree of the camera build, `VIDEO_IMX681=m`, `VIDEO_OV13858=m`, `VIDEO_VD55G1=m`, `LEDS_GPIO=y`), Fedora 44 container, native aarch64 gcc, `W=1` |
| Windows data (read only) | `sources/windows/DriverStore/surfacecam{front,rear,aux}sensor_extension8380.inf_arm64_*`: `com.surface.sensormodule.*.bin` (QTI Chromatix), `SCFG_*.bin` (AeoB) |
| Earlier evidence | `2026-10-30-rea-windows.md`, `2026-10-30-camera-driver-reference.md`, `2026-10-30-rea-seven-questions.md`, `2026-10-30-cphy-port.md`; the survey decoders in `~/repositories/surface/rea/camera/tools` (outside this repository, read only, reimplemented in the generator) |
| Fedora | `dnf repoquery` and the RPM payloads of `libcamera` and `libcamera-ipa` 0.7.2-2.fc44 in the Fedora 44 container (RPMs unpacked under `out/camera-research/`, outside git) |

## The patches

| # | File | Content | Checks |
|:--|:--|:--|:--|
| 0011 | `media-i2c-add-a-sensor-register-blob-parser` | `drivers/media/i2c/sensor-regblob.h`: header-only parser of the register blob (SRB v1 and v2; v2 adds a POLL operation), layout documented in its header comment | compiled in 0013 and 0016, host test (below and "Reconciliation") |
| 0012 | `dt-bindings-media-i2c-ovti-ov13858-allow-register-bl` | `firmware-name`, up to three link frequencies | `dt_binding_check` clean |
| 0013 | `media-i2c-ov13858-load-additional-modes-from-a-regis` | optional blob modes appended to the built-in ones, own link-frequency entry, `select CRC32` | `ov13858.o` W=1 clean |
| 0014 | `arm64-dts-qcom-x1-microsoft-denali-refine-the-rear-c` | rear LED on GPIO105 (own pin state), `leds` retargeted, CCI0 bus 1 at 400 kHz, `firmware-name`, 592.8 MHz in `link-frequencies`, MCLK1 drive 4 mA | `CHECK_DTBS` clean |
| 0015 | `dt-bindings-media-i2c-add-Sony-IMX681` | binding (C-PHY, 1 to 3 trios, `firmware-name` required) + MAINTAINERS | `dt_binding_check` clean |
| 0016 | `media-i2c-add-a-driver-for-the-Sony-IMX681` | the `imx681` V4L2 sensor driver, Kconfig, Makefile, MAINTAINERS | `imx681.o` W=1 clean |
| 0017 | `dt-bindings-media-i2c-st-vd55g1-describe-the-VD55G0` | `st,vd55g0` in the `st,vd55g1` schema (no driver binds it) | `CHECK_DTBS` clean |
| 0018 | `arm64-dts-qcom-x1-microsoft-denali-describe-the-fron` | front camera, pm8550 L7B and L16B (disabled), pm8010 L3M, CCI1 bus 1, CSIPHY2 C-PHY port | `CHECK_DTBS` clean |
| 0019 | `arm64-dts-qcom-x1-microsoft-denali-describe-the-IR-c` | IR camera, pm8010 L2M/L4M/L7M, CCI0 bus 0, CSIPHY0 D-PHY port | `CHECK_DTBS` clean |

All nine: `checkpatch.pl --strict` reports only "Missing Signed-off-by" (intentional); `Assisted-by: Claude Sonnet 5.5`; no
`Signed-off-by`. Each applies with `git apply --cached` in order on `v7.3` + full series + cameras 0001-0010 (resulting tree equals
the scratch branch tree `9430c177`); they also apply in order on bare `v7.3` after cameras 0001-0010.

Checks of the devicetrees: the packaged `x1p64100-microsoft-denali.dtb`, the existing `...-cam-rear` variant and the new
`...-cam-all` variant (`hardware/cameras/dtb-variants/`) are `CHECK_DTBS=y` clean. A negative test (deleting `avdd-supply` of the
front node in a throw-away variant) makes the checker report "'avdd-supply' is a required property", so the check is live. The
disabled nodes of the packaged DTB are not validated by `CHECK_DTBS`, the `cam-all` variant is what validates them.

Order for `kernel/series` (after cameras 0001-0010): 0011, 0012, 0013, 0014, 0015, 0016, 0017, 0018, 0019. 0013 needs 0011 and 0012;
0016 needs 0011 and 0015; 0018 needs 0016 (compatible) and 0014 (the `cam_mclk1` hunk shares context); 0019 needs 0017.

## Verified

| Fact | Evidence |
|:--|:--|
| The rear indicator is GPIO105 active high; the front and IR share GPIO225 | `2026-10-30-rea-seven-questions.md` Q1; the DTB with both LED nodes is `CHECK_DTBS` clean |
| The GPIO105 pin defaults to function `cci_i2c`; the LED state selects `gpio` | `sources/linux/drivers/pinctrl/qcom/pinctrl-x1e80100.c:1672` (`PINGROUP(105, cci_i2c, ...)`) and the Windows data (TLMM 101-104 muxed to CCI, 105 never) |
| CCI0 bus 1 at 400 kHz; front on CCI1 bus 1 pins GPIO235/236 with function `aon_cci`; MCLK4 on GPIO100 is `cam_aon` | `pinctrl-x1e80100.c:1667,1802-1803`; `rea-seven-questions.md` Q4 |
| CAMSS ports map to CSIPHY indices: port@0, port@2 are csiphy0, csiphy2 | binding `^port@[0-3]$`; `camss.c` `csd->interface.csiphy_id = vep.base.port`; Windows indices 0, 1, 2 equal the PCFG field (`rea-seven-questions.md`, Other findings) |
| The pm8550 `vdd-l6-l7` input is BOB2 in the Denali DT, so L7B can be described without a new parent | `x1-microsoft-denali.dtsi` `regulators-0` |
| pm8010 NLDO range (528 mV + 8 mV steps, max 1.544 V) has no 1.15 V point; 1.152 V is the nearest | `drivers/regulator/qcom-rpmh-regulator.c` `pmic5_nldo502`; the IR core rail range in 0019 is 1.15 to 1.152 V |
| PLDO ranges cover 2.8 V (pm8010 LDO7, pm8550 L7B) and 2.9 V (L16B); pm8010 LDO3/LDO4 give 1.8 V | `pmic5_pldo502`, `pmic5_pldo`, `pmic5_pldo502ln` |
| The CAMSS binding has two CSIPHY supplies only; the J rails (LDO3_J 0.88 V, LDO2_J 1.2 V) already feed the USB/PCIe PHYs of the board, so they stay on while those are enabled | `qcom,x1e80100-camss.yaml:121-127`; `x1-microsoft-denali.dtsi` consumers of `vreg_l3j_0p8`, `vreg_l2j_1p2` |
| The privacy LED is switched by the V4L2 core: `led_get(dev, "privacy")` at sensor registration, max brightness when streaming starts, 0 when it stops | `drivers/media/v4l2-core/v4l2-subdev.c:173-186,498-500,2399,2493`, `v4l2-fwnode.c:1275` |
| The `vd55g1` driver accepts only model ids `S5G1` (0x53354731) and `S5G3` (0x53354733), reads them as a 32 bit register at offset 0, and loads an embedded firmware patch (`vd55g1_patch_array`, start address 0x2000) after the id check; any other id returns `-ENODEV` before the patch | `vd55g1.c:31,137-165,1696-1725,1209,1763` |
| Same register offsets in the VD55G0 module data and `vd55g1.c`: EXT_CLOCK 0x0220, MIPI_DATA_RATE 0x0224, LINE_LENGTH 0x0300, firmware patch region 0x2000; different: the id (0x3047 in a 16 bit read at offset 0 on this device), the GPIO control register (0x0468 against `0x051d + 0x50*ctx`) | `vd55g1.c:34,46,47,53,98`; Windows data via `2026-10-30-rea-windows.md` D9 |
| The three sensor modules carry, per sensor: one `initSetting` array, four driver arrays in the order stream on, stream off, group-hold on, group-hold off, and one `resSettings` array per mode; the stream-on array writes `0x0100 = 1` for OV13858 and IMX681 | local decode of the three modules (this session); roles confirmed by content |
| Register entries are all 16 bit addresses with 8 bit data (plus 3 entries with 16 bit data that belong to test-pattern or actuator arrays), operation 0 write, operation 4 (VD55G0 only; 7 records, all with a non-zero delay) is a POLL, see "Reconciliation" (earlier read as "write then delay", superseded), operation 3 with a slave address is an EEPROM read | decode statistics of the three modules |
| Superseded by "Reconciliation" below (SRB v2, new test run): the first host test parsed the three SRB v1 blobs of the earlier generator | host test of the earlier session |
| The generated OV13858 blob has pixel rate 474.24 MHz, matching `link_freq_to_pixel_rate(592.8 MHz)` in `ov13858.c`; the register value of the line length (1122) times 4 is the driver's pixels per line for the 540 MHz mode (4488) | `ov13858.c:61-62,954-960` |
| The VD55G0 module programs sensor GPIO1 as a strobe output (register 0x0468 = 2); the generator rewrites that one write to 1 (input) and reports it | generator run, `s2_rewrites = 1` |
| libcamera in Fedora 44: `libcamera-0.7.2-2.fc44`, sub-packages `-ipa`, `-tools` (`cam`), `-qcam`, `-gstreamer`, `-v4l2`; `pipewire-plugin-libcamera-1.6.10-1.fc44`; `snapshot-50.0-1.fc44`; `cheese-44.1-16.fc44`; `v4l-utils-1.32.0-3.fc44` | `dnf repoquery` in the Fedora 44 container |
| libcamera 0.7.2 ships camera sensor helpers `ov13858` and `vd55g1`; none for `imx681` or `vd55g0` | strings of `libcamera.so.0.7.2` (helper names registered with the helper factory: ar0144 ... ov13858 ... vd55g1, vd56g3) |
| The simple pipeline handler matches `qcom-camss` media devices; the Software ISP is `libcamera::SoftwareIsp` with CPU statistics for packed RAW10 (`statsBGGR10P`, `statsGBRG10P` and the other orders); `LIBCAMERA_SOFTISP_MODE` selects CPU or GPU | same strings; `libcamera-ipa` ships `ipa_soft_simple.so` |
| The only simple-IPA tuning shipped is `/usr/share/libcamera/ipa/simple/uncalibrated.yaml` with `BlackLevel`, `Awb`, `Adjust`, `Agc`; the `Ccm` algorithm exists but is commented out ("should only be enabled if tuned") | the RPM payload of `libcamera-ipa` |

## Inference

| Statement | Reasoning | What would change it |
|:--|:--|:--|
| The front sensor sends one C-PHY trio, not three | the Windows module data says lanes = 1 and the C-PHY flag 1 for every IMX681 mode; the symbol rate 2.4 Gsym/s per trio at 1 trio gives 5.49 Gbit/s, which carries 3840x2640 RAW10 at 30 fps (3.0 Gbit/s active) with the module's blanking, while 3 trios at 2.4 Gsym/s would be 16 Gbit/s, far above any need. The request text names "3 trios" as the C-PHY maximum; DT 0018 uses `data-lanes = <1>` because CAMSS programs the trio count from the DT and a mismatch with the sensor would break the link | a RAW capture; the IMX681 driver refuses a blob whose trio count differs from the endpoint |
| The link frequency of a C-PHY sensor is half the symbol rate: 1.2 GHz for modes 0 to 4 | V4L2 defines `LINK_FREQ` as `1/(2 UI)` and the C-PHY UI is one symbol (`2026-10-30-cphy-port.md`); the PLL (19.2 MHz / 3 x 375) gives 2400 MHz (`rea-windows.md` D8) | the CSIPHY rate class chosen at the first stream |
| Rail roles of the front: pm8010 LDO3 1.8 V is the I/O rail (`dovdd`), pm8550 L7B 2.8 V the analog rail (`avdd`) | the voltages, the same convention as the OV13858 and the survey (I3) | a datasheet; the sensor is not damaged by the order below, only mis-named |
| The front power order is clock first (Windows order), then I/O, analog, 1 ms, reset release, 10 ms | the PEP sequence (`rea-windows.md`), delay unit milliseconds (`rea-seven-questions.md` Q3) | none expected |
| The IR rails are core 1.15 V (pm8010 LDO2), I/O 1.8 V (LDO4), analog 2.8 V (LDO7) | the VD55G1 binding voltages (vcore 1.15, vddio 1.8, vana 2.8) against the Windows rail voltages | a datasheet |
| (Resolved, now Verified) Mode `i` owns its `resSettings` and `streamConfiguration` through pointers in its `resolutionData` record | see "Reconciliation"; the symbol-order guess was right for all 9 modes the builder checks (the skipped presence mode is not) | none |
| IMX681 control registers follow the public MIPI CCS addresses (exposure 0x0202, analogue gain 0x0204, frame length 0x0340, 16 bit big endian) | the IMX681 init writes CCS registers 0x0111 (PHY type), 0x0112 (CSI format), 0x0114 (lanes), 0x0136 (EXTCLK); the module names only the digital gain (0x020e), short exposure (0x0224) and a middle exposure (0x30b2), not the analogue gain | a RAW capture with two exposures; REA of the gain path |
| The sensor array of the IMX681 is 4032 x 3024 | the module's `dimension` field (0xfc0 x 0xbd0) | the active-array crop of each mode (`activeArrayCropInfo` is zero) |
| `hts` for the OV13858 is the line-length register times 4 | equality with the Linux driver's pixels per line for the same register value (Verified, above) | a measured frame rate; for the IMX681 and VD55G0 the scale is 1 and their blanking figures are not trusted |
| One Windows mode per frame size is enough: the generator keeps the lowest frame rate of each size (mode 2 over mode 1 at 3840x2160) and drops the presence mode 5 (504x378 at 3 fps) | the driver selects a mode by size; the 60 fps mode would need more CSIPHY and CSID bandwidth for no benefit before the first capture | a user need for 60 fps |
| IR rail and GPIO functions in the Windows module (strobe on sensor GPIO1) | register 0x0468 value 2 and the earlier survey's register map | REA of the IR driver |

## Unknown, only hardware or later REA can settle

| # | Unknown | What answers it |
|:--|:--|:--|
| U1 | Bayer order of the IMX681 (the generated blob says `rggb` by default, a guess); OV13858 GRBG is an Inference (see "Reconciliation") | one RAW capture of a coloured target, or REA of the colour-filter enumeration |
| U2 | Whether the C-PHY link locks (CSIPHY C-PHY sequence, CSID bit 24, settle values, trio polarity) | the first stream of the front camera on the device |
| U3 | IMX681 analogue gain register and gain code law; hblank and frame rate units; active-array crop per mode | REA (questions below) and measurement |
| U4 | Whether the register blobs boot the sensors: the init/mode split of the Windows tables, the order init then mode, and the stream on/off sequences were read from the module data, never executed | the first stream |
| U5 | VD55G0: whether a driver derived from this design works; the model id read (0x3047) and the address 0x60 | a probe through a `vd55g0` driver (no `i2cdetect`) |
| U6 | pm8010 and pm8550 supply parents for L2M/L3M/L4M/L7M (pm8010 `vdd-l*` inputs) | REA question 2 of `camera-driver-reference.md`; the DT leaves them out (the RPMh driver accepts that) |
| U7 | Whether the CSIPHY needs the J rails from the camera path | device test with the J consumers disabled; not needed on the live USB |
| U8 | What the actuator rail L16B 2.9 V feeds (DW9800 voice coil, EEPROM M24C64 at 8-bit 0xA0): no lens driver, no node | a DW9800 driver decision; nothing consumes the rail |
| U9 | Whether the front and the IR share one LED safely: the V4L2 core has no use count, so the LED goes off when either sensor stops | the first simultaneous capture; see "Privacy LED" |

## Reconciliation of the generator and the module survey (SRB v2)

Two independent pieces of work disagreed: the generator (SRB v1: write and delay only) and the module survey
(`2026-10-30-module-data-format.md`: operation 4 is a poll, mode-to-array pointers found, IR file MSHW0492, OV13858 colour code,
IMX681 colour code). Reconciled in place, because patches 0011 to 0019 are in no built kernel yet. No register address, value
or table appears in this section (S5).

| Topic | Before | Now | Grade |
|:--|:--|:--|:--|
| Blob format | SRB v1: write8, delay | SRB v2: version field 1 or 2, parser reads both. New op 2 POLL takes two 4-byte slots (slot 0: register, expected value, op; slot 1: mask, 24-bit timeout in microseconds). Mask must be non-zero, timeout 1 to 10 s. A v1 file with a poll is invalid. The first poll that times out fails the list with `-ETIMEDOUT` and a `dev_err` naming register, timeout, value read, expected value and mask | design |
| `srb_apply()` | `(ops, write, ctx)` | `(dev, ops, write, read, ctx)`; `read` may be NULL (a poll then returns `-EOPNOTSUPP`). `imx681` supplies a CCI read; `ov13858` still converts the list to its own register table and refuses every non-write operation, so a delay or poll in an OV13858 blob drops the blob (built-in modes stay) | design |
| Windows op 4 | write then sleep | POLL until equal, delay field = timeout in microseconds, mask 0xff (the module has no mask). The builder refuses a poll without a timeout, with 16-bit data or above 10 s | Inference, strong (position next to the `vd55g1.c` boot polls); Windows consumer not read |
| Mode to array mapping | symbol order guess | the builder follows `resolutionData` +0x14/+0x18 (`streamConfiguration`) and +0x6C/+0x70 (`resSettings`), checks symbol names and sizes, and records `mode_pointers_match_symbol_order` in the manifest: true for all three modules | Verified |
| IR module file | MSHW0492 already selected by name | explicit check in the builder that the file is the MSHW0492 one (the MSHW0472 file belongs to another SKU) | Verified (device id `pnp-present`) |
| OV13858 Bayer | media bus code 0 (driver default) | GRBG written into every mode, and the only order the builder accepts | Inference, medium (even window origins and flip bits as the Linux full mode, `ov13858.c:1280-1284`) |
| IMX681 Bayer | mandatory option | option defaulting to `rggb`; every run prints a loud note and the manifest stores it; a RAW capture decides | Unknown |
| VD55G0 strobe | rewritten to input | unchanged: one write rewritten (manifest `s2_rewrites = 1`) | Verified |

Generated blobs (this machine, `out/firmware-private/cameras/`, mode 0600, never in git): `ov13858-mshw0491.bin` (3 modes, 0 polls),
`imx681-mshw0490.bin` (4 modes, 1 dropped same-size mode, 0 polls), `vd55g0-mshw0492.bin` (1 mode, 7 polls: 3 in stream on, 4 in
the mode list). All three are SRB v2. The builder's independent verifier re-checks versions, slot pairs, mask and timeouts.

Kernel parser test (the real, unmodified `drivers/media/i2c/sensor-regblob.h` of the amended 0011, compiled on the host with
`-fsanitize=address,undefined` against a small shim of the kernel headers, exact-size heap buffers; scratchpad, not in git):

| Case | Result |
|:--|:--|
| synthetic v1 and v2 blobs, with and without polls | accepted; `srb_apply` runs them |
| the three real blobs | accepted as v2 (OV13858 3 modes, IMX681 4, VD55G0 1) |
| the same three relabelled v1 | OV13858 and IMX681 accepted (no poll); VD55G0 rejected (contains polls) |
| poll succeeds after 3 not-ready reads (synthetic); the real VD55G0 against a fake device that answers each poll with its expected value after 2 reads | `apply = 0`, all 599 writes issued |
| poll never ready (50 ms timeout) | `-ETIMEDOUT`, elapsed 55 ms, the list stops at the poll (later writes not issued); the real VD55G0 does the same |
| poll with a mask | matches under the mask |
| poll with no read callback | `-EOPNOTSUPP` |
| v1 with poll, poll cut by the list count, mask 0, timeout 0, timeout above 10 s, unknown op 3, version 0 and 3, header size 48 | all rejected `-EINVAL`; timeout exactly 10 s accepted |
| every truncation (128 v1 prefixes, 148 v2 prefixes) | all rejected |
| every payload byte flipped (64 v1, 84 v2), wrong CRC field, bad magic, total size beyond the file | all rejected |
| 6000 random mutations with the CRC repaired, 30 percent also truncated | 1446 accepted, 4554 rejected, no ASAN or UBSAN report |

Compile tests on the scratch tree (`w/cameras-fts`, rebased: 0011, 0013, 0016 amended): `imx681.o`, `ov13858.o`, `vd55g1.o` with `W=1`:
no warning. `checkpatch.pl --strict` on all nine commits: only "Missing Signed-off-by". `git apply --cached` of all 62 patches
(the 48 entries of the current `kernel/series`, which already hold cameras 0001-0005 and the audio 0006-0016 group, then cameras 0006
to 0019) on `v7.3`: clean, and the camera files equal the scratch branch.

Still Unknown after this reconciliation: whether op 4 really is "equal" (not "not equal" or a bit test) and whether the timeout is the
poll limit (needs the Windows consumer in `QcDeviceMFT8380.dll`, REA); the IMX681 colour code 3; the OV13858 GRBG (a RAW capture);
whether the blobs boot the sensors (U4).

## Front camera: the IMX681 driver

Design (patch 0016): `drivers/media/i2c/imx681.c`, about 870 lines. It contains no sensor register value.

- Probe order: read `firmware-name`; `request_firmware()`; `srb_parse()`; check the endpoint (C-PHY, one to three trios, link
  frequencies); build the mode table; only then clock, supplies, reset GPIO, regmap and power on. A missing or invalid blob fails
  the probe **before the hardware is touched**.
- The blob names the identification register and value. A mismatch logs the value read and returns `-ENODEV`: this makes the
  first device test self-documenting (`dmesg` prints the chip id the sensor returned).
- Streaming: `enable_streams` runs the init list, the mode list, the control handler setup, then the stream-on list;
  `disable_streams` runs the stream-off list. Runtime PM powers the sensor.
- Media bus code: the blob's field, which must be a RAW10 Bayer code. The generator defaults the IMX681 to `rggb` (a GUESS, printed as a loud note on every run and stored in the manifest); `--bayer` / `--bayer-imx681` overrides it. The OV13858 is fixed to GRBG.
- Limits: one mode per frame size; every mode must share the media bus code and the trio count of the endpoint; a link frequency
  of a mode that the endpoint does not list rejects the blob; the native array size is reported as the largest mode (the module
  says 4032 x 3024, not used yet).
- Reports C-PHY with the endpoint's trio count through `get_mbus_config`; provides link frequency, pixel rate, hblank, vblank,
  exposure, analogue gain (the last three only if the blob lists their registers), plus orientation and rotation from the DT.

Register blob format (SRB v2, v1 still readable; see "Reconciliation"): documented in the header comment of `sensor-regblob.h` (patch 0011): 64 byte header
(`SPSRBLOB`, version, size, CRC-32, offsets), 4 byte operations (write8, delay in milliseconds, and in v2 a poll that takes two slots), 20 byte control records,
40 byte mode records. The kernel parser validates magic, version, size, CRC, offsets, counts, operation codes and every mode
and control record before any accessor reads a byte. Nothing hardware-specific is in the format.

The blob files and their names (DT `firmware-name`): `ov13858-mshw0491.bin`, `imx681-mshw0490.bin`. They go to
`/usr/lib/firmware/updates/` (the kernel looks there first; the Wi-Fi board file uses the same place).

## IR camera: compatibility check of `vd55g1.c` and the design

Result: **do not extend `vd55g1.c` blindly.**

- The id check rejects the VD55G0 (`vd55g1_detect`, `vd55g1.c:1696-1725`): the Windows driver reads 0x3047 from a 16 bit read at
  offset 0; `vd55g1.c` reads a 32 bit value and accepts only two ids. That is the right behaviour.
- The register map overlaps (clock, data rate, line length, patch start) but the GPIO control differs, and `vd55g1.c` loads
  its own firmware patch after the id check. The Windows VD55G0 init carries a different patch in its 601-entry mode list.
  Accepting the VD55G0 id in `vd55g1.c` would write another sensor's patch into this one. A minimal change is therefore **not
  safe** without the VD55G0 datasheet, and the generator output cannot replace the patch inside `vd55g1.c`.
- Patch 0017 adds `st,vd55g0` to the schema only; the node of 0019 binds no driver, so enabling it in the `cam-all` variant powers
  nothing except what the DT supplies describe (the supplies are regulators with no consumer, so the core leaves them off).

Design for a `vd55g0` driver (not written, because the sensor cannot be exercised): copy the structure of `imx681.c`, change
the bus to one D-PHY lane (`MEDIA_BUS_FMT_Y10_1X10`, `bus-type` D-PHY), the supplies to `vcore`, `vddio`, `vana`, the clock check
(19.2 MHz is inside the 6 to 27 MHz of the family), and take everything else from the blob. The VD55G0 blob already exists in the
generator output (one mode 644x604 RAW10 mono, 60 fps, 840 Mbit/s per lane, 420 MHz link frequency, init empty, stream on 7
operations, stream off 1, mode list 605 operations with the firmware patch). The strobe output on sensor GPIO1 is neutralised
(S2). The first job of that driver is the identification read at address 0x60.

## RGB stage: the image-side plan

Why RAW cannot be the product: CAMSS on this SoC is RDI only (`2026-10-30-camera-driver-reference.md`); the RGB stage is the
libcamera Software ISP.

| Piece | Package (Fedora 44, Verified by `dnf repoquery`) | Notes |
|:--|:--|:--|
| libcamera runtime, simple pipeline handler, soft ISP IPA | `libcamera`, `libcamera-ipa` 0.7.2-2.fc44 | `ipa_soft_simple.so` (CPU statistics; GPU path selected with `LIBCAMERA_SOFTISP_MODE`) |
| tools | `libcamera-tools` (`cam`), `libcamera-qcam`, `v4l-utils` 1.32.0-3.fc44 | for the test plan |
| PipeWire to applications | `pipewire-plugin-libcamera` 1.6.10-1.fc44 (and `pipewire`, already in Workstation) | portals and browsers get the camera through PipeWire |
| GStreamer | `libcamera-gstreamer` 0.7.2-2.fc44 (`libcamerasrc`) | Snapshot and others |
| Camera app | `snapshot` 50.0-1.fc44 (GNOME Camera); `cheese` 44.1-16.fc44 as a fallback | Snapshot uses PipeWire |
| V4L2 compatibility | `libcamera-v4l2` | optional, for apps that need `/dev/video*` |

Kernel configuration the RGB path needs (kernel owner confirms against the Fedora config): `CONFIG_VIDEO_QCOM_CAMSS`,
`CONFIG_I2C_QCOM_CCI`, `CONFIG_VIDEO_OV13858`, `CONFIG_VIDEO_IMX681` (new), `CONFIG_V4L2_CCI_I2C`, `CONFIG_CRC32`,
`CONFIG_LEDS_GPIO`, `CONFIG_CLK_X1E80100_CAMCC`, `CONFIG_REGULATOR_QCOM_RPMH`, and for the Software ISP buffers
`CONFIG_DMABUF_HEAPS` with `CONFIG_DMABUF_HEAPS_SYSTEM` (access to `/dev/dma_heap` for the logged-in user: the udev rule of
the `libcamera` package or `uaccess` must be checked on the image, Unknown).

Tuning files (the question for libcamera 0.7):

- Sensor helpers: `ov13858` exists, so gain codes of the rear camera convert correctly. For `imx681` and `vd55g0` there is **no
  helper**; libcamera is expected to fall back to using the control value as the gain (Inference, the helper code was not read), which would make automatic
  exposure and gain unreliable but not block capture. To add them: a `CameraSensorHelperImx681` (and `Vd55g0`) in
  `src/ipa/libcamera/camera_sensor_helper.cpp` with the gain model of the sensor (the analogue gain code law is U3) and the
  black level; registration with `REGISTER_CAMERA_SENSOR_HELPER("imx681", ...)`. Work: derive the gain law (REA or a two-point
  measurement), write the helper, send it upstream or carry it as a Fedora patch (Fedora-native first: ask upstream, carry a
  patch only for the image).
- Tuning YAML for the simple IPA: only `uncalibrated.yaml` is shipped (BlackLevel, Awb, Adjust, Agc). With it the picture is
  colour-correct only through grey-world AWB; the colour correction matrix stays off. A per-sensor file
  `/usr/share/libcamera/ipa/simple/<sensor>.yaml` named like the sensor (`ov13858.yaml`, `imx681.yaml`) enables `Ccm` and a
  black level. The values can come from the Windows `com.surface.tuned.*.bin` files (black level `bls12`, colour correction
  `cc13`, gamma, lens shading `lsc41`); the survey's `tuning.py` already decodes them. Converting them yields Windows-derived
  numbers: a local, private-mode file only (S5). Deliverable of the next session: `build-libcamera-tuning.py` next to the
  firmware generator, writing under `out/firmware-private/cameras/`. Until then the image ships `uncalibrated.yaml`.
- Colour order: the Software ISP debayers with the media bus code reported by the sensor; a wrong Bayer order gives swapped red
  and blue (U1), which is exactly what the RAW capture check of the test plan detects.

Privacy LED (Verified mechanism): the DT gives each sensor `leds = <&led>; led-names = "privacy";`.
`v4l2_async_register_subdev_sensor()` calls `led_get(dev, "privacy")` (defers the probe until the LED exists, so `LEDS_GPIO=m`
is acceptable), the V4L2 core sets the LED to its maximum brightness when streaming starts and to 0 when it stops
(`v4l2-subdev.c:173-186`, `498-500`, `2399`, `2493`). No driver code is involved; ov13858 and imx681 get the behaviour from the
DT. Rear: GPIO105; front and IR: GPIO225. Known gap: GPIO225 is shared and the core keeps no use count, so stopping the IR stream
while the front still streams turns the LED off (Windows counts uses per LED). Until a core patch adds a counter, the LED is only
correct if the two sensors are not used at the same time. This is a privacy defect to fix before any release (U9).

## What the front/IR/RGB deliverables lack until REA or the device answers

REA questions for later, in the order of usefulness (not asked now; the audio agent holds REA):

1. `surfacecamfrontsensor8380.sys` / the module: the field of a `resolutionData` record that names its `resSettings`
   array, and the enumeration behind the colour-filter code (3 = ?, 0 = ?, 4 = mono).
2. The IMX681 analogue gain register, the gain law (`realToRegGain`, `regToRealGain` are empty in the module, so the law is in the
   driver code), the frame-length register and the active-array crop per mode.
3. The units of `LLPCK` (line length) against the output pixel clock for the IMX681 and VD55G0.
4. `surfacecamauxsensor8380.sys`: the GPIO strobe register map of the VD55G0, the id width at offset 0 and whether the address
   is strapped.
5. pm8010 `vdd-l1-l2`, `vdd-l3-l4`, `vdd-l5`, `vdd-l6`, `vdd-l7` parents (already question 2 of the earlier list).
6. Windows sensor driver: does it write the sensor's own privacy or strobe registers.

## Requests

For the kernel worker (series order, after cameras 0001-0010 and 0006-0010):

- K1: add `hardware/cameras/patches/0011` to `0019` to `kernel/series` in the order 0011, 0012, 0013, 0014, 0015, 0016, 0017,
  0018, 0019. All apply on the full current series.
- K2: confirm in the Fedora-based config: `CONFIG_VIDEO_IMX681=m`, `CONFIG_VIDEO_OV13858=m`, `CONFIG_CRC32=y`,
  `CONFIG_DMABUF_HEAPS_SYSTEM=y`, `CONFIG_LEDS_GPIO` (m or y), plus the earlier list (CAMSS, CCI, CAMCC, RPMH).
- K3: build `hardware/cameras/dtb-variants/x1p64100-microsoft-denali-cam-all.dts` as a diagnostic variant (`scripts/kernel-dev.sh
  <id> variant`); the earlier rear-only variant stays valid.
- K4 (optional, later): a V4L2 core patch with a use count for a shared privacy LED (U9).

For the image worker:

- I1: install `libcamera`, `libcamera-ipa`, `libcamera-tools`, `libcamera-qcam`, `libcamera-gstreamer`,
  `pipewire-plugin-libcamera`, `snapshot`, `v4l-utils` (Workstation Live is expected to carry PipeWire and GStreamer core; not re-checked).
- I2: install `hardware/cameras/collector/cameras.sh` as `/etc/sp11-log-collector.d/cameras.sh` (read-only).
- I3 (private mode only, D25): install the operator-provided `out/firmware-private/cameras/ov13858-mshw0491.bin` and
  `imx681-mshw0490.bin` to `/usr/lib/firmware/updates/`, and never in the public image. Generate them with
  `python3 -I hardware/cameras/userspace/build-camera-firmware.py all [--bayer-imx681 <rggb|bggr|grbg|gbrg>] [--ccs-controls
  --again-range MIN:MAX:STEP:DEFAULT]` before the image build. The IMX681 Bayer order is Unknown and defaults to `rggb`: build the
  first private ISO with that, read the colours of the RAW capture, rebuild if red and blue are swapped. The OV13858 blob is
  GRBG without an option. All blobs are SRB v2 now.
- I4: check access to `/dev/dma_heap/system` and `/dev/media*` for the live user (the Software ISP needs both).

For the REA owner (after the audio agent releases REA): the six questions above.

## Not done

- No `vd55g0` driver; the IR node binds nothing.
- No libcamera tuning files or sensor helpers; no `build-libcamera-tuning.py`.
- No lens driver or actuator node (DW9800 on the rear bus, EEPROMs), so no autofocus and no calibration data.
- The IR illuminator, the PMIC flash and the sensor strobe are not described (S2).
- No kernel build and no `vmlinux` link: only the touched objects were compiled, as in the earlier camera work.
