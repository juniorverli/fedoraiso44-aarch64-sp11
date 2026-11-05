# Rev25 closed-loop audio work split (2026-11-03)

Goal: advance the **speaker-protection closed loop** (SP + VI/CPS from the two WSA8845), not a general audio tuning pass. No speaker output is enabled by this plan; S1/D26 stay. This is a working split, not a device result.

## Current state

- Kernel audio series in `kernel/series`: 0010-0016 (guard, V/I+CPS, AudioReach links/calibration, machine gate, DT), 0017/0018, 0019, 0020, full-context 0021, 0022, 0023.
- Private image: `spk` entry on `m15-spk` with `/sound` model `X1E80100-Microsoft-Surface-Pro-11-CL`, `sp11.entry=spk`, `sp11.allow_nominal=1`, no automatic test; kill switch `sp11.nospk`. After the 2026-11-03 audit fixes, private staging installs the generated CL topology as `...-CL-tplg.bin` and both supplements as `...-CL-sp11cl.bin` / `...-CL-sp11cal.bin`; public images carry none. `sp11cal` is 36 bytes and is **not** a measured per-unit calibration.
- Audit fixes prepared in the image: the CL supplements now match the model-derived names the loaders request, and `speaker-supervisor` requests the advertised S16_LE/48 kHz/stereo front end instead of S32/8 kHz/4 ch. Neither is a device result.
- Remaining kernel defect: the calibration mask can survive a VI graph that closes before start; see `hardware/audio-speakers/evidence/2026-11-03-closed-loop-audit.md`. A kernel worker is implementing the fail-closed lifetime fix.
- Topology: design A (separate VI/CPS back-end links + trigger capture), parser-checked in the offline harness; ADSP acceptance, H3 (cross-graph control link), H10 (trigger capture with unconnected input), live VI/CPS and measured R0/T0 are unverified.
- UCM: the 2026-11-03 candidate removing the userspace-only `Speakers Volume` cset is now in the canonical image input and `m28.json`; physical PA 6/0 writes remain. This addresses the leading `Failed to enable UCM device Speaker` source, but is untested on the device.
- Guard: open allowed without VI/CPS/calibration in closed-loop mode, amplifier unmute gated; no measured R0/T0 mode; `sp11.allow_nominal=1` is the test-only exception.

## REA survey (orchestrator, read-only)

Sanitized findings are in `out/review/rea-audio-closedloop-findings.md`; raw artifacts stay private. Key observations:
- `qcadcm8380.sys` contains `Number NumChannels SP module: %d SP VI module numChannels: %d`, `failed to match num_speaker param in SP and SP VI module`, `SetSpkrProtVIMode: R0T0 parameters got from registry R0 %x, T0 %x`, `UseCalibR0T0`, `SetSpeakerProtectionCalibParams R0CalQ24 failed for ch %d`, `EVENT_ID_SPv5_SPEAKER_DIAGNOSTICS`, `EVENT_ID_VI_CALIBRATION`, and the two-speaker SP/VI tag lookups.
- `qcaudminiport8380.sys` builds `QCAUD\Feature\SpeakerProtection` in `FUN_14008bdc0` and has `SpeakerCoolDownTimerInSec`, `IsSpeakerProtQuickCalib`, `SpeakerInternalChannelMapping`, `SpkrProtCalibProcWorkItemContext`, `Speaker protection recalibration`, `Speaker protection ftm`.
- `qcaucd8380.sys` exposes `AddSpeakerDisableLatencyMS` but the current Ghidra pass did not recover V/I sense gain tables; do not invent gains/port maps. PDB-less indirect tables remain a limitation.
- Inference: Windows matches SP/SP VI channel counts, uses per-channel R0/T0 calibration (Q24), and has a cooldown/recalibration policy. The Linux path must reproduce the channel-count/schema expectations and fail closed; nominal calibration is a test stand-in only.

Independent Gemini 3.8 Flash review (private log `out/review/agy-rev25-audio-gemini.log`): proceed only with a strictly muted Design A validation; do not allow audible output. Test Design A first; keep Design B (RFC multiplexed V/I on the playback link) as fallback. It ranks the risks as H3/H10 graph rejection, V/I port/stream mismatch, userspace trigger not holding the capture open, and nominal-calibration error (~25 K per 10% R0). It recommends: SP/VI channel-count match, exact calibration schema/bounds, APM return-code instrumentation, zero-VI watchdog, and a muted evidence matrix.

## Delegation

| Owner | Task | Status |
|:--|:--|:--|
| audio-speakers / Codex Terra max (`out/review/codex-rev25-audio-closedloop-max.log`) | Audit topology/guard/calibration against the REA findings; prepare the smallest fail-closed change or an explicit no-change; update the muted test plan; no device/build | Done; audit integrated |
| sources / REA follow-up | Decide whether qcaucd8380 PDB/indirect V/I gain tables or the miniport IOCTL payload are recoverable; if not, record the limitation. Do not invent sense gains | Pending; orchestrator REA pass recorded |
| kernel | Implement the fail-closed calibration-lifetime fix (clear on every VI attempt/failure/close; mute if an active graph loses calibration); no other behavior change | Candidate `kernel/patches/0011-...` created; apply/checkpatch and adapted host tests pass; not in `series`, not built, no device |
| image / userspace | CL topology/supplement names fixed in `private-m14.py` and checked by L0; supervisor front-end format fixed; verify in the rebuilt private ISO/L0 | Prepared; build/L0 pending |
| Gemini 3.8 Flash | Independent design/safety review | Done |
| Orchestrator (DeepSeek) | Integrate evidence, keep the work split, run static checks, do not declare protection | In progress |

## Muted first-hardware matrix (no sound)

Boot `spk` with `sp11.allow_nominal=1` only on that entry, under the operator and S1/D26. Keep the sink muted and PA at 0; do not unmute.

1. **Topology accepted:** `APM_CMD_GRAPH_OPEN`/`PREPARE`/`START` return success for the playback and trigger capture graphs; record GPR error codes and topology hash. A rejection points to H3/H10 or a schema mismatch.
2. **VI/CPS real:** the MultiMedia5 capture is present and held open; capture buffers are non-zero/dynamic, not a flat zero stream. Zero data means a port/routing/sense-ADC mismatch, not proof of graph acceptance.
3. **Calibration:** the private `sp11cal` is exactly the expected size/schema; the DSP accepts the R0/T0 parameter for both channels; record the Q24 values. A malformed/36-byte placeholder must be rejected, not silently used.
4. **Guard would unmute:** guard reports all inputs (SP module, calibration, VI/CPS, diagnostics) and `allowed` transitions; if it stays muted, record each failed precondition. The kill switch `sp11.nospk` must still refuse.
5. **Stop:** any fault/latch, graph rejection, zero VI, UCM failure, parity burst or heat ends the session. No loud test until this matrix and the measured R0/T0 path pass.

## Not claimed

No closed-loop protection, no speaker safety beyond D26, no UCM fix and no reset/camera relation is claimed. `sp11.allow_nominal=1` is not a production calibration. The next non-muted test remains blocked.

## Rev25-menu ISO (image-only audio fixes)

- Artifact: `out/iso/sp11-fedora44-aarch64-kiwi-20261104T000512Z-private.iso`, SHA-256 `f44ef2696e31a119459751e18c30d63dd89d933052af1a9c658815135ddffebf`, kernel `7.3.0-65.sp11.24.fc44.aarch64`, 19 GRUB entries.
- Private staging record: `...-CL-tplg.bin` `000b6d72…`, `...-CL-sp11cl.bin` `2eb5a114…`, `...-CL-sp11cal.bin` `5ec3b834…`; the unsuffixed names are rejected. The supervisor source hash is the corrected S16_LE/48 kHz/stereo version.
- L0/L1 were started on 2026-11-04; results pending. This ISO does **not** contain the guard-lifetime candidate, so it is not a closed-loop test artifact.

## Rev25-menu gate results

- L1 PASS on the new private ISO: 19/19 menu titles, VM entry boot `3b782e93-0beb-417f-88e4-2e042dc8d37b`, complete ESP collector, BTF, both sessions, 7 allowlisted failed units, clean ESP.
- L0 clean rerun (alone) pending; the previous 271/1 was the stale 12-entry checker, fixed to 19. The concurrent retry's only failures were private mode/owner checks caused by L1's shared-`/out` chown, not content.
- This ISO remains a debug-menu plus image-audio-staging artifact; it does not contain the guard-lifetime candidate.

- Final gates: **L0 272/0** and **L1 PASS** on the rev25-menu ISO. The private CL topology/sp11cl/sp11cal and supervisor are validated as installed. The guard-lifetime candidate remains unbuilt and not in this ISO.

## Rev25b reset-axis finding

- All eight debug variants on the rev25-menu ISO reset; both safe boots survive. The m15 DTB differs from m15-safe by the GPU node and by the deletion of `orientation-switch` on both QMP combo PHYs (usb-typec 0003 experiment). The switch was restored in m15; DTB rebuild and new checker gates are in progress.
- Three new menu axes (22 entries total): safe DTB + debug services (no pstore), safe DTB + EFI pstore (safe services), and m15 DTB + safe services. These split DTB/GPU/orientation from debug services and pstore. No device result.

## Rev25b audio code status (after completeness audit)

- **Not fully coded/demonstrated.** The worker added `patches/0024-...validate-calibration-flags-report-VI-identity.patch` and `0025-...propagate-topology-widget-load-errors.patch` (on top of 0011), plus `userspace/closed-loop/speaker-supervisor` and `guard-report` with host tests. They are not in `kernel/series`, not compiled, and no ISO/device test. The 2-vs-4 channel map, host V/I data, CPS, measured calibration and cooldown/recalibration remain unresolved. S1/D26 and no audible output.

- Rev25b final ISO: `c9ada4a3…`, 22 entries, restored m15; L0/L1 pending. This ISO carries the reset-axis entries, not the closed-loop kernel candidates.

- Final ISO `c9ada4a3…`: L0 **272/0**; L1 running. It has the 22-entry reset-axis menu and restored m15; it does not contain the closed-loop kernel candidates.

## Rev25c: safe entries, builder fix and the first sound/camera test set

- Menu is now 24 entries. Line 22 `SP11 debug, safe, rear rotation test` (`m15-safe-camrot`) and line 23 `SP11 debug, safe, muted closed-loop VI` (`m15-safe-cl`, `sp11.nospk=1`) sit on the surviving `m15-safe` base; the default stays line 2 `safe`. **Finding (rev25f build): `m15-safe-camrot.dtb` is byte-identical to `m15-safe.dtb` (`244d6e77…`)** because camera patch 0026 is in the series and `rotation = <180>` is already in every variant. Line 22 is therefore a named duplicate; it is documented as such and scheduled for removal, and the rear-orientation check runs on line 2.
- `scripts/kernel-dtb-m15.sh` now accepts the unbound `sp11,speaker-policy` marker for the two new d26 variants and publishes their diffs/records; `scripts/kernel-m8-check.py` applies the M16.2 camera-graph assertions to them too. Without this the builder would have failed their `dt-validate` branch and never published either DTB.
- Rev25 image staging: legacy flags-0 CL supplement `2eb5a114…` (for the `spk` first test), nominal calibration `5ec3b834…`, CL topology `000b6d72…`; camera YAMLs with Agc 3.5 and measured gamma. No device result; no sound claim.
- Ordered next tests, each stopped on the first fault/reset:
  1. `safe` (line 2) control: camera open, audio playback of the public D26 path, collector run.
  2. `safe` (line 2) rear orientation: read the rear sub-device rotation control (expect 180) and compare saved output; line 22 is byte-identical to line 2 in this build and needs no separate boot.
  3. `safe, muted closed-loop VI` (line 23): guard/VI diagnostics per `hardware/audio-speakers/test-plan.md`; no playback.
  4. `speakers (gated)` (`spk`) only under the operator, sink muted, PA 0, S1/D26, with `sp11.allow_nominal=1`; the first audible step is a separate decision after the muted matrix.

## Rev25i camera correction: AWB gain ceiling and measured fallback

- Root cause candidate for the green cast: libcamera's simple IPA clamps white-balance gains at 4.0, while the front module's own calibration (`MWBGainV1`, ten illuminant triplets) needs up to 8.93× red and 4.28× blue. The estimator saturates and leaves green. The rear ladder stays under 4.0, so its cast (if any) is not explained by the clamp and must come from CCM, black pedestal or CFA.
- Image content: `libcamera-sp11-awb-fixed-gains.patch` adds `Awb: maxGains` (default 4.0, accepted 1..16) and `Awb: gains` (fixed measured gains). The private YAMLs now state front 9.83/4.71 and rear 4.07/4.00; `check-awb-ceiling.py` passes structurally, and `camera-diagnostic/calibrate.py` provides the grey-card fallback with `.sp11-orig` backup and `--restore`.
- Prediction (not a result): front improves markedly; rear only if its cast was also gain-limited. The per-frame `ColourGains`/`ColourCorrectionMatrix`/`ColourTemperature` from `camera-diagnostic` decide the next step if green persists.
- Audio unchanged this round: the muted closed-loop entry and its manual tools are in the image; closed-loop sound remains unproven and off.

## Rev25k: on-image AWB report

- `camera-diagnostic/awb-report.sh` is installed in the image: safe-entry and observer gated, enumerates both cameras, enables `IPASoftAwb` debug for one 10-frame capture per camera, parses the applied gains and prints `AWB_STUCK`/`AWB_CEILING`/`AWB_OK`/`AWB_NO_LINE` with CCT and the ceiling in use. No samples read, no frames saved, no LED or control changes; a 0600 report under `/var/tmp`. This replaces the manual `cam` commands in the device procedure.

## Rev25l: debug resets at first GPU use — software-GL workaround

- Evidence (`sp11-logs-4-2`): m15 + msm reaches full GPU init and resets at session start (line 1 and line 21, 33 s); msm blacklisted survives (lines 17/19, user rebooted 17 by hand); safe and safe+pstore survive. Services, pstore and the safe DTB are exonerated.
- `sp11-debug-software-gl.service` forces `LIBGL_ALWAYS_SOFTWARE=1`/`GALLIUM_DRIVER=softpipe` for the debug entry before GDM, notifies the operator and is skipped by `sp11.gpu_accel=1`. The GPU remains loaded for the manual `sp11.gpu_diag=1` two-step. Workaround, not an msm fix.

## Rev25m: reset do debug resolvido por msm.skip_gpu=1 (confirmado no aparelho)

- Linha 1 com `msm.skip_gpu=1`: o driver Adreno não registra, o DPU mantém o display e a máquina não reinicia (operador confirmou). É workaround; o bug do primeiro uso da GPU/DPU no msm permanece.
- Câmera do debug: o wrapper WirePlumber passa a forçar softpipe quando `msm.skip_gpu=1` (sem render node o caminho Mesa/GPU travava). Serviço de software GL removido.
- GPU para diagnóstico: `msm.skip_gpu=0` + `sp11.gpu_diag=1` no GRUB (pode reiniciar; marcadores no pendrive).
