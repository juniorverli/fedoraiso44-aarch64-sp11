# audio-speakers

## 1. Summary

Two WSA8845 smart amplifiers on SoundWire, driven by the ADSP through AudioReach. Safe use requires speaker protection: a thermal and excursion model fed by voltage/current (VI) sense from the amplifiers. Linux 7.3 has the codec, the machine driver and the AudioReach module IDs for protection, but no wired-up graph or calibration for this machine. Status: `survey`.

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
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| protection graph (SP/VI) not wired in topology | TBD |
| per-unit calibration (ACDB REV_0D) to Linux format | TBD |
| VI capture path | TBD |
| amplifier reset GPIO and port map are reference-design values | TBD |
| UCM profile | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which AudioReach modules and parameters does Windows use for SP and VI (module IDs, calibration blobs)? | TBD | REA of `qcadcm8380.sys`, `qcaudminiport8380.sys`; parse ACDB files of `surface_acsp8380` REV_0D |
| Q2 | Speaker parameters: resistance, thermal constants, excursion limits | TBD | ACDB calibration for REV_0D (this unit is `REV_0d`) |
| Q3 | Amplifier reset GPIO, SoundWire port mapping, gain limits | TBD | Compare DT values with Windows configuration; REA |
| Q4 | Is there an upstream topology with speaker protection for any X1E laptop? | TBD | linux-firmware / audioreach-topology / alsa-ucm-conf history |

## 7. Acceptance

1. Speaker protection module active with VI feedback, verified by logs before any loud test (risk S1)
2. Stereo playback at normal volume without distortion
3. Protection reduces gain under sustained load

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
