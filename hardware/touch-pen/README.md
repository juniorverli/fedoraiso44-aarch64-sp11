# touch-pen

## 1. Summary

MSHW0484 is the Surface Touch G6 HID-over-SPI digitizer with touch and pen
collections. Status: **designed**; session 3 ports the working SP11 reference
onto v7.3, with a separate enabled DT patch and no QSPI firmware upload.

The previous image lacks the host/GPI QSPI support, matching transport and
enabled DT. The reference expects preloaded **SE protocol 9**, uses eight
hardware-generated dummy clocks and requires **iptsd 3.1.0**. The complete
comparison, commit hashes and firmware resolution are in
[working-reference evidence](evidence/2026-10-29-working-reference.md).
The full BTF Image/modules build and both DT checks pass.
Software checks and their remaining blockers are in
[validation](evidence/2026-10-29-validation.md). No device pass is claimed.
The [2026-10-30 lint triage](evidence/2026-10-30-lint-triage.md) classifies
every upstream finding, confirms 0016–0020 remain clean, and rechecks the
current 29-patch integration and enabled DT without a full kernel build.

## 2. Hardware

Board values were independently reproduced by the
[Claude cross-check](crosscheck/claude-2026-10-28.md); hashes and source
locations are there and in [ACPI evidence](evidence/2026-10-24-acpi.md).

| Item | Value | Grade |
|:--|:--|:--|
| Device | MSHW0484 revision 1, associated with GTCH / PNP0C51 | Verified inventory; GTCH association Inference |
| Controller | QUP1 SE2, `spi10@a88000`, GIC SPI 802, GPI1 SEID2 | Verified ACPI/Linux mapping |
| Personality | QSPI, SE protocol **9**; DT/GPI selector **4** | Verified working-source contract; current unit register TBD |
| Bus | CS0 active-low, mode 0, 8-bit, ACPI maximum 40 MHz | Verified; driver retains reference 20 MHz cap |
| Phases | Opcode single-lane, address/data quad; eight dummy clocks on read | Inference from verified `_DSM=0xa000` and public specification; reference agrees |
| Bus pins | 40–43 mux1, 49/50 mux2, `qup1_se2` | Verified independent policy/mux reproduction; IO2/IO3 order unneeded and still Hypothesis |
| Extra-pin electrical settings | Not independently decoded | TBD; port selects mux only on 49/50 |
| Interrupt | GPIO51 falling edge, no bias | Verified value / Inference DT translation |
| Reset / power | GPIO48 active-low reset; GPIO64 active-high enable | Verified direct TLMM sequencing / Inference polarity names |
| Timing | Cold power 500 ms; reset hold 300 ms; reset before off 10 ms | Verified ACPI, independently cross-checked |
| Protocol data | Addresses 1000/1004/2000; opcodes eb/e2; `_DSM` revision 3 | Verified values; semantic roles follow specification |
| Other interrupt | ACPI 0x0440, outside plain TLMM range | TBD wake routing; omitted from Linux node |

## 3. Windows

| DriverStore package | Role |
|:--|:--|
| `hidspi_km` | HID-over-SPI transport for PNP0C51; firmware flashing excluded |
| `qcspi8380` | Host driver; REA verifies `_STR` QSPI selection and QSPIBinaryPath policy selection; no separately named QSPI microcode established |
| `surface_spiext_den8380` | Board extension selecting `BSRC_QSPI_DEN.bin`; decoded clock/GPIO power policy **data**, never disassembled |
| `surfacedigitizerwotextnpackage` | WakeScreenOnTouch policy; does not establish Linux wake routing |
| `surfacetouchg6fwupdateextnpackage0c80`, `...0c83` | Not opened; update path outside scope |
| `surfacetouchpenprocessor0c80update`, `...0c83update` | Not opened |
| `surfacepenblelcaddradaptationdriver` | Not opened |
| `surfacepen0c0ffirmwareupdate` | Not opened; no flashing |
| `surfacepenwirelesschargerhotkey` | Not opened |

[Windows evidence](evidence/2026-10-24-windows.md) records package versions and
collections. Package presence does not prove the active Windows version or
actual Linux report capabilities. No Windows bytes or private log lines are
part of this change.

## 4. Linux 7.3

- Base has no SPI-HID transport (`sources/linux/drivers/hid/Kconfig:1536`,
  `Makefile:186`). The selected baseline is Jingyuan Liang's posted v7,
  11 patches, with original authorship and trailers retained.
- `spi10` is disabled with only four bus pins by default
  (`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:1689`, `:6458`).
- Base host has no quad/GPI QSPI contract and accepts ordinary SPI protocol 1;
  only protocol 255 invokes the generic loader
  (`sources/linux/drivers/spi/spi-geni-qcom.c:627–658`, `:1114`).
- The generic loader's table covers 0–5, not 9, and reads firmware-name from
  the wrapper (`sources/linux/drivers/soc/qcom/qcom-geni-se.c:125`, `:1553`).
  The working reference makes no touch change to that file.
- New patches 0016–0020 add bindings, QSPI GPI/host, MSHW0484 transport/reset
  quirks and a separate LCD DT node. Current `kernel/series` includes them
  after v7 and the speaker/GPU disablement; diagnostic RFC 0014 is retired. See
  [patch selection](patches/series) and [patch notes](patches/README.md).
- No touch firmware-name is added. Fedora's generic QUP image contains no
  protocol 9; the port requires a preprogrammed SE, as the reference does.

## 5. Gaps

| Gap | Answer / remaining gate |
|:--|:--|
| GENI/GPI and HID quad path | Implemented as a small port of the working downstream contract; source/build results in validation |
| Board DT / sequencing | Separate 0020 and MSHW0484 match data use independently cross-checked board values |
| Strict lint | 0016–0020 clean; all six warnings / eleven checks classified as unchanged upstream v7 findings in the 2026-10-30 triage; orchestrator exception decision pending |
| Independent review | Newly imported QSPI register/TRE constants and v7 rebind adaptation need Claude cross-check before integration |
| Actual SE state and first input | Next boot must show protocol9 and HID/iptsd/input enumeration; no device test yet |
| Userspace | Official f44 repos have no iptsd; image must build/install a native 3.1.0 RPM and preserve its udev/service integration |
| Wake and acceptance | Second Windows wake resource unresolved; suspend/pen and ten-contact acceptance need device evidence |

## 6. Open questions

| Question | Grade / next evidence |
|:--|:--|
| Is this unit's SE preloaded with protocol9 under our boot path? | TBD; retained `touch-pen-diag` journal record, not raw MMIO reads |
| Which platform boot component originally programs that SE? | Inference: boot firmware; no named payload/load in the reference Linux path. Not needed if protocol9 is present |
| Are retained extra-pin electrical settings sufficient? | TBD; verified mux only, no guessed pulls/drive. Observe pinctrl and transfer errors on next boot |
| Does metadata-driven iptsd configuration work on this unit? | Inference from unmodified reference package; collect service logs, dimensions and touch behavior |
| Does pen expose pressure/tilt/buttons, and does recovery retain heatmap mode? | TBD; evtest and coordinated device acceptance |
| What is the second wake resource? | TBD; no guessed GPIO1088 or wake claim |
| Why do some taps need repeating? | Ranked causes in the [missed-taps evidence](evidence/2026-10-31-missed-taps.md); decided by the A/B run and collector |
| What does Windows use for contact thresholds on 0C80 (host heatmap processing or on-chip contacts; where the limits live)? | TBD; REA question listed in the missed-taps evidence section 8, not run |

## 7. Acceptance

First, GNOME receives correctly oriented taps/drags/scrolling and ten contacts
without reset storms or increasing transport errors. Then verify reset/power
recovery, agreed suspend policy and pen pressure/tilt/buttons from real
capabilities. All device acceptance remains pending. See [test-plan](test-plan.md).

## 8. Requests

### Kernel: current integration and lint triage

Current `kernel/series` already includes these entries in this order;
do not append them again. Diagnostic RFC 0014 is retired, as recorded by
the kernel worker for M8. Keep the S1 speaker-disable and GPU-disable
patches. Leave old v6 and RFCs 0012/0013/0015 out.
The following list is also available as [kernel-series.list](kernel-series.list).

```text
hardware/touch-pen/patches/v7/0001-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0002-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0003-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0004-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0005-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0006-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0007-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0008-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0009-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0010-spi-hid-v7.patch
hardware/touch-pen/patches/v7/0011-spi-hid-v7.patch
hardware/touch-pen/patches/0016-dt-bindings-qspi-mshw0484.patch
hardware/touch-pen/patches/0017-dmaengine-qcom-gpi-qspi.patch
hardware/touch-pen/patches/0018-spi-geni-qcom-qspi.patch
hardware/touch-pen/patches/0019-spi-hid-mshw0484.patch
hardware/touch-pen/patches/0020-denali-lcd-touch.patch
```

Use [kernel-dev.config](kernel-dev.config) as the additional fragment; release
needs SPI_HID_CORE/OF, SPI_QCOM_GENI, QCOM_GPI_DMA, HIDRAW and INPUT_UINPUT,
with both BTF symbols enabled. ACPI frontend can build but the device boot
uses OF. No Intel IPTS/ITHC host driver is required for this ARM SPI device.
0016–0019 can ship without 0020; 0020 is the separate enablement switch.
Keep [touch-pen-state.dts](touch-pen-state.dts) as a controller-only
diagnostic alternative. It removes both the child and its supply, selects
the generic host/DMA binding and leaves extra pins untouched; a protocol9
rejection in that entry is expected after the diagnostic sample. Merge it
with the image owner's GPU-off/speaker-off variant policy.

This remains **designed**: [lint triage](evidence/2026-10-30-lint-triage.md)
recommends preserving all 17 upstream findings unchanged, with no finding
in 0016–0020. The raw strict checker still returns findings; the orchestrator
must decide the upstream exception and obtain independent review of the new
QSPI/rebind code before sw-ready clearance. Any future release RPM rebuild
uses the kernel owner's normal process. The retained session-3 full dev
build occupies 7.7 GiB; this session's DT-only guard reports 29 GiB headroom,
below the release helper's 60 GiB start threshold. Account for storage before
a future release build rather than bypassing that guard. Never add
a broad protocol0-to-SPI firmware workaround. Unexpected protocol must fail.

**2026-10-30 hand-back:** no patch used by `kernel/series` changed; this
triage requires **no kernel rebuild**. All 29 current patches pass sequential
`git apply --check`; fresh `CHECK_DTBS=y`, `dt-validate`, binding validation
and compiled-DTB safety/wiring checks pass. The checked DTB matches M10's
packaged DTB hash. Kernel owner: add Fedora `python3-ply` to the build
container's dependencies so checkpatch's SPDX helper can run. The old raw
touch lint log contains missing-`ply` tracebacks despite the prior validation
note; this session's replacement log has none. The component lint helper
now accepts an explicit composed root and fails on tool stderr/missing totals.
The temporary Fedora RPM dependency and all raw outputs remain under
`out/agents/touch-pen/lint-20261030/`.

### Image: native iptsd and one combined read-only collection

Build/install local `iptsd-3.1.0-1.fc44.aarch64.rpm` from the pinned upstream
release using Fedora RPM tooling, as detailed in
[userspace evidence](evidence/2026-10-29-iptsd-fedora.md). There is no official
f44 iptsd NEVRA. Retain its standard udev rule and `iptsd@.service`; start with
the upstream default configuration and metadata-derived dimensions/orientation.
The working reference adds no SP11 preset. Include `libinput-utils`, `evtest`
and uinput availability before iptsd starts. If the live image does not
already provide it, use Fedora's modules-load.d convention with
`/etc/modules-load.d/iptsd.conf` containing `uinput`. Do not hardcode a
hidraw index.

Stage [collect-read-only.sh](collect-read-only.sh) at
`/usr/libexec/sp11-touch-pen-collect` (0755). After the existing collector has
set up debugfs, execute exactly:

```sh
shsnap touch-pen.txt 'bash /usr/libexec/sp11-touch-pen-collect'
```

Equivalent root terminal command:

```sh
bash /usr/libexec/sp11-touch-pen-collect
```

The helper reads normal SE/protocol diagnostics, kernel HID/SPI/GPI logs,
live DT/driver state, pinctrl/clocks, iptsd journal, `libinput list-devices`
and bounded evtest capability output. It does not mount, load modules,
request/resume an engine, bind/unbind, access raw MMIO, drive GPIOs or change
modes. Store its output in the normal private device logs. Review/sanitize
before moving conclusions into git.

Preserve D19–D24's working boot policy: default GPU off, speakers off,
`qcom_battmgr` blocked, no thermal/charging changes. The reference also uses
`arm64.nopauth`; no evidence ties that argument specifically to touch, so
keep it as an explicit reference-parity diagnostic if needed rather than
silently changing the global default.

### Image: missed-tap A/B test (2026-10-31)

Operator reports taps that sometimes need repeating; analysis in
[missed-taps evidence](evidence/2026-10-31-missed-taps.md). No kernel change. Stage
[collector/sp11-touch-tap-diag](collector/sp11-touch-tap-diag) at
`/usr/libexec/sp11-touch-tap-diag` (0755, on demand, root, `sp11-touch-tap-diag 30`), install
[userspace/iptsd-sp11.conf](userspace/iptsd-sp11.conf) at `/usr/share/sp11/touch/iptsd-sp11.conf`,
[userspace/sp11-touch-conf-select](userspace/sp11-touch-conf-select) at
`/usr/libexec/sp11-touch-conf-select` (0755) and
[userspace/10-sp11-touch-conf.conf](userspace/10-sp11-touch-conf.conf) at
`/usr/lib/systemd/system/iptsd@.service.d/10-sp11-touch-conf.conf`. The marker is
`sp11_touch_conf=A|B` in the existing boot-medium GRUB environment block (`sp11-esp-env`); the kernel command line
stays static. Confirm the grubenv round trip keeps the unknown variable. Add `python3` use only; no new package.

### Sources / firmware / orchestrator

- **Sources:** pin the v7 messages, six immutable reference commits, original
  Nikkuss QSPI patches and iptsd 3.1.0 source/spec. Research copies/hashes are
  in `out/agents/touch-ref/` and linked evidence; no shared source was edited.
- **Firmware:** no new touch firmware manifest row or DriverStore extraction.
  The reference uses preloaded protocol9; BSRC policy is not SE microcode.
- **Orchestrator:** commission a Claude cross-check of newly imported QSPI
  register/TRE constants and the v7 rebind port; board GPIO/timing values
  already match the merged Claude cross-check. Review uncommitted changes
  and record them; this worker ran no write-capable git command.

## 9. Log

- 2026-10-23: static survey dossier created.
- 2026-10-24: unchanged spi-hid v6 built in minimal BTF configuration;
  disabled board draft and quad/firmware gaps documented.
- 2026-10-28: exported v7; decoded six-pin policy; verified Fedora QUP ELF
  lacks protocol9; drafted unsigned diagnostics/sequencing/binding RFCs.
- 2026-10-29, session 3: traced the complete working SP11 reference and its
  Nikkuss/orvitpng provenance; resolved protocol9 versus GPI selector4,
  hardware dummy clocks and absence of a Linux QSPI firmware payload;
  ported host/GPI/HID/reset code onto v7.3 after current kernel/series with
  separate LCD DT; completed full BTF Image/modules build, enabled and controller-only DT
  validation,
  native iptsd request and combined read-only collector. Status designed
  pending full-series strict lint clearance and independent new-code review;
  no device test or git write.
- 2026-10-30: individually triaged all six upstream v7 warnings and eleven
  checks; 0016–0020 remain clean and all selected patches unchanged. Rechecked
  all 29 current integration patches with sequential `git apply --check`,
  fresh DT-only `CHECK_DTBS=y`, explicit schema and safety/wiring checks.
  Corrected the missing-ply lint environment using an extracted Fedora RPM;
  recorded the container dependency request. Status designed pending upstream
  exception disposition and independent QSPI/rebind cross-check; no full
  kernel build, device test, rebuild request or git write.
- 2026-10-31: missed-tap analysis: iptsd 3.1.0 has no 0C80 preset and no debug logging; ranked causes, A/B profile
  (upstream Surface Laptop Studio 2 values), selector, on-demand tap collector; IRQ trigger (edge falling) matches
  ACPI and the reference, so no patch 0022; no kernel build, device test or git write.
