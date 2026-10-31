# audio-mics test plan

Entry `SP11 audio, microphones` (DTB `m11-audio`); speakers are off by construction (S1).

1. `ls /sys/bus/soundwire/devices`: absent or empty. `cat /proc/asound/cards`: `X1E80100-Microsoft-Surface-Pro-11`.
2. `dmesg | grep -E 'tplg|q6apm|CMD timeout'`: topology loaded, no SPF timeout.
3. `arecord -D hw:0,1 -f S16_LE -r 48000 -c 2 -d 5 /tmp/mic2.wav`, then `-c 1`; `sox /tmp/mic2.wav -n stats` shows level, both channels non-silent.
4. Tap or speak near the left then the right edge while recording; note which channel moves (channel order).
5. `wpctl status` lists a source; GNOME Settings input shows level.
6. Record 10 s of speech; the result is intelligible, no distortion (a /2 clock divider would distort, see the dossier).

## Audio routes (2026-10-31, `evidence/2026-10-31-audio-routes.md`)

Read-only first: `extra-audio-routes.txt` from the log collector holds the verbs, devices, jack controls and PipeWire state.

7. `alsaucm -c hw:0 list _devices/HiFi`: `Mic`; `HDMI0` and `HDMI1` only on a DTB with the DP dai links.
8. Capture gain: `amixer -c 0 cget name='VA_DEC0 Volume'` reads 98 (+14 dB) after the microphone opens (UCM enable), never above 108. Record speech at 30 cm: peak around -12 to -6 dBFS.
9. Default capture is the built-in microphones; `pactl get-default-source` shows `alsa_input.platform-sound.*`.
10. With a DP monitor (DTB with links): `amixer -c 0 cget iface=CARD,name='DP0 Jack'` on, `wpctl status` lists a sink, it becomes the default; play at the minimum level (`aplay -D hw:0,2`). Unplug: the sink disappears.
11. USB headset: becomes the default sink, the built-in microphones stay the default source.
12. Bluetooth headset (after pairing, `bluetooth` component): A2DP sink becomes the default; select its input to get HFP mSBC.
13. Offline, before any boot: `docker run --rm -v <repo>/hardware:/hw:ro registry.fedoraproject.org/fedora:44 sh /hw/audio-mics/userspace/tests/ucm-routes-test.sh`, and `sh hardware/audio-mics/userspace/tests/mic-gain-check.sh`.

