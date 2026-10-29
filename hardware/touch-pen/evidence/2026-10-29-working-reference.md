# Session 3: why the Arch reference works

This is source evidence and a software port, not a local device pass. Raw M5
logs remain private in `out/device-logs/m5-20261028/`; none was copied here.
The reference's touchscreen/pen success is an external report for this model.
The current unit's clocked SE protocol still requires the next boot. A
bounded text scan of both M5 boot folders found no touch-pen diagnostic,
`Invalid proto`, SE2 geni_spi or SPI-HID messages. Only match counts and
protocol numbers were examined for this conclusion; no raw lines were
exported. Those boots therefore supply no protocol0/9 observation.

## Reproducible reference identities

- [archiso-aarch64-sp11](https://github.com/dwhinham/archiso-aarch64-sp11),
  local HEAD `9a50ce3c81e4e17b30adcfc0dd517c19795e89f3`, README feature table:
  touch/pen working, requires iptsd. `configs/releng/profiledef.sh:17`
  uses `clk_ignore_unused pd_ignore_unused arm64.nopauth` and also masks
  `tpm2.target`. These arguments are context, not a substitute for QSPI code.
- [linux-sp11](https://github.com/dwhinham/linux-sp11),
  `v7.2.11-arch1-sp11`, HEAD `d6333a45f9bc9a1fa82a90146dbc9c159e83cd1b`.
  Relevant commits below are read from its history; patch bodies were fetched
  through immutable GitHub commit URLs to `out/agents/touch-ref/`. No git
  fetch/checkout/apply/commit or other write-capable git command was run.
- [x1e-nixos](https://git.scug.io/nikkuss/x1e-nixos),
  current tree `ca7db709ee29ecdd3c00fec679febdfb2ebfaa32`, original QSPI commit
  [`95f3f072da16549f69c7eaea398be37336c7922c`](https://git.scug.io/nikkuss/x1e-nixos/commit/95f3f072da16549f69c7eaea398be37336c7922c).
  Both original QSPI patches are unchanged in orvitpng's vendored copy.
- [nix1e](https://github.com/orvitpng/nix1e/tree/b274dd722fb1797a369ffab34a05b28cf0401a94),
  `b274dd722fb1797a369ffab34a05b28cf0401a94`, Carter Davis/orvitpng.
  `modules/spi-hid/default.nix` selects v4 plus `fullduplex.patch`;
  `vendor/x1e-nixos/kernel/modules/qcom-qspi/` contains the original host/GPI
  patches. Its SL7 board policy is not interchangeable with Denali's.

## Complete touch-related reference delta

Grade **Verified source** for every row; these are implementation facts,
not a claim that we sampled this unit's registers.

| Commit in linux-sp11 | Paths / necessary behavior | Disposition on v7.3 |
|:--|:--|:--|
| `5890c85bcb801ed4ba75697664d6152511f9638e` through `a979e697f2781a502cbee6a079d7d9a32cedd3e3` | `Documentation/hid/hid-transport.rst`, `include/linux/hid.h`, `drivers/hid/{Kconfig,Makefile,hid-core.c,spi-hid/**}`, `Documentation/devicetree/bindings/input/hid-over-spi.yaml`: Jingyuan Liang's v5 SPI-HID baseline | Use the newer posted v7, already exported under `patches/v7/`; its 11 Message-IDs and hashes are in the v7 evidence |
| `c002193d3f45311b9a0ac3cf065cf8f1ddb866ef`, `d823f45e2474296000aaa523a43006af3ebaf2c5` | `spi-hid-core.c`: reset assertion error propagation and resume reset handshake | v7 already contains the corresponding corrected behavior; do not apply these v5 fixes again |
| [`7ec26d21fff8dbb6de65a143c79159b5397c9bc2`](https://github.com/dwhinham/linux-sp11/commit/7ec26d21fff8dbb6de65a143c79159b5397c9bc2) | `drivers/spi/spi-geni-qcom.c`: protocol 9, four IO mux lanes, GPI-only mode, SE_DMA settling before GPI, per-message IRQ/DMA restoration, command 7, explicit RX length, RX-channel completion, 20 MHz cap | Port in 0018; bind through v7.3's existing resource callback data; return `-EINVAL` on unexpected protocol instead of the reference's stale successful `ret` |
| [`990b7a0453e2836126b9f31d036e87d6474456f0`](https://github.com/dwhinham/linux-sp11/commit/990b7a0453e2836126b9f31d036e87d6474456f0) | `drivers/dma/qcom/gpi.c`, `include/linux/dma/qcom-gpi-dma.h`, `include/dt-bindings/dma/qcom-gpi.h`: QSPI binding selector 4 becomes hardware protocol 9 in channel scratch; QSPI CONFIG0/GO/DMA TRE encoding; TX command truncation; RX IEOT completion | Ports 0016/0017; distinguish the enum name `QSPI_TX_RX` from v7.3's existing local SPI_TX_RX macro, both numeric 7 |
| [`1a10ba716fb528a92523406aac461a7af9bbf285`](https://github.com/dwhinham/linux-sp11/commit/1a10ba716fb528a92523406aac461a7af9bbf285) | `spi-hid-core.{c,h}`: one combined TX/RX transfer for a read; separate DMA-safe TX allocation | Port in 0019, restricted to MSHW0484; retain normal two-transfer reads for other v7 devices |
| [`87e5399ae755c858d7d9c577a85fcb48aaeac510`](https://github.com/dwhinham/linux-sp11/commit/87e5399ae755c858d7d9c577a85fcb48aaeac510) | `spi-hid-of.c`: device-specific SPI ID, needed for module autoload | Already handled by v7's per-compatible SPI match data; add matching `mshw0484` OF/SPI entries in 0019 |
| [`d7e99026f785b61d7ddbf6eebc7426e2d3a13c41`](https://github.com/dwhinham/linux-sp11/commit/d7e99026f785b61d7ddbf6eebc7426e2d3a13c41) | `spi-hid-core.c`, `spi-hid-of.c`, `spi-hid.h`: recreate HID after reset even if descriptor CRC is unchanged, reconnecting iptsd so it restores heatmap mode; based on Jizhou Tong's Romulus13 RFC | Port in 0019 with v7's locking/handshake and MSHW0484-only match data |
| [`091886ac74061683ed47c2c054a4fbe2047cdde0`](https://github.com/dwhinham/linux-sp11/commit/091886ac74061683ed47c2c054a4fbe2047cdde0) | `arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi`: enable QUP1 SE2/GPI1, add extra mux pins, touch child, IRQ/reset/power | Separate patch 0020, confined to LCD board; v7-compatible properties and cross-checked timings |

The original Nikkuss host and GPI patch SHA-256 values are respectively
`62b8d61a0ca93d2610c29be97103d7589aa82ed73805fd8062606b0dbcc09c3e`
and `9096f07956d45fa8ec8d43b0659b2af38a25c0f30bad56705d9de67da5ee6c0d`.
The orvitpng full-duplex patch hash is
`76c333872591b07c1ae40f555139060c42f119876bf06bc6aaa703a8e68105b2`.
They match the research inputs recorded in session 1: that lead was real;
our earlier sessions did not implement it.

### qcom-geni-se: no missing downstream firmware-loader patch

The working reference does **not** alter `drivers/soc/qcom/qcom-geni-se.c`
for touch. The latest commit affecting it in that branch is upstream
`220cea6c1662b9049d1af752fdac21939d2a6a94` (RAM-depth validation).
Comparing its final file against pinned v7.3 shows only v7.3's additional
GENI register tracepoint include/export near the top. Loader and resource
logic otherwise match. There is consequently no QSPI loader change to port.

The QSPI host restores the appropriate IRQ/events after the existing
resource activation. The reference comment blames `geni_se_resources_on()`
for IRQ writes, but that helper only enables clocks/pinctrl; generic SE
initialization/mode selection actually writes those registers. The port
corrects that comment while retaining the reference's per-message setup. It consumes a programmed personality instead of calling
`geni_load_se_firmware()` for QSPI. The ordinary SPI branch still has its
existing protocol-255 loading behavior. No broadened zero-protocol loader,
I2C/UART change, or new qcom-geni-se protocol table is necessary for reference
parity. Source baseline: `sources/linux/drivers/spi/spi-geni-qcom.c:627–658`,
`sources/linux/drivers/soc/qcom/qcom-geni-se.c:1553–1601`.

## Protocol and dummy-clock resolution

**Verified source contract:** the original Nikkuss patch and Dale's working
SP11 port both require **SE protocol 9**. **4** is the new DT/GPI client selector,
not the SE hardware protocol. GPI explicitly translates 4 to 9 in scratch.
This settles what our port must accept; actual register observation on this
unit remains **TBD**, to be captured by the retained normal-probe diagnostic.
Zero will now produce a clear failed QSPI probe, with no speculative upload.

**Verified specification and implementation:** eight placeholder **clocks**
follow the three-byte quad address. This equals four quad bytes if implemented
as a manual dummy data phase. The reference instead programs `dummy_clk_cnt=8`
in CONFIG0, submits only the four opcode/address bytes on TX, and receives
exactly the report length on RX. Its transport's in-memory fifth approval byte
is not clocked onto the bus. Our quirk copies only the four command bytes.

Thus the earlier dossier's eight-clock requirement was correct, but the claim
that the reference necessarily needs a four-byte userspace/transport dummy
buffer was too strong. Hardware generates these clocks in this implementation.
The posted spi-mem RFC remains a possible upstream design, not a prerequisite
for reproducing this working downstream contract. This port retains the
reference's fixed eb-command recognition and 1-4-4 behavior, not a generic
spi-mem implementation or support for arbitrary multi-lane devices.

## Firmware: no DriverStore payload or manifest addition

**Verified source:** no `firmware-name` property is added by the reference DT
on SE2 or QUP1, and its QSPI probe never requests a firmware file. It requires
protocol 9 to be present before that branch runs. Therefore the required Linux
firmware **filename is none**, file **source is none in these projects**, and
Linux performs **no QSPI microcode load**. **Inference:** platform boot firmware
initializes the SE before Linux. The exact UEFI component and payload version
have not been traced. Neither source inspection nor a successful external boot
proves which platform component originally wrote IRAM.

Fedora's `qcom-firmware` / linux-firmware `qcom/x1e80100/qupv3fw.elf`
(decompressed SHA-256
`dcb4ca490098f081dd3f85d91ca230c4755d376a4cdca51e6a4ba918fa4ab077`)
has protocols `{1,2,3,4,5,6,8,260}` and **no 9**. This agrees exactly with the
Claude cross-check. It is not a touch dependency for this port. Do not alias
its protocol-1 segment to QSPI or add a touch-specific manifest destination.

The catalogued `qcspi8380/BSRC_QSPI.bin` and board extension
`surface_spiext_den8380/BSRC_QSPI_DEN.bin` are structured power/clock/pin policy
**data**, not executable sequencer firmware. They were never disassembled.
No DriverStore file is requested by this series. **Firmware request:** no
new firmware row, extraction, copy, conversion or device firmware write.
Retain generic QUP firmware only for independent consumers that need it.

### REA method and limits

The registered MCP has no language parameter and its configured environment
contains Ghidra/JDK paths but no `REA_GHIDRA_LANGUAGE_ID`. Use of that server
could not satisfy protocol §9. The allowed **CLI fallback** was used instead,
under `flock out/.ghidra.lock`, explicitly setting
`REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`, `GHIDRA_MAXMEM=4G` and the configured
Ghidra 12.1.4 / JDK paths. Catalog lookup preceded analysis of
`DriverStore/qcspi8380.inf_arm64_14b48dd9d115a472/qcspi8380.sys`, SHA-256
`34cabf2e7b59d3f8c0608da80dfdc705173c82427611312d32e7c1a9720e33ec`.

- Enumerated 373 procedure entries (including externals) first:
  `ev_b360b80cadf82abad9359ca076138fa23d50383e9ed267fa3c85d560fcb4f366`.
- String search confirms QSPI at `0x14001fda0` and QSPIBinaryPath at
  `0x14001fdc8`: `ev_7af13ccbed98accd77bc2280f096d4fbbe9654ee218d566abe3ea6caf5d31fdf`.
- The previously failed `0x140023790` now decompiles:
  `ev_0149b55f7fa82bad20006b58cd3beb0fb1fa896e8b448ac202252f01ba83be01`.
  It is WPP logging initialization, not proof of a microcode loader.

Snapshots and raw results stay in `out/agents/touch-ref/`. No pseudocode or
proprietary bytes enter this dossier. These results do not independently
establish Windows' numeric QSPI compare; the protocol-9 conclusion above is
explicitly the working downstream implementation contract. Procedure `0x14000f710` was re-decompiled successfully with the same
`ev_f2d5eb353ee07b62e1c1437732b84b054a66fe5e04aa1bc2f85987a8a150b2fd`
identity, reproducing `_STR` parsing and QSPI policy selection. The earlier
`0x14000fa70` registry-selection evidence remains recorded in session 2.

## Comparison with our dossier and Claude

| Item | Earlier dossier / Claude | Working reference | This port and grade |
|:--|:--|:--|:--|
| SE mapping | Agree on QUP1 SE2, `0xa88000`, GIC SPI 802, `spi10`, GPI1 SEID2 | Same | Same; Verified mapping |
| Numeric protocol | Dossier: downstream 9, actual unit TBD. Claude: numeric TBD | Host requires 9; GPI selector 4 translates to 9 | Static contract settled at 9; actual unit still TBD |
| Firmware | Both verified Fedora has no 9; payload suitability unresolved | No requested file; accepts preloaded 9 only | No touch firmware load; initial platform loader remains Inference |
| Bus pins | Both reproduce 40–43 mux1, 49/50 mux2 | Same, plus 6 mA / no bias on extra pins | Select verified mux only on 49/50; do not guess electrical fields |
| IRQ / reset / enable | Agree: 51 falling/no bias, 48 active-low, 64 active-high | Same in SP11; SL7 nix1e instead uses level-low/pull-up and 16 mA reset | Use cross-checked SP11 resources and 2 mA reset from direct TLMM decode; no SL7 electrical transplant |
| Reset / power | Both reproduce 300 ms reset, cold `_PS0` 500 ms, shutdown gap 10 ms | SP11 DT has 10 ms startup and generic v5 100 ms reset; SL7 DT has 1 s startup | Preserve cross-checked 500/300/10 ms in 0019/0020 rather than copying either shortcut |
| Addresses / opcodes | Agree on 1000/1004/2000 and eb/e2 | Same, supplied by v5 DT properties | v7 per-compatible MSHW0484 data; generic v7 G6 0b/02 remains unchanged |
| `_DSM` revision | Claude proves 3; revision 2 unsupported by SSDT | v5 ACPI frontend already requests 3 | v7 also requests 3; no extra ACPI revision patch, DT path uses match data |
| Dummy phase | Dossier says eight clocks/four quad bytes; Claude TBD | CONFIG0 emits eight clocks; TX length is four command bytes | Same eight clocks; no manual quad dummy buffer needed |
| Userspace/reset | Not integrated | iptsd plus heatmap rebind after reset | Native RPM request plus device-scoped rebind port |
| Second IRQ / wake | Both unresolved | SP11 DT omits it | Omitted; no wake promise or guessed GPIO1088 |

The existing Claude cross-check supplies the board-value gate for the port.
The orchestrator still needs an independent review/cross-check of the newly
imported QSPI register/TRE constants and the v7 reset-rebind adaptation before
integration. External success is not local electrical or device acceptance.
