# touch-pen

## 1. Summary

MSHW0484 is the Surface Touch G6 HID-over-SPI digitizer, with touch and pen
collections reported by Windows. Status: **designed**; the newest found
spi-hid series (v6, 2026-10-19) builds unchanged on v7.3, but the board needs
quad SPI and sequencing that the unchanged stack cannot provide.

The resumed session completed warning and schema checks: all new C files
compile with `W=1`, the binding passes `dt_binding_check` with YAML lint, and
the disabled board draft validates against HID, fixed-regulator and TLMM
schemas. This does not clear the component's functional or cross-check gaps.

All work is software-only. The [DT draft](touch-pen-draft.dtsi) and its RFC
patch keep controller, supply and HID child disabled. No device access,
firmware writing, git-index changes or commits were performed.

## 2. Hardware

Full path/hash/line citations and grade reasoning are in
[ACPI evidence](evidence/2026-10-24-acpi.md). The controller is in the DSDT;
the digitizer resources and methods are in **ssdt.dsl**, not dsdt.dsl.

| Item | Value | Grade | Evidence |
|:--|:--|:--|:--|
| Windows IDs | ACPI MSHW0484 revision 1; HID Col01–Col0A | Verified | ACPI evidence C:2855 and Windows evidence collection rows |
| Controller | QCOM0C0E / MSHW0489, SP11, QUP_1_SE_2, MMIO `0x00a88000` | Verified | A:51534–51561 |
| Linux controller | `&spi10` | Inference | MMIO/clock match, `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:1689` |
| SPI framing | CS 0 active low, 40 MHz, mode 0, 8-bit words | Verified raw / Inference conversion | B:1566–1570 |
| Data lanes | Quad reads and writes, opcode on one lane | Inference | B:1656–1659 flags `0xa000`, Microsoft specification pp.12/16 |
| Input IRQ | TLMM GPIO 51, falling edge, no pull, wake-capable ACPI declaration | Verified raw / Inference DT translation | B:1571–1576 |
| Additional resources | GPIO64 GpioIo/pull-down; GpioInt `0x0440` active-high edge/pull-down | Verified; second IRQ meaning TBD | B:1577–1588 |
| Reset / power enable | TLMM GPIO48 active-low reset; GPIO64 active-high supply enable | Inference | B:1669–1688, B:1711–1752, Linux TLMM register layout |
| Explicit timing | Cold D0: 500 ms; reset: 300 ms; reset-before-power-off: 10 ms; `_INI`: 10 ms | Verified constants / Inference ms conversions | B:1711–1752 |
| Report addresses | Input header `0x1000`, body `0x1004`, output `0x2000` | Verified | B:1625–1638 |
| Opcodes / flags | Read `0xeb`, write `0xe2`, flags `0xa000` | Verified | B:1640–1659 |
| Physical supply voltage, quad pinmux | Unknown | TBD | Additional source evidence and independent cross-check |

GTCH's `_HID` reads SHSD from NVS; its association with inventory MSHW0484 is
an **Inference**, not a literal ID found in the ASL. `_DSM` does not expose
a separate descriptor-register address: revision 3 functions 1–3 are report
addresses; revision 1 function 1 returns integer 1 with legacy meaning TBD.

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `hidspi_km (inbox)` | HID-over-SPI transport, Inference from compatible ID/specification; inbox binary not examined |
| `qcspi8380` | Verified SPI host driver `qcspi`, binds QCOM0C0E, depends on SpbCx, references distinct SPI/QSPI data blobs; both INF versions examined |
| `surfacedigitizerwotextnpackage` | Verified extension matches MSHW0484 and includes input.inf / WakeScreenOnTouch.HW; Windows wake-screen policy request, not a decoded Linux wake route |
| `surfacetouchg6fwupdateextnpackage0c80` | TBD; not opened; firmware updating excluded from this task |
| `surfacetouchg6fwupdateextnpackage0c83` | TBD; not opened |
| `surfacetouchpenprocessor0c80update` | TBD; not opened |
| `surfacetouchpenprocessor0c83update` | TBD; not opened |
| `surfacepenblelcaddradaptationdriver` | TBD; not opened |
| `surfacepen0c0ffirmwareupdate` | TBD; not opened |
| `surfacepenwirelesschargerhotkey` | TBD; not opened |

[Windows evidence](evidence/2026-10-24-windows.md) records the INF hashes,
versions and collection map. Col04 is named Surface Touch Screen Device and
Col07 Surface Touch Pen Device (**Verified inventory labels**); actual report
layout and capabilities remain TBD.

## 4. Linux 7.3

- **Verified:** no generic spi-hid directory or Kconfig entry in the base;
  Intel THC/QuickSPI is hardware-specific, not this GENI host
  (`sources/linux/drivers/hid/Kconfig:1536`, `sources/linux/drivers/hid/Makefile:186`).
- **Verified:** `spi10` exists but is disabled, with ordinary SPI pinctrl
  GPIOs 40–43 (`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:1689`, :6458).
  Denali enables the wrapper at
  `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1030`.
- **Verified:** protocol 0 returns `-EINVAL`; only protocol 255 triggers loading
  (`sources/linux/drivers/spi/spi-geni-qcom.c:642`). Actual device state is TBD.
  The firmware-name belongs on the wrapper
  (`sources/linux/drivers/soc/qcom/qcom-geni-se.c:1565`).
- **Verified:** the controller advertises no quad modes
  (`sources/linux/drivers/spi/spi-geni-qcom.c:1114`). Unsupported multi-lane
  bits are warned about and cleared (`sources/linux/drivers/spi/spi.c:4326`).
- **Verified software test:** v6 patches 0001–0011 apply unchanged with zero
  fuzz/offsets and build vmlinux plus core/OF/ACPI modules with BTF. See
  [upstream/build evidence](evidence/2026-10-24-spi-hid-v6.md).
  This is a small ARM64 compatibility config, not a Fedora RPM build.
- **Verified software checks:** new driver objects compile without warnings
  under `W=1`; binding/example and disabled board DT validate. The unchanged
  upstream series still has strict checkpatch findings, recorded in that evidence.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| No base generic transport | Preserve newest posted v6 unchanged as baseline; clear upstream checkpatch/sign-off issues before integration |
| Required quad transfers; v6 single-lane only | Split-width opcode/address/data handling, verified GENI/QSPI support and board pinmux |
| Protocol 0 bypasses firmware load | Evidence-backed kernel/soc-boot request: identify QSPI personality before assessing a narrow ordinary-SPI NONE-or-INVALID gate; a firmware file alone is insufficient |
| DT / sequencing | Disabled draft models 500 ms cold-power wait; add 300 ms reset and 10 ms shutdown sequencing separately |
| Additional interrupt and panel/wake | Resolve `0x0440` and select policy before adding wakeup-source/panel |
| Cross-check, central input pins and patch hygiene | Other-runtime cross-check; sources owner pins upstream series and public spec; resolve existing strict checkpatch findings without fabricated sign-offs |

See [GENI and DT analysis](evidence/2026-10-24-geni-and-dt.md). These gaps
prevent `sw-ready` even though the transport baseline builds.

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which quad GENI/QSPI personality, driver and extra data pins implement QCOM0C0E? | TBD | Linux/upstream evidence, then catalog-guided Windows host investigation if needed |
| Q2 | What is GpioInt `0x0440`, and which wake/panel policy is valid? | TBD | GPIO/controller semantics and independent ACPI read |
| Q3 | Which sequencing change supplements v6? | Inference proposal | Cross-check `_PS0/_PS3/_RST`, then device-specific driver data/sequence |
| Q4 | Does the engine report protocol 0, 1, 255, or something else? | TBD | Future approved boot logs; no device evidence this session |
| Q5 | Which reports/capabilities and fragment sizes do touch and pen use? | TBD; collection labels Verified | Report/device descriptors and evtest; inventory identifies Col04/Col07 |
| Q6 | Is `qcom/x1e80100/qupv3fw.elf` compatible with the required mode? | Hypothesis | Firmware-owner pin and segment analysis; not a proven dependency |

## 7. Acceptance

1. Ten-finger touch with correct orientation in GNOME.
2. Pen pressure, tilt, barrel button and eraser in a drawing app.
3. Touch/panel transitions and agreed wake behavior without lost input or reset storms.

Future commands and software gates are in [test-plan.md](test-plan.md).
No device acceptance criterion has been exercised.

## 8. Requests

- **Sources:** pin cover `20261019-send-upstream-v6-0-cb9ba4b3d6fa@chromium.org`,
  its 11 patches, and the Microsoft specification with the evidence hashes.
  Lore returned HTTP 403; original mbox was retrieved from Patchew, outside git.
  Pin the exact nix1e QSPI research blobs listed in the GENI evidence if the
  follow-up proceeds; these were inspected but not applied or build-tested.
- **Orchestrator:** commission protocol §5.1 cross-check on the other runtime:
  SPI framing/quad flags, GPIO arithmetic, all delays, `_DSM`, disabled DT.
  None has occurred. Review/adopt the unsigned DT RFC before signing it.
- **Kernel / soc-boot:** resolve quad controller/pinmux and protocol-0 handling.
  The GENI evidence identifies a concrete QSPI/GPI glue lead from Dale's
  SP11 upstream-thread report, including a distinct downstream protocol 9.
  Eventual config needs SPI_HID=m, SPI_HID_OF=m (core selected), SPI_QCOM_GENI,
  REGULATOR_FIXED_VOLTAGE, HID_MULTITOUCH and both BTF symbols. Full Fedora
  config/RPM build remains required; do not integrate 0012 as an enabled device.
  The ACPI module is optional for DT boot.
  The concrete protocol-0 decision and path/error checks are in
  [GENI evidence](evidence/2026-10-24-geni-and-dt.md#request-to-kernel--soc-boot-protocol-0-decision).
  Do not classify `qupv3fw.elf` as an established touch dependency.
- **Firmware:** determine a compatible GENI/QSPI image and provenance if needed;
  do not assume generic SPI firmware implements quad mode.
- **Display / image:** keep touch disabled in current phase-1 images. Later
  coordinate panel/wake policy and collect GENI/HID/input evidence on an approved boot.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: found v6, preserved/applied 11 unchanged patches and BTF build-tested
  them on v7.3; extracted SP11 DSDT and GTCH SSDT data, decoded required quad
  mode, documented protocol-0 rejection, drafted disabled DT and future test plan.
  Status designed; cross-check, quad support and sequencing open.
- 2026-10-24 (resumed): preserved the completed application/BTF builds, confirmed
  all 14 final upstream blobs, passed new-file W=1 and binding/disabled-board
  validation, identified the WoT extension's policy request, and finalized the
  sequencing/GENI requests and test plan. Status remains designed; changes left
  uncommitted for orchestrator review as instructed.
