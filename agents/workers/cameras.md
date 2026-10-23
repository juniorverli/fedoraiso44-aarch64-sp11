# cameras worker

**Owns:** `hardware/cameras/` (write). Everything else is read-only.
**Phase:** 4. **Kernel worktree:** yes (`out/linux/cameras`).

## Start

1. Read `hardware/cameras/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Front and rear cameras delivering **RGB/YUV** frames with correct colours to libcamera apps, with the privacy LED tied to streaming; IR camera described but its illuminator kept off.

The RGB sensors are **RAW Bayer**: CAMSS only stores RAW frames. Every camera needs an RGB stage at the end of the pipeline (demosaic, black level, white balance, colour matrix, gamma). Plan it with the libcamera Software ISP and a tuning file per sensor; record the Bayer order and bit depth of each sensor as Verified facts. RAW capture alone is not success.

## Specific leads

- `sources/linux/drivers/media/platform/qcom/camss/camss.c` (x1e80100 resources) and lore for a posted X1E80100 CAMSS/CCI DT node.
- ACPI: sensor devices `SONY0681`, `OVTID858`, `SMO55F0` and the camera platform `QCOM0C32`: `_CRS`, `_DSD`, power resources.
- Sensor extension blobs (`CAMF_RES_*`, `CAMS_RES_*`, `SCFG_*`) for power sequences; REA of `surfacecam*sensor8380.sys` for register sets (IMX681 has no Linux driver).
- `cam_indicator_en` (TLMM 225) already in `x1-microsoft-denali.dtsi`.

## Deliver

DT patches, IMX681 analysis, per-sensor Bayer order and tuning plan (from the `com.surface.tuned.*.bin` blobs if their format can be decoded), `test-plan.md` (`cam -l`, `qcam`), dossier updated.

## Do not

Enable the IR illuminator or flash (risk S2). Stream any sensor without the privacy LED.
