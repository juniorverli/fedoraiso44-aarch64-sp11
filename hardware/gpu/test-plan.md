# GPU device acceptance plan

These commands are **planned, not run**. Run on an approved test image/device
only, after the orchestrator's independent cross-check of the clock limit and
fuse extraction. Preserve logs locally, then redact unrelated identity fields
before adding selected evidence to git. Do not dump all of qfprom.

## 0. Two-step diagnostic after the silent reset (M13, operator-initiated)

**Warning:** this entry may reset the machine within seconds. Run it only on the live USB, with the operator present, and
never before the cross-check of section 1's safety values. Evidence: [two-step](evidence/2026-10-30-two-step.md).

1. Boot `SP11 debug, GPU diagnostic` (DTB `m13-gpu`, `sp11.gpu_diag=1`, multi-user target). Wait up to 3 minutes. If the
   machine resets, boot the same entry again; do not boot Windows in between.
2. Collect from the boot USB (`SP11LOGS` or `EFI/sp11-logs`) the folder `gpu-two-step/`: `state.log`, `<boot-id>/previous-boot-report.txt`,
   `step*.dmesg`, `step*.regulators`, `step*.clocks`, `step*.genpd`, `step*.pm`, `kmsg-follow.txt`, any `pstore/`.
3. Read the last marker of the dead boot: died in `STEP1` = CX GDSC/GMU device power (rank 2 cause not yet involved);
   died after `STEP2_SUB open-call` and before `open-returned` = `adreno_load_gpu()` (GMU boot, AHB fence, or PAS 13 zap; the last
   lines of `kmsg-follow.txt` tell which if the kernel markers exist); survived both = the reset needs the GNOME session
   (GPU job, or something other than the GPU open).
4. Record in `hardware/gpu/evidence/`. A death makes later boots skip that step; add `sp11.gpu_diag_force=1` to retry once.

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
