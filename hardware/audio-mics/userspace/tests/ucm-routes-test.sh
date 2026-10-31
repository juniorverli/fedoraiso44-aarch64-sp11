#!/bin/sh
# Offline test of the SP11 audio route layer in a Fedora 44 container (alsa-ucm + alsa-ucm-utils from Fedora).
# Usage: docker run --rm -v <repo>/hardware:/hw:ro registry.fedoraproject.org/fedora:44 sh /hw/audio-mics/userspace/tests/ucm-routes-test.sh
# A virtual card has no controls, so in the copies under test: ControlExists becomes a string compare (true or
# false), ${CardId} becomes a literal, and every cset becomes an exec that appends "control=value" to a log. The
# log shows what a real card would get and in which order. Nothing here touches a sound device.
set -u
dnf -y -q install alsa-ucm alsa-ucm-utils >/dev/null 2>&1
M=/hw/audio-mics/userspace
SP=/hw/audio-speakers/userspace
S=$SP/overlay/usr/share/alsa/ucm2/Qualcomm/x1e80100
SS=$SP/overlay-speakers/usr/share/alsa/ucm2/Qualcomm/x1e80100
LOG=/tmp/ucm-order.log
W=/work
CARD=X1E80100Microso
fail=0
pass() { echo "PASS: $1"; }
bad() { echo "FAIL: $1"; fail=1; }
yes_() { if grep -q -- "$1" "$2"; then pass "$3"; else bad "$3"; fi; }
eq_() { if [ "$1" = "$2" ]; then pass "$3"; else bad "$3 (got '$1', want '$2')"; fi; }
no_() { if grep -q -- "$1" "$2"; then bad "$3"; else pass "$3"; fi; }

# $1 tree, $2 speaker-owner dir with MICROSOFT-Surface-Pro-11.conf + Surface11-HiFi.conf, $3 jack condition: true|false
build() {
	rm -rf "$1"; mkdir -p "$1"; cp -a /usr/share/alsa/ucm2 "$1/ucm2"
	D=$1/ucm2/Qualcomm/x1e80100
	cp "$M/overlay-ucm-fix/usr/share/alsa/ucm2/Qualcomm/x1e80100/x1e80100.conf" "$D/"
	cp "$2"/*.conf "$D/"
	cp "$M"/overlay-audio-routes/usr/share/alsa/ucm2/Qualcomm/x1e80100/SP11-*.conf "$D/"
	mkdir -p "$1/ucm2/conf.virt.d"
	sed 's|^Define.DMI_info .*|Define.DMI_info "Microsoft Corporation-Surface-Microsoft Surface Pro, 11th Edition"|' \
		"$D/x1e80100.conf" > "$1/ucm2/conf.virt.d/sp11test.conf"
	sed 's|^Define.DMI_info .*|Define.DMI_info "Microsoft Corporation-Surface-Surface Pro 12in 1st Ed with Snapdragon"|' \
		"$D/x1e80100.conf" > "$1/ucm2/conf.virt.d/sp12test.conf"
	sed -i "s/\\\${CardId}/$CARD/g" "$D"/*.conf
	if [ "$3" = true ]; then s2=x; else s2=y; fi
	sed -i "s/Type ControlExists/Type String/; s|^\\(\\t*\\)Control \"iface=CARD,name=.*|\\1String1 \"x\"\\n\\1String2 \"$s2\"|" "$D/SP11-Routes.conf"
	for f in "$D"/SP11-MicGain.conf "$D"/SP11-DP*.conf "$D"/Surface11-HiFi.conf "$1"/ucm2/codecs/qcom-lpass/*/*.conf "$1"/ucm2/codecs/wsa884x/*/*.conf \
		"$D"/Surface11-SpeakerSeq.conf "$D"/Surface11-WsaInit.conf; do
		[ -f "$f" ] && sed -i "s|cset \"name='\\([^']*\\)' \\([^\"]*\\)\"|exec \"/bin/sh -c 'echo \\1=\\2 >> $LOG'\"|" "$f"
	done
	return 0
}
devs() { ALSA_CONFIG_UCM2=$1/ucm2 alsaucm -c "$2" list _devices/HiFi 2>/dev/null; }
getv() { ALSA_CONFIG_UCM2=$1/ucm2 alsaucm -c sp11test get "$2" 2>/dev/null | sed 's/^[^=]*=//; s/^_ucm[0-9]*\.//'; }
ucm_enable() { rm -f $LOG; ALSA_CONFIG_UCM2=$1/ucm2 alsaucm -c sp11test set _verb HiFi set _enadev "$2" >/dev/null 2>&1; cat $LOG 2>/dev/null; }

echo "=== A. default profile (microphones only), DP jack controls absent"
build $W/a $S false
devs $W/a sp11test | tee /tmp/dev-a
yes_ ' Mic$' /tmp/dev-a "A: Mic offered"
no_ 'HDMI' /tmp/dev-a "A: no DP device without DP jack controls"
no_ 'Speaker' /tmp/dev-a "A: no speaker device (S1)"
echo "-- 12in negative control"
devs $W/a sp12test | tee /tmp/dev-12
yes_ 'Speaker' /tmp/dev-12 "A: 12in keeps Fedora's Speaker profile"
no_ 'HDMI' /tmp/dev-12 "A: 12in gets no SP11 route layer"

echo "=== B. default profile, DP jack controls present"
build $W/b $S true
devs $W/b sp11test | tee /tmp/dev-b
yes_ ' Mic$' /tmp/dev-b "B: Mic offered"
yes_ 'HDMI0' /tmp/dev-b "B: HDMI0 offered"
yes_ 'HDMI1' /tmp/dev-b "B: HDMI1 offered"
no_ 'Speaker' /tmp/dev-b "B: no speaker device (S1)"
eq_ "$(getv $W/b PlaybackPCM/HDMI0/HiFi)" "hw:$CARD,2" "B: HDMI0 PCM hw:card,2"
eq_ "$(getv $W/b PlaybackPCM/HDMI1/HiFi)" "hw:$CARD,3" "B: HDMI1 PCM hw:card,3"
eq_ "$(getv $W/b JackControl/HDMI0/HiFi)" "DP0 Jack" "B: HDMI0 jack"
eq_ "$(getv $W/b JackControl/HDMI1/HiFi)" "DP1 Jack" "B: HDMI1 jack"
eq_ "$(getv $W/b PlaybackPriority/HDMI0/HiFi)" "200" "B: HDMI0 priority 200"
eq_ "$(getv $W/b CapturePCM/Mic/HiFi)" "hw:$CARD,1" "B: Mic PCM hw:card,1"
echo "-- Mic enable sequence (in order):"; ucm_enable $W/b Mic | tee /tmp/mic-log
eq_ "$(grep 'VA_DEC0 Volume' /tmp/mic-log | tail -1)" "VA_DEC0 Volume=98" "B: last VA_DEC0 Volume is 98 (+14 dB)"
eq_ "$(grep 'VA_DEC1 Volume' /tmp/mic-log | tail -1)" "VA_DEC1 Volume=98" "B: last VA_DEC1 Volume is 98 (+14 dB)"
yes_ "^VA_DEC0 Volume=100$" /tmp/mic-log "B: base profile still writes 100 first (our 98 overrides it)"
echo "-- DP enable sequences:"; ucm_enable $W/b HDMI0 | tee /tmp/dp-log; ucm_enable $W/b HDMI1 | tee -a /tmp/dp-log
yes_ "^DISPLAY_PORT_RX_0 Audio Mixer MultiMedia3=1$" /tmp/dp-log "B: DP0 route MultiMedia3"
yes_ "^DISPLAY_PORT_RX_1 Audio Mixer MultiMedia4=1$" /tmp/dp-log "B: DP1 route MultiMedia4"
no_ 'WSA\|Spkr\|PA Volume\|RX_CODEC\|MultiMedia1' /tmp/dp-log "B: DP enable touches no speaker control (S1)"

echo "=== C. gated speaker profile (overlay-speakers) keeps working under the route layer"
build $W/c $SS true
devs $W/c sp11test | tee /tmp/dev-c
yes_ 'Speaker' /tmp/dev-c "C: Speaker still offered in the speaker entry"
yes_ ' Mic$' /tmp/dev-c "C: Mic offered"
yes_ 'HDMI0' /tmp/dev-c "C: HDMI0 offered"
ucm_enable $W/c Mic > /tmp/mic-c; echo "-- C Mic log:"; cat /tmp/mic-c
eq_ "$(grep 'VA_DEC0 Volume' /tmp/mic-c | tail -1)" "VA_DEC0 Volume=98" "C: Mic gain 98"

if [ "$fail" = 0 ]; then echo "ALL PASS"; else echo "FAILURES"; exit 1; fi
