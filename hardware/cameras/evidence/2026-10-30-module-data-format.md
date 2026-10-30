# Cameras: format of the Windows sensor module data

Date: 2026-10-30. Static analysis of data files plus one REA attempt. No kernel build, no
device access. Structure only: no register address, value or table is quoted (S5). The
tool `hardware/cameras/userspace/parse-camera-module.py` reads the files and prints
structure; its `--emit` mode writes raw records outside git for the local generator.

Grades: **Verified** (read from the data, checked by a script on all three files),
**Inference** (reasoning given), **Unknown**.

## Inputs and classification

| Sensor | File (DriverStore package `surfacecam*sensor_extension8380`) | Size | Classification |
|:--|:--|:--|:--|
| Rear OV13858 | `com.surface.sensormodule.rfc_ov13858.bin` | 148262 | QTI Chromatix container, data, no code |
| Front IMX681 | `com.surface.sensormodule.ffc_imx681.bin` | 212272 | same |
| IR VD55G0 (MSHW0492, the module `pnp-present` lists) | `com.surface.sensormodule.aux_vd55g0_MSHW0492.bin` | 136411 | same |

SHA-256 values are in `sources/binary-catalog.tsv` (rows of the three files). The MSHW0472
IR file differs (pixel clock 75.6 MHz, 4 bytes shorter) and belongs to another SKU; the
parser and the generator must use the MSHW0492 file.

Classification (Verified): little endian, byte-aligned, architecture neutral. Every field
is a `u32` or a `double`; there are no pointers, a reference is a symbol index. Not
compressed, not encrypted, not signed (only a CRC-32). The same container serves the
actuator, EEPROM and flash drivers of a module. Inference: it is the serialized form of the
CamX `ImageSensorData` structures (symbol names such as `resolutionData`, `regSetting`,
`powerSetting`, `moduleConfiguration` are CamX field names, and the consumer path in
`QcDeviceMFT8380.dll` is `CamX/camx/src/core/SensorDataManager/camximagesensormoduledata.cpp`).

## Container layout (Verified)

- Header: magic `QTI Chromatix Header` at 0x00; `u32` at 0x1C equals file size minus 4;
  `u32` words 3 and 1 at 0x20 and 0x24 (container version, identical in all files); parser
  version string `Parameter Parser V3.4.0 (2106301010)` at 0x28; module name at 0x58; section
  table offset 0xA8 and count 3 at 0xA0.
- Section table: `{id, offset, size}` x 3. Section 0 symbol table, section 1 data heap,
  section 2 a 20-byte trailer (constant, no content).
- Symbol record, 0x38 bytes: `u32 index` (1..N in file order), `char[32] name`, three `i32`
  (`a`, `b`, `c`: unused here, constant 0/0/-1 or 1/0/0), `u32 data_offset` (into section 1),
  `u32 data_size`. 2117, 3035 and 1956 symbols for rear, front, IR. The same name appears
  many times (one symbol per array element or per mode); the name is the type, the index
  is the identity.
- Integrity: the last four bytes are the zlib CRC-32 of all preceding bytes. Verified equal
  for all three files. No signature, no hash, no version field beyond the parser string.
  Offsets and sizes of symbols stay inside section 1 for every record (checked).
- Object model: a fixed member is stored inline; a variable-length member is a
  `(u32 count, u32 symbol index)` pair; an array is the bytes of its symbol. The root
  object is the symbol `sensorDriverData` (568 bytes, one per file); `cameraModuleData`
  (20 bytes) points at `moduleConfiguration`.

## Modes (Verified, per sensor)

`resolutionData`: one symbol holding `n_modes` records of 252 bytes, mode index = record
index. Mode counts: rear 3, front 6, IR 1 (matches the earlier survey).

Fields of a record, by byte offset (names from the symbol table, roles by data and by the
earlier cross-checks):

| Offset | Size | Role | Grade |
|:--|:--|:--|:--|
| 0x10 | u32 | numeric colour filter code, one value per sensor (0 rear, 3 front, 4 IR) | Verified (position); meaning see below |
| 0x14, 0x18 | u32, u32 | `(count 1, symbol)` of this mode's `streamConfiguration` | **Verified** (resolves the generator's open question 1: the mode owns its arrays through these pointers, not by symbol order) |
| 0x24, 0x28 | u32 | line length and frame length in the module's units | Verified (position), Inference (units) |
| 0x2C, 0x30 | u32 | minimum horizontal and vertical blanking | Inference |
| 0x34 | u32 | output pixel clock in Hz | Verified by the derived link rates |
| 0x40 | double | frame rate | Verified |
| 0x50 | u32 | lanes (D-PHY) or trios (C-PHY) | Verified |
| 0x60 | u32 | C-PHY flag, 1 only for IMX681 | Verified |
| 0x6C, 0x70 | u32, u32 | `(count 1, symbol)` of `resSettings` | **Verified** |

`streamConfiguration` (60 bytes = 15 `u32`): word 1 is the symbol of the 4-byte `vc` object
(all zero, virtual channel 0), word 2 the MIPI data type (0x2B for every mode), words 5, 6
the output width and height, word 7 the bits per sample (10 everywhere). Words 3 and 4 vary
per mode with no consumer found (crop origin is plausible). **Unknown.**

`resSettings` (8 bytes) is `(record count, regSetting symbol)`: the mode's register
sequence. The derived link rate is `pixel clock x bits / lanes`: 1185.6 Mbit/s per lane
(rear), 840 Mbit/s (IR); for C-PHY it is per trio before the 7/16 symbol conversion
(front 2.4 Gsym/s, mode 5 2.87 Gsym/s). Verified (matches the survey).

## Register records (Verified)

`regSetting` array element, 40 bytes, ten `u32`:

| Word | Meaning |
|:--|:--|
| 0, 1 | slave address override: present flag, symbol of a 1 to 4 byte value (8-bit form, `>> 1` for Linux). Present on one record per rear and front module only (EEPROM read), never in mode sequences |
| 2 | register address (32-bit holder, 16-bit in use) |
| 3, 4 | data value count and symbol of the data array. Count is 1 in all 2160 records: **no burst records exist**. The value is a `u32` in the symbol |
| 5 | address type code: 2 = 16-bit in every mode, init and stream sequence (1 = 8-bit appears only in actuator and EEPROM records of the rear module; 0 in one IR record that is not a sequence record) |
| 6 | data type code: 1 = 8-bit in every mode, init and stream sequence (2 = 16-bit in a test-pattern record and in the EEPROM read) |
| 7 | operation: 0 = write, 3 = read (EEPROM, data word is the length), 4 = poll (IR only) |
| 8, 9 | delay: present flag, symbol of a `u32` delay in microseconds (unit by name, Inference). Non-zero only on the seven IR poll records |

Op 4 grade: **Inference, strong.** The IR poll records appear where the upstream `vd55g1.c`
polls the boot command register until it clears and the FSM state register for ready. The
delay is the poll timeout. They must not be replayed as "write then sleep".
Rear, front and the IR mode records otherwise contain writes only.

I2C slave: **not in the sequences.** The sensor slave comes from `SCFG_*` (see
`2026-10-30-rea-seven-questions.md`); the module carries only the EEPROM and actuator
overrides. No I2C speed is in the module.

## Sequences and roles (Verified by content on rear and front, by position on IR)

- Root `sensorDriverData` holds four `(count, regSetting symbol)` pairs at 0x168, 0x170,
  0x178, 0x180: **stream on, stream off, group-hold on, group-hold off**.
- Init: pair at 0x1A8 to `initSettings` (12-byte elements `{u32 0, count, symbol of
  initSetting}`), each `initSetting` element is `(count, regSetting symbol)`. One element in
  all three files.
- Mode sequences: `resSettings` of each mode. They are complete mode settings (not deltas
  against init): PLL, geometry and format are all in them (Inference from the first record
  kinds; rear 207, front 68 or 204, IR 601 records).
- Record counts: rear init 1, on 1, off 1, hold 1+2, modes 207 each. Front init 364, on 1,
  off 1, hold 1+1, modes 68 x5 and 204 (the presence mode). IR init 1, on 4 (one write and
  three polls), off 1, hold 1+1, one mode of 601 records (597 writes, 4 polls).
- Other regSetting arrays (rear 5, front 3, IR 4) are actuator, EEPROM, test pattern, lens
  park and similar, not needed for streaming.
- Group-hold records, exposure and gain address symbols: the module names the registers; the
  generator's control table depends on them (see `build-camera-firmware.py` notes). Gain law
  is not in the module (`realToRegGain` and `regToRealGain` are 1-byte stubs). Unknown.

## The numeric colour filter code (Unknown for IMX681, partial for the others)

Position and values are Verified (0 rear, 3 front, 4 IR). Its meaning needs the consumer's
enumeration.

- REA attempt: `QcDeviceMFT8380.dll` (sha256 `c241b7fb`, matches the catalog; it contains
  the parser strings `QTI Chromatix Header` and the CamX source path above) did not finish
  Ghidra import within the 330000 ms startup deadline (24 MB image, 2G heap). No function
  address obtained. Request for the sources worker: `REA_GHIDRA_STARTUP_TIMEOUT_MS` at
  least 1800000, `GHIDRA_MAXMEM` 6G. `qccamisp8380.sys` has no enumeration (earlier session).
- The DLL contains no Bayer order name strings (ASCII or UTF-16), so there is no printable
  table; the order must come from code that maps the number.
- Mono IR = 4 fits an enumeration with four Bayer orders first and a luma entry fifth. It
  excludes nothing of the four Bayer orders for 0 and 3.
- OV13858 cross-check (Inference, medium): the Windows modes start their window on even
  columns and rows and keep the flip register bits the same as the Linux full mode, so the
  Windows output should have the Linux order (GRBG). That contradicts a "BGGR first"
  enumeration for code 0 unless the Windows flip bits differ in a way the datasheet would
  show (not available). So the enumeration order is not settled by this check.
- IMX681 code 3: **Unknown.** Decide with one RAW frame of a coloured target. The
  generator already makes the order an explicit option.

## Blob formats

1. **SRB v1** (`SPSRBLOB`, kernel patch 0011): the format the drivers load; the existing
   `build-camera-firmware.py` builds it from the same data. Mapping from the module:
   init, on, off from the sequences above; per mode width/height from `streamConfiguration`,
   lanes from 0x50, link frequency and pixel rate from 0x34, hts/vts from 0x24/0x28 (scaled
   per sensor), mbus code from the colour code (Unknown) and the bit width, ops from
   `resSettings`. Poll records are not representable in SRB v1 (write and delay only).
2. **SPMODREC v1** (written by `--emit`; superset, raw, lossless; layout in the script's
   docstring): 48-byte header (magic, version 1, header size, total size, CRC-32 of the
   body, mode count, sensor index 0/1/2, colour code, 16-byte sensor name), five
   `{offset, count}` sequence entries (init, stream on, stream off, hold on, hold off), one
   56-byte record per mode (width, height, fps x 1000, lanes, C-PHY flag, bits, data type,
   virtual channel, colour code, pixel clock, lane rate in kbit/s, line length, frame
   length, minimum blanking, mbus code or 0, operation list offset and count), and 20-byte
   operation records (register, value, delay in microseconds, operation code, address and
   data widths in bytes, slave override flag and value). Sensor identity of a driver blob is
   the sensor index plus name, the chip id check stays in SCFG.

## Tool results (this machine, 2026-10-30)

`python3 -I hardware/cameras/userspace/parse-camera-module.py` read all three files: CRC
ok, 11/14/10 regSetting arrays with 632/915/613 records, 3/6/1 modes, every record count
matches its symbol size, no burst, no dangling symbol. `--emit` wrote three files whose CRC
and bounds were re-checked by an independent reader. The tool refuses a directory inside the
git tree unless git ignores it (the repository's `/out`, a symlink to the main checkout's
ignored `out/`).

## Unknown

- Meaning of the colour filter code for IMX681 (and a firm one for OV13858).
- Stream configuration words 3 and 4.
- Units of line length and frame length for IMX681 and VD55G0.
- Poll semantics of op 4 against the actual Windows consumer (REA of `QcDeviceMFT8380.dll`).
- Whether the group-hold records matter for a first driver (no).
