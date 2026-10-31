#!/bin/sh
# Parse test for the SP11 microphone UCM in a Fedora 44 container (alsa-ucm + alsa-utils from Fedora).
# Usage: docker run --rm -v <repo>/hardware:/hw:ro registry.fedoraproject.org/fedora:44 sh /hw/audio-mics/userspace/tests/ucm-syntax-test.sh
set -eu
dnf -y -q install alsa-ucm alsa-ucm-utils >/dev/null 2>&1
W=/work; mkdir -p $W; cp -a /usr/share/alsa/ucm2 $W/ucm2
O=/hw/audio-mics/userspace/overlay-ucm-fix/usr/share/alsa/ucm2/Qualcomm/x1e80100
S=/hw/audio-speakers/userspace/overlay/usr/share/alsa/ucm2/Qualcomm/x1e80100
cp $O/x1e80100.conf $W/ucm2/Qualcomm/x1e80100/
cp $S/MICROSOFT-Surface-Pro-11.conf $W/ucm2/Qualcomm/x1e80100/
# a virtual card has no CardId: test with a literal card id (the real card id is X1E80100Microso)
sed 's/\${CardId}/X1E80100Microso/g' $S/Surface11-HiFi.conf > $W/ucm2/Qualcomm/x1e80100/Surface11-HiFi.conf
# virtual card: the driver file with DMI_info replaced by the SP11 string, to run the real If.SURFACEPro11 regex
mkdir -p $W/ucm2/conf.virt.d
sed 's|^Define.DMI_info .*|Define.DMI_info "Microsoft Corporation-Surface-Microsoft Surface Pro, 11th Edition"|' $O/x1e80100.conf > $W/ucm2/conf.virt.d/sp11test.conf
# negative control: a Surface Pro 12in string must not select the SP11 profile
sed 's|^Define.DMI_info .*|Define.DMI_info "Microsoft Corporation-Surface-Surface Pro 12in 1st Ed with Snapdragon"|' $O/x1e80100.conf > $W/ucm2/conf.virt.d/sp12test.conf
export ALSA_CONFIG_UCM2=$W/ucm2
echo "== sp11test verbs";   alsaucm -c sp11test list _verbs
echo "== sp11test devices"; alsaucm -c sp11test list _devices/HiFi
echo "== sp11test dump";    alsaucm -c sp11test dump text 2>&1 | head -60
echo "== sp11test capture PCM"; alsaucm -c sp11test get CapturePCM/Mic/HiFi
echo "== sp12test (must be the 12in profile, not Mic-only)"; alsaucm -c sp12test list _devices/HiFi
