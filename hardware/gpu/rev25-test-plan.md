# Rev25 menu: restored-orientation and debug-service discriminators

2026-11-04. **Planned only; no new test has run.** The old preemption-first
plan below is historical and must not be executed. All eight debug menu
variants already reset, including MSM-off and multi-user. The new primary
control is the observed `test-msm-off` boot, with both pin helpers skipped.
See the [ten-boot evidence](evidence/2026-11-04-rev25-menu-reset.md).

## Constraints for every trial

- Use no GPU **or** GMU `power/control` writes. Retain
  `sp11.gpu_pin=0`; verify in the actual initramfs and rootfs that both pin
  helpers skip before any GPU write. Keep `sp11.gpu_diag=1` absent and verify
  the two-step unit is inactive. Do not use a stock debug entry that enables
  the pin. No temperature, clock, frequency, regulator or ACD changes.
- Preserve S1/D26: no speaker output or closed-loop audio experiment. Keep
  speakers muted and the audio configuration unchanged. Preserve S2–S6,
  including no IR/flash, device-firmware writes or Windows-partition writes.
- Use the same boot medium, Type-C port, plug orientation, charger/battery
  state, peripherals, quiet observation, collector/services and kernel
  command line. Do not add workload, force a camera stream or alter tracing.
  Record their actual state rather than assuming no background activity.
- The MSM-blacklisted display may be blank. Establish recovery and durable
  boot-medium logging first; do not require a desktop-ready timestamp. On each
  failure, stop, boot the established safe recovery entry and preserve that
  boot's files and any pstore **before** further experiments. No automatic
  retries. Keep the existing safe recovery entry available and unchanged.

## Common command line and artifact preflight

In the tested `f44ef269…` image, `test-msm-off` supplies the base debug line,
including these exact distinguishing arguments:

```text
efi_pstore.pstore_disable=0 printk.always_kmsg_dump=1 sp11.gpu_pin=0 module_blacklist=msm sp11.test=test-msm-off sp11.entry=debug
```

**Keep the entire original linux line unchanged**, not just that excerpt,
including dynamic-debug, trace, ignore-unused and root arguments. Do not change
`sp11.test`: image scripts may inspect it. Use the same kernel, modules,
initrd, firmware, rootfs, systemd units, debug services, collector and boot
medium. Confirm `Module msm is blacklisted`/absence from `lsmod`, pin-skip
markers, no two-step opt-in, `/proc/cmdline`, boot ID and actual DT properties
for every boot. A command-line intent without effective readback is incomplete.

Image/kernel owners: make old m15, restored m15 and unchanged m15-safe
selectable **as distinct non-default DTB files** while leaving the known
recovery intact. Before device use, hash the ISO, kernel, initrd, relevant
rootfs/firmware, and all DTBs; compare complete effective FDTs. Old m15 versus
restored m15 must differ only in the two QMP `orientation-switch` properties;
restored m15 versus m15-safe must differ only in GPU `status`. The tested old
m15 and safe hashes are in the evidence. Verify what GRUB actually loads,
not just the source or filename. Retain BTF on any rebuilt kernel. If another
image changes userspace, logging, firmware, kernel or other payloads, the
old observed failure is historical rather than a strict control; create a
matched old-m15 baseline on the *same* new artifact before attributing a
change to orientation. Do not repeat that reset automatically.

The shared checkout has a newer draft `test-safe-debug` menu entry. It omits
the EFI-pstore arguments and `module_blacklist=msm`, changes `sp11.test`, and
has a matching special case in the image's WirePlumber helper. Therefore it is
**not** the same controlled line as `test-msm-off`; do not compare it directly
with B as a DTB-only test. The actual release image must be checked again:
this observation is about source in progress, not a built ISO.

## A → B: restore QMP orientation, MSM and GPU pin still off

| Row | DTB | Kernel command line | Outcome |
|:--|:--|:--|:--|
| A | Original m15, orientation properties absent, GPU `okay` | Original `test-msm-off` line | Existing seq 5 reset; use as a strict control only if all other artifact and exposure conditions match. |
| B | Restored m15, orientation properties present on both QMP PHYs, GPU `okay` | **Identical** to A | First next one-variable trial; the pair of restored properties is the single Type-C topology intervention. |

Select the `test-msm-off` GRUB entry and, if necessary, edit **only its
`devicetree` path** to the verified restored m15 file; leave the `linux` and
`initrd` lines untouched. Verify the on-device tree contains both properties
and the GPU node is `okay`; confirm MSM remains blacklisted and the GPU pin is
skipped. Use the existing debug kmsg service; check its boot-ID stream and
publisher status. Observe at least 150 s of boot uptime, with boot-medium
heartbeats and/or operator observation, without assuming the last logged time
is the reset time. A missing stream, wrong DTB, unexpected pin/driver activity
or reset before verification makes the relevant conclusion incomplete.

- B survives after a comparable A failure: supports an association with the
  restored Type-C topology under this exposure; it does not prove a QMP/PS8830
  lane defect, rail fault or permanent fix. A single survival is not proof.
- B resets like A: restoration was insufficient in that run; Type-C remains
  possible through other paths or interactions, but the property deletion is
  less compelling as a sole cause. Preserve the failed boot first.

## B → C: m15-safe DTB with debug services and EFI arguments

Starting from **the same `test-msm-off` entry and its unchanged linux/initrd
lines**, change only its `devicetree` path from restored m15 to the verified
m15-safe DTB:

```text
/boot/dtb/qcom/x1p64100-microsoft-denali-m15-safe.dtb
```

This is the requested safe-DTB + `sp11.entry=debug` test. It retains
`efi_pstore.pstore_disable=0`, `printk.always_kmsg_dump=1`,
`sp11.gpu_pin=0`, `module_blacklist=msm`, the test marker and the debug-entry
service/collector configuration, so B→C changes GPU DT status only if the
preflight verifies the full FDT diff. Confirm `/proc/device-tree` or an
owner-verified DTB read shows GPU `disabled` and both orientation properties
present; verify MSM blacklist and pin skip. Keep the existing collector and
observe the same duration. C is **not** a plain safe boot.

| B restored m15 | C safe DTB + same debug line | Interpretation |
|:--|:--|:--|
| reset | reset | GPU node being `okay` and an MSM driver are unnecessary in C; debug services/EFI arguments or other common factors remain. No specific service or power domain is proven. |
| reset | survives | GPU node status, a dependent probe or an interaction with the changed DT gains support under MSM blacklist; this does not prove GPU/GMU execution. |
| survives | reset | GPU status or its interactions/timing differ, but the direction does not establish mechanism; repeat matched observations before drawing a conclusion. |
| survives | survives | A→B supports an orientation association only if artifact and exposure matched; a stable C does not identify which prior difference mattered. |

If C also resets, a later owner-prepared test can change **one** of: the
`sp11.entry` service selector, the kmsg-tail service, or one EFI-pstore/printk
parameter, with all other inputs held fixed. Changing `sp11.entry` changes a
group of image behaviors; it is not a single-service test. Disabling kmsg-tail
also removes its evidence and USB/FAT I/O, so use an identical independent
observer in both control and treatment or explicitly report the coverage gap.
Do not infer a specific service from the current safe comparison, which
changes multiple axes. Do not add a new observer only to one side and call it
a one-variable comparison.

## Evidence and stop conditions

Record boot ID, hashes, exact command line, effective DT properties, physical
setup, service conditions, kernel sequence gaps, published last timestamp,
collector errors, status/uptime and operator-observed reset or survival.
Collect bounded read-only QMP/PS8830/PMIC-GLINK, PCIe, ath12k, regulator,
interconnect, GPU/GMU and watchdog evidence already available in the image;
snapshots are not live physical-rail measurements. Preserve raw pstore and
systemd archive filenames and errors on safe recovery; backend registration
and retention are still unproven. Never guess an EC/PMIC reset-reason register.
Do not treat a missing pstore record, a quiet tail, or one completed boot as a
fix. Any accidental added parameter, changed payload, different port/polarity,
lost stream or unverified node status limits the comparison.

---

## Historical 2026-11-03 rev24 proposal — superseded, do not execute

The text below is retained for provenance only. Its preemption-first order,
ACD-off proposal, early GPU pin, capture changes and workload actions do not
apply to this task and are not authorized by the current no-power-write rule.

<details><summary>Superseded rev24 plan</summary>

# Rev25: no-build GPU reset discriminator

2026-11-03. **Planned only; no test has run.** Use the *existing rev24 ISO*,
kernel, DTB and firmware. There is no rev25 kernel candidate. The default safe
entry remains the recovery path. Stop on the first reset, preserve that boot's
logs and pstore on a safe recovery boot, and review them before another debug
boot. Do not enable IR/flash, change clocks, frequency or thermal limits, write
GMU `power/control`, or alter the D26 speaker path. Record AC/battery,
peripherals, desktop/login, ambient conditions, exact artifact/boot IDs, and
operator-observed desktop and reset times. Keep these and instrumentation the
same in each matched trial.

## Decision and single-variable matrix

First obtain **C**, a control with the capture procedure below and no camera app
or deliberate camera stream for at least 150 s after desktop-ready. Then use
**P**, the first parameter trial, with only `msm.enable_preemption=0` added to
the otherwise identical control command line. Capture and review the first
reset before proceeding. The recommendation is preemption-off first because
the rev24 source selects it automatically for this chip, while final34 shows
only the initial GMU start; it is not proof preemption caused the reset.

| Boot | Change relative to C | Required readback and interpretation |
|:--|:--|:--|
| C | None beyond the common capture arguments below. Existing debug GPU pin remains enabled. | Verify preemption parameter is `-1`, ACD disable is `N`/`0`, GPU pin `on` was written before first load, and no camera preview was launched. A pre-action reset demonstrates camera **streaming was not necessary in that run**, if no automatic stream occurred. Capture evidence of actual GPU jobs before asserting a GPU workload caused it. |
| P | `msm.enable_preemption=0` | Read `/sys/module/msm/parameters/enable_preemption` as `0` and check loaded MSM GPU events. If repeated C resets and matched P survives, changed preemption/ring/scheduler behavior is associated with stability, not necessarily the Oct patch 6 suspend-record bug. If both reset, preemption is weakened as a sole explanation. |
| R | `sp11.gpu_pin=0` | Parameter makes **both** image pin helpers skip; check their skip messages and actual GPU `power/control`, runtime status, PM events and suspended time. The parameter does not force `auto`; if control never becomes auto or no transition is observed, the intended runtime-PM comparison is incomplete. A difference implicates the pin or the behaviors it changes, not a particular callback. |
| A | `msm.disable_acd=1` | **Later, idle only**, after the power-thermal owner reviews this intervention; read parameter as `Y`/`1` and confirm `Skipping GPU ACD probe`. The default trace sent AOSS an ACD-enable request. Disabling ACD removes a clock-droop throttling mechanism and may change dynamic clock behavior even without changing a frequency limit. Do not combine with a GPU workload or camera preview, and do not describe it as a passive read. A survival difference implicates the broad ACD-related change, not a physical rail or proven fix. |

Each trial is a **fresh boot** based on C: do not accumulate parameters. If C
survives, a single stable P/R/A is inconclusive; repeat matched control/trial
exposures. If the parameter is absent, ignored, unreadable, or instrumentation
fails, that trial is invalid. Safe vs debug differs in more than the GPU, so
safe survival by itself does not identify the reset's cause. Existing final34
is useful context but is not C: its automatic collector ran `cam -l`, and its
session journal ended before the reset.

## Common GRUB edit, all matrix boots

Select the existing rev24 **debug** entry and press `e`. Replace its existing
`trace_event=` argument with exactly one combined argument; keep all other
original arguments, including `sp11.entry=debug`. Add the following common
instrumentation arguments to C and all parameter trials:

```text
trace_clock=mono trace_buf_size=16M trace_event=:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg,rpm:*,power:device_pm_callback_start,power:device_pm_callback_end,:mod:msm systemd.unit=multi-user.target systemd.mask=sp11-log-collector.service systemd.debug_shell=1
```

Then add exactly the row's one parameter, or none for C. `rpm:*` requests the
runtime-PM events in `include/trace/events/rpm.h`; `:mod:msm` requests MSM
module tracepoints even if the module loads later
(`sources/linux/Documentation/trace/events.rst:58`). Do not add a second
`trace_event=`. `trace_buf_size` is per CPU; full MSM plus RPM events can create
substantial I/O and affect timing. Measure loss. These common arguments delay
the desktop until capture is ready, expose a root debug shell on tty9 for this
boot, and mask the main collector because its normal run invokes `cam -l`.
The separately enabled `sp11-kmsg-tail.service` is not masked and still invokes
the collector's `live-append` command. The session snapshot paths can still
run; they do not invoke the camera drop-in. Verify on the actual boot. Masking
the normal collector and delaying GDM differ from final34, but are identical in
C/P/R/A. Never leave the debug shell enabled for ordinary use.

## Capture before the desktop

This is a manual no-rebuild fallback, not a claim of initramfs live capture.
It cannot capture a reset before reaching tty9, and its live trace starts after
the early GPU initialization. The boot-enabled ring may preserve earlier
events; save its snapshot and report overruns. Before testing, recover any old
raw `/sys/fs/pstore` and `/var/lib/systemd/pstore` files to the **verified boot
medium**, retaining original names/boot ID. Check backend registration,
availability and retention separately; an empty store cannot exclude a panic
or reset. Do not induce a panic or create a new ramoops reservation.
Preserve earlier boot directories somewhere outside the collector's managed
log tree before starting: the existing kmsg publisher can prune old boots to
enforce its size cap.

Boot to multi-user, switch to tty9 (Ctrl-Alt-F9), and ensure GDM is inactive.
Use `cat /proc/cmdline`, `findmnt /run/initramfs/live`, and
`lsblk -o NAME,PKNAME,FSTYPE,LABEL,PARTTYPE,SIZE,RM,MOUNTPOINTS` to identify
the live boot disk and its writable FAT log partition. The final34 disk had a
64 MiB `BOOT` FAT partition, but device letters and labels may differ. The
partition **must** be on that boot disk, not internal Windows/NVMe; refuse a
disk containing NTFS, BitLocker or a Microsoft reserved partition. Do not
format, repartition, remount Windows or guess if the disk is ambiguous. Check
free space first: reserve at least 24 MiB before capture, and stop before the
filesystem has less than 8 MiB free. A dedicated larger boot-medium log
partition is preferable if already available. The existing collector's
`boot-medium.txt` and `sp11-kmsg-tail` status are additional checks, not a
substitute for confirming the current boot.

As root in tty9, replace the placeholder with the **verified** boot-medium FAT
partition. The long-lived mount is separate from the collector mount. If either
mount or the existing kmsg publisher fails, stop and record the failure. These
commands write only a new boot-ID directory on that partition and tracefs
markers, never a power control:

```bash
BOOT_FAT=/dev/REPLACE_WITH_VERIFIED_BOOT_PARTITION
mkdir -p /run/sp11-rev25
mount -t vfat -o rw,noatime,nodev,nosuid,noexec "$BOOT_FAT" /run/sp11-rev25 || exit 1
findmnt -T /run/sp11-rev25
df -Pk /run/sp11-rev25
# Continue only if the source and free space meet the checks above.
test "$(findmnt -n -o FSTYPE -T /run/sp11-rev25)" = vfat || exit 1
free_kib=$(df -Pk /run/sp11-rev25 | awk 'NR == 2 {print $4}')
test -n "$free_kib" && test "$free_kib" -ge 24576 || exit 1
BID=$(cat /proc/sys/kernel/random/boot_id)
D=/run/sp11-rev25/sp11-rev25/$BID
test ! -e "$D" || { echo 'boot directory already exists; do not overwrite'; exit 1; }
mkdir -p "$D" || exit 1
T=/sys/kernel/tracing
mountpoint -q "$T" || mount -t tracefs tracefs "$T" || exit 1
cat /proc/cmdline > "$D/cmdline.txt"
uname -a > "$D/uname.txt"
cat "$T/trace_clock" > "$D/trace-clock.txt"
cat "$T/set_event" > "$D/enabled-events.txt"
cat "$T/available_events" > "$D/available-events.txt"
head -c 4194304 "$T/trace" > "$D/trace-before-live.txt" 2>> "$D/errors.txt"
systemctl is-active gdm.service sp11-kmsg-tail.service > "$D/services.txt" 2>&1
for f in /sys/module/msm/parameters/{enable_preemption,disable_acd} \
         /sys/bus/platform/devices/{3d00000.gpu,3d6a000.gmu}/power/{control,runtime_status,runtime_suspended_time}; do
    printf '%s: ' "$f" >> "$D/parameters-pm.txt"
    cat "$f" >> "$D/parameters-pm.txt" 2>> "$D/errors.txt" || true
done
```

The pre-live snapshot is bounded to 4 MiB and may be truncated; record its last
timestamp. Check the selected trace clock is `[mono]`, `set_event` actually contains RPM
and `drm_msm_gpu` events, GDM is inactive, kmsg-tail is active, parameter and
GPU-pin readbacks match the intended row, and `trace-before-live.txt` plus
errors were saved. If MSM events are missing after the module is loaded, the
capture is invalid until explicitly enabled and recorded:

```bash
echo 1 > /sys/kernel/tracing/events/drm_msm_gpu/enable
cat /sys/kernel/tracing/set_event >> "$D/enabled-events.txt"
```

Start exactly **one** live trace reader and one session-journal follower. The
existing independent kmsg service supplies the earlier boot and live kmsg;
confirm its boot-ID file and status advance. Its publisher batches up to 10 s
and can rotate the stream at 2 MiB or a smaller shared-storage cap; inspect
kernel sequence numbers, publisher errors and missing beginnings, and do not
assume its first or last record survived. These bounded readers protect the
small FAT volume; hitting a cap ends capture and invalidates the rest of that
boot. The sync loop records per-CPU ftrace stats and stops the readers if free
space falls below 8 MiB. All paths below are root-owned; leave tty9 running.

```bash
head -c 12582912 "$T/trace_pipe" > "$D/trace-live.txt" 2>> "$D/errors.txt" &
TP=$!
stdbuf -oL -eL journalctl -b -n 0 -f -o short-monotonic --no-pager 2>> "$D/errors.txt" | \
    head -c 4194304 > "$D/journal-live.txt" &
JP=$!
(
    while kill -0 "$TP" 2>/dev/null && kill -0 "$JP" 2>/dev/null; do
        free_kib=$(df -Pk "$D" | awk 'NR == 2 {print $4}')
        if [ -z "$free_kib" ] || [ "$free_kib" -lt 8192 ]; then
            echo 'capture stopped: free space below reserve or unknown' >> "$D/errors.txt"
            kill "$TP" "$JP" 2>/dev/null || true
            break
        fi
        { cat /proc/uptime; for s in "$T"/per_cpu/cpu*/stats; do
            echo "$s"; cat "$s"; done; } >> "$D/ftrace-stats.txt" 2>> "$D/errors.txt"
        sync -f "$D/trace-live.txt" || break
        sync -f "$D/journal-live.txt" || break
        sleep 5
    done
    echo 'capture ended; check errors, cap and reader status' >> "$D/errors.txt"
    sync -f "$D" || true
) &
SP=$!
printf 'TP=%s JP=%s SP=%s\n' "$TP" "$JP" "$SP" > "$D/reader-pids.txt"
printf 'REV25 %s CAPTURE_READY\n' "$BID" | tee "$T/trace_marker" /dev/kmsg >/dev/null
sync -f "$D"
kill -0 "$TP" "$JP" "$SP"
```

Check live trace and journal files grow, no write/sync errors are recorded, the
kmsg publisher's separate boot-ID stream advances, and per-CPU overrun/drop
counts are recorded. FAT sync, a USB controller cache and a sudden reset can
still lose the tail. A `trace` snapshot is non-consuming; `trace_pipe` consumes
events, so never start a second reader. The stats at the last successful sync
bound loss only up to that time. If any reader stops, a cap is hit, free space
is exhausted, or logging is unavailable, stop the test and mark it incomplete.

Start GDM only after capture is ready:

```bash
printf 'REV25 %s DESKTOP_REQUEST\n' "$BID" | tee "$T/trace_marker" /dev/kmsg >/dev/null
systemctl start --no-block gdm.service
```

Switch to the graphical session. As the logged-in user, open a terminal and
record the moment the desktop is ready, then leave it alone for **150 s**.
The terminal/marker are common to all boots; GNOME itself can render at idle.
Do not open Snapshot or run `cam -l` in this interval. Record any automatic
camera service or stream shown in the live journal; enumeration/open alone is
not proof of a stream.

```bash
BID=$(cat /proc/sys/kernel/random/boot_id)
printf 'REV25 %s DESKTOP_READY\n' "$BID" | sudo tee /sys/kernel/tracing/trace_marker /dev/kmsg >/dev/null
# Wait 150 s without a camera app. Then:
printf 'REV25 %s IDLE_150_DONE\n' "$BID" | sudo tee /sys/kernel/tracing/trace_marker /dev/kmsg >/dev/null
```

No `IDLE_150_DONE` means the idle exposure was not completed. A reset after the
desktop-ready marker and before 150 s, with journal/camera observations showing
no stream, establishes a no-manual-camera reset for that run; if automatic
streaming is unresolved, say so. One trace event close to the reset gives
correlation, not a physical reset cause. RPM events expose host runtime PM;
MSM events expose instrumented submissions/frequency/preemption. Neither is
direct hardware IFPC residency, GMU internal state, or rail voltage.

## After a successful 150 s idle

For C, P or R only, and only if the existing power-thermal short-load gate has
been released, mark a **brief** GPU-only workload with no camera preview. This
is not a stress or frequency-limit test. Use the same workload on matched runs.
From the graphical user's terminal, with the normal session environment:

```bash
printf 'REV25 %s GPU_BEGIN\n' "$BID" | sudo tee /sys/kernel/tracing/trace_marker /dev/kmsg >/dev/null
glxinfo -B | sudo tee /run/sp11-rev25/sp11-rev25/"$BID"/glxinfo.txt
timeout 10s glxgears -info 2>&1 | sudo tee /run/sp11-rev25/sp11-rev25/"$BID"/glxgears.txt
GPU_RC=${PIPESTATUS[0]}
printf 'glxgears exit=%s\n' "$GPU_RC" | sudo tee -a /run/sp11-rev25/sp11-rev25/"$BID"/glxgears.txt
printf 'REV25 %s GPU_END\n' "$BID" | sudo tee /sys/kernel/tracing/trace_marker /dev/kmsg >/dev/null
```

Confirm `glxgears -info` reports the Adreno/freedreno renderer and that MSM
submit events occur after `GPU_BEGIN`. If unavailable or software-rendered,
record that and do not call it a GPU-only workload. `GPU_RC` is the workload's
exit status, rather than `tee`'s; a timeout normally yields 124. No load is run
in A.

If still stable, mark one visible RGB camera preview, identify the selected
rear/front sensor from the app and camera logs, observe the privacy LED, and
record visible frames plus camera start/end. Stop preview if the required
privacy LED is dark; retain the existing camera safety gate. From the graphical
terminal:

```bash
printf 'REV25 %s CAMERA_BEGIN sensor=front\n' "$BID" | sudo tee /sys/kernel/tracing/trace_marker /dev/kmsg >/dev/null
snapshot
```

Close the preview, then mark its end manually:

```bash
printf 'REV25 %s CAMERA_END sensor=front\n' "$BID" | sudo tee /sys/kernel/tracing/trace_marker /dev/kmsg >/dev/null
```

Use `sensor=rear` if that is what the operator actually selects, and note any
switch. Verify the selected identity and stream/frame evidence in the live
journal; launching the app is not proof of frames. `snapshot` may return while
the application remains D-Bus activated, so the end marker is deliberately a
separate manual action. Do not start another camera during idle.

- Reset during 150 s with no confirmed stream: camera streaming is unnecessary
  for that run; GPU/display, background activity, shared rails and autonomous
  resets remain possible.
- Reset after verified GPU submissions but before camera: the action is
  associated with a GPU workload; it does not isolate GPU hardware from shared
  power, display, CPU, memory, software or timing.
- Reset only after a marked, verified camera stream, after matched idle/GPU
  phases survive: stream-associated or combined-load mechanisms gain support;
  neither the camera nor GPU is individually proven guilty.
- Both entries survive: the failure did not reproduce for those exposures;
  repeat matched trials, do not call it fixed. Any missing marker, wrong
  parameter, trace loss or unmatched phase constrains the conclusion.

On a clean completion, return to tty9 and stop the readers before unmounting:

```bash
printf 'REV25 %s TEST_END\n' "$BID" | tee "$T/trace_marker" /dev/kmsg >/dev/null
{ cat /proc/uptime; for s in "$T"/per_cpu/cpu*/stats; do echo "$s"; cat "$s"; done; } >> "$D/ftrace-stats.txt"
kill "$TP" "$JP" "$SP" 2>/dev/null || true
wait "$TP" "$JP" "$SP" 2>/dev/null || true
sync -f "$D"
cd /
umount /run/sp11-rev25
```

On reset, do not attempt another debug boot until the evidence is copied. For
safe recovery, add these common GRUB arguments to prevent the normal collectors
from pruning the failed boot and to inspect raw pstore before systemd archives
it:

```text
rd.systemd.mask=systemd-pstore.service systemd.mask=systemd-pstore.service systemd.mask=sp11-log-collector.service systemd.mask=sp11-kmsg-tail.service systemd.mask=sp11-log-collector-session-first.path systemd.mask=sp11-log-collector-session-user.path
```

Verify the masks and identify/mount the verified boot FAT partition as above;
copy the failed boot-ID trace, live journal, kmsg stream/status and raw and
archived pstore files, retaining filenames, hashes and read errors. The mask may
not stop a pstore consumer outside those services; record what is actually
present. Do not erase any pstore entry before copying it. Keep private
identifiers and Windows binaries out of git. Ask power-thermal/ec-sam for an
owner-verified read-only reset reason; do not invent registers or write firmware.
Pstore absence is not a reset classification.

</details>
