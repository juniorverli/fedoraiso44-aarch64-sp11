# touch-pen

## 1. Summary

The touchscreen and pen digitizer, a Microsoft Touch G6 controller (`MSHW0484`) speaking HID over SPI. The pen is a HID collection of the same device. Linux 7.3 has no HID-over-SPI transport. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_MSHW&DEV_0484&REV_0001` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `HID\VEN_MSHW&DEV_0484&REV_0001&Col01..Col0A` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C0E&SUBSYS_MSHW0489 (SPI)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `hidspi_km (inbox)` | TBD |
| `qcspi8380` | TBD |
| `surfacedigitizerwotextnpackage` | TBD |
| `surfacetouchg6fwupdateextnpackage0c80` | TBD |
| `surfacetouchg6fwupdateextnpackage0c83` | TBD |
| `surfacetouchpenprocessor0c80update` | TBD |
| `surfacetouchpenprocessor0c83update` | TBD |
| `surfacepenblelcaddradaptationdriver` | TBD |
| `surfacepen0c0ffirmwareupdate` | TBD |
| `surfacepenwirelesschargerhotkey` | TBD |

## 4. Linux 7.3

- Driver: `spi-geni-qcom`
- Nothing in the DT.
- Native coverage: **none** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| no HID-over-SPI driver in 7.3 | TBD |
| no DT node for the touch controller | TBD |
| GENI SE may come up unprogrammed (protocol 0) | TBD |
| SPI speed, IRQ, reset and supply GPIOs from ACPI _CRS/_PS0/_RST | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | SPI bus, chip select, max speed, mode, interrupt GPIO and trigger | TBD | ACPI `_CRS` of the `MSHW0484` device in `live-inventory/acpi/dsdt.dsl` |
| Q2 | Reset and supply GPIOs and the power-on timing | TBD | `_PS0`/`_PS3`/`_RST` methods in the DSDT; REA of `hidspi_km` is inbox, so the protocol is the public Microsoft HID-over-SPI spec |
| Q3 | Is there an upstream HID-over-SPI series to backport, and which revision? | TBD | lore.kernel.org, linux-input; the Microsoft/Google `spi-hid` series |
| Q4 | Does the SPI GENI engine come up programmed? | TBD | `dmesg` for `geni_spi` on M2 |
| Q5 | Which collections are needed for touch, pen, pen buttons and eraser? | TBD | HID report descriptor read on the device |

## 7. Acceptance

1. 10-finger touch with correct orientation in GNOME
2. Pen pressure, tilt, barrel button and eraser in a drawing app
3. Touch wakes the panel follower (panel on/off) correctly

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
