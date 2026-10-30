# Cameras: the seven open questions, answered from the Windows stack

Date: 2026-10-30. Static analysis only. No kernel build, no device access, no firmware write.
The IR illuminator and the flash were read, never driven (S2). No Windows bytes, register
tables, memory addresses or serials are quoted (S5); only file names, short hash prefixes,
function addresses, pin numbers, rail names and conclusions.

Grades: **Verified** (read from data or from decompiled code at the cited place),
**Inference** (derived, reasoning given), **Unknown**.

## Method and REA log

One binary at a time, each closed with `close_binary` before the next. Every sha256 in the
result was compared with `sources/binary-catalog.tsv`: all matched. The Ghidra language was
`auto-from-header` in this MCP session (AArch64 PE, so identical to the catalog's
`AARCH64:LE:64:v8A`); the protocol asks for it to be forced, which the sources worker should
set in the MCP server environment.

| Order | Binary | sha256 prefix | Used for |
|:--|:--|:--|:--|
| 1 | `qcpep8380.sys` (1.0.4458.2600 package) | `e5bdeb8c` | PEP `DELAY` unit (Q3) |
| 2 | `qccamplatform8380.sys` | `836714ec` | privacy LED table and writer (Q1) |
| 3 | `surfacecamfrontsensor8380.sys` | `80a8e4a1` | sensor configuration parser, I2C fields (Q4, Q5) |
| 4 | `surfacecamrearsensor8380.sys` | `b7d7a278` | sensor identity used by the LED table (Q1) |
| 5 | `surfacecamfrontsensor8380.sys` (again) | `80a8e4a1` | same identity check for the front (Q1) |
| 6 | `qccamisp8380.sys` | `64463b4d` | search for a Bayer pattern table (Q6): none |
| 7 | `qccamflash8380.sys` | `6bc1d698` | IR LED setup (Q7) |

Data files were read with plain scripts (AeoB container: tag 3 container, tag 1 string, tag 0
value; Chromatix module: the decoders of the earlier survey in `~/repositories/surface/rea/camera/tools`,
outside this repository). ACPI was read as text from `sources/windows/live-inventory/acpi/dsdt.dsl`.
`iasl` is not needed: the `.dsl` files are already decompiled.

## Q1. Which GPIO drives each camera's recording indicator, and its polarity

**Answer: Verified.**

| Camera | Indicator | Polarity | Grade |
|:--|:--|:--|:--|
| Rear OV13858 | **GPIO105** | active high | Verified (table and writer); sensor identity Inference, strong |
| Front IMX681 | **GPIO225** | active high | Verified |
| IR VD55G0 | **GPIO225** (shared with the front) | active high | Verified for the table; IR identity by elimination (see below) |

How it was read:

- `dsdt.dsl` device `CAMP` (`QCOM0C32`) lists exactly two `GpioIo` resources, in this order:
  pin 225 then pin 105. No other device in the DSDT references either pin (text search of
  `dsdt.dsl`, one hit each, both in `CAMP`). Index 0 is therefore GPIO225 and index 1 is GPIO105.
- `qccamplatform8380.sys` (sha `836714ec`), `Get_PrivacyLED_ACPI_Info` at `0x140001884`: it reads
  the `PrldBinaryPath` file (`CAMP_PRLD_MSHW0495.bin`, six words, only two non-zero) and
  expands every word into a per-sensor mask (low byte, one bit per sensor index), an LED type
  (2 bits; type 1 is "GPIO"), a GPIO index (3 bits) and a polarity bit. Decoding the two
  non-zero words: the first selects sensor indices 1 and 2, type GPIO, GPIO index 0; the second
  selects sensor index 0, type GPIO, GPIO index 1. Both have the polarity bit clear.
- The writer, `FUN_140001b38` (called through `0x140001db4`), turns the LED on by writing the
  line high when the polarity bit is clear (it inverts only when the bit is set), through the
  GPIO resource hub connection of that GPIO index. The log strings confirm: "Privacy LED on GPIO
  index %d was turned %s by %s". Each LED is reference counted per sensor use, so it is on
  while at least one mapped sensor streams.
- Sensor index: the writer maps the sensor identifier it receives to an index: `0x5e34e1c5`
  gives 0, `0xf27170b8` gives 1, `0x65528936` gives 2. These are the first dwords of GUIDs that
  sit in `.rdata` of the sensor drivers: `0x5e34e1c5` is in `surfacecamrearsensor8380.sys`
  (`b7d7a278`, `0x14001b4e0`), `0xf27170b8` is in `surfacecamfrontsensor8380.sys` (`80a8e4a1`,
  `0x140016398`), and `0x65528936` is absent from both. Rear is index 0, front index 1.
  The IR driver (`surfacecamauxsensor8380.sys`) was not opened; index 2 is the IR by
  elimination (and `PCFG` orders the sensors rear, front, IR, with flash and face
  authentication only on the third).
- That a driver contains its identifier is Verified; that it sends that identifier as its
  LED sensor id is Inference (strong: no other use is plausible and the mapping matches the
  earlier survey that reached the same split, rear 105 and front/IR 225).

Consequence: the rear camera's indicator is GPIO105, not GPIO225. GPIO225 is the front and IR
indicator. The rear and the front cameras never share an LED.

## Q2. What powers the CSIPHY, and what feeds the pm8010 LDOs

**CSIPHY supplies: Verified. pm8010 parent supplies: Unknown.**

CSIPHY (`qccammipicsi_ext8380/C1MD.bin`, `C1PD.bin`): every CSIPHY component (0, 1, 2, 4)
votes the same four PMIC rails when it powers up and releases them when it powers down:

| Windows rail | Voltage | Linux regulator on Denali (`x1-microsoft-denali.dtsi`) |
|:--|:--|:--|
| `LDO1_C` | 1.2 V | `vreg_l1c_1p2` (pmic `c`, pm8550ve) |
| `LDO2_C` | 0.88 V | `vreg_l2c_0p8` (880000 uV in the DT) |
| `LDO3_J` | 0.88 V | `vreg_l3j_0p8` (880000 uV) |
| `LDO2_J` | 1.2 V | `vreg_l2j_1p2` (1256000 uV) |

Plus the usual `rail_mmcx`, `gcc_camera_xo_clk`, `gcc_camera_ahb_clk`, `cam_cc_gdsc_clk`,
`cam_cc_titan_top_gdsc`, `cam_cc_cpas_ahb_clk` at 80 MHz, and the `csiphyN` and `csiNphytimer`
clocks of that PHY (PHY clock 480 MHz, timer clock 400 MHz at the top p-state; the same for
all four PHYs).

- The C pair is what patch 0005 already uses (`vdd-csiphy-0p8-supply = <&vreg_l2c_0p8>`,
  `vdd-csiphy-1p2-supply = <&vreg_l1c_1p2>`): **confirmed**, no longer a convention-only guess.
- The J pair is also voted by Windows for every CSIPHY. The CAMSS binding has two CSIPHY
  supplies only. The J regulators are already on in the Denali DT (they feed the USB and PCIe
  PHYs), so omitting them is harmless in practice; whether the PHY needs them from the
  camera path is Unknown.
- The pm8010 identity: ACPI PMIC map entry index 12 at SPMI slave id `0x0C` is letter M, and
  `hamoa-pmics.dtsi` has `pm8010: pmic@c`. Verified (`dsdt.dsl` PMIC table, `hamoa-pmics.dtsi`).
- What feeds the pm8010 LDO inputs (`vdd-l1-l2`, `vdd-l3-l4`, `vdd-l5`, `vdd-l6`, `vdd-l7`):
  **Unknown.** The PEP resource data only votes the output rails; the supply tree is not in
  `qcpep8380.sys` strings, the INF, the ACPI tables or any camera data file. The reference
  board DT of a sibling SoC (`sm8550-mtp.dts`) feeds LDO1/2 from an SMPS, LDO3/4 from BOB2,
  LDO5/6 from an SMPS and LDO7 from BOB1, but that is a different board and stays a
  Hypothesis. Patch 0005 leaves the parents out, which the RPMh driver accepts.

## Q3. PEP delay unit

**Answer: milliseconds. Verified.**

`qcpep8380.sys` (sha `e5bdeb8c`): the `DELAY` resource handler `FUN_140128170` (the log string
`pDelayNode`, source `PEP_ResourceMgmt.c`) takes the node value and, when the device is
in D3 power-down transition at raised IRQL, calls `KeStallExecutionProcessor(value * 1000)`
(microseconds), after comparing a timer-based elapsed estimate with `value * 1000`. In the
normal path it waits through `KeDelayExecutionThread` with an interval built from the same
value by `FUN_1400336f8`. The stall argument is the value times 1000, so the stored number is
milliseconds. This matches the Qualcomm downstream convention in the earlier reference.

Consequence: all `DELAY` values in `CAMS_RES`, `CAMF_RES`, `CAMI_RES` are milliseconds. The
rear sequence is: 1 ms after the first three rails, MCLK and reset release, then **10 ms**
before the sensor is used. Patch 0002 `ov13858_power_on` already uses 1 ms and 10 ms. No
change.

## Q4. CCI controller and bus, and I2C speed, per sensor; 7-bit addresses

**Controller and bus: Verified in the Windows data, mapping to Linux nodes Inference (high).
Speed at probe: Verified. 7-bit addresses: Verified up to the 8-bit/7-bit convention, which is
Inference with strong support.**

`CAMP_PCFG_MSHW0495.bin` (decoded by the `PcfgBinaryPath` parser in `qccamplatform8380.sys`,
log strings "I2C master", "CSI PHY index", "flash index", "Face Authentication"):

| Sensor | I2C master index | CSI PHY index | Flash | Face authentication |
|:--|:--|:--|:--|:--|
| Rear (index 0) | 1 | 1 | none | no |
| Front (index 1) | 3 | 2 | none | no |
| IR (index 2) | 0 | 0 | present, index 0 | yes |

I2C master index to controller and bus: index = 2 x CCI + bus. Rear: CCI0 bus 1, front:
CCI1 bus 1, IR: CCI0 bus 0. Evidence for the mapping: the `CAMP_RES` TLMM list holds exactly
GPIO101 to 104 (CCI0, two buses) and 235, 236 (CCI1, one bus), the `CAMP` memory regions are
CCI0 and CCI1, and the pin groups `gpio235`/`gpio236` in `pinctrl-x1e80100.c` carry the function
**`aon_cci`**, not `cci_i2c`. In Linux terms: rear `cci0_i2c1` (GPIO103 SDA, GPIO104 SCL), IR
`cci0_i2c0` (GPIO101, GPIO102), front `cci1_i2c1` on GPIO235/236 with function **`aon_cci`**.

Per-sensor configuration (`SCFG_REAR/FRONT/AUX_*.bin`), parsed by `FUN_140001b48` in
`surfacecamfrontsensor8380.sys` (`80a8e4a1`): the first word carries a 16-bit slave address
(low half), a 2-bit I2C frequency code, a 2-bit register address type and a 2-bit register data
type; the second word the probe register and expected chip id. Results:

| | Rear | Front | IR |
|:--|:--|:--|:--|
| Slave address field | 0x20 | 0x20 | 0xC0 |
| 7-bit (field shifted right by one) | **0x10** | **0x10** | **0x60** |
| I2C frequency at probe | 400 kHz | 400 kHz | 400 kHz |
| Register address type | 16-bit | 16-bit | 16-bit |
| Probe | chip id register, expected id as in `rea-windows.md` | same | same |

The frequency decode is `FUN_140002000`: code 0 gives 100 kHz, code 1 gives 400 kHz, code 2
gives 1000 kHz; all three sensors use code 1, and the probe routine accepts the value into the
runtime frequency only if it is between 100 and 3396 (kHz). The Chromatix module data does not
carry a runtime I2C mode for any of the three (the `sensorI2CFrequencyMode` and
`i2cFrequencyMode` symbols are zero-sized), so the runtime speed is the probe speed:
400 kHz (Inference from absence).

The 8-bit convention is supported by the other devices on the same buses: the EEPROM entries
read 0xA0 (7-bit 0x50, the standard 24Cxx address) and the DW9800 actuator 0x18 (7-bit 0x0C),
and the rear 0x20 (7-bit 0x10) equals the address the Linux `ov13858` binding and ACPI path
use. Not 7-bit literal.

Patch impact: `cci0_i2c1` in patch 0003 has `clock-frequency = <1000000>` (lines 49 and 57,
the upstream-style default for Hamoa). Windows runs all three sensors at 400 kHz. Patch 0005
should override `clock-frequency = <400000>` on `&cci0_i2c1` (the rear bus), which is the
only timing proven to work on this board.

## Q5. IR sensor I2C address (binding text conflict)

**Answer: 7-bit 0x60 on CCI0 bus 0. Verified in the data, Inference only for "the binding does
not apply".**

The Windows field is 0xC0 (8-bit); the same convention gives 0x10 for the rear and front
sensors and 0x50 for the EEPROMs (Q4), so IR is 0x60. The VD55G1 binding text says the address
is fixed to 0x10 (`st,vd55g1.yaml`), which describes the VD55G1/G4 family; the Windows driver
configures the VD55G0 module at a different address, and its own probe (chip id word 0x3047 at
register 0) only passes at that address. Treat 0x10 as the family default and 0x60 as the
programmed address of this module. Whether the sensor strap or a boot command moves it is
Unknown; the address is still what the first probe must use.

Not Verified on hardware (there is no `i2cdetect`, by instruction).

## Q6. IMX681 Bayer order and modes; OV13858 PLL and mode set; VD55G0 mode

**IMX681 Bayer order: Unknown. Mode lists: Verified. OV13858 link rate: Verified.**

Modes come from the `resolutionData` and `streamConfiguration` records of
`com.surface.sensormodule.*.bin` (decoded with the earlier survey tool; the per-mode data rate is
derived from the module's pixel clock, bits per sample and lane count).

Rear OV13858 (three modes, D-PHY, 4 lanes, same PLL for all three):

| Mode | Output | Rate | Link |
|:--|:--|:--|:--|
| 0 | 4076 x 2806 RAW10 | 30 fps | 1185.6 Mbit/s per lane (592.8 MHz DDR clock) |
| 1 | 4064 x 2286 RAW10 | 30 fps | same |
| 2 | 3736 x 2802 RAW10 | 30 fps | same |

- The three Windows modes are crops of the 4224 x 3136 array. They differ from the Linux
  `ov13858.c` modes (4224 x 3136 at 1080 Mbit/s, three half and quarter modes at 540 Mbit/s).
  None of the Windows sizes exists in Linux.
- The Windows PLL differs from both Linux link configurations in two PLL1 control registers
  (the first and the third of the block); the remaining PLL1/PLL2 and MIPI control registers
  are the same as Linux. The three Windows modes have identical PLL registers.
- The Windows mode registers are Windows-derived data and cannot be committed (S5). The
  Linux path should keep its own modes (1080 and 540 Mbit/s, `link-frequencies` 540000000 and
  270000000 as in patch 0005); the CAMSS D-PHY tables cover both. The Windows 592.8 MHz
  link is therefore reference only. If a Windows-equivalent mode is wanted later, it is
  generated on the device into a local, uncommitted table.
- Flip bits: Windows writes a different value of the register that carries mirror/flip
  (0x3820) than Linux; the effect on the Bayer order is not established. The Linux driver
  reports only `SGRBG10_1X10`.

Front IMX681 (six modes, all C-PHY, 1 trio):

| Mode | Output | Rate | Symbol rate per trio |
|:--|:--|:--|:--|
| 0 | 3840 x 2640 RAW10 | 30 fps | 2.40 Gsym/s |
| 1 | 3840 x 2160 RAW10 | 60 fps | 2.40 Gsym/s |
| 2 | 3840 x 2160 RAW10 | 30 fps | 2.40 Gsym/s |
| 3 | 3520 x 2640 RAW10 | 30 fps | 2.40 Gsym/s |
| 4 | 3660 x 2440 RAW10 | 30 fps | 2.40 Gsym/s |
| 5 | 504 x 378 RAW10 | 3 fps | 2.87 Gsym/s |

(Symbol rate derived from pixel clock x bits per sample / lanes x 7/16.)

- Bayer order: the module data carries a colour-filter code (3 for IMX681, 0 for OV13858, 4 for
  the mono IR) but it is a numeric code of the CamX enumeration, which this session could not
  tie to a named order: `qccamisp8380.sys` has no pattern-name strings, the Qualcomm
  reference has no such enumeration, and two plausible orderings (the mm-camera order and the
  Android order) disagree for the IMX681 code (RGGB versus BGGR). The OV13858 code does not
  reproduce the Linux GRBG either. **Unknown**; resolve on the device by capturing one RAW
  frame of a coloured target and reading the Bayer order, or by the order of the AWB reference
  points in the tuning data (not conclusive, the earlier survey lists the channel order as
  assumed).
- Mode 5 (504 x 378 at 3 fps) is a low-power presence mode; ignore it for a first driver.

IR VD55G0: one mode, 644 x 604 RAW10 monochrome, 60 fps, D-PHY 1 lane, 840 Mbit/s
(420 MHz DDR clock).

## Q7. PMIC channel of the IR emitter (read only, S2 keeps it disabled)

**Verified (earlier REA of the same binaries; the entry points re-checked this session).**

- `CAMP_PCFG` marks only the IR sensor (index 2) as having a flash, flash index 0, CCI timer
  index 0, trigger type 0. The IR sensor is also the only one flagged for face authentication.
- `qccamflash8380.sys` (sha `6bc1d698`) exposes the white-LED driver API with "LED1" and "LED2"
  currents (`CameraWhiteLEDFlashPMIC_SetTargetCurrent with LED1 %d LED2 %d`, `..._Fire`),
  reads `IrLedCurrentMilliampere` from the INF (default 700 mA when absent, in
  `FUN_14002c760`) and sends the requests to the PMIC flash interface of `qcpmic8380.sys`.
- Earlier REA (`sources/windows/rea-evidence/camera-flash/`, the survey `rea/camera/flash/README.md`):
  the flash module belongs to the pm8550 at SPMI bus 0 slave 1 (Linux `pm8550` node in
  `hamoa-pmics.dtsi`, the `PMC8380C` of the comment), 4-channel type; Windows "LED1" (index 0)
  drives **channels 1 and 4 together**, splitting 700 mA between them (350 mA each); "LED2"
  (channels 2 and 3) is zero for the IR LED; flash mode with a hardware strobe, level
  triggered, active high; the sensor's own GPIO1 is the strobe source and no TLMM pin is
  configured for it. This session did not re-decompile the ganging handlers.
- S2: nothing in any patch describes this LED. Linux node, when someone clears S2:
  `&pm8550_flash` with `led-sources = <1>, <4>`, `flash-max-microamp = <700000>`. Do not add
  it now.

## Other findings from the ACPI and PEP data

- Lane map and sensor-to-CSIPHY mapping: rear CSIPHY 1 (D-PHY, 4 lanes, lane assignment
  0x3210, which is the identity), front CSIPHY 2 (C-PHY, 1 trio), IR CSIPHY 0 (D-PHY,
  1 lane). The Windows CSIPHY index equals the `PCFG` field: **Verified** (previously Inference).
- MIPI link rates: rear 1185.6 Mbit/s per lane, front 2.4 Gsym/s, IR 840 Mbit/s (Q6).
- ACPI: `CAMS`, `CAMF`, `CAMI` have no `_CRS`; I2C, lanes and power are in the data files.
  `CAMP` carries the CCI regions, three interrupts, and the two GPIOs of Q1. No `_DSD` or
  `CAMP`-side link frequency exists in the ACPI.
- Linux gaps found while mapping: Denali has no pm8550 `l7b` (front 2.8 V rail) and no `l16b`
  (rear actuator, 2.9 V). Needed only for the front camera and for autofocus.

## Patch review: exact lines that change

| Patch | Line | Change | Reason |
|:--|:--|:--|:--|
| `0005-...-rear.patch` | 132 `leds = <&camera_indicator>;` | point to a new GPIO105 LED node (rear indicator) | Q1: rear is GPIO105, active high; GPIO225 is front and IR |
| `0005-...-rear.patch` | 128-131 comment ("only camera indicator known is GPIO225") | replace with "rear indicator is GPIO105, front and IR use GPIO225" | Q1 |
| `0004-...-came.patch` | after line 57 (the GPIO225 LED) | add `camera_indicator_rear` with `gpios = <&tlmm 105 GPIO_ACTIVE_HIGH>` and its own pinctrl state (GPIO function) | Q1; the 0004 commit message "GPIO105 not established" becomes "established" |
| `0005-...-rear.patch` | `&cci0_i2c1` node (line 103) | add `clock-frequency = <400000>;` | Q4: Windows runs 400 kHz; 0003 sets 1 MHz at lines 49/57 |
| `0005-...-rear.patch` | lines 81-82 | no change | Q2: CSIPHY C-pair confirmed |
| `0005-...-rear.patch` | line 110 `reg = <0x10>` | no change | Q4/Q5 |
| `0005-...-rear.patch` | line 139 `link-frequencies` | no change (Linux modes, not Windows) | Q6 |
| `0005-...-rear.patch` | `regulators-8` block | no parent supplies; unchanged | Q2: parents Unknown |
| `0002-...-driver.patch` | `usleep_range(1000,...)` / `usleep_range(10000,...)` (lines 84, 109, 115) | no change | Q3: the delays are milliseconds |
| CSIPHY index 1, 4 lanes, `reset-gpios` 110 active low | none | already match | Verified now |

Front/IR facts for the next patches (not in the existing set): front pinctrl function on
GPIO235/236 is `aon_cci`; front sensor needs pm8550 `l7b` and pm8010 `ldo3`; IR is on
`cci0_i2c0`, address 0x60, CSIPHY 0.

## Still Unknown

- pm8010 LDO input supply tree.
- Whether the CSIPHY needs the J rail pair from the camera path.
- IMX681 Bayer order (code known, naming not).
- Whether VD55G0 is accepted by `vd55g1.c` (chip id 0x3047 differs from the S5G1/S5G3 ids).
- IR strobe wiring from the VD55G0 GPIO1 to the PMIC (not described by Windows).
- Hardware confirmation of everything above (needs the device; no `i2cdetect`).
