# soc-boot

## 1. Summary

Everything the kernel needs before any peripheral works: CPUs, PSCI, cpufreq, idle states, clocks, interconnect, SMMU, GPIO and PMIC pin controllers, QUP serial engines, the device tree itself. Phase 1 only needs a stable boot to GDM. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| SoC | Snapdragon X Plus X1P64100, "Snapdragon(R) X 10-core X1P64100 @ 3.40 GHz" | Verified | `pnp-present.json` (`ACPI\VEN_ACPI&DEV_0007`, 10 instances) |
| CPUs in DT | 12 `cpu@` nodes | Verified | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi` |
| CPUs present | 10; which two of the 12 are fused off is TBD | Verified (count) / TBD (which) | `pnp-present.json`; `live-inventory/acpi/pptt.dsl`, `apic.dsl` (MADT) |
| DTB | `qcom/x1p64100-microsoft-denali.dtb` | Verified | `sources/linux/arch/arm64/boot/dts/qcom/Makefile:473` |
| Boot exception level | EL1 (so the `-el2` DTB does not apply) | Hypothesis | Check `dmesg` "CPU: All CPU(s) started at EL1" on M2 |

## 3. Windows

`qcpep.wd8380` (power engine plug-in: clocks, power rails, per-device power sequences), `qcppx8380` (PCIe PEP), `qcsmmu8380`, `qciommu`, `qcgpio8380`, `qcpmic*`, `qcspmi8380`, `qcscm`, `qcsyscache8380`, `qcgpi8380`, `qci2c8380`, `qcspi8380`, `qcuart8380`, `qcipcc8380`, `qcglink8380`. `qcpep8380.sys` is the main reverse-engineering target when a power sequence is unknown for any component.

## 4. Linux 7.3

PSCI, `cpuidle-psci`, SCMI cpufreq, `gcc-x1e80100`, `interconnect/qcom/x1e80100`, `arm-smmu`, `pinctrl-x1e80100`, `pinctrl-spmi-gpio`, `spmi-pmic-arb`, `qcom_scm` (`microsoft,denali` allowlisted for QSEECOM at `drivers/firmware/qcom/qcom_scm.c:2326`), `geni-se`, `qcom-pdc`.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Two CPU nodes without a core | DT patch deleting the two absent CPUs and their references (cpu-map, idle domains, cpufreq domains) in `x1p64100-microsoft-denali.dts`, once Q1 is answered |
| Kernel command line | Start without `clk_ignore_unused`/`pd_ignore_unused`; add only with a log that justifies it |
| QUP engines may be unprogrammed | GENI loads `qupv3fw.elf` only for protocol 255 in some paths; check on M2 which engines report protocol 0 (affects touch SPI, I2C) |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which two cores of the 12-core die are absent (MPIDR values)? | TBD | MADT GICC entries and PPTT in `live-inventory/acpi/`; `dmesg` "failed to boot CPU" lines on M2 |
| Q2 | Are all idle states in `hamoa.dtsi` safe on this firmware? | TBD | M2 boot; stress idle |
| Q3 | Does the vanilla kernel boot without `clk_ignore_unused`? | TBD | M2 |

## 7. Acceptance

Ten CPUs online, cpufreq scaling on all clusters, no PSCI errors, boot to GDM three times in a row.

## 8. Requests

- image: log collector dumps `/proc/cpuinfo`, `/sys/devices/system/cpu/*/cpufreq`, `cpuidle` stats, `clk_summary`, `regulator_summary`, `pinctrl` (debugfs).

## 9. Log

- 2026-10-23: dossier created from the static survey.
