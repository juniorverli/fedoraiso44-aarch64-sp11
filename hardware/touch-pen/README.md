# touch-pen

## 1. Summary

MSHW0484 is the Surface Touch G6 HID-over-SPI digitizer, with touch and pen
collections in Windows. Status: **designed**; the shortest supported path is
GENI QSPI/GPI plus correct multi-lane transport, with one controller-state
capture before choosing a firmware change. Pen is optional for this session's
working-touchscreen milestone.

Session 2 identifies the extra data-pin policy, rules out treating generic
SPI firmware as an established quad fix, and supplies unsigned protocol,
sequencing, binding, disabled-DT and diagnostic RFCs. The newest found
spi-hid baseline is v7 (2026-10-24), exported unchanged; no functional quad
controller patch is claimed. The current ISO's inactive touch is expected:
it has no spi-hid series and the touch DT is disabled. See the
[session-2 evidence](evidence/2026-10-28-quad-firmware-sequencing.md) and
[minimal implementation design](quad-design.md).

All changes remain under this component and uncommitted. The kernel checkout
still contains the previous session's unchanged v6 and old disabled draft;
no kernel checkout, shared owner file or device was modified this session.

## 2. Hardware

Grades, input hashes and exact offsets are in the
[ACPI evidence](evidence/2026-10-24-acpi.md) and
[session-2 evidence](evidence/2026-10-28-quad-firmware-sequencing.md).

| Item | Value | Grade / evidence |
|:--|:--|:--|
| Device | ACPI MSHW0484 revision 1; HID Col01–Col0A | Verified inventory; association with dynamic GTCH `_HID` is Inference |
| Controller | QCOM0C0E / MSHW0489, SP11, QUP_1_SE_2, MMIO `0x00a88000` | Verified DSDT:51534–51561 |
| Linux controller | `&spi10`, wrapper 1 SE2; GENI QSPI personality | Inference from MMIO/clock/policy; not the standalone QSPI block |
| SPI framing | CS0 active-low, 40 MHz maximum, mode 0, 8-bit words | Verified ACPI raw / Inference conversion |
| Data phases | Quad reads and writes; opcode single-lane | Inference from `_DSM=0xa000` and Microsoft spec pp.12/16 |
| Read turnaround | Eight placeholder clocks: four bytes in quad mode | Verified spec §7.1.2 p.23; v6/v7 one-byte placeholder is insufficient |
| Bus mux | GPIO40–43: SE2 selector 1; extra GPIO49/50: SE2 selector 2 | Verified Windows QSPI-policy tuples and Linux mux slots; board wiring Strong Inference, cross-check pending |
| Touch IRQ | GPIO51 falling edge, no pull in ACPI, wake-capable declaration | Verified raw / Inference translation; keep it in GPIO mode |
| Reset / supply enable | GPIO48 active-low reset; GPIO64 active-high enable | Inference from direct TLMM operations and power methods |
| Timing | Cold D0 500 ms; reset 300 ms; reset-before-power-off 10 ms; `_INI` 10 ms | Verified raw constants / Inference decimal conversion |
| Report addresses / opcodes | `0x1000`, `0x1004`, `0x2000`; read `eb`, write `e2` | Verified raw; meanings follow public spec |
| Additional interrupt | ACPI GpioInt `0x0440` | Verified raw; encoding/role TBD, not TLMM GPIO1088 |
| Unknown electrical details | Extra-pin drive/pulls, supply voltage and parent | TBD; no electrical settings invented for GPIO49/50 |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `hidspi_km (inbox)` | HID-over-SPI transport, Inference from compatible ID/specification; binary not examined |
| `qcspi8380` | Verified host driver binds QCOM0C0E; REA shows QSPI selection from `_STR`, then QSPIBinaryPath. BSRC_QSPI is ACPI clock/bus/GPIO power-policy data; actual sequencer-microcode loading remains TBD |
| `surfacedigitizerwotextnpackage` | Verified extension requests Windows WakeScreenOnTouch policy; does not establish Linux wake routing |
| `surfacetouchg6fwupdateextnpackage0c80` | TBD; not opened; updating excluded |
| `surfacetouchg6fwupdateextnpackage0c83` | TBD; not opened |
| `surfacetouchpenprocessor0c80update` | TBD; not opened |
| `surfacetouchpenprocessor0c83update` | TBD; not opened |
| `surfacepenblelcaddradaptationdriver` | TBD; not opened |
| `surfacepen0c0ffirmwareupdate` | TBD; not opened |
| `surfacepenwirelesschargerhotkey` | TBD; not opened |

[Windows evidence](evidence/2026-10-24-windows.md) records INF versions and
collections. The newer qcspi package's presence does not prove it was the
active Windows version. Col04/Col07 labels identify touch/pen collections;
report descriptors and actual input capabilities remain unknown.

## 4. Linux 7.3

- No generic spi-hid in the base (`sources/linux/drivers/hid/Kconfig:1536`,
  Makefile:186). The archived v6 patches build with BTF and new-file W=1
  in the previous minimal compatibility configuration. The current exported
  baseline is v7: clean application and final source-blob verification on
  7.3, but no new build. Its strict checkpatch findings remain open. See
  [v7 assessment](evidence/2026-10-28-spi-hid-v7.md) and
  [historical v6 build](evidence/2026-10-24-spi-hid-v6.md).
- `spi10` is disabled, with GPIO40–43 pinctrl and GPI instance 1 / SEID 2
  (`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:1689`, :6458).
- `spi-geni-qcom` has no dual/quad modes or transfer-width handling
  (`sources/linux/drivers/spi/spi-geni-qcom.c:1114`). The SPI core clears
  unsupported width mode bits (`sources/linux/drivers/spi/spi.c:4326`).
  Linux-next next-20261028 still lacks this support; no posted GENI dual/quad
  series was found in the bounded search. See session-2 evidence for queries,
  source commit and hashes; downstream X1E work is not an upstream backport.
- The host loads ordinary SPI firmware for protocol 255 only; zero is rejected
  (`sources/linux/drivers/spi/spi-geni-qcom.c:642`). The existing loader reads
  firmware-name on the wrapper and rejects protocol 9
  (`sources/linux/drivers/soc/qcom/qcom-geni-se.c:1553–1601`).
- Fedora's `qcom-firmware` supplies `qcom/x1e80100/qupv3fw.elf.xz`. Its verified
  decompressed hash matches the inspected upstream ELF: ordinary SPI protocol
  1 exists, **no protocol-9 segment exists**. Presence is not evidence that
  the required QSPI personality is available or loaded.
- The revised DT and RFCs are not build/schema validated. Previous DT results
  apply to the **old** disabled draft. Current status does not meet sw-ready.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| GENI QSPI personality / GPI transfers | Capture current clocked engine state; assess a narrow host/GPI implementation using the design. No speculative protocol-1 quad patch |
| Transport width and turnaround | Split opcode from address/data; preserve CS; eight placeholder clocks, four bytes for quad. Neither unchanged v7 nor a mode_bits-only change suffices |
| Current protocol / compatible firmware | Read normal probe diagnostics. Protocol 0 is an old second-hand report; generic firmware has no protocol 9. Identify the actual authorized payload/load path if the engine needs programming |
| Board mux and electrical configuration | Disabled draft adds GPIO49/50 SE2 mux; independently decode electrical fields and cross-check before enabling |
| Reset and power sequencing | RFC 0013 plus binding RFC 0015: eb/e2 match data, 300 ms reset and checked 10 ms reset-before-disable; fixed regulator retains cold 500 ms wait |
| Device support not integrated | Preserve newest v7 unchanged; port posted spi-mem transport RFC; sources pin, kernel dev/BTF build, strict checkpatch, final DT validation and Claude cross-check precede integration |
| Wake resource / pen capabilities | Leave second IRQ and wake policy unresolved; first milestone is ordinary touch input, pen optional |

## 6. Open questions

| # | Question / current answer | Grade | Remaining evidence |
|:--|:--|:--|:--|
| Q1 | Same GENI SE with QSPI personality; extra-pin policy names 49/50. No upstream GENI quad/dual implementation found | Inference for board mapping; raw policy/mux slots Verified | Actual SE personality, supported QSPI/GPI command contract and electrical-field cross-check |
| Q4 | Old project reported protocol 0 second-hand; current raw value unknown. Windows selects QSPI power policy, not a proven microcode payload | Reported / TBD | Controller-only diagnostic boot; identify actual sequencer initialization if firmware is absent |
| Q3 | eb/e2 match data, 300 ms reset and 10 ms power-off sequencing drafted | Inference implementation of Verified constants | Build, final DT validation and independent Claude reproduction |
| Q6 | Fedora generic image has no protocol 9 | Verified metadata; suitability for touch unresolved | Compatible QSPI image/personality and provenance, if needed; do not load ordinary SPI by assumption |
| Q2 | GpioInt `0x0440` and wake/panel policy | TBD | Controller semantics / independent ACPI investigation; not needed to guess a wake route for first touch |
| Q5 | Actual touch reports and fragment sizes; pen optional | TBD; collection labels Verified | HID descriptors and evtest after transport works |

## 7. Acceptance

First milestone: correct touch orientation, taps/drags/scrolling and ten
simultaneous contacts in GNOME, without reset storms or growing bus errors.
Then power-cycle/display/suspend recovery under the agreed policy. Pen
pressure/tilt/buttons/eraser remain optional in this session and must be
reported from actual capabilities. No device criterion has been exercised.
See [test-plan.md](test-plan.md).

## 8. Requests

### Image worker: next boot, exact read-only collection

Stage [collect-read-only.sh](collect-read-only.sh) in the image as
`/usr/libexec/sp11-touch-pen-collect` (mode 0755). Inside the existing collector,
after its existing debugfs setup, run exactly:

```sh
shsnap touch-pen.txt 'bash /usr/libexec/sp11-touch-pen-collect'
```

For an interactive collector invocation, run as root:

```sh
bash /usr/libexec/sp11-touch-pen-collect
```

The helper contains the complete commands: kernel journal filtering; live DT
status/firmware-name/clock/DMA properties; platform binding/runtime state;
`/sys/kernel/debug/gpio` actual mux/pull/drive for GPIO40–43/48–51/64;
pinctrl ownership/configuration; QUP clocks; deferred probes; and installed
firmware hashes/SEFW protocol metadata. It writes only stdout, which `shsnap`
records. Do not add devmem, gpioget/gpioset, modprobe, bind/unbind, debug-control
writes, firmware loading or a forced runtime resume.

**A disabled controller cannot answer its register state.** Current 7.3 does
not expose those GENI registers through a read-only sysfs file. Before spending
the next reboot on this question, coordinate with kernel to include temporary
[RFC 0014](patches/0014-spi-geni-state-diagnostic-rfc.patch) and the
[controller-only DT variant](touch-pen-state.dts), using the current working
LCD base. This needs no spi-hid backport. The variant selects only stock
GPIO40–43, removes wrapper firmware-name and leaves extra pins inherited;
no touch child may be enabled. Kernel must verify the final DT has no enabled
HID child or touch-supply consumer. The added probe message captures `proto`,
raw firmware revision, interface/clock status and HW parameters before protocol
dispatch; the collector only reads it. This is a development diagnostic image,
not touch integration.

Interpret the log using [quad-design.md](quad-design.md). Missing messages with
DT disabled mean **not sampled**, not zero. A boot-time pin dump is Linux's
current state, not proof of Windows' prior mux. Preserve the complete kernel
journal in the normal private collector output; sanitize evidence before git.

### Kernel / soc-boot

Assess RFC 0014 and the controller-only variant first. Retain normal rejection
of zero/nine and do not import the old project's broad 0027/0028 firmware
changes as a touch fix. Cross-check the observed protocol against clocks and
hardware fields. After a real quad implementation exists, apply/review the
unsigned RFCs in order **0015, 0013, 0012**; all remain excluded from series.
The worker kernel checkout has not been updated to these revisions.

With patches applied by the owning worker, use the project dev helper:

```sh
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
  scripts/kernel-dev.sh touch-pen module drivers/hid/spi-hid
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
  scripts/kernel-dev.sh touch-pen module drivers/spi/spi-geni-qcom.ko
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
  scripts/kernel-dev.sh --check touch-pen dtbs
```

For the diagnostic variant, use `scripts/kernel-dev.sh --check touch-pen variant
hardware/touch-pen/touch-pen-state.dts` after applying RFC 0014, and inspect the
resulting DT. Neither these commands nor a new build ran this session. Verify
both BTF symbols and BTF sections, controller/GPI changes, bindings and final
DT. Resolve unsigned authorship and v7's strict checkpatch findings before
sw-ready; this worker must not add a Signed-off-by.

### Sources / firmware / orchestrator

- **Sources:** centrally pin spi-hid v7 (cover `20261024-send-upstream-v7-0-abad13174b43@chromium.org`),
  the October 10 Romulus spi-mem RFC, the Microsoft specification, and the
  exact downstream GENI/GPI research blobs already listed in the older
  evidence. Pin a primary QSPI/TRE implementation contract before turning
  its magic constants into a controller patch. Current next commit/hashes
  and negative-search limits are in the session-2 evidence. One additional
  catalog-forced REA decompile of qcspi8380 procedure `0x140023790` returned
  `Analysis failed` without an evidence ID; no conclusion uses that attempt.
  Reproduce through the existing snapshot/lock if tracing Windows sequencer
  initialization requires that procedure.
- **Firmware:** inspect the matching protocol/personality and its provenance
  if the state capture shows an unprogrammed engine. The current Fedora
  image's protocol list is established; it contains no protocol 9. Determine
  the actual Windows sequencer initialization separately from BSRC power
  policy. No new firmware upload is requested by these diagnostics.
- **Orchestrator:** commission a Claude cross-check before integration. Ask
  for an independent read of SP11/GTCH resources, BSRC selected bus pins,
  `_PS0/_PS3/_RST`, `_DSM` flags and quad read-approval clocks; then compare
  against this dossier per protocol §5.1. Include the new MSHW0484 binding,
  GPIO translations and all pin electrical settings before enabling touch.

## 9. Log

- 2026-10-23: dossier created from static survey.
- 2026-10-24: preserved/applied spi-hid v6's 11 unchanged patches; completed
  minimal BTF and new-file W=1 builds and binding/old disabled-DT checks;
  documented quad/GENI/sequencing gaps. Changes left uncommitted as instructed.
- 2026-10-28, session 2: identified GENI SE2 QSPI personality and Windows
  GPIO49/50 policy with a complete data decoder; checked next-20261028 and
  upstream searches; established no protocol-9 payload in Fedora generic
  firmware; evaluated old 0027/0028 without copying them; exported spi-hid
  v7 unchanged and identified the posted Romulus spi-mem transport RFC;
  drafted scoped protocol/sequencing/binding and probe-state RFCs, revised
  disabled mux DT, and exact
  read-only next-boot collector. Status designed; new RFCs unbuilt, final DT
  and strict checkpatch gates incomplete; no git writes or device access.
