# ec-sam

## 1. Summary

The Surface Aggregator Module, Microsoft's embedded controller, reached over UART2. It carries the Type Cover (keyboard, touchpad), battery and AC, tablet-mode switch, performance profile and fan. Linux 7.3 has the SSAM driver and a `sp11` device group for `microsoft,denali`. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_MSHW&DEV_0084 (serial hub)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_MSHW&DEV_0153 (KIP hot plug)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_MSHW&DEV_0040 (buttons)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_MSHW&DEV_0005 (laptop/slate)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_PNP&DEV_0C0D (lid)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_PNP&DEV_0C0B (fan)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_ACPI&DEV_000E&SUBSYS_MSHW0217 (wake alarm)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_MSHW&DEV_0299` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `HID\Target_KIP&Category_HID` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `UEFI\RES_{632cbe1c-c56f-4c43-b309-87e5da648d16} (SAM)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `surfaceserialhubdriver` | TBD |
| `surfacesam` | TBD |
| `surfacehidminidriver` | TBD |
| `surfacehotplug` | TBD |
| `surfacebattery` | TBD |
| `surfacebutton` | TBD |
| `surfacepowerstate` | TBD |
| `surfacetimealarmacpifilter` | TBD |
| `surfaceacpiplatformextensiondriver` | TBD |
| `surfacesystemmanagementframeworkdriver` | TBD |
| `surfacesmfclient` | TBD |
| `surfaceihvcpusmfclient` | TBD |
| `surface.smf.117.0.*` | TBD |
| `surfacetypecoverv7fwupdate` | TBD |
| `surfacetypecoverv7fprudedriver` | TBD |
| `surfacecfuoverhid` | TBD |

## 4. Linux 7.3

- Driver: `platform/surface/aggregator (microsoft,surface-sam)`
- Driver: `surface_aggregator_registry (group sp11)`
- Driver: `surface_aggregator_hub`
- Driver: `surface_hid`
- Driver: `surface_battery`
- Driver: `surface_charger`
- Driver: `surface_aggregator_tablet_switch`
- Driver: `gpio-keys (lid)`
- DT: `x1-microsoft-denali.dtsi &uart2 embedded-controller, gpio-keys`
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| volume buttons (MSHW0040) not described | TBD |
| sp11 group lists penstash: present on this unit? | TBD |
| keyboard backlight control | TBD |
| Type Cover fingerprint reader (UDE driver) unknown | TBD |
| fan/perf profile over SAM | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which SSAM devices in the `sp11` group exist on this unit (e.g. pen stash)? | TBD | `/sys/bus/surface_aggregator/devices` on the device |
| Q2 | Volume up/down and power button wiring (`MSHW0040`) | TBD | DSDT `_CRS` of `MSHW0040` (GPIO or PMIC) |
| Q3 | Keyboard backlight command | TBD | REA of `SurfaceHidMiniDriver.sys` / KIP traffic |
| Q4 | Fan and performance profile requests | TBD | REA of the SMF fan/thermal clients; `surface_platform_profile` |
| Q5 | Type Cover fingerprint reader: what bus and protocol? | TBD | `surfacetypecoverv7fprudedriver` INF and REA |

## 7. Acceptance

1. Keyboard and touchpad work with the cover attached and detached
2. Battery percentage and AC state correct
3. Tablet mode toggles when folding the cover
4. Volume and power buttons emit key events

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
