# Rev25 menu: ten-boot reset and DTB comparison

2026-11-04. **No device test or fix was performed in this session.** The raw
logs are private under `out/device-logs/m16-20261104-menu/<boot-id>/`; the
figures below omit device identifiers other than boot IDs. The operator reports
that all eight selected debug variants reset and both safe boots completed.
The logs support the recorded cutoffs and safe completions, but do not supply
an independently timestamped reset or its electrical/firmware reason.

## Verdict and grading

**Inference:** an m15 DT-dependent or debug-entry-dependent common factor is a
better discriminator than a necessary MSM/GMU driver, GNOME, GPU pin, GPU
preemption or ACD mechanism. The old m15's omission of both QMP PHY
`orientation-switch` properties is the first A/B to test. It is a real
behavioral difference, not evidence that a double flip, a USB link or a PMIC
reset caused the failure. An enabled GPU DT node with MSM absent, GPUCC/SMMU,
USB-C, NVMe/PCIe, a shared rail, debug-only services and EFI-pstore arguments
remain possible, including interactions. A single failure or survival does
not establish necessity or sufficiency across boots.

**Unknown:** hard power loss vs EC/PMIC reset vs watchdog vs firmware hang vs
kernel/software event. A silent power/reset event is compatible with the
truncated streams, not proven by them. Wi-Fi scans and GMU starts are recorded
activity, not reset reasons. The old rev24 preemption-first ranking is
superseded; see the [new matched plan](../rev25-test-plan.md).

## Artifact and effective DTB comparison

**Verified:** private ISO `out/iso/sp11-fedora44-aarch64-kiwi-20261104T000512Z-private.iso`
has SHA-256 `f44ef2696e31a119459751e18c30d63dd89d933052af1a9c658815135ddffebf`.
The audio boundary plan in the shared checkout reports 19 entries and L0/L1
pass; those checks are not a device result. This ISO does not contain the
closed-loop audio guard-lifetime candidate. The audio plan retains S1/D26 and
its separate muted closed-loop boundary.

Read the ISO9660 directory and embedded FDT structure directly, comparing
node paths and property byte strings (not DTS source comments or the current
worktree). Both trees have the same 1,506 node paths, reserve map and boot CPU.
The **only three** differing properties in the tested ISO are:

| Effective node/property | Old m15 | m15-safe |
|:--|:--|:--|
| `/soc@0/gpu@3d00000` `status` | `okay` | `disabled` |
| `/soc@0/phy@fd5000` `orientation-switch` | absent | present, empty |
| `/soc@0/phy@fda000` `orientation-switch` | absent | present, empty |

The embedded m15 DTB SHA-256 is
`029a2ab95f0ca7505b8ad2c4896fb0300b81a66b3bf40a15787f10c56c0b9d31`;
the embedded safe DTB is
`5c51dc43058d60193f2280c2c899ef5f39649b607c44f1a5ca877ec0cd81d712`.
The shared checkout's m15 source has since removed the two deletion blocks,
but this worker has **not** verified the rebuilt DTB or a new ISO. The worker
checkout still has the old source, so do not mistake its contents for the
orchestrator's new artifact. Actual booted DTB identity and the new artifact's
full effective diff must be verified for the next trial.

## All ten boots

These are the eight **last published `/dev/kmsg` records**, with the start of
the last 200 records (not metadata continuation lines). Raw records have
monotonic microsecond timestamps. Safe has no debug-only live-kmsg file, so its
last journal record and collector status are given instead. `COMPLETE` means
the collector completed; the quoted journal bound is independently later than
the recorded collector uptime. A final durable line is not the exact instant
of reset. Boot order is `SEQ`.

| Seq | Entry / boot ID | Result; last published time (s) | Start of last 200 kmsg records (s) |
|:--|:--|:--|:--|
| 1 | debug `25663556-00bc-4e38-9a87-dd71c06297bb` | reset; 59.764004, ath12k 11d scan start | 34.292235 |
| 2 | test-acd-off `4cbaff14-dd4c-4a27-8135-456bc3c2aa6e` | reset; 59.704481, ath12k 11d scan start | 34.294445 |
| 3 | safe `e1f5555f-e9a8-4f83-8d35-2b5ff2349c8a` | COMPLETE; status uptime 114.75, journal last 118.465540 | no live kmsg |
| 4 | test-pinoff `23554396-9cf2-46a1-b657-29161dab68ce` | reset; 84.707661, GMU HFI start returned 0 | 52.893226 |
| 5 | test-msm-off `c8dbb8f5-6986-414d-8a0e-65ed1867611f` | reset; 68.715710, ath12k 11d scan start | 35.395293 |
| 6 | test-softgl `20d011b1-25f2-4c26-ad3c-e19e12540c7b` | reset; 61.261507, journald stream FD sent | 54.978092 |
| 7 | safe `c7139de9-bae1-46f4-8a87-6c743162d524` | COMPLETE; status uptime 119.05, journal last 122.644252 | no live kmsg |
| 8 | test-preempt-off `a33220e8-c6a2-4c91-89d1-2cde7af0a9c5` | reset; 60.755872, ath12k 11d scan start | 35.304928 |
| 9 | test-multi-user `6163b0a0-d8b9-473c-bea1-42a80a908464` | reset; 59.827480, ath12k 11d scan start | 34.259829 |
| 10 | test-ignore-unused `264e9eeb-3dca-48ea-9b02-9a932380a201` | reset; 53.475946, journald stream FD sent | 34.637502 |

A first-match text classification of each saved 200-record debug window is
below. `Other` is mainly Bluetooth setup, HDMI ELD and rfkill messages; the
FastRPC/GLINK category includes routine and failed events. These are countable
log-message categories, not counts of hardware operations. No separate
USB/Type-C, PCIe/NVMe, PMIC/regulator/ICC record matched in these windows.

| Seq | Wi-Fi/MHI | systemd/audit | GPU trace | FastRPC/GLINK | Other |
|:--|--:|--:|--:|--:|--:|
| 1 | 71 | 105 | 0 | 4 | 20 |
| 2 | 66 | 105 | 0 | 9 | 20 |
| 4 | 27 | 101 | 48 | 5 | 19 |
| 5 | 130 | 48 | 0 | 5 | 17 |
| 6 | 14 | 178 | 0 | 0 | 8 |
| 8 | 59 | 105 | 0 | 16 | 20 |
| 9 | 134 | 23 | 0 | 29 | 14 |
| 10 | 66 | 106 | 0 | 8 | 20 |

For reproducibility, SHA-256 of `kmsg-live-<boot-id>.txt`, in seq order 1, 2,
4, 5, 6, 8, 9, 10:

```text
c9ec760dbb14fae1decc1b18bf838900e7af7f1be3c715dcd1e36b60c047a999
48a13587f4486b9bbc27b8fa14f56650307dfdee9f5356171247f1520620abea
a6027ac7ca2bc284bca94d995f6bb5b558db207a35d62161324de89a6ab52e6c
76dda9cfabbaa2f24d6babcff274c4f06eb29c17bd50af7576dc90c09a24f7c2
be339d785c45c1848f376e72adb61eecce361af7e94010443ca3b77f937ddb50
6b70a6a11d1dfd5ad492319a1a88cc8162fbca2d354b2729a144cfe4b42059ef
1929723267ace9eaff22c8ac12148b8aba276ac36c66edf68ed95b84ee033329
b7d8ae1ef15fb62b6ed93b2fd798e67744da6e23135a475c20fdbdb7ad0186b3
```

Safe `journal.txt.gz` SHA-256: seq 3
`e3d8a7b314fb41e66ac82062fbda585eaaa0d5ecfb11109663a7d0ddb9c02ad6`;
seq 7 `a7490e44bb505d93de987e13abf9558764f7999773e0e17333cc23ecb01be0be`.
Their last 200 *kernel journal* messages span 34.534405–87.960058 and
34.269513–84.237024 s, respectively; later journal records are userspace.

**Coverage:** all eight saved debug streams have kernel sequence numbers from
0 continuously through the last saved record. That checks the saved prefix,
not loss after it. The publisher batches nonurgent output for up to 10 s,
uses a bounded queue and a separate boot-medium publisher; USB/storage,
scheduling, errors or reset can lose further records. The supplied ftrace
files are snapshots: seq 4 ends at 46.372616 s and seq 5 at 36.491745 s,
well before their kmsg cutoffs. The debug session journal snapshots likewise
end early (seq 4: 52.600272/52.285284 s; seq 5:
45.921867/45.693853 s); multi-user has no session snapshots. They are not
continuous observations of the reset.

## What was actually observed

- **MSM-off:** seq 5 cmdline includes `module_blacklist=msm` and
  `sp11.gpu_pin=0`; live kmsg explicitly reports `Module msm is blacklisted`
  and repeated pin-skip messages. `lsmod.txt.gz` has no MSM; sampled GPU and
  GMU `runtime_status` are both `unsupported`, with `control=auto`.
  The GPU platform device still appears and is added to an IOMMU group; the
  GMU platform device exists. No GMU firmware-start trace occurs. The GPU node
  is **not** disabled merely because its driver is blacklisted. Snapshot
  hashes: `gpu-runtime-pm.txt.gz`
  `51b8ca831239961791decb0f4492f55e794eea77a71a7f44dd6d8eac64c0ed2a`;
  `lsmod.txt.gz`
  `203fc1dfecd94e722269d03163e607e3273ba121d487497e6b673e594b966b71`.
- **Debug-service exposure:** the repository's `sp11-kmsg-tail` is debug
  gated; its separate publisher periodically appends and syncs to the verified
  boot-medium FAT filesystem (`image/overlay/usr/libexec/sp11-kmsg-tail`;
  `image/overlay/usr/libexec/sp11-log-collector:644`). The saved boot-ID streams
  establish that publication occurred, but the installed script bytes were not
  separately attested here. The normal collector also writes in safe, so this
  is a candidate difference, not proof that a write caused reset. All eight debug streams say the CDSP experiment did not
  run because its opt-in marker was absent or unreadable. The GPU two-step
  service requires `sp11.gpu_diag=1`, absent from these command lines
  (`hardware/gpu/collector/sp11-gpu-two-step.service:4`); do not assert its
  state hooks ran solely from `sp11.entry=debug`.
- **Other variants:** seq 4 records pin-skip messages, sampled GPU/GMU
  `auto`/`suspended`, and 13 GMU firmware-start entries; its last HFI start
  returns 0. These starts alone do not prove a suspend cause or a reset. Seq 2
  logs `Skipping GPU ACD probe`; seq 8 requests preemption-off; seq 9 requests
  `multi-user.target`; seq 6 requests software GL via a systemd environment
  argument; seq 10 requests `regulator_ignore_unused`. A requested parameter
  or target is not a full runtime readback, nor does software GL prove every
  process used software rendering. `regulator_ignore_unused` does not hold
  every rail/domain at a physical voltage or prevent all PM transitions.
- **Wi-Fi/PCIe:** the seq 5 Wi-Fi PCIe link comes up at 29.541047 s;
  scan starts at 52.372042 and 68.715710 s. Safe seq 3 starts the same scan
  at 51.343411, 59.947267, 76.273359 and 86.048430 s and continues.
  Safe seq 7 starts one at 59.836471 s and continues. Debug seq 4 ends on
  GMU, and seq 6/10 on journald. Thus the common final scan text does not
  identify ath12k or PCIe as the cause. Correctable **NVMe** PCIe/AER errors
  occur early in some debug boots and safe seq 7 at 31.220203–31.220883 s;
  they are not a reset-aligned fatal Wi-Fi PCIe report.
- **USB-C:** seq 5 sees PMIC-GLINK port 1 raw orientation 1 at 5.262394 s,
  retimer orientation `0 -> 2` at 5.265927 s, switch return 0 at 5.269892 s,
  `conn_status=23/00/00` at 5.274015 s and QMP mode 0 to 2 at 5.359467 s.
  Safe seq 3 sees the same raw orientation, retimer tuple, successful switch
  and QMP mode at 5.608014, 5.841010, 5.840880 and 5.918531 s. The Type-C
  boot medium is enumerated at high speed in both. These are early control
  events; neither PHY lane register readback nor a reset-aligned detach or
  electrical fault is supplied. Seq 6 has retimer `2 -> 0 -> 2` around
  5.556938–5.568687 s, but still does not prove a cause.
- **PMIC / interconnect / regulator:** both failing and safe logs include
  early PMIC-GLINK `Failed to create device link` messages; e.g. seq 5
  4.072919 s and safe seq 3 4.219651 s for supplier `3-0008`. These are
  software device-link messages, not a measured PMIC shutdown. The seq 9
  last-200 window contains FastRPC endpoint timeout/failure around
  34.791183–34.793002 s; the same failure is present in both safe boots,
  including seq 7 34.785011–34.785107 s. No reset-aligned PMIC brownout,
  overcurrent, thermal trip, ICC failure, fatal PCIe error or GPU fault is
  recorded in the available tails. `regulator_summary.txt.gz` and ftrace
  are earlier snapshots of Linux's reported state and requests, not continuous
  electrical measurements; no inference of stable physical voltage follows.
- **Watchdog / pstore / EFI:** both following safe boots record SBSA watchdog
  `bootstatus: 0` and `status: 0x0`. The pinned driver sets `WDIOF_CARDRESET`
  when the sampled WS1 bit is set (`sources/linux/drivers/watchdog/sbsa_gwdt.c:345`),
  but firmware/reset retention and timing are unknown, so zero does not rule
  out any watchdog or other reset. The SBSA driver initialized with a 10 s
  timeout, which is not proof it expired. EFI variables registered and debug
  requested EFI pstore; no pstore payload or backend-registration message was
  found in these captures. Prior consumption, backend registration, firmware
  retention and collection errors are unresolved. Empty/missing pstore is not
  evidence that no panic occurred. Source shows that `pstore_disable` controls
  EFI backend initialization (`sources/linux/drivers/firmware/efi/efi-pstore.c:22`),
  while `always_kmsg_dump` changes which reasons reach registered dumpers
  when a dump occurs (`sources/linux/kernel/printk/printk.c:4827`, `:4864`);
  the latter is not evidence of a periodic operation at the observed cutoff.

## Orientation and shared-supply analysis

**Verified source:** `ps883x_sw_set()` forwards orientation to its connected
switch before updating/caching the retimer state
(`sources/linux/drivers/usb/typec/mux/ps883x.c:269`); the Type-C framework
matches a remote switch by `orientation-switch` and makes a NULL switch a
successful no-op (`sources/linux/drivers/usb/typec/mux.c:35`, `:94`, `:215`).
The QMP callback records orientation and may reinitialize an active PHY;
QMP starts at NORMAL and uses a port-select bit for REVERSE
(`sources/linux/drivers/phy/qualcomm/phy-qcom-qmp-combo.c:4776`, `:5214`,
`:4064`). It registers switch and mux when **either** property is present
(`:5252`); consequently removing the orientation property changes graph
matching while leaving the mode-switch path. Denali connects each PHY through
a PS8830 to PMIC-GLINK (`sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:741`,
`:807`, `:1270`, `:1300`). Linux models orientation and mode as separate
logical operations ([kernel Type-C documentation](https://www.kernel.org/doc/html/latest/driver-api/usb/typec.html)).

**Inference:** old m15 can leave the QMP orientation at its normal default
while the PS8830 is set for a reverse notification; restoring the property
restores orientation forwarding. This is a meaningful experiment for the
observed attach. It does **not** prove the resulting lane map, board wiring,
a harmful "double flip", a PMIC event, or a reset mechanism. The earlier
[USB-C independent verdict](../../usb-typec/evidence/2026-10-31-double-flip-verdict.md)
notes that multiple upstream boards including a Surface Laptop use both
switches. The old single-analyst double-flip claim cannot establish this
board's wiring or Windows behavior.

**Verified DT wiring, not a voltage measurement:** in the old m15 embedded
FDT the same `vdda-pll-supply` phandle links both Type-C QMP PHYs
(`/soc@0/phy@fd5000`, `/soc@0/phy@fda000`), the NVMe PCIe PHY
(`/soc@0/phy@1bfc000`) and DP PHY (`/soc@0/phy@aec5a00`) to regulator
`vreg_l2j_1p2`. The pinned source names these PHYs and supplies at
`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:2829`, `:2900`, `:3520`,
`:5976` and `x1-microsoft-denali.dtsi:930`, `:974`, `:1270`, `:1300`.
The Wi-Fi PCIe PHY uses a *different immediate supply*, `vreg_l3e_1p2`
(`x1-microsoft-denali.dtsi:941`); source assigns that regulator and
`vreg_l2j_1p2` the same upstream `vreg_s5j_1p2` parent (`:599`, `:685`).
The DT graph supports investigating a shared upstream path, not a proven
physical rail disturbance, PCIe fault or GPU-to-Wi-Fi rail identity. GPU
interconnect and GMU GPUCC domains are separately described at
`hamoa.dtsi:4013`, `:4175`, `:4201`.

## Windows REA and candidate

The catalog lists active Type-C UCSI, qcpep, PMIC, PMIC-apps and Surface
system-management `.sys` files as ARM64 PE code requiring forced Ghidra
`AARCH64:LE:64:v8A` (`sources/binary-catalog.tsv`). This session attempted the
read-only REA `binary_session` call and received `MCP tool call requires
approval, but approval policy is never`; no `rea` executable was on PATH.
No new binary was opened, no procedure address or REA evidence ID was
obtained, and no Windows QMP/PS8830/PMIC/EC sequence can be asserted. The
older Type-C report's auto-detected language and abbreviated evidence IDs do
not satisfy protocol §9 for a new verified conclusion. Prior compliant GPU
REA `0x140431488`,
`ev_3397a1efbf71cceec903316395b30d6453bd4d6e34ba0bca2cebd9ffb1e9480a`,
is a configuration-file loader, **not** evidence about this reset or Type-C.
Request sources owner access to an approved forced-language REA process; list
procedures before targeted decompilation and record binary hash, function
address, complete evidence ID and limits.

**Candidate:** no new GPU or kernel patch. The owner is already preparing the
narrow m15 orientation restoration as a diagnostic DTB, not a proven fix.
Keep that candidate isolated, compare effective DTBs, and run the matched
MSM-off pair in the [test plan](../rev25-test-plan.md). No GPU/GMU
power-control writes, thermal/frequency changes, speaker-output tests, IR,
flash, firmware writes or Windows-partition writes are authorized here.
