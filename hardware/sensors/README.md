# sensors

## 1. Summary

Motion, orientation and light sensors attached to the ADSP sensor core (SSC). Windows reaches them through `MSHW048A`/`MSHW048B`; Linux has no kernel driver and reaches the SSC from userspace over FastRPC/QMI. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_MSHW&DEV_048A&SUBSYS_MSHW0487` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_MSHW&DEV_048B&SUBSYS_MSHW0487` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `Simple Device Orientation Sensor` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcsensors` | TBD |
| `surfacepro_snscfgcrd8380` | TBD |
| `sensorshidclassdriver` | TBD |
| `sensorsalsdriver` | TBD |
| `sensorsservicedriver` | TBD |

## 4. Linux 7.3

- Driver: `misc/fastrpc`
- Driver: `userspace: hexagonrpcd, libssc, iio-sensor-proxy`
- Nothing in the DT.
- Native coverage: **none** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| no kernel driver: SSC is reached over FastRPC/QMI from userspace | TBD |
| physical sensor chips unidentified | TBD |
| sensor registry/config files from the ADSP package | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which physical chips are present? | TBD | Sensor registry/config files in `surfacepro_snscfgcrd8380` and the ADSP package |
| Q2 | Is the Linux userspace stack (`hexagonrpcd`, `libssc`, `iio-sensor-proxy`) packaged for Fedora 44? | TBD | Fedora/Copr search |
| Q3 | Which registry files must be installed and where? | TBD | Compare with other X1E laptops using libssc |

## 7. Acceptance

1. Screen rotates with the device
2. Automatic brightness reacts to ambient light

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
