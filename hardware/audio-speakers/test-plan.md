# audio-speakers test plan

**Current rev20 procedure:** [PA regression evidence](evidence/2026-11-02-pa-gain-regression.md) supersedes conflicting historical steps below. Rev19 logs confirm D26 open-loop and late-probe caps; the revised UCM, actual startup mute, effective digital gain and microphone signal still require validation. D26 is an operator-authorised open-loop exception, not closed-loop thermal/excursion protection. Keep a speaker-off fallback. Any audible test requires the operator present.

## 2026-11-03: UCM, volume and fault timeline (current)

This supersedes the revision-20 instruction to write/test `Speakers Volume` in the Speaker cset sequence; retain that alias as the PipeWire playback mixer. The candidate removes only this cset and must first be integrated by the image owner. Keep D26 open-loop policy, caps and readiness, startup mute, first-test 5% marker, kill switch and speaker-off fallback. No independent proof of closed-loop protection is claimed. Do not create audible output for this investigation without the operator and all existing D26 gates; stop on an unexpected fault, repeated parity or distortion/heat. Do not reset a fault or change amplifier register masks.

1. On the already planned first-test boot, record boot ID, monotonic and wall time, command line, installed file hashes (including all four D28 UCM files and `x1e80100.conf`), kernel/topology hashes, six cap lines, and `cat /sys/kernel/debug/sp11/guard`. Require open-loop, `caps_ready: 1`, no fault, all caps and the fallback. Collect the complete system and user journal with monotonic timestamps and full error text from boot onwards; record user/session and command exit codes. Identify both amps and stream openers; do not claim that a list of available UCM devices is the active state.
2. In the active graphical user's environment, before opening any player, capture `wpctl status`, `wpctl inspect @DEFAULT_AUDIO_SINK@`, `wpctl get-volume @DEFAULT_AUDIO_SINK@`, `pw-dump`, active UCM verb/devices, and both `amixer -D hw:0 contents` and `amixer -c 0 contents`. Confirm helper/default-route mute, the 5% first-test setting, and that `hw:0` has the two PA controls but no userspace-only `Speakers Volume` alias. The remapped mixer should show the alias. Record exact PA L/R and alias, RX0/RX1 and both MIX values/maxima, digital mute, WSA mode, DAC/COMP/BOOST/PBR/VISENSE/CPS, WSA RX muxes and INP0, WSA_CODEC_DMA mixer and the active PCM. Take a monotonic timestamp immediately before each collection, and keep raw output and errors. Confirm expected RX/MIX cap <=81, PA <=6 and no out-of-range values. Do not equate PA value 0 with a software mute.
3. Obtain a **muted**, exclusive diagnostic of `alsaucm` and WirePlumber sequences, with a single UCM manager at a time: arrange a test session that keeps the sink muted and has no competing UCM user, player or PCM; instrument ALSA UCM logging or ioctl control tracing so each cset, target handle, return/errno, and PA state is recorded. With the original configuration, reproduce only if the already scheduled boot still uses it; do not reinstall it just to make a failure. Record verb `HiFi`, `_enadev Speaker` return and `_enadevs` from the same UCM manager, then before/after PA L/R, macro route and guard. Determine whether `name='Speakers Volume' 6` fails on `hw` after the physical PA writes or a different command fails. Stop on a fault or any missing mute/cap. Repeat on the candidate image, then disable/re-enable and reselect the verb while muted, and record return codes, actual active devices, both PA values (6 after enable, 0 after disable), alias, routes and guards each time. Test whether BootSequence or session management subsequently overwrites the physical PA values. WirePlumber should enable Speaker without the warning, and the selected sink should use the mapped mixer; otherwise retain logs and do not infer success. UCM operations modify controls: perform them only under the existing safety gates and restore the muted state after diagnostic handoff.
4. Before any sound, confirm the current default sink and stream software volumes, mutes, route, target node and the full hardware state above. Record these again **during** the same short known stereo signal and immediately after, with timestamp and `wpctl`/`pw-dump` stream values, app volume, stream peak if available, `/proc/asound/card0/pcm0p/sub*/status`, guard and journal. Begin at the specified 5% with the operator present after step 3 passes, then stop. Any subsequent controlled comparison of ordinary user sink/stream volume must stay within the existing D26 policy, use the same known signal and record each setting; do not change PA/RX/MIX caps, UCM 72, speaker mode or route as a loudness experiment. Preserve startup mute. Correlate the operator's observation with these times, and stop on a latch or repeated errors.
5. For the already scheduled end of session/reboot, record user command time, stream closure, UCM device transitions, guard state and a continuous `journalctl -b -o short-monotonic -f` through collector shutdown. Capture raw interrupt bytes, device, driver PA state, first latch, reboot request and WirePlumber/PipeWire shutdown times; also record runtime PM, clocks and regulator summaries at each feasible stage without forcing a resume or changing votes. The two debug boot `kmsg-live` streams previously ended near 61 s, so absence later is not evidence. Test separately in an idle interval before shutdown; do not deliberately force a fault or clear status. An interrupt during ordinary idle/active playback is materially different from one only during reboot. Classify status1 bit 1 only after an authoritative source or independent REA cross-check; maintain fail-closed behavior while unknown.

## Revision 20: muted safety and PA sequence

1. Use a clean safe boot with no camera application or stream; append `sp11.audio_first_test=1` for the first audible test. On the speaker-off fallback verify the WSA speaker path is disabled. On each speaker entry record boot ID, DTB, topology hash, mode and cap logs; require D26 open-loop, all six PA/RX/MIX cap successes and `speaker volume caps ready`, plus `caps_ready: 1`. No sound yet.
2. Verify global and per-device `device.routes.default-sink-volume = 0.0`. In the graphical session identify the built-in sink and use `wpctl get-volume` to verify the helper muted it and set 5% on the first-test boot; normal boots must be muted at 100%. The helper must mute before setting volume. WirePlumber 0.5.19 does not implement `api.acp.max-volume`; do not treat it as a ceiling.
3. Complete muted T2c before unmuting. Inspect UCM and `amixer -c 0`: PA max 6 (0 dB), both WSA RX and RX MIX maxima 81 (-3 dB), and UCM digital initialization 72 (-12 dB). Read left/right PA and stereo `Speakers Volume` after UCM enable, after verb re-selection, and after disable/enable: each must read 6; on disable they must read 0. Verify WsaInit BootSequence does not overwrite PA after enable; record failed csets and reattach behavior. Measure digital values and `wpctl`/`pw-dump` at 100% while muted: if digital rises from 72 to 81, require an implemented and verified real clamp before accepting the path. Fail any missing mute, cap, fallback or sequence gate.
4. With the operator present and T2c passed, unmute at 5%, play a short known stereo tone, check both channels and stop. Stop immediately on distortion or heat. Only after that test passes, boot normally, start from minimum and raise stepwise; record effective sink and hardware values and temperatures. This tests playback, not closed-loop SP/VI.

## Revision 20: post-session microphone evidence

Run in the active graphical user's environment, with a bounded wait for PipeWire/WirePlumber; record boot ID, timestamps and command failures. Avoid simultaneous applications using the capture device. Record `wpctl status`, `wpctl inspect @DEFAULT_AUDIO_SOURCE@`, `wpctl get-volume @DEFAULT_AUDIO_SOURCE@`, and `alsaucm -c hw:0 dump` (plus `alsaucm -c hw:0 get CaptureChannels/Mic/HiFi`). Confirm the default source resolves to the built-in microphone, is unmuted, and capture channels are 2. Record `amixer -c 0 contents`, including `MultiMedia2 Mixer VA_CODEC_DMA_TX_0`, `VA DEC0/1 MUX`, `VA DMIC MUX0/1`, `VA_AIF1_CAP Mixer DEC0/1`, and `VA_DEC0/1 Volume`; repeat while capture is active. Expected routes are VA_DMIC, DMIC0/DMIC1 and both AIF switches on. Record gains as found: snapshots show 100 while the staged gain layer requests 98; do not silently normalize the discrepancy.

With the operator speaking at a normal level, capture two seconds of stereo S16_LE at 48 kHz directly from `hw:0,1` and calculate each channel's RMS and peak; record exit status and contemporaneous kernel/user errors. A nonzero RMS in both channels correlated with speech is required, not merely a nonzero noise floor. Do not retain the speech sample in collected logs. Example, from a shell running as the graphical user:

```bash
sample=$(mktemp /tmp/sp11-mic-XXXXXX.wav)
trap 'rm -f "$sample"' EXIT
arecord -D hw:0,1 -f S16_LE -r 48000 -c 2 -d 2 "$sample" &
record_pid=$!
amixer -c 0 contents
wait "$record_pid"
record_status=$?
printf 'arecord exit=%s\n' "$record_status"
if [ "$record_status" -eq 0 ]; then
  python3 - "$sample" <<'PYRMS'
import math, struct, sys, wave
with wave.open(sys.argv[1], 'rb') as wav:
    assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (2, 2, 48000)
    data = wav.readframes(wav.getnframes())
samples = struct.unpack('<%dh' % (len(data) // 2), data)
for channel in range(2):
    values = samples[channel::2]
    if not values:
        raise SystemExit('empty capture')
    rms = math.sqrt(sum(x*x for x in values) / len(values)) / 32768
    peak = max(abs(x) for x in values) / 32768
    print(f'channel {channel}: RMS={rms:.8f}, peak={peak:.8f} (fraction of full scale)')
PYRMS
fi
rm -f "$sample"
trap - EXIT
```

Also test the selected PipeWire default source, e.g. `arecord -D pipewire -f S16_LE -r 48000 -c 2 -d 2` with the same metrics, and record its exit status. Direct ALSA success alone does not prove the default source works. Do not alter UCM until the collected state and capture isolate a fault.

## Historical procedures

The procedures below describe prior stages and do not override the current rev20 gates above.

## T0, historical speaker-off entry (S1 off)

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
4. Historical pre-rev20 expectation was PA 0; use the current rev20 enable/disable checks above.

## T2c, D28 muted public-entry test (after patch and image integration)

1. Verify model `X1E80100-Microsoft-Surface-Pro-11`, marker `d26-open-loop-v1`, public topology filename/hash, and guard mode `open-loop`; parsed graph has no SP module.
2. Before opening audio, confirm the software sink is muted and the applicable startup level and kernel caps match the current procedure. After codec binding/card late probe and before opening audio, confirm there are no `speaker volume cap failed` lines; require `speaker volume cap installed for <control>: 0` or `: 1` for each of the six required WSA RX/RX MIX and left/right PA controls, plus `speaker volume caps ready`. Read PA (max 6), WSA RX digital and RX MIX caps (max 81), and confirm `caps_ready: 1` in guard debugfs. Check optional WSA2 and Woofer/Tweeter success lines when those controls are present.
3. Open and prepare/start the speaker PCM while the sink remains muted. Expect successful muted prepare/start without `-22`; the PCM must not appear until late-probe cap installation has completed. `sp11_guard_check` admits the stream, while the amplifier remains muted until the user unmutes; the unmute gate then reports open-loop allowed without VI/CPS, calibration, SP enable or diagnostics prerequisites. Confirm no SP diagnostics registration request or unsupported response and verify silence at both speakers while muted.
4. Capture journal timestamps, guard state before and after, active UCM verb/device, PCM, sink mute/volume and all hardware mixer values. Fail if any cap is missing, mode is unknown/refused, a diagnostic event is attempted, or sound is audible. Do not unmute during this test.

## T3, first sound (only with the operator present)

After T2c proves muted prepare with `caps_ready: 1` and all caps present, unmute deliberately and play a short, low-level tone. Confirm both speakers are audible at the 5% first-test level within the hardware caps, then stop. Stop immediately on distortion or warmth. Log `hwmon` temperature before, during and after. Acceptance items 1 to 3 of the dossier apply.

## T2b, M13 gated speaker variant (D26)

Entry `m13-spk`, no volume, nothing playing. Expect: card registers, both WSA8845 enumerate, no `CMD timeout for [1001021]`, `aplay -D hw:0,0` fails with `Operation not supported` (gate, patch 0009), microphones record. Power off at once if any playback starts. Details: `evidence/2026-10-30-d26-audio.md` section 7. T3 stays blocked until the closed-loop protection (evidence section 8.4, stages 2 to 5) is validated.

## T4, closed-loop speaker protection (first hardware test, operator present)

Procedure, what to read and what to collect: `evidence/2026-10-30-closed-loop.md` section 8. Order: A silent bring-up (guard shows `open_allowed: yes` and `allowed: no`; with the V/I capture not running `aplay` may open the stream but the amplifier stays muted and the log says `speaker stays muted`; without the closed-loop file `aplay` fails), B V/I stream data, C calibration at the minimum volume (`sp11.allow_nominal=1` only for this test), D one quiet tone. Kill switch: boot the entry with `sp11.nospk`. Stop on any fault line, distortion or heat. T3 above stays blocked until A to D pass and the orchestrator reads the evidence.

Checks that need no sound: `cat /sys/kernel/debug/sp11/guard` (reason text changes as inputs arrive); `dmesg | grep -E 'sp11|speaker protection|amplifier interrupt'`; with `sp11.nospk` the same `aplay` must fail with `Operation not supported` and the guard must say `nospk: 1`; with the calibration file removed the amplifier must stay muted ("no R0/T0 calibration was applied" in the `speaker stays muted` line). Order of a real playback (flash review 2026-10-31): open the V/I capture first and keep it open, then `aplay`; the amplifier unmutes at the start of the stream, not at open. Closing the V/I capture while playing must mute the speakers; pause and resume must not unmute after a fault.

