# Revision 24 device checklist (2026-11-03)

Control: rev23 ISO `out/iso/sp11-fedora44-aarch64-kiwi-20261103T185134Z-private.iso`,
SHA-256 `12b8f05430a721024be7b698b7a17b8b75cba93ce39323704ca915924e749770`.
Candidate: rev24 ISO (kernel 7.3.0-65.sp11.24.fc44.aarch64, active-C-PHY-trio,
CSID-680 drop/crop and VFE-680 MIPI_RAW candidates; fill name/hash from the record).

The rev24 kernel is a **candidate**, not a proven reset fix. The active-trio patch is the
prime source-level explanation for the debug front-stream reset; the CSID/VFE patches are
frame-path candidates. The rev23 control must be run for the same action.

## 0. Safety

- Stop at the first reset; copy the previous-boot kmsg, live trace and pstore before the
  next boot. Keep the private ISO/logs local and redact before evidence.
- No IR/flash, no cap increase, no GMU `power/control` write, no frequency/thermal change.
- Use the D26 speaker path and LED gate unchanged.

## 1. Decisive reset split (cheapest first)

### A. Debug idle, no camera, 150 s
Boot `SP11 debug` (rev23 control first, then rev24); do not open Snapshot/any camera.
Leave the desktop idle for at least 150 s.

- Reset near 64 s on rev23 and/or rev24: time/GPU/EC/PMIC path. The rev24 active-trio
  patch cannot explain an idle reset; continue GPU/PMIC and the rev23 BW-vote A/B.
- Rev23 stable: the original reset is camera-action-associated; go to B/C.
- Rev23 resets, rev24 idle stable: the active-trio/legacy C-PHY or another rev24 change is
  implicated, but only the marked stream A/B can separate it.

### B. Debug front direct
On fresh debug boots, run `cam -l`, then the direct front capture with `--metadata`, LED
watched, live kmsg and trace to the boot medium. Stop at the first reset.

- rev23 resets, rev24 survives and completes buffers/IRQs: the legacy C-PHY trio
  programming is the leading cause of the front-stream reset.
- Both reset: the active-trio change is insufficient; the CSID/VFE/front timing or a
  hardware/power path remains.
- Both survive: the original reset was not reproduced; repeat once and do not claim a fix.

### C. Debug rear direct
Same as B for the rear OV13858. This validates that the CSID-680/VFE-680 candidates did not
regress the working D-PHY path and separates front C-PHY from shared CAMSS.

### D. Safe direct
On safe (GPU off), run direct `cam` front and rear, one per boot, LED watched. If a direct
front stream resets in safe, the C-PHY path is independent of the GUI/GPU. If it works,
the safe UI blocker is the WirePlumber/llvmpipe crash.

## 2. Safe camera and quality

- Rev23/24 include `/usr/libexec/sp11-wireplumber-safe`: on `sp11.entry=safe` it forces
  `GALLIUM_DRIVER=softpipe LIBGL_ALWAYS_SOFTWARE=1` for WirePlumber. Test Snapshot safe.
  If it still crashes, collect `coredumpctl` (the image collector now records metadata).
- Green/dark: save a RAW frame plus exposure/gain/frame-length metadata and per-channel
  means under controlled light. The front is RGGB 3840x2160; the rear is mode-dependent.
  The reference line-length 8704/gain inversion remain gated on stable reception and
  measured line loss; do not change the private blob or gain law blindly.
- If the front is fixed but the image is still green/dark, next experiment is the
  reference's soft-IPA AGC target/CCM/tuning against the current YAML, one variable.

## 3. Keyboard and safe parity

- Type Cover is SSAM `045E:09AE` (touchpad `09AF`); the Ugreen `-71` is storage. Safe SAM
  chose `silent`. Test safe → reboot → type, recording SSAM events, KIP/POS and tablet
  switch, and outgoing SAM mode. Debug is the control.
- POS/tablet-switch patch is an opt-in diagnostic; it is not proven for this reboot
  freeze. Do not change the default or the USB-C orientation switches without the
  one-variable test and a DP recovery check.

## 4. Instrumentation

- Debug GRUB: one `trace_event=` list with `:mod:msm`, `rpm:rpm_suspend,rpm:rpm_resume,
  rpm:rpm_idle,rpm:rpm_return_int,rpm:rpm_status,power:device_pm_callback_start,
  power:device_pm_callback_end`, `trace_clock=mono`, `trace_buf_size=16M`; live
  `trace_pipe` to the boot medium.
- After a reset: boot debug with `rd.systemd.mask=systemd-pstore.service rd.break=pre-mount`,
  read `/sys/fs/pstore`, continue and read `/var/lib/systemd/pstore`.
- Archive every boot under `out/device-logs/2026-11-03-rev24/<boot-id>/`.

## 5. Outcome table

| Test | rev23 | rev24 | Interpretation |
|:--|:--|:--|:--|
| Debug idle 150 s | reset/stable | reset/stable | time vs camera |
| Debug front direct | reset/stable | reset/stable | active-trio C-PHY |
| Debug rear direct | reset/stable | reset/stable | D-PHY/CAMSS regression |
| Safe front direct | reset/stable | reset/stable | C-PHY without GPU |
| Safe Snapshot | crash/stream | softpipe result | WirePlumber/llvmpipe |
| Keyboard safe reboot | freeze/works | freeze/works | SAM/EC vs USB-C |
