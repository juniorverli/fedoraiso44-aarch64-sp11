# Audio bring-up plan: microphones first, speakers behind S1 (2026-10-30)

Scope: current audio state from the M8 and M10 device logs, what the devicetree needs, the safety layers that must exist before any speaker is enabled, what the image needs, and what evidence lifts S1. Inputs are static: logs, `sources/linux` (v7.3), the reference project (`out/ref/archiso-aarch64-sp11`, `out/ref/linux-sp11`), upstream `audioreach-topology` and `alsa-ucm-conf`, and the Fedora 44 repositories. REA was not used (another agent owns it); questions for it are in section 9.

Log citations (SHA-256 prefixes of the `.gz` files): M10 `out/device-logs/m10-20261030/f7939948-b4b6-43b0-8671-04a3ff7c5eaf/` `dmesg.txt.gz` 2512ca378d3ddefc, `sound.txt.gz` 02d11d36aa9f2dee, `lsmod.txt.gz` aea3bcbd45cb3c73, `devicetree.dts.gz` 0db30e9fdc3912ed, `extra-dsp-subsystems.txt.gz` b256064c9a9c2e66. M8 `out/device-logs/m8-20261029/4b6f080c-18f7-4235-9764-2e126b4d5a06/` `dmesg.txt.gz` 3753b5c97a558d77, `sound.txt.gz` f4b616cc6cb3d900.

## 1. Decision summary

1. Safety rule S1 is not lifted by anything in this plan. A volume cap is not protection (`plan/risks.md` S1). The upstream topology for this machine has no speaker-protection or VI modules (section 5), so protection does not exist yet on Linux for this unit.
2. Microphones carry no S1 risk if the speaker path is physically absent from the DT. Stage A (`m11-audio`) enables the sound card with the VA capture link only and leaves `&swr0` disabled, so no WSA8845 is enumerated or programmed.
3. Stage B (speakers) stays on hold. Its sources are prepared (DT fragment, capped UCM, limits) and kept out of every image and boot menu until the evidence in section 8 exists.
4. Before stage A can show a card, the ADSP audio framework must answer. Today it does not (section 2). That is the first blocker and it belongs to `dsp-subsystems` with audio input.

## 2. Current audio state

| Fact | Grade | Source |
|:--|:--|:--|
| No sound card. `/proc/asound/cards`: "no soundcards", `aplay -l`: none, `/dev/snd` has only `seq` and `timer`, no `/sys/bus/soundwire/devices` | Verified | M10 and M8 `sound.txt.gz` |
| The DT on the device has `/sound` `status = "disabled"` and `&swr0` (`soundwire@6b10000`) `status = "disabled"`; both `speaker@0,0` and `speaker@0,1` hang under it | Verified | M10 `devicetree.dts.gz` (`/sound` model `X1E80100-Microsoft-Surface-Pro-11`, `swr0` label `WSA`), `kernel/patches/0001-arm64-dts-qcom-denali-lcd-disable-unprotected-speakers.patch` |
| `q6apm`, `q6apm_dai`, `q6apm_lpass_dais`, `q6prm`, `q6prm_clocks`, the four LPASS macros (`wsa`, `va`, `rx`, `tx`) and `lpass-lpi-pinctrl` are loaded; `snd_soc_x1e80100`, `soundwire_qcom`, `snd_soc_wsa884x`, `snd_soc_qcom_sdw` are not | Verified | M10 `lsmod.txt.gz`, `modules-loaded-late` |
| ADSP is `running` with `qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn`; the `adsp_apps` GLINK channel carries GPR services `gprsvc:service:2:1` (APM) and `2:2` (PRM); `msm/adsp/audio_pd` instance 74 is found by the PD mapper | Verified | M10 `dmesg.txt.gz` 10:25:57 to 10:25:57,78; M8 same at 19:45:49 |
| `qcom-apm gprsvc:service:2:1: CMD timeout for [1001021] opcode`, logged about 33 s after boot (the 5 s wait ends there); identical in M8, M10 and M5 (32 s) | Verified | M10 `dmesg.txt.gz` 10:26:26,332999; M8 19:46:17,732569; `audioreach.c:617-623`, `q6apm.c:143-152,886`, `audioreach.h:42` (opcode is `APM_CMD_GET_SPF_STATE`) |
| The timeout is independent of `/sound`: `q6apm` probes because its `gpr` node sits under the ADSP `glink-edge` | Verified | `hamoa.dtsi` gpr node; `hardware/dsp-subsystems/evidence/2026-10-28-m5-device-log.md:74` |
| The separate CDSP edge `OPEN_ACK` timeouts (`IPCRTR`, `fastrpcglink-apps-dsp`) are not the ADSP audio path | Verified | M10 `dmesg.txt.gz` 10:26:02 and 10:26:25 on `32300000.remoteproc:glink-edge`, not `6800000` |
| The ADSP answered GLINK and PDR for other services (charger, PMIC, UCSI) while the SPF query timed out, so transport works and the audio framework (SPF) did not answer | Inference | dsp-subsystems M8/M9 evidence: `hardware/dsp-subsystems/evidence/2026-10-29-m8-and-m9.md:32` |
| The topology file `qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin` is not in the image (linux-firmware 20261019 has no Surface Pro 11 topology) | Verified | `topology.c:1422` builds the name from `driver_name` and `card->name`; `dnf repoquery -l qcom-firmware` in a Fedora 44 container lists X1E80100 topologies for ASUS, LENOVO 21N1 and 83ED only; `pkgs.txt.gz` has `linux-firmware-20261019-1.fc44` |

Why the SPF may not answer, none confirmed:

| # | Hypothesis | Observation that answers it |
|:--|:--|:--|
| H1 | The audio PD is slow to start and the single `GET_SPF_STATE` at `q6apm` probe is too early | After boot, `modprobe -r snd_q6apm q6prm ...; modprobe snd_q6apm` (or `rmmod` and reload) and read the dmesg: an answer means a timing issue only |
| H2 | The Windows ADSP image starts its audio PD only on a request from the Windows audio driver that Linux does not send | REA question R6 (what Windows sends to the ADSP before audio starts) |
| H3 | The static PD mapper reports `audio_pd` UP (the indication `state: 0x1fffffff` may come from the in-kernel PD mapper rather than from a started PD) while the real PD never started | A GLINK or QRTR trace with `trace_event=:mod:qcom_glink` (already on the M10 command line) shows whether any `avs/audio` service appears |
| H4 | GPR addressing (domain, service, port) differs in the Windows build of the ADSP | REA question R7 |

Request to the owner of the next test image: add a read-only late reload of `snd_q6apm` and the dmesg lines to the collector (this is H1, no risk to speakers because `/sound` stays off).

## 3. What the DT needs

The 7.3 board DT already contains everything the sound card needs; the project overrides disable it. Compared with the reference project's DT changes:

| Item | State in 7.3 | Grade | Source |
|:--|:--|:--|:--|
| `sound` node: `compatible = "qcom,x1e80100-sndcard"`, `model = "X1E80100-Microsoft-Surface-Pro-11"` | present | Verified | `x1-microsoft-denali.dtsi:309-312`; M10 DT dump |
| `audio-routing`: `SpkrLeft IN` from `WSA WSA_SPK1 OUT`, `SpkrRight IN` from `WSA WSA_SPK2 OUT`, `VA DMIC0` and `VA DMIC1` from `vdd-micb` | present | Verified | `x1-microsoft-denali.dtsi:312-315` |
| `wsa-dai-link`: codecs `left_spkr`, `right_spkr`, `&swr0 0`, `&lpass_wsamacro 0`; CPU `WSA_CODEC_DMA_RX_0` | present | Verified | `x1-microsoft-denali.dtsi:317-332` |
| `va-dai-link`: codec `&lpass_vamacro 0`, CPU `VA_CODEC_DMA_TX_0` | present | Verified | `x1-microsoft-denali.dtsi:334-348` |
| `&swr0` with two `sdw20217020400` speakers, reset GPIO `lpass_tlmm 12`, supplies `vreg_l15b_1p8`, `vreg_l12b_1p2`, port maps `1 2 3 7 10 13` and `4 5 6 7 11 13`, pinctrl `wsa_swr_active` + `spkr_01_sd_n_active` | present | Verified (copied from Romulus and CRD, which use the same WSA8845 layout and reset GPIO; not yet proven on this unit) | `x1-microsoft-denali.dtsi:1079-1107`; `x1e80100-microsoft-romulus.dtsi:1278-1300`; `x1-crd.dtsi:1447-1470`. Q3 of the dossier stays open |
| `&lpass_vamacro`: `dmic01_default` only, `vdd-micb` `l1b`, `qcom,dmic-sample-rate = <2400000>` | present | Verified | `x1-microsoft-denali.dtsi:865-871`; M10 DT dump `qcom,dmic-sample-rate = <0x249f00>`. The reference commit `d34ce0c788b5` records why: Windows runs `DMIC0_CTL = 0x5` (divider /4, 2.4 MHz), 4.8 MHz distorts, and only two microphones exist |
| `&lpass_wsamacro` instance | present, always enabled | Verified | M10 DT `codec@6b00000`; `wsa_macro 6b00000` probes in M10 `dmesg.txt.gz` |
| tx macro, `&swr2`, `&swr1`, `&lpass_txmacro` | not used by Denali (no headset codec, no analog mic) | Inference | Denali has no `wcd938x` node; the topology VA path uses the VA macro only |
| DisplayPort audio links (`displayport-0/1-dai-link`) | absent in 7.3, present in the reference (`2db74c78d5f2`); also in the upstream topology and UCM | Verified | `git show 2db74c78d5f2` in `out/ref/linux-sp11`; not needed for speakers or microphones, left out here |

Conclusion: no new nodes are needed. The work is selective enabling.

- Stage A `m11-audio` (microphones, S1 intact): `x1-microsoft-denali-audio-mics.dtsi` sets `/sound` to okay, replaces `audio-routing` with the two DMIC routes and deletes `wsa-dai-link`. `&swr0` is not touched. Built on `x1p64100-microsoft-denali-m10.dts` it differs from M10 only in the sound node (checked by decompiling both DTBs with `dtc`, only phandle numbers and the sound node differ).
- Stage B (speakers, on hold): `x1-microsoft-denali-audio-speakers.dtsi` sets `/sound` and `&swr0` to okay, which restores the upstream board behaviour.
- `kernel-dtb-safety.py` reports `m11-audio` as unsafe because the `x1e80100-sndcard` node is enabled, although both speaker nodes are effectively disabled. Both `speaker@0,*` nodes report `effective_enabled = False` for `m11-audio` and `True` for the speaker variant. Request to kernel: allow an enabled card only when it has no `wsa-dai-link` and `swr0` is effectively disabled; keep the existing failure for any other case.

DT-level gain limit: the WSA884x binding has no gain property and no mixer-limit property exists for the card, so no DT property can cap the gain. The cap is in the machine driver (next section). Inventing a binding property was rejected: the driver cap is already upstream and is the same for every board.

## 4. Safety layers before any speaker is enabled

Layers, outermost last. Each must hold even if the next fails.

| # | Layer | State | Grade / source |
|:--|:--|:--|:--|
| L1 | Default DTB and every packaged DTB keep `/sound` and `&swr0` disabled; `m11-audio` has no speaker path; the speaker variant source is not in any image or menu | Implemented (patches in `kernel/`, new files in `patches/`) | `kernel/patches/0001`; `patches/dtb-variants/` |
| L2 | Machine-driver ceilings: WSA digital volume at 81 (-3 dB), `PA Volume` at 6 (0 dB) via `snd_soc_limit_volume()`, applied when the WSA link initialises | Upstream, already in 7.3 | `sound/soc/qcom/x1e80100.c:36-52` Verified |
| L3 | MIX path digital volumes (`WSA_RX0_MIX`, `WSA_RX1_MIX`, `-84..+40 dB`) were uncapped; ceilings added | Patch `0002` | `lpass-wsa-macro.c:2199-2202` Verified |
| L4 | `PA Volume` was left at the register reset value after every slave attach. `wsa884x_reg_init` writes `WSA884X_DRE_CTL_1 = 0x04` (field 2, mixer value 29, TLV nominal +34.5 dB) on each attach (`wsa884x_update_status` calls `wsa884x_init` on attach). The cap of L2 is applied once, so a bus reset or clock stop re-opens the gain until user space writes the control. Reset value changed to the field for mixer value 6 | Patch `0001` | `wsa884x.c:1112,1540-1566,1735-1737` Verified by reading; the effect on hardware is an Inference (register semantics from the code, no datasheet) |
| L5 | Userspace never exceeds the kernel ceilings: UCM values (PA 0 at start, never above 6, WSA RX 78) are below the ALSA maxima. Upstream UCM writes `PA Volume 12` and `WSA_RX0 Digital Volume 84`; both exceed the kernel ceilings and `soc_mixer_valid_ctl()` returns `-EINVAL` for them, so the upstream speaker sequence would fail at those lines | Files in `userspace/stage-b-speakers-HOLD/` | `soc-ops.c:151-163` Verified; upstream UCM text Verified (fetched from `alsa-ucm-conf` master `codecs/wsa884x/two-speakers/SpeakerSeq.conf` and `codecs/qcom-lpass/wsa-macro/init.conf`); the failure of the sequence is an Inference (depends on how alsa-lib handles a failed `cset`) |
| L6 | Mixer exposes no unlimited gain: ALSA control maxima report the cap (`soc_info_volsw` uses `platform_max`), so PipeWire and GNOME see 0..6 for `PA Volume`. Software gain above 100 % is disabled in GNOME with a locked dconf key, because software gain would otherwise bypass L2 | `userspace/overlay/etc/dconf/db/distro.d/` | `soc-ops.c:192-193` Verified; GNOME key `org.gnome.desktop.sound allow-volume-above-100-percent` Verified in the Fedora 44 schema. That Fedora's dconf profile reads the `distro` database is Hypothesis; the image worker must check `/etc/dconf/profile/user` or use `local.d` |
| L7 | Default muted: UCM sets `PA Volume` 0 (TLV minimum is mute) at verb enable and on speaker disable; WirePlumber `device.routes.default-sink-volume = 0.05` instead of 0.064 | `userspace/` | WirePlumber setting exists, type float, 0..1, default 0.064, Verified in Fedora 44 `wireplumber.conf`. The mute behaviour of PA Volume 0 is an Inference from `DECLARE_TLV_DB_SCALE(pa_gain, -900, 150, -900)` (mute flag set), not tested |
| L8 | Amplifier built-in protection, enabled by the driver defaults: over-current limit `WSA884X_CURRENT_LIMIT` 0x15 written at each power-on (`wsa884x_spkr_post_pmu`), `OCP_CTL 0xc6`, clip detect `0x7e/0x4c`, PA state machine error control `0x00`, temperature ADC readable only 5..45 degC (`WSA884X_LOW/HIGH_TEMP_THRESHOLD`), hwmon `temp1_input` exists | Hypothesis that these are active and effective | `wsa884x.c:725-726,956-967,1063,1672-1692,1947-1960`. The driver has no interrupt handler and no thermal action: over-temperature or over-current is not reported to the kernel and gain is never reduced |
| L9 | Speaker protection with VI feedback | Absent | Topology has no SP/VI modules (section 5); the `VISENSE Switch` is set to 0 by upstream UCM, so the amplifier's current and voltage sense is not even streamed |

What none of these layers do: model cone excursion or voice-coil temperature. The cap keeps the amplifier at or below roughly the level used by other X1E machines in the upstream ecosystem ("intentionally limited", reference README line 26). Whether that level is safe for this unit's speakers is TBD: it needs the Windows limits (section 9).

## 5. Topology, UCM and what Fedora provides

Checked in a Fedora 44 aarch64 container on 2026-10-30.

| Item | Fedora 44 state | Grade | What is needed |
|:--|:--|:--|:--|
| `alsa-ucm` 1.2.16.1-1.fc44 (the UCM package is named `alsa-ucm`, not `alsa-ucm-conf`) | has `Qualcomm/x1e80100/` with Dell, Lenovo, TUXEDO, Surface Pro 12in; no Surface Pro 11. Has `codecs/wsa884x/two-speakers/*`, `codecs/qcom-lpass/{wsa,va}-macro/*`, `lib/ctl-remap.conf` | Verified | Add local `MICROSOFT-Surface-Pro-11.conf`, `Surface11-HiFi.conf` and a `conf.d/x1e80100/X1E80100-Microsoft-Surface-Pro-11.conf` link (the `conf.d` entries are links named after the card, for example `X1E80100-CRD.conf`) |
| Upstream UCM for the Surface Pro 11 | in `alsa-ucm-conf` master (PR 847 was closed on 2026-10-09 with merged=false in the API; the files are on master) | Verified (files); merge history Inference | Not yet released into Fedora; our local copy follows it |
| `qcom-firmware` 20261019-1.fc44 (linux-firmware subpackage that holds qcom files; the image installs `linux-firmware`) | topologies for ASUS, LENOVO, qcs/sm boards; none for Surface Pro 11 | Verified | Install `qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin` locally |
| Topology source | `linux-msm/audioreach-topology` commit `aab5c37c4fb9d9daed2dc789b8b7ca91c4133899` (PR 76, merged 2026-09-14), `X1E80100-Microsoft-Surface-Pro-11.m4` | Verified | `userspace/build-topology.sh` builds it with Fedora 44 `alsa-topology-utils` 1.2.16; output SHA-256 `b192044f01e97eabe7f6df9ae0d394086badb3c30124573210bc781093da8c03` (22856 bytes) |
| Topology content | Four stream sub-graphs (MultiMedia1 and 3 and 4 playback with a volume module, MultiMedia2 capture), device sub-graphs `WSA_CODEC_DMA_RX_0`, `DISPLAY_PORT_RX_0/1`, `VA_CODEC_DMA_TX_0`, all 48 kHz S16_LE. No speaker-protection module, no VI capture | Verified | Protection needs a different topology with SP and VI modules and calibration (TBD, section 9) |
| WirePlumber 0.5.18, PipeWire 1.6.10 | in the image (`pkgs.txt.gz`) | Verified | Config drop-in only |

The topology binary is built from public upstream source (BSD-3-Clause) and may be installed; it is not a Windows file (S5 not touched). It is not committed here: the recipe and the hash are. Request to firmware/image: install it at `/usr/lib/firmware/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin` in the private image, or ship it as a small local RPM until linux-firmware carries it.

Local additions for stage A (all under `hardware/audio-speakers/userspace/overlay/`): the microphone-only UCM profile, the WirePlumber default-volume drop-in and the locked dconf key. The speaker UCM (capped, muted at start) is in `stage-b-speakers-HOLD/` and must not enter an image before S1 changes.

## 6. Boot entries

| Entry | DTB | Speakers | When |
|:--|:--|:--|:--|
| Default (M10 and later) | `x1p64100-microsoft-denali-m10.dtb` | off, no card | always the default; unchanged |
| `SP11 audio, microphones` | `x1p64100-microsoft-denali-m11-audio.dtb` | off, no WSA link, `swr0` off | stage A: once the SPF question (section 2) is solved or while collecting H1 evidence |
| `SP11 audio, speakers` | `x1p64100-microsoft-denali-m11-audio-spk.dtb` | on, limited | not generated until S1 is lifted in `plan/risks.md`; `scripts/kernel-dtb-variants.sh` must not build it by default and L0 check 2.18 must keep failing for any device entry that enables speakers |

`m11-audio` mirrors the M10 entry arguments (verbose, `clk_ignore_unused pd_ignore_unused`, `rd.driver.blacklist=qcom_battmgr`) plus `sp11.entry=audio` and the trace already used (`qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink`). Image must allow the module list `snd_soc_x1e80100`, `snd_soc_qcom_common`, `snd_soc_qcom_sdw` late (squashfs, not initramfs); on the packaged kernel they are Fedora config modules (to be confirmed in the kernel RPM file list by the image worker).

## 7. Patch series proposed (`hardware/audio-speakers/patches/`)

Applied on v7.3 plus the full current `kernel/series` (20 `git am`, the rest `git apply` for the touch-pen patches that carry no mail headers); the three patches are commits on top in `out/linux/audio-speakers` (branch `w/audio-speakers`).

| Patch | Content | Check |
|:--|:--|:--|
| `0001-ASoC-codecs-wsa884x-reset-the-PA-gain-to-0-dB-instea.patch` | `DRE_CTL_1` reset value from mixer 29 to mixer 6 (0 dB) | `checkpatch --strict`: 0 errors, 0 warnings. Not compiled: no kernel build was run (build lock) |
| `0002-ASoC-qcom-x1e80100-also-limit-the-WSA-MIX-path-digit.patch` | Four `snd_soc_limit_volume()` calls for the MIX controls | same |
| `0003-arm64-dts-qcom-x1-microsoft-denali-add-opt-in-audio-.patch` | Two include-only DT fragments, no Makefile entry, no existing DTB changes | `checkpatch --strict`: 0 errors, one MAINTAINERS notice for new files. Fragments compiled and decompiled through the DTS variants below |
| `dtb-variants/x1p64100-microsoft-denali-m11-audio.dts`, `...-m11-audio-spk.dts` | Variant sources on top of the M10 DTS; not patches, not in the RPM | compiled with `cpp` and `dtc` (container `sp11-kernel-fc44`), speaker nodes effective status checked with `kernel-dtb-safety.py` |

All three patches end with `Assisted-by: Claude Sonnet 5.5` and have no `Signed-off-by`. The speakers are not enabled in any DTB that the kernel RPM builds.

## 8. Evidence needed to lift S1

S1 requires speaker protection that runs and is evidenced. The operator decides whether S1 changes; this plan does not.

Path P (protection, the rule as written): all of the following.

1. A topology or graph with the speaker-protection and VI modules for this unit, loaded without error (`dmesg` shows the topology and no AudioReach error), and a captured log showing the SP module in the graph with VI feedback streaming (`VISENSE Switch` on, VI capture running).
2. Calibration for this unit (`REV_0d`): speaker resistance, thermal constants and excursion limits taken from the Windows ACDB or driver configuration (R1 to R3), applied through the topology or a calibration blob.
3. A play test at the ceilings of section 4 with `hwmon` amplifier temperature logged before, during and after, and proof that gain falls under sustained load (the dossier's Acceptance 3).

Path E (operator exception, not protection): only the operator can write it into `plan/risks.md`, with the scope in words. If the operator chooses it, the minimum observations before the first audible test are:

1. Stage A finished: the card probes, microphones record, no WSA device appeared (`ls /sys/bus/soundwire/devices` empty).
2. A silent bring-up of the speaker variant with `PA Volume` 0: both `sdw20217020400` devices enumerate, `wsa884x` probes without error, `hwmon` temperature readings plausible, no kernel warnings.
3. `amixer` shows the ceilings: `SpkrLeft PA Volume` and `SpkrRight PA Volume` maximum 6, the four `WSA ... Digital Volume` and four `_MIX` maximum 81; writing 7 or 82 fails. After forcing a SoundWire re-attach, `PA Volume` still reads at or below 6 (patch 0001).
4. The Windows limits (R1 to R4) show the ceilings are at or below what Windows allows for this unit.
5. First sound only with the operator present, lowest step, short tones, and a stop on any distortion or heat.

## 9. REA questions for later (do not run now)

Windows driver store paths under `sources/windows/DriverStore/`; language from `sources/binary-catalog.tsv` per `agents/protocol.md` §9 before opening.

| # | Question | Targets |
|:--|:--|:--|
| R1 | What speaker-protection parameters does Windows apply for this unit: resistance, thermal model, excursion and power limits, per speaker and per `REV_0d`? | `qcadcm8380.sys`, `qcaudminiport_base8380`, `qcaudminiport_apo8380`, `surface_acsp8380` (`REV_0D`) |
| R2 | Which AudioReach modules and parameter IDs does Windows put in the playback graph (SP, VI, limiter, volume, compander) and in what order? | `qcaudminiport8380.sys`, `qcadcm8380.sys`, `surface_acsp8380` |
| R3 | How are the ACDB files organised (container format, which blocks are calibration for SP and VI, how `REV_0D` is selected)? | `surface_acsp8380.inf_arm64_*` ACDB and workspace files |
| R4 | What gain, volume and thermal limits does Windows apply on the WSA8845 path: `PA`, digital volume, compander, "SPKR" thermal thresholds, current limit, PBR? | `qcaudminiport8380.sys`, `qcasd8380.sys`, `qcasd_apo8380`, `dax3_ext_qc`, `surfaceapoextension` |
| R5 | Which volume cap does the Windows volume control map to (the 0 to 100 % scale into dB), and is there a hard ceiling? | `surfaceapoextension`, `surfaceihvaudiofilterdriver`, `surface_audiominiext8380` |
| R6 | What does Windows send to the ADSP before the audio PD answers (GPR service open, `SPF` boot, calibration load)? Compare with Linux `APM_CMD_GET_SPF_STATE` | `qcaudminiport8380.sys`, `qcadcm8380.sys`, `qcslimbus8380` |
| R7 | GPR domain, service and port numbering in the Windows build; does the APM service id differ from Linux `GPR_DOMAIN_ID_ADSP` 2 and `APM` 1? | `qcadcm8380.sys` and ADSP-side config under `surfacepro_ext_adsp8380` |
| R8 | Microphone data: how many microphones, DMIC lines, sample rate and clock divider (`DMIC0_CTL`), channel order, and which APO (voice clarity) runs in the capture path | `qcasd8380.sys`, `qcasd_apo8380`, `voiceclarityep_audio_component`, `mep_audio_component`, `live-inventory/audio` |
| R9 | WSA8845 reset GPIO, SoundWire port map and amplifier mode (speaker versus receiver) as Windows sets them | `qcadcm8380.sys`, ACPI `ADCM` and `AUCD` devices in `live-inventory/acpi` |

Answer R6 and R7 first: without an answering SPF, no audio test is possible. R1 to R5 gate path P.

## 10. Hand-off

Requests (written in the dossiers): kernel (build the three patches and the two variants, relax the DTB safety check as in section 3), image (menu entry for `m11-audio`, topology and overlay install, collector reload for H1), firmware (topology install path), dsp-subsystems (SPF timeout, with H1 to H4), and the orchestrator (S1 decision and the audio-mics and audio-speakers statuses).
