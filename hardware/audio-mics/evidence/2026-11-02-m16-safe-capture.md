# M16 safe capture, 2026-11-02

## Verdict and grades

**TBD:** the operator reports that the microphone does not work. The supplied snapshot contains no capture attempt, audio samples, contemporaneous PipeWire source/mute state, or capture-specific failure. It cannot establish why capture is silent or demonstrate a fix. A missing Mic UCM definition or unselected DMIC routing is not supported by the snapshot. A UCM/kernel patch changing that route would be speculative.

**Verified:** safe applies the D26 speaker overlay, although a safe fallback must keep speakers off under S1. The source `image/overlay/usr/lib/systemd/system/sp11-speaker-ucm.service:3-5` selects safe, debug and spk, and `image/overlay/usr/libexec/sp11/speaker-ucm-enable:7-14` copies the files. The safe cmdline has `sp11.entry=safe`; dmesg records `sp11-speaker-ucm: speaker UCM overlay installed`. Runtime hashes below exactly match the speaker overlay source, establishing the actual shipped runtime files without relying on a vanished L0 root. Image owner must remove this overlay from safe and verify the safe DT/boot path satisfies S1; this is an isolation correction, not a proven cure for silence. D26's authorized main speaker path is separate.

**Verified:** live UCM lists `Speaker`, `Mic`, `HDMI0`, `HDMI1`; Mic `CapturePCM` is `hw:X1E80100Microso,1`. The speaker `Surface11-HiFi.conf` contains Mic, DMIC0/1 sequences and capture PCM; it also includes WSA controls in `SectionVerb`. The mic-only file contains the same capture selection without speaker initialization. `SP11-Audio.conf` replaces HiFi with `SP11-HiFi.conf`, which includes the active `Surface11-HiFi.conf` then `SP11-Routes.conf`. The offline ALSA execution substitutes control writes with logged commands; setting HiFi and Mic with the speaker profile logs WSA initialization, while mic-only has no WSA writes. This is not proof any specific WSA cset failed on the live system.

**Verified:** `extra-audio.txt.gz` records `MultiMedia2 Mixer VA_CODEC_DMA_TX_0` = `on,off` (the two values are reported as-is), both `VA DEC0/1 MUX` = VA_DMIC, DMIC MUX0 = DMIC0, MUX1 = DMIC1, AIF1 DEC0/1 = on and both DEC gains = 98. `arecord -l` shows card 0 PCM 1 MultiMedia2 Capture and PCM 4 MultiMedia5 Capture. `extra-audio-routes.txt.gz` uses `amixer` without a working explicit card and reports `Cannot find the given element from control sysdefault:0`; use the successful full card dump instead. Both snapshots precede a collected logged-in user graph, so do not demonstrate stream operation.

**Verified Linux topology:** `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:334` links VA to `VA_CODEC_DMA_TX_0` at line 342, and line 866 selects `dmic01_default`. `sources/linux/sound/soc/codecs/lpass-va-macro.c:1227` and `:1231-1257` trace AIF1 through DEC0/1 and their DMIC muxes to DMIC0/1. The M16 closed-loop topology source `hardware/audio-speakers/userspace/build-topology/m4/X1E80100-Microsoft-Surface-Pro-11-closedloop.m4:72,86,89` connects MultiMedia2 to that backend. These facts describe the intended graph, not actual acoustic capture or channel order.

**Verified:** dmesg reports MultiMedia4 *Playback* has no backend, followed by repeated WSA_CODEC_DMA_RX_0 media-format errors (-22); these do not identify a MultiMedia2 capture failure. `extra-audio.txt.gz` reports both DP mixers off in the snapshot. No causal connection to the reported silent microphone is established.

## Evidence identifiers

All logs are under `out/device-logs/m16-20261102/9e275ce6-2064-46f7-a153-b569a6f1b1a4/`; SHA-256 of compressed files:

- `cmdline.txt.gz`: `9ad89bbfd3f0954c58b0b7192c30aaf0ae0bd30a0332e6559d41df964044d3e5`.
- `dmesg.txt.gz`: `18b956e876012f35cf086d79a09eb2353300ffa5cd279883b82e1b394181ccd9`.
- `extra-audio.txt.gz`: `14f8480983b56aab3347760da4e68e9fa1d57cc28f8d2676688dafcbac529c17`.
- `extra-audio-routes.txt.gz`: `1b6dcfff46eeb8f748420c19843c0800eb8162dd9cc46aad6010bde3962548e7`.

Live `MICROSOFT-Surface-Pro-11.conf` SHA-256 `20672b687d2b43853d0b9b88baac3d2ce6c8cac44c840cea09065e4f859ea80f`; live `Surface11-HiFi.conf` `08fba12baf11be8e67e283df51c96b6f364946638a4175a0402858e5075fe3cb`. Both match `hardware/audio-speakers/userspace/overlay-speakers/usr/share/alsa/ucm2/Qualcomm/x1e80100/`. Mic-only base hashes respectively `3713e1b6fee436f46ce8517845ca59a169f73a1494daa59969ccd6dcbfb14243` and `4ab8b5cd67acfbd89b1f521d44a167f76c63f1963e0945622c797aef63eca16f` in `hardware/audio-speakers/userspace/overlay/`. These are runtime hash observations and source matches, not direct ISO filesystem extraction.

## Offline validation and next test

`mic-gain-check.sh` against the safe `extra-audio.txt.gz` passes: 98 = +14 dB and 108 = +24 dB for both controls. Fedora 44 container `ucm-routes-test.sh` passes for microphone-only and speaker source profiles with virtual card substitutions; it cannot validate real ALSA control availability, DSP, hardware, or audio. `image/tools/ucm-lookup-test.sh` also passes against a staged Fedora 44 UCM tree plus the mic-only and route overlay sources, with its documented virtual-card and DP-condition substitutions; it was not run on extracted ISO contents. An initial lookup attempt lacked Python in the base container, then passed after installing it. A test without network initially failed because the base container had no ALSA UCM packages; dependency failure is now explicit in the script. No device capture or kernel/ISO build was performed. No kernel patch was justified; checkpatch is not applicable.

For the next scheduled device test, use the isolated safe profile with S1 verified. Follow `hardware/audio-mics/test-plan.md` M16 section: save runtime profile hashes and device list, inspect actual card 0 controls and logged-in PipeWire selection, record a short stereo 48 kHz sample with PCM 1 and verify both channels and speech, then separately test PipeWire. Capture exit status and relevant kernel/user errors during the attempt. If direct PCM works, focus on source/policy/mute; if it fails, collect DSP and DAPM state while active. No playback or amplifier activation is required.
