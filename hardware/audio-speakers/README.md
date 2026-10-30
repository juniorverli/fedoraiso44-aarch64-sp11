# audio-speakers

## 1. Summary

Two WSA8845 smart amplifiers on SoundWire, driven by the ADSP through AudioReach. Safe use requires speaker protection: a thermal and excursion model fed by voltage/current (VI) sense from the amplifiers. Linux 7.3 has the codec, the machine driver and the AudioReach module IDs for protection, but no wired-up graph or calibration for this machine. Status: `designed` (2026-10-30): safe bring-up plan and three patches written, nothing built or run; speakers stay off under S1.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `MEDIA ADCM\VEN_QCOM&DEV_0CE6&SUBSYS_MSHW0486&REV_0d (ACX audio)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ADCM\VEN_QCOM&DEV_0CC1&SUBSYS_MSHW0486&REV_0d` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `AUCD\VEN_QCOM&DEV_0C29&SUBSYS_MSHW0486&REV_0d` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ADSP\VEN_QCOM&DEV_0C22&SUBSYS_MSHW0486&REV_0d (calibration manager)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ADSP\VEN_QCOM&DEV_0C0F (slimbus/soundwire)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcaudminiport_base8380` | TBD |
| `qcaudminiport_apo8380` | TBD |
| `qcaucd8380` | TBD |
| `surface_aucdext8380` | TBD |
| `qcadcm8380` | TBD |
| `surface_acsp8380` | TBD |
| `surface_audiominiext8380` | TBD |
| `qcasd8380` | TBD |
| `qcasd_apo8380` | TBD |
| `surface_asdext8380` | TBD |
| `qcslimbus8380` | TBD |
| `dax3_ext_qc` | TBD |
| `surfaceapoextension` | TBD |
| `surfaceaposwcinstaller` | TBD |
| `surfaceihvaudiofilterdriver` | TBD |

## 4. Linux 7.3

- Driver: `sound/soc/qcom/x1e80100.c`
- Driver: `codecs/wsa884x`
- Driver: `codecs/lpass-wsa-macro`
- Driver: `qdsp6 q6apm/audioreach (MODULE_ID_SPEAKER_PROTECTION, _VI)`
- Driver: `soundwire/qcom`
- Driver: `userspace: AudioReach topology, alsa-ucm-conf`
- DT: `x1-microsoft-denali.dtsi sound, &swr0 left_spkr/right_spkr, &lpass_tlmm`
- Machine driver speaker ceilings: `sound/soc/qcom/x1e80100.c:36-52` (WSA digital volume 81 = -3 dB, `PA Volume` 6 = 0 dB, `snd_soc_limit_volume`).
- No protection in the driver: `sound/soc/codecs/wsa884x.c` has no interrupt handler or thermal action; hwmon temperature only (`:1947-1960`).
- Upstream topology `X1E80100-Microsoft-Surface-Pro-11` (audioreach-topology PR 76) has no SP/VI modules. See `evidence/2026-10-30-audio-plan.md` sections 4 and 5.
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| protection graph (SP/VI) not wired in topology | New topology with SP/VI plus calibration (R1 to R3); upstream one has none |
| per-unit calibration (ACDB REV_0D) to Linux format | TBD |
| VI capture path | TBD |
| amplifier reset GPIO and port map are reference-design values | TBD |
| UCM profile | Local copy of alsa-ucm-conf master; capped and muted speaker variant on hold (`userspace/`) |
| SPF query times out at `q6apm` probe (no card possible) | dsp-subsystems with audio input; H1 to H4 in the evidence file |
| PA gain reset to the maximum on SoundWire re-attach | patch 0001 |
| WSA MIX digital volumes uncapped | patch 0002 |
| speaker path must be removable per boot entry | patch 0003 and `patches/dtb-variants/` |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which AudioReach modules and parameters does Windows use for SP and VI (module IDs, calibration blobs)? | TBD | REA of `qcadcm8380.sys`, `qcaudminiport8380.sys`; parse ACDB files of `surface_acsp8380` REV_0D |
| Q2 | Speaker parameters: resistance, thermal constants, excursion limits | TBD | ACDB calibration for REV_0D (this unit is `REV_0d`) |
| Q3 | Amplifier reset GPIO, SoundWire port mapping, gain limits | TBD | Compare DT values with Windows configuration; REA |
| Q4 | Is there an upstream topology with speaker protection for any X1E laptop? | Verified for Surface Pro 11: no (PR 76 topology has no SP/VI module); other X1E boards not checked | rest of the audioreach-topology tree |
| Q5 | Why does `APM_CMD_GET_SPF_STATE` time out with the Windows ADSP image? | Hypothesis H1 to H4 | late reload of `snd_q6apm`; REA R6 and R7 |
| Q6 | Are the machine-driver ceilings (PA 0 dB, digital -3 dB) safe for this unit's speakers? | TBD | Windows limits, REA R1 to R5 |

## 7. Acceptance

1. Speaker protection module active with VI feedback, verified by logs before any loud test (risk S1)
2. Stereo playback at normal volume without distortion
3. Protection reduces gain under sustained load

## 8. Requests

- kernel: build and check patches `0001` to `0003` (in `patches/`; branch `w/audio-speakers`); copy `patches/dtb-variants/x1p64100-microsoft-denali-m11-audio.dts` into `kernel/dtb-variants/` and build it; do NOT build `...-m11-audio-spk.dts` into any image. Extend `scripts/kernel-dtb-safety.py`: an enabled `x1e80100-sndcard` is acceptable when it has no `wsa-dai-link` and `swr0` is effectively disabled.
- image: boot entry `SP11 audio, microphones` (DTB `m11-audio`, args as M10 plus `sp11.entry=audio`); install `userspace/overlay/` and the topology (`userspace/build-topology.sh`); collector step for H1 (reload `snd_q6apm` late, dmesg, read-only). L0 check 2.18 must keep failing for speaker-enabled device entries.
- firmware: install path for `qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin` (SHA-256 `b192044f...da8c03`, built from upstream source, not a Windows file).
- dsp-subsystems: take the SPF timeout (Q5) with the audio owners; H1 evidence needs no speaker path.
- orchestrator: S1 stays; decide whether the operator wants Path E (exception) or waits for Path P (`evidence/2026-10-30-audio-plan.md` section 8). Run REA R6 and R7 first, then R1 to R5, when REA is free. Cross-check (`agents/protocol.md` §5.1) any value that enters a patch or safety decision: the ceilings 81 and 6 and the WSA port map.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-30: audio plan (`evidence/2026-10-30-audio-plan.md`): M8/M10 state, DT, safety layers, topology/UCM, patches 0001 to 0003, REA questions; status `designed`.

## Requests (2026-10-30, orchestrator)

- **S1 evidence, Path P:** the Argon REA report (`evidence/2026-10-30-argon-rea-report.md`, spot-checked) shows Windows protects the two 4 ohm speakers with a closed-loop SPv5 speaker-protection module in the ADSP (V/I and CPS feedback, thermal model, 110 C hard limit, 180 s cooldown) plus ACDB calibration, not with a static volume cap. Linux 7.3 has none of that (no V/I sense ports, no IMCL links, no SPv5 calibration). Speakers therefore stay OFF in every DTB and image. Microphones are safe and may proceed (`m11-audio`).
