# Revision 21 device test checklist (2026-11-03)

Status: **GO for the single device test, no ISO or kernel rebuild**. This checklist is the
operator document for the boot. Where `plan/rev20.md` section 3, `hardware/gpu/test-plan.md`
items 1-4, `hardware/gpu/README.md` line 5 or the stale `image/README.md` log entries conflict
with this file, this file and D40 win. The worker-owned files still need their owners to sync
them (section 7); the device test does not wait for that.

## 0. Artifact and safety

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261103T011453Z-private.iso` |
| SHA-256 | `e55fb6e77469c1fade7d9103d24633648fcda83ea165f6be357e3a371bb56879` |
| Kernel | `7.3.0-65.sp11.21.fc44.aarch64`, series rev21 (88 patches), BTF 5935/5935 |
| L0 | 272 passed, 0 failed, 0 skipped |
| L1 | PASS, boot `ca63310a-c7ef-4cd3-b5b7-52e23626c542`; 8 allowed Fedora-stock TCG failures |

- This is the **private** ISO. Never share it, its logs or its record. Keep raw logs outside git
  and redact device identifiers before any evidence file (S5).
- S1/D26: open-loop speakers only; startup mute and `0.0` sink default stay. PA <= 6,
  WSA RX/MIX <= 81, UCM digital 72. No cap increase, no closed-loop claim, no `spk` entry.
- S2: IR illuminator and flash stay off. Do not enable them for any camera test.
- Collectors write only to the live boot medium, never to the internal disk. The Windows
  partition is read-only (S4); never mount it read-write and never touch it while hibernated or
  BitLocker-encrypted.
- Do not add `sp11.gpu_diag=1`, do not write `3d6a000.gmu/power/control`, do not add a
  ramoops node, and do not change the boot entries other than the single documented GRUB edit
  for the boot under test.
- Verify the stick was written with the ISO above before the first boot. A wrong hash stops
  the test.

Boot entries used here:

1. `SP11 debug` (line 1): m15 DTB, GPU on, early GPU pin **on**, EFI pstore args
   (`efi_pstore.pstore_disable=0 printk.always_kmsg_dump=1`).
2. `SP11 debug, safe (no GPU)` (line 2, default): m15-safe DTB, GPU off, **no** EFI pstore args.
3. `SP11 debug, speakers (closed-loop experiment; private)`: not part of this test.

L1 covers the `vmtest` entry only. The debug entry's pin/pstore/kmsg instrumentation is
static/fixture-checked; the first debug boot is its first runtime test.

## 1. Before the first boot (host side)

- Prepare rollback media:
  - primary: rev19 ISO `20261102T194754Z`, SHA-256
    `8d3dad66c212138da2d9ce35bda60de47b68cc3a763a44600f55779adca6260a` — L1 PASS and the
    round-2 audio/microphone-working image;
  - `49bbf53d41904c21f4ff8b0b3082c09bea8f244f41888e9dacea8e824051399d` (20261102T222639Z)
    is the round-3 boot-proven rev19, but that image is the audio-regressed one. Keep it only
    as a boot-proven fallback, never for an audio test.
  - keep `out/rpms/archive/7.3.0-65.sp11.19`.
- Inspect the ESP `sp11/` directory and remove `sp11/cdsp-experiment` and
  `sp11/cpufreq-uncapped` before the test. Do not create `sp11.gpu_diag=1`.
- Copy the rollback ISOs to the Windows side or a second stick with their hashes; never leave
  the only copy on the Surface.

## 2. EFI pstore positive control (before any GPU boot)

The safe entry deliberately lacks the EFI pstore arguments. After a debug reset the firmware
may boot the default safe entry, so "the next safe boot" cannot prove pstore. Do this control
first, on the debug entry:

1. Boot `SP11 debug`. Write a known marker and sync:

   ```sh
   printf '<6>sp11-pstore-marker %s\n' "$(cat /proc/sys/kernel/random/boot_id)" | sudo tee /dev/kmsg
   sync
   ```

2. Clean warm reboot into `SP11 debug`.
3. At the GRUB editor append `rd.systemd.mask=systemd-pstore.service rd.break=pre-mount`.
4. In the initramfs shell:

   ```sh
   mount -t pstore pstore /sys/fs/pstore 2>/dev/null || true
   ls -l /sys/fs/pstore
   ```

5. Record or copy the records, then continue the boot and inspect `/var/lib/systemd/pstore`.

If no record survives, record pstore as **unproven** and fall back to `sp11-kmsg-tail` plus the
SBSA watchdog `bootstatus`. Do not conclude "no pstore" from the automatic safe boot. No pmsg
sentinel: EFI pstore advertises dmesg only. Do not induce a crash.

## 3. Boot order (one variable per boot; stop the affected track on failure)

### Step 1 — camera-disabled LED map (no stream)

Boot `SP11 debug, safe (no GPU)` and append `module_blacklist=imx681,ov13858` at the GRUB
editor. This keeps the V4L2 privacy path from claiming the gpio-leds.

```sh
for led in /sys/class/leds/white:indicator /sys/class/leds/white:indicator-1; do
  echo 1 | sudo tee "$led/brightness"; sleep 1
  echo 0 | sudo tee "$led/brightness"
done
```

Record which physical indicator lights for each path (front near the user camera vs rear).
This is the independent camera-to-indicator wiring map. No stream and no manual simulation of
a streaming LED. Reboot without the blacklist afterwards. If the watched indicator stays dark
in the later stream steps, stop that stream.

### Step 2 — safe baseline

Boot `SP11 debug, safe (no GPU)` with no edits, no camera application and no audio test.
Confirm the desktop, no oops, `caps_ready: 1`, and that the collector ran.

### Step 3 — safe audio/microphone first test

Boot `SP11 debug, safe (no GPU)` and append `sp11.audio_first_test=1` at the GRUB editor.
No camera application and no camera stream in this boot.

- Test undocked, or explicitly select the built-in Speaker sink; a DP/HDMI sink outranks it.
- Before the tone:

  ```sh
  systemctl --user status sp11-audio-safety.service --no-pager || true
  wpctl get-volume @DEFAULT_AUDIO_SINK@
  ```

  If the helper timed out before the card appeared, mute the sink and set 5 % manually; do not
  skip the mute.
- Verify the fail-safe (`device.routes.default-sink-volume = 0.0`), `caps_ready: 1`, PA 6 and
  RX/MIX <= 81 (also check `alsa-info`/`amixer`).
- **5 % is a floor, not a proven audible level**: D32 measured it at about -78 dB. Start
  muted at 5 %, unmute, then raise one step at a time in the same session to the first
  audible level. Do not reboot to the 100 % path for the first audible test.
- Play a short known tone (at most 2 s), check both channels, distortion and heat, then stop.
  Stop immediately on distortion or heat; do not raise the caps.
- Microphone on the same clean boot, while speaking at about 30 cm: run the 2 s stereo
  `arecord` and, **while it is capturing**, run:

  ```sh
  amixer -c 0 contents
  ```

  Record `MultiMedia2 Mixer VA_CODEC_DMA_TX_0`, `VA DEC0/1 MUX`, `VA DMIC MUX0/1` and
  `VA_AIF1_CAP Mixer DEC0/1`. The automatic collector samples `amixer` before the capture and
  its filter omits MultiMedia2. Test both `hw:0,1` and `default`/PipeWire and record per-channel
  RMS/peak, channel order and the default source. Do not retain speech samples.

### Step 4 — safe camera graph only

Boot safe, no stream:

```sh
media-ctl -p
v4l2-ctl --list-devices
cam -l
```

Expect the rear OV13858 as the working sensor. The front IMX681 is **not expected in libcamera
in this build**: the shipped private register blob has `n_ctrls=0`, so the subdev exposes
neither `V4L2_CID_EXPOSURE` nor `V4L2_CID_ANALOGUE_GAIN`, and libcamera 0.7.2 drops the raw
sensor. That is a blob/driver limitation, not a failure of the 0023 C-PHY patch.

### Step 5 — safe rear stream (D-PHY; validates patch 0003)

Only after Step 1. Watch the rear indicator (GPIO105). Start the rear stream, ensure the LED is
on during the stream and off after, and save an RGB/YUV frame with sensible colour through
libcamera. Stop if the LED stays dark, or on any `csiphy_reset`, oops or SMMU fault. The rear
D-PHY path is the direct regression test for the 0x2000 CSIPHY window fix.

### Step 6 — safe front RAW diagnostic (exercises patch 0023, not libcamera)

Watch the front indicator (GPIO225). Use the media-controller/`v4l2-ctl` RAW diagnostic on the
IMX681/C-PHY path, with no IR illuminator and no flash. Enable the CAMSS dynamic debug and
sample the clocks while the front stream/RAW capture is active:

```sh
sudo sh -c 'echo "module qcom_camss +p" > /sys/kernel/debug/dynamic_debug/control'
# in a second terminal, while the front attempt is active:
sudo grep -E 'cam_cc_(cphy_rx_clk_src|csiphy2_clk|csi2phytimer_clk|csid_clk|csid_csiphy_rx_clk)' /sys/kernel/debug/clk/clk_summary
```

Patch `0023` requests `csiphy2` 480 MHz, `csiphy2_timer` 400 MHz, and `csid`/`csid_csiphy_rx`
480 MHz. Record the active rates, parents, enable counts, the negotiated RAW data type/VC
(RAW10 VC0 expects the diagnostic capture-control write `0x2b002b5`), the CSID IRQ/ECC/CRC
state and the media route. A debug request line is not a rate readback. Do not use `devmem` or
write CSID/PHY registers. A front frame through libcamera is **deferred** until the blob is
regenerated and the ISO rebuilt; do not read front absence in `cam -l` as a `0023` failure.
Stop on a dark LED, an oops, or an unexpected clock/CSID error; capture the exact error.

### Step 7 — debug GPU with the shipped early pin (safety-net/capture boot)

Boot `SP11 debug` as shipped: GPU on, early pin on, EFI pstore args present. No camera
application, no `sp11.gpu_pin=0`, no `sp11.gpu_diag=1`, no 3+3 repeats. The pin suppresses the
66 ms runtime-PM transitions and the pin write can itself force a GMU resume, so a clean boot
here **does not validate the 0005/0006 GMU vote fixes**; label it safety-net-only. Record:

- the pin kmsg timestamp (`sp11-gpu-pm-early` line) and its readback;
- GPU `power/control`, `runtime_status`; GMU state read-only;
- every GMU firmware/HFI start and its timestamp, the first autosuspend, the reset time;
- SBSA watchdog `bootstatus/status/timeleft`, AC/battery state;
- whether pstore or the kmsg tail survived.

The udev pin can run after the first in-kernel DRM open during `msm` probe, so do **not** use
"first `GPU_BOOT_TRACE` after the pin" as an acceptance predicate. Judge the pin by its
timestamp against the first autosuspend/post-pin GMU start. The debug entry has no
`power:runtime_*`/`drm_msm_gpu:*` tracepoints (only glink/smp2p/aoss/rpmh); record that
limitation.

### Step 8 — pin-off kernel-only boot (first fix-validation test)

Only after Step 7 completes its observation window with no reset/hang. Boot `SP11 debug` and
append `sp11.gpu_pin=0`. This is the first controlled test of the 0005/0006 GMU vote fixes;
compare the same observations as Step 7. Do not start the 3+3 repeat matrix before this result.
Note that patches 0004/0007 modify `a6xx_pm_resume`, which this GPU's `a7xx_gpu_funcs` does not
use; they are tree fixes, not evidence for this reset.

### Step 9 — GPU fallback variables (only after a pin-off reset)

One variable per boot, no combinations:

1. `msm.disable_acd=1` on the GRUB line. It is `module_param_unsafe`, so it taints the kernel
   and logs a dangerous-option notice. `adreno.*` is silently ignored; the module is `msm`.
2. If unchanged, a separate boot with `msm.enable_preemption=0`.
3. IFPC has no module parameter; it requires a kernel build. The MX clamp is only for a dmesg
   `Mx Level ... not found in the RPMh list`/GMU probe failure after 0005 and also requires a
   build.

No speculative GPU patch, no frequency/thermal change, no 3+3 repeats before the pin-off result.

## 4. Log archive after each boot or stream

```sh
systemctl --user start sp11-post-session-collect.service
# wait for the unit to finish
sudo /usr/libexec/sp11-log-collector once
```

Verify the `COMPLETE` marker, then copy the `<boot-id>` directory to
`out/device-logs/2026-11-03/<boot-id>/` together with the ISO hash, the GRUB entry and the
effective command line. Do this before the next boot. Keep the logs private and git-ignored;
redact before writing any evidence file. After a debug reset, do not rely on the automatic safe
boot: select debug (or append the EFI pstore arguments) and copy pstore before any further
shutdown.

## 5. Stop rules

- Camera: stop the stream if the watched LED stays dark, on a `csiphy_reset`/oops/SMMU fault,
  or on an unexpected clock/CSID error. Never enable IR or flash.
- Audio: stop on distortion or heat; never raise PA/RX/MIX caps or remove the startup mute.
- GPU: no automatic retry after a reset; power off, copy the logs and record the outcome. A
  silent reset with no pstore/watchdog record is inconclusive, not a hardware conclusion.
- Private data: stop and scrub if any device identifier or raw sample would leave the private
  log area.

## 6. Rollback

- If the rev21 safe entry does not reach GDM, re-flash the L1-PASS rev19 `8d3dad66...` rather
  than debugging on the only boot medium. `49bbf53d...` is boot-proven but audio-regressed; use
  it only if the `8d3dad66...` medium itself fails.
- Keep the rev19 RPM archive for a kernel rollback.

## 7. Documentation sync owed by the worker owners (no device gate)

The checklist above overrides these stale texts; their owners must sync them in their next
session:

- `hardware/gpu/test-plan.md` items 1-4 (dual-device diagnostic, GMU `power/control` write,
  pmsg sentinel, ramoops, "next safe boot") and `hardware/gpu/README.md` line 5 / requests.
- `image/README.md` log/description lines that say the GPU pin was disabled, the helper sets
  30 %, the ACP ceiling is 0.251, or safe has cameras off (`1135`, `1139`, `1141`, and the
  related log entries).
- `scripts/image-build-kiwi.sh` comment at `549-550` describing safe/debug DTB contents.
- `journal/2026-11-02.md:130` (audio on debug) and `:141` (failed-unit count wording).

## 8. Waivers and limitations recorded for this test

- Camera protocol §5.1: no independent `hardware/cameras/crosscheck/` artifact exists for the
  0x2000 CSIPHY and 0xf000 VFE windows. Orchestrator waiver for this device boot: the values
  remain **Inference**; the device result is the validation. Do not mark the camera component
  `sw-ready` or `pass` until the cross-check is completed or the device evidence itself
  reproduces the values. (Recorded in D40.)
- Front libcamera acceptance is deferred: the shipped blob has no control records. Only the
  RAW diagnostic exercises 0023 in this build.
- The first GPU boot is pin-on safety-net only. The pin-off boot is the first test of the
  kernel vote fixes.
- The udev pin may land after the first in-kernel DRM open; the trace-before-pin predicate is
  not valid.
- The debug entry has no GPU runtime-PM tracepoints; a reset with no captured transition can
  remain ambiguous.
- Audio 5 % may be inaudible (-78 dB per D32); the ramp procedure is mandatory, and an
  inaudible 5 % is not a speaker failure.
- The camera indicator wiring and the C-PHY rails/CSID routing remain inferences until the LED
  map and the RAW diagnostic produce device evidence.
