# audio-mics test plan

Entry `SP11 audio, microphones` (DTB `m11-audio`); speakers are off by construction (S1).

1. `ls /sys/bus/soundwire/devices`: absent or empty. `cat /proc/asound/cards`: `X1E80100-Microsoft-Surface-Pro-11`.
2. `dmesg | grep -E 'tplg|q6apm|CMD timeout'`: topology loaded, no SPF timeout.
3. `arecord -D hw:0,1 -f S16_LE -r 48000 -c 2 -d 5 /tmp/mic2.wav`, then `-c 1`; `sox /tmp/mic2.wav -n stats` shows level, both channels non-silent.
4. Tap or speak near the left then the right edge while recording; note which channel moves (channel order).
5. `wpctl status` lists a source; GNOME Settings input shows level.
6. Record 10 s of speech; the result is intelligible, no distortion (a /2 clock divider would distort, see the dossier).
