# Revision 23 investigation map: debug reset, safe camera, keyboard, safe parity

Input: operator copy `C:\sp11-logs-3-2`, archived at
`out/device-logs/m16-20261103-final32/`. Boots:

- `3edfc8b6-582e-4d5e-98bb-26e3cde07d52` — **safe**, ISO rev22, complete collector at 118.75 s.
- `15c54307-6dd6-473d-8c41-6c4b7c8ad46e` — **debug**, ISO rev22, early collector at 33.03 s;
  live kmsg ends at monotonic ~64.3 s.

## 1. What the logs already establish

1. **Front enumeration is fixed.** Both `cam -l` outputs list `Internal back camera` (OV13858) and
   `Internal front camera` (IMX681). The rev22 three-control blob works at enumeration level.
2. **MX clamp works at probe.** The debug `gpu.txt` has no `Mx Level 432 not found` line (rev21
   did); GMU firmware/HFI start returns 0. The GPU pin is `on`; GMU read-only `active`.
3. **Debug still resets, with no kernel record.** Live kmsg ends at ~64.3 s with Wi-Fi scan lines;
   no panic/oops/SSM/SMMU/watchdog/thermal line. SBSA `bootstatus: 0`. The debug early collector
   does not cover the reset; the pstore payload was not copied by a later boot.
4. **Safe survives the same hardware.** The safe boot runs 118.75 s and completes collection.
   Both boots have the same CAMSS/OV13858/IMX681 enumeration and the same ath12k firmware/board
   warnings; those are not sufficient to reset.
5. **Safe USB is flaky where debug is clean.** Safe `dmesg` at 17:30:41:
   `usb 3-1: Device not responding to setup address`, `device not accepting address 2, error -71`,
   then a successful re-enumeration at 17:30:44. Debug enumerates the Ugreen storage directly at
   17:36:09. The only functional DTB difference besides GPU is the USB-C orientation-switch:
   `m15-safe` re-adds `orientation-switch` to both QMP combo PHYs; `m15`/debug deletes it
   (`kernel/dtb-variants/...-m15.dts` vs `...-m15-safe.dts`, usb-typec patch 0003).
6. **Safe camera app ran but the LED stayed off.** Safe journal: `snapshot` ran 36.6 s and exited
   status 0 at ~94 s; no libcamera/portal error in the captured journal. The safe `cam -l` sees
   both sensors; the app may fail before `s_stream` (GPU-off preview) or open the wrong sensor.
7. **Bayer mismatch candidate.** The rear OV13858 media pad reports `SGRBG10` (GRBG), while the
   private rear blob manifest is `bayer: bggr` and the mode data is BGGR10. The front reports
   `SRGGB10` (RGGB), matching its manifest. A GRBG/BGGR mismatch produces the reported green tint;
   the dark image needs the AGC/exposure and crop/selection evidence.
8. **Missing early Spectra guard.** Safe journal at 3.9 s: `/usr/libexec/sp11-camera-spectra-guard:
   No such file or directory`, udev install command for `i2c_qcom_cci` retcode 127. The helper
   exists in the mounted rootfs but the initramfs udev rule runs before it is available; this is an
   image/initramfs bug to fix or silence, not yet proven to affect camera probe.

## 2. Hypotheses, ranked

### H1 — the camera stream is the debug reset trigger (highest)
The debug boot differs from safe by GPU enable and by the camera app actually streaming/LED. The
GPU now probes cleanly (MX clamp). A camera stream (rear D-PHY or front C-PHY via 0023) can fault
CAMSS/CSIPHY/CSID/VFE or a shared rail without a kernel oops. The safe boot never reaches
`s_stream` (LED off), so it does not reset. Test: debug GPU-only action (no camera) versus a
headless rear stream and a headless front stream, with live kmsg/trace and LED observation.

### H2 — GPU runtime/PM or a shared power domain still resets (still open)
The MX clamp removes the probe error but does not prove runtime votes. The GPU pin is on; the
debug reset has no kernel trace. Test: GPU-only action with live `power`/`drm_msm_gpu` tracepoints;
pin-off control; ACD/preemption only after the A/B. REA the Windows GPU/PMIC power sequence.

### H3 — safe camera LED off is a GPU-off preview/app issue, not CAMSS
Safe has no GPU; Snapshot may fail to create its GL preview and never start the libcamera stream.
Headless `cam --capture` in safe (no GUI) will light the LED if CAMSS/sensor is fine. If it does,
the safe fix is a software-rendering camera path or a small GPU enable, not a camera driver change.

### H4 — green/dark camera: rear Bayer mismatch plus AGC/crop
Fix the OV13858 mbus code/Bayer to BGGR (matching the private blob and tuning) or prove the sensor
is GRBG and regenerate the blob/tuning. Measure exposure/gain and the crop/selection rectangles;
the rear driver still lacks `get_selection`. Do not change 0023 rates without active clock/IRQ data.

### H5 — safe keyboard freeze is the USB-C orientation-switch/double-flip
Safe re-adds `orientation-switch`; debug deletes it. Safe shows USB `error -71`/address retry on
the Ugreen hub; debug is clean. If the keyboard is on that hub (or the Type Cover path shares the
USB-C/EC state), the debug-only fix explains the difference. Test: apply the orientation-switch
deletion to m15-safe (or a targeted quirk) and repeat the keyboard-after-reboot test; compare
`surface_aggregator`/EC logs and the USB tree.

### H6 — Type Cover/EC state after reboot differs (alternative)
The Type Cover HID `045E:09AF` and SPI touch enumerate in both. The safe reboot may leave the EC/SAM
or pogo keyboard in a bad state; debug may reset it via the GPU/EC path. Compare `ec-sam`/SSAM logs,
`surface_aggregator` events and the DTB power domains.

## 3. Workstreams and owners

1. **GPU/reset (gpu worker, Terra xhigh):** A/B GPU-only vs camera; live tracepoints; pstore;
   PMIC/EC/thermal; REA `qcdxkm8380.sys`, PMIC/EC; other projects (linux-sp11, archiso-aarch64-sp11,
   postmarketOS, Fedora aarch64). Update `hardware/gpu/`.
2. **Camera safe/debug + quality (cameras worker, Terra xhigh):** safe headless stream vs GUI;
   front/rear identification; Bayer/AGC/crop/tuning; the Spectra guard; REA `qccamplatform8380.sys`
   /`surfacecam*sensor8380.sys`; libcamera/ISP. Update `hardware/cameras/`.
3. **Keyboard/safe parity (usb-typec worker, Terra xhigh):** orientation-switch diff, USB -71,
   hub/keyboard; propose the safe DTB fix and test. Update `hardware/usb-typec/`.
4. **EC/SAM keyboard (ec-sam worker, Terra xhigh):** Type Cover/pogo/EC after reboot; compare
   safe/debug; propose EC/SSAM or DTB change. Update `hardware/ec-sam/`.
5. **Independent reviewers:** Antigravity Gemini 3.8 Flash High and Claude Sonnet 5.5 High read the
   same logs and challenge H1-H6; no edits.
6. **REA/web:** Windows GPU/PMIC/camera/USB drivers and public Surface Pro 11 Linux reports.

## 4. Device tests that discriminate (one variable per boot)

- **Safe headless rear:** `cam -l`, then `cam --camera 1 --capture=…` with the LED watched; no GUI.
- **Safe headless front:** same with the front index; stop on LED dark/reset.
- **Debug GPU-only:** no camera app; `vulkaninfo --summary`/short GL; live trace; confirm no reset.
- **Debug camera-only:** no GPU workload beyond the preview; rear then front separately; stop at first
  reset; copy pstore and live trace.
- **Keyboard after reboot:** boot safe, reboot, type; then debug, reboot, type; capture
  `libinput`, `hid`, `surface_aggregator`, `usb` logs. Test the orientation-switch variant.
- **Safe parity:** after the USB-C fix, repeat the safe boot and verify no `error -71`, keyboard
  responsive, camera LED with headless capture.

## 5. Safety

No IR/flash, no cap increase, no GMU `power/control` write, no speculative camera rate/CSID change,
no private ISO/log sharing. Preserve the D26 speaker path and the LED gate.

## 6. Rev23 evidence update (2026-11-03, after the workers)

- **Safe camera:** the full safe journal proves GNOME Snapshot selected the front IMX681 and
  configured 1920x1080 XRGB / SoftISP 3840x2160 RGGB10; WirePlumber PID 5829 SIGSEGV in
  llvmpipe (`llvm_pipeline_generic`) at 60.55 s; Snapshot lost the PipeWire target. No
  `s_stream`/buffer/frame is proven. The LED stayed off. The primary safe blocker is the
  WirePlumber/llvmpipe crash, not enumeration.
- **Debug reset:** the MX error is gone; GMU/HFI start return 0; the pin is on. The reset at
  ~64 s has no panic/oops/SMMU/watchdog/thermal line. The front camera is the default in
  safe; the debug app/sensor is not identified, but the front LED report and the safe
  front selection make the **front C-PHY stream** the top candidate. The **stale boot BW
  vote** is the second candidate; the 2026-10-24 upstream backport is in rev23 as a
  diagnostic candidate, with the rev22 ISO as control.
- **Green/dark:** the rear is mode-dependent (GRBG built-in, BGGR Windows modes); the front
  is RGGB. No global Bayer fix. The green/dark needs raw frames, exposure/gain metadata and
  per-channel means; AWB/CCM/AGC/tuning are the likely contributors.
- **Keyboard:** Type Cover is SSAM `045E:09AE`; safe SAM chose `silent` at runtime; the
  USB-C `-71` is the Ugreen storage. The keyboard freeze is more likely SAM/EC than the
  orientation switch. One-variable test needed.
- **Rev23 candidate:** kernel BW-vote backport, initramfs guard, safe-only WirePlumber
  softpipe wrapper, coredump metadata, rev23 gates. Control is the rev22 ISO. Tests in
  `plan/rev23-device-checklist.md`.
- **Review:** Gemini 3.8 Flash ranked front C-PHY first; Sonnet 5.5 found no proven cause
  and recommended the debug-idle 150 s and direct-camera A/B before any behavioral fix.
