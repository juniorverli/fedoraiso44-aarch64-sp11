# Rev26 delivery matrix: audio closed loop, microphone, interfaces, camera

Scope of the goal: deliver the closed-loop audio + microphone and the
interfaces (LCD, USB 3, USB-C, USB4/Thunderbolt, camera). GPU and NPU are
post-installation by decision. This file records status and evidence; a line
without device evidence is not a claim of delivery.

| Item | State | Evidence / gap |
|:--|:--|:--|
| Speakers, public D26 | Works on device | Operator playback on safe/debug; volume capped by design (PA 6, digital/MIX 81) because no validated protection |
| Speakers, closed loop | Code complete, unproven | Guard lifetime 0011, calibration/VI 0024, graph-open 0026, muted metadata 0027; rev26 adds VI calibration event 0x08001511 consumption (fail-closed, layout unverified). CPS stream and measured R0/T0 still missing; muted matrix not run |
| Microphone | Works on device | UCM HiFi, DMIC 2.4 MHz clock patch, unity gain; operator confirms capture |
| LCD | Works on device | msm DPU panel on safe/debug; backlight through DP AUX |
| USB 3 | Works (ports) | Reference and our logs: USB-C data ports enumerate; Surface Dock connector unverified |
| USB-C (DP Alt Mode) | Works | orientation-switch restored in m15/m15-safe; typec/DP stack present (usb4 evidence, 2026-10-31) |
| USB4 / Thunderbolt | Not deliverable today | Linux has no Qualcomm USB4 host-router glue (hardware/usb4 status `survey`); the reference project also reports USB4/Thunderbolt as unsupported. Plain USB-C and DP Alt Mode are unaffected |
| Cameras (rear/front) | Streams work; colour pending | rev25/26: dual RGB streams in safe; AWB gain ceiling fix (front clips 2/10 calibrated illuminants with stock 4.0), calibrate tools; green/dark still needs the device RAW measurement |
| GPU | Post-installation | Debug live uses msm.skip_gpu=1 (driver skipped to avoid the first-use reset); the GPU experiment is `msm.skip_gpu=0` + `sp11.gpu_diag=1`; the msm first-use bug remains open |
| NPU | Post-installation | Private QAIRT/NPU installer staged; not part of the live image |
| Base | F44 now; F45 in migration | Kernel stays our 7.3.0-65.sp11.26.fc44; the F45 userland retarget is in progress with its own gates |

## What "closed loop complete" requires

1. The muted matrix on entry 23 (guard, VI, graph open, no playback).
2. The VI calibration event path verified on device (payload layout and R0
   per channel), or the per-unit R0CalQ24/T0CalQ6 values read from the
   owner's Windows data and installed post-installation.
3. A CPS stream in the private topology (generator refuses --with-cps until
   the chain is complete).
4. An independently verified physical-output inhibitor (a PA register read is
   not proof of silence).
5. Cooldown/recalibration policy from the Windows `QCAUD\Feature\SpeakerProtection`
   flags mapped to the Linux guard.

Until all five hold, the guard stays fail-closed and the public D26 path is
the only sound delivery.
