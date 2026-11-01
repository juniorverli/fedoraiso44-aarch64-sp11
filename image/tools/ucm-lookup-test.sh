#!/usr/bin/env bash
# alsaucm lookup test on the UCM files of an image root, with alsaucm from Fedora (audio-mics userspace/tests/ucm-syntax-test.sh, adapted):
# the driver file with the Surface Pro 11 DMI string must list the verb HiFi and the device Mic with a capture PCM; the 12in string must not.
# List/get only: no verb is set, no mixer is written.   ucm-lookup-test.sh ROOT WORKDIR
set -eu
R=${1:?root} W=${2:?work}
command -v alsaucm >/dev/null 2>&1 || dnf -y -q install alsa-ucm-utils >/dev/null 2>&1
rm -rf "$W"; mkdir -p "$W"
cp -a "$R/usr/share/alsa/ucm2" "$W/ucm2"
O=$W/ucm2/Qualcomm/x1e80100
# The DP route layer gates its two DisplayPort devices on card controls ("DP0 Jack"/"DP1 Jack",
# Type ControlExists). alsaucm has no sound card here, so it cannot resolve a control device and
# aborts the whole verb parse ("cannot determine control device" then "failed to import ... -22"),
# hiding the Mic/HiFi lookup this test is about. Drop only those two If blocks from the COPY; the
# shipped UCM files are not touched and the DP outputs are covered by the ucm-routes-test.
python3 -I - "$O/SP11-Routes.conf" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path).read()
for name in ('sp11dp0', 'sp11dp1'):
    while True:
        m = re.search(r'^[ \t]*If\.' + re.escape(name) + r'\s*\{', text, re.M)
        if not m:
            break
        start, depth, i = m.start(), 0, m.end() - 1
        while i < len(text):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        text = text[:start] + text[i + 1:]
open(path, 'w').write(text)
PY
# a virtual card has no CardId: substitute the real card id literally (X1E80100Microso)
sed -i 's/\${CardId}/X1E80100Microso/g' "$O/Surface11-HiFi.conf"
mkdir -p "$W/ucm2/conf.virt.d"
sed 's|^Define.DMI_info .*|Define.DMI_info "Microsoft Corporation-Surface-Microsoft Surface Pro, 11th Edition"|' "$O/x1e80100.conf" >"$W/ucm2/conf.virt.d/sp11test.conf"
sed 's|^Define.DMI_info .*|Define.DMI_info "Microsoft Corporation-Surface-Surface Pro 12in 1st Ed with Snapdragon"|' "$O/x1e80100.conf" >"$W/ucm2/conf.virt.d/sp12test.conf"
export ALSA_CONFIG_UCM2=$W/ucm2
alsaucm -c sp11test list _verbs 2>&1 | grep -q 'HiFi' || { echo "FAIL: no HiFi verb for the Surface Pro 11 string"; exit 1; }
alsaucm -c sp11test list _devices/HiFi 2>&1 | grep -q 'Mic' || { echo "FAIL: no Mic device"; exit 1; }
alsaucm -c sp11test get CapturePCM/Mic/HiFi 2>&1 | grep -q 'hw:X1E80100Microso,1' || { echo "FAIL: capture PCM is not hw:<card>,1"; exit 1; }
if alsaucm -c sp12test list _devices/HiFi 2>&1 | grep -q '^ *[0-9]*: Mic$' && ! alsaucm -c sp12test list _devices/HiFi 2>&1 | grep -q Speaker; then
	echo "FAIL: the 12in string selected the Mic-only SP11 profile"; exit 1
fi
echo "PASS ucm lookup"
