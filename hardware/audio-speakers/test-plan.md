# audio-speakers test plan

**Current rev20 procedure:** [PA regression evidence](evidence/2026-11-02-pa-gain-regression.md) supersedes conflicting historical steps below. Rev19 logs confirm D26 open-loop and late-probe caps; the revised UCM, actual startup mute, effective digital gain and microphone signal still require validation. D26 is an operator-authorised open-loop exception, not closed-loop thermal/excursion protection. Keep a speaker-off fallback. Any audible test requires the operator present.

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

