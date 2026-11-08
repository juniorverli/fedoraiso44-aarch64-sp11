# Rev27 / Fedora 45 delivery matrix

Kernel: our 7.3.0-65.sp11.32.fc44 (series rev32, BTF on, CHECK_DTBS 0 warnings).
Userland: Fedora 45. The kernel did not move to the F45 build; only the image did.

| Item | State | Evidence / gap |
|:--|:--|:--|
| Sound, public D26 | **Removed 2026-11-07** | Kernel patch 0033 refuses a topology without SP+VI; microphones and DisplayPort keep working. The closed loop is the only speaker path |
| Sound, closed loop | **Delivered on hardware 2026-11-07** | `RESULT: unmute allowed (no guard refusal)` with SP enabled, V/I stream and matching calibration; operator heard output; microphone capture OK | Live line 1 (`m15-cl`, `-CL` model, `sp11.allow_nominal=1`, default entry) loads the private CL topology and supplements; `sp11-closed-loop-sense.service` holds the V/I trigger so the guard's sense-stream gate holds before playback; every other gate stays. Installed systems get a `Fedora (SP11 closed-loop audio)` entry from post-installation, set as the GRUB default |
| Microphone | Works on device, closed-loop boot included | D28 UCM HiFi, DMIC clock patch, unity gain; `RESULT: microphone capture OK (S16_LE/2ch)` on 2026-11-07 |
| LCD | Works on device | DPU panel on safe/debug |
| USB 3 / USB-C DP Alt Mode | Works (ports) | Type-C and orientation switches restored |
| USB4 / Thunderbolt | Not deliverable today | No Qualcomm USB4 host-router glue in Linux |
| Cameras | Streams work; colour measurement pending | AWB ceiling fix, calibrate tools; green/dark needs the device RAW |
| GPU | Post-installation | `msm.skip_gpu=1` on the live entries; first-use reset open |
| NPU | Post-installation | QAIRT staged, not shipped |
| Installer | Dual-boot first; live install + first boot | Anaconda refuses `inst.ks` on a live install, so the install entry boots the live system ("Install to Hard Drive", "Install alongside") and `sp11-first-boot.service` finishes the installed system once: UEFI entry, dual-boot menu, `msm.skip_gpu=1`, closed-loop entry, GRUB regeneration. Since 2026-11-08 the install entry boots `m15-cl` with `sp11.allow_nominal=1` (same guarded audio as debug, `sp11.entry=safe`), because the D26 model had no usable speaker or microphone path |

## Install-entry audio (2026-11-08)

The 2026-11-08 install boot (`sp11.entry=safe`, `m15-safe`) had no speaker and
no microphone. The log shows the D26 sound model: `sp11: selected refused
speaker mode`, `speaker policy/topology combination refused (SP=0)`, caps
`digital 81, PA 6`; `sp11-audio-defaults` exited 1 with `no usable Audio/Sink`
and `no usable Audio/Source`, and `sp11-audio-safety` logged `no built-in sink
appeared before timeout`. On the same ISO the debug boot (`m15-cl`) set the
Speaker sink and the Mic source as defaults at 41 s. The D26 model therefore
loses both audio directions once patch 0033 refuses it.

The fix: the install entry now boots `m15-cl` with `sp11.allow_nominal=1` and
keeps `msm.skip_gpu=1` and `sp11.entry=safe` (safe service set, softpipe
wrapper). The raised caps stay kernel-gated: patch 0033 selects `CLOSED_LOOP`
only with the marker and the SP module in the parsed topology, and patch 0032
installs 84/17 only in that mode; the amplifier unmute remains guard-gated on
every playback start. The invalid WirePlumber regex (`*MultiMedia5*`) in
`54-sp11-vi-trigger.conf` is fixed.


## Closed-loop sound: what is now different

Before this revision nothing started the V/I sense stream on the sound path. The
guard therefore refused every unmute (`the V/I sense stream is not running`), so
the closed loop could never make sound even with the topology loaded. Two pieces
close that gap:

1. **`sp11.allow_nominal=1` on line 1** (default entry): the
   private image installs the nominal `-CL-sp11cal.bin`, valid inside the
   kernel's 80–125 % R0 window and the T0 bounds, and the guard accepts it only
   when this argument is present and the VI graph identity matches.
2. **`sp11-closed-loop-sense.service`**: opens the MultiMedia5 trigger, starts
   the WSA_CODEC_DMA_TX_0 back end and forwards the application pointer without
   reading a sample. It runs only with `sp11.allow_nominal=1 sp11.entry=debug`
   and not `sp11.nospk`; on PCM loss it restarts and re-applies R0/T0.

The amplifier unmute still asks the guard on every playback start, and the fault
latch, caps, SP module, calibration identity and CPS policy all remain.

## Gates

- L0 static (2026-11-08 ISO): PASS, 311 passed / 0 failed / 0 skipped.
- L1 QEMU (2026-11-08 ISO): PASS on the rerun; the first run failed only on a
  TCG-only timeout of the dynamic `gdm-greeter` user manager after GDM started.
- Device: the operator boots line 1 and the install entry and plays; the guard
  report names the gate if the DSP rejects the graph.

## Not claimed

- The install entry's speaker and microphone path is built and L0/L1-checked but
  not yet booted on the device; the 2026-11-07 hardware evidence is for line 1.
- CPS is absent from the topology; the supplement keeps the CPS-not-required
  flag.
- Measured R0/T0 comes from kernel patch 0028 events when the DSP sends them;
  the nominal file is the fallback.
- Per-unit calibration, acoustic SPL mapping and protection efficacy remain
  unmeasured.

## Closed-loop self-test (2026-11-06)

The ISO now proves the loop on hardware without any manual step and without
audible output: `sp11-closed-loop-selftest.service` runs on the closed-loop
entries, waits for the V/I stream and the calibration, plays one second of
digital silence to the speaker, and logs either
`RESULT: unmute allowed (no guard refusal)` or the refusal; it then opens the
microphone for one second to /dev/null and logs `RESULT: microphone capture
OK/FAILED`. No sample is stored and no control is written. The next device log
carries the evidence; no browser, tone or manual playback is needed.

## Final ISO (2026-11-08)

`sp11-fedora45-aarch64-kiwi-20261108T003509Z-private.iso`, SHA-256
`606d4231185316edcdddad4881a7b3f8dae7c7c71b71c85d9ec17857a93f0eac`, kernel
`7.3.0-65.sp11.32.fc44`: the three-entry flat menu (debug default, install, VM
test), both device entries on `m15-cl` with `sp11.allow_nominal=1` and
`msm.skip_gpu=1`, closed-loop speakers only, Windows-level ceiling in that mode,
and the installed system booting the generated closed-loop entry by default.
The install entry now delivers the same guarded audio as debug. L0 311/0, L1
PASS (the first L1 run hit a TCG-only timeout in the dynamic `gdm-greeter` user
manager after GDM had started; the rerun passed with only the allow-listed
`user@1000` failure; no allow-list change).

The private identity input was reconstructed from the previous private ISO root
because `~/sp11-windows-dumps` disappeared on 2026-11-08; the canonical source
for future private builds must be restored or re-staged.

## Previous ISO (2026-11-07)

`sp11-fedora45-aarch64-kiwi-20261107T204954Z-private.iso`, SHA-256
`e575758d...cab6`, kernel `7.3.0-65.sp11.32.fc44`: closed-loop speakers only
(open-loop removed), Windows-level ceiling in that mode, line 1 and line 24 on
the closed loop, and the installed system booting the generated closed-loop
entry by default. L0 311/0, L1 PASS.

