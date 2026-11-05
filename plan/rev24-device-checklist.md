# Revision 24 device checklist (2026-11-03)

Control: rev23 ISO `out/iso/sp11-fedora44-aarch64-kiwi-20261103T185134Z-private.iso`,
SHA-256 `12b8f05430a721024be7b698b7a17b8b75cba93ce39323704ca915924e749770`.
Candidate: rev24 ISO `out/iso/sp11-fedora44-aarch64-kiwi-20261103T213714Z-private.iso`,
SHA-256 `7cf42a2125972f599650d9ec5bdb213eb27e21ba5d8bd200e2d02b3387937012`
(kernel 7.3.0-65.sp11.24.fc44.aarch64, active-C-PHY-trio, CSID-680 drop/crop and
VFE-680 MIPI_RAW candidates).

The rev24 kernel is a **candidate**, not a proven reset fix. The active-trio patch is the
prime source-level explanation for the debug front-stream reset; the CSID/VFE patches are
frame-path candidates. The rev23 control must be run for the same action.

## 0. Safety

- Stop at the first reset; copy the previous-boot kmsg, live trace and pstore before the
  next boot. Keep the private ISO/logs local and redact before evidence.
- No IR/flash, no cap increase, no GMU `power/control` write, no frequency/thermal change.
- Use the D26 speaker path and LED gate unchanged.

## 1a. Rev25 GRUB debug isolation matrix (one variable per boot)

The next image (rev24 kernel, image-only menu change) adds seven flat GRUB entries. Each is
line 1 `SP11 debug` with the same `m15` DTB and the same debug-only services (`sp11.entry=debug`),
plus exactly one variable named by `sp11.test=<id>`; boot one entry per test and change nothing
else. The `safe` default and the existing 12 entries are unchanged.

| Menu entry | One variable | What it isolates |
|:--|:--|:--|
| `SP11 debug, test multi-user (no GNOME)` | `systemd.unit=multi-user.target` | GNOME/GDM/Turnip/3D workload vs kernel+GPU idle |
| `SP11 debug, test ignore unused (regulator)` | `regulator_ignore_unused` | late regulator cleanup; debug already has `clk_ignore_unused pd_ignore_unused` (the archiso reference uses only these two) |
| `SP11 debug, test GPU pin off` | `sp11.gpu_pin=0` | GPU runtime-PM pin/forced resume |
| `SP11 debug, test ACD off` | `msm.disable_acd=1` | ACD/rail collapse (module parameter; unsafe/taints) |
| `SP11 debug, test preemption off` | `msm.enable_preemption=0` | preemption records/queues (module parameter) |
| `SP11 debug, test msm off (display may be off; logs only)` | `module_blacklist=msm` | GPU/display driver absent; `sp11.gpu_pin=0` skips the now-unusable pin helper; read the boot-medium logs |
| `SP11 debug, test software GL` | `systemd.setenv=LIBGL_ALWAYS_SOFTWARE=1` | userspace GL path; best effort, compare with multi-user |

The GPU worker's first pair is the existing `SP11 debug` control with no camera app for 150 s,
then the same boot plus only `msm.enable_preemption=0` (`test preemption off`), also no camera
app. The automatic collector's `cam -l` enumerates but does not stream; keep that identical
on both boots. Order: run the cheapest first (`multi-user`, then `preemption off` — the GPU
worker's strongest immediately testable difference — then `pin off`, `ACD off`, `ignore unused`,
`msm off`, `software GL`). A stable boot is not a fix by itself; repeat the
same entry once and record the boot ID, kmsg, trace and pstore. IFPC is not a module parameter
and is not in this matrix; it needs a kernel candidate and its own A/B.

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
- Rear orientation: the rev25 candidate `hardware/cameras/patches/0026-...rotation.patch`
  adds `rotation = <180>` metadata only. It does not rotate pixels in libcamera 0.7.2's
  simple pipeline (no writable sensor flips); if the consumer still shows the rear upside
  down, test a separately marked rear-only processed-frame 180° transform. Confirm with an
  asymmetric target in preview and saved output; check for double rotation; do not rotate the
  front. This needs a rev25 kernel/DTB build, not the menu-only ISO.
- Green/dark: save a RAW frame plus exposure/gain/frame-length metadata and per-channel
  means under controlled light. The front is RGGB 3840x2160; the rear is mode-dependent.
  Correct the report: front advertised exposure 4–3550 lines / gain 1–15.5152, rear
  4–3206 / 0–63.9922; these are limits, not applied frame values. The reference line-length
  8704/gain inversion remain gated on stable reception and measured line loss; do not change
  the private blob or gain law blindly.
- If measurements isolate AGC/brightness, the private per-sensor experiment
  (`hardware/cameras/userspace/quality/libcamera-sp11-rev25-agc-experiment.patch`, front-only
  2.5 vs 3.5) is the next separately named build; green may be AWB/CCM/CFA and is not fixed by
  the AGC target. Do not import Windows CCMs into git.

## 3. Keyboard and safe parity

- Type Cover is SSAM `045E:09AE` (touchpad `09AF`); the Ugreen `-71` is storage. The final34
  safe boot logged `default` at probe, then the rotor selected **`clean`** (not `silent`;
  `silent` was the older final32 safe value). The final34 archive has no identified cover
  keystrokes or typing result, so the safe keyboard outcome is unknown. Test safe → reboot →
  type, recording SSAM events, KIP state and outgoing SAM mode; debug is the control.
- First keyboard comparison uses the **existing safe entry** and an explicit, boot-only
  argument added with GRUB `e`: `surface_aggregator.shutdown_mode=default` versus
  `silent` (never `clean`); the rotor honors the explicit argument and does not advance.
  Do not add the SAM argument permanently to the menu; the menu checker forbids SAM
  arguments by policy. Record predecessor boot ID/mode and successor boot ID/mode.
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
