# soc-boot

## 1. Summary

Everything the kernel needs before any peripheral works: CPUs, PSCI, cpufreq, idle states, clocks, interconnect, SMMU, GPIO and PMIC pin controllers, QUP serial engines, and the device tree. Status: `designed`; the M16 safe DT has the correct ten-CPU topology, while packaged DT integration and broader runtime acceptance remain open. See [M16 evidence](evidence/2026-11-03-cpu-reset-review.md).

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| SoC | Snapdragon X Plus X1P64100, "Snapdragon(R) X 10-core X1P64100 @ 3.40 GHz" | Verified | `pnp-present.json` (`ACPI\VEN_ACPI&DEV_0007`, 10 instances) |
| CPUs in upstream DT | 12 `cpu@` nodes; this patch reduces the LCD board to ten | Verified | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi` |
| CPUs enabled by firmware | 10; UID 7 / MPIDR `0x10300` and UID 11 / MPIDR `0x20300` are disabled | Verified | MADT `sources/windows/live-inventory/acpi/apic.dat`, SHA-256 `50b032d657ad12b06793d4de71f0425d93a143fbf45965645203b40009a038d0`; GICC offsets `0x25c`, `0x39c`; [evidence](evidence/2026-10-30-cpu-topology.md) |
| Physical fusing of those CPUs | Firmware-disabled cores are treated as unavailable; MADT does not establish the physical fuse mechanism | Inference | Same MADT flags and ten-core SKU |
| Remaining topology | 4 + 3 + 3 CPUs across the three existing SCMI performance and PSCI cluster domains | Verified (DT) | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:66`; compiled-patch checks in the evidence |
| DTB | `qcom/x1p64100-microsoft-denali.dtb` | Verified | `sources/linux/arch/arm64/boot/dts/qcom/Makefile:473` |
| Boot exception level | EL1 (so the `-el2` DTB does not apply) | Hypothesis | Check `dmesg` "CPU: All CPU(s) started at EL1" on M2 |

## 3. Windows

`qcpep.wd8380` (power engine plug-in: clocks, power rails, per-device power sequences), `qcppx8380` (PCIe PEP), `qcsmmu8380`, `qciommu`, `qcgpio8380`, `qcpmic*`, `qcspmi8380`, `qcscm`, `qcsyscache8380`, `qcgpi8380`, `qci2c8380`, `qcspi8380`, `qcuart8380`, `qcipcc8380`, `qcglink8380`. `qcpep8380.sys` is the main reverse-engineering target when a power sequence is unknown for any component.

## 4. Linux 7.3

PSCI, `cpuidle-psci`, SCMI cpufreq, `gcc-x1e80100`, `interconnect/qcom/x1e80100`, `arm-smmu`, `pinctrl-x1e80100`, `pinctrl-spmi-gpio`, `spmi-pmic-arb`, `qcom_scm` (`microsoft,denali` allowlisted for QSEECOM at `drivers/firmware/qcom/qcom_scm.c:2326`), `geni-se`, `qcom-pdc`.

The inherited `hamoa.dtsi` has `cpu7` at line 161, `cpu11` at 211, their map references at 255/273, and PSCI CPU domains at 423/447. SCMI performance-domain references are properties of the CPU nodes themselves; deleting the two CPUs removes those references without deleting any shared performance domain. CPU C4, cluster CL4/CL5 and system SS3 are defined at 281/292/300/308, respectively; the system domain references SS3 at 473. `purwa.dtsi:13` provides the upstream pattern for removing inherited CPU/map/PSCI nodes.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Packaged LCD DTB integration of CPU/idle parity remains unconfirmed; M16 safe variant already has ten CPUs | [0001](patches/0001-arm64-dts-qcom-denali-lcd-boot-parity.patch) deletes `cpu7`, `cpu11`, `cpu_pd7`, `cpu_pd11`, cluster1/cluster2 `core3`, and the system SS3 reference. LCD board only; all three clusters and CL4/CL5 remain. Integration requested below |
| System SS3 safety unknown | Preserve D20's existing exclusion; no evidence establishes SS3 as a reset cause. Re-enable only as a separate controlled experiment |
| Kernel command line | D20 currently retains `clk_ignore_unused pd_ignore_unused rootdelay=10`; necessity remains unisolated. This patch changes no command line |
| QUP engines may be unprogrammed | GENI loads `qupv3fw.elf` only for protocol 255 in some paths; check on M2 which engines report protocol 0 (affects touch SPI, I2C) |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 (closed for tested M16 topology) | Must two more CPUs be disabled or are the absent cores restarting? | Verified / Inference | MADT disables UID 7 / `0x10300` and UID 11 / `0x20300`; the safe live DT omits both and all three boots start ten matching CPUs. No evidence implicates those absent cores in resets. Physical fusing and reset cause remain unproven; independent patch cross-check remains pending. |
| Q2 | Is system SS3 safe and needed? Do retained idle states work correctly? | TBD | Existing parity excludes SS3; batched read-only idle counters and a later isolated SS3 experiment |
| Q3 | Can the D20 clock/power-domain workarounds be removed? | TBD | Separate boot comparison after a stable integrated baseline |

## 7. Acceptance

Ten CPUs online, cpufreq scaling on all three clusters, no PSCI CPU-start errors, and boot to GDM three times in a row. M16 establishes ten-CPU startup and one idle snapshot; it does not establish all-policy scaling or three stable cold boots. See [test-plan.md](test-plan.md).

## 8. Requests

- **R-O1, orchestrator:** obtain the independent Claude cross-check required by protocol §5.1 before promotion to `sw-ready`. Give the checker the pinned MADT and upstream board/SoC DTS inputs without this worker's conclusions; ask it to derive unavailable MPIDRs, map/domain deletions and retained performance/idle domains. Have it write under `hardware/soc-boot/crosscheck/`. Review and commit these uncommitted component files per D24.
- **R-K1, kernel:** integrate the DT patch and variant/checker migration together, in this order:

  1. Append `hardware/soc-boot/patches/0001-arm64-dts-qcom-denali-lcd-boot-parity.patch` **once**, after the current complete `kernel/series`. It was tested on pinned `v7.3` plus all 29 current patches. Keep this DT change separate from driver changes. Bump `kernel/base.toml` to the next unused `series_rev` (currently 8) and recalculate `series_sha256` with `bash -c '. scripts/kernel-common.sh; kernel_series_hash'` after finalizing the series.
  2. Keep the historical parity file for builders using old source snapshots. For the **new series only**, replace the parity file in the builder's staging directory with this shim **before** `kernel-dev.sh variant` copies the DTS files. The integrated series already supplies all deletions; do not apply 0001 a second time in a variant builder. This staging-only migration was validated for every parity-based variant, including both M10 variants:

     ```dts
     // SPDX-License-Identifier: BSD-3-Clause
     /* Parity is supplied by the integrated LCD board patch. */
     #include "x1p64100-microsoft-denali.dts"
     ```

  3. Extend the revision dispatch in `scripts/kernel-dtb-variants.sh` and the release/variant record checks to the new revision; the current M10 helper is pinned to revision 7. Update `scripts/kernel-check` so the new revision actually runs S1, wiring, RPM and schema checks (its current revision 5/6/7 conditional would skip them). Extend `scripts/kernel-m8-check.py` with an explicit packaged-parity mode, e.g. `--parity-in-base`, requiring 10 CPUs, absent CPU/map/PSCI nodes and no system SS3 reference for the new packaged DT; preserve the old revision's 12-CPU expectation. Keep all existing S1, GPU-off, CMA, touch and fallback assertions.
  4. After updating the series, run this concrete scratch-source/DT-only recipe from the repository root. It refuses to overwrite a source directory. The helper takes `flock out/.kernel-build.lock` internally; do not nest an outer lock:

     ```bash
     set -euo pipefail
     test ! -e out/linux/soc-boot-integration
     mkdir out/linux/soc-boot-integration
     git -C sources/linux archive c03c1a14507dfaf8b856c2608f9ac216021fc222 |
         tar -x -C out/linux/soc-boot-integration
     while IFS= read -r patch_path; do
         patch_path=${patch_path%%#*}
         [ -n "$patch_path" ] || continue
         patch --batch --fuzz=0 -p1 -d out/linux/soc-boot-integration < "$patch_path"
     done < kernel/series
     mkdir -p out/build/soc-boot-integration-stage
     cp kernel/dtb-variants/*.dts out/build/soc-boot-integration-stage/
     cat > out/build/soc-boot-integration-stage/x1p64100-microsoft-denali-parity.dts <<'DTS'
     // SPDX-License-Identifier: BSD-3-Clause
     /* Parity is supplied by the integrated LCD board patch. */
     #include "x1p64100-microsoft-denali.dts"
     DTS
     scripts/kernel-dev.sh --check soc-boot-integration dtbs
     scripts/kernel-dev.sh --check soc-boot-integration variant out/build/soc-boot-integration-stage/x1p64100-microsoft-denali-m10.dts
     scripts/kernel-dev.sh --check soc-boot-integration variant out/build/soc-boot-integration-stage/x1p64100-microsoft-denali-m10-notouch.dts
     ```

     Require zero `CHECK_DTBS` and explicit `dt-validate` diagnostics, both BTF config symbols set, and S1 effective-status success. Compare the new packaged DTB and M10 default against `out/dtb-variants/7.3.0-65.sp11.7.fc44.aarch64/qcom/x1p64100-microsoft-denali-m10.dtb` byte for byte, and the fallback against the corresponding `m10-notouch.dtb`. Require the fallback's only DT change to be the touchscreen status. Exact validation commands and hashes are in the evidence.
  5. For the next packaged delivery, the **kernel owner** runs `scripts/kernel-build.sh -j 6`, then `scripts/kernel-build.sh --check-only`, then the updated `scripts/kernel-dtb-variants.sh`. These release helpers own the shared build lock. The existing 60 GiB release-headroom guard must pass; this session's dev logs reported 29 GiB. Verify the RPM-extracted LCD DTB equals the validated parity DTB, BTF exists in vmlinux and modules, and the new series/revision/hash are recorded. This worker has deliberately not run that full build.

- **R-I1, image:** after integration, batch the exact read-only commands in [test-plan.md](test-plan.md) into the next collector. Retain speakers off (S1), GPU off (D22), D23's battery-manager restriction and D20's current command line. No extra reboot is requested solely for this patch. Private raw logs stay in `out/`; only sanitized conclusions enter git.

- **R-I2, image (historical; superseded by read-only M16 follow-up):** M16 shows SCMI policy0 active but has no captured policy for CPUs 4–9. Collect all policies at multiple times as in the test plan; do not change frequencies for this investigation. Previously: `scmi_cpufreq` is `CONFIG_ARM_SCMI_CPUFREQ=m` and never loads, because its SCMI device exists only after the module registers (no autoload alias). Add `image/overlay/etc/modules-load.d/sp11-cpufreq.conf` containing `scmi_cpufreq`, ideally opt-in for the first boot, with governor `schedutil` and `scaling_max_freq` capped to a mid-range level from `scaling_available_frequencies` (never `performance`); extend L0 and the collector (already records cpufreq). See [evidence](evidence/2026-10-31-cpufreq.md).
- **R-K2, kernel (optional):** `CONFIG_ARM_SCMI_CPUFREQ=y` in `sp11.config` at the next planned build; not needed for R-I2.
- **R-T1, power-thermal / orchestrator:** after the first cpufreq boot, soc-boot writes patch 0002 (passive 104000 mC or lower plus cpufreq cooling-maps, criticals only lowered); S6 forbids any raise.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-30: resolved Q1 from MADT bytes; wrote LCD-only DT parity patch; checked full-series application, DT schemas, S1 and variant equivalence without a full build; requested independent cross-check and kernel-owner integration (D24, uncommitted).
- 2026-10-31: root cause of missing cpufreq found (module never autoloaded; DT and config sound); requested image modules-load entry; evidence in `evidence/2026-10-31-cpufreq.md`.

- 2026-11-03: reviewed M16 CPU/DT and reset logs; closed the absent-core question for the tested topology, recorded the incomplete cpufreq coverage and pstore limitation, and updated the read-only test plan.
