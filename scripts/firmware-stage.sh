#!/usr/bin/env bash
# Stage the DriverStore firmware listed in firmware/manifest.toml.
#
#   scripts/firmware-stage.sh [--check] [--phase N] [--src DIR] [--out DIR] [--manifest FILE]
#
# Reads every [[blob]] with origin = "driverstore" (phase <= N, default: all),
# verifies the SHA-256 of each source file, and copies it to
#   <out>/lib/firmware/<linux_path>
# Default <out> is out/firmware-root, default <src> is sources/windows
# (both are links to the main checkout in a worktree).
#
# Rules (plan/risks.md S5, agents/workers/firmware.md):
#   * Pass 1 verifies everything and writes nothing. Any missing file, any
#     SHA-256 mismatch, any pinned hash that disagrees with
#     sources/windows/MANIFEST.sha256 stops the run with exit 1.
#   * Pass 2 copies into a fresh directory and swaps it in, so a failed run never
#     leaves a half-staged tree and files dropped from the manifest disappear.
#   * origin = "linux-firmware" blobs are NOT copied: the image installs the
#     Fedora package named in [[package]] (D12). They are only listed.
#   * Never writes inside git-tracked paths. The output is refused unless it is
#     outside this repository or git-ignored.
#
# --check runs pass 1 only (no output directory is touched).
set -euo pipefail

die() { echo "firmware-stage: $*" >&2; exit 1; }

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
manifest="$repo/firmware/manifest.toml"
src="$repo/sources/windows"
out="$repo/out/firmware-root"
phase=99
check_only=0

while [ $# -gt 0 ]; do
	case "$1" in
	--check) check_only=1 ;;
	--phase) phase=${2:?--phase needs a number}; shift ;;
	--src) src=${2:?--src needs a directory}; shift ;;
	--out) out=${2:?--out needs a directory}; shift ;;
	--manifest) manifest=${2:?--manifest needs a file}; shift ;;
	-h | --help) sed -n '2,25p' "${BASH_SOURCE[0]}"; exit 0 ;;
	*) die "unknown option $1" ;;
	esac
	shift
done

[ -f "$manifest" ] || die "manifest not found: $manifest"
[ -d "$src/DriverStore" ] || die "no DriverStore under $src"
[ -f "$src/MANIFEST.sha256" ] || die "no MANIFEST.sha256 under $src"
case "$phase" in '' | *[!0-9]*) die "--phase must be a number" ;; esac
command -v sha256sum >/dev/null || die "sha256sum not found"
command -v python3 >/dev/null || die "python3 (tomllib) not found"

# Output location: must not be a tracked path of this repository.
out_created=0
[ -d "$out" ] || out_created=1
mkdir -p "$out"
out_real=$(cd "$out" && pwd -P)
refuse_out() {
	[ "$out_created" -eq 0 ] || rmdir "$out_real" 2>/dev/null || true
	die "$*"
}
repo_real=$(cd "$repo" && pwd -P)
case "$out_real/" in
"$repo_real"/*)
	git -C "$repo" check-ignore -q "$out_real" 2>/dev/null ||
		refuse_out "refusing to write firmware inside the repository at a path git does not ignore: $out_real"
	;;
esac
case "$(basename "$out_real")" in
firmware-root) ;;
*) refuse_out "output directory must be named firmware-root (got $out_real); the script replaces its contents" ;;
esac

# Manifest -> TSV: linux_path, source, sha256, id. Fedora blobs are listed on stderr.
rows=$(python3 -I - "$manifest" "$phase" <<'PY'
import sys, tomllib, re
path, maxphase = sys.argv[1], int(sys.argv[2])
with open(path, "rb") as f:
    m = tomllib.load(f)
seen = set()
for b in m.get("blob", []):
    if b.get("phase", 1) > maxphase:
        continue
    i = b.get("id", "?")
    if b.get("origin") == "linux-firmware":
        print("FEDORA\t%s\t%s\t%s" % (b["linux_path"], b.get("package", "?"), i))
        continue
    if b.get("origin") != "driverstore":
        print("ERROR\t%s\tunknown origin %r" % (i, b.get("origin")))
        continue
    lp, s, h = b.get("linux_path", ""), b.get("source", ""), b.get("sha256", "")
    problems = []
    if not lp or lp.startswith("/") or ".." in lp.split("/") or re.search(r"[\t\n]", lp):
        problems.append("bad linux_path %r" % lp)
    if lp in seen:
        problems.append("duplicate linux_path")
    seen.add(lp)
    if not s.startswith("DriverStore/") or ".." in s.split("/") or re.search(r"[\t\n]", s):
        problems.append("bad source %r" % s)
    if not re.fullmatch(r"[0-9a-f]{64}", h):
        problems.append("sha256 is not 64 lowercase hex")
    if problems:
        print("ERROR\t%s\t%s" % (i, "; ".join(problems)))
        continue
    print("STAGE\t%s\t%s\t%s\t%s" % (lp, s, h, i))
for p in m.get("package", []):
    print("PACKAGE\t%s\t%s\t%s" % (p.get("name", "?"), p.get("fedora_release", "?"), p.get("fedora_updates", "?")))
PY
) || die "cannot parse $manifest"

errors=0
fail() { echo "ERROR  $*" >&2; errors=$((errors + 1)); }

stage_list=$(mktemp)
trap 'rm -f "$stage_list"; [ -n "${newdir:-}" ] && rm -rf "$newdir"' EXIT

# ---- pass 1: verify, write nothing ----------------------------------------
n=0
while IFS=$'\t' read -r kind a b c d; do
	case "$kind" in
	ERROR) fail "manifest entry $a: $b" ;;
	FEDORA) echo "fedora  $a  (package $b, not copied)" ;;
	PACKAGE) echo "package $a  release=$b  updates=$c  (image installs it)" ;;
	STAGE)
		lp=$a s=$b h=$c id=$d
		f="$src/$s"
		if [ ! -f "$f" ] || [ -L "$f" ]; then
			fail "$id: missing or not a regular file: $s"
			continue
		fi
		got=$(sha256sum "$f" | cut -d' ' -f1)
		if [ "$got" != "$h" ]; then
			fail "$id: SHA-256 mismatch for $s (manifest $h, file $got)"
			continue
		fi
		# The pinned hash must also agree with the DriverStore's own MANIFEST.sha256.
		pinned=$(awk -v p="./$s" '$2 == p { print $1 }' "$src/MANIFEST.sha256")
		if [ "$pinned" != "$h" ]; then
			fail "$id: $s is not in $src/MANIFEST.sha256 with this hash (found '${pinned:-none}')"
			continue
		fi
		printf '%s\t%s\t%s\t%s\n' "$lp" "$s" "$h" "$id" >>"$stage_list"
		n=$((n + 1))
		echo "ok      $id  $lp  $h"
		;;
	esac
done <<<"$rows"

[ "$errors" -eq 0 ] || die "$errors problem(s); nothing was written"
[ "$n" -gt 0 ] || die "no driverstore blob selected (phase <= $phase); nothing to stage"

if [ "$check_only" -eq 1 ]; then
	echo "firmware-stage: --check: $n file(s) verified, nothing written"
	exit 0
fi

# ---- pass 2: copy into a fresh tree, verify the copies, swap ---------------
newdir=$(mktemp -d "$out_real.new.XXXXXX")
while IFS=$'\t' read -r lp s h id; do
	dest="$newdir/lib/firmware/$lp"
	mkdir -p "$(dirname "$dest")"
	cp -- "$src/$s" "$dest"
	chmod 0644 "$dest"
	got=$(sha256sum "$dest" | cut -d' ' -f1)
	[ "$got" = "$h" ] || die "$id: copy does not match after writing ($dest)"
	printf '%s  lib/firmware/%s\n' "$h" "$lp" >>"$newdir/STAGED.sha256"
done <"$stage_list"
chmod 0644 "$newdir/STAGED.sha256"
chmod 0755 "$newdir"

# Replace the old contents (generated data only; name checked above).
find "$out_real" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a -- "$newdir"/. "$out_real"/
rm -rf "$newdir"
newdir=

( cd "$out_real" && sha256sum --quiet -c STAGED.sha256 ) || die "final verification of $out_real failed"
echo "firmware-stage: staged $n file(s) into $out_real/lib/firmware (STAGED.sha256 written, verified)"
