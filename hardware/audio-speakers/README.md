# audio-speakers

## 1. Summary

Two WSA8845 smart amplifiers on SoundWire, driven by the ADSP through AudioReach. Safe use requires speaker protection: a thermal and excursion model fed by voltage/current (VI) sense from the amplifiers. A closed-loop topology, calibration loader and fail-closed kernel guard are prepared and parser-checked, but ADSP graph start, live VI feedback and per-unit calibration remain unverified on the device. Status: `designed`; S1 requires a speaker-off fallback, but the published M16 safe DTB enables the speaker bus and needs correction (see M16 incident evidence).

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
- Machine driver speaker ceilings: `sound/soc/qcom/x1e80100.c:36-52` (WSA digital volume 81 = -3 dB, `PA Volume` 6 = 0 dB, `snd_soc_limit_volume`).
- No protection in the driver: `sound/soc/codecs/wsa884x.c` has no interrupt handler or thermal action; hwmon temperature only (`:1947-1960`).
- Upstream topology `X1E80100-Microsoft-Surface-Pro-11` (audioreach-topology PR 76) has no SP/VI modules. See `evidence/2026-10-30-audio-plan.md` sections 4 and 5.
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| protection graph and calibration | Closed-loop topology plus guard are prepared and parser-checked; ADSP acceptance, separate-graph ordering (H3), VI trigger graph start (H10), live feedback and calibration remain device TBD |
| per-unit calibration (ACDB REV_0D) to Linux format | TBD |
| VI capture path | TBD |
| amplifier reset GPIO and port map are reference-design values | TBD |
| UCM profile | Local copy of alsa-ucm-conf master; capped and muted speaker variant on hold (`userspace/`) |
| M15.1 boot evidence | Available `safe` and `spectra` boots have `swr0` disabled, no WSA link, and guard correctly closed; no speaker-enabled test was captured. Repeatable WSA macro flat-cache warning lacks register/caller context. |
| SPF query times out at `q6apm` probe | Root cause found: GPR callback installed after probe (patches 0006, 0007); the timeout does not block the card (evidence `2026-10-30-d26-audio.md` section 2) |
| PA gain reset to the maximum on SoundWire re-attach | patch 0001 |
| WSA MIX digital volumes uncapped | patch 0002 |
| speaker path must be removable per boot entry | patch 0003 and `patches/dtb-variants/` |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which AudioReach modules and parameters does Windows use for SP and VI (module IDs, calibration blobs)? | TBD | REA of `qcadcm8380.sys`, `qcaudminiport8380.sys`; parse ACDB files of `surface_acsp8380` REV_0D |
| Q2 | Speaker parameters: resistance, thermal constants, excursion limits | TBD | ACDB calibration for REV_0D (this unit is `REV_0d`) |
| Q3 | Amplifier reset GPIO, SoundWire port mapping, gain limits | TBD | Compare DT values with Windows configuration; REA |
| Q4 | Is there an upstream topology with speaker protection for any X1E laptop? | Verified for Surface Pro 11: no (PR 76 topology has no SP/VI module); other X1E boards not checked | rest of the audioreach-topology tree |
| Q5 | Why does `APM_CMD_GET_SPF_STATE` time out with the Windows ADSP image? | Hypothesis H1 to H4 | late reload of `snd_q6apm`; REA R6 and R7 |
| Q6 | Are the machine-driver ceilings (PA 0 dB, digital -3 dB) safe for this unit's speakers? | TBD | Windows limits, REA R1 to R5 |

## 7. Acceptance

1. Speaker protection module active with VI feedback, verified by logs before any loud test (risk S1)
2. Stereo playback at normal volume without distortion
3. Protection reduces gain under sustained load

## 8. Requests

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
