# Windows speaker protection: how R0/T0 and the volumes are handled — 2026-11-05

Scope: static REA of the two Windows audio drivers shipped for this device. No
device run, no kernel change and no sound. Values are structure and identifiers
only; no calibration values were recovered from this machine (see limitations).

## Binaries

- `sources/windows/DriverStore/qcaudminiport_base8380.inf_arm64_738ad101f903ae9b/qcaudminiport8380.sys`,
  SHA-256 `79b26804d05332304c736c4e03e942db6a07ea886a2b07f3a4ff5947d1d05531`,
  Ghidra 12.1.4, `AARCH64:LE:64:v8A` (catalog language).
- `sources/windows/DriverStore/qcadcm8380.inf_arm64_f5fba49e0720d715/qcadcm8380.sys`,
  SHA-256 `37f76305ac8051b0b03b6d2ce1df7a353253debf546e512e447c9d95ec661429`.

## What the miniport does (qcaudminiport8380.sys)

`FUN_14008bdc0` is the speaker-protection initialisation. It reads the feature
key `QCAUD\Feature\SpeakerProtection` (values `SpeakerCoolDownTimerInSec`,
`IsSpeakerProtQuickCalib`), allocates its work item/timer, registers a callback
and sends a 28-byte (0x1c) message through the GLINK/QMI audio path. A failure
leaves the protection in the "not calibrated" state (flags at +0x118/+0x11c/
+0x138), which is the same fail-closed shape the Linux guard uses.

## What the ACDB driver does (qcadcm8380.sys)

Strings (addresses in the loaded image):

- `SpeakerProtectionInfo\` at `0x1400b03a0`; value names `R0CalQ24`
  (`0x1400b0420`) and `T0CalQ6` (`0x1400b04a8`), and `UseCalibR0T0`
  (`0x1400b04e8` onward). Log: "R0T0 parameters got from registry R0 %x, T0 %x".
- Setter path: `CreateSpkrProtR0T0ViPayload` → `gsl_set_tag_data_to_acdb` →
  `AUDIO_DSP_IOCTL_GRAPH_SET_SPKR_PROT_CALIB_PARAMS`; readback:
  `AUDIO_DSP_IOCTL_GRAPH_GET_SPKR_PROT_R0T0_MODE`.
- DSP custom events registered in `SetSpkrProtEndpointEffect` (decompiled):
  - `0x08001511` = `EVENT_ID_VI_CALIBRATION`,
  - `0x0800138C` = `EVENT_ID_SPv5_SPEAKER_DIAGNOSTICS`,
  - a per-speaker calibration event (`EVENT_ID_VI_PER_SPKR_CALIBRATION`).
  The event payload logs `channel:%u R0:0x%x Mid:0x%x`; a per-speaker variant
  carries one R0 per channel.
- Diagnostics: `Speaker temperature overshoot condition arise`,
  `DC Protection Failed`, `Calibration requested when speaker is active ... not
  allowed`, cooldown via `SpeakerCoolDownTimerInSec`.

So Windows' model is **hybrid**: per-unit R0/T0 can be provisioned in the
registry (`UseCalibR0T0`), otherwise the DSP runs the (quick) VI calibration and
reports measured R0 back through event `0x08001511`. The volumes are applied by
the DSP with those values; the driver sends/reads the same parameter the Linux
side already uses.

## Linux mapping

- Linux already sends `PARAM_ID_SP_TH_VI_R0T0_CFG = 0x080011f5`
  (`audioreach-sp11.c`), the same set-parameter Windows uses.
- Missing on Linux: registering and consuming the calibration events
  (`0x08001511`, `0x0800138c`) from the SP/VI module, per-channel R0 readback,
  the quick-calibration trigger and the cooldown policy. That is the kernel
  patch that would let the guard learn the measured R0/T0 instead of requiring
  a static file.
- The static 36-byte `SP11CA01` file remains the fallback; its R0 must be Q24
  and T0 Q6, matching the Windows registry scaling.

## Limitations

- The values are **not present** in this machine's live registry under
  `Enum\ROOT`, `Enum\SWD`, `Enum\ACPI`, `Services\qcadcm8380` or
  `SOFTWARE\Qualcomm` (searched with `reg.exe query /f R0CalQ24 /s`). They may
  be created only during a Windows audio session, held by the DSP, or stored in
  a per-unit ACDB delta not found under `C:\ProgramData`.
- No PDB was available; names are REA's recovered identifiers, not symbols.
- No payload bytes for the calibration event were decoded; the event IDs and
  the log-field names are observed, the structure layout is not.
- Static evidence only: no Windows audio session, no Linux device run and no
  claim that the Linux event path works.
