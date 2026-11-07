# audio-speakers

## 1. Summary

Two WSA8845 smart amplifiers on SoundWire are driven by the ADSP through AudioReach. The [muted VI diagnostic candidates](evidence/2026-11-04-muted-vi-implementation.md) provide fail-closed CPS policy, calibration/graph diagnostics, capture supervision and a GPU-off safe DT proposal. Kernel candidates 0011, 0024, audio 0026 and 0027 are integrated in series rev25 (audio 0025 remains excluded pending its cleanup review), the `m15-safe-cl` DTB variant is compiled and published, and the rev25c private image stages the CL topology, both supplements, the manual supervisor and the read-only reporter under a separate nondefault `safe, muted closed-loop VI` entry. None of it has been run on the device yet. Status remains `testing` for the broader D26 image. Closed-loop protection, physical mute and sound safety are not established; S1/D26 and the speaker-off fallback remain. The current requests and test plan supersede conflicting historical material.

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
| `qcaudminiport_base8380` | QCAUD service points to the catalogued miniport SYS; its protection/calibration flow was not decoded this session (`qcaudminiport_Base8380.inf:447,454`) |
| `qcaudminiport_apo8380` | TBD |
| `qcaucd8380` | AUCD service points to the catalogued SYS (`qcaucd8380.inf:52,60`); historical amplifier analysis requires a forced-language repeat |
| `surface_aucdext8380` | TBD |
| `qcadcm8380` | ADCM service and speaker-protection VI endpoint rate/width configuration (`qcadcm8380.inf:53,79-80,89`); runtime calibration-manager flow unverified |
| `surface_acsp8380` | REV_0D ACDB path and calibration data (`surface_acsp8380.inf:131`) |
| `surface_audiominiext8380` | Surface audio settings including speaker calibration cooldown (`surface_audiominiext8380.inf:175-176`); runtime semantics unverified |
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
- Machine driver speaker ceilings: `sound/soc/qcom/x1e80100.c:36-52` (WSA digital volume 81 = -3 dB, `PA Volume` 6 = 0 dB, `snd_soc_limit_volume`).
- No protection in the driver: `sound/soc/codecs/wsa884x.c` has no interrupt handler or thermal action; hwmon temperature only (`:1947-1960`).
- Upstream topology `X1E80100-Microsoft-Surface-Pro-11` (audioreach-topology PR 76) has no SP/VI modules. See `evidence/2026-10-30-audio-plan.md` sections 4 and 5.
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| calibration state can survive an unstarted VI graph in the integrated kernel | Kernel 0011 plus 0024 are apply-checked candidates; integrate and test lifetime, acknowledgement and identity before capture |
| Correct CL names and FE format are staged but supervisor liveness is not established | Integrate the revised MultiMedia5 supervisor with negotiated-parameter, RUNNING/XRUN/stall checks and no sample reads; device behavior remains unknown |
| protection graph and calibration | VI-only diagnostic candidates require CPS in the guard, but have no CPS chain. ADSP acceptance, H3/H10, live feedback and per-unit calibration remain TBD |
| per-unit calibration (ACDB REV_0D) to Linux format | TBD |
| VI capture path | TBD |
| amplifier reset GPIO and port map are reference-design values | TBD |
| UCM profile | Canonical image input `image/component-inputs/d28/audio`; retained speaker sequence synchronized below; runtime transitions require verification |
| M15.1 boot evidence | Available `safe` and `spectra` boots have `swr0` disabled, no WSA link, and guard correctly closed; no speaker-enabled test was captured. Repeatable WSA macro flat-cache warning lacks register/caller context. |
| SPF query times out at `q6apm` probe | Root cause found: GPR callback installed after probe (patches 0006, 0007); the timeout does not block the card (evidence `2026-10-30-d26-audio.md` section 2) |
| PA gain reset to the maximum on SoundWire re-attach | patch 0001 |
| WSA MIX digital volumes uncapped | patch 0002 |
| speaker path must be removable per boot entry | patch 0003 and `patches/dtb-variants/` |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which AudioReach modules and parameters does Windows use for SP and VI (module IDs, calibration blobs)? | Partly verified as ACDB data; Windows runtime order TBD | Compliant REA of the catalogued drivers and workspace decoding |
| Q2 | Speaker parameters: resistance, thermal constants, excursion limits | Nominal Re interpretation is an inference; per-unit values TBD | Independently establish ACDB semantics and a measured calibration path |
| Q3 | Amplifier reset GPIO, SoundWire port mapping, gain limits | TBD | Compare DT values with Windows configuration; REA |
| Q4 | Is there an upstream topology with speaker protection for any X1E laptop? | Verified for Surface Pro 11: no (PR 76 topology has no SP/VI module); other X1E boards not checked | rest of the audioreach-topology tree |
| Q5 | Why does `APM_CMD_GET_SPF_STATE` time out with the Windows ADSP image? | Hypothesis H1 to H4 | late reload of `snd_q6apm`; REA R6 and R7 |
| Q6 | Are the machine-driver ceilings (PA 0 dB, digital -3 dB) safe for this unit's speakers? | TBD | Windows limits, REA R1 to R5 |

## 7. Acceptance

1. Speaker protection module active with VI feedback, verified by logs before any loud test (risk S1)
2. Stereo playback at normal volume without distortion
3. Protection reduces gain under sustained load

## 8. Requests

**Current muted-only integration status, 2026-11-04:** [full evidence and exact owner steps](evidence/2026-11-04-muted-vi-implementation.md) supersede conflicting closed-loop requests below. Kernel series rev25 applies lifetime 0011, calibration/VI identity 0024, graph-open propagation audio 0026 and muted metadata/readback 0027 on top of audio 0023, keeps BTF (`vmlinux` and every module) and all guards, and compiles the [GPU-off safe CL DTB](patches/dtb-variants/x1p64100-microsoft-denali-m15-safe-cl.dts) as `m15-safe-cl`; audio 0025 stays out because its widget-error cleanup has no owner. The kernel adds no sample tap: it records OPEN and SET_CFG results, requested DMA/VI/SoundWire configuration and direct PA-enable reads when the device is attached. A register read is not a physical-silence guarantee.

Image: rev25c keeps the public D26 `safe` default and adds the separate private, nondefault `safe, muted closed-loop VI` entry (`m15-safe-cl`, `sp11.entry=safe`, `sp11.nospk=1`, no `sp11.allow_nominal`). The CL files are generated with `SP11_TOPOLOGY=1 .../build-closedloop.sh --vi-only-diagnostic --nominal-cal`; the three model-matched `...-CL-...` names are staged privately, the public topology is never overwritten, and the CPS-required flag, CRC, one VI link and 36-byte calibration length are checked. The private supplement staged for the `spk` first test was restored byte-for-byte to the legacy flags-0 file (`2eb5a114…`) so that entry keeps the reviewed input; the flags-1 diagnostic file is not staged. The supervisor and reporter are installed as manually invoked tools only; no auto capture, playback or tone helper. The next planned operation is the one [capture-only muted test](test-plan.md), now that the code is built into the image; any failed graph or uncertain PA read is a stop/inconclusive result, and no device run has happened.

Sources/REA: independently establish SP speaker count, codec-DMA packing and actual SoundWire slot assignments, CPS semantics/stream, gains, measured R0/T0 schema and workflow, DSP consumption/readback and cooldown policy. ACDB logical VI map `[1,2,3,4]` now matches Linux's two-speaker expansion, but does not prove DMA packing. The prior REA rejection remains; restore authorized catalog-forced access rather than bypassing it.

**Earlier 2026-11-04 requests (superseded where conflicting):**

**2026-11-04 priority, kernel:** review and integrate main `kernel/patches/0011-audio-speakers-guard-calibration-lifetime.patch` (SHA-256 `7fe2881bcebff5ec7fa823ec9de71e87c92d3369100629bd285e982cd9f80551`) immediately after audio 0023, then review [component candidate 0024](patches/0024-ASoC-qcom-validate-calibration-flags-report-VI-identity.patch) and [candidate 0025](patches/0025-ASoC-qcom-propagate-topology-widget-load-errors.patch). Candidate 0011 binds calibration to the VI graph, invalidates it on setup/start failure and close, and requests existing mute on invalidation; 0024 rejects unknown envelope flags/reserved fields and exposes graph match/ambiguity. None is in the current series or ISO. Candidate 0025 propagates widget parser errors; audit partial-allocation cleanup and retest public and malformed topologies because it may expose previously ignored failures. Apply-check the composed series, run strict checks and host tests, and validate graph-close/retry/concurrency on the actual kernel before any capture test. Preserve all gates and BTF; do not relax nominal, CPS or fault handling.

**Kernel, evidence instrumentation:** report each graph OPEN/PREPARE/START/SET_CFG operation and return status, DSP module/parameter IDs, actual WSA TX0 DMA media count and format, VI operation speaker count and VI map, both SoundWire port/slot assignments, and the current graph identity match without exposing pointers. Do not infer sample validity from a running stream. Establish an independently verifiable physical-output inhibitor before proposing any playback graph test. The two-versus-four count cannot be changed safely without the evidence described in the completeness audit. Obtain a supported muted VI/CPS data or DSP readback path and document what it measures; do not invent mappings, gains or measurement values.

**Image:** corrected CL names and S16_LE/48 kHz/stereo are staged in private f44ef and L0/L1 reported pass; runtime is unverified. Review [the candidate supervisor](userspace/closed-loop/speaker-supervisor) and [read-only guard reporter](userspace/closed-loop/guard-report), integrate only after review, and test MultiMedia5 identification, RUNNING/XRUN handling and signal cleanup. The existing `speaker-first-test` can generate tones and checks supervisor liveness only once; keep it unavailable for this muted investigation, and require any future playback helper to stop on supervisor/PCM loss and every guard refusal. Preserve private-only CL staging, public absence, default mute, S1/D26, caps and speaker-off fallback. Use the current [muted matrix](test-plan.md); the existing ISO is baseline-only for this investigation.

**Calibration / sources:** the 36-byte SP11CA01 is a Linux envelope, not a demonstrated Windows ABI; the generated nominal R0 and assumed T0 are not unit measurements. Recover the DSP R0/T0 SET_CFG layout and measured calibration/event/readback workflow from documented sources or catalog-forced `AARCH64:LE:64:v8A` REA; cross-check the speaker count, VI map, sense gain and CPS requirement. Do not create measured values or a recalibration policy from inference. REA `binary_session` was rejected by automatic approval policy `never`; restore authorized access rather than working around it. Provide file hashes, function addresses and evidence IDs; the workspace format remains undecoded.

**2026-11-03 UCM status:** the canonical and [retained Speaker sequence](userspace/overlay-d28/usr/share/alsa/ucm2/Qualcomm/x1e80100/Surface11-SpeakerSeq.conf) now match at SHA-256 `163cd2d165fb3a0e7003f7ec8b7e7801f5f23737e4274ef9efb1cf091478c179`; the image L0 checker rejects an alias cset and checks the physical PA writes. The original failed cset remains a strong inference, not traced on the device. Retain the remapped mixer, default mute, caps, D26 and the speaker-off fallback; the earlier request to make this source edit is complete, runtime validation is not.

**Kernel:** retain the latch for unknown 0x0200, including PA-off events. Obtain authoritative bit semantics and safe diagnostics before classifying the event or proposing a filter. Handle register I/O errors fail-closed; capture timing and affected amplifier. No cap increase or latch bypass is requested.

**Historical revision 20 image policy (superseded by the 2026-11-03 status above):** At revision 20 the canonical and retained Speaker sequences wrote left and right PA and stereo `Speakers Volume` to 6 after DAC/BOOST; both files then had SHA-256 `73526c093294589554cad1326a46e2acaa7b4a83394b66af3048cca614312879`. The canonical and retained files have since been synchronized to the candidate without the alias cset. Runtime PA values and WsaInit ordering still need the muted checks in the test plan.

Global and per-device `device.routes.default-sink-volume = 0.0` provide the fail-safe. The helper mutes first, then sets 100% on normal boots or 5% with `sp11.audio_first_test=1`. Kernel caps are PA <= 6 (0 dB) and WSA RX/MIX <= 81 (-3 dB); UCM initializes digital volume to 72 (-12 dB). WirePlumber 0.5.19 does not implement `api.acp.max-volume`; it is not a ceiling. Measure digital values at 100% and require a real clamp before acceptance if they rise from 72 to 81. Retain cap readiness, open-loop policy and speaker-off fallback. Capture source/route controls and stereo microphone RMS/peak without retaining speech; no microphone UCM change without evidence. The operator must be present for audible tests; follow [test plan](test-plan.md).

**Historical D28 requests:** the revision-20 request above supersedes conflicting statements below. Rev19 integration and cap installation are evidenced; remaining safety and playback/capture validation gates are in [regression evidence](evidence/2026-11-02-pa-gain-regression.md).

- **kernel:** review and integrate candidates 0019, 0020 and 0021 after the existing 0001–0018 series, then add patches 0022 and 0023. Patch 0023 installs PA/RX/MIX caps in card late probe, before PCM registration; only negative `snd_soc_limit_volume()` returns fail (positive 1 means the control value changed). Preserve closed-loop gates whenever SP is present; allow open loop only for no-SP topology plus exact D26 marker; refuse unreadable policy, no-SP without marker, and any failed PA/RX/MIX cap. Run strict checks and mode/fault/kill negative cases. No kernel build has been run.
- **image / audio-mics:** install the UCM files from the canonical `image/component-inputs/d28/audio` input. Run `userspace/build-topology.sh out/reference-inputs/audioreach-topology` from `linux-msm/audioreach-topology` commit `993a17dcb672357998a463a73f120064d6c74f4f`; install as `X1E80100-Microsoft-Surface-Pro-11-tplg.bin`. For the closed-loop DT model override `X1E80100-Microsoft-Surface-Pro-11-CL`, install the private topology as `X1E80100-Microsoft-Surface-Pro-11-CL-tplg.bin`. Default boot must follow the current revision-20 policy above and retain a speaker-off fallback. Verify model-to-firmware matching and initramfs contents in L0; no early selector service is needed.
- **orchestrator:** no audible test without the operator. Do not regard request text as an implemented kernel guard, or a 5% initial volume as a software ceiling. Build only after the requested implementations and static checks are completed.

- kernel: build and check patches `0001` to `0003` (in `patches/`; branch `w/audio-speakers`); copy `patches/dtb-variants/x1p64100-microsoft-denali-m11-audio.dts` into `kernel/dtb-variants/` and build it; do NOT build `...-m11-audio-spk.dts` into any image. Extend `scripts/kernel-dtb-safety.py`: an enabled `x1e80100-sndcard` is acceptable when it has no `wsa-dai-link` and `swr0` is effectively disabled.
- kernel: if the `wsa_macro 6b00000.codec: using zero-initialized flat cache` warning reproduces in a speaker-enabled diagnostic entry, identify the register and caller before proposing cache/default changes; preserve current mute/guard behavior. See [M15.1 evidence](evidence/2026-11-01-m15.1-audio-safe-boots.md).
- image: boot entry `SP11 audio, microphones` (DTB `m11-audio`, args as M10 plus `sp11.entry=audio`); install `userspace/overlay/` and the topology (`userspace/build-topology.sh`); collector step for H1 (reload `snd_q6apm` late, dmesg, read-only). L0 check 2.18 must keep failing for speaker-enabled device entries.
- firmware: install path for `qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin` (SHA-256 `b192044f...da8c03`, built from upstream source, not a Windows file).
- dsp-subsystems: take the SPF timeout (Q5) with the audio owners; H1 evidence needs no speaker path.
- orchestrator: S1 stays; decide whether the operator wants Path E (exception) or waits for Path P (`evidence/2026-10-30-audio-plan.md` section 8). Run REA R6 and R7 first, then R1 to R5, when REA is free. Cross-check (`agents/protocol.md` §5.1) any value that enters a patch or safety decision: the ceilings 81 and 6 and the WSA port map.
- kernel: after the flash review, add `patches/0004` (wsa884x: write the cached PA gain at attach) and `patches/0005` (wsa macro: EAR SPKR PA Gain stays below the user volume) to `kernel/series` after `0003`. Latent while speakers are off; both must be in any kernel that boots a speaker-enabled DTB. Apply-checked on the full series, checkpatch clean, not built. See `hardware/ec-sam/evidence/2026-10-30-flash-review-verdicts.md`.

- **kernel (M16 incident):** restore a speaker-off m15-safe while retaining microphone and DP links; exact three-include replacement, compiled-DTB assertions and isolation plan are in [M16 evidence](evidence/2026-11-01-m16-safe-audio-die.md). The missing oops header prevents assigning cause; do not change GPIOs, regulators or drivers on this evidence.
- **image / audio-mics:** use microphone-only UCM on the speaker-off fallback and capture the first complete oops, active PCM and UCM state; validate microphone signal only after a stable boot. See [M16 evidence](evidence/2026-11-01-m16-safe-audio-die.md).

- **kernel (M16 playback):** review and integrate candidate patches 0019 then 0020 after 0018 in a later revision, retaining BTF and all guards. Patch 0020 allows preparation on DSP unsupported for SP diagnostics but latches a fault and keeps the amplifier muted because DSP fault events are unavailable. Validate the response and guard on a muted device test; determine an independently evidenced replacement fault-observation path before considering unmute. Do not bypass watermark errors; see [playback evidence](evidence/2026-11-02-m16-safe-playback.md).
- **image / audio-mics (M16 playback):** preserve the existing DP route layer when switching the speaker overlay; fix the collector to address the actual card with `amixer -c 0`, capture DP1 mixer switch state at MultiMedia4 open, active UCM devices, connector state and PCM opener with timestamps, plus topology hash and guard state; do not force routes. Preserve the previously requested speaker-off fallback. See [playback evidence](evidence/2026-11-02-m16-safe-playback.md).

## 9. Log

- 2026-11-07 (closed-loop volume): recovered the Windows endpoint maximum (`surface_audiominiext8380.inf` `MaxEpVolume` 0 dBFS; `acdb_cal_0D.acdb` analog PA target +16.5 dB), added kernel patch 0032 so only `SP11_MODE_CLOSED_LOOP` gets WSA RX/MIX 84 (0 dB) and PA 17 (+16.5 dB) while D26/open-loop stays 81/6, and added the closed-loop-only digital raise to `sp11-audio-safety` (gated by `sp11.allow_nominal=1`; the kernel `platform_max` remains the authority). Static apply/checkpatch/helper tests pass; no kernel or image build and no device run.

- 2026-11-04 (muted VI implementation): matched the ACDB four-entry VI map to Linux's two-speaker map; added explicit CPS-required diagnostic generation, graph-open and metadata/readback candidates, no-read supervisor and safe CL DTB proposal. Host apply/checkpatch/tests pass; no kernel/image/ISO/device build or git write.

- 2026-11-04: audited closed-loop completeness; confirmed the lifetime candidate is unintegrated; added calibration/guard and topology-error candidates, monitored capture supervisor, host checks and a muted-only matrix. No kernel/image build or device test.

- 2026-11-03 (closed-loop audit): reproduced stale VI calibration across an unstarted graph in a host harness, found CL supplement-name and supervisor FE-format mismatches, parsed catalogued ACDB metadata, and requested one priority fail-closed kernel change. REA MCP approval was rejected; added a muted-only test delta. No device action, kernel/image/ISO build or git write.

- 2026-11-03: analysed safe and debug boot audio, identified the raw-control versus remapped alias as the leading UCM failure cause, prepared a retained sequence candidate, and correlated the unknown PA-off latch with reboot; updated muted test and collection requests. No device test or commit.

- 2026-11-02 (D32–D34 sync): synchronized the retained Speaker sequence to the canonical image input, recorded hashes and requested an L0 comparison; updated muted startup, cap, PA alias and BootSequence verification. Device validation remains open.

- 2026-11-02 (rev20 independent verification): compared rev18/rev19 raw PA and DMIC snapshots, kernel cap code and staged UCM; documented the 9 dB nominal PA difference, unproven transition and image/capture retest request; the ceiling interpretation is superseded by D32. No image/kernel edits, device test or git writes.

- 2026-11-02 (D28): built the pinned public topology artifact; added patch 0022 with strict open-loop mode selection and patch 0023 with late-probe cap installation; clarified positive `snd_soc_limit_volume()` return semantics and updated D28 device retest criteria. No kernel/ISO build or device test.
- 2026-11-02 (M16 rev18 follow-up): patch 0023 moves Denali cap setup to card late probe, accepts nonnegative limit returns, logs each control's return plus final readiness, and keeps WSA unmute closed on any missing required cap. Recorded the control-name and ordering evidence plus updated retest criteria; no UCM change, kernel build, ISO build or device test.

- 2026-11-02: added candidate 0021 for degraded SP diagnostics, gated on explicit SP enable, non-nominal closed-loop calibration, VI/CPS and the existing amplifier guards. Windows byte-scan findings and revision-17 merge/reject criteria are in [M16 safe playback](evidence/2026-11-02-m16-safe-playback.md). No build, device test or commit.

- 2026-11-02: checked firmware and miniport byte patterns; added patch 0020 to permit unsupported diagnostics registration while latching a guard fault and keeping speakers muted. No build or device test.

- 2026-11-02: checked the private ISO topology and kernel parser against the SH_MEM lead; the backend does not call watermark registration, and no functional fix is supported. See [M16 safe playback](evidence/2026-11-02-m16-safe-playback.md).

- 2026-11-02: identified DSP opcode as SP event registration, not a proven RX format rejection; DP routes are present but live control state is unobserved. Added fail-closed diagnostic patch 0019 and retest evidence; functional fix remains open. See [M16 safe playback](evidence/2026-11-02-m16-safe-playback.md).

- 2026-11-01 (M16 incident): reviewed the published safe DTB and audio probe paths; 0xe4 is a GPIO phandle, actual offsets 12/13 are in range; cause of DIE remains unknown. Requested a speaker-off fallback and controlled audio isolation; no kernel fix or build. See [M16 evidence](evidence/2026-11-01-m16-safe-audio-die.md).

- 2026-10-30 (closed-loop session): REA of `qcaucd8380.sys` (amplifier init, sense gain table, interrupts); patches 0010 to 0016 (binding, amplifier settings, `sp11` guard, V/I and CPS capture, AudioReach control links and calibration, machine driver gate, DT fragment); generator `userspace/build-topology/` for the private supplement files; stage 4 plan. Offline only. See `evidence/2026-10-30-closed-loop.md`.
- 2026-10-30 (D26 session): GPR callback race verified and fixed (0006, 0007); D26 marker fragment (0008) and WSA playback gate (0009); variants `m13` (mics) and `m13-spk` (marked, gated); `kernel-dtb-safety.py --profile`; `userspace/overlay-speakers/`; closed-loop V/I design from the ACDB. Stages 0 and 1 done, 2 to 5 open. See `evidence/2026-10-30-d26-audio.md`.
- 2026-10-23: dossier created from the static survey.
- 2026-10-30: flash review follow-up patches 0004, 0005 (latent safety, speakers still off everywhere)
- 2026-10-30: audio plan (`evidence/2026-10-30-audio-plan.md`): M8/M10 state, DT, safety layers, topology/UCM, patches 0001 to 0003, REA questions; status `designed`.

- 2026-10-31 (topology and RFC session): closed-loop topology generated locally (`userspace/build-topology/m4/`, `build-closedloop.sh` with `SP11_TOPOLOGY=1`) and loaded through the real kernel parser in a QEMU harness (`build-topology/harness/`, 16 checks pass); acdb_inspect module names corrected (0x0700101a is DATA_LOGGING, not MFC, so no host tap is needed); Qualcomm RFC fetched, pinned and evaluated; no kernel patches. See `evidence/2026-10-31-topology-rfc.md`.
- 2026-11-01: M15.1 safe and Spectra logs confirm the speaker bus/link are disabled and guard state remains closed as intended; recorded the unresolved WSA macro flat-cache warning and read-only microphone endpoint observations. No graph failure or safe-path speaker defect inferred. See [M15.1 evidence](evidence/2026-11-01-m15.1-audio-safe-boots.md).
- 2026-10-31 (flash review, kernel part): independent review F-01..F-12 verified against the composed tree; the amplifier unmute (not the stream open) is now the gate; patches 0012 to 0015 amended in place; see `evidence/2026-10-31-flash-review-verdicts.md`.

## Requests (2026-10-30, orchestrator)

- **S1 evidence, Path P:** the Argon REA report (`evidence/2026-10-30-argon-rea-report.md`, spot-checked) shows Windows protects the two 4 ohm speakers with a closed-loop SPv5 speaker-protection module in the ADSP (V/I and CPS feedback, thermal model, 110 C hard limit, 180 s cooldown) plus ACDB calibration, not with a static volume cap. Linux 7.3 has none of that (no V/I sense ports, no IMCL links, no SPv5 calibration). Speakers therefore stay OFF in every DTB and image. Microphones are safe and may proceed (`m11-audio`).

## Requests (2026-10-30, D26 session)

Full text in `evidence/2026-10-30-d26-audio.md` section 9.

- kernel: add 0006 to 0009 after 0005; add `patches/dtb-variants/x1p64100-microsoft-denali-m13.dts` and `-m13-spk.dts` to `kernel/dtb-variants/`; `kernel-dtb-safety.py --profile d26` only for `m13-spk`, `default` for every other DTB. A kernel that boots `m13-spk` must contain 0001, 0002, 0004, 0005, 0009.
- image: entries `no speakers` (M12 DTB), `microphones` (`m13`, `overlay/`), extra `speakers (gated)` (`m13-spk`, `overlay/` + `overlay-speakers/`); `m13-spk` is not the default until the first test (evidence section 7) passes; L0 2.18 accepts speaker DTBs only for that entry with the `d26` profile.
- orchestrator: Stage 2 (wsa884x TX ports and sense registers, port map, second reset) needs a REA session on `qcaucd8380.sys` and `qcadcm8380.sys`; REA was not used in this session.

## Requests (2026-10-30, closed-loop session)

Full text and grades in `evidence/2026-10-30-closed-loop.md`.

- kernel: add `patches/0010` to `0016` to `kernel/series` in that order after `0009` (0010 binding, 0011 amplifier settings, 0012 guard, 0013 amplifier capture and faults, 0014 AudioReach, 0015 machine driver, 0016 DT). 0015 replaces the unconditional refusal of 0009 with the guard of 0012; both must be in the same kernel. Config: `CONFIG_SND_SOC_SP11_GUARD=m` (selected by `CONFIG_SND_SOC_X1E80100`). Copy the updated `patches/dtb-variants/x1p64100-microsoft-denali-m13-spk.dts` (now includes `x1-microsoft-denali-audio-closedloop.dtsi`) over the old one; it is the only variant that includes the fragment. Run `kernel-dtb-safety.py --profile d26` on it (checked on the compiled DTB of this session: accepted) and `--profile default` on every other DTB. Check the module `sp11.ko` is in the RPM and that `modules.dep` lists it before `snd-soc-x1e80100`.
- image: boot entries: keep `SP11 speakers (gated)` (`m13-spk`), add `SP11 speakers kill` (same DTB plus the kernel argument `sp11.nospk`). Never add `sp11.allow_nominal` to a default entry. Private mode only (D25, S5): install `out/firmware-private/audio/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-sp11cl.bin` (and `...-sp11cal.bin` if present) to `/usr/lib/firmware/qcom/x1e80100/`; the public ISO never carries them; record hashes only. Run `userspace/build-topology/build-closedloop.sh` before the private image build (hook: it writes into `out/firmware-private/audio/`; add `--nominal-cal` only for the operator's first test, `--with-cps` only when the topology has the CPS chain). UCM: the speaker verb must not start playback by itself; a user-space supervisor that opens the V/I capture stream before any playback is needed once the topology has one (not yet possible, evidence section 6). Collector for stage 4: evidence section 8 (`/sys/kernel/debug/sp11/guard`, the V/I recording, `/proc/cmdline`, hashes of the private files).
- firmware: the topology file name is unchanged (`X1E80100-Microsoft-Surface-Pro-11-tplg.bin`, public, no SP/VI). The two new private files above are Windows-derived: keep them out of `firmware/` manifests that feed public output.
- orchestrator: (1) decide the V/I link design before the first hardware test: separate back-end links (this series) or the RFC style link on the playback back end (evidence section 3; it needs an ASoC core change and has hardware testing). (2) Cross-check (`agents/protocol.md` section 5.1) the values of evidence section 7 with a reader that does not see the answers: the amplifier registers of the two-cell set, the sense gains (-21 dB, +12 dB), the control link ports and intents. (3) `qcadcm8380.sys` was not opened; the SPv5 diagnostics payload and the R0/T0 flow of the Windows driver are still Unknown. (4) S1 stays; this series does not lift it.

## Test plan additions

See `test-plan.md` section T4 and evidence section 8.

## Requests (2026-10-31, topology session)

Full text in `evidence/2026-10-31-topology-rfc.md` section 7.

- image (private mode only): run `SP11_TOPOLOGY=1 userspace/build-topology/build-closedloop.sh` before the build; install `out/firmware-private/audio/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin` OVER the public topology of the same name (the kernel requests only this name), plus `...-sp11cl.bin`; `...-sp11cal.bin` (`--nominal-cal`) and `sp11.allow_nominal=1` only on a dedicated first-test entry, never the default. The public ISO carries none of these. User-space supervisor: open the MultiMedia5 capture (PCM index 4) and keep it open, never read it, before any playback.
- kernel: nothing for M14. For M15 only if the first run shows the closed-loop graph cannot start: port the RFC (evidence section 5 plan), plus the `audioreach_get_module_priv_data()` size fix and parser error propagation.
- orchestrator: S1 stays. Decide whether the first-test entry with nominal calibration is allowed (recommendation in evidence section 6).

## Requests (2026-10-31, flash review)

- kernel: re-check `kernel/series` against the amended `patches/0012` to `0015` (file names unchanged, series order unchanged, `git apply --check` clean on v7.3 plus the full 69-entry series). Config: `CONFIG_SND_SOC_SP11_GUARD` is now selected by `SND_SOC_QDSP6_APM` and `SND_SOC_X1E80100`, and `SND_SOC_WSA884X` depends on it being built the same way; no `sp11.config` change is needed, but `scripts/kernel-check` and `scripts/kernel-m8-rpm-check.py` should also assert that `wsa884x.o` calls `sp11_guard_unmute_check` (the amplifier is where the gate is enforced) and that `x1e80100.o` still calls `sp11_guard_check` (it now only decides whether a stream may open).
- image: the user-space order is unchanged (open the V/I capture first, keep it open, then play). A speaker stream now opens without the V/I capture and plays silently; the debugfs file shows `open_allowed` and `allowed` separately.
