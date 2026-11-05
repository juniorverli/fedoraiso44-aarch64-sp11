#!/usr/bin/env bash
# Build the local sensor RPMs (hexagonrpcd, libssc, libssc-devel, libssc-tools, iio-sensor-proxy, sp11-sensors) with
# Fedora tools in the image container. Outputs go to out/rpms-local/ (out/rpms belongs to the kernel and iptsd).
# Same pattern as scripts/image-build-iptsd.sh: container run, sources pinned by SHA-256, builddep, rpmbuild.
#   hardware/sensors/userspace/build-sensors-rpms.sh            build all
#   hardware/sensors/userspace/build-sensors-rpms.sh check      rpmlint + file lists of the built RPMs
#   hardware/sensors/userspace/build-sensors-rpms.sh install    install test in a scratch root (dnf --installroot)
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
step=${1:-build}
if [ -z "${SP11_OUT:-}" ] || [ ! -d /sp11 ]; then
	exec env SP11_DOCKER_MEMORY=4g "$here/scripts/image-container.sh" run /sp11/hardware/sensors/userspace/build-sensors-rpms.sh "$step"
fi
rel=${SP11_FEDORA_RELEASE:-44}
ud=/sp11/hardware/sensors/userspace
work=$SP11_OUT/image-work/sensors-rpms
rpms=$SP11_OUT/rpms-local
mkdir -p "$work"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} "$rpms"
cd "$work"

check_step() {
	dnf -y -q --setopt=install_weak_deps=False install rpmlint >/dev/null
	for r in "$rpms"/*.rpm; do
		case "$r" in *.src.rpm) continue ;; esac
		echo "=== $(basename "$r")"
		rpm -qpl "$r"
		rpm -qp --requires "$r" | sort -u | sed 's/^/  requires: /'
	done
	# The specs are checked as well; warnings are listed, not hidden.
	rpmlint "$rpms"/*.rpm "$work"/SPECS/*.spec 2>&1 | tail -n 80 || true
}

pick() { ls "$rpms"/$1 | grep -v -E 'debug|\.src\.rpm$'; }

install_step() {
	root=$work/scratch-root
	rm -rf "$root"; mkdir -p "$root"
	# Real transaction with dependency resolution, scriptlets and sysusers, in a scratch root. The RPMs are
	# unsigned local builds, so gpg checks are off for them only.
	dnf -y --installroot="$root" --releasever="$rel" --use-host-config --setopt=install_weak_deps=False --nogpgcheck \
		install $(pick 'hexagonrpcd-0.5.0-*.rpm') $(pick 'libssc-0.4.4-*.rpm') $(pick 'libssc-tools-*.rpm') \
		$(pick 'iio-sensor-proxy-3.9-*.rpm') $(pick 'sp11-sensors-*.rpm') 2>&1 | tail -n 25
	echo "--- files by package"
	for p in hexagonrpcd libssc libssc-tools iio-sensor-proxy sp11-sensors; do
		echo "== $p"; rpm --root "$root" -ql "$p" | grep -v -E '/usr/share/(doc|licenses|man)/'
	done
	echo "--- user and group"
	grep -E '^(hexagonrpcd|fastrpc):' "$root/etc/passwd" "$root/etc/group" || echo "(missing)"
	echo "--- preset results"
	for u in hexagonrpcd-sensors.service hexagonrpcd-sensors-sleep.service iio-sensor-proxy.service; do
		echo "$u: $(systemctl --root="$root" is-enabled "$u" 2>&1)"
	done
	echo "--- unit verification"
	systemd-analyze --root="$root" verify hexagonrpcd-sensors.service hexagonrpcd-sensors-sleep.service iio-sensor-proxy.service 2>&1 | head -n 30 || true
	echo "--- udev rules verification"
	udevadm verify --root="$root" /usr/lib/udev/rules.d/61-sp11-fastrpc-adsp.rules /usr/lib/udev/rules.d/80-iio-sensor-proxy.rules /usr/lib/udev/rules.d/81-sp11-iio-sensor-proxy-ssc.rules 2>&1 | tail -n 15 || true
	echo "--- D-Bus policy and polkit"
	ls -l "$root"/usr/share/dbus-1/system.d/net.hadess.SensorProxy.conf "$root"/usr/share/polkit-1/actions/net.hadess.SensorProxy.policy
	echo "--- binaries link"
	chroot "$root" ldd /usr/bin/hexagonrpcd /usr/bin/sscregistrygen /usr/bin/ssccli /usr/libexec/iio-sensor-proxy 2>&1 | grep -E 'not found|=> not' || echo "all libraries resolve"
	echo "--- iio-sensor-proxy has SSC support"
	strings "$root"/usr/libexec/iio-sensor-proxy | grep -E -c 'ssc-(accel|light|compass)'
	echo "--- no Windows or Qualcomm payload in the RPMs"
	for r in $(pick 'hexagonrpcd-0.5.0-*.rpm') $(pick 'libssc-*.rpm') $(pick 'iio-sensor-proxy-3.9-*.rpm') $(pick 'sp11-sensors-*.rpm'); do rpm -qpl "$r"; done | grep -E -i '\.(mbn|jsn|bin|pb)$|qcom/x1e80100|DriverStore' || echo "none"
}

case "$step" in check) check_step; exit 0 ;; install) install_step; exit 0 ;; build) ;; *) echo "usage: $0 [build|check|install]" >&2; exit 2 ;; esac

# --- pins: sources/sources.toml first, then the provisional table next to this script -----------------------
python3 -I - /sp11/sources/sources.toml "$ud/rpm/pins.toml" <<'PY' >pins.txt
import sys, tomllib
central = tomllib.load(open(sys.argv[1], 'rb'))
local = tomllib.load(open(sys.argv[2], 'rb'))
for name in ('hexagonrpcd', 'libssc', 'iio-sensor-proxy'):
    if name in central:
        pins, where = central[name], 'sources/sources.toml'
    else:
        pins, where = local[name], 'rpm/pins.toml (PROVISIONAL: ask the sources worker to pin it)'
    for key in ('version', 'archive_url', 'archive_sha256', 'upstream_commit'):
        assert pins[key] and '\n' not in pins[key], (name, key)
    assert len(pins['archive_sha256']) == 64
    print('\t'.join([name, pins['version'], pins['archive_url'], pins['archive_sha256'], pins['upstream_commit'], where]))
PY
fetch() { # name file
	local line; line=$(awk -F'\t' -v n="$1" '$1==n' pins.txt)
	IFS=$'\t' read -r _ ver url sha commit where <<<"$line"
	echo "pin $1 $ver from $where" >&2
	curl --fail --location --retry 3 -s "$url" -o "SOURCES/$2"
	printf '%s  %s\n' "$sha" "SOURCES/$2" | sha256sum -c - >&2
}
fetch hexagonrpcd hexagonrpc-0.5.0.tar.gz
fetch libssc libssc-0.4.4.tar.gz
fetch iio-sensor-proxy iio-sensor-proxy-3.9.tar.bz2

cp "$ud"/rpm/*.spec SPECS/
cp "$ud"/rpm/hexagonrpc-000*.patch "$ud/rpm/50-sp11-sensors.preset" SOURCES/
cp "$ud/hexagonrpcd.sysusers" "$ud/units/hexagonrpcd-sensors.service" "$ud/units/hexagonrpcd-sensors-sleep.service" \
   "$ud/units/61-sp11-fastrpc-adsp.rules" "$ud/units/81-sp11-iio-sensor-proxy-ssc.rules" "$ud/sp11-sensors-test" \
   "$ud/collector/sensors.sh" SOURCES/
cp "$ud/units/iio-sensor-proxy-sp11.conf" SOURCES/iio-sensor-proxy-sp11.conf
cp "$ud/rpm/sp11-sensors-README" SOURCES/

# Fedora's own package must not silently win or be shadowed: report what Fedora offers.
dnf -q repoquery --available --queryformat '%{name}-%{evr}.%{arch}' hexagonrpcd libssc iio-sensor-proxy >fedora-query.txt || true
cat fedora-query.txt

dnf -y --setopt=install_weak_deps=False install dnf5-plugins rpm-build >/dev/null
rb() { # spec
	rpmbuild --define "_topdir $work" --define "dist .fc$rel" --define '_smp_mflags -j2' -ba "SPECS/$1" >"build-${1%.spec}.log" 2>&1 || {
		tail -n 60 "build-${1%.spec}.log"; exit 1; }
	echo "built $1"
}
for s in libssc hexagonrpcd; do
	dnf -y --setopt=install_weak_deps=False builddep "SPECS/$s.spec" >/dev/null
done
rb libssc.spec
# iio-sensor-proxy builds against the libssc just built
dnf -y --setopt=install_weak_deps=False --nogpgcheck install RPMS/aarch64/libssc-0.4.4-*.rpm RPMS/aarch64/libssc-devel-0.4.4-*.rpm >/dev/null
for s in iio-sensor-proxy sp11-sensors; do
	dnf -y --setopt=install_weak_deps=False builddep "SPECS/$s.spec" >/dev/null
done
rb hexagonrpcd.spec
rb iio-sensor-proxy.spec
rb sp11-sensors.spec

# Only this component's outputs: out/rpms-local is shared with the Spectra module and others,
# and wiping the whole directory silently removed them.
rm -f "$rpms"/{libssc,libssc-tools,libssc-devel,hexagonrpcd,iio-sensor-proxy,sp11-sensors}-[0-9]*.rpm "$rpms"/sensors-rpms.json
cp RPMS/aarch64/*.rpm RPMS/noarch/*.rpm "$rpms"/
cp SRPMS/*.src.rpm "$rpms"/
python3 -I - "$work" "$rpms" "$ud" <<'PY'
import hashlib, json, pathlib, subprocess, sys
work, rpms, ud = map(pathlib.Path, sys.argv[1:])
digest = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
pins = [l.split('\t') for l in (work / 'pins.txt').read_text().splitlines()]
record = {
    'rpms': {p.name: digest(p) for p in sorted(rpms.glob('*.rpm'))},
    'sources': {n: {'version': v, 'url': u, 'sha256': s, 'upstream_commit': c, 'pinned_in': w} for n, v, u, s, c, w in pins},
    'specs': {p.name: digest(p) for p in sorted((work / 'SPECS').glob('*.spec'))},
    'patches': {p.name: digest(p) for p in sorted((work / 'SOURCES').glob('*.patch'))},
    'fedora_query': (work / 'fedora-query.txt').read_text().split(),
    'build_packages': subprocess.check_output(['rpm', '-qa'], text=True).splitlines(),
    'tests': 'hexagonrpcd: meson test (iobuffer, hexagonfs incl. write test) in %check; libssc and iio-sensor-proxy: no tests run (QRTR loopback and umockdev are not available in the container)',
}
(rpms / 'sensors-rpms.json').write_text(json.dumps(record, indent=2) + '\n')
PY
echo "sensor RPMs and record: $rpms"
ls -l "$rpms"
