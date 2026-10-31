#!/usr/bin/env bash
# Build sp11-camera-spectra (camera_x1e80100.ko out of tree) as an RPM with Fedora tools; outputs under out/.
#
#   hardware/cameras/spectra/rpm/build-spectra-rpm.sh [KVER]
#
# KVER defaults to the newest kernel-devel in out/rpms (7.3.0-65.sp11.11.fc44.aarch64 today). The matching
# kernel-devel and kernel-debuginfo RPMs of that directory are installed in the container (BTF for the module needs
# the kernel's vmlinux). Inputs: out/ref/camera-driver at commit 08171dd (git archive) and
# hardware/cameras/spectra/patches/*.patch. Output: out/rpms-local/sp11-camera-spectra-*.rpm (+ .src.rpm, .json),
# never out/rpms (that directory holds the kernel release RPMs only).
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)
if [ -z "${SP11_OUT:-}" ] || [ ! -d /sp11 ]; then
	exec env SP11_DOCKER_MEMORY=8g "$here/scripts/image-container.sh" run /sp11/hardware/cameras/spectra/rpm/build-spectra-rpm.sh "$@"
fi
COMMIT=08171ddc9d6ad81c13e6f1b362248d4736b0e804
SRCDIR=/sp11/hardware/cameras/spectra
if [ $# -ge 1 ]; then kver=$1; else
	kver=$(ls "$SP11_OUT"/rpms/kernel-devel-[0-9]*.aarch64.rpm | sed -E 's|.*/kernel-devel-||; s|\.rpm$||' | sort -V | tail -1)
fi
[ -f "$SP11_OUT/rpms/kernel-devel-$kver.rpm" ] && [ -f "$SP11_OUT/rpms/kernel-debuginfo-$kver.rpm" ] || { echo "build-spectra-rpm: kernel-devel/kernel-debuginfo $kver missing in out/rpms" >&2; exit 1; }
work=$SP11_OUT/image-work/camera-spectra
rm -rf "$work"; mkdir -p "$work"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
cd "$work"
git config --global --add safe.directory "$SP11_OUT/ref/camera-driver"
git -C "$SP11_OUT/ref/camera-driver" cat-file -e "$COMMIT^{commit}"
git -C "$SP11_OUT/ref/camera-driver" archive --format=tar --prefix=camera-driver-08171dd/ "$COMMIT" | gzip -n > SOURCES/camera-driver-08171dd.tar.gz
cp "$SRCDIR"/patches/*.patch SOURCES/
cp "$SRCDIR"/rpm/sp11-camera-spectra-guard SOURCES/
cp "$SRCDIR"/rpm/sp11-camera-spectra.modprobe.conf SOURCES/
cp "$SRCDIR"/rpm/sp11-camera-spectra-README SOURCES/
cp "$SRCDIR"/rpm/sp11-camera-spectra.spec SPECS/
dnf -y --setopt=install_weak_deps=False install rpm-build rpmlint rpmdevtools dwarves gcc make xz elfutils-libelf-devel kmod git \
	"$SP11_OUT/rpms/kernel-devel-$kver.rpm" "$SP11_OUT/rpms/kernel-debuginfo-$kver.rpm" \
	"$SP11_OUT/rpms/kernel-debuginfo-common-aarch64-$kver.rpm" >dnf.log 2>&1 || { tail -n 30 dnf.log; exit 1; }
rpmbuild --define "_topdir $work" --define 'dist .sp11.fc44' --define "kver $kver" --define '_smp_mflags -j4' \
	-ba SPECS/sp11-camera-spectra.spec >build.log 2>&1 || { tail -n 60 build.log; exit 1; }
rpm=$(ls RPMS/aarch64/sp11-camera-spectra-1.0-*.aarch64.rpm); srpm=$(ls SRPMS/sp11-camera-spectra-1.0-*.src.rpm)
mkdir -p "$SP11_OUT/rpms-local"
cp "$rpm" "$srpm" "$SP11_OUT/rpms-local/"
rpmlint "$rpm" >rpmlint.log 2>&1 || true
python3 -I - "$work" "$SP11_OUT/rpms-local" "$kver" "$COMMIT" "$(basename "$rpm")" "$(basename "$srpm")" <<'PY'
import hashlib, json, pathlib, subprocess, sys
work, out, kver, commit, rpm, srpm = sys.argv[1:7]
work, out = pathlib.Path(work), pathlib.Path(out)
d = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
rec = {'rpm': rpm, 'rpm_sha256': d(out / rpm), 'srpm': srpm, 'srpm_sha256': d(out / srpm), 'kver': kver,
       'camera_driver_commit': commit, 'source_tarball_sha256': d(work / 'SOURCES/camera-driver-08171dd.tar.gz'),
       'patches': {p.name: d(p) for p in sorted((work / 'SOURCES').glob('000*.patch'))},
       'spec_sha256': d(work / 'SPECS/sp11-camera-spectra.spec'),
       'files': subprocess.check_output(['rpm', '-qlp', str(out / rpm)], text=True).split(),
       'requires': subprocess.check_output(['rpm', '-qp', '--requires', str(out / rpm)], text=True).split('\n')[:-1],
       'rpmlint': (work / 'rpmlint.log').read_text().strip().splitlines()[-1],
       'signed': False, 'firmware_in_rpm': False}
(out / (rpm[:-4] + '.json')).write_text(json.dumps(rec, indent=2) + '\n')
print(json.dumps(rec, indent=2))
PY
chown -R "${SP11_UID:-0}:${SP11_GID:-0}" "$SP11_OUT/rpms-local" "$work" 2>/dev/null || true
