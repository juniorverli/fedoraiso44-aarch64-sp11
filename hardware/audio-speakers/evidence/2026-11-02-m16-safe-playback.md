# M16 revision-15 safe: playback investigation, 2026-11-02

Status: **designed; functional fix not established**. Do not bypass event registration, ignore its error, weaken the guard, or infer working protection from calibration. No playback, thermal/power experiment, kernel build, ISO, or device changes were done. S1/D26 still requires a speaker-off fallback; request to restore it remains open.

## Device evidence

**Verified:** safe boot `9e275ce6-2064-46f7-a153-b569a6f1b1a4`, kernel `7.3.0-65.sp11.15` per operator. Source `out/device-logs/m16-20261102/9e275ce6-2064-46f7-a153-b569a6f1b1a4/dmesg.txt.gz`, SHA-256 `18b956e876012f35cf086d79a09eb2353300ffa5cd279883b82e1b394181ccd9`. Exact first occurrence, followed by eleven repeats:

```text
2026-11-02T09:53:18,769270+00:00  MultiMedia4 Playback: ASoC: no backend DAIs enabled for MultiMedia4 Playback, possibly missing ALSA mixer-based routing or UCM profile
2026-11-02T09:53:19,026685+00:00 q6apm-lpass-dais 6800000.remoteproc:glink-edge:gpr:service@1:bedais: Error (3) Processing 0x0100100e cmd
2026-11-02T09:53:19,026711+00:00 q6apm-lpass-dais 6800000.remoteproc:glink-edge:gpr:service@1:bedais: DSP returned error[100100e] 3
2026-11-02T09:53:19,026724+00:00 q6apm-lpass-dais 6800000.remoteproc:glink-edge:gpr:service@1:bedais: Failed to set media format -22
2026-11-02T09:53:19,027354+00:00 q6apm-lpass-dais 6800000.remoteproc:glink-edge:gpr:service@1:bedais: ASoC error (-22): at snd_soc_dai_prepare() on WSA_CODEC_DMA_RX_0
2026-11-02T09:53:19,344636+00:00 q6apm-lpass-dais 6800000.remoteproc:glink-edge:gpr:service@1:bedais: speaker calibration applied (nominal)
```

Card and PCMs 0, 2, 3 exist (`sound.txt.gz`); the truncated control names are the stream volume controls, not the DAPM route control names. Nominal calibration later is not evidence that playback graph started or that feedback works.

## RX failure

**Verified:** `sources/linux/sound/soc/qcom/qdsp6/audioreach.h:67` defines `0x0100100e` as `APM_CMD_REGISTER_MODULE_EVENTS`; `APM_CMD_SET_CFG` is `0x01001006` (`:63`). The M16 closed-loop patch 0014 calls `audioreach_sp11_register_events()` after SP parameter configuration, operation mode and enable; its registration targets the SP module instance with event `0x0800138c`, no event payload, then returns failure to `audioreach_set_media_format()`. That error propagates through `q6apm_graph_media_format_pcm()` (`sources/linux/sound/soc/qcom/qdsp6/q6apm.c:443`) to the generic `Failed to set media format` message (`q6apm-lpass-dais.c:257`). Inference: the observed DSP error is a rejected SP diagnostics subscription, not evidence of a rejected PCM format. Exact DSP reason, target validity, required payload, and graph state at registration are **TBD**. The prior report cites event occurrence in ACDB but does not independently establish registration ABI; see `2026-10-30-argon-rea-report.md` and `2026-10-30-closed-loop.md` H7. Do not treat error code 3 as identifying which field is wrong.

**Verified source / Inference for runtime:** topology source `userspace/build-topology/m4/X1E80100-Microsoft-Surface-Pro-11-closedloop.m4:22-83` declares MultiMedia1 S16_LE, 48 kHz, stereo and WSA RX graph 105 with the same format, WSA interface RX0; SP is in graph 105, VI in graph 106. Public topology `out/ref/srini-art/X1E80100-Microsoft-Surface-Pro-11.m4` SHA-256 `41b658e92860b52646f05fdc3f9b2ae4737b790c90515c40ce8595b9e05b3728` agrees on RX format and routing but has no SP. Patch 0015 forces 48 kHz on RX, leaves channels and format from FE, and forces TX_0 to 8 kHz, S32_LE, two logical speakers; the VI code expands their mapping. `q6dma_hw_params` uses the channel interval **maximum**, `params_width()` and `params_rate()` (`q6apm-lpass-dais.c:169-180`), and `audioreach_codec_dma_set_media_format()` sends those values (`audioreach.c:705-765`). Exact negotiated RX values were not logged; if the FE constraints are honored they should be 2/48000/16. A channel/rate/format fix is not supported by this error, and the TX change does not establish an RX defect. Furthermore the failure at the SP module can precede the codec DMA configuration; the log does not prove that the DSP ever received the RX endpoint format. Request read-only parameter and module/command tracing if a safe diagnostic becomes available.

Patch 0019 only identifies failed SP diagnostics registration; it retains the error and guard behavior. It is not a functional fix. `checkpatch --strict`: 1 error for missing Signed-off-by, 0 warnings or checks; with `--no-signoff`, 0 errors, warnings or checks. No sign-off was fabricated. Apply checked against the relevant source after patches 0014 and 0018. No build or device test.

## UCM and DP

**Verified:** speaker base verb sets `WSA_CODEC_DMA_RX_0 Audio Mixer MultiMedia1` to 1 and uses PCM 0; microphone route is `MultiMedia2 Mixer VA_CODEC_DMA_TX_0`. Audio-mics' `SP11-HiFi.conf` wraps the speaker verb and `SP11-Routes.conf`; `SP11-DP0.conf` enables `DISPLAY_PORT_RX_0 Audio Mixer MultiMedia3` on HDMI0/PCM 2, and `SP11-DP1.conf` enables `DISPLAY_PORT_RX_1 Audio Mixer MultiMedia4` on HDMI1/PCM 3, disabling them when the respective device is disabled. The topology connects these exact pairs. Route controls are separate from the truncated volume controls.

**Verified:** safe `extra-audio-routes.txt.gz`, SHA-256 `1b6dcfff46eeb8f748420c19843c0800eb8162dd9cc46aad6010bde3962548e7`, lists HiFi, Speaker, Mic, HDMI0 and HDMI1 with correct DP PCMs and jack names; it does not prove device enable or active routing. Its `amixer` reads all fail on `sysdefault:0`; it cannot establish mixer state. Both DRM connectors were disconnected at that snapshot. **TBD:** which process opened MultiMedia4, whether UCM had enabled HDMI1 then, and why the warning occurred. A raw PCM probe or a disconnected/disabled device could produce it; neither is established. Existing route layer is present, so an unconditional DP route or duplicated definitions would not be a demonstrated fix. Speaker overlay comment corrected to document the actual composition; no routing or mute values changed.

## Device retest requirements

On a future planned boot, first verify the selected DTB and fallback satisfy D26/S1, all existing guard/mutes remain active, no automatic audible playback, and collect the actual loaded topology hash. Without opening or starting a speaker PCM, collect boot dmesg, `/sys/kernel/debug/sp11/guard`, `/proc/asound/cards`, `alsaucm` verb/device lists, and `amixer -c 0 controls` plus `amixer -c 0 cget` for the three exact route names and jack controls (including interface CARD for jacks); record failures. Capture UCM active verb/devices, PipeWire/WirePlumber nodes and their PCM opener and relevant journal timestamps. Distinguish a PCM probe with a disabled device from an enabled HDMI1 route failure; use existing audio-mics tests for DP and no speaker output. No command here authorizes playback or unmuting.

Only after the registration ABI and a safe diagnostic procedure are independently established should a controlled, muted graph test demonstrate that registration succeeds, the RX graph prepares with recorded 2 channels/48000/S16_LE and no errors, and that the guard still refuses unmute until all required protection conditions are evidenced. Success cannot be inferred from the absence of an error when the graph was never opened. Closed-loop protection and actual sound remain unverified.
