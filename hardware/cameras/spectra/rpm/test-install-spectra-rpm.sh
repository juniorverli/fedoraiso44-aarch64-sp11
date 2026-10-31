#!/usr/bin/env bash
# Install-test sp11-camera-spectra in a scratch root (container, nothing on the host or the device).
#
#   hardware/cameras/spectra/rpm/test-install-spectra-rpm.sh [RPM]
#
# Checks: rpm -i into a scratch root (--nodeps: the root has no kernel package, the Requires is verified separately),
# file list, depmod in the root (module found, alias for the DT node resolves to camera_x1e80100), module is a valid
# ELF with .BTF and vermagic equal to the kernel, modprobe `install` guard (Spectra DT present or absent), erase.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)
if [ -z "${SP11_OUT:-}" ] || [ ! -d /sp11 ]; then
	exec "$here/scripts/image-container.sh" run /sp11/hardware/cameras/spectra/rpm/test-install-spectra-rpm.sh "$@"
fi
rpmf=${1:-$(ls "$SP11_OUT"/rpms-local/sp11-camera-spectra-1.0-*.aarch64.rpm | sort -V | tail -1)}
dnf -y -q --setopt=install_weak_deps=False install kmod rpm >/dev/null 2>&1 || true
kver=$(rpm -qp --requires "$rpmf" | sed -n 's/^kernel-uname-r = //p')
root=$(mktemp -d); trap 'rm -rf "$root"' EXIT
ok() { echo "PASS  $*"; }; bad() { echo "FAIL  $*"; rc=1; }; rc=0
echo "rpm: $(basename "$rpmf")  kver: $kver"
rpm -qp --requires "$rpmf" | grep -q "^kernel-uname-r = $kver\$" && ok "Requires: kernel-uname-r = $kver" || bad "kernel-uname-r requirement"
mkdir -p "$root/var/lib/rpm"; rpm --root "$root" --initdb
rpm --root "$root" -ivh --nodeps --noscripts "$rpmf" >/dev/null && ok "rpm -i into scratch root (scriptlets skipped: the root has no /bin/sh; text checked below)"
rpm -qp --scripts "$rpmf" | grep -q "depmod -a $kver" && ok "%post/%postun run depmod -a $kver" || bad "scriptlets"
mod=$root/lib/modules/$kver/extra/camera_x1e80100.ko.xz
[ -f "$mod" ] && ok "module installed in /lib/modules/$kver/extra ($(stat -c %s "$mod") bytes)" || bad "module missing"
for f in usr/libexec/sp11-camera-spectra-guard usr/lib/modprobe.d/sp11-camera-spectra.conf usr/share/doc/sp11-camera-spectra/README; do
	[ -e "$root/$f" ] && ok "file $f" || bad "file $f"; done
[ -z "$(find "$root" -name 'CAMERA_ICP*')" ] && ok "no firmware in the package" || bad "firmware found in the package"
# %post ran depmod against the (absent) real root only; run it in the scratch root
depmod -b "$root" -a "$kver" && ok "depmod -b root -a $kver"
grep -q 'extra/camera_x1e80100.ko.xz' "$root/lib/modules/$kver/modules.dep" && ok "modules.dep lists the module" || bad "modules.dep"
# udev autoload: the module's OF aliases must match Qualcomm's Spectra nodes and none of the upstream camera nodes.
# spec = node-name|compatible1|compatible2 ... ; the kernel modalias is of:N<name>T<type>C<c1>C<c2>
modalias() { local IFS='|'; set -- $1; local n=$1 out; shift; out="of:N${n}T<NULL>"; for c in "$@"; do out+="C$c"; done; echo "$out"; }
for spec in 'qcom,cam-req-mgr|qcom,cam-req-mgr' 'qcom,cam-sync|qcom,cam-sync' 'qcom,cci0|qcom,cci|simple-bus' \
            'qcom,csid0|qcom,csid695' 'qcom,csiphy1|qcom,csiphy-v2.1.2|qcom,csiphy' 'qcom,cam-sensor1|qcom,cam-sensor'; do
	hit=$(modprobe -d "$root" -S "$kver" -R "$(modalias "$spec")" 2>&1 || true)
	[ "$hit" = camera_x1e80100 ] && ok "OF alias: ${spec%%|*} autoloads camera_x1e80100" || bad "alias ${spec%%|*}: '$hit'"
done
for spec in 'isp|qcom,x1e80100-camss' 'cci|qcom,x1e80100-cci|qcom,msm8996-cci' 'camera|ovti,ov13858' 'camera|sony,imx681'; do
	hit=$(modprobe -d "$root" -S "$kver" -R "$(modalias "$spec")" 2>&1 || true)
	case $hit in *"not found"*) ok "no alias for upstream node ${spec#*|}" ;; *) bad "upstream node ${spec#*|} resolves to '$hit'" ;; esac
done
xz -dc "$mod" > "$root/m.ko"
[ "$(readelf -S "$root/m.ko" | grep -c ' \.BTF')" -ge 1 ] && ok "module has a .BTF section" || bad "no .BTF"
vm=$(modinfo -F vermagic "$root/m.ko"); case $vm in "$kver "*) ok "vermagic: $vm" ;; *) bad "vermagic $vm" ;; esac
[ "$(modinfo -F license "$root/m.ko" | sort -u)" = "GPL v2" ] && ok "license GPL v2 (every sub-driver)" || bad "license: $(modinfo -F license "$root/m.ko" | sort -u | tr '\n' ' ')"
[ -z "$(modinfo -F sig_id "$root/m.ko")" ] && ok "unsigned (as designed)" || bad "module carries a signature"
echo "modinfo depends: $(modinfo -F depends "$root/m.ko")   softdep (conf): $(grep softdep "$root/usr/lib/modprobe.d/sp11-camera-spectra.conf")"
echo "OF aliases: $(modinfo -F alias "$root/m.ko" | wc -l); aliases for qcom,cam-cpas / qcom,camera_x1e80100 (expected 0): $(modinfo -F alias "$root/m.ko" | grep -c 'cam-cpas\|camera_x1e80100')"
# guard logic: a fake device-tree root decides
dt=$root/dt; mkdir -p "$dt/soc@0/qcom,cam-cpas@ac13000"; printf 'okay\0' > "$dt/soc@0/qcom,cam-cpas@ac13000/status"
g=$root/usr/libexec/sp11-camera-spectra-guard
shim=$root/shim; mkdir -p "$shim"; printf '#!/bin/sh\necho "MODPROBE-CALLED $*" > %s/called\n' "$root" > "$shim/modprobe"; chmod +x "$shim/modprobe"
sed "s|/usr/sbin/modprobe|$shim/modprobe|" "$g" > "$root/guard"; chmod +x "$root/guard"
run() { rm -f "$root/called"; SP11_DT_ROOT=$1 "$root/guard" "$2" "$3" >/dev/null 2>&1; [ -f "$root/called" ] && echo yes || echo no; }
[ "$(run "$dt" skip-if-spectra qcom_camss)" = no ] && ok "Spectra DT active: qcom_camss refused" || bad "camss not refused on Spectra DT"
[ "$(run "$dt" load-if-spectra camera_x1e80100)" = yes ] && ok "Spectra DT active: camera_x1e80100 allowed" || bad "spectra module refused on Spectra DT"
printf 'disabled\0' > "$dt/soc@0/qcom,cam-cpas@ac13000/status"
[ "$(run "$dt" load-if-spectra camera_x1e80100)" = no ] && ok "Spectra node disabled: camera_x1e80100 refused" || bad "spectra module allowed with disabled node"
mkdir -p "$root/dt-none"
[ "$(run "$root/dt-none" load-if-spectra camera_x1e80100)" = no ] && ok "no Spectra DT: camera_x1e80100 refused" || bad "spectra module allowed without Spectra DT"
[ "$(run "$root/dt-none" skip-if-spectra qcom_camss)" = yes ] && ok "no Spectra DT: qcom_camss allowed" || bad "camss refused without Spectra DT"
# the modprobe conf as modprobe sees it
modprobe -d "$root" -S "$kver" --show-depends camera_x1e80100 2>&1 | head -n 3 | sed 's/^/  show-depends: /'
rpm --root "$root" -e --noscripts sp11-camera-spectra && ok "rpm -e" || bad "rpm -e"
[ ! -e "$mod" ] && ok "module removed by erase" || bad "module left behind"
exit $rc
