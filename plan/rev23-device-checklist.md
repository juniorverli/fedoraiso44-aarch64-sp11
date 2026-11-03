# Revision 23 device test checklist (2026-11-03)

Control: rev22 ISO `out/iso/sp11-fedora44-aarch64-kiwi-20261103T130351Z-private.iso`
(SHA-256 `0f3e6bacdd2647954a2ea2253e1094eb135457ae629cbcc1f51efb61bf5e6bd9`).
Candidate: rev23 ISO (GPU stale-BW-vote backport, initramfs guard, safe WirePlumber
softpipe wrapper); fill the name/hash from its build record before the boot.

The goal is to **identify the debug reset cause and make the debug boot stable**, then
make safe camera/keyboard work. Do not declare a fix before the A/B results.

## 0. Safety and evidence

- One variable per boot. Stop at the first reset; copy the complete previous-boot
  kmsg/trace/pstore before another attempt.
- The private ISO/logs never leave this machine; keep raw frames/logs under `out/`.
- No IR/flash, no cap increase, no GMU `power/control` write, no speculative camera
  rate/CSID or GPU frequency change.
- Use a sacrificial/read-only root state where possible; repeated hard resets can
  corrupt the live filesystem.

## 1. Decisive reset split (cheapest first)

### A. Debug idle, no camera, 150 s
Boot `SP11 debug` (GPU on, pin on), do **not** open Snapshot/any camera app, leave the
desktop idle for at least 150 s.

- If it resets near the same time as the camera boots: the trigger is **time/GPU/EC/PMIC**,
  not the camera app. The rev23 BW-vote candidate targets this path.
- If it survives 150 s: the reset is **camera-action-associated**; go to B and C.
- Record the exact reset time and whether the desktop was truly idle.

### B. Debug GPU-only action, no camera
On a fresh debug boot, run a marked GPU action with no camera:
`vulkaninfo --summary` or a short `glmark2-es2-wayland`; no Snapshot.
This separates ordinary GPU rendering from the camera path. Stop at reset.

### C. Debug camera direct, one sensor per boot
Use libcamera's `cam` (not Snapshot/PipeWire) after `cam -l`:
`cam --camera <rear-index> --capture=120 --metadata` and, on a separate boot, the front
index. Watch the physical LED and record:
- sensor, mode, `s_stream` start/return, first completed buffer/sequence, bytes;
- active CSIPHY/CSID/VFE clocks, IRQ deltas, route, errors;
- LED on/off and exact reset time.

If only the front resets, the C-PHY path (0023) is the cause candidate; if only the rear
resets, D-PHY/CAMSS; if both, a shared CAMSS/power/GPU-preview path.

### D. Safe camera direct
On safe (GPU off), run the same direct `cam` rear and front tests, one per boot, with the
LED watched. Safe has no GPU/llvmpipe; if a direct front stream resets here, the C-PHY
path is independent of the GUI/GPU. If it streams and lights, the safe GUI blocker is the
WirePlumber/llvmpipe crash (below), not CAMSS.

## 2. Safe camera GUI and quality

- Rev23 adds `/usr/libexec/sp11-wireplumber-safe`, which forces
  `GALLIUM_DRIVER=softpipe LIBGL_ALWAYS_SOFTWARE=1` only on `sp11.entry=safe`. Test
  Snapshot safe: if the WirePlumber SIGSEGV is gone, the LED should light and the preview
  should appear; if it still crashes, collect `coredumpctl info` and the full backtrace.
- If the GUI still fails, use direct `cam`/`qcam` as the safe fallback and record the
  crash; do not claim the camera fixed.
- Green/dark: save a raw frame plus exposure/gain/frame-length metadata and per-channel
  means under controlled light; compare front and rear. The front is RGGB 3840x2160; the
  rear is mode-dependent (built-in GRBG, Windows blob BGGR). Do not globally change Bayer
  or tuning without the raw evidence.

## 3. Keyboard and safe parity

- Both boots enumerate Type Cover `045E:09AE` (SSAM) and touchpad `045E:09AF`; the Ugreen
  storage `error -71` is USB, not the cover.
- Test safe: boot → reboot → type, with `surface_aggregator`/SSAM logging and the SAM
  shutdown mode recorded. Repeat debug as control.
- The safe DTB keeps the USB-C orientation switches for DP recovery; the debug deletes
  them. Do not delete them from safe without a DP recovery test. A separate parity DTB
  entry is the one-variable experiment if the USB `-71` matters.
- The safe SAM mode was `silent` at runtime; try `sp11.ssam_shutdown=default/clean` as a
  manual GRUB test only, not a default change, and record the next boot.

## 4. Instrumentation

- Debug GRUB: merge a single `trace_event=` list with `rpm:rpm_suspend,rpm:rpm_resume,
  rpm:rpm_idle,rpm:rpm_return_int,rpm:rpm_status,power:device_pm_callback_start,
  power:device_pm_callback_end,:mod:msm` and `trace_clock=mono`; keep
  `trace_buf_size=16M`. Start a live `trace_pipe` to the boot medium and sync during the
  action; the RAM ring alone is lost on reset.
- After a reset, boot debug with `rd.systemd.mask=systemd-pstore.service
  rd.break=pre-mount`, read `/sys/fs/pstore`, then `/var/lib/systemd/pstore`; do not rely
  on the automatic safe boot.
- Archive every boot under `out/device-logs/2026-11-03-rev23/<boot-id>/` with ISO hash,
  entry, cmdline, timestamps and the result table.

## 5. Outcome table

| Test | Control rev22 | Candidate rev23 | Interpretation |
|:--|:--|:--|:--|
| Debug idle 150 s | reset / stable | reset / stable | time-vs-camera trigger |
| Debug GPU-only | reset / stable | reset / stable | GPU path / BW vote association |
| Debug rear direct | reset / stable | reset / stable | rear D-PHY |
| Debug front direct | reset / stable | reset / stable | front C-PHY |
| Safe front direct | reset / stable | reset / stable | C-PHY without GPU |
| Safe Snapshot | crash / no LED | softpipe result | WirePlumber/llvmpipe |
| Keyboard safe reboot | freeze / works | freeze / works | SAM/EC vs USB-C |
