# audio-mics

## 1. Summary

The built-in microphone array, digital microphones on the LPASS VA macro, captured through the ADSP. Linux 7.3 describes `VA DMIC0` and `DMIC1`; whether that matches this unit is unconfirmed. Status: `designed` (2026-10-30): stage A DT variant, topology and UCM prepared by the audio-speakers worker (patch 0003, `hardware/audio-speakers/userspace/`); not built or run. Capture needs the ADSP audio framework to answer first (SPF timeout, `hardware/audio-speakers/evidence/2026-10-30-audio-plan.md` section 2).

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `MMDEVAPI Microphone Array (Qualcomm Aqstic ACX Static Endpoint)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `QCASD\StaticEndpointDevice0` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcasd8380` | TBD |
| `qcasd_apo8380` | TBD |
| `surface_asdext8380` | TBD |
| `surface_acsp8380` | TBD |
| `voiceclarityep_audio_component` | TBD |
| `mep_audio_component` | TBD |

## 4. Linux 7.3

- Driver: `codecs/lpass-va-macro`
- Driver: `sound/soc/qcom/x1e80100.c (VA Capture)`
- DT: `x1-microsoft-denali.dtsi &lpass_vamacro (DMIC0/1, 2.4 MHz, vdd-micb l1b)`
- DT already complete in 7.3: `x1-microsoft-denali.dtsi:334-348` (`va-dai-link`), `:865-871` (`dmic01_default`, 2.4 MHz, `vdd-micb`). The M10 device DT dump shows `qcom,dmic-sample-rate = <0x249f00>` (2400000) and `status = "disabled"` on `/sound`.
- Machine driver: nothing special for VA capture (`x1e80100.c` default branch).
- Upstream topology: `VA_CODEC_DMA_TX_0`, capture `MultiMedia2`, 1 to 2 channels, 48 kHz S16_LE (audioreach-topology PR 76, commit `aab5c37c`).
- Upstream UCM `Surface11-HiFi.conf` `Mic` device: `hw:${CardId},1`, DMIC0 and DMIC1 enable sequences.
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| number of microphones and their DMIC lines unconfirmed | Two DMICs on `dmic01` in the DT and the reference; confirm with REA R8 |
| topology and UCM | Topology built from upstream source (`hardware/audio-speakers/userspace/build-topology.sh`); microphone-only UCM profile in `.../userspace/overlay/`; install by image/firmware |
| ADSP audio framework does not answer (`GET_SPF_STATE` timeout), so no card | dsp-subsystems with audio owners (H1 to H4 in the speakers evidence) |
| sound card disabled in every current DTB | DT variant `m11-audio` (microphones only, S1 intact) |
| beamforming/noise suppression only in userspace | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | How many microphones, which DMIC lines, which clock rate? | TBD | ACDB/topology data; Windows endpoint format in `live-inventory/audio` |
| Q2 | What topology graph does capture need? | Verified (upstream): stream sub-graph MultiMedia2 to VA codec DMA TX 0, no processing modules | `X1E80100-Microsoft-Surface-Pro-11.m4` |
| Q3 | Echo cancellation and noise suppression: DSP or userspace? | TBD | Windows APO list vs PipeWire WebRTC module |

## 7. Acceptance

1. Recording in GNOME Settings shows level on every microphone
2. Recorded speech is intelligible, channel order correct

## 8. Requests

- kernel / image / firmware: as listed in `hardware/audio-speakers/README.md` section 8: DTB variant `m11-audio`, boot entry `SP11 audio, microphones`, topology install, microphone UCM overlay, late `snd_q6apm` reload in the collector.
- audio-speakers: ask REA R8 (microphone count, DMIC lines, divider, channel order, voice-clarity APO) when REA is free.
- orchestrator: this component is not subject to S1 if the card has no WSA link and `swr0` stays off (check `kernel-dtb-safety.py` change requested in the speakers dossier).

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-30: stage A plan and test plan; status `designed`. Facts in `evidence/2026-10-30-mics-plan.md`.
