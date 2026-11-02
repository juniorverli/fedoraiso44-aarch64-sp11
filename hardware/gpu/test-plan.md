# GPU device acceptance plan

**Current next test (2026-11-02c):** the debug-only GPU platform `power/control=on` discriminator, including early ordering, readback, full GMU-start stream, matched GNOME use, interpretation and safety gates, is specified in [resume evidence](evidence/2026-11-02-resume-comparison.md). It supersedes older isolation proposals below.

These commands are **planned, not run**. Run on an approved test image/device
only, after the orchestrator's independent cross-check of the clock limit and
fuse extraction. Preserve logs locally, then redact unrelated identity fields
before adding selected evidence to git. Do not dump all of qfprom.

## 0. Clean GPU-enabled debug entry (planned; no build or device test)

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
