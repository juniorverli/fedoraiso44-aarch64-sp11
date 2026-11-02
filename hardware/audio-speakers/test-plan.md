# audio-speakers test plan

**D28 current test and prerequisites:** [public audio evidence](evidence/2026-11-02-d28-public-audio.md) supersedes historical default-path instructions below. Patch 0022 implements the requested open-loop guard but is not integrated or built. The public entry must boot software-muted with an enforced -12 dBFS ceiling and hardware PA/RX/MIX caps; the separate fallback keeps speakers off. No kernel/ISO build or device test has been run. Any audible test requires the operator present.

The public graph has no closed-loop thermal/excursion protection; D26 accepts only muted-by-default, capped open-loop use. First validate the device while muted. All commands are read-only unless stated.

## T0, every boot (S1 off)

1. `cat /proc/asound/cards` on the default entry: "no soundcards". `ls /sys/bus/soundwire/devices`: no such directory.
2. `dmesg | grep -E 'CMD timeout|q6apm|tplg'`: record whether `GET_SPF_STATE` (`1001021`) still times out.
3. H1: `sudo modprobe -r snd_q6apm_dai snd_q6apm_lpass_dais q6prm_clocks q6prm snd_q6apm; sudo modprobe snd_q6apm; dmesg | tail -20`. An answer (no timeout) means a timing problem. Speakers cannot start: `/sound` is disabled.

## T1, entry `SP11 audio, microphones` (S1 off)

1. `ls /sys/bus/soundwire/devices` must not exist or be empty. `dmesg | grep -i wsa884`: no `wsa884x` probe.
2. `cat /proc/asound/cards`: card `X1E80100-Microsoft-Surface-Pro-11`. `dmesg | grep tplg`: topology loaded, no error.
3. Expect `aplay -l` to list no WSA device; playback is not part of this stage.
4. `amixer -c 0 contents | grep -i 'PA Volume'` must print nothing.

## T2, speaker variant, silent bring-up (only after S1 changes)

1. Both `sdw20217020400` devices enumerate; `wsa884x` probes without error; `cat /sys/class/hwmon/*/temp1_input` plausible.
2. `amixer -c 0 cget name='SpkrLeft PA Volume'` shows `max=6`; same for Right. `WSA WSA_RX0 Digital Volume`, `WSA_RX1`, and the two `_MIX` controls show `max=81`. `amixer -c 0 cset name='SpkrLeft PA Volume' 7` must fail.
3. Force a SoundWire re-attach (runtime suspend then resume of the card, or a stream start after 10 s idle) and read `PA Volume` again: at most 6 (patch 0001).
4. Before any sound: UCM verb enable leaves `PA Volume` 0.

## T2c, D28 muted public-entry test (after patch and image integration)

1. Verify model `X1E80100-Microsoft-Surface-Pro-11`, marker `d26-open-loop-v1`, public topology filename/hash, and guard mode `open-loop`; parsed graph has no SP module.
2. Before opening audio, confirm the software sink is muted and its enforced maximum is -12 dBFS. Read PA (max 6), WSA RX digital and RX MIX caps (max 81); confirm cap readiness in guard debugfs.
3. Open and prepare/start the speaker PCM while the sink remains muted. Expect success without `-22`; `sp11_guard_check` admits the stream, and the unmute gate reports open-loop allowed without VI/CPS, calibration, SP enable or diagnostics prerequisites. Confirm no SP diagnostics registration request or unsupported response and verify silence at both speakers throughout.
4. Capture journal timestamps, guard state before and after, active UCM verb/device, PCM, sink mute/volume and all hardware mixer values. Fail if any cap is missing, mode is unknown/refused, a diagnostic event is attempted, or sound is audible. Do not unmute during this test.

## T3, first sound (only with the operator present)

Lowest step, short tones, stop on distortion or warmth. Log `hwmon` temperature before, during, after. Acceptance items 1 to 3 of the dossier apply.

## T2b, M13 gated speaker variant (D26)

Entry `m13-spk`, no volume, nothing playing. Expect: card registers, both WSA8845 enumerate, no `CMD timeout for [1001021]`, `aplay -D hw:0,0` fails with `Operation not supported` (gate, patch 0009), microphones record. Power off at once if any playback starts. Details: `evidence/2026-10-30-d26-audio.md` section 7. T3 stays blocked until the closed-loop protection (evidence section 8.4, stages 2 to 5) is validated.

## T4, closed-loop speaker protection (first hardware test, operator present)

Procedure, what to read and what to collect: `evidence/2026-10-30-closed-loop.md` section 8. Order: A silent bring-up (guard shows `open_allowed: yes` and `allowed: no`; with the V/I capture not running `aplay` may open the stream but the amplifier stays muted and the log says `speaker stays muted`; without the closed-loop file `aplay` fails), B V/I stream data, C calibration at the minimum volume (`sp11.allow_nominal=1` only for this test), D one quiet tone. Kill switch: boot the entry with `sp11.nospk`. Stop on any fault line, distortion or heat. T3 above stays blocked until A to D pass and the orchestrator reads the evidence.

Checks that need no sound: `cat /sys/kernel/debug/sp11/guard` (reason text changes as inputs arrive); `dmesg | grep -E 'sp11|speaker protection|amplifier interrupt'`; with `sp11.nospk` the same `aplay` must fail with `Operation not supported` and the guard must say `nospk: 1`; with the calibration file removed the amplifier must stay muted ("no R0/T0 calibration was applied" in the `speaker stays muted` line). Order of a real playback (flash review 2026-10-31): open the V/I capture first and keep it open, then `aplay`; the amplifier unmutes at the start of the stream, not at open. Closing the V/I capture while playing must mute the speakers; pause and resume must not unmute after a fault.

