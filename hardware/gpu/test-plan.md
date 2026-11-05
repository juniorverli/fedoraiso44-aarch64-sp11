# Current reset plan: revision 25 menu

The current plan is the [matched restored-orientation and safe-DTB debug matrix](rev25-test-plan.md), based on the [ten-boot evidence](evidence/2026-11-04-rev25-menu-reset.md). It supersedes all older instructions below, including their GPU pin, ACD, preemption, workload and additional kernel-test proposals. No GPU or GMU power-control writes, thermal/frequency changes or speaker-output test are authorized in the current matrix. No device test or new kernel build was performed in this session.

---

# Revision 23: controlled reset discriminator — 2026-11-03

This section supersedes the revision-22 and earlier reset capture instructions below. **No test was run.** Safe remains default; debug retains the existing early GPU-only `on` pin, GMU is read-only. Keep the same DTB, AC/battery, peripherals, desktop, login, ambient conditions and logging across the matched control and patched debug boots. No camera app or automatic camera capture in the GPU-only boot. No IR/flash, thermal/frequency change, GMU `power/control` write, ACD/preemption change, or speaker-policy change. First check recovery, thermal gate and free space. Stop after the first reset, collect evidence on safe, and only resume the remaining matrix after the operator has the logs and recovery is confirmed. Report every failed/missing event or collector. These short diagnostic actions are not the 30-minute acceptance load.

## Kernel and image owner preflight

1. Keep revision-22 clamp and BTF. Include tracing and runtime PM event support; verify actual built config and actual booted tracefs events, not only config. Set debug kernel command line to the following **single** `trace_event=` argument (merge it into any existing list, never duplicate/replace required events):

   `trace_clock=mono trace_event=:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg,interconnect:icc_set_bw,interconnect:icc_set_bw_end,rpm:rpm_suspend,rpm:rpm_resume,rpm:rpm_idle,rpm:rpm_return_int,rpm:rpm_status,power:device_pm_callback_start,power:device_pm_callback_end,drm_msm_gpu:*:mod:msm trace_buf_size=16M`

   The requested `power:runtime_*` names do not exist in pinned v7.3 `include/trace/events/power.h`; runtime-PM events are in `include/trace/events/rpm.h` as `rpm:rpm_*`. Include power callback events as complementary evidence. Rev22 has `CONFIG_DRM_MSM=m`; the `:mod:msm` suffix retains the request until module load (`Documentation/trace/events.rst:55`). Verify enabled events after msm loads and before action, otherwise explicitly enable with `echo 'drm_msm_gpu:*' >> /sys/kernel/tracing/set_event`. Keep existing event entries. Record `available_events`, `set_event`, buffer overruns and clock selection. The trace only records enabled instrumented sites, not the GMU's internal IFPC state or a physical rail.
2. Start live trace and kmsg capture **early**, ideally initramfs after mounting the verified writable boot medium and before first GPU load; preserve early ring when handing off to the single trace_pipe reader. The manual commands below begin only when run and cannot recover overwritten events. Require a boot-ID-named directory, live kmsg plus trace, bounded free-space policy, reported write/sync errors and no automatic pruning of the failing boot. Confirm progress and heartbeats; per-second fsync limits but does not eliminate loss, and USB/controller cache or reset can lose the last data. Boot-medium I/O and tracing can change timing; repeat with same instrumentation.
3. On a safe boot, preserve prior `/sys/fs/pstore` and `/var/lib/systemd/pstore` before any tests or cleanup. Verify actual registered pstore backend and mounted pstore. If `/dev/pmsg0` exists, write a uniquely labelled non-sensitive sentinel, sync, perform a normal warm reboot, copy both raw pstore and systemd-pstore archive to boot medium, then verify the sentinel and provenance persist through another reboot. Do not induce a panic or assume EFI pstore supplies pmsg. Rev22 config has EFI pstore and pmsg enabled but `CONFIG_PSTORE_RAM=m` (`out/build/kernel/rpmbuild/BUILD/kernel-7.3.0-build/kernel-7.3/linux-7.3.0-65.sp11.22.fc44.aarch64/.config:2610,12848`); configured is not registered or retained. If no qualified backend/sentinel, explicitly record that pstore recovery is unverified and keep the A/B interpretation bounded. Any new ramoops reservation needs the separate ownership and retention checks in historical notes below; do not blindly add one.
4. Retain successful GPU pin before first open; log its exact path, write/readback, time and errors, plus read-only GPU and GMU `control`, `runtime_status`, `runtime_suspended_time`, all firmware/HFI start results, initial and final status, kernel/DTB/ISO hashes and command line. Preserve actual pstore payloads with original filenames and previous boot ID before systemd-pstore or cleanup consumes them. Build and identify the control and patch-0004 diagnostic kernel variants described below; image instrumentation is requested.

## Live capture and markers

The image owner should implement this from early userspace; the following is an explicit root-shell manual fallback, run on the **device** after tracefs and the confirmed writable boot-medium filesystem are mounted. Substitute `LOGROOT` only after checking `findmnt -T` and free space; it must be a directory on the boot medium, not `/run`, the live overlay, or Windows. This starts one destructive consumer of trace_pipe: do not run another trace_pipe reader. Preserve prior files and never run cleanup. `sync -f` depends on GNU coreutils; record any failure. This procedure cannot guarantee a hard-reset tail survives.

```sh
# Root shell; replace path with the verified mounted boot-medium directory.
LOGROOT=/mnt/BOOT-MEDIUM/sp11-rev23
findmnt -T "$LOGROOT" || exit 1
df -h "$LOGROOT" || exit 1
BID=$(cat /proc/sys/kernel/random/boot_id)
D="$LOGROOT/$BID"
mkdir -m 700 "$D" || exit 1
T=/sys/kernel/tracing
mountpoint -q "$T" || mount -t tracefs tracefs "$T" || exit 1
cat /proc/cmdline > "$D/cmdline.txt"
cat "$T/trace_clock" > "$D/trace-clock.txt"
cat "$T/available_events" > "$D/available-events.txt"
# msm must already be loaded here; the boot argument requests earlier events.
for e in rpm/rpm_suspend rpm/rpm_resume rpm/rpm_idle rpm/rpm_return_int rpm/rpm_status power/device_pm_callback_start power/device_pm_callback_end; do
    test -e "$T/events/$e/enable" || { echo "MISSING $e" | tee -a "$D/errors.txt"; exit 1; }
    echo 1 > "$T/events/$e/enable" || exit 1
done
test -d "$T/events/drm_msm_gpu" || { echo 'MISSING drm_msm_gpu' | tee -a "$D/errors.txt"; exit 1; }
echo 1 > "$T/events/drm_msm_gpu/enable" || exit 1
cat "$T/set_event" > "$D/enabled-events.txt"
cat "$T/trace_pipe" >> "$D/trace-live.txt" 2>> "$D/errors.txt" & TRACEPID=$!
# Existing image kmsg stream should be used; only start one if it is absent.
# This reads new messages from /dev/kmsg; do not replace existing early kmsg.
(dmesg --follow --decode --time-format=raw >> "$D/kmsg-live.txt" 2>> "$D/errors.txt") & KMSGPID=$!
(while kill -0 "$TRACEPID" 2>/dev/null && kill -0 "$KMSGPID" 2>/dev/null; do
    sync -f "$D/trace-live.txt" || { echo 'trace sync failed' >> "$D/errors.txt"; exit 1; }
    sync -f "$D/kmsg-live.txt" || { echo 'kmsg sync failed' >> "$D/errors.txt"; exit 1; }
    sleep 1
done; echo 'collector stopped' >> "$D/errors.txt") & SYNCPID=$!
mark() {
    printf '%s\n' "REV23 $BID $*" > "$T/trace_marker" || return 1
    printf '<6>REV23 %s %s\n' "$BID" "$*" > /dev/kmsg || return 1
    printf '%s uptime=%s\n' "$*" "$(cut -d' ' -f1 /proc/uptime)" >> "$D/actions.txt"
    sync -f "$D/actions.txt"
}
mark capture_ready
```

Check trace lines and kmsg are advancing, the selected clock is `mono`, and `kill -0` succeeds for all three PIDs. Capture `cat /sys/kernel/tracing/per_cpu/cpu*/stats` before and after the action, all status/errors and PM attributes. Avoid dumping unsafe DRM debugfs state. Action output must itself reach the verified medium; image services should capture it and flush it with the action markers. At clean end mark `test_end`, sync, terminate the two readers and sync loop, save event/overrun stats and their exit status, and sync again. A loss, missing marker, no completed action, or reset before action makes that case inconclusive. A live trace last line can precede reset by storage latency and ring overruns; compare with independent kmsg and observed boot time, not as exact reset time.

On the next safe boot **before another debug boot**, copy the existing original boot-ID directory and raw `/sys/fs/pstore` files plus `/var/lib/systemd/pstore` archive to a new durable recovery directory; record source, filenames, hashes and any read errors. Capture available firmware/EC/watchdog reset reason read-only through owner-provided tooling. Never assume an empty pstore means no panic or no hard reset, and never erase records before the copy.

## Kernel A/B and workload matrix

Request a rev22-derived **control** kernel and an otherwise identical **patched** kernel with only [GPU patch 0004](patches/0004-drm-msm-a6xx-clear-stale-boot-bw-vote.patch) added after the existing rev21 RPMh fixes and GPU MX clamp 0003. Kernel owner must review OPP NULL side effects and live GPU OPP dependencies, apply with zero fuzz, build and verify BTF (`CONFIG_DEBUG_INFO_BTF=y`, `CONFIG_DEBUG_INFO_BTF_MODULES=y`) and matching modules. Use distinct kernel release identifiers, images, initramfs/module directories and hashes; verify each booted artifact to prevent cross-loading. Do not bundle Oct 1/2/6/7 or other behavioral fixes. Keep the same DTB and firmware. Image owner: preserve safe as default and provide explicit separate control and patched debug entries, each with the same existing early GPU-only pin, trace and collection, with no automatic retry. Record the actual kernel, module, initramfs, DTB, firmware and image IDs. If a single image cannot hold both unambiguously, use two otherwise matched images and document every difference.

Before action, record boot OPP and host ICC votes read-only, including path/client/aggregate if actually exposed. Enable both `interconnect:icc_set_bw` and `interconnect:icc_set_bw_end` from boot; these trace host requests and return values (`sources/linux/drivers/interconnect/trace.h`), not autonomous GMU bandwidth votes or physical rails. Record failures and event availability. Ask kernel owner for an owner-reviewed read-only diagnostic of `nr_gpu_bws` and the generated table if no existing interface exposes them; do not infer the exact runtime count from source. Compare the initial host request and successful later clear for this GPU, controlling for other ICC clients; an absent clear, failed return or missing trace makes mechanism verification inconclusive.

Run the A/B/C workload rows below on the control and repeat the **same** rows on the patched kernel under matched conditions. At minimum compare the same baseline and action in both variants; collect repeated matched pairs after recovery where practical. Stop after every reset, recover and preserve evidence before any subsequent boot; do not schedule automatic retries. Trace from early boot through at least the 130 s baseline and the action plus 60 s. If control resets before an action, compare that same pre-action interval first; do not claim camera causality. A reproducible control-only reset with patched survival supports a patch association, while both resetting weakens a sole-cause claim and both surviving is inconclusive. Correlate actions, ICC return, GPU jobs/frequency/PM and other events; a trace or pstore gap cannot exclude silent firmware/hardware reset. Other workload or artifact differences invalidate a clean patch A/B.

## Workload rows and inference

All debug action runs in each kernel variant start at matched uptime (target >=130 s, later if capture setup is not ready); observe an idle baseline to at least 130 s on each boot, then at least 60 s after the marked action or after stream ends. A reset before action is a separate baseline result. Use `cam -l` to establish actual index/ID; do not infer LED or sensor identity from index alone. Log command start/end/exit, request/frame count and observable LED, including operator timestamp. Capture with no GUI/preview, no saved images by default, and stop immediately if LED is dark; make a distinct boot for each camera. No automatic retries.

| Boot | Marked intervention | Readout and interpretation |
|:--|:--|:--|
| A debug GPU-only | No camera clients or `cam -l`; mark `gpu_begin`, run `vulkaninfo --summary` and `glxinfo -B`; if the power-thermal owner permits short GPU rendering, run e.g. `timeout 10s vkcube`, then mark `gpu_end` and exit codes. Record renderer and GPU submit events. | Reset before any camera access shows camera streaming is **not necessary in that run**; GPU/display, time, Wi-Fi, unrelated services and shared PM remain candidates. Passing only bounds this particular exposure and workload. `vulkaninfo` alone does not establish actual GPU jobs. |
| B debug rear | Mark `rear_begin` immediately before `LIBCAMERA_LOG_LEVELS='*:INFO' stdbuf -oL -eL cam --camera <observed-rear-index> --capture=120 --metadata`; route output live to boot medium and check exit; mark `rear_end`. Observe LED, negotiated sensor, stream-start messages and increasing completed request sequence/nonzero bytes. | Reset reproducibly after confirmed rear stream but not A strengthens stream-associated H1; it does not prove CAMSS versus stream-induced GPU/CPU/ISP/PMIC/shared-rail load. A launch without completed frames is not a confirmed stream. |
| C debug front | New boot, same procedure, `front_begin` / front ID / `front_end`, no rear stream in this boot. | Same logic independently for front. Rear-only vs front-only correlations narrow sensor/path candidates but do not establish the faulty component; failure to reach confirmed stream is inconclusive. |

A concrete action sequence after `mark capture_ready` (set the IDs from `cam -l` in each camera boot, and substitute only the applicable block):

```sh
# A: In the graphical session with the correct DISPLAY/WAYLAND_DISPLAY and XDG_RUNTIME_DIR.
mark gpu_begin
vulkaninfo --summary 2>&1 | stdbuf -oL tee "$D/vulkaninfo-live.txt"; VULKAN_RC=${PIPESTATUS[0]}
glxinfo -B 2>&1 | stdbuf -oL tee "$D/glxinfo-live.txt"; GLX_RC=${PIPESTATUS[0]}
# Only after the power-thermal gate permits short rendering:
timeout 10s vkcube 2>&1 | stdbuf -oL tee "$D/vkcube-live.txt"; CUBE_RC=${PIPESTATUS[0]}
mark "gpu_end vulkan=$VULKAN_RC glx=$GLX_RC cube=$CUBE_RC"

# B or C, as an authorized session user with camera access, using actual cam -l identity.
# REAR_OR_FRONT must be rear or front; CAMERA_INDEX is the observed numeric index.
REAR_OR_FRONT=rear
CAMERA_INDEX=1
mark "${REAR_OR_FRONT}_begin index=$CAMERA_INDEX"
LIBCAMERA_LOG_LEVELS='*:INFO' stdbuf -oL -eL cam --camera "$CAMERA_INDEX" --capture=120 --metadata 2>&1 | stdbuf -oL tee "$D/${REAR_OR_FRONT}-cam-live.txt"
CAM_RC=${PIPESTATUS[0]}
mark "${REAR_OR_FRONT}_end exit=$CAM_RC"
sync -f "$D/${REAR_OR_FRONT}-cam-live.txt"
```

The root-only trace marker, kmsg and root-owned destination require a small image-provided wrapper for session-user actions, or root/session permissions deliberately arranged by the image owner; do not run a root-owned graphical client without valid session access. The example defaults reproduce the *observed* rear index only; confirm it on that boot and set `REAR_OR_FRONT=front` and the observed front index for C. Image logging must flush action output periodically while `cam` runs: `tee` plus the end-of-command sync alone can lose the final stream output on reset. Preserve the exit code, camera output and observation separately even if the command exits unsuccessfully. The 120-frame exposure may be brief; never infer a long-term pass from it.

For robust correlation repeat the matched case after safe recovery; one pass is not proof of absence. Both camera cases reset with A passing favors a common stream path or common power load; A also resetting weakens stream necessity but does not exclude an independent camera issue. All pass means the intermittent trigger or prior workload/timing was not reproduced, not that H1/H2 are false. If A resets, do not proceed automatically; inspect trace/pstore and device state before deciding next controlled test. **A GPU pin-off comparison, ACD/preemption/IFPC experiment, or changes to camera timing are not part of this first matrix** and need a new evidence-backed plan. Concurrent GNOME rendering means the headless stream is not physically GPU-off; the test isolates the additional explicit stream action, not all GPU traffic.

---

# GPU device acceptance plan

## Revision 22: MX clamp and reset discrimination (2026-11-03)

Preflight: kernel owner reviews and integrates [GPU patch 0003](patches/0003-drm-msm-a6xx-clamp-mx-dependency-vote.patch) after rev21 GPU RPMh fixes, builds BTF and validates the image/DTB. Keep safe as default, existing clocks and thermal limits, and debug GPU early pin; never write GMU `power/control`. Camera IR/flash remain disabled. Confirm safe-entry recovery and power-thermal gate before any sustained GPU load. Log continuously to durable storage beyond the expected reset; record boot ID, monotonic timestamps, actual cmdline, artifact IDs, pstore files and provenance, reset reason, and collection failures.

1. Boot safe first; record ten online CPUs and recovery. In debug record GPU early `written=on readback=on` before first `GPU_BOOT_TRACE load begin`, snapshot GPU and GMU PM state separately, and confirm the `Mx Level 432` error is absent. Check firmware/HFI, runtime resume and hw-init returns; a missing error alone does not prove the vote or stability. Where feasible expose the selected MX dependency indices read-only and verify level 432 maps to index 9 / 416 without changing clocks, rails or policy.
2. After an idle desktop baseline with continuous logs, mark each action with a monotonic timestamp. Compare a GPU desktop/render action without camera with a separately marked camera open and stream-on/stream-off using the existing allowed RGB path; record whether preview and actual camera stream started and which node/sensor was used. Respect camera-owner instructions. Stop after the first reset; collect the complete previous boot's durable stream and any actual pstore files after recovery. A missing record or failed collector makes the comparison inconclusive. A reset only during a camera action is correlation, not proof of a camera defect; a reset during a GPU-only action strengthens GPU involvement but is not conclusive.
3. If stable, do not claim a fix on a single run. Capture repeated controlled comparisons and the normal acceptance tests only after thermal and independent safety cross-check gates. Record devfreq max and thermal state read-only. Compare against rev21 and document all concurrent changes before attributing any outcome.

Historical plans follow; where they request GMU power-control writes or different entry policy, this rev22 plan supersedes them.

**Historical revision 20 test (superseded):** the following proposal is retained for context. The revision-22 plan above governs any conflicts, including its prohibition on GMU power-control writes. No ramoops retention is established by these archives.

1. Before image integration, qualify the candidate 2 MiB ramoops range against the actual EFI map, all device-tree reservations and boot allocations, with independent cross-check. Reject the candidate on unknown ownership. Verify final BTF and four built-in PSTORE config options, validated DTB and backend registration. Use a non-destructive pmsg sentinel and warm reboot to establish that the next boot's systemd-pstore archive and raw pstore copy reach durable storage, then verify content after a further reboot. An empty store is not proof of a hardware reset.
2. Verify actual debug artifact: each exact GPU and GMU power/control path has a timestamped successful `on` write and readback or a visible failure, ordered before first possible suspend if feasible; record unit result and timing against first GMU start. Every fast and full collector cycle must record boot ID, monotonic time, `control`, `runtime_status`, and `runtime_suspended_time` for both devices, with explicit read errors. Verify urgent `KERN_ERR` and matching-line publication and actual synced destination, including under failure/lock contention. Preserve sequence gaps and loss indicators.
3. In the explicit debug entry, record image/kernel/DTB IDs, boot ID, command line, firmware versions and hashes, exact time GNOME appears and any reset. Preserve all four GMU phase markers (firmware begin/return and HFI begin/return) for **each** start, plus recovery messages and PM tracepoints if available. A second start proves entry to the GPU runtime-resume path but can also occur during recovery. An early `on` readback alone does not establish that no transition occurred; incomplete timing, logs or failed pin makes the discriminator inconclusive.
4. On the next safe boot, before further tests, preserve systemd-pstore archive, raw pstore if present, collector status, previous boot ID and kmsg stream on durable media. Compare reset timing and matched workload to round 3. If it survives, runtime transitions or the changed power state are implicated, not a particular driver line; if it resets despite verified pins, the autosuspend-trigger theory is weakened, not all GPU/firmware causes excluded. A hard reset may leave no record.
5. Check the GPU devfreq ceiling remains at or below 1250000000 Hz and thermal restrictions are unchanged. Do not run sustained stress until the existing power-thermal and cross-check gates are met.

These commands are **planned, not run**. Run on an approved test image/device
only, after the orchestrator's independent cross-check of the clock limit and
fuse extraction. Preserve logs locally, then redact unrelated identity fields
before adding selected evidence to git. Do not dump all of qfprom.

## 0. Historical clean GPU-enabled debug entry (superseded where conflicting)

D29 makes `safe` the default. Use the explicit GPU-on `debug` entry once; the
last run may reset the machine. Do not add `sp11.gpu_diag=1`, do not place the
CDSP experiment opt-in marker on any boot medium, and do not manually start
or retry either experiment. CDSP normal startup is distinct from the experiment.
Leave power controls, clocks, thermal policy and frequency limits unchanged.
The test compares a GPU-on boot with both agents absent, not a completely idle
machine; the first DRM open can occur in initramfs before userspace collection.
Record exact image/kernel/DTB identifiers. Keep GPU-disabled safe recovery ready.

Before testing, the image owner must verify on the actual artifact: safe is
default, debug uses m15 GPU-on, both experiment guards are off, the actual
initrd and rootfs contain the expected GPU firmware at the observed locations,
and an independently started early persistent kmsg/journal collector has a
working destination. Validate persistence with a known marker and `sync` on a
safe boot. A userspace follower started after boot cannot recover an early reset;
if persistent collection or a serial/external console is unavailable, a reset
may remain unexplained. Keep Windows unmounted and never write its partition.
Use a designated writable Linux/USB logging filesystem; do not write the ISO or
UEFI variables. Preserve private raw logs separately and redact before git.

1. Boot safe first to check logging/recovery and collect any existing pstore,
   journal from the previous boot if persistent, and platform-provided reset
   reason if exposed. Do not clear pstore before preserving it; empty pstore or
   unavailable prior journal does not mean a clean shutdown.
2. Boot GPU-on debug once. Observe whether it reaches a stable session. Record
   approximate elapsed time and whether reboot, hang, screen loss, or shutdown
   occurred; preserve all durable logs even when no command can be run. Do not
   repeat automatically. The collector should record boot ID, kernel, cmdline,
   timestamps, full kernel log including the *first* oops/panic, complete DRM,
   GMU, HFI, zap/PAS, SMMU, thermal and watchdog messages, and experiment unit
   status/markers. Verify the experiment's actual skip result; inactive or failed
   systemd unit alone does not establish whether a restart already happened.
3. If it survives, capture the following from a terminal, writing output to the
   designated durable log directory (`LOGDIR` set explicitly by the operator).
   Run graphics commands in the normal graphical session; both may open the GPU
   and submit work, so start with the metadata and persist each step. Missing
   commands are recorded as missing; no package installation is required here.

```sh
: "${LOGDIR:?set LOGDIR to a writable persistent log directory}"
mkdir -p "$LOGDIR"
uname -a > "$LOGDIR/uname.txt"
cat /proc/cmdline /proc/sys/kernel/random/boot_id > "$LOGDIR/boot.txt"
systemctl status sp11-gpu-two-step.service sp11-cdsp-experiment.service --no-pager > "$LOGDIR/experiment-status.txt" 2>&1 || :
journalctl -b -o short-monotonic --no-pager > "$LOGDIR/journal.txt" 2>&1 || :
sudo dmesg > "$LOGDIR/dmesg.txt" 2>&1 || :
ls -l /sys/class/drm /dev/dri > "$LOGDIR/drm.txt" 2>&1 || :
for d in /sys/class/drm/card[0-9]* /sys/class/drm/renderD*; do
    [ -e "$d" ] || continue
    printf '\n%s -> %s\n' "$d" "$(readlink -f "$d")" >> "$LOGDIR/drm.txt"
    for f in status enabled modes; do
        [ ! -r "$d/$f" ] || { printf '%s: ' "$f"; cat "$d/$f"; } >> "$LOGDIR/drm.txt"
    done
done
rpm -q qcom-firmware mesa-dri-drivers mesa-vulkan-drivers > "$LOGDIR/packages.txt" 2>&1 || :
sync
command -v glxinfo >/dev/null && glxinfo -B > "$LOGDIR/glxinfo.txt" 2>&1 || :
sync
command -v vulkaninfo >/dev/null && vulkaninfo --summary > "$LOGDIR/vulkaninfo.txt" 2>&1 || :
sync
sudo dmesg > "$LOGDIR/dmesg-after.txt" 2>&1 || :
sync
```

Capture GPU devfreq `available_frequencies`, `cur_freq`, `max_freq` and thermal
zone/cooling-device names, temperatures and states following section 2, without
changing them. Identify the GPU device by its sysfs link, not by assuming card or
render numbering. Capture the system's disclosed reset reason and pstore if
available, plus `/proc/iomem` and firmware-provided EFI memory map for the
reservation question; these are evidence only, not instructions to access memory.
Record mounted initramfs/rootfs firmware locations and package hashes separately.
A 30-minute stress test remains gated on the independent safety cross-check and
power-thermal release; this initial test does not prescribe one.

4. On a reset or hang, recover to safe and immediately save previous-boot
   persistent logs, pstore and any reset reason before another GPU-on attempt.
   A complete panic, SMMU fault, GMU/HFI/PAS error or thermal event narrows the
   subsystem; a reliable hardware watchdog/PMIC reason can narrow reset type.
   A silent reset or absent reason is **inconclusive**, not proof of GPU power
   collapse. If the clean boot survives and hardware GL/Turnip work, that weakens
   but does not prove the earlier agents were responsible. If it reproduces,
   an agent-specific trigger is less likely, but GPU power, other boot activity,
   timing, shared domains and missing early logs remain alternatives. No
   unobserved "under load" condition should be inferred from the prior open.

### Historical two-step diagnostic (superseded)

The historical procedure and its observations are retained in
[two-step evidence](evidence/2026-10-30-two-step.md) and [reset evidence](evidence/2026-11-02-m16-gpu-reset.md).
Do not run it or force a retry during the clean test.

## 1. Image checks and first fuse read

Image/kernel owners first verify:

- `CONFIG_DRM_MSM=m` (already requested in `kernel/config/sp11.config:12`),
  QFPROM/NVMEM and `CONFIG_NVMEM_SYSFS=y`,
  `CONFIG_FW_LOADER_COMPRESS_XZ=y`, and the mandatory BTF options.
- The actual installed versions of `qcom-firmware`, `mesa-dri-drivers` and
  `mesa-vulkan-drivers` match the pinned compose. Capture `rpm -q` for all three.
- Both Fedora `gen70500_*` files and the Microsoft zap shader from the manifest
  are available in the boot filesystem/initramfs wherever msm probes.
  Check with `lsinitrd`; verify the uncompressed Microsoft file's SHA-256
  against `firmware/manifest.toml`.
- A diagnostic boot entry uses `module_blacklist=msm rd.driver.blacklist=msm
  modprobe.blacklist=msm systemd.unit=multi-user.target`. This first entry keeps
  msm from loading until the fuse is checked. It can also prevent the msm
  display driver from binding, so preserve the project's alternative log path.

On that diagnostic boot, confirm msm is absent from `lsmod`, then read only
the aligned QFPROM word containing the speed-bin cell:

```sh
sudo python3 - <<'PY'
from pathlib import Path
import os
paths = list(Path('/sys/bus/nvmem/devices').glob('qfprom*/nvmem'))
if len(paths) != 1:
    raise SystemExit('STOP: identify the qfprom provider; no fuse was read')
fd = os.open(paths[0], os.O_RDONLY)
try:
    word = os.pread(fd, 4, 0x118)
finally:
    os.close(fd)
if len(word) != 4:
    raise SystemExit('STOP: incomplete fuse read')
fuse = (int.from_bytes(word, 'little') >> 15) & 0xff
print('GPU speed-bin fuse:', fuse)
if fuse != 7:
    raise SystemExit('STOP: unexpected fuse; retain msm blacklist and report')
PY
```

**Inference, extraction formula:** hamoa's cell starts at byte `0x119`, bit 7,
width 8 (`hamoa.dtsi:8790`), so in the aligned word at `0x118` it starts at bit
15. QFPROM uses four-byte stride/word reads and adjusts the cell offset
(`sources/linux/drivers/nvmem/qfprom.c:338`, `:370`). Print only the extracted
fuse, not the enclosing word. If sysfs access is unavailable, the first read
remains TBD; do not replace it with `/dev/mem` or assume a bin.

Expected: **7**. Once independently confirmed, the orchestrator can release a
subsequent boot with msm enabled. If it differs, investigate the mapping before
booting accelerated graphics. No kernel/DT frequency override is prescribed.

## 2. Driver, filtered OPPs and firmware

On the subsequent controlled boot, collect before benchmarks:

```sh
uname -r
rpm -q qcom-firmware mesa-dri-drivers mesa-vulkan-drivers
sudo dmesg | grep -Ei 'msm|adreno|gmu|zap|firmware|speed.bin|gpu.*(fault|hang)'
find /sys/class/devfreq -mindepth 1 -maxdepth 1 -printf '%f\n'
```

Find the devfreq device whose resolved device node is GPU `3d00000.gpu`;
do not assume a glob containing `gpu` matches every kernel naming scheme.
Read its `name`, `available_frequencies`, `min_freq`, `max_freq`, `cur_freq`,
`governor` and, if exposed, `trans_stat`. Expected maximum available frequency
and `max_freq`: **1250000000 Hz**. A thermally restricted runtime maximum may
be lower; record it and retain cooling controls. No frequency may be higher.
Never force the performance governor or write frequency/thermal limits.

Read the DRM chip/fuse value as a second check, selecting the msm render node:

```sh
# Replace this path only after identifying the msm render node.
python3 - /dev/dri/renderD128 <<'PY'
import fcntl, os, struct, sys
fd = os.open(sys.argv[1], os.O_RDONLY)
try:
    # drm_msm_param: pipe=MSM_PIPE_3D0, param=MSM_PARAM_CHIP_ID, len/pad=0.
    value = bytearray(struct.pack('=IIQII', 0x10, 3, 0, 0, 0))
    # _IOWR('d', DRM_COMMAND_BASE + DRM_MSM_GET_PARAM, sizeof(value)).
    request = (3 << 30) | (len(value) << 16) | (ord('d') << 8) | 0x40
    fcntl.ioctl(fd, request, value, True)
    chip = struct.unpack('=IIQII', value)[2]
    print(f'chip=0x{chip & 0xffffffff:08x} fuse=0x{chip >> 32:04x}')
finally:
    os.close(fd)
PY
```

Expected chip **0x43050c01**, fuse **0x0007**. UAPI layout and read-only params:
`sources/linux/include/uapi/drm/msm_drm.h:50`, `:76`, `:130`, `:558`;
export: `sources/linux/drivers/gpu/drm/msm/adreno/adreno_gpu.c:390`.
`0xffff` is the unknown/zero-read sentinel and cannot validate the expected
fuse (`sources/linux/drivers/gpu/drm/msm/adreno/a6xx_gpu.c:2756`).

Stop if `missing support for speed-bin`, an unexpected/sentinel fuse, a ceiling
above 1250000000, firmware authorization failure, or a GPU/GMU fault appears.
An absence of firmware errors alone is not proof of successful zap loading;
capture the driver bind and working hardware rendering as well as logs.

## 3. Rendering and stability

`power-thermal` must release the sustained-load tests after checking GPU
cooling policy (QCOM0CF7 request). Use normal cooling/governor controls.
In the graphical user's session:

```sh
glxinfo -B
vulkaninfo --summary
journalctl -b _COMM=gnome-shell
timeout --signal=INT 1800s vkcube
timeout --signal=INT 1800s glmark2-es2-wayland --run-forever
sudo dmesg | grep -Ei 'msm|adreno|gmu|zap|gpu.*(fault|hang)|iommu.*fault'
```

Expected: direct hardware GL with freedreno / Adreno X1-85, and Vulkan Turnip
for the same GPU. Lavapipe/llvmpipe do not satisfy acceptance. Confirm GNOME's
own renderer from its startup log where exposed and its open `/dev/dri/`
render-node descriptors; GL/Vulkan tools alone do not prove Shell's renderer.
No GMU timeout/reset loop, GPU hang/fault or IOMMU fault; both demos remain
responsive for 30 minutes each. Timeout exit 124 at the requested duration is
normal and is not a demo failure. Sample the devfreq/thermal readings during
both runs and record any throttling. Stop immediately on faults or a limit
violation; do not repeat the load automatically.

Record whether IFPC is enabled and whether idle/resume-between-loads produces
GMU errors. This checks Q4, not system suspend. Add dated, redacted logs and
the exact image/kernel/package identifiers to `hardware/gpu/evidence/`.
Only the orchestrator can set `pass` after reviewing this device evidence.

## 4. Controlled M15 boot-stage trace

This is diagnostic instrumentation, not a fix. Do not enable the GPU until the
image owner has isolated early DRM opens, verified initramfs firmware staging,
added markers around the hook and its helper's global deadline, and confirmed
the operator's thermal safeguards. Then, only for a controlled test kernel,
set `CONFIG_DRM_MSM_GPU_BOOT_TRACE=m` using [patch 0001](patches/0001-drm-msm-add-opt-in-gpu-boot-phase-trace.patch); it defaults off.

Collect `dmesg` from boot start and retain timestamped markers:

- `load begin`, then `firmware ready` or no following marker: lazy DRM-open
  firmware lookup failure.
- `runtime resume begin/returned`: runtime PM/GMU resume result.
- `GMU firmware start` and `GMU HFI start` begin/return markers: GMU phase.
- `hw init begin/returned`: remaining hardware init, which includes zap/PAS.

These markers do not isolate zap/PAS within hardware init. Preserve the
collector's `STEP0`/`STEP1` markers and image hook before/after markers. Do not
repeat automatically after a reset. Disable the option after the diagnostic
build.
