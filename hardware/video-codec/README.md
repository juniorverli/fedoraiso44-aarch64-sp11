# video-codec

## 1. Summary

The Iris hardware video decoder/encoder, plus a separate AV1 encoder. Linux 7.3 has the Iris driver and a disabled DT node for this SoC. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `part of ACPI\VEN_QCOM&DEV_0C36 (GPU/display device)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcdx8380 (qcvss8380.mbn, qcav1e8380.mbn, video MFTs)` | TBD |

## 4. Linux 7.3

- Driver: `media/platform/qcom/iris (matches qcom,sm8550-iris)`
- DT: `hamoa.dtsi iris: video-codec@aa00000, qcom,x1e80100-iris + qcom,sm8550-iris, status disabled`
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| node disabled in Denali | TBD |
| firmware name and signing (Windows qcvss8380.mbn vs linux-firmware vpu file) | TBD |
| AV1 encoder has no Linux driver | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which firmware file does Iris request for x1e80100 and is it in linux-firmware? | TBD | `drivers/media/platform/qcom/iris/` platform data |
| Q2 | Is the Windows `qcvss8380.mbn` signed for the same PAS ID? | TBD | Header comparison |
| Q3 | Does GStreamer/FFmpeg in Fedora 44 use V4L2 stateful decoders on Iris? | TBD | Package check |

## 7. Acceptance

1. H.264 and HEVC decode via V4L2 in GStreamer with low CPU use

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
