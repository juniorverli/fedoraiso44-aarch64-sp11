# Revision 22 device checklist (2026-11-03)

Status: build in progress. Fill the artifact line from `out/iso/<name>.json` before the boot.
This checklist supersedes `plan/rev21-device-checklist.md` for the rev22 boot; the safety rules in
`plan/risks.md` §1 still override everything.

## 0. Artifact and safety

| Item | Value |
|:--|:--|
| ISO | `out/iso/<rev22-private>.iso` (from the build record) |
| SHA-256 | from `out/iso/<rev22-private>.iso.sha256` |
| Kernel | `7.3.0-65.sp11.22.fc44.aarch64` |
| L0/L1 | must be 0 failures and PASS before the boot |

- Private ISO: never share it or its raw logs; keep logs on the live boot medium and copy them
  to `out/device-logs/2026-11-03/` before shutdown; redact before evidence (S5).
- S1/D26: open-loop speakers only; startup mute and the `0.0` sink default stay. PA <= 6,
  WSA RX/MIX <= 81, UCM digital 72. No cap increase, no `spk` entry.
- S2: IR illuminator and flash stay off. Camera streams only with the physical privacy LED
  watched; stop if it stays dark.
- No `sp11.gpu_diag=1`, no GMU `power/control` write, no ramoops, no speculative tuning or
  frequency change.

## 1. Audio first (safe entry, normal 100 %)

The rev22 UCM removes the `Speakers Volume` alias cset while keeping both physical PA writes.
This is the audio correction under test.

1. Boot `SP11 debug, safe (no GPU)` with no camera application and no first-test marker.
2. Before playback:

   ```sh
   systemctl --user status sp11-audio-safety.service --no-pager
   wpctl get-volume @DEFAULT_AUDIO_SINK@
   wpctl inspect @DEFAULT_AUDIO_SINK@ | grep -E 'node.name|device.name|audio.channels'
   journalctl --user -b --no-pager | grep -i 'Failed to enable UCM device Speaker'
   ```

   The UCM warning must be absent; the sink must be the built-in Speaker and unmuted at the
   startup level (100 % normal boot).
3. Play a short known tone. Record left/right, perceived level, distortion and heat. If it is
   still low, capture the sink and stream levels, `pw-dump`, `amixer -c 0 contents` and the UCM
   verb/device state **during playback**; do not raise caps or remove the startup mute. Stop on
   distortion or heat.
4. Microphone: 2 s stereo `arecord` at about 30 cm, with a concurrent `amixer -c 0 contents`
   recording `MultiMedia2 Mixer VA_CODEC_DMA_TX_0`, `VA DEC0/1 MUX`, `VA DMIC MUX0/1` and
   `VA_AIF1_CAP Mixer DEC0/1`; both `hw:0,1` and default; per-channel RMS, channel order, no
   speech retained.

## 2. Cameras (safe entry; LED gate)

The rev22 private staging replaces the IMX681 blob with three control records (exposure,
analogue gain, frame length) and four modes. The front should now enumerate; streaming is still
a separate test.

1. Graph and enumeration only:

   ```sh
   media-ctl -p
   v4l2-ctl --list-devices
   cam -l
   v4l2-ctl -d /dev/v4l-subdevN -L   # for each OV13858/IMX681 subdev
   ```

   Expect both `Internal back camera` (OV13858) and the front IMX681. If the front is absent,
   record the exact mandatory-control error, the installed blob SHA-256/size and the subdev
   controls; do not change 0023.
2. Rear OV13858: complete the camera-disabled LED map first (`module_blacklist=imx681,ov13858`,
   toggle `white:indicator`/`white:indicator-1`), then a **headless** capture with continuous
   logs per `hardware/cameras/test-plan.md` (live kernel journal, 1 s state sampler, LED
   observation). Save an RGB/YUV frame; stop on a dark LED, oops, CSID/PHY error or reset.
3. Front IMX681: only after the rear and the LED map; use the RAW/stream diagnostic under the
   front LED and record exposure/gain controls, C-PHY clocks, CSID IRQ/ECC/CRC and the exact
   error or frame. No IR/flash; stop on a dark LED, oops or reset. Front libcamera acceptance is
   not claimed until a frame and colour are saved.

## 3. GPU (debug entry)

The rev22 kernel adds the upstream MX dependency-vote clamp. It is a correctness fix, not a
proven reset fix; the round must say so.

1. Boot `SP11 debug` as shipped (early pin on). Record the pin kmsg line
   (`3d00000.gpu ... written=on readback=on`), GPU/GMU PM state and every `GPU_BOOT_TRACE`.
   Confirm whether `Mx Level 432 not found` is absent.
2. A/B with timestamped markers and live logs:
   - first a GPU-only action (e.g. `vulkaninfo --summary` or a short `glmark2-es2-wayland`
     run) with no camera;
   - then, on a separate boot, a marked camera open/stream with the same logging.
   Stop at the first reset; recover the complete previous-boot stream and any actual pstore
   payload after the reset. A reset only during the camera action is correlation, not proof; a
   reset during the GPU-only action strengthens GPU involvement but is not conclusive.
3. Do not start the 3+3 repeat matrix, ACD/preemption or IFPC experiments until the A/B result
   and the pin-off (`sp11.gpu_pin=0`) result. No frequency or thermal change.

## 4. CPU

No change is expected. Confirm ten online CPUs and no hotplug/stall/fault; the two
firmware-disabled cores are already absent (soc-boot evidence).

## 5. After each boot

```sh
systemctl --user start sp11-post-session-collect.service   # wait for it
sudo /usr/libexec/sp11-log-collector once
```

Verify the `COMPLETE` marker, then copy `<boot-id>/` to `out/device-logs/2026-11-03/<boot-id>/`
with the ISO hash, entry, cmdline and timestamps before the next boot. Keep logs private and
redact before evidence.
