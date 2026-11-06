# Rev27 / Fedora 45 delivery matrix

Kernel: our 7.3.0-65.sp11.30.fc44 (series rev30, BTF on, CHECK_DTBS 0 warnings).
Userland: Fedora 45. The kernel did not move to the F45 build; only the image did.

| Item | State | Evidence / gap |
|:--|:--|:--|
| Sound, public D26 | Works on device, capped | Operator playback on safe/debug; the volume caps are unchanged |
| Sound, closed loop | ISO delivers it; hardware evidence pending the operator boot | Live line 24 (`m15-cl`, `-CL` model, `sp11.allow_nominal=1`) loads the private CL topology and supplements; `sp11-closed-loop-sense.service` holds the V/I trigger so the guard's sense-stream gate holds before playback; every other gate stays. Installed systems get a non-default `Fedora (SP11 closed-loop audio)` entry from post-installation |
| Microphone | Works on device | D28 UCM HiFi, DMIC clock patch, unity gain |
| LCD | Works on device | DPU panel on safe/debug |
| USB 3 / USB-C DP Alt Mode | Works (ports) | Type-C and orientation switches restored |
| USB4 / Thunderbolt | Not deliverable today | No Qualcomm USB4 host-router glue in Linux |
| Cameras | Streams work; colour measurement pending | AWB ceiling fix, calibrate tools; green/dark needs the device RAW |
| GPU | Post-installation | `msm.skip_gpu=1` on the live entries; first-use reset open |
| NPU | Post-installation | QAIRT staged, not shipped |
| Installer | Dual-boot first; live install + first boot | Anaconda refuses `inst.ks` on a live install, so the install entry boots the live system ("Install to Hard Drive", "Install alongside") and `sp11-first-boot.service` finishes the installed system once: UEFI entry, dual-boot menu, `msm.skip_gpu=1`, closed-loop entry, GRUB regeneration |

## Closed-loop sound: what is now different

Before this revision nothing started the V/I sense stream on the sound path. The
guard therefore refused every unmute (`the V/I sense stream is not running`), so
the closed loop could never make sound even with the topology loaded. Two pieces
close that gap:

1. **`sp11.allow_nominal=1` on line 24** (and the speaker first-test line): the
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

- L0 static (this ISO): pending on the build.
- L1 QEMU: pending on L0.
- Device: the operator boots line 24 and plays; the guard report names the gate
  if the DSP rejects the graph.

## Not claimed

- The `-CL` topology has not been booted on the device yet.
- CPS is absent from the topology; the supplement keeps the CPS-not-required
  flag.
- Measured R0/T0 comes from kernel patch 0028 events when the DSP sends them;
  the nominal file is the fallback.

## Closed-loop self-test (2026-11-06)

The ISO now proves the loop on hardware without any manual step and without
audible output: `sp11-closed-loop-selftest.service` runs on the closed-loop
entries, waits for the V/I stream and the calibration, plays one second of
digital silence to the speaker, and logs either
`RESULT: unmute allowed (no guard refusal)` or the refusal; it then opens the
microphone for one second to /dev/null and logs `RESULT: microphone capture
OK/FAILED`. No sample is stored and no control is written. The next device log
carries the evidence; no browser, tone or manual playback is needed.
