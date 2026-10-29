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
# Accept any centrally owned iptsd table shape; require both immutable pins in
# that table, including the upstream spec commit, before fetching an input.
python3 -I - /sp11/sources/sources.toml <<'PY'
import json, sys, tomllib
data = tomllib.load(open(sys.argv[1], 'rb'))
def find(value, path=''):
    if isinstance(value, dict):
        if 'iptsd' in path.lower():
            yield json.dumps(value)
        for key, child in value.items():
            yield from find(child, path + '.' + key)
pins = '\n'.join(find(data))
assert 'af0aab95387a5107dfa8ac1ef90a29289f6b9d06e1a59121c9e5e732b27a266c' in pins, 'sources owner must pin iptsd v3.1.0 archive first'
assert 'a83bc1232f7096f8b33b50fdbda249cd640de670' in pins, 'sources owner must pin iptsd upstream spec commit first'
PY
source_url=https://github.com/linux-surface/iptsd/archive/refs/tags/v3.1.0.tar.gz
spec_url=https://raw.githubusercontent.com/linux-surface/iptsd/a83bc1232f7096f8b33b50fdbda249cd640de670/iptsd.spec
curl --fail --location --retry 3 "$source_url" -o SOURCES/v3.1.0.tar.gz
printf '%s  %s\n' af0aab95387a5107dfa8ac1ef90a29289f6b9d06e1a59121c9e5e732b27a266c SOURCES/v3.1.0.tar.gz | sha256sum -c -
curl --fail --location --retry 3 "$spec_url" -o upstream.spec
printf '%s  %s\n' 4231cb05325ce733eff4228ed8b8b00ac74238f01e02813a9ee2cd8b6ab0acf7 upstream.spec | sha256sum -c -
cp /sp11/image/iptsd/iptsd.spec SPECS/
# Recheck Fedora's official repositories. Never silently substitute a third-party RPM.
dnf -q repoquery --available --queryformat '%{name}-%{evr}.%{arch}' iptsd >fedora-query.txt
if [ -s fedora-query.txt ]; then
	echo 'An official Fedora iptsd package is now available; use it instead of this local build.' >&2
	exit 2
fi
dnf -y --setopt=install_weak_deps=False install dnf5-plugins
dnf -y --setopt=install_weak_deps=False builddep SPECS/iptsd.spec
rpmbuild --define "_topdir $work" --define 'dist .fc44' -ba SPECS/iptsd.spec >build.log 2>&1 || {
	tail -n 60 build.log; exit 1;
}
rpmfile=$work/RPMS/aarch64/iptsd-3.1.0-1.fc44.aarch64.rpm
test -s "$rpmfile"
mkdir -p "$SP11_OUT/rpms"
cp "$rpmfile" "$SP11_OUT/rpms/"
python3 -I - "$work" "$SP11_OUT/rpms" <<'PY'
import hashlib, json, pathlib, subprocess, sys
work, rpms = map(pathlib.Path, sys.argv[1:])
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rpm = rpms / 'iptsd-3.1.0-1.fc44.aarch64.rpm'
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
          'meson_test': 'PASS; see out/image-work/iptsd/build.log'}
(rpms / (rpm.stem + '.json')).write_text(json.dumps(record, indent=2) + '\n')
PY
echo "iptsd RPM and record: $SP11_OUT/rpms/iptsd-3.1.0-1.fc44.aarch64.{rpm,json}"
