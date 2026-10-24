# GENI protocol 0 and disabled DT draft

All Linux source citations refer to immutable `sources/linux/`, tag `v7.3`,
commit `c03c1a14507dfaf8b856c2608f9ac216021fc222`. This is static analysis;
the engine's actual state on the Surface remains **TBD**.

## Protocol dispatch

**Verified:** `GENI_SE_NONE=0`, `GENI_SE_SPI=1`, and
`GENI_SE_INVALID_PROTO=255` are distinct enum values
(`sources/linux/include/linux/soc/qcom/geni-se.h:33`).
`geni_se_read_proto()` reads the protocol field, bits 15:8 of
`GENI_FW_REVISION_RO`, without normalizing zero to 255
(`sources/linux/include/linux/soc/qcom/geni-se.h:180`, :369).

**Verified:** `spi_geni_init()` resumes the device, reads the protocol, and
branches as follows (`sources/linux/drivers/spi/spi-geni-qcom.c:627`):

| State | v7.3 host-mode behavior |
|:--|:--|
| 1 (SPI) | Continue initialization without requesting firmware |
| 255 (INVALID) | Call `geni_load_se_firmware(se, GENI_SE_SPI)` |
| 0 (NONE) | Log `Invalid proto 0`, return `-EINVAL`, do not request firmware |
| Other protocol | Log invalid protocol and return `-EINVAL` |

SPI-target mode accepts only `GENI_SE_SPI_SLAVE` (5) and does not use this
host firmware-load branch. GPIO reset of the touch controller does not
change the GENI host's protocol dispatch.

**Inference:** if this Surface reports zero, merely installing a firmware file
or adding a firmware-name DT property cannot repair the probe failure.
A narrowly scoped future change could include `GENI_SE_NONE` in the load
condition, while continuing to reject engines programmed for another protocol.
No such change was made this session; zero may also signal inaccessible or
incorrectly powered MMIO. A device log and clock/resource checks are needed
before treating it as proven empty firmware.

I2C and UART have the same invalid-255-only loading gate
(`sources/linux/drivers/i2c/busses/i2c-qcom-geni.c:1083`,
`sources/linux/drivers/tty/serial/qcom_geni_serial.c:1359`). This is a shared
SoC/kernel-owner issue, not a transport-driver fix.

## Firmware loading requirements and limits

**Verified:** `geni_load_se_firmware()` reads `firmware-name` from the
**wrapper** device, not the SPI child. It defaults to FIFO, switches to GPI
DMA only if the SE has `qcom,enable-gsi-dma`, requests that exact firmware
path, converts `-ENOENT` to `-EPROBE_DEFER`, and loads the requested protocol
(`sources/linux/drivers/soc/qcom/qcom-geni-se.c:1553`).

**Verified:** the parser selects a segment with matching serial protocol
(`sources/linux/drivers/soc/qcom/qcom-geni-se.c:1298`); the loader programs
configuration and IRAM, and writes the protocol revision
(`sources/linux/drivers/soc/qcom/qcom-geni-se.c:1428`, :1510–1514).
This is engine firmware loading, not evidence of touch-controller firmware
flashing. No loader or device operation was executed in this session.

**Verified:** `qupv3_1` has no firmware-name in `hamoa.dtsi:1492`, and Denali
only enables it in
`sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1030`.

**Hypothesis:** `qcom/x1e80100/qupv3fw.elf` may supply ordinary SPI engine
firmware once protocol dispatch and platform authorization are understood.
Neither that filename nor any particular image is hardcoded in the loader.
The firmware owner must identify/pin a compatible image and verify its
protocol segments; presence of a file alone is insufficient. No firmware
property is added to the draft. Whether a distinct QSPI personality is
needed for QCOM0C0E is **TBD**.

## Quad mode is a separate blocker

**Inference:** the captured `_DSM(3,6)=0xa000` requires quad reads/writes
with a single-lane opcode; see the pinned inputs and specification decode
in [ACPI evidence](2026-10-24-acpi.md).

**Verified:** v7.3 `spi-geni-qcom` advertises only CPOL, CPHA, LOOP and
CS_HIGH, no RX_QUAD/TX_QUAD
(`sources/linux/drivers/spi/spi-geni-qcom.c:1113`). The SPI core warns and
**clears** unsupported multi-lane mode bits in
`sources/linux/drivers/spi/spi.c:4326`; it does not make this controller quad
capable merely because the DT requests four lanes.

**Verified (posted v6 code):** patch 07's ACPI reader explicitly omits the
multi-SPI flags; patch 09's OF code also documents multi-SPI as unsupported.
The final `drivers/hid/spi-hid/spi-hid-core.c:193` transmits the opcode,
address and approval byte together without setting transfer lane counts,
then reads the response. Its output path uses `spi_write()` at :225.
These files are in `out/linux/touch-pen`, not immutable `sources/linux`;
their exact upstream blob IDs are recorded in the series evidence.

**Inference:** the unchanged series is useful as a buildable starting point,
but cannot implement the captured board protocol. Fixing protocol 0 alone
cannot solve missing quad controller support, pinmux, or split-width transfers.

## DT draft and provenance

`../touch-pen-draft.dtsi` and `../patches/0012-denali-touch-draft.patch`
describe a **disabled, incomplete software draft**. The latter modifies only
the LCD board DTS in the worker kernel tree. Every numeric hardware value
comes from [ACPI evidence](2026-10-24-acpi.md), with the grades below.

| DT item | Grade and basis |
|:--|:--|
| `&spi10`, `reg=0`, 40 MHz, mode 0/default active-low CS | Inference from SP11/GTCH resources and the matching MMIO node |
| `spi-rx-bus-width=4`, `spi-tx-bus-width=4` | Inference from flags `0xa000` and specification p.16; unsupported by the current stack |
| IRQ TLMM 51 / falling edge / no pull | Inference translating the first GpioInt |
| Reset TLMM 48 / active low / GPIO / no pull | Inference from GI48 address arithmetic, `_RST` and RCFG |
| Supply enable TLMM 64 / active high / GPIO / no pull | Inference from GI64 arithmetic and `_PS0` VCFG; `_CRS` declares a pull-down in its GpioIo descriptor |
| Regulator startup 500000 us | Inference converting the conditional 500 ms `_PS0` cold-start wait; regulator use is a modeling choice |
| Header/body/output `0x1000/0x1004/0x2000`; opcodes `/bits/ 8 <0xeb>/<0xe2>` | Verified raw values; semantic translation follows specification and v6 ACPI reader |
| `microsoft,g6-touch-digitizer`, `hid-over-spi` | Inference selecting the device-specific compatible allowed by v6 patch 08 |
| No microvolts or parent supply | TBD; a GPIO-controlled fixed regulator can be described without inventing voltage |
| No wakeup-source, second IRQ or panel link | TBD wake-resource mapping and panel policy; no wiring is guessed |

**Verified:** v7.3 fixed-regulator binding requires compatible and regulator-name,
but not a voltage (`sources/linux/Documentation/devicetree/bindings/regulator/fixed-regulator.yaml:117`).
It accepts startup-delay-us (:89); the driver reads it at
`sources/linux/drivers/regulator/fixed.c:194`. This describes a switched
supply abstraction; it does not identify the physical power rail.

**Verified:** upstream OF defaults are 10 ms after enabling power and 100 ms
minimum reset (v6 `spi-hid-of.c:53`). Match data is looked up in a table that
only contains `hid-over-spi`; therefore the device-specific compatible falls
back to the same timing. The schema does not expose arbitrary timing properties.

**Inference:** regulator startup-delay-us can account for a cold-power wait,
with the generic driver's 10 ms added afterward. It cannot enforce the 300 ms
standalone reset pulse or the `_PS3` 10 ms reset-before-power-off delay.
Add a separate, cross-checked device timing/sequencing change before enabling.
Preserve the upstream series unchanged as the baseline for that future patch.

Stock pinctrl for spi10 covers GPIO43 CS and GPIO40/41/42 MISO/MOSI/CLK
(`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:6458`); the board's quad
data pins are **TBD**. No extra pins are invented. A panel follower may be
considered after wake policy is resolved; v6 logs that wakeup and following
the panel conflict (`spi-hid-core.c:1599` in the worker tree).

## Concrete QSPI follow-up lead (not applied)

**Verified report, not local device evidence:** in a
[2026-09-19 upstream-thread reply](https://www.mail-archive.com/linux-trace-kernel@vger.kernel.org/msg29212.html),
Dale Whinham reports SP11 touch/pen working with v4 **plus** extra GENI QSPI
code and Denali DT changes, and points to
[orvitpng/nix1e](https://github.com/orvitpng/nix1e). This corroborates the need
for controller glue; it is not a claim that the unchanged transport worked alone.

The following primary-source files were retrieved read-only via GitHub blob
IDs and retained under `out/build/touch-pen/nix1e-research/`, outside git.
They are research leads, not centrally pinned project inputs or tested backports.

| External path in `orvitpng/nix1e` | Git blob | SHA-256 |
|:--|:--|:--|
| `modules/spi-hid/default.nix` | `c50563db143fad95ad6c1c5cae8756c8de8343fb` | `d1c4f9914713db360707fd632e1cdd2c5392f56b24d1a7e6c76c9a5668502918` |
| `modules/spi-hid/fullduplex.patch` | `c4bff2be6e3bf3df6d446d5785fec80b646d19ee` | `76c333872591b07c1ae40f555139060c42f119876bf06bc6aaa703a8e68105b2` |
| `devicetree/hardware/qspi.dtsi` | `ad87ab2c6aed21ea56706702f9eba5f370b707e5` | `f1bc460f944a584e250b53771332bcfd756c526f606d93419951d363b279f88a` |
| `vendor/x1e-nixos/kernel/modules/qcom-qspi/spi-geni-qcom.patch` | `efa6a94eeeafeb40ee4302a83b5cc9dc50abc015` | `62b8d61a0ca93d2610c29be97103d7589aa82ed73805fd8062606b0dbcc09c3e` |
| `vendor/x1e-nixos/kernel/modules/qcom-qspi/gpi.patch` | `1826f5081ef5e5d26d9d2f3e715dd20434a3b211` | `9096f07956d45fa8ec8d43b0659b2af38a25c0f30bad56705d9de67da5ee6c0d` |

**Verified source facts:** default.nix:10–14 selects v4 plus fullduplex.patch.
That patch's first hunk changes `spi_hid_input_sync()` from separate approval
and read transfers to one TX/RX transfer, so it is an additional transport
change. The controller patch defines QSPI protocol **9** at patch line 17,
rejects other protocol values in its QSPI branch at lines 241–252, enables
quad mode bits at lines 330–332, and requires a corresponding GPI path. It
does not demonstrate that ordinary `GENI_SE_SPI` firmware is the right choice.
In the pinned base, the loader's protocol-name table has only entries 0–5
(`sources/linux/drivers/soc/qcom/qcom-geni-se.c:125`) and rejects a requested
protocol outside that range at :1560. Adding protocol 9 would therefore need
more than changing the SPI driver's zero-protocol gate; this says nothing
about which firmware image is actually available for this unit.

**Verified source / Hypothesis for this board:** qspi.dtsi:3–11 proposes
GPIO49/50 as spi10's additional data pins and a downstream
`qcom,geni-spi-qspi` compatible at :22. Linux independently lists GPIO49/50
among allowed `qup1_se2` mux pins
(`sources/linux/drivers/pinctrl/qcom/pinctrl-x1e80100.c:1198`). This is a
candidate, not proof of this unit's wiring; these pins were not added to the
draft. Protocol 9 on this unit, the code's provenance/sign-off chain and its
compatibility with v6/v7.3 remain **TBD**. The next software step should assess
these glue changes and GPI support before proposing a generic protocol-0 load fix.
