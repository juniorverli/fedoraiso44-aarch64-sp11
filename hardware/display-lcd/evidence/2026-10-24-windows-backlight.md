# Denali LCD backlight and power evidence

## Pinned local inputs

Paths are relative to `sources/windows/`; each was looked up in
`sources/binary-catalog.tsv` before inspection.

| Label | Path | SHA-256 | Catalog interpretation |
|:--|:--|:--|:--|
| IDP | `DriverStore/surface_dxext_8380.inf_arm64_69910c8aa1a39011/qcdxkmext8380_DENidp.bin` | `581d11553cc9961da63b301ee81228f9495acad16983218b45d6329b1982fa47` | data; never disassembled |
| CRD | `DriverStore/surface_dxext_8380.inf_arm64_69910c8aa1a39011/qcdxkmext8380_DENcrd.bin` | `e35fb31ae7ff7ac65a5439675339af4061fbf4dd8a2743a687ccd2cbdac4e740` | data; never disassembled |
| INF | `DriverStore/surface_dxext_8380.inf_arm64_69910c8aa1a39011/surface_dxext_8380.inf` | `436cf01e504769fca0f53b15296ef34f1bad7caa6ca2fdf357bca4281faa23cf` | text |
| DSDT | `live-inventory/acpi/dsdt.dsl` | `8a7b849b9ac2148a9806d967612eb0d5195020c3e29ffd834b837767256a8ede` | text, derived ACPI |
| DX | `DriverStore/qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkm8380.sys` | `46237eba1c2c0a51d700cdf14730aae3f41b0a55775a185b87e618cab8285814` | ARM64 code; `AARCH64:LE:64:v8A` |
| PEP | `DriverStore/qcpep.wd8380.inf_arm64_eb671871f8fef501/qcpep8380.sys` | `e5bdeb8c0fb8823990f7520a19c00807711cf909f91f8d67db78ffb18c1b2277` | ARM64 code; `AARCH64:LE:64:v8A` |

## Extension selection and format

**Verified:** INF line 63 matches the unit's `IDP08380&REV_008A` to the IDP
installation section; line 132 selects DENidp as `AcpiExtFile`. CRD is a
different hardware-ID installation. The brightness maxima in lines 144–149
also differ (600000 IDP, 900000 CRD); these do not encode PWM duty cycles.

**Verified structure:** both blobs begin with a 52-byte header, magic
`0x80807070`, revision 1, ten directory entries, and `8380_DEN_EXT`. Each
12-byte directory entry has a four-byte method name, offset and length.
Every method body has `AeoB`, length and argument count, then packed ACPI
method arguments (`uint16 type`, `uint16 length`, data of at least four bytes).
Integer payloads have eight bytes; strings are NUL terminated; type 3 holds
nested arguments. The helper `tools/decode-static.py` checks all directory
boundaries, body lengths, root counts, argument lengths and string endings
in both blobs. This is a data-format decode, not Ghidra output.

**Inference (format meaning):** these are serialized ACPI evaluation results
used as method overrides. The method names and corresponding DSDT packages
provide independent semantic context; no executable header or CPU is implied.

## Q1: method and wiring

**Strong Inference:** the LCD uses an external PMIC PWM backlight. The evidence
combines the unit-selected IDP override, its extra GPIO setup absent from CRD,
the matching DSDT data, and a posted patch for this exact LCD board with a
reported LCD test. No DPCD dump has been captured locally, so AUX backlight
capabilities remain unknown; their presence would not by itself disprove the
board's external PWM wiring.

Raw configuration records below are **Verified** at the stated offsets in IDP
(SHA above). Numeric record fields are recorded without guessing their enums.

| Operation | Offset | Selected argument values |
|:--|:--|:--|
| FSTATE ENTER, TLMM power pin | 0x0f78 | `TLMMGPIO [70, 0, 0, 0, 1, 0]` |
| FSTATE ENTER (power-down), delay | 0x0fd5 | `DELAY [500]`, unit ms established by independent PEP REA |
| FSTATE ENTER, HPD pin | 0x0ff3 | `TLMMGPIO [119, 1, 0, 0, 1, 0]` |
| FSTATE ENTER, PMIC inputs | 0x1050 / 0x10c8 / 0x1140 | PMIC/index pairs `3/9`, `3/3`, `0/4` |
| FSTATE EXIT, TLMM power pin | 0x150b | `TLMMGPIO [70, 1, 0, 1, 3, 7]` |
| FSTATE EXIT, HPD pin | 0x1568 | `TLMMGPIO [119, 1, 1, 0, 0, 0]` |
| FSTATE EXIT, PMIC supply pin | 0x15c5 | `IOCTL_PM_GPIO_CONFIG_DIGITAL_OUTPUT [3, 9, 0, 1, 10, 2, 4]` |
| FSTATE EXIT, PMIC enable pin | 0x1656 | `IOCTL_PM_GPIO_CONFIG_DIGITAL_OUTPUT [3, 3, 0, 1, 10, 2, 4]` |
| FSTATE EXIT, PMIC PWM pin | 0x16e7 | `IOCTL_PM_GPIO_CONFIG_DIGITAL_OUTPUT [0, 4, 0, 0, 4, 2, 4]` |

Matching DSDT evidence (SHA above): HPD at lines 5175–5186; the three output
records at 5189–5234. DSDT `G0MD` at 23105 selects between board packages by
TBID. Do not assume an arbitrary reference `_ROM` panel is the selected LCD.
CRD has only the `3/3` PMIC output at 0x14a7 and does not have the IDP's
`3/9` or `0/4` entries in G0MD (Verified, CRD SHA above).

| Required value | Conclusion and grade | Reason/citation |
|:--|:--|:--|
| PWM controller / channel | PMK8550 LPG (**Inference**), proposed Linux PWM index 0 (**Hypothesis after cross-check**) | Exact-board posted patch proposes 0, but independent Windows evidence names no channel; Linux maps index 0 to base 0xe800 at `sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:1814`, not proof of routing |
| PWM pin / mux | PMK8550 GPIO5, `func3` (**strong Inference**) | IDP `0/4` zero-based pair plus exact-board patch; Linux controller at `sources/linux/arch/arm64/boot/dts/qcom/hamoa-pmics.dtsi:265` |
| Requested PWM period / frequency | 5000000 ns / 200 Hz (**strong Inference**) | Exact-board, LCD-tested posted patch; this matches, but is not proved by, reference XML |
| Actual Windows PWM resolution | **TBD** | Reference `gpu0-rom-0.xml` says 12 bits, but describes B133HAN05.3; it is not a board measurement |
| Linux resolution | Selected by LPG driver from subtype and requested period (**Verified source behavior**) | `sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:417`, `:452`; no fixed 12-bit property is added |
| Backlight enable | PMC8380_3 GPIO4, active high (**strong Inference**) | IDP `3/3` pair + exact-board patch; existing Linux names it `edp_bl_en` at `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1008` |
| Backlight supply enable | PMC8380_3 GPIO10, active high (**strong Inference**) | IDP `3/9` pair + exact-board patch; voltage is **TBD**, so no voltage is invented in DT |
| Panel logic supply enable | TLMM GPIO70, 3.3 V (**Verified existing DT; Windows pin corroborated**) | `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:128`; IDP 0x150b |
| HPD | TLMM GPIO119, `edp0_hot` (**strong Inference for board mux**) | IDP 0x1568 + DSDT + `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:6110` + exact-board posted HPD patch |

The interpretation of Windows GPIO indices as one less than the physical
PMIC GPIO numbers is an **Inference**, corroborated by the exact-board patch
and the pre-existing Linux GPIO4 enable, independently reproduced by the
Claude cross-check. See [Q1/Q2 reconciliation](2026-10-24-crosscheck-reconciliation.md)
for agreements and differences, including resolution and the power-down wait.

Patch 0003 remains held: func3 requires an LV/MV pad
(`sources/linux/drivers/pinctrl/qcom/pinctrl-spmi-gpio.c:323`), while this
unit's PMK8550 GPIO5 subtype is **TBD**. M2 must establish the subtype and
DPCD backlight capabilities before review can release the patch. First
integration is 0001/0002 only; absence of a pinctrl error without 0003 applied
does not establish support for that mux.

## Upstream search, 2026-10-24

Found Dale Whinham's 2026-10-17 series, with reported OLED and LCD testing:

- [Cover letter](https://lists.openwall.net/linux-kernel/2026/10/17/1092)
- [HPD message](https://lists.openwall.net/linux-kernel/2026/10/17/1001), message ID `20261017-sp11-lcd-fixes-v1-1-0eb916c01a3d@gmail.com`
- [Backlight message](https://lists.openwall.net/linux-kernel/2026/10/17/1002), message ID `20261017-sp11-lcd-fixes-v1-2-0eb916c01a3d@gmail.com`

These are the original mailing-list messages via an archive mirror. Lore raw
requests returned HTTP 403. HTML copies stay outside git in
`out/rea/display-lcd/upstream-lcd-{hpd,backlight}.html`; their SHA-256 values are
`117e56190d6e82aa75b9a0f0209ff435bd6a683311389f072a50ad33e5862960` and
`d08b50bd796ec117d1d68283375a87d7b3d5bb955037ecfbfe2e04757b2806e6`.
No claim of upstream acceptance is made. Searches for 0x077b and
LP129WT342166 did not identify a panel-edp addition.

Local patches 0002/0003 adapt those diffs without changing their DT values.
Their `Fixes` footer is omitted because this repository's squashed v7.3 base
does not contain the referenced historical commit; the upstream Link is kept.
No upstream Tested-by is attached to local testing performed here.
