# Audio routes collector drop-in (audio-mics, 2026-10-31). Sourced by /usr/libexec/sp11-log-collector in a subshell;
# the output becomes extra-audio-routes.txt. Read only: no mixer write, no playback, no capture, no verb enable
# (alsaucm "list" and "get" never run a sequence), no pairing. Privacy: Bluetooth addresses and USB serial numbers
# are masked; the card long name (unit specific) is never printed; no user name, no host name.
mask() {
	sed -E \
		-e 's/([0-9A-Fa-f]{2})([:_-])([0-9A-Fa-f]{2})\2([0-9A-Fa-f]{2})\2([0-9A-Fa-f]{2})\2([0-9A-Fa-f]{2})\2([0-9A-Fa-f]{2})/xx\2xx\2xx\2xx\2xx\2xx/g' \
		-e 's/usb-[A-Za-z0-9_.+-]+/usb-<masked>/g' \
		-e 's/(serial|Serial|SERIAL)[^,;]*/\1 <masked>/g'
}
card=$(sed -n 's/^ *\([0-9][0-9]*\) \[X1E80100Microso.*/\1/p' /proc/asound/cards 2>/dev/null | head -n 1)
card=${card:-0}
echo "## card index: $card"
echo
echo "## aplay -l (playback devices)"
timeout 8 aplay -l 2>&1 | mask
echo
echo "## arecord -l (capture devices)"
timeout 8 arecord -l 2>&1 | mask
echo
echo "## UCM (list only)"
echo "-- verbs"
timeout 8 alsaucm -c "hw:$card" list _verbs 2>&1 | head -n 10
echo "-- devices of HiFi"
timeout 8 alsaucm -c "hw:$card" list _devices/HiFi 2>&1 | head -n 20
for dev in Mic HDMI0 HDMI1; do
	echo "-- $dev"
	for k in CapturePCM PlaybackPCM PlaybackPriority CapturePriority JackControl; do
		timeout 5 alsaucm -c "hw:$card" get "$k/$dev/HiFi" 2>/dev/null
	done
done
echo
echo "## DisplayPort and capture controls (cget, read only)"
for c in "iface=CARD,name='DP0 Jack'" "iface=CARD,name='DP1 Jack'" \
	"name='DISPLAY_PORT_RX_0 Audio Mixer MultiMedia3'" "name='DISPLAY_PORT_RX_1 Audio Mixer MultiMedia4'" \
	"name='VA_DEC0 Volume'" "name='VA_DEC1 Volume'" "name='MultiMedia2 Mixer VA_CODEC_DMA_TX_0'"; do
	echo "-- $c"
	timeout 5 amixer -c "$card" cget "$c" 2>&1 | head -n 6
done
echo
echo "## DRM audio-capable connectors (EDID audio is not read here, only the connector state)"
for s in /sys/class/drm/card*-DP-*/status; do
	[ -r "$s" ] && echo "$(basename "$(dirname "$s")"): $(cat "$s")"
done
echo
echo "## Bluetooth audio stack (names and versions only, no addresses)"
echo "services: bluetooth=$(systemctl is-active bluetooth 2>&1) pipewire=$(systemctl --global is-enabled pipewire.socket 2>&1 | head -n 1)"
rpm -q pipewire pipewire-libs wireplumber bluez libsbc fdk-aac-free liblc3 libldac alsa-ucm alsa-ucm-utils 2>&1
echo "spa bluez5 codec plugins:"
find /usr/lib64/spa-0.2/bluez5 -name 'libspa-*.so' -printf '%f\n' 2>&1 | sed 's/^libspa-//; s/\.so$//' | sort
echo
echo "## PipeWire and WirePlumber as the logged-in user (if a session exists)"
uid=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$3 != "root" {print $2; exit}')
user=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$3 != "root" {print $3; exit}')
if [ -n "$uid" ] && [ -n "$user" ] && command -v wpctl >/dev/null 2>&1; then
	ru() { timeout 15 runuser -u "$user" -- env XDG_RUNTIME_DIR="/run/user/$uid" "$@" 2>&1; }
	echo "-- wpctl status"
	ru wpctl status | mask | head -n 80
	echo "-- pactl list short sinks"
	ru pactl list short sinks | mask
	echo "-- pactl list short sources"
	ru pactl list short sources | mask
	echo "-- pactl get-default-sink / get-default-source"
	ru pactl get-default-sink | mask
	ru pactl get-default-source | mask
	echo "-- default source and sink volume"
	ru wpctl get-volume @DEFAULT_AUDIO_SOURCE@
	ru wpctl get-volume @DEFAULT_AUDIO_SINK@
	echo "-- priority.session of the audio nodes (policy check)"
	ru pw-dump | awk '
		/"node.name"/ { gsub(/[",]/, ""); name = $2 }
		/"priority.session"/ { gsub(/[",]/, ""); print name, "priority.session=" $2 }' | mask
else
	echo "(no user session yet, or wpctl missing: PipeWire state not collected at this snapshot)"
fi
true
