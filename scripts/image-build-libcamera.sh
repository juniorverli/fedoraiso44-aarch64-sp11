#!/usr/bin/env bash
# Build a LOCAL libcamera RPM from Fedora's own libcamera source package (0.7.2) plus the cameras owner's two patches
# (hardware/cameras/userspace/quality/libcamera-sp11.patch, then libcamera-sp11-imx681-helper.patch). Outputs stay under out/rpms-local/.
# The release carries ".sp11" so it sorts above Fedora's "2.fc44" and a Fedora update cannot replace it silently.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [ -z "${SP11_OUT:-}" ] || [ ! -d /sp11 ]; then
	exec env SP11_DOCKER_MEMORY=8g "$here/scripts/image-container.sh" run /sp11/scripts/image-build-libcamera.sh
fi
work=$SP11_OUT/image-work/libcamera
rm -rf "$work"; mkdir -p "$work"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS,dl}
cd "$work"
dnf -y --setopt=install_weak_deps=False install dnf5-plugins rpm-build rpmdevtools >dnf0.log 2>&1 || { tail -n 20 dnf0.log; exit 1; }
dnf download --source --destdir dl libcamera >dl.log 2>&1 || { tail -n 20 dl.log; exit 1; }
srpm=$(ls dl/libcamera-0.7.2-*.src.rpm)
rpm -ivh --define "_topdir $work" "$srpm" >/dev/null
spec=SPECS/libcamera.spec
q=/sp11/hardware/cameras/userspace/quality
cp "$q/libcamera-sp11.patch" "$q/libcamera-sp11-imx681-helper.patch" SOURCES/
grep -q '^%autosetup' "$spec" || { echo "spec has no %autosetup; cannot add patches" >&2; exit 1; }
grep -qE '^Release:[[:space:]]+[0-9]+%\{\?dist\}' "$spec" || { echo "unexpected Release line" >&2; grep -n '^Release' "$spec" >&2; exit 1; }
lastsrc=$(grep -nE '^(Source|Patch)[0-9]*:' "$spec" | tail -n1 | cut -d: -f1)
sed -i "${lastsrc}a Patch9001: libcamera-sp11.patch\nPatch9002: libcamera-sp11-imx681-helper.patch" "$spec"
sed -i -E 's/^(Release:[[:space:]]+[0-9]+)%\{\?dist\}/\1.sp11%{?dist}/' "$spec"
dnf -y --setopt=install_weak_deps=False builddep "$spec" >builddep.log 2>&1 || { tail -n 30 builddep.log; exit 1; }
rpmbuild --define "_topdir $work" --define '_smp_mflags -j6' -ba "$spec" >build.log 2>&1 || { tail -n 60 build.log; exit 1; }
mkdir -p "$SP11_OUT/rpms-local/libcamera"
rm -f "$SP11_OUT"/rpms-local/libcamera/*.rpm
cp RPMS/*/*.rpm "$SP11_OUT/rpms-local/libcamera/"
cp "$work"/SRPMS/*.src.rpm "$SP11_OUT/rpms-local/libcamera/"
python3 -I - "$work" "$SP11_OUT/rpms-local/libcamera" "$srpm" <<'PY'
import hashlib, json, pathlib, sys
work, out, srpm = map(pathlib.Path, sys.argv[1:4])
d = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
rec = {'fedora_source_rpm': srpm.name, 'fedora_source_rpm_sha256': d(srpm),
       'patches': {p: d(work / 'SOURCES' / p) for p in ('libcamera-sp11.patch', 'libcamera-sp11-imx681-helper.patch')},
       'rpms': {p.name: d(p) for p in sorted(out.glob('*.rpm'))}}
(out / 'libcamera-sp11-build.json').write_text(json.dumps(rec, indent=1) + '\n')
print(len(rec['rpms']), 'rpms')
PY
chown -R "${SP11_UID:-0}:${SP11_GID:-0}" "$SP11_OUT/rpms-local" "$work" 2>/dev/null || true
echo "libcamera local RPMs in $SP11_OUT/rpms-local/libcamera"
