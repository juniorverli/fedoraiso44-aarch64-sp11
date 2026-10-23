# audio-mics

## 1. Summary

The built-in microphone array, digital microphones on the LPASS VA macro, captured through the ADSP. Linux 7.3 describes `VA DMIC0` and `DMIC1`; whether that matches this unit is unconfirmed. Status: `survey`.

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
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| number of microphones and their DMIC lines unconfirmed | TBD |
| topology and UCM | TBD |
| beamforming/noise suppression only in userspace | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | How many microphones, which DMIC lines, which clock rate? | TBD | ACDB/topology data; Windows endpoint format in `live-inventory/audio` |
| Q2 | What topology graph does capture need? | TBD | AudioReach topology for the VA path |
| Q3 | Echo cancellation and noise suppression: DSP or userspace? | TBD | Windows APO list vs PipeWire WebRTC module |

## 7. Acceptance

1. Recording in GNOME Settings shows level on every microphone
2. Recorded speech is intelligible, channel order correct

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
