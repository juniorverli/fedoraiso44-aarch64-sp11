#!/usr/bin/env bash
# Build the local iptsd RPM with Fedora tools; all outputs remain under out/.
# Source ownership: sources must centrally pin the archive/spec before this runs.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [ -z "${SP11_OUT:-}" ] || [ ! -d /sp11 ]; then
	exec env SP11_DOCKER_MEMORY=4g "$here/scripts/image-container.sh" run /sp11/scripts/image-build-iptsd.sh
fi
work=$SP11_OUT/image-work/iptsd
mkdir -p "$work"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
cd "$work"
# Consume the sources owner's table directly and validate the approved release
# before fetching either input. Failure cannot fall through to unpinned URLs.
python3 -I - /sp11/sources/sources.toml <<'PY' >pins.txt
import sys, tomllib
pins = tomllib.load(open(sys.argv[1], 'rb'))['iptsd']
assert pins['version'] == '3.1.0', 'local spec requires iptsd 3.1.0'
assert pins['archive_sha256'] == 'af0aab95387a5107dfa8ac1ef90a29289f6b9d06e1a59121c9e5e732b27a266c'
assert pins['upstream_commit'] == 'a83bc1232f7096f8b33b50fdbda249cd640de670'
assert pins['spec_sha256'] == '4231cb05325ce733eff4228ed8b8b00ac74238f01e02813a9ee2cd8b6ab0acf7'
for key in ('archive_url', 'archive_sha256', 'spec_url', 'spec_sha256'):
    value = pins[key]
    assert value and '\n' not in value
    print(value)
PY
mapfile -t pins <pins.txt
source_url=${pins[0]}
source_sha=${pins[1]}
spec_url=${pins[2]}
spec_sha=${pins[3]}
curl --fail --location --retry 3 "$source_url" -o SOURCES/v3.1.0.tar.gz
printf '%s  %s\n' "$source_sha" SOURCES/v3.1.0.tar.gz | sha256sum -c -
curl --fail --location --retry 3 "$spec_url" -o upstream.spec
printf '%s  %s\n' "$spec_sha" upstream.spec | sha256sum -c -
cp /sp11/image/iptsd/iptsd.spec SPECS/
# Recheck Fedora's official repositories. Never silently substitute a third-party RPM.
dnf -q repoquery --available --queryformat '%{name}-%{evr}.%{arch}' iptsd >fedora-query.txt
if [ -s fedora-query.txt ]; then
	echo 'An official Fedora iptsd package is now available; use it instead of this local build.' >&2
	exit 2
fi
dnf -y --setopt=install_weak_deps=False install dnf5-plugins
dnf -y --setopt=install_weak_deps=False builddep SPECS/iptsd.spec
rel=${SP11_FEDORA_RELEASE:-44}
rpmbuild --define "_topdir $work" --define "dist .fc$rel" --define '_smp_mflags -j2' -ba SPECS/iptsd.spec >build.log 2>&1 || {
	tail -n 60 build.log; exit 1;
}
rpmfile=$work/RPMS/aarch64/iptsd-3.1.0-1.fc${rel}.aarch64.rpm
test -s "$rpmfile"
mkdir -p "$SP11_OUT/rpms"
cp "$rpmfile" "$SP11_OUT/rpms/"
python3 -I - "$work" "$SP11_OUT/rpms" "$rel" <<'PY'
import hashlib, json, pathlib, subprocess, sys
work, rpms = map(pathlib.Path, sys.argv[1:3])
rel = sys.argv[3]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rpm = rpms / f'iptsd-3.1.0-1.fc{rel}.aarch64.rpm'
record = {'nevra': rpm.stem, 'rpm_sha256': digest(rpm),
          'source_url': 'https://github.com/linux-surface/iptsd/archive/refs/tags/v3.1.0.tar.gz',
          'source_sha256': digest(work / 'SOURCES/v3.1.0.tar.gz'),
          'upstream_commit': 'a83bc1232f7096f8b33b50fdbda249cd640de670',
          'upstream_spec_sha256': digest(work / 'upstream.spec'),
          'local_spec_sha256': digest(work / 'SPECS/iptsd.spec'),
          'central_pins_sha256': digest(pathlib.Path('/sp11/sources/sources.toml')),
          'build_packages': subprocess.check_output(['rpm', '-qa'], text=True).splitlines(),
          'activation': '50-iptsd.rules SYSTEMD_WANTS -> iptsd@<escaped-hidraw-path>.service',
          'config': 'unmodified upstream defaults and presets; metadata-driven dimensions',
          'meson_test': 'Completed successfully; upstream defines no tests; see out/image-work/iptsd/build.log'}
(rpms / (rpm.stem + '.json')).write_text(json.dumps(record, indent=2) + '\n')
PY
echo "iptsd RPM and record: $SP11_OUT/rpms/iptsd-3.1.0-1.fc${rel}.aarch64.{rpm,json}"
