# video-codec worker

**Owns:** `hardware/video-codec/` (write). Everything else is read-only.
**Phase:** 4. **Kernel worktree:** yes, for the DT enable patch.

## Start

1. Read `hardware/video-codec/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Hardware video decode (and encode where Iris supports it) through V4L2 on 7.3.

## Specific leads

- `sources/linux/drivers/media/platform/qcom/iris/`: platform data that `qcom,sm8550-iris` selects, the firmware name requested, resources versus the `hamoa.dtsi` node.
- `qcvss8380.mbn` header (PAS ID) versus the linux-firmware VPU file.

## Deliver

DT enable patch, firmware request, `test-plan.md` (`v4l2-ctl --list-devices`, GStreamer `v4l2h264dec`), dossier updated.
