# Session 2: GENI QSPI, firmware and sequencing

Static investigation only. The operator reports that the current image boots
GNOME Wayland on the LCD with kernel `7.3.0-65.sp11.3`; it has display patches
0001–0003, no spi-hid integration, and disabled touch DT. This report is not
evidence of a successful or failed SPI-HID probe. No hardware access, firmware
load, write-capable git command, commit or kernel-worktree edit was performed.

## Q1: same serial engine, different personality

**Verified:** SP11's ACPI description is `QUP_1_SE_2,QSPI`; its register range
is `0x00a88000/0x4000` and it depends on QGP1. See
`sources/windows/live-inventory/acpi/dsdt.dsl:51534–51561`, SHA-256
`8a7b849b9ac2148a9806d967612eb0d5195020c3e29ffd834b837767256a8ede`
(catalog row 1497). The matching Linux SE is `spi10`, with wrapper-1 SE2
clock and GPI instance 1 / SEID 2
(`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:1689–1722`).

**Inference:** this is a GENI/QUPv3 SE running a QSPI personality, rather than
the separate controller implemented by `spi-qcom-qspi.c`. The dedicated QSPI
driver has a different register map, `iface`/`core` clocks, and the
`qcom,qspi-v1` binding (`sources/linux/drivers/spi/spi-qcom-qspi.c:20–47`,
`sources/linux/Documentation/devicetree/bindings/spi/qcom,spi-qcom-qspi.yaml:18–46`).
Its X1E80100 mux functions use GPIO127–133; SP11's policy uses GPIO40–43/49–50
(`sources/linux/drivers/pinctrl/qcom/pinctrl-x1e80100.c:1130–1156`, :1694–1700).
Do not bind the standalone QSPI driver to `0xa88000`.

It is also premature to call this ordinary protocol-1 SPI with extra mode
bits. The locally retained downstream GENI/GPI implementation requires SE
protocol **9**. That is a **Verified downstream implementation fact**, not a
register observation on this unit. Its hashes and blob IDs are in the
[earlier evidence](2026-10-24-geni-and-dt.md#concrete-qspi-follow-up-lead-not-applied).

### Upstream check, 2026-10-28

**Verified source snapshot:** linux-next master resolved to commit
`6d0933ae9d46674a6ea63a87e9e9ab4e662670c9` (next-20261028). Files were fetched
from kernel.googlesource.com into memory; nothing was added to `sources/`.

| File in that commit | Bytes | SHA-256 | Result |
|:--|--:|:--|:--|
| `drivers/spi/spi-geni-qcom.c` | 37699 | `5ea2354f2efd520f16c3aceeae1b1225fedeeb622ea84060756e7ef65722bda4` | line 1186 advertises CPOL/CPHA/LOOP/CS_HIGH only; no DUAL/QUAD or tx/rx_nbits handling |
| `include/linux/soc/qcom/geni-se.h` | 18184 | `6aab274a8a269605887d426b71022ad018d5b9439f4e5fdfc980041a457c322d` | no QSPI protocol enum; SPI/I2C/UART etc. remain 1–5 |

Reproduce using the immutable
[linux-next SPI source](https://kernel.googlesource.com/pub/scm/linux/kernel/git/next/linux-next/+/6d0933ae9d46674a6ea63a87e9e9ab4e662670c9/drivers/spi/spi-geni-qcom.c?format=TEXT)
and [GENI header](https://kernel.googlesource.com/pub/scm/linux/kernel/git/next/linux-next/+/6d0933ae9d46674a6ea63a87e9e9ab4e662670c9/include/linux/soc/qcom/geni-se.h?format=TEXT)
(base64 payloads). Next still uses the invalid-255-only firmware gate at
SPI source line 653. The live Torvalds SPI source also lacks multi-lane support.

**Bounded negative search:** lore's linux-spi queries returned HTTP 403.
Patchwork kernel.org API v1.2 `patches/?q=geni%20quad&per_page=100` returned
`[]`; `geni QSPI` returned 14 duplicated 2021 memory-leak patches for the
*other* `spi-qcom-qspi` driver; `GENI_SE_QSPI` returned `[]`. `geni dual`
returned unrelated Geniezone/Mediatek subjects. Web searches for
`"spi-geni-qcom" "quad"`, `"QSPI" "spi-geni"`, and
`"GENI_SE_QSPI"` found no posted GENI multi-lane series.

**Conclusion / Inference:** no merged support in the inspected current next,
and no posted dual/quad GENI series found. Consequently there is no evidenced
upstream list of SoCs with that support to backport. Downstream X1E experiments
and the reported SP11/SL7 results are separate from an upstream series. This
search does not prove that no unindexed posting exists. Recent SA8255p GENI
SPI resource/trace changes are not evidence of dual/quad transfers.

A follow-up search found the October 10 **SPI-HID transport** spi-mem quad
RFC and the newer October 24 v7 transport baseline. The RFC cover explicitly
keeps GENI/GPI QSPI dependencies downstream, outside that series; it is not
a counterexample to the controller result above. The new baseline, source
hashes and transport lead are in [the v7 assessment](2026-10-28-spi-hid-v7.md).
Current `patches/series` selects unchanged v7; v6 stays archived. The local
RFCs and DT were rebased onto v7 without changing the kernel checkout.

### Pinmux: ACPI description plus Windows policy

**Verified absence within the captured ASL:** SP11's `_CRS` contains MMIO and
IRQ only. GTCH's `_CRS` contains SPI framing and GPIO51/64/0x0440, not the
bus pinmux (`dsdt.dsl:51547–51561`; `ssdt.dsl:1564–1592`, SHA-256
`95ee103a7ad5d9b55cc84ff09065171d638b6de9d1aafcde6efc69ce6a824f1b`).
The ASL therefore does not directly answer which extra data pins Windows uses.

The `qcspi8380` BSRC files **do** answer the policy question. Catalog rows
618/619 identify them as **data**, with no Ghidra language. They were decoded
as ACPI_EVAL_OUTPUT_BUFFER / packed ACPI_METHOD_ARGUMENT records, never code.
The [reproducer](../tools/decode-bsrc.py) checks the catalog hashes, entire
file sizes, all package/argument bounds, 24 root records in each file, and
exactly one `DEVICE / \\_SB.SP11` policy. It prints only that policy's GPIOs.

| Input under `sources/windows/DriverStore/qcspi8380.inf_arm64_14b48dd9d115a472/` | SHA-256 |
|:--|:--|
| `BSRC_QSPI.bin` (55788 bytes) | `b06b6f0a26652f1187bc12e347c53e8a51ef25c47b82cd403c9b73f64e48d11a` |
| `BSRC_SPI.bin` (53556 bytes) | `4ce2d0fba6560f544198bfb5de4c3c33ae9d8527a66e5468379a161524926443` |

**Verified raw records** (offset of the containing TLMMGPIO package):

| File / SP11 state | Offset | Tuple |
|:--|:--|:--|
| QSPI / DSTATE 0 | `0x5d32` | `[49, 1, 2, 0, 1, 1]` |
| QSPI / DSTATE 0 | `0x5d8f` | `[50, 1, 2, 1, 1, 1]` |
| QSPI / DSTATE 0 | `0x5dec`, `0x5e49`, `0x5ea6`, `0x5f03` | pins 40, 41, 42, 43, respectively; third field 1 |
| QSPI / DSTATE 3 | `0x6217` | `[49, 0, 2, 1, 1, 0]` |
| QSPI / DSTATE 3 | `0x6274` | `[50, 0, 2, 0, 1, 0]` |
| ordinary SPI / DSTATE 0 | `0x5a4a`–`0x5b61` | pins 40–43 only; no 49/50 |

**Verified Linux mapping:** the SE2 function group lists 40–43,49,50,51
(`sources/linux/drivers/pinctrl/qcom/pinctrl-x1e80100.c:1198`). PINGROUP puts
GPIO at selector 0, f1 at 1, f2 at 2 (:14–32); pins 40–43 have `qup1_se2`
at f1 (:1607–1610), pins 49/50 at f2 (:1616–1617). GPIO51's SE2 alternative
is also f2, but this board uses it as the touch IRQ: do not mux it to SE2.

**Strong Inference:** GPIO49/50 are the additional SE2 data pins for this
board, selected with `qup1_se2` / mux2. Which of these is IO2 versus IO3,
and all remaining tuple fields' electrical meanings, are not independently
decoded. Do not translate their last fields into pull/drive settings by guess.
The revised disabled draft adds the mux group only; electrical settings and
the entire device remain held for the Claude cross-check. The stock group's
6 mA setting is not evidence that 6 mA is correct for these two extra pins.

### Single-lane disposition and read-approval detail

**Verified raw:** GTCH `_DSM(3,6)` returns `0xa000` (`ssdt.dsl:1656–1659`).
**Inference using the Microsoft specification:** bits 15:14 select quad,
bit 13 also selects multi-lane writes. Both reads and writes therefore need
one-lane opcodes followed by four-lane address/data. FourWireMode means a
non-three-wire bus; it does not override these flags.

The public [HID-over-SPI 1.0 specification](https://download.microsoft.com/download/c/a/0/ca07aef3-3e10-4022-b1e9-c98cea99465d/HidSpiProtocolSpec.pdf),
SHA-256 `b1e7080c880c6328dcd102c52115bfe9fe9bb21353c64214f64496bb9c73f87b`,
§4.1 p.12 and §5.2.2 p.16 establish the widths. **Additional Verified
specification fact:** §7.1.2 p.23 requires **eight placeholder clocks** after
the three-byte read address: one byte in single mode, two in dual, four in
quad. Unchanged v6 allocates five-byte approvals and writes only one `0xff`
(`out/linux/touch-pen/drivers/hid/spi-hid/spi-hid-core.h:16`, core.c:129–138).
Its final source hashes are pinned in the earlier evidence. Merely setting
`rx_nbits=4` without widening the approval would still be wrong.

**Disposition:** ordinary single-lane transfers cannot implement the captured
contract. There is no evidence that this controller accepts alternate
single-lane opcodes or negotiates a fallback. This is not proof that every
undocumented single-lane mode is electrically impossible. Do not spend a
device reboot testing a guessed fallback or delete bus-width properties to
hide the missing controller support.

## Q4: protocol state and firmware

### What this unit has actually reported

**TBD current raw state.** No current boot log or clocked SE register sample
was supplied. The previous project analysis reports `Invalid proto 0` at
`a88000.spi` on ISO `bf0651c9`, but explicitly attributes it to a third-party
summary of screenshots, not raw logs. Treat that as a **reported observation**,
not Verified register evidence. Current disabled DT may produce no probe at all.

Read-only historical input:
`/home/juniormverli/repositories/surface/docs/analysis/geni-serial-engine-proto-0-2026-10-22.md`,
SHA-256 `1b6dc6373fd3a47f6c9f3e9f1a0fdae2f1063e2121e02730405f4ff6789eb2d8`.
Its claim that zero proves an empty engine is stronger than its evidence:
an enum and Linux's writer are not a hardware reset-value specification,
nor do they rule out inaccessible, reset or unclocked registers.

### What qcspi8380 selects

**Verified REA static control flow**, not an observed Windows execution:

- Binary: `sources/windows/DriverStore/qcspi8380.inf_arm64_14b48dd9d115a472/qcspi8380.sys`.
  Catalog row 622, SHA-256
  `34cabf2e7b59d3f8c0608da80dfdc705173c82427611312d32e7c1a9720e33ec`.
- Provider Ghidra 12.1.4, forced `AARCH64:LE:64:v8A` using
  `REA_GHIDRA_LANGUAGE_ID`; `GHIDRA_MAXMEM=4G`; every invocation protected
  with `flock out/.ghidra.lock`. Procedure enumeration preceded decompilation:
  `ev_b360b80cadf82abad9359ca076138fa23d50383e9ed267fa3c85d560fcb4f366`.
- Procedure `0x14000f710` parses the ACPI `_STR` using `QUP_%d_SE_%d` and
  records whether it contains `QSPI`:
  `ev_f2d5eb353ee07b62e1c1437732b84b054a66fe5e04aa1bc2f85987a8a150b2fd`.
- Procedure `0x14000fa70` calls that parser, then selects registry
  `Resources/QSPIBinaryPath` for that
  flag, or `SPIBinaryPath` otherwise, and calls `0x14001d8b8`:
  `ev_4b3d4ed9232de086c2853154a24841e5ec2b603b054882237caf38b30728a040`.
  Both procedures decode without the protocol's bad-instruction markers.
- The selected QSPIBinaryPath names `BSRC_QSPI.bin` in the examined INF
  (`2026-10-24-windows.md`, INF hash/line 52). The decoded blob is PEP
  clock/bus/GPIO power-policy data, not a `SEFW` ELF image.

**Inference:** with this package and the captured `_STR`, Windows chooses
the QSPI policy containing the extra pinmux. **Still TBD:** which component
loads SE sequencer microcode, the actual loaded protocol/revision, and the
microcode's origin. Neither the file's name nor its resource-loader call is
proof that qcspi uploads that blob into SE IRAM. No proprietary bytes or
decompiled code were exported to git. The REA snapshot is outside git at
`/tmp/touch-pen-qcspi8380.snap`; only conclusions/addresses are recorded here.

### Fedora qupv3fw.elf and Linux 7.3

**Verified package provenance from the firmware owner's manifest:**
`firmware/manifest.toml:179–183` records Fedora `qcom-firmware`, packaged XZ
SHA-256 `448c37c85f55b73dc038dca389774d9417051d9a28af5d03e12e443684b93f62`,
uncompressed SHA-256
`dcb4ca490098f081dd3f85d91ca230c4755d376a4cdca51e6a4ba918fa4ab077`.
`linux-firmware` is the source package; the installed Qualcomm subpackage
is `qcom-firmware` (firmware dossier §2).

The [upstream file](https://gitlab.com/kernel-firmware/linux-firmware/-/raw/main/qcom/x1e80100/qupv3fw.elf)
was fetched into memory and **matched that uncompressed hash**, 52288 bytes.
Parsing its ELF32 little-endian program headers and the documented
`se_fw_hdr` layout (`sources/linux/drivers/soc/qcom/qcom-geni-se.c:144–158`)
gives the following **Verified metadata**, without disassembly:

| SEFW segment | File offset | Protocol (u16) | Firmware version (u16) | Core |
|--:|:--|--:|:--|:--|
| 2 | `0x5018` | 6 | `0x0114` | `0x300c0000` |
| 3 | `0x5598` | 3 | `0x0203` | same |
| 4 | `0x5d20` | 260 (`0x104`) | `0x040c` | same |
| 5 | `0x6da0` | 4 | `0x0501` | same |
| 6 | `0x7f08` | 8 | `0x0203` | same |
| 7 | `0x8630` | **1 (SPI)** | `0x0b02` | same |
| 8 | `0x8e90` | 5 | `0x010a` | same |
| 9 | `0x9168` | 2 | `0x0405` | same |

There is **no protocol-9 SEFW segment**. Segment 1 starts with `QSI ` rather
than SEFW; metadata/hash segments are not protocol firmware. Firmware version
is a header value, not a claim about the SE's currently loaded RO register.

**Verified Linux behavior:** the loader can load this ELF's ordinary SPI
segment when requested with protocol 1, subject to the hardware RAM-depth
check. It supports selecting FIFO or GPI transfer mode and programs IRAM
(`qcom-geni-se.c:1250–1330`, :1428–1538, :1553–1601). It reads firmware-name
from the **wrapper**, maps missing-file ENOENT to EPROBE_DEFER, and rejects
requested protocols outside the 0–5 name array (:125, :1560). SPI host probe
requests it only for protocol 255 (`spi-geni-qcom.c:642–659`), not zero or
nine. Denali has no wrapper firmware-name. Linux 7.3 thus has a GENI loader;
it has neither a protocol-9 loader path nor protocol-9 payload in this file.

**Disposition:** this is a candidate *ordinary SPI* image, not an established
QSPI touch fix. It cannot satisfy the downstream protocol-9 requirement.
Whether a different firmware/personality can implement the required quad
contract remains open; installing the package or widening the zero gate is
insufficient evidence for doing so. No firmware loading is requested for the
diagnostic boot.

### Previous project patches 0027 and 0028

Both were read without applying or copying them into this patch series.
Directory: `/home/juniormverli/repositories/surface/kernel/patches/`.

| Patch | SHA-256 | Assessment |
|:--|:--|:--|
| `0027-arm64-dts-qcom-x1-microsoft-denali-name-the-QUP-firm.patch` | `126a151167bfa868b84dc2b1304a102c879b4ba7a9d4e001297d188b43c8ca8b` | Correct wrapper-property location; exposes the generic loader only when the driver calls it. Adds it to all three wrappers without demonstrating touch's required personality. Not a quad fix. |
| `0028-soc-qcom-geni-se-load-the-firmware-of-an-engine-that.patch` | `898fe0f2a7674f89758517b0ee79dbba5e97ac2a17b1a3835542d46a6b76b9b8` | Widens zero/255 gates in SPI, I2C, UART and newly enables SPI-target firmware loading. Still requests protocol 1 for this host. No quad/GPI/pinmux change and no post-load readback. Too broad to import as the touch solution. |

Its remaining nonzero-protocol rejection is useful design evidence. Its
assertion that zero and 255 necessarily mean the same hardware condition is
not established by raw logs. A future zero-gate change needs a matching
protocol image, clock/resource evidence, error-path checks and readback; keep
unrelated UART/I2C/target changes with their owners. The operator reports
that the older project's touch never worked either.

## Q3: sequencing RFC

Raw ASL actions and hashes are already recorded in the
[ACPI evidence](2026-10-24-acpi.md#direct-gpio-operations-and-timing).
Re-reading `ssdt.dsl:1726–1752` confirms:

| Path | Captured behavior | Proposed OF implementation |
|:--|:--|:--|
| `_PS0`, cold supply | Raise GPIO64, wait 500 ms, release reset GPIO48 | Existing fixed-regulator startup-delay-us=500000, followed by existing OF 10 ms; at least the captured cold interval |
| `_RST`, warm reset | GPIO48 low, wait 300 ms, high | MSHW0484-specific minimal_reset_delay_ms=300 |
| `_PS3` | GPIO48 low, wait 10 ms, GPIO64 low | Device-specific pre_power_off_delay_ms=10; power_down reasserts reset, checks success, then waits before regulator_disable |

RFC 0013 is now based on v7 and also supplies the captured eb/e2 opcodes
and report addresses as per-compatible data. v7's generic G6 data uses
0b/02, which must not silently replace this unit's values. The revised DT
uses only `microsoft,mshw0484`; v7 removes the generic hid-over-spi fallback
and address/opcode DT properties.

Raw constants are Verified; GPIO roles and Linux translations remain
Inference pending independent cross-check. `_INI`'s 10 ms is not a shorter
replacement for `_PS0`. The regulator's enable transition supplies the cold
delay, so a warm reset does not power-cycle the device or add 500 ms.

The protocol/sequencing RFC covers suspend, fatal-recovery, remove and the power-down
error path in initial reset release. A failed reset assertion leaves the
supply enabled rather than knowingly removing power without the interval.
A new `microsoft,mshw0484` compatible scopes the timings to this hardware ID;
its binding proposal is separate from the C patch. These are **unbuilt RFCs**.

## Validation and disposition

- `tools/decode-bsrc.py`: both complete data trees validate, with the tuples
  above. No opaque blob was disassembled.
- `collect-read-only.sh`: `bash -n` passes. It writes only to stdout, invokes
  no mount, modprobe, bind/unbind, runtime-PM control, GPIO request or MMIO tool.
  It has not run on the device.
- RFCs 0012–0015: zero-fuzz application after v7 to temporary source copies;
  kernel worktree remains unchanged. Detailed final checkpatch results are
  in `2026-10-28-validation.md`.
- No new `scripts/kernel-dev.sh` build or final DT validation has occurred.
  Earlier BTF and schema results apply to the unchanged v6 / **old** disabled
  draft only, not these revised RFCs. Full strict checkpatch remains failed:
  the RFCs are deliberately unsigned, and no Signed-off-by is fabricated.

Status stays **designed**. The [quad design](../quad-design.md) separates the
evidenced requirements from the missing GENI/GPI implementation contract.
No speculative controller register patch is exported as a working quad fix.
Next boot must capture engine state using normal probe instrumentation and
the read-only collector; the image request explicitly accounts for a disabled
controller producing no evidence. Claude cross-check precedes integration.
