# Revision 24 final34: GPU and platform reset investigation

Date: 2026-11-03. This is a read-only analysis of existing device captures and
the rev24 build tree, plus a public-source search. No new device boot, REA
decompilation, kernel build, or reset fix was performed. The current procedure
is the [rev25 GRUB matrix](../rev25-test-plan.md).

## Judgment

**Inference, leading investigation:** GPU/GMU activity or a shared platform
power/firmware path is a better next test target than another camera patch.
The safe boot processes camera frames with the GPU platform device absent and
survives; the debug boot initializes the GPU and the operator reports a reset
5–10 s after the desktop appears. This is a comparison across different boot
entries, not a controlled GPU-only experiment. The debug capture does not prove
that no camera app ran after its session journal stopped. Shared PMIC, EC,
thermal, watchdog, firmware, display and other debug-entry differences remain
possible. A reset reason and causal domain are **TBD**.

Use the same rev24 image for an instrumented, no-camera control and then first
vary **`msm.enable_preemption=0`**. This is a diagnostic ordering choice: the
catalog enables preemption by default, and disabling it also changes ring and
scheduler behavior. It does not specifically test Oct patch 6. A later
`sp11.gpu_pin=0` boot tests the effect of the existing pin. ACD-off is last,
idle only: ACD is a droop-related clock-throttling mechanism, and the default
debug trace contains an AOSS enable request. See the safety and readback
conditions in the plan. Do not infer a fix from one surviving boot.

## Captures and exact bounds

All paths below are under `out/device-logs/m16-20261103-final34/`; hashes refer
to the exact compressed or raw files in each boot directory. Both boots identify
`7.3.0-65.sp11.24.fc44.aarch64`. Their command lines are not identical: among
other things they select `sp11.entry=debug` versus `safe`, and the debug line
has EFI-pstore parameters. Their behavior cannot be attributed to one change.

### Debug `e28d7229-c3d9-40c3-8bdd-3ab5635f13a8`

- **Verified:** early GPU-only `power/control` write/readback `on` at
  **4.762537 s**, before GPU `load begin` at **5.055563 s**. The first GMU
  firmware start begins **5.079789 s**, returns 0 **5.084486 s**; HFI returns 0
  **5.085499 s**; the initial overall GPU runtime resume and hardware init
  return 0 at **5.103939** and **5.123783 s**. GMU firmware reports v4.3.17.
  The pin is repeated at **29.824656** and **30.612121 s**. The snapshot
  reports GPU `on`, active, `runtime_suspended_time=0`; GMU `auto`, active,
  suspended time 85 ms. `gpu-runtime-pm.txt.gz` SHA-256
  `bd855866950deda4680df191d67aabcfcd65926b1b60492fc6d1a0124bf5e686`.
  These are software states/samples, not measurements of IFPC or rails.
- **Verified:** exactly one GMU start marker appears in the captured live
  kmsg, ending **59.148154 s** (preceding line 59.148133 s; last lines are Wi-Fi
  frequency-range updates). No second start is recorded in this window. The
  earlier [M16 boot](2026-11-02-resume-comparison.md) had four starts, but is a
  different boot. A start marker denotes entry into the instrumented GMU resume
  path, not necessarily autosuspend: recovery or other paths may enter it.
  `kmsg-live-e28d7229-c3d9-40c3-8bdd-3ab5635f13a8.txt` SHA-256
  `bf36d57a3538c60d3738efb8cf21cb8c936e542a202d582b7d608a4ad78d2490`.
  The operator-reported reset was after the last durable record; its exact
  monotonic time and cause are unknown. The last Wi-Fi messages do not identify
  a cause. No reset-aligned panic/oops or reset reason is in the supplied tail.
- **Verified:** the trace is a snapshot, not a live trace; its last event is
  **29.804516 s**, about 29.34 s before the final kmsg, and its enabled event
  list did not request `rpm:rpm_*` or `:mod:msm`. Its header reports 4058/4058
  entries *at snapshot*, not loss-free coverage through the reset. It shows an
  AOSS `{class: gpu, res: acd, val: 1}` send at **5.003827 s** and successful
  return at **5.008388 s**. That verifies the host request, not live ACD
  residency or a reset mechanism. `trace.txt.gz` SHA-256
  `847f518a78c0717d5cb0f8ae3633abdd3bc49359317256a5549c49beb7a3ac96`.
- **Verified:** the first and user session journal snapshots end at
  **34.855212** and **35.189910 s**, respectively, before the last kmsg.
  Their hashes are `3db876eb424e932c303e067852ca0f4f4fe487f10a930790bd24093e4640b288`
  and `fc26a435205972bce5a194c8a606abc22d959e2783d0edab53cdacca1474acc2`.
  They do not establish whether Snapshot or another camera app was opened in
  the unrecorded interval. In fact the automatic image collector itself ran
  `cam -l` at **38.905–43.697 s**; its file expressly says enumeration only,
  no capture, and it lists both sensors. `extra-cameras.txt.gz` SHA-256
  `b560ff3b3866f5faaeaa8c425531cdaa02be8cc35baf43fa4cd9aa25b4b50ed1`.
  Enumeration is not a stream. No complete debug session journal, marked
  camera action, completed frame or desktop GPU-submit trace was supplied;
  first initialization and a render node do not by themselves prove GNOME
  actually submitted hardware-rendering jobs.
- **Verified:** the sampled devfreq ceiling is 1.25 GHz, current frequency
  300 MHz, with fuse 7 in `gpu-speed-bin.txt.gz`; this is not a continuous
  frequency or voltage record. `gpu-speed-bin.txt.gz` SHA-256
  `63fc441286c07b06e3d8f7e516fbb77a8f05d859096619b85c6d95268160d101`;
  `gpu.txt.gz` SHA-256
  `70b8ff93706ba662559060caf4aab8a697fbdc8e5026e8386774a0f4b88ed424`.
  The SBSA watchdog initialized with a 10 s timeout; no actual watchdog reset
  reason is captured. The raw archive contains no pstore payload. Configured
  pstore is not evidence of a registered, retained backend.

### Safe `f736d653-ea76-4073-a5f7-08478e70b7d6`

- **Verified:** `STATUS` records uptime **167.75 s**, and `COMPLETE` exists;
  the journal shows a normal session shutdown near that time. Snapshot starts
  at **88.893573 s**, calls the camera portal at **90.907020 s**, and exits
  successfully at **165.394292 s**. The safe WirePlumber process configures
  1920x1080 streams at **91.356528** and **103.392289 s**; at **93.573895**
  and **105.585229 s** it reports processing 30 debayer frames in each batch.
  Additional configurations occur at **125.687633**, **143.860842**, and
  **150.068942 s**. Both OV13858 and IMX681 were separately enumerated; the
  operator reports seeing both rear and front previews. The provided INFO
  lines do not themselves tag each 30-frame batch with a sensor ID, so that
  mapping is operator evidence, not a logged per-frame identity. A frame batch
  is stronger than enumeration, but does not establish image quality.
  `journal.txt.gz` SHA-256
  `06f22c07697e9bb1d8508d4248edaa9dc95556ad50628b0f838a21ed60f77814`;
  `extra-cameras.txt.gz` SHA-256
  `1e53ff366b9954a3093736ac744fe315f285dd9382d95aa53746bd9fcc2b822f`.
- **Verified:** the journal starts `/usr/libexec/sp11-wireplumber-safe` at
  **54.493875 s**. The image's matching helper sets `GALLIUM_DRIVER=softpipe`
  and `LIBGL_ALWAYS_SOFTWARE=1` for `sp11.entry=safe`
  (`image/overlay/usr/libexec/sp11-wireplumber-safe:8-11`); its environment or
  actual renderer was not independently dumped. EGL initialization errors in
  the journal do not negate the later logged software debayer batches.
- **Verified:** `/sys/bus/platform/devices/3d00000.gpu/power/*` is absent;
  GMU runtime status is `unsupported`. Turnip cannot obtain a GPU ID and
  Xwayland falls back to software. `/dev/dri/renderD128` exists even in safe,
  so that node alone is not evidence of Adreno work. `gpu.txt.gz` SHA-256
  `f19f12158099eb3841ba8eda15f8050643fd027effb61b0784b4cd8a34c58db9`;
  `gpu-runtime-pm.txt.gz` SHA-256
  `bbad976fc870930f55ca4b04dc4b6a0cc39e5807ca16d3cb2299df1834a91eaf`.
  **Inference:** this boot supports camera processing without an initialized
  Adreno GPU; it does not prove that every possible GPU-associated shared
  domain was physically off or that every camera condition is safe.

## Rev24 source and October 24 candidates

The rev24 RPM build log identifies
`out/build/kernel/rpmbuild/BUILD/kernel-7.3.0-build/kernel-7.3/linux-7.3.0-65.sp11.24.fc44.aarch64/`
as the build source and applies GPU 0003 and 0004 at
`out/build/kernel/rpmbuild.log:829,839`. This is source/build correlation,
not binary attestation. In that tree `drivers/gpu/drm/msm/adreno/a6xx_gmu.c`
SHA-256 is `ab51d854a1f28cb3bfb9d60f7a5136980562278105a8e36de423edaac7e9d49d`;
`a6xx_gpu.c` is `c52d741cfaaa34fb65aaf20db14421b47f2c683ebbe42ffa9407b6c63671326e`.
The backport's `a6xx_gmu_scales_bw()` and clear occur at rev24 `a6xx_gmu.c:79`
and `:1397-1401`. Debug still reset; the clamp and stale-vote backport are
therefore insufficient *in this boot*, not disproved for every failure.

| Candidate | Source/evidence | Decision |
|:--|:--|:--|
| [1: BX index](https://lore.jethome.com/lkml/20261024-assorted-fixes-oct-v1-1-2977f974ddb7@oss.qualcomm.com/) | No `gbx`/GMU BX vote path in rev24 MSM Adreno source. | Not applicable as posted; do not backport. |
| [2: GMU shutdown idle](https://lore.jethome.com/lkml/20261024-assorted-fixes-oct-v1-2-2977f974ddb7@oss.qualcomm.com/) | Relevant idle-check code exists (`a6xx_gmu.c:265-295,1456` in rev24), but no shutdown/slumber failure or reset-aligned suspend is captured. Early GPU pin and zero sampled suspended time weaken ordinary GPU runtime-suspend as the necessary trigger. IFPC and recovery are not excluded. | Defer; request PM trace and preserve as a source candidate. |
| [4: devfreq idle time](https://lists.openwall.net/linux-kernel/2026/10/24/420) | Rev24 `msm_gpu_devfreq.c:294-336,341-374` still timestamps in delayed idle work; canceled work can leave a stale timestamp and cause a spurious boost, as the 2026-10-24 proposal explains. The sampled 300 MHz does not exclude earlier boosts. | Real source defect, but no measured boost or reset link; no behavioral patch/frequency change for this experiment. |
| [5: scheduler priority](https://lists.openwall.net/linux-kernel/2026/10/24/425) | Rev24 `msm_gpu.h:543-559` retains the inversion; `include/drm/gpu_scheduler.h:68-75` has kernel/high/normal/low in reversed ordering. `msm_submitqueue.c:136-156` uses the result. This supports the upstream priority-mapping defect. | Real source defect, but no reset-aligned queue/priority or starvation evidence. Do not bundle it into the first test. |
| [6: preemption records](https://lists.openwall.net/linux-kernel/2026/10/24/427) | Rev24 still has the proposed suspend/resume record issue; chip `0x43050c01` has preemption and IFPC quirks (`a6xx_catalog.c:1573-1588`), and auto preemption selects four rings (`a6xx_gpu.c:2750`). The proposal specifically concerns stale records after GPU power collapse/suspend and later preemption; neither sequence is captured here. | Defer patch pending sequence. Preemption-off is a broader diagnostic and cannot prove patch 6 is the fix. |
| [7: CLX](https://lore.jethome.com/lkml/20261024-assorted-fixes-oct-v1-7-2977f974ddb7@oss.qualcomm.com/) | Rev24 has no `clx_tbl` infrastructure in its MSM Adreno sources and this chip catalog has no CLX table. | Not applicable as posted; do not invent prerequisites. |

**Other paths:** `disable_acd` and `enable_preemption` are MSM module parameters
in rev24 `adreno_device.c:19-25`. ACD is assembled from OPP properties and
reported to AOSS (`a6xx_gmu.c:2011` onward); the trace verifies the default
enable request in this boot. Qualcomm describes ACD as clock throttling during
voltage droop ([2025-04-22 ACD series](https://lore-kernel.gnuweeb.org/dri-devel/20250422-beneficial-fractal-otter-ebd1d2%40kuoka/T/));
`module_param_unsafe` is not an assurance of safety. IFPC is selected in the
chip/GMU path, but no supported IFPC-off boot switch or physical residency is
established here. Do not invent one. The GPU pin is not a GMU pin and cannot
disable autonomous IFPC. `sp11.gpu_pin=0` makes both image helpers skip their
GPU write (`image/overlay/usr/libexec/sp11-gpu-{pm-early,no-runtime-pm}:9`);
verify skip and actual `control`, not just the command line.

Early initramfs GPU load and firmware placement may affect ordering; this boot
successfully loaded firmware and completed initial GPU init before the session.
There is no evidence that early versus late initialization causes the reset;
removing initramfs firmware would also change availability and is not a clean
single-variable test. No new kernel patch or kernel build is requested.

## Windows sequence and REA availability

Protocol §9 order was followed through Linux source, public upstream, ACPI and
captured INF/registry before attempting REA. `sources/windows/live-inventory/acpi/dsdt.dsl:67096`
identifies `QCOM0CF7`; `thermal/thermal-query.txt:431-440,2178-2179` identifies
the active GPU-limits PEP and the selected qcpep image. The captured registry
`camera/reg_flash_pmicapps.txt:78,95` identifies active qcpmicapps and qcpmic
images; that binding does not prove they implement the GPU power sequence.
The actual Surface EC handler and its role are not established.
The three source files have SHA-256, respectively:
`8a7b849b9ac2148a9806d967612eb0d5195020c3e29ffd834b837767256a8ede`,
`d088dce5f2e84d49fd475bb424be89744235c84f913d09246d8c858b9a05adfa`, and
`99414746da102c373240793b34b4e90bf14eb16bd145ef67103542fb0a7b77c2`.

All five requested candidates were first checked in `sources/binary-catalog.tsv`
and SHA-256 verified. All are PE ARM64 code, requiring forced Ghidra language
`AARCH64:LE:64:v8A`:

| DriverStore binary | SHA-256 |
|:--|:--|
| `qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkm8380.sys` | `46237eba1c2c0a51d700cdf14730aae3f41b0a55775a185b87e618cab8285814` |
| `qcpep.wd8380.inf_arm64_eb671871f8fef501/qcpep8380.sys` | `e5bdeb8c0fb8823990f7520a19c00807711cf909f91f8d67db78ffb18c1b2277` |
| `qcpmic8380.inf_arm64_70a073eda9e484fb/qcpmic8380.sys` | `756b5c2e4eb8d5a2bdc0dcc0f7f5703eef79dec0c963155c54e42097bc2f790e` |
| `qcpmicapps8380.inf_arm64_714225d945ee24ad/qcpmicapps8380.sys` | `8418c2739e6d969a0c791d937a09f583eeeacd70e866126d9362b2f56d13cca7` |
| `surfacesystemmanagementframeworkdriver.inf_arm64_43935ab23e5514e6/SurfaceSystemManagementFrameworkDriver.sys` | `c2e5ed8db4e767fe5f3cb9b43b926f502b6c8e6aaaf72c9b52b77adf19b6ff5e` |

The read-only REA MCP `binary_session` call was rejected: `MCP tool call
requires approval, but approval policy is never`. No `rea` executable was found
on PATH. No binary was opened under an unattested automatic language. The only
prior compliant GPU REA procedure `0x140431488`, evidence
`ev_3397a1efbf71cceec903316395b30d6453bd4d6e34ba0bca2cebd9ffb1e9480a`,
is a configuration-file loader, not a collapse handler. Older
[Windows notes](2026-10-30-rea-windows.md) used auto-detection and explicitly
fail §9.2; their power-order claims cannot establish a verified comparison.
**TBD:** Windows GPU power-collapse, ACD, IFPC and PMIC/EC ordering. Sources
owner: restore a forced-language, approved REA provider; inventory procedures
first, then find and decompile the relevant callers, recording each binary,
hash, function address, evidence ID and unresolved indirect calls. Do not
manufacture a sequence from strings.

## Public project check (accessed 2026-11-03)

- [dwhinham X1P issue #6](https://github.com/dwhinham/archiso-aarch64-sp11/issues/6)
  reported a GNOME black screen on 2025-03-18 and then suggested software
  rendering for an X1P without a working GPU driver; it was closed 2026-09-26.
  This historical result is not a diagnosed current desktop reset. Its
  [Arch image](https://github.com/dwhinham/archiso-aarch64-sp11) names
  [linux-sp11](https://github.com/dwhinham/linux-sp11) as the kernel and
  describes vendor-firmware setup.
- [dwhinham issue #25](https://github.com/dwhinham/archiso-aarch64-sp11/issues/25),
  opened 2026-03-16, reports a freeze/reboot in GRUB on an X1E, before Linux's
  desktop; it is not the present symptom or evidence of an Adreno reset.
- [jglathe SP11 discussion #57](https://github.com/jglathe/linux_ms_dev_kit/discussions/57)
  includes a 2026-02-26 X1P LCD Ubuntu setup using the matching DTB and
  Microsoft GPU firmware for acceleration; it does not diagnose this reset.
  [Fedora Surface setup](https://github.com/rjindael/fedora-surface-pro-11)
  targets an X1E and documents firmware/boot setup, not this X1P desktop reset.
- [postmarketOS trailblazer MR 5616](https://gitlab.com/postmarketOS/pmaports/-/merge_requests/5616)
  adds initfs modules and firmware for X1 Elite laptops (2024); it is not an
  X1P64100 reset workaround. Targeted postmarketOS SP11/X1P searches produced
  no matching primary report. Search coverage is limited; this does not prove
  that no report or workaround exists. No public source found supports
  attributing this reset to IFPC, ACD or a PMIC rail.
