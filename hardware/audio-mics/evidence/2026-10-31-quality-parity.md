# Windows audio quality parity: speaker and microphone processing

Author: audio-mics worker (Claude Sonnet 5.5), 2026-10-31. Nothing built, nothing run on the device, nothing committed. S1 stays: this work does not enable the speakers. S5: no calibration or tuning value is printed or committed here; all values live in private `out/firmware-private/audio/`.

Grades: Verified (read from data or decompiled code, with path, hash, offset), Inference (derived, reasoning given), Unknown.

## 1. Where the Windows quality actually comes from

The operator asked for the original Windows quality, not a generic Linux profile. The data shows that quality is spread over four places, and only one of them is in the ACDB.

| Layer | What it holds | Replayable on Linux |
|:--|:--|:--|
| ADSP graph and calibration (`acdb_cal_0D.acdb`) | SAL peak limiter, SPv5 speaker protection, ECNS and Fluence voice modules, tuning blobs of unnamed static modules | Partly (section 4) |
| Dolby DAX3 tuning (`dax3_ext_qc.../AUCD_DEV_0C29_SUBSYS_MSHW0486_REV_0D_ADCM_SUBSYS_MSHW0486.xml`) | The speaker "sound": per-channel 20-band speaker EQ, multiband compressor, regulator, bass handling, volume leveler, profiles | The EQ yes, the engine no (section 5) |
| Proxy APOs (`ProxyAPO.dll`, `AcxProxyAPO.dll`) | Nothing: glue (section 6) | Not needed |
| Microsoft Voice Clarity (`voiceclaritycpuapo.dll`) | DNN echo cancel and noise suppression on the CPU | No (proprietary models) |

### 1.1 Surface APO (`SurfaceAPO_0D.json`): effectively off

Verified (`surfaceapoextension.inf_arm64_5e2a398e403eefd7/SurfaceAPO_0D.json`): a host mode effect with one 16-biquad EQ per processing mode (default, raw, notification, comms, movie, media), 80 coefficients each. Every `Enabled` flag is false. In ten of twelve blocks all 16 sections are identity (unity b0, zeros). Two blocks (notification) have two non-identity sections each. Inference: it is not quality-defining; it is a dormant hook.

## 2. Endpoint configuration (miniport and ASD INF)

Verified, `surface_audiominiext8380.inf` (sha256 `5acd5091...8134`, catalog row) and `surface_asdext8380.inf` (sha256 `30403fe6...5a6f`):

- Speaker endpoint `WaveSpeaker`: stereo, 48 kHz, 16 bit; default device volume REV_0D is -12.0 dBFS; endpoint volume range -75 to 0 dBFS in 0.5 dB steps; modes RAW, DEFAULT, MEDIA, MOVIE, COMMUNICATIONS, NOTIFICATION. Mode effects advertised: EQ (`6f64adc3`), bass boost (`6f64adc5`), DRC (`6f64adce`) (the INF comments say so). Host effect chain: Dolby wrapper SFX/MFX plus the Surface render MFX plus the proxy endpoint effect.
- The built-in microphone is NOT the miniport's `TopologyMicIn` (`InstallEndpoint` = 0 there). It is `MicArray1` from the ASD extension (`InstallEndpoint` = 1): stereo 48 kHz 16 bit in every mode (DEFAULT, RAW, COMMUNICATIONS, SPEECH), plus a buffered 16 kHz stereo listen pin. The only effect it advertises, in every mode, is EQ (`6f64adc3`); the noise suppression, echo cancellation, AGC and DRC lines are commented out in the INF.
- Mic gain: default device volume +14 dB, maximum +24 dB, sensitivity -20 dB, SNR 66 dB.
- Array geometry (REV_0D): two microphones, linear array, subcardioid capsules, y coordinates +20 mm and -20 mm (spacing 40 mm, x = z = 0), declared band 75 Hz to 20 kHz. Microphone 0 faces forward (0 degrees); microphone 1 carries a horizontal angle of -180 degrees (about -31416 in the INF's 1e-4 radian unit). The INF comments say channel 0 sits on the device's right side.
- Effect GUID meanings (Inference, from the Windows SDK constant list recalled by the worker and confirmed by the INF's own comments for `adc3` EQ, `adc5` bass boost, `adce` DRC, `adc2` constant tone removal, `adbf` noise suppression, `adbe` AEC, `adc0` AGC): the GUID base is `6f64adXX-8211-11e2-8c70-2c27d7f001fa`.

## 3. APO question: glue or DSP? (REA)

Verified with REA (Ghidra provider, ARM64 PE, `ProxyAPO.dll` sha256 `b8b7cb0d3a7d671b7f84722c0ee533f7a4fee73b9636c06c4eaa2f36334591fc`, matches `sources/binary-catalog.tsv`; function `0x1800230c0` decompiled, evidence `ev_1597e7ea24cb2197ffb91924c4ffb1ba933f91f169810b6acf6bd6a357656277`): `CProxyAPOMFX::APOProcess` copies the input buffer to the output when they differ (a `memmove` sized by frames x channels x bytes) and copies the buffer flags; there is no filter, gain or table code. Strings: `GetEffectsList`, `IAudioSystemEffects`, `EffectsGuid` registry change event, nothing else. `AcxProxyAPO.dll` (sha256 `42e1c2a7...2660`) has the same class layout and no DSP strings (Inference: same role, not decompiled). Conclusion: both are glue that exposes the ADSP effect list to the Windows audio engine. Those effects run in the ADSP (the INF's GUIDs name modules of the ACDB graphs), not on the CPU.

REA note: the session loaded the language from the PE header (`auto-from-header`, ARM64) and not forced as protocol 9.2 asks, because the MCP server environment is not mine to set. The PE header is unambiguous and matches the catalog's `AARCH64:LE:64:v8A`.

The real host-side processing is elsewhere:

- Dolby DAX3. `dax3_ext_qc.inf` carries only the tuning data, not the engine (the engine is a store package, absent here). Verified from the REV_0D XML: nine profiles (dynamic, movie, music, game, voice, voice_onlinecourse, personalize_user1..3, off); each has a `tuning-cp` block (surround, IEQ, dialog enhancer, volume leveler, virtualizer, regulator, graphic EQ, bass enhancer, virtual bass) and a `tuning-vlldp` block (8-channel 20-band audio optimizer, filter coefficients, 4-group multiband compressor, regulator, sliding bass, speaker PEQ, noise gate, peak level). Channels 0 and 1 of the audio optimizer hold literal 20-value arrays (left and right speaker curve); the other channels reference zero presets. The band centre table for 48 kHz is in the same file (20 bands, 47 Hz to 19.7 kHz). In profile `music`, the enabled stages are: regulator, volume leveler, volume leveler DRC (cp); audio optimizer, multiband slow gain, regulator speaker distortion (vlldp). Speaker PEQ is enabled in `dynamic` and `voice` but its filter list has no entries.
- Microsoft Voice Clarity (`voiceclaritycpuapo.dll`, sha256 catalogued under the voiceclarity INF). Strings only: acoustic echo cancellation interfaces and a DNN inference engine with embedded models (`asgvad_model_1_6.fpie`, `aligncruse_model_4_1.fpie`). Inference: it is the communications noise suppressor and echo canceller that Windows 11 applies on top of `MicArray1`. Not replayable.

## 4. ACDB use cases and module chains

Tool: `userspace/quality/acdb_usecases.py` (decodes the ACDB as data, reuses the audio-speakers container decoder read only). Verified: 86 graph key vectors, 261 subgraph instances, 49 distinct module ids. Output (private): `out/audio-mics/acdb-usecases.json` (ids, instance ids, parameter ids, sizes; no values).

Graph key vectors are full graphs (stream plus device). Inference: in the 6-key vectors the last key selects the device or use case (1 speaker RX, 3 other RX, 2/4/5/16 microphone TX, 9 uplink processing, 12/13 voice call, 8/10/11/15 RX processing); the key ids are not named in the ACDB, the meaning rests on the module chains.

Module registration in `qcadsp8380.mbn` (sha256 `921870a8...0da13`, Hexagon, `Hexagon:LE:32:default` per catalog). Verified by byte scan: a static module table (16-byte entries: flags, module id, two code pointers) at file offset `0x12c5b80` onward, and a dynamic module table (flags, id, 1, pointer to `.so` name, pointer to capi name) at `0x12c68d0` onward. Every module id of every chain is registered in one of the two, except `0x070010af`, `0x07001082`, `0x07001085`, `0x070010c2` (the last three are Bluetooth codec modules from the ACDB `MODM` chunk; `0x070010af` appears in two voice chains and is unregistered: Unknown).

Verified names from the dynamic table (so file in the Windows ADSP folder, `/statichashes/` lists it): `0x07001031` `capi_smecns_v2` (`smecns_v2_module_fvxiii.so.1`), `0x0700102d` `capi_ffecns`, `0x07001033` `capi_fluence_ef`, `0x070010a3` `capi_fluence_nn`, `0x070010d9` `capi_fluence_nn_ns`, `0x0700103d` `capi_fluence_bs`, `0x07001034/3e` `capi_fluence_pro_vc/vr`, `0x0700103f/40` `capi_sm/mm_fluence_sb`, `0x070010d8` `capi_ans`, `0x07001063` `capi_audiosphere`. Linux names from `audioreach.h` and the public m4 cover the framework modules (WR/RD shared memory, GAIN, PCM, SAL, MFC, DATA_LOGGING, VOL_CTRL `0x0700101b`, codec DMA, SPv5, VI). The static modules `0x07001011/13/14/17/19/20/28/29/2a/2e/32/38/41/43/45/97/98` stay UNNAMED: the image has capi code for `iir_mbdrc`, `multistageiir`, `popless_equalizer`, `pbe`, `drc`, `fir_filter`, `soft_vol`, `peakmeter`, `virtualizer`, `splitter`, `mux_demux`, `spr` and others, but mapping ids to them needs the init functions. Unknown. The REA attempt (Hexagon, full image) did not finish Ghidra analysis within the 330 s deadline twice (22 MB, 2 GB heap); see Requests.

### 4.1 Speaker playback (music and media)

Verified chains (names where known, ids otherwise, DATA_LOGGING omitted):

- Device (guarded, 14 key vectors): `SAL > CODEC_DMA_SOURCE(V) > CODEC_DMA_SOURCE(CPS) > 0x1013 > SPEAKER_PROTECTION > SPEAKER_PROTECTION_VI > 0x1098 > 0x1011 > CPS_DATA_ROUTER > CODEC_DMA_SINK`. SAL has the peak limiter enabled (parameter `0x0800101e`).
- Stream, low latency and low power: `WR_SHARED_MEM_EP | SH_MEM_PULL_MODE > PCM_CNV | PCM_DEC > VOL_CTRL > 0x1097 > [0x1045 > VOL_CTRL] > MFC > 0x1019 > 0x1032`.
- Processing-only RX subgraphs: `VOL_CTRL > 0x1097 > 0x1014 [> 0x1014]` and `0x1038 > SAL > VOL_CTRL > 0x1097 > 0x1014 [> 0x1014]`.

Quality-defining on the ADSP side: SPv5 (protection, with its own large parameters 612 to 2188 bytes: thermal and excursion model, possibly internal filtering: Unknown), the SAL limiter, and the Q? candidates `0x1014` (four parameters, one of 164 bytes) and `0x1045` (a 112-byte parameter). Plumbing: shared memory endpoints, PCM, MFC, `0x1011`, `0x1013`, `0x1019`, `0x1032`, `0x1097`, VOL_CTRL, DATA_LOGGING, CODEC_DMA.

Inference (important): the ADSP speaker chain has little tone shaping of its own. The tonal character of Windows speakers comes from the Dolby tuning (section 3), which runs host-side. Replaying the ACDB alone would not reproduce the Windows sound.

### 4.2 Microphone capture

Verified chains (microphone use cases, perf mode 1 is low latency):

- Plain record: `CODEC_DMA_SOURCE > [0x1013] > 0x1011` (device), `MFC > 0x1019 > PCM_CNV > SH_MEM_PUSH_MODE` (stream).
- Single-mic voice (also the "uplink" group): `MFC > 0x1014 > 0x1028 > GAIN > capi_smecns_v2 > 0x1097 > VOL_CTRL`.
- Dual-mic voice, noise-network: `MFC > 0x1014 > GAIN > 0x1014 > 0x1028 > capi_fluence_ef | (0x1013 > capi_fluence_nn) > 0x1014 > 0x1068 > 0x1017 > 0x1097 > VOL_CTRL`.
- Far-field: `MFC > MFC > 0x1028 > capi_ffecns > 0x1011 > 0x1020 > 0x10af`.

Quality-defining: `capi_smecns_v2` (echo cancel and noise suppression, 13 parameters), `capi_ffecns` (33 parameters), `capi_fluence_ef` (19), `capi_fluence_nn` (34, neural noise suppression), `0x1014` (EQ/DRC/HPF candidate: one parameter of 164 bytes, 61 key rows in some chains), `0x1017` (61 key rows, 128-byte parameter: a per-condition filter), `0x1043`, `0x102e` (23 parameters, one of 55180 bytes: a model or table). GAIN and VOL_CTRL set levels. Beamforming and AEC in the Windows sense live in the fluence and ffecns modules; Inference from their names, not from their parameters. The listing never shows a plain "beamformer" or "AGC" module by name.

Beamforming and AEC are only ever used with the dynamic modules that need their `.so` served to the ADSP (section 7).

## 5. What Linux 7.3 can express

Verified, `sources/linux` v7.3, `sound/soc/qcom/qdsp6/audioreach.c`, `topology.c`, `include/uapi/sound/snd_ar_tokens.h`:

| Windows module | Linux handler in `audioreach_set_media_format()` |
|:--|:--|
| WR/RD/SH_MEM, PCM_CNV/ENC/DEC, placeholders, I2S, GAIN, SAL (limiter enabled), MFC, DATA_LOGGING, CODEC_DMA, GAPLESS, DISPLAY_PORT | named cases (audioreach.c:1472-1535) |
| SMECNS_V2 | named case, sends the module priv data as one `APM_CMD_SET_CFG` (audioreach.c:836-852) |
| SPv5, VI | named cases; the closed-loop series (audio-speakers 0014) adds records and control links |
| VOL_CTRL | none needed, controlled through the volume control (topology token path) |
| everything else (fluence, ffecns, 0x1014, 0x1045 ...) | none: the `default:` case does nothing |

The topology format has one generic blob carrier: the module vendor array of type `SND_SOC_AR_TPLG_MODULE_CFG_TYPE` (`0x01001006`, snd_ar_tokens.h:336), read by `audioreach_get_module_priv_data()` (topology.c:309-333). Today that data is sent only for SMECNS_V2. The data must already be complete `apm_module_param_data` records (instance id, parameter id, size, error code, payload). The size is the vendor array size (u32) and is limited in practice by the GPR packet: the closed-loop loader caps one record at 4 KiB and so does this work. Parameters above 4 KiB need chunking or out-of-band memory, which the kernel does not implement: `capi_smecns_v2`/`0x102e` has one 55180-byte parameter, `PCM_CNV` has ones of 6604 bytes; neither is replayed.

Gap (Request to the kernel owner): change the `default:` of `audioreach_set_media_format()` to send `module->data` (if present) with `audioreach_set_module_config()`, so any module with a topology blob works without a new case; or load the records of `<card>-sp11q.bin` the way 0014 loads `sp11cl`.

The public topology for this model (`out/ref/audioreach-topology/X1E80100-Microsoft-Surface-Pro-11.m4`) is minimal: playback `WR_SH > PCM_DEC > PCM_CNV > VOL_CTRL > MFC > LOG` into a WSA codec DMA back end (no SAL, no SP), capture from the VA DMIC with one logger. `MODULE_ID_SMECNS_V2` is defined in the m4 include but never instantiated. It carries no tuning.

## 6. What was generated (private)

All in `out/firmware-private/audio/`, mode 0600, never git, never public ISO.

- `sp11q-plan.json`: for every one of the 261 subgraphs, the module chain, the use-case label and a replay decision per (module, parameter): replayable, or the reason it is not (guard-owned, ambiguous key rows, over 4 KiB, framework-managed, plumbing candidate, unregistered).
- `qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-sp11q.bin`: 23 sets, 92 records for the microphone use cases on static modules.
- `...-sp11q-dyn.bin`: 7 sets, 117 records for the dynamic modules (smecns, ffecns, fluence): only for a topology variant that uses them, after the `.so` files are served.
- `...-sp11q-spk.bin` (flag GATED): 23 sets, 175 records for speaker stream-side modules; only with `--include-playback`, to be read only after the guard reports the closed-loop graph up.
- `pipewire/sp11-speaker-quality.conf`: 20-band per-channel EQ (40 biquads), preamp that cancels the largest boost, limiter at -3 dBFS; `pipewire/sp11-mic-quality.conf` (75 Hz high-pass per channel, broadside mono sum, software gain default 0); `pipewire/sp11-mic-echo-cancel.conf` (WebRTC template with the geometry commented in, no Windows numbers).

Format `SP11Q001` is defined in `quality/sp11_quality.py`. It is verified by an independent decoder (`--self-test`) and by a check that no record overlaps the existing `sp11cl` file (`--check-against-sp11cl`, passed). It is NOT verified by the kernel parser harness: there is no kernel loader for `SP11Q001`, and the blobs are not part of the topology binary, so `run-harness.sh` has nothing to load. The harness stays the check for the topology when the capture m4 exists (Request).

### 6.1 Merge interface with the closed-loop protection (the guard stays authoritative)

1. The guard owns instances `0x4024 .. 0x402b` (SP, VI, CPS and their feeders), the module ids `0x070010e2/e3/e4` and SAL limiter enable. The generator refuses to emit a record for them, and `sp11_quality.py` fails if a record would. The decisions file lists all of them as `guard-owned`.
2. The speaker tuning file is separate and flagged GATED. The kernel applies it only when the same condition that replaces the 0009 refusal holds (closed-loop graph up, no fault). Without it the file is not read.
3. Order in the graph keeps SPV5 downstream of every tuned stream module (Verified: SP follows SAL in the device graph, and stream modules precede it). Tuning can change the signal the guard sees; it cannot bypass the guard.
4. Records of `sp11cl` win over `sp11q` for the same (instance, parameter); there is none today.
5. The host-side EQ never exceeds 0 dB: the preamp cancels the largest boost and the limiter sits at -3 dBFS. It cannot raise the level above the user volume, and the kernel caps (PA 0 dB, digital 81) stay beneath.

## 7. Replayed versus approximated

| Windows element | Linux | Status |
|:--|:--|:--|
| SAL limiter, SPv5 | guard (speaker owner) | Not mine; guard authoritative |
| ACDB calibration of registered static modules (mic path) | `sp11q.bin` via the generic path | Replayed, if the kernel gains the loader or the default case. Semantics of the unnamed modules are Unknown, so the effect is unproven |
| ACDB calibration of ffecns, smecns, fluence | `sp11q-dyn.bin` | Replayable only if the ADSP can load the `.so` files (Hypothesis: serve `ADSP/*.so.1` through FastRPC `hexagonrpcd`, the same mechanism the sensors owner needs; unverified, hardware only) |
| Large blobs (55180 B, 6604 B) | none | Not replayed |
| Dolby speaker audio optimizer (20 bands, L/R) | PipeWire filter-chain, 40 peaking biquads | Band centres and gains replayed; filter shape approximated (Dolby does not publish it; Q from the band spacing) |
| Dolby regulator, multiband compressor, volume leveler | one limiter (`fast_lookahead_limiter_1913`, swh-plugins) | Approximated; the Windows behaviour is not reproduced |
| Dolby virtual bass, sliding bass, IEQ, dialog enhancer, virtualizer, surround | none | Not replayed |
| Voice Clarity (DNN AEC and NS) | none; `libpipewire-module-echo-cancel` with WebRTC | Approximated |
| ADSP dual-mic beamforming and ECNS | broadside mono sum plus WebRTC | Approximated; two-mic WebRTC beamforming support in Fedora's library is Unknown |
| Mic gain default +14 dB | software gain default 0 in the generator | Approximated; level needs an on-device measurement |

Hardware-only questions: whether the dynamic modules load, whether the stereo 48 kHz capture path matches Windows' level, the audible match of the EQ, whether PipeWire accepts the generated files (the filter-chain syntax was written from the module's documented format and was not run: no PipeWire on this host; Unknown).

## 8. Requests

- kernel: in `audioreach_set_media_format()` replace `default: rc = 0` by sending `module->data` through `audioreach_set_module_config()` when the module has a topology blob (or add a loader for `<card>-sp11q.bin` modelled on `audioreach-sp11.c`; format in `quality/sp11_quality.py`). Keep a 4 KiB per-record cap.
- speaker owner: consume `<card>-sp11q-spk.bin` only behind the guard condition; keep `sp11cl` authoritative for instances `0x4024..0x402b`; read `sp11q-plan.json` (`playback` section) for the subgraphs, and use `sp11-speaker-quality.conf` as the user-space EQ once the gate allows playback.
- image owner (private mode only): install `pipewire/*.conf` into the user PipeWire config; install the sp11q files next to `sp11cl`; Fedora packages to add: `swh-plugins` (limiter), `webrtc-audio-processing`, `pipewire-module-filter-chain` (part of `pipewire`); in the sensors/audio work, evaluate serving `ADSP/*.so.1` to the ADSP (FastRPC) for the voice modules.
- sources/REA owner: raise `REA_GHIDRA_STARTUP_TIMEOUT_MS` (above 330000, the Hexagon analysis of `qcadsp8380.mbn` did not finish twice) and `GHIDRA_MAXMEM`, so the static module ids `0x1011/13/14/17/19/32/38/41/45/97/98` can be named from their `capi_*` init functions (each entry of the static table at file offset `0x12c5b80` holds two code pointers: static properties and init).
- orchestrator: decide whether the Dolby-derived curve may be part of the private image (data is Windows-derived; S5 exception D25 covers private mode only).
