# audio-speakers worker

**Owns:** `hardware/audio-speakers/` (write). Everything else is read-only.
**Phase:** 3. **Kernel worktree:** yes (`out/linux/audio-speakers`).

## Start

1. Read `hardware/audio-speakers/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Stereo speaker playback that is protected: AudioReach graph with speaker protection and VI feedback, calibrated for this unit (`REV_0d`), before any audible test.

## Specific leads

- `sources/linux/sound/soc/qcom/qdsp6/audioreach.{c,h}` (`MODULE_ID_SPEAKER_PROTECTION`, `_VI`), `sound/soc/codecs/wsa884x.c` (VI sense ports), `sound/soc/qcom/x1e80100.c`.
- ACDB and workspace files under `surface_acsp8380.inf_arm64_*/REV_0D/`: format, which blocks are SP/VI parameters.
- REA: `qcadcm8380.sys` (calibration manager), `qcaudminiport8380.sys` (graph setup), for module IDs, parameter IDs and the order they are sent.
- Upstream: AudioReach topology repository and alsa-ucm-conf for any X1E machine that already ships protection.

## Deliver

A protection design in `evidence/`, topology/UCM proposals, `test-plan.md` that verifies protection is active **before** raising volume.

## Do not

Enable speaker output in any ISO without protection evidence (risk S1). A volume cap is not protection.
