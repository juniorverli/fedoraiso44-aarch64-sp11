#!/usr/bin/bash
set -euo pipefail
export LC_ALL=C PATH=/usr/sbin:/usr/bin:/sbin:/bin

repo=$(cd "$(dirname "$0")/../.." && pwd)
helper=$repo/image/component-inputs/private-sensors/seed-private-sensor-registry
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
src=$tmp/source
state=$tmp/state
mkdir -m 0700 "$src" "$state"
mkdir -m 0750 "$state/registry"
printf 'seed-one\n' >"$src/first"
printf 'seed-two\n' >"$src/second"
chmod 0600 "$src/first" "$src/second"
user=$(id -un)
group=$(id -gn)

"$helper" "$src" "$state/registry" "$user" "$group"
for name in first second; do
	cmp "$src/$name" "$state/registry/$name"
	test "$(stat -c %a "$state/registry/$name")" = 640
	test "$(stat -c %U:%G "$state/registry/$name")" = "$user:$group"
done
test "$(stat -c %a "$state/registry")" = 750
touch "$state/registry/preexisting"
chmod 0640 "$state/registry/preexisting"
before=$(sha256sum "$state/registry/preexisting")
"$helper" "$src" "$state/registry" "$user" "$group" | grep -q 'existing registry preserved'
test "$before" = "$(sha256sum "$state/registry/preexisting")"

ln -s first "$src/unsafe-link"
mkdir -m 0750 "$tmp/symlink-destination"
if "$helper" "$src" "$tmp/symlink-destination" "$user" "$group" >/dev/null 2>&1; then
	echo 'FAIL helper accepted a symlink seed' >&2
	exit 1
fi
echo 'PASS private sensor seeder copies owner/group/mode, preserves populated state, rejects symlink seeds'
