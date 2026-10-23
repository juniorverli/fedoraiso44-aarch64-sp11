# soc-boot worker

**Owns:** `hardware/soc-boot/` (write). Everything else is read-only.
**Phase:** 1 (only what blocks a boot to GDM), 4 (the rest). **Kernel worktree:** yes (`out/linux/soc-boot`, branch `w/soc-boot`).

## Mission

A vanilla-7.3-based kernel that boots this machine to GDM reliably, with the device tree matching the silicon: ten CPUs, correct idle and frequency domains, no unexplained command-line workarounds.

## Start

1. Read `hardware/soc-boot/README.md` and `component.toml`.
2. Q1 first: identify the two absent cores.

## Specific leads

- **CPUs (Q1).** `sources/windows/live-inventory/acpi/apic.dsl` (MADT GICC entries: MPIDR, enabled flags), `pptt.dsl` (clusters). Compare with the `cpu@` nodes, `cpu-map`, power domains and SCMI performance domains in `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi`. Check how other X1P SKUs in the tree handle fused-off cores (`x1p42100.dtsi`, `purwa.dtsi`) and whether upstream has a pattern for deleting CPU nodes in a board DTS.
- **Idle (Q2).** List the idle states of `hamoa.dtsi`; note any known issues on lore for X1 laptops; mark which ones need device evidence.
- **Command line (Q3).** Decide the default kernel command line for the first ISO (as small as possible) and send it to the image worker as a request with the reason for each argument.
- **QUP engines.** Write the `dmesg` filters the image worker's log collector needs to tell which GENI engines report protocol 0.

## Deliver

1. `patches/`: the CPU-node patch, upstream-style, with MADT evidence cited.
2. `evidence/<date>-cpu-topology.md`.
3. `test-plan.md`: `nproc`, `lscpu`, cpufreq per policy, `cpuidle` usage, three cold boots.
4. Dossier and `component.toml` updated.

## Do not

- Disable idle states or add `clk_ignore_unused`/`pd_ignore_unused` without a log that shows the failure.
