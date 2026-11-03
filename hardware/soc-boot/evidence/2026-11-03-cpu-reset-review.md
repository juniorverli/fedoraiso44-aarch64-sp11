# CPU topology and reset review, 2026-11-03

Scope: the M16 safe boot `d552c86b-f581-4254-bb9f-61b90d722778` and debug
boots `20079066-0668-4323-bdd3-7ab7584f1c19` and
`16aa40e6-4092-4669-9909-aa18f931b74a`, under
`out/device-logs/m16-20261103/`. Lines below are 1-based in the decompressed
files. These are archived observations, not a new device test. The CPU and DT
snapshots exist only for the safe boot. Hashes below are of the compressed files.

## Topology

**Verified:** The Windows MADT `sources/windows/live-inventory/acpi/apic.dat`
(SHA-256 `50b032d657ad12b06793d4de71f0425d93a143fbf45965645203b40009a038d0`)
has 12 GICCs but enables ten: UID 7, MPIDR `0x10300`, and UID 11, MPIDR
`0x20300`, have enabled flag 0 at offsets `0x268` and `0x3a8` (MPIDRs at
`0x2a0`, `0x3e0`); see `apic.dsl:188` and `:280` and the byte-level review in
[2026-10-30 evidence](2026-10-30-cpu-topology.md). The catalog identifies the
MADT and PPTT as data, not code. PPTT `pptt.dat` SHA-256
`e29bf901a1111537626b8f9d9483424b8fa4d24d4841a0c24b710710f4018a04`,
`pptt.dsl:156`–`:331`, describes IDs 0–11 in groups 0–3, 4–7 and 8–11;
PPTT describes hierarchy and does not override MADT enabled flags.

**Verified:** Safe `devicetree.dts.gz` (SHA-256
`ebe49fb408a5487d4f357227fba36571564501d36d1118aea8c8b9b6353bc214`),
lines 10905–11147, has exactly the ten CPU nodes with MPIDRs `0`, `100`, `200`,
`300`, `10000`, `10100`, `10200`, `20000`, `20100`, `20200` (hex). Neither
`cpu@10300` nor `cpu@20300` remains, even disabled. Its CPU map has 4 + 3 + 3
entries (lines 10989–11040), and the PSCI CPU power domains for inherited
`cpu7` and `cpu11` are absent (lines 10502–10603). The ten retained CPU nodes
reference the three performance domains. The inherited source nodes are at
`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:161` and `:211`.
The DT label `cpu8` and Linux logical CPU 8 are different naming schemes: debug
boot lines 200–212 show logical CPU 7 starts at MPIDR `0x20000`, not `0x10300`.

**Verified:** Safe `lscpu.txt.gz:4`–`:5` shows 10 CPUs online 0–9;
`cpuinfo.txt.gz:1`–`:90` lists processors 0–9. All three `dmesg.txt.gz:125`,
`:131`, `:180`–`:213` report SLUB CPUs=10, `nr_cpu_ids=10`, nine successful
secondary starts, and ten CPUs brought up. **Inference:** the safe boot DT
matches the ten enabled MADT entries; debug startup MPIDRs match that same
set. No further CPU deletion is indicated for the tested configuration. MADT
does not establish whether the two unavailable CPUs are physically fused off.

## Reset and runtime evidence

**Verified:** A search of each complete archived `dmesg.txt.gz`, including all
contents of `16aa40e6/dmesg.txt.gz`, found no CPU start failure or CPU offline/
online hotplug event after startup, PSCI/SCMI/cpuidle failure, RCU stall,
soft/hard lockup report, kernel panic, oops, or SMMU fault. The logs show
PSCI 1.1 and OSI initialization (lines 54–59, 265–269); each also reports
`MIGRATE_INFO_TYPE not supported` at line 57, without a CPU-start failure. Each reports that the
hard lockup watchdog is permanently disabled because NMI support is incomplete
(safe and `16aa40e6` lines 514–515; `20079066` lines 517–518); each also logs
SBSA watchdog initialization with a 10-second timeout, action=0 (safe line
1062, debug lines 1063 and 1060). Initialization is not evidence of a
watchdog firing, and lack of a hard-lockup report is limited by its disabled
watchdog. Logs are snapshots and can miss the last events of an abrupt reset.

The `16aa40e6` file contains an Adreno `Mx Level 432 not found in the RPMh
list` error at line 1619; `20079066` has the same error at line 1548. This is
a GPU-worker lead, not proof of reset causation. Although the supplied task
describes imported pstore records in `16aa40e6/dmesg.txt.gz`, the archived
file is a single timestamped current-boot log ending at 11:49:13, with a pstore
mount message at line 625 but no identifiable imported pstore record or prior
boot section. No separate pstore-named file was found in this archive. Thus the
contents of an independent pstore record cannot be verified here.

**Verified:** Safe `cpufreq.txt.gz:4`–`:50` and
`cpu-policies.txt.gz:1`–`:72` expose only policy0 / CPUs 0–3, SCMI and schedutil;
its observed current frequency changes across sequential per-CPU reads, and
its recorded policy maximum is 1920000 kHz. Those reads are not simultaneous.
The capture does not establish whether policies for CPUs 4–9 exist later or
prove scaling on them. `cpuidle.txt.gz:1`–`:20` reports nonzero WFI and
`cpu-sleep-0` usage and time for every logical CPU; this is one snapshot and
does not prove later counter advancement or fault-free idle. No frequency,
idle or command-line changes are proposed.

**Inference:** Nothing in the available records supports the specific theory
that the two firmware-disabled cores restart or cause these resets. This does
not rule out an unlogged CPU, power, or other fault. Keep the reset cause open
and investigate the GPU evidence on its own track.

## Input integrity

| File, relative to the boot directory | SHA-256 |
|:--|:--|
| safe `lscpu.txt.gz` | `f5e2d48a20f350945cf5dee0a62264e18c3deed5caa50dee235738f9c9148515` |
| safe `cpuinfo.txt.gz` | `5b5fda12f120ac846a245a5b87b8f4d80c53591b85fb5cdc2f7fad91d9f51ce7` |
| safe `cpufreq.txt.gz` | `34ab9728a65083c2aadff8066fa6bdcaee99b5574f5f842279051a0a31da02a7` |
| safe `cpu-policies.txt.gz` | `ebc8dfc0c72992d402eb5f343d5ea3444079d18616028d9edc1a59c27a8a1181` |
| safe `cpuidle.txt.gz` | `228ce22787ba79cefaaba52b697aa30341c49acbac9f37f83c33b49ead478a53` |
| safe `dmesg.txt.gz` | `88d4af402a35946cbb2049084b439e85b13a8f8d33ceb98898e3447f47f77dfb` |
| `20079066/dmesg.txt.gz` | `512c3a06a87fa2c214d18bc6d318d665247eb63277c6f5115f5ed7d27d66d0ff` |
| `16aa40e6/dmesg.txt.gz` | `15cd6bdd4c949c8e0190652682d7754edbbe4c561a844daf922ca733064c5e0a` |
