# audio-mics worker

**Owns:** `hardware/audio-mics/` (write). Everything else is read-only.
**Phase:** 3. **Kernel worktree:** only if a DT change is needed.

## Start

1. Read `hardware/audio-mics/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Built-in microphones recording through the VA macro with correct channel count and order.

## Specific leads

- `x1-microsoft-denali.dtsi` `&lpass_vamacro` and the `VA Capture` link; `sound/soc/codecs/lpass-va-macro.c`.
- Microphone count and DMIC lines from the ACDB of `surface_acsp8380` and the Windows endpoint format in `live-inventory/audio/`.
- Share topology work with `audio-speakers` through requests, not edits.

## Deliver

`test-plan.md` (arecord per channel, PipeWire source), dossier updated.

## Do not

Change anything on the playback path.
