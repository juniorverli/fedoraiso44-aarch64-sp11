#!/usr/bin/env bash
# Container side of the kiwi ISO build (decision D16). Run by scripts/image-build.sh, not directly.
#
# Fedora's own description (pagure.io/fedora-kiwi-descriptions, branch f44, commit pinned in
# image/kiwi/DESCRIPTION_COMMIT), profile Workstation-Live, built the way Fedora's CI builds it:
# the repository's own `kiwi-build` wrapper (tmt/tests/build-image.fmf), which calls
#   kiwi-ng --type=iso --profile=Workstation-Live --kiwi-file=Fedora.kiwi system build \
#           --description DIR --target-dir DIR-build  <ISO volid/application id from Fedora's generator>
# On top of it only the SP11 layer of image/README.md ("kiwi layer"):
#   image/kiwi/patches/*.patch   two patches of Fedora files (include our layer, verbose cmdline)
#   image/kiwi/overlay/          sp11.xml, GRUB template, root files (dracut, SELinux, collector conf)
#   image/overlay/               log collector and its unit (shared with the lmc build)
#   out/firmware-root            DriverStore firmware, copied into the root overlay
#   out/rpms -> out/repo         our kernel RPMs, local repository with priority over Fedora's
set -euo pipefail

OUT=${SP11_OUT:-/out}
REPO=/sp11
name_arg= post_only= smoke=0 private=0
while [ $# -gt 0 ]; do
	case $1 in
	--post-only) post_only=${2:?build id}; shift ;;   # redo steps 6b-9 of a finished kiwi run
	--private) private=1 ;;   # operator-only build: stage from out/private-stage (image/README.md)
	--smoke) smoke=1 ;;   # D19: a missing DTB variant is replaced by a copy of the packaged DTB (pipeline test only)
	*) name_arg=$1 ;;
	esac
	shift
done

id=${post_only:-$(date -u +%Y%m%dT%H%M%SZ)}
kind=kiwi; [ "$smoke" = 1 ] && kind=kiwi-smoke
name=${name_arg:-sp11-fedora44-aarch64-$kind-$id}
if [ "$private" = 1 ]; then
	case $name in *-private*) ;; *) name=$name-private ;; esac
fi
work=$OUT/image-work/$id
isodir=$OUT/iso
log() { echo "image-build[kiwi]: $*" >&2; }
if [ "$smoke" = 0 ]; then
	validation=$OUT/image-inputs/audio/d28-runtime-validation.json
	if [ "$private" = 1 ]; then
		[ -s "$validation" ] && python3 -I /sp11/image/tools/check-d28-build-gate.py "$validation" private >/dev/null || {
			log "REFUSED: private D28 build requires pinned source_commit and topology_sha256 in $validation"; exit 6;
		}
		log "PRIVATE OPERATOR-ONLY: D28 runtime safety is unvalidated; this ISO must never be shared"
	else
	[ -s "$validation" ] && python3 -I /sp11/image/tools/check-d28-build-gate.py "$validation" public >/dev/null || {
		log "REFUSED: D28 runtime safety evidence missing/incomplete at $validation (image build remains gated)"; exit 6;
	}
	fi
fi
mkdir -p "$work/tmp" "$isodir" "$OUT/kiwi"
cd "$work"   # /sp11 is a worktree whose .git file points outside the container
# private mode: whatever happens, the staged values and the copies in the work tree are removed
scrub_private() {
	rm -rf "$OUT/private-stage"
	rm -f "$work/description/root/etc/sp11/bt-address" "$work/description/root/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf" \
		"$work/description/root/etc/systemd/network/10-sp11-wifi.link" \
		"$work/description/root/usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin" \
		"$work/description/root/usr/lib/firmware/updates/"*.bin "$work/description/root/etc/dracut.conf.d/93-sp11-cdsp46.conf" \
		"$work/description/root/usr/lib/firmware/qcom/x1e80100/"*-sp11c*.bin "$work/description/root/usr/lib/firmware/qcom/x1e80100/"*-tplg.bin
	rm -rf "$work/description/root/usr/lib/firmware-sp11-cdsp46" "$work/description/root/usr/share/qcom" "$work/description/root/usr/libexec/sp11/sp11-npu-install-private"
	rm -rf "$work/description/root/var/lib/hexagonrpcd/registry" "$work/description/root/usr/share/sp11/pipewire-gated" "$work/description/root/usr/share/licenses/sp11-camera-icp"
	rm -f "$work/description/root/usr/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn" "$work/description/root/usr/share/libcamera/ipa/simple/"{ov13858,imx681}.yaml \
		"$work/description/root/etc/pipewire/pipewire.conf.d/"sp11-*.conf "$work/description/root/usr/lib/firmware/qcom/x1e80100/"*-sp11q*.bin
}
[ "$private" = 1 ] && trap scrub_private EXIT

# The local Fedora-native iptsd RPM must be prepared before the single compose.
iptsd_rpm=$OUT/rpms/iptsd-3.1.0-1.fc44.aarch64.rpm
iptsd_record=${iptsd_rpm%.rpm}.json
[ -s "$iptsd_rpm" ] && [ -s "$iptsd_record" ] &&
[ "$(sha256sum "$iptsd_rpm" | cut -d' ' -f1)" = "$(jq -r .rpm_sha256 "$iptsd_record")" ] &&
[ "$(sha256sum "$REPO/image/iptsd/iptsd.spec" | cut -d' ' -f1)" = "$(jq -r .local_spec_sha256 "$iptsd_record")" ] || {
	log "REFUSED: build the pinned Fedora-native iptsd RPM with scripts/image-build-iptsd.sh first"; exit 6;
}

if [ -z "$post_only" ]; then
# ---- 0. the kernel RPMs. Only the top level of out/rpms counts (older builds live in out/rpms/archive/):
# exactly one kernel NEVRA may sit there, and it must be newer than the last kernel that is known not
# to carry the M3 display patches (image/kiwi/MIN_KERNEL_EXCLUSIVE, D19). All five RPMs of the image
# come from that one build.
nevras=$(for f in "$OUT"/rpms/kernel*-[0-9]*.rpm; do
	[ -e "$f" ] || continue
	case $f in *.src.rpm) continue ;; esac
	rpm -qp --qf '%{version}-%{release}.%{arch}\n' "$f"
done | sort -u)
[ -n "$nevras" ] || { log "no kernel RPM in $OUT/rpms"; exit 1; }
if [ "$(echo "$nevras" | wc -l)" -gt 1 ]; then
	log "REFUSED: more than one kernel NEVRA at the top level of $OUT/rpms (older ones belong in $OUT/rpms/archive/):"
	echo "$nevras" | sed 's/^/    /' >&2
	exit 5
fi
kver_full=$nevras
kcore_src=$OUT/rpms/kernel-core-$kver_full.rpm
[ -f "$kcore_src" ] || { log "no kernel-core-$kver_full.rpm in $OUT/rpms"; exit 1; }
newest_vr=${kver_full%.*}
min=$(tr -d '[:space:]' <"$REPO/image/kiwi/MIN_KERNEL_EXCLUSIVE")
if [ "$(rpm --eval "%{lua:print(rpm.vercmp('$newest_vr', '$min'))}")" -le 0 ]; then
	log "REFUSED: kernel $newest_vr is not newer than $min; the M3 image needs the build with the display patches (D19)"
	exit 5
fi
log "kernel $kver_full (newer than $min, the only kernel NEVRA at the top level of out/rpms)"

# M15/M16 accepts revision-12..24 RPMs and all six atomically published DTB/JSON pairs (m15, m15-safe, m15-nosnd, m15-notouch, m15-spk, m15-spectra).
[ "$kver_full" = 7.3.0-65.sp11.24.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.23.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.22.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.21.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.20.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.19.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.18.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.17.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.16.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.15.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.14.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.13.fc44.aarch64 ] || [ "$kver_full" = 7.3.0-65.sp11.12.fc44.aarch64 ] || {
	log "REFUSED: M15/M16 requires kernel revision 12 through 21 (7.3.0-65.sp11.*.fc44.aarch64), found $kver_full"; exit 6;
}
patch_series_sha=$( . "$REPO/scripts/kernel-common.sh"; kernel_series_hash )
for v in m15 m15-safe m15-nosnd m15-notouch m15-spk m15-spectra; do
	vsrc=$OUT/dtb-variants/$kver_full/qcom/x1p64100-microsoft-denali-$v
	[ -s "$vsrc.dtb" ] && [ -s "$vsrc.json" ] || {
		log "REFUSED: $v DTB and JSON not yet published by the kernel worker"; exit 6;
	}
	[ "$(sha256sum "$vsrc.dtb" | cut -d' ' -f1)" = "$(jq -r .sha256 "$vsrc.json")" ] &&
	[ "$(jq -r .kver "$vsrc.json")" = "$kver_full" ] &&
	{ [ "$(jq -r .series_rev "$vsrc.json")" = 12 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 13 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 14 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 15 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 16 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 17 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 18 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 19 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 20 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 21 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 22 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 23 ] || [ "$(jq -r .series_rev "$vsrc.json")" = 24 ]; } &&
	[ "$(jq -r .series_hash_sha256 "$vsrc.json")" = "$patch_series_sha" ] || {
		log "REFUSED: $v DTB hash/release/series differs from the kernel worker JSON"; exit 6;
	}
	case $v in
		m15|m15-safe) expected_model=X1E80100-Microsoft-Surface-Pro-11 ;;
		m15-spk) expected_model=X1E80100-Microsoft-Surface-Pro-11-CL ;;
		*) expected_model= ;;
	esac
	if [ -n "$expected_model" ]; then
		actual_model=$(fdtget -t s "$vsrc.dtb" /sound model 2>/dev/null || true)
		[ "$actual_model" = "$expected_model" ] || {
			log "REFUSED: $v /sound model is '$actual_model', expected '$expected_model' (audio-speakers kernel patch 0022)"; exit 6;
		}
	fi
done

# ---- 1. Fedora's description at the pinned commit
pin=$(tr -d '[:space:]' <"$REPO/image/kiwi/DESCRIPTION_COMMIT")
src=$OUT/kiwi/fedora-kiwi-descriptions.git
url=https://pagure.io/fedora-kiwi-descriptions.git
head=$(git ls-remote "$url" refs/heads/f44 | cut -f1)
[ -n "$head" ] || { log "cannot read branch f44 of $url"; exit 1; }
[ -d "$src" ] || { log "cached description $src missing; request it from the sources owner (no git writes)"; exit 1; }
log "description pin $pin, branch f44 head $head$([ "$pin" = "$head" ] && echo ' (same)' || echo ' (DIFFERENT: the pin is kept)')"
git -C "$src" cat-file -e "$pin^{commit}" || { log "pinned commit not in the clone"; exit 1; }
desc=$work/description
mkdir -p "$desc"
git -C "$src" archive "$pin" | tar -x -C "$desc"
cd "$desc"

# ---- 2. SP11 layer: patches of Fedora files (fail loudly when the pin drifts), overlay, firmware
for p in "$REPO"/image/kiwi/patches/*.patch; do
	log "patch $(basename "$p")"
	patch -p1 --no-backup-if-mismatch -s <"$p"
done
cp -a "$REPO/image/overlay/." "$desc/root/"
rm -f "$desc/root/etc/sp11-log-collector.conf"   # lmc-only; the kiwi overlay has its own (ESP label BOOT)
cp -a "$REPO/image/kiwi/overlay/root/." "$desc/root/"
cp -a "$REPO/image/kiwi/overlay/sp11.xml" "$REPO/image/kiwi/overlay/grub-arm.cfg.iso-template" "$desc/"
chmod 0755 "$desc/root/usr/libexec/sp11-log-collector" "$desc/root/usr/libexec/sp11-kmsg-tail"
chmod 0755 "$desc/root/usr/libexec/sp11-touch-userspace-collect"
# D19 / display-lcd request: the DPCD reader of the display worker, shipped unchanged and run by the
# collector as root against every /dev/drm_dp_aux*
cp "$REPO/hardware/display-lcd/tools/collect-dpcd.py" "$desc/root/usr/libexec/sp11-collect-dpcd.py"
chmod 0755 "$desc/root/usr/libexec/sp11-collect-dpcd.py"
# Touch owner section 8: stage the stdout-only helper unchanged.
install -m 0755 "$REPO/hardware/touch-pen/collect-read-only.sh" "$desc/root/usr/libexec/sp11-touch-pen-collect"
# M15 touch (hardware/touch-pen evidence 2026-10-31-missed-taps.md): iptsd profile B (lower thresholds, upstream Surface Laptop Studio 2 values, scoped to
# 045E:0C80) is the DEFAULT, profile A (compiled defaults) is selected by the boot-medium marker sp11/touch-conf-A through the image-owned selector
# (the owner's selector read a GRUB variable; M15 GRUB is static). The tap diagnostic is an on-demand tool, never run by the collector.
install -D -m 0644 "$REPO/hardware/touch-pen/userspace/iptsd-sp11.conf" "$desc/root/usr/share/sp11/touch/iptsd-sp11.conf"
install -D -m 0644 "$REPO/hardware/touch-pen/userspace/10-sp11-touch-conf.conf" "$desc/root/usr/lib/systemd/system/iptsd@.service.d/10-sp11-touch-conf.conf"
install -m 0755 "$REPO/hardware/touch-pen/collector/sp11-touch-tap-diag" "$desc/root/usr/libexec/sp11-touch-tap-diag"
# Component collector requests (R-I1 and Wi-Fi I1/I2), copied unchanged from the merged dossiers.
mkdir -p "$desc/root/etc/sp11-log-collector.d"
for c in dsp-subsystems wifi; do
	cp "$REPO/hardware/$c/collector/$c.sh" "$desc/root/etc/sp11-log-collector.d/$c.sh"
done
# M11: the owner's DSP collector plus the image-owned sp11-glink/remoteproc append (one drop-in, one output file)
cat "$REPO/hardware/dsp-subsystems/collector/dsp-subsystems.sh" "$REPO/image/component-inputs/dsp-glink-append.sh" \
	>"$desc/root/etc/sp11-log-collector.d/dsp-subsystems.sh"
cp "$REPO/hardware/wifi/collector/wifi-unblock-probe.sh" "$desc/root/usr/libexec/sp11-wifi-unblock-probe.sh"
# D24: read-only snapshots taken with git show main:<path>, pinned in sources.json.
# Public build: no operator address input is read or staged. Private mode: see below.
inputs=$REPO/image/component-inputs
install -m 0755 "$inputs/bluetooth/userspace/sp11-bt-address" "$desc/root/usr/libexec/sp11-bt-address"
install -m 0755 "$inputs/bluetooth/userspace/sp11-bt-collect" "$desc/root/usr/libexec/sp11-bt-collect"
install -m 0644 "$inputs/bluetooth/userspace/sp11-bt-address.service" "$desc/root/usr/lib/systemd/system/sp11-bt-address.service"
mkdir -p "$desc/root/usr/libexec/sp11/ec-sam" "$desc/root/etc/systemd/system/sys-subsystem-bluetooth-devices-hci0.device.wants"
for tool in collect-input-capabilities.sh collect-power.sh ssam-ro.py; do
	install -m 0755 "$inputs/ec-sam/tools/$tool" "$desc/root/usr/libexec/sp11/ec-sam/$tool"
done
# M11/D28: collectors and the D28 UCM profiles.
install -m 0644 "$inputs/ec-sam/collector/ec-sam.sh" "$desc/root/etc/sp11-log-collector.d/ec-sam.sh"
cp -a "$REPO/hardware/audio-speakers/userspace/overlay/." "$desc/root/"
# M15 integration of the finished component pieces (each dossier's Requests; pins in image/component-inputs/m15-integration.json, L0 8.44).
# (2) audio: UCM route layer (DisplayPort HDMI0/HDMI1, SP11-Audio, capture gain step 98 capped at 108), WirePlumber priorities, dconf, audio-routes collector.
cp -a "$REPO/hardware/audio-mics/userspace/overlay-audio-routes/." "$desc/root/"
# (3) cameras: the owner collectors (the image drop-in is the owner file), the Spectra collector, and the Spectra test loader (marker sp11/spectra-load)
install -m 0755 "$REPO/hardware/cameras/collector/cameras.sh" "$desc/root/etc/sp11-log-collector.d/cameras.sh"
install -m 0644 "$REPO/hardware/cameras/spectra/collector/spectra.sh" "$desc/root/etc/sp11-log-collector.d/spectra.sh"
chmod 0755 "$desc/root/usr/libexec/sp11/spectra-load"
mkdir -p "$desc/root/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/sp11-gpu-no-runtime-pm.service "$desc/root/etc/systemd/system/multi-user.target.wants/sp11-gpu-no-runtime-pm.service"
ln -sf /usr/lib/systemd/system/sp11-spectra-load.service "$desc/root/etc/systemd/system/multi-user.target.wants/sp11-spectra-load.service"
# (4) volume buttons: the on-demand collector of the ec-sam owner (never run automatically)
install -D -m 0755 "$REPO/hardware/ec-sam/tools/collect-volume-buttons.sh" "$desc/root/usr/libexec/sp11/ec-sam/collect-volume-buttons.sh"
install -m 0644 "$REPO/hardware/sensors/userspace/collector/sensors.sh" "$desc/root/etc/sp11-log-collector.d/sensors.sh"
# (1) sensors: units of package sp11-sensors, enabled explicitly as well as by the package preset (Fedora's preset-all would otherwise decide); adsprpcd* stays unmasked
ln -sf /usr/lib/systemd/system/hexagonrpcd-sensors.service "$desc/root/etc/systemd/system/multi-user.target.wants/hexagonrpcd-sensors.service"
mkdir -p "$desc/root/etc/systemd/system/sleep.target.wants"
ln -sf /usr/lib/systemd/system/hexagonrpcd-sensors-sleep.service "$desc/root/etc/systemd/system/sleep.target.wants/hexagonrpcd-sensors-sleep.service"
# D28: sound-model firmware names select topology in the kernel at component probe; UCM DMI selection is driver-level.
install -D -m 0644 "$REPO/image/component-inputs/d28/audio/x1e80100.conf" "$desc/root/usr/share/alsa/ucm2/Qualcomm/x1e80100/x1e80100.conf"
for f in MICROSOFT-Surface-Pro-11.conf Surface11-HiFi.conf Surface11-SpeakerSeq.conf Surface11-WsaInit.conf; do
	install -D -m 0644 "$REPO/image/component-inputs/d28/audio/$f" "$desc/root/usr/share/alsa/ucm2/Qualcomm/x1e80100/$f"
done
rm -f "$desc/root/usr/share/alsa/ucm2/Qualcomm/x1e80100/SP11-Audio.conf"
topology=qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin
[ -s "$OUT/image-inputs/audio/$topology" ] || {
	log "REFUSED: missing public D28 topology artefact (build hardware/audio-speakers/userspace/build-topology.sh)"; exit 6;
}
install -D -m 0644 "$OUT/image-inputs/audio/$topology" "$desc/root/usr/lib/firmware/$topology"
mkdir -p "$desc/root/etc/systemd/user/graphical-session-pre.target.wants"
install -m 0755 "$REPO/image/overlay/usr/libexec/sp11-audio-safety" "$desc/root/usr/libexec/sp11-audio-safety"
install -m 0644 "$REPO/image/overlay/usr/lib/systemd/user/sp11-audio-safety.service" "$desc/root/usr/lib/systemd/user/sp11-audio-safety.service"
ln -sf /usr/lib/systemd/user/sp11-audio-safety.service "$desc/root/etc/systemd/user/graphical-session-pre.target.wants/sp11-audio-safety.service"
mkdir -p "$desc/root/etc/systemd/user/graphical-session.target.wants"
install -m 0755 "$REPO/image/overlay/usr/libexec/sp11-post-session-collect" "$desc/root/usr/libexec/sp11-post-session-collect"
ln -sf /usr/lib/systemd/user/sp11-post-session-collect.service "$desc/root/etc/systemd/user/graphical-session.target.wants/sp11-post-session-collect.service"
# Compile the locked distro dconf database after kiwi has installed dconf,
# before Fedora's config.sh exits.
sed -i '$i # SP11 M11: compile the locked GNOME volume policy.\ndconf update' "$desc/config.sh"
# M15: the gpu worker's two-step diagnostic (hardware/gpu/collector) is ENABLED (multi-user.target.wants, preset `enable`) and runs only through the owner
# unit's ConditionKernelCommandLine=sp11.gpu_diag=1, an operator-supplied argument absent from every menu entry; the image drop-in orders it before
# gdm. GRUB is static; the markers are plain files on the boot medium (sp11-boot-state). The machine reset of the first DRM open cannot be prevented here.
# Image-owned changes to the owner script, pinned in image/component-inputs/m15.json and required exactly by L0 8.37: (1) the label list gains BOOT (this ISO's embedded ESP label);
# (2) the hook functions of image/component-inputs/gpu-state-hooks.sh are inserted before the main section; (3) four one-line calls to them.
# The owner unit stays byte for byte; the image adds a drop-in with Before=gdm.service.
gpu_src=$REPO/hardware/gpu/collector
gpu_hooks=$REPO/image/component-inputs/gpu-state-hooks.sh
for pat in '^	for lbl in SP11LOGS ANACONDA; do$' '^cp "\$OUT/previous-boot-report.txt" "\$RUN/report.txt" 2>/dev/null$' '^start_follower$' '^\[ "\$limit" -ge 1 \] && { step1 || true; } || mark "SKIP step 1 (died there last time)"$' '^mark DONE$' '^# --------------------------------------------------------------- main -----$'; do
	[ "$(grep -c -- "$pat" "$gpu_src/gpu-two-step.sh")" = 1 ] || { log "REFUSED: gpu-two-step.sh no longer has exactly one line matching $pat"; exit 6; }
done
bash "$REPO/image/tools/test-gpu-two-step-transform.sh" || { log "REFUSED: the GPU two-step image transformation test failed"; exit 6; }
awk -v hooks="$gpu_hooks" -f "$REPO/image/component-inputs/gpu-two-step-patch.awk" "$gpu_src/gpu-two-step.sh" >"$desc/root/usr/libexec/sp11-gpu-two-step"
chmod 0755 "$desc/root/usr/libexec/sp11-gpu-two-step"
bash -n "$desc/root/usr/libexec/sp11-gpu-two-step" || { log "REFUSED: the patched gpu-two-step.sh has a syntax error"; exit 6; }
install -m 0644 "$gpu_src/sp11-gpu-two-step.service" "$desc/root/usr/lib/systemd/system/sp11-gpu-two-step.service"
mkdir -p "$desc/root/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/sp11-gpu-two-step.service "$desc/root/etc/systemd/system/multi-user.target.wants/sp11-gpu-two-step.service"
# M14: power-thermal owner files (suspend ladder opt-in, default-on s2idle cpuidle guard, thermal sampler opt-in) and its read-only collector
cp -a "$REPO/hardware/power-thermal/userspace/overlay/." "$desc/root/"
install -m 0644 "$REPO/hardware/power-thermal/collector/power-thermal.sh" "$desc/root/etc/sp11-log-collector.d/power-thermal.sh"
chmod 0755 "$desc/root/usr/libexec/sp11/power-thermal/"* "$desc/root/usr/lib/systemd/system-sleep/sp11-suspend"
for u in sp11-suspend-policy.service sp11-wakeup-policy.service sp11-suspend-diag.service sp11-thermal-sample.service; do
	case $u in sp11-suspend-policy.service) w=sysinit ;; *) w=multi-user ;; esac
	mkdir -p "$desc/root/etc/systemd/system/$w.target.wants"
	ln -sf "/usr/lib/systemd/system/$u" "$desc/root/etc/systemd/system/$w.target.wants/$u"
done
# M15: Linux-side experiments (image-owned; the GRUB menu is static, state is plain files on the boot medium via sp11-boot-state, S4): the SAM
# shutdown mode rotor, the identity switch (marker sp11/identity-none) and the cpufreq cap (marker sp11/enable-cpufreq-cap) at sysinit/multi-user,
# the opt-in CDSP experiment (main entry and boot-medium marker), all shown through operator-notice.
mkdir -p "$desc/root/etc/systemd/system/sysinit.target.wants" "$desc/root/etc/systemd/system/multi-user.target.wants"
for u in sp11-sam-mode-rotor.service sp11-identity-switch.service sp11-wifi-identity.service; do
	ln -sf "/usr/lib/systemd/system/$u" "$desc/root/etc/systemd/system/sysinit.target.wants/$u"
done
for u in sp11-cdsp-experiment.service sp11-cpufreq-cap.service; do
	ln -sf "/usr/lib/systemd/system/$u" "$desc/root/etc/systemd/system/multi-user.target.wants/$u"
done
chmod 0755 "$desc/root/usr/libexec/sp11-touch-conf-select" "$desc/root/usr/libexec/sp11-boot-state" "$desc/root/usr/libexec/sp11/"{operator-notice,sam-mode-rotor,cdsp-experiment,cpufreq-cap,identity-switch,gpu-retry,speaker-supervisor,speaker-first-test}
# M15: identity experiment of the wifi and bluetooth workers (hardware/wifi/image-request-identity.md, hardware/bluetooth/image-request.md), installed in every
# ISO (inert without the private-mode marker /usr/share/sp11/image-mode). The switch sp11.identity=none is the boot-medium marker sp11/identity-none.
install -m 0644 "$REPO/hardware/wifi/collector/identity.sh" "$desc/root/etc/sp11-log-collector.d/wifi-identity.sh"
install -m 0755 "$REPO/hardware/wifi/userspace/sp11-wifi-identity" "$desc/root/usr/libexec/sp11-wifi-identity"
install -m 0644 "$REPO/hardware/wifi/userspace/sp11-wifi-identity.service" "$desc/root/usr/lib/systemd/system/sp11-wifi-identity.service"
install -m 0644 "$REPO/hardware/bluetooth/collector/identity.sh" "$desc/root/etc/sp11-log-collector.d/bluetooth-identity.sh"
install -m 0755 "$REPO/hardware/bluetooth/collector/sp11-identity-bt" "$desc/root/usr/libexec/sp11-identity-bt"
install -m 0644 "$REPO/hardware/bluetooth/collector/sp11-identity-bt-pre.service" "$desc/root/usr/lib/systemd/system/sp11-identity-bt-pre.service"
ln -sf /usr/lib/systemd/system/sp11-identity-bt-pre.service "$desc/root/etc/systemd/system/sys-subsystem-bluetooth-devices-hci0.device.wants/sp11-identity-bt-pre.service"
# M14 (d): the NPU installer for the operator's own QAIRT download is private-mode only (below); fastrpc, fastrpc-services and qrtr are packages (sp11.xml)
ln -sf /usr/lib/systemd/system/sp11-bt-address.service "$desc/root/etc/systemd/system/sys-subsystem-bluetooth-devices-hci0.device.wants/sp11-bt-address.service"
mkdir -p "$desc/root/etc/systemd/system/multi-user.target.wants"
# Plymouth is installed (required by Fedora's package groups) but switched off: units masked
for u in start quit quit-wait read-write switch-root halt reboot poweroff kexec; do
	ln -sf /dev/null "$desc/root/etc/systemd/system/plymouth-$u.service"
done
for u in sp11-log-collector.service sp11-log-collector-session-first.path sp11-log-collector-session-user.path sp11-rfkill-events.service sp11-ssam-rebind.service; do
	ln -sf "/usr/lib/systemd/system/$u" "$desc/root/etc/systemd/system/multi-user.target.wants/$u"
done
mkdir -p "$desc/root/etc/systemd/system/sysinit.target.wants"
ln -sf /usr/lib/systemd/system/sp11-ssam-shutdown.service "$desc/root/etc/systemd/system/sysinit.target.wants/sp11-ssam-shutdown.service"
ln -sf /usr/lib/systemd/system/sp11-kmsg-tail.service "$desc/root/etc/systemd/system/sysinit.target.wants/sp11-kmsg-tail.service"

# Private mode (operator device only): copy the staged tree made by the host side. It holds the
# Bluetooth address file, the Wi-Fi address (NetworkManager conf and .link) and the derived board file.
if [ "$private" = 1 ]; then
	ps=$OUT/private-stage
	[ -s "$ps/private-record.json" ] && [ -d "$ps/root" ] || { log "REFUSED: private stage missing; run scripts/image-build.sh --private"; exit 6; }
	cp -a "$ps/root/." "$desc/root/"
	chown -R 0:0 "$desc/root/etc/sp11"
	[ ! -d "$desc/root/usr/lib/firmware/updates" ] || chown -R 0:0 "$desc/root/usr/lib/firmware/updates"
	chown 0:0 "$desc/root/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf" "$desc/root/etc/systemd/network/10-sp11-wifi.link"
	cp "$ps/private-record.json" "$work/private-record.json"   # hash prefixes only
	# M14: camera blobs, the alternate CDSP pair (also in the initramfs), the closed-loop speaker files (kept under a distinct name alongside the public topology), the staged sensor configuration and the NPU installer. Verified here with the owners' checks; names and counts only in the log.
	python3 -I "$REPO/image/tools/private-m14.py" stage --fp "$OUT/firmware-private" --root "$desc/root" --repo "$REPO" \
		--record "$work/private-m14-record.json" >"$work/private-m14-stage.txt" 2>&1 || { cat "$work/private-m14-stage.txt" >&2; log "REFUSED: private M14 staging failed"; exit 6; }
	cat "$work/private-m14-stage.txt" >&2
	log "PRIVATE build: staged device settings copied into the root (values not logged)"
fi

[ -d "$OUT/firmware-root/lib/firmware" ] || { log "$OUT/firmware-root missing; run scripts/firmware-stage.sh"; exit 1; }
mkdir -p "$desc/root/usr/lib/firmware"
cp -a "$OUT/firmware-root/lib/firmware/." "$desc/root/usr/lib/firmware/"
rm -f "$OUT/image-work/firmware-installed.sha256"
( cd "$OUT/firmware-root/lib/firmware" && find . -type f | sort | xargs sha256sum ) >"$OUT/image-work/firmware-installed.sha256"

# ---- 3. local repository with our kernel RPMs (no debuginfo, devel, uki)
log "local repository from $OUT/rpms"
rm -rf "$OUT/repo"
mkdir -p "$OUT/repo"
for n in kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra; do
	f=$OUT/rpms/$n-$kver_full.rpm
	[ -f "$f" ] || { log "no $n-$kver_full.rpm in $OUT/rpms"; exit 1; }
	cp "$f" "$OUT/repo/"
done
cp "$iptsd_rpm" "$OUT/repo/"
# M15 integration: the local sensor RPMs, the Spectra module RPM (rebuilt against this kernel-devel) and the local libcamera set (Fedora source + the cameras patches)
sensors_rpms="hexagonrpcd libssc libssc-tools iio-sensor-proxy sp11-sensors"
for n in $sensors_rpms; do
	f=$(ls "$OUT"/rpms-local/$n-[0-9]*.rpm | grep -v -E '\.src\.rpm$|debuginfo|debugsource' | head -n1)
	[ -f "$f" ] || { log "REFUSED: local sensor RPM $n missing in out/rpms-local (hardware/sensors/userspace/build-sensors-rpms.sh)"; exit 6; }
	cp "$f" "$OUT/repo/"
done
spectra_rpm=$(ls "$OUT"/rpms-local/sp11-camera-spectra-1.0-*.aarch64.rpm 2>/dev/null | head -n1)
[ -f "$spectra_rpm" ] && [ "$(jq -r .kver "${spectra_rpm%.rpm}.json")" = "$kver_full" ] && [ "$(sha256sum "$spectra_rpm" | cut -d' ' -f1)" = "$(jq -r .rpm_sha256 "${spectra_rpm%.rpm}.json")" ] || {
	log "REFUSED: sp11-camera-spectra RPM missing or not built for $kver_full (hardware/cameras/spectra/rpm/build-spectra-rpm.sh $kver_full)"; exit 6; }
cp "$spectra_rpm" "$OUT/repo/"
libcamera_dir=$OUT/rpms-local/libcamera
if [ -s "$libcamera_dir/libcamera-sp11-build.json" ]; then
	for f in "$libcamera_dir"/*.rpm; do
		case $f in *.src.rpm | *debuginfo* | *debugsource*) continue ;; esac
		[ "$(sha256sum "$f" | cut -d' ' -f1)" = "$(jq -r --arg n "$(basename "$f")" '.rpms[$n]' "$libcamera_dir/libcamera-sp11-build.json")" ] || { log "REFUSED: $f differs from its build record"; exit 6; }
		cp "$f" "$OUT/repo/"
	done
	echo local >"$work/libcamera-source.txt"
else
	echo stock >"$work/libcamera-source.txt"
fi
createrepo_c -q "$OUT/repo"
kcore=$(ls "$OUT"/repo/kernel-core-*.rpm)
kver=$(rpm -qp --qf '%{version}-%{release}.%{arch}' "$kcore")
echo "kernel-core-$kver" >"$OUT/image-work/kernel-nevra.txt"

# ---- 4. DTB on the ISO root (config-cdroot.tar of kiwi, unpacked into the ISO tree)
dtbtmp=$work/dtb
mkdir -p "$dtbtmp/boot/dtb/qcom"
rpm2cpio "$kcore" | cpio -i --quiet --to-stdout "./lib/modules/$kver/dtb/qcom/x1p64100-microsoft-denali.dtb" \
	>"$dtbtmp/boot/dtb/qcom/x1p64100-microsoft-denali.dtb"
[ -s "$dtbtmp/boot/dtb/qcom/x1p64100-microsoft-denali.dtb" ] || { log "DTB not in $kcore"; exit 1; }
# M11: the kernel worker variants next to the packaged DTB. The build fails without
# it; with --smoke a copy of the packaged DTB stands in (recorded, never for the device).
variants_smoke_copy=0
for v in m15 m15-safe m15-nosnd m15-notouch m15-spk m15-spectra; do
	vf=x1p64100-microsoft-denali-$v.dtb
	vsrc=$OUT/dtb-variants/$kver/qcom/$vf
	if [ -s "$vsrc" ]; then
		cp "$vsrc" "$dtbtmp/boot/dtb/qcom/$vf"
		mkdir -p "$work/dtb-records"
		for r in "${vsrc%.dtb}.json" "$vsrc.json"; do [ -f "$r" ] && cp "$r" "$work/dtb-records/$vf.json"; done
	elif [ "$smoke" = 1 ]; then
		log "SMOKE: $vsrc missing, using a copy of the packaged DTB for the $v entry"
		cp "$dtbtmp/boot/dtb/qcom/x1p64100-microsoft-denali.dtb" "$dtbtmp/boot/dtb/qcom/$vf"
		variants_smoke_copy=1
	else
		log "REFUSED: DTB variant $vsrc is missing (the kernel worker writes it); --smoke only for a pipeline test"
		exit 6
	fi
done
tar -C "$dtbtmp" -cf "$desc/config-cdroot.tar" boot

# ---- 5. pins for the build record
dnf -q repoinfo fedora updates --setopt=reposdir=/etc/yum.repos.d 2>/dev/null |
	grep -E '^(Repo-id|Repo-revision|Repo-updated)' >"$work/repos.txt" || true
printf "pin=%s\nhead=%s\nkver=%s\nvariants_smoke_copy=%s\n" "$pin" "$head" "$kver" "$variants_smoke_copy" >"$work/build-vars.env"
# ---- 6. kiwi, through Fedora's own wrapper
# The image root must not be built below /out: /out is a bind mount of a host path, kernel-install
# computes the BLS entry paths from the mount's source (/proc/self/mountinfo) and wrote the host path
# (with the user name) into /boot/loader/entries/*.conf of the first kiwi ISO (L0 check 7.2). The
# container's own file system has root "/", so the paths stay clean. Results are copied to $work.
kiwiout=/var/tmp/sp11-kiwi
rm -rf "$kiwiout"; mkdir -p "$kiwiout"
log "kiwi-ng via kiwi-build, log: $work/kiwi.log (several tens of minutes)"
start=$(date +%s)
set +e
./kiwi-build --debug --image-type=iso --image-profile=Workstation-Live --kiwi-file=Fedora.kiwi \
	--kiwi-description-dir="$desc" --output-dir="$kiwiout/out" >"$work/kiwi.log" 2>&1
rc=$?
set -e
tail -n 25 "$work/kiwi.log" | cut -c1-300
[ "$rc" = 0 ] || { log "kiwi failed (rc=$rc), see $work/kiwi.log"; exit 1; }
elapsed=$(($(date +%s) - start))
mkdir -p "$work/out-build"
cp "$kiwiout"/out-build/Fedora.aarch64-44.* "$kiwiout"/out-build/kiwi.result* "$work/out-build/"
iso=$(ls "$work"/out-build/*.iso 2>/dev/null | head -n1)
[ -f "$iso" ] || { log "no ISO in $work/out-build"; ls -la "$work/out-build" >&2; exit 1; }
log "ISO $iso after ${elapsed}s"
echo "elapsed=$elapsed" >>"$work/build-vars.env"
else
	[ -f "$work/build-vars.env" ] || { log "no finished run $post_only"; exit 1; }
	# shellcheck disable=SC1091
	. "$work/build-vars.env"
	iso=$(ls "$work"/out-build/*.iso | head -n1)
fi
cd "$work"

# ---- 6b. FAT32 ESP (decision D17). kiwi 11.1.1 makes the embedded ESP with `mkdosfs -n BOOT FILE`
# (bootloader/config/grub2.py, _create_embedded_fat_efi_image): no -F, so mkfs.fat picks FAT16 for
# 30 MiB (15321 clusters), and the only knob, efifatimagesize, sets the size, not the FAT type
# (a size that gives >= 65525 clusters would need cluster size 512 B, which mkdosfs does not choose
# either). The Surface UEFI boots only from a FAT32 USB ESP. So the finished ISO is replayed with a
# 64 MiB FAT32 ESP made with the documented flags and the same EFI/BOOT files:
#   xorriso -boot_image any replay -append_partition 2 0xef ESP   (El Torito entry follows partition 2)
log "replacing the FAT16 ESP by a 64 MiB FAT32 ESP (D17)"
esp=$work/esp; rm -rf "$esp"; mkdir -p "$esp/files"
xorriso -osirrox on -indev "$iso" -extract_boot_images "$esp/old/" >/dev/null 2>&1
mcopy -n -s -i "$esp/old/eltorito_img1_uefi.img" ::EFI "$esp/files/"
# ---- D18: the stick boots Fedora's GRUB directly. On the Surface the firmware returned to its boot
# menu before GRUB with shim 16.1-7 as BOOTAA64.EFI (Secure Boot off; reason unknown, Hypothesis), and
# reached the Linux console with GRUB there (previous project, 2026-10-18). Secure Boot is off anyway
# (D9), so shim does nothing for us. EFI/BOOT after this step:
#   BOOTAA64.EFI = grubaa64.efi (byte-identical), shimaa64.efi = kiwi's shim (kept, unused),
#   mmaa64.efi (shim's MokManager, unused, kept), grubaa64.efi, grub.cfg (marker line first).
# bootx64.efi is removed: kiwi writes the aa64 shim under an x86 name (same size and content as
# bootaa64.efi, from its x86 fallback-name list); no arm64 firmware looks for it, and it would be a
# shim at a fallback path.
efib=$esp/files/EFI/BOOT
fnd() { find "$efib" -maxdepth 1 -iname "$1" | head -n1; }
if [ -z "$(fnd shimaa64.efi)" ]; then mv "$(fnd bootaa64.efi)" "$efib/shimaa64.efi"; fi   # re-runs: already renamed
rm -f "$(fnd bootx64.efi)"
rm -f "$(fnd bootaa64.efi)"
[ -n "$(fnd grubaa64.efi)" ] || { log "no grubaa64.efi in the ESP"; exit 1; }
cp "$(fnd grubaa64.efi)" "$efib/BOOTAA64.EFI"
marker='echo "SP11: GRUB started (direct EFI boot, no shim)"'
cfg=$(fnd grub.cfg)
grep -qxF "$marker" "$cfg" || { { echo "$marker"; cat "$cfg"; } >"$cfg.new" && mv "$cfg.new" "$cfg"; }
# M15: no GRUB environment block and no state file is created here: the menu is static and sp11-boot-state creates sp11/state/ on the boot medium at first use.
mkfs.fat -C -F 32 -s 1 -S 512 -n BOOT "$esp/esp32.img" 65536 >/dev/null
mcopy -s -i "$esp/esp32.img" "$esp/files/EFI" ::
xorriso -indev "$iso" -outdev "$iso.fat32" -boot_image any replay -append_partition 2 0xef "$esp/esp32.img" -commit >"$esp/xorriso.txt" 2>&1 \
	|| { tail -n 5 "$esp/xorriso.txt" >&2; log "xorriso replay failed"; exit 1; }
mv -f "$iso.fat32" "$iso"
# the replay changed the bytes the media tag of kiwi (implantisomd5) covers: tag again, or checkisomd5 fails
implantisomd5 --force --supported-iso "$iso" >"$esp/implant.txt" 2>&1 || { cat "$esp/implant.txt" >&2; log "implantisomd5 failed"; exit 1; }
rm -rf "$esp/old"

# ---- 7. the checks of the task: no quiet/rhgb/splash in any grub.cfg of the ISO and its ESP
log "grep check: quiet/rhgb/splash in every grub.cfg"
chk=$work/grubcheck
rm -rf "$chk"; mkdir -p "$chk"
for f in /boot/grub2/grub.cfg /boot/grub2/loopback.cfg /EFI/BOOT/grub.cfg /EFI/fedora/grub.cfg; do
	xorriso -osirrox on -indev "$iso" -extract "$f" "$chk/$(echo "$f" | tr / _)" >/dev/null 2>&1 || { log "FAIL: $f not in the ISO"; exit 1; }
done
xorriso -osirrox on -indev "$iso" -extract_boot_images "$chk/bi/" >/dev/null 2>&1
mcopy -i "$chk/bi/eltorito_img1_uefi.img" ::EFI/BOOT/grub.cfg "$chk/esp-grub.cfg"
for f in "$chk"/_* "$chk/esp-grub.cfg"; do
	# kernel arguments only: a menu title or a parameter value such as shutdown_mode=quiet is not the kernel argument `quiet`
	if grep -E '^[[:space:]]*(linux|linuxefi)[[:space:]]' "$f" | tr -s ' \t' '\n\n' | grep -x -E 'quiet|rhgb|splash' >/dev/null; then log "FAIL: quiet/rhgb/splash argument in $f"; exit 1; fi
done
n=$(grep -c "^menuentry '" "$chk/_boot_grub2_grub.cfg"); [ "$n" = 12 ] || { log "FAIL: $n top-level menu entries, expected 12 (M15: flat static menu)"; exit 1; }
[ "$(grep -c -E '^[[:space:]]*submenu[[:space:]]' "$chk/_boot_grub2_grub.cfg")" = 0 ] || { log "FAIL: submenu command in the M15 menu"; exit 1; }
for e in debug safe nosnd notouch spk usbdbg nodsp wifi-unblock nomodeset initramfs spectra vmtest; do grep -q "sp11.entry=$e\$" "$chk/_boot_grub2_grub.cfg" || { log "FAIL: no entry with sp11.entry=$e"; exit 1; }; done
python3 -I "$REPO/image/tools/check-m8-menu.py" "$chk/_boot_grub2_grub.cfg"
for f in x1p64100-microsoft-denali-m15 x1p64100-microsoft-denali-m15-safe x1p64100-microsoft-denali-m15-nosnd x1p64100-microsoft-denali-m15-notouch x1p64100-microsoft-denali-m15-spk x1p64100-microsoft-denali-m15-spectra; do
	xorriso -indev "$iso" -find "/boot/dtb/qcom/$f.dtb" -type f 2>/dev/null | grep -q . || { log "FAIL: /boot/dtb/qcom/$f.dtb not on the ISO"; exit 1; }
done

# ---- 8. publish
mv -f "$iso" "$isodir/$name.iso"
( cd "$isodir" && sha256sum "$name.iso" >"$name.iso.sha256" )
sha=$(cut -d' ' -f1 "$isodir/$name.iso.sha256")

# ---- 9. build record
python3 - "$isodir/$name.json" "$name" "$sha" "$id" "$elapsed" "$work" "$REPO" "$OUT" "$pin" "$head" "${variants_smoke_copy:-0}" "$kind" "$private" <<'PYEOF'
import hashlib, json, os, re, subprocess, sys
rec, name, sha, bid, elapsed, work, repo, out, pin, head, variants_smoke_copy, kind, private = sys.argv[1:14]

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def read(p, default=''):
    try:
        return open(p).read()
    except OSError:
        return default

pk = []
for l in read(f"{work}/out-build/Fedora.aarch64-44.packages").splitlines():
    f = l.split('|')
    if len(f) >= 5:
        pk.append(f"{f[0]}-{0 if f[1] == '(none)' else f[1]}:{f[2]}-{f[3]}.{f[4]}")
pk.sort()
fw = [l.split() for l in read(f"{out}/image-work/firmware-installed.sha256").splitlines() if l]
cfg = read(f"{work}/grubcheck/_boot_grub2_grub.cfg")
entries = []
for m in re.finditer(r"^[ \t]*menuentry '([^']*)'[^\n]*\{(.*?)^[ \t]*\}", cfg, re.S | re.M):
    lin = re.search(r"^\s*linux \S+ (.*)$", m.group(2), re.M)
    entries.append({"title": m.group(1), "linux_args": lin.group(1).strip() if lin else None,
                    "devicetree": bool(re.search(r"^\s*devicetree ", m.group(2), re.M))})
series = f"{repo}/kernel/series"
manifest = f"{repo}/firmware/manifest.toml"
kernel_record_path = f"{out}/rpms/{read(f'{out}/image-work/kernel-nevra.txt').strip().replace('kernel-core-', 'kernel-')}.json"
patches = sorted(os.listdir(f"{repo}/image/kiwi/patches"))
series_paths = [''.join(line.split('#', 1)[0].split()) for line in read(series).splitlines()]
patch_series = ''.join(f"{p} {sha256(f'{repo}/{p}')}\n" for p in series_paths if p)
d28_path = f"{out}/image-inputs/audio/d28-runtime-validation.json"
d28_input = json.load(open(d28_path)) if os.path.isfile(d28_path) else None
m28_pin = json.load(open(f"{repo}/image/component-inputs/m28.json"))
import importlib.util
d28_gate_spec = importlib.util.spec_from_file_location("d28_build_gate", f"{repo}/image/tools/check-d28-build-gate.py")
d28_gate = importlib.util.module_from_spec(d28_gate_spec)
d28_gate_spec.loader.exec_module(d28_gate)
d28_record = d28_gate.build_record(d28_input, m28_pin["topology"], "private" if private == "1" else "public")
record = {
    "name": name, "kind": kind, "builder": "kiwi", "smoke": kind == "kiwi-smoke", "build_id": bid,
    "iso_sha256": sha, "iso_size": os.path.getsize(f"{out}/iso/{name}.iso"),
    "build_seconds": int(elapsed),
    "kernel_nevra": read(f"{out}/image-work/kernel-nevra.txt").strip(),
    "kernel_series_sha256": sha256(series) if os.path.exists(series) else None,
    "kernel_patch_series_sha256": hashlib.sha256(patch_series.encode()).hexdigest(),
    "firmware_manifest_sha256": sha256(manifest) if os.path.exists(manifest) else None,
    "firmware_installed": [{"sha256": a, "path": b} for a, b in fw],
    "firmware_installed_listing_sha256": hashlib.sha256("\n".join(" ".join(x) for x in fw).encode()).hexdigest(),
    "dtb": "qcom/x1p64100-microsoft-denali.dtb",
    "dtb_files": {f: sha256(f"{work}/dtb/boot/dtb/qcom/{f}") for f in sorted(os.listdir(f"{work}/dtb/boot/dtb/qcom"))},
    "dtb_variants_smoke_copy": variants_smoke_copy == "1",
    "dtb_variants_source": "out/dtb-variants/<kernel version>/qcom/ (kernel worker)",
    "dtb_variant_records": {f: json.load(open(f"{work}/dtb-records/{f}")) for f in sorted(os.listdir(f"{work}/dtb-records"))} if os.path.isdir(f"{work}/dtb-records") else {},
    "kernel_cmdline_reasons": "image/README.md, GRUB 2 and the kernel command line",
    "grub_entries": entries,
    "milestone": "M16",
    "kernel_release_record_sha256": sha256(kernel_record_path),
    "kernel_touch_modules": next(v["touch_modules"] for k in ("m16", "m15", "m14", "m13") for v in [json.load(open(kernel_record_path)).get(k)] if v and "touch_modules" in v),
    "module_policy": {"qcom_battmgr": "blacklist + install false + dracut omit_drivers (D23)",
                      "ucsi_glink": "retained early", "ath12k.debug_mask": "0x70; CONFIG_ATH12K_DEBUG=y; output checked by L0",
                      "scmi_cpufreq": "modules-load.d/sp11-cpufreq.conf (soc-boot R-I2); cap by default, lifted only by the boot-medium marker sp11/cpufreq-uncapped"},
    "menu": "M15 flat static menu, 12 entries, no GRUB function except load_video, no grubenv, no variable: debug (m15 with GPU and cameras), safe (m15-safe), nosnd, notouch, spk, usbdbg, nodsp, wifi-unblock, nomodeset, initramfs, spectra, vmtest",
    "diagnostic_args_reason": {"debug": "M15 line 1: m15 DTB (microphones + rear/front/IR camera nodes + GPU/GMU/zap), no automatic GPU two-step (manually add sp11.gpu_diag=1; may reset the machine), USB dynamic debug (usb-typec R-I1), PDR dynamic debug, DSP trace string without power:power_domain_target; nothing variable",
                               "safe": "m15-safe: microphones only, camera and GPU nodes off (the M13/M14-safe content); the always-booting fallback, line 1 arguments except entry marker",
                               "nosnd": "m15-nosnd: sound card off", "notouch": "touch-pen section 8: m15-notouch, touch child disabled",
                               "spk": "private-only closed-loop experiment: m15-spk must select the CL sound model; public image omits the CL topology and fails closed; sp11.nospk kill switch",
                               "spectra": "Qualcomm Spectra camera test: m15-spectra DTB, the safe arguments plus module_blacklist=camera_x1e80100 (the kernel then refuses every load of that module); sp11-spectra-load.service loads it only with the marker sp11/spectra-load on the boot medium and without that argument",
                               "usbdbg": "M13 USB + DSP trace (8M buffer) on m15-safe", "nodsp": "qcom_q6v5_pas blacklisted (no early DSP) on m15-safe",
                               "wifi-unblock": "sp11.wifi_unblock=1 on m15-safe", "nomodeset": "nomodeset on m15-safe", "initramfs": "rd.break=pre-mount on m15-safe", "vmtest": "L1 only, no devicetree"},
    "linux_side_experiments": {"sam_mode_order": "silent, clean, quiet, default (sp11-sam-mode-rotor.service; counter sp11_sam_counter in sp11/state/ on the boot medium)",
               "cdsp_variants": ["fw=c1-00078 keep_proxy_pds=0 forced", "fw=c1-00046.1 keep_proxy_pds=default (-1: votes kept)", "fw=c1-00046.1 keep_proxy_pds=0 forced", "fw=c1-00078 keep_proxy_pds=default (-1: votes kept)"],
               "cdsp_mechanism": "sp11-cdsp-experiment.service: main entry with boot-medium sp11/cdsp-experiment marker only, once per boot, restart of the cdsp remoteproc with keep_proxy_pds and the firmware directory; counter sp11_cdsp_counter",
               "identity_switch": "marker sp11/identity-none on the boot medium (private ISO); sp11-identity-switch.service",
               "cpufreq_cap": "cap applies BY DEFAULT (schedutil, median scaling_max_freq); marker sp11/cpufreq-uncapped lifts it (S6); sp11-cpufreq-cap.service",
               "gpu_two_step": "enabled; runs only with manually supplied sp11.gpu_diag=1; plain-file markers on the boot medium"},
    "collector_sources": {c: sha256(f"{repo}/hardware/{c}/collector/{c}.sh") for c in ("dsp-subsystems", "wifi")},
    "m15_inputs": json.load(open(f"{repo}/image/component-inputs/m15.json")),
    "m28_inputs": json.load(open(f"{repo}/image/component-inputs/m28.json")),
    "d28_runtime_validation": d28_record,
    "m15_integration": json.load(open(f"{repo}/image/component-inputs/m15-integration.json")),
    "libcamera_source": read(f"{work}/libcamera-source.txt").strip(),
    "local_rpm_sha256": {os.path.basename(f): sha256(f) for f in sorted(__import__("glob").glob(f"{out}/repo/*.rpm")) if not os.path.basename(f).startswith("kernel")},
    "touch_collector_sha256": sha256(f"{repo}/hardware/touch-pen/collect-read-only.sh"),
    "touch_userspace_collector_sha256": sha256(f"{repo}/image/overlay/usr/libexec/sp11-touch-userspace-collect"),
    "iptsd": json.load(open(f"{out}/rpms/iptsd-3.1.0-1.fc44.aarch64.json")),
    "component_inputs": json.load(open(f"{repo}/image/component-inputs/sources.json")),
    "m11_inputs": json.load(open(f"{repo}/image/component-inputs/m11.json")),
    "kiwi_description": {"url": "https://pagure.io/fedora-kiwi-descriptions.git", "branch": "f44", "pinned_commit": pin,
                         "branch_head_at_build": head, "profile": "Workstation-Live", "kiwi_file": "Fedora.kiwi",
                         "sp11_patches": patches},
    "repos": read(f"{work}/repos.txt").strip().splitlines(),
    "container_image": os.environ.get("SP11_IMAGE_ID", ""),
    "package_count": len(pk), "packages": pk,
    "tools": {t: subprocess.run(["rpm", "-q", t], capture_output=True, text=True).stdout.strip()
              for t in ("kiwi-cli", "dnf5", "grub2-efi-aa64", "shim-aa64", "dracut", "xorriso", "erofs-utils")},
}
if private == "1":
    # hash prefixes and the board hash only (image/tools/private-stage.py); never an address
    record["private"] = json.load(open(f"{work}/private-record.json"))
    record["private_m14"] = json.load(open(f"{work}/private-m14-record.json"))   # hashes and counts only
    record["distribution"] = "forbidden: operator-only private ISO; never share; D28 runtime safety is unvalidated"
json.dump(record, open(rec, "w"), indent=1)
PYEOF
log "done: $isodir/$name.iso ($sha)"
log "record: $isodir/$name.json"
