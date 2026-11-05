#!/usr/bin/env bash
# Verify that the pushed integration branch equals kernel/series applied to the
# pinned base. The branch is the reviewable mirror; the series is what the
# Fedora kernel.spec applies. They must never drift.
#
#   scripts/kernel-series-branch-check.sh
#
# Needs the local clone at sources/linux (the same clone kernel-build.sh uses)
# and the base/branch pins in kernel/base.toml. Prints PASS/FAIL only.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
toml() { sed -n -E "s/^$1[[:space:]]*=[[:space:]]*\"?([^\"#]*[^\"# ])\"?[[:space:]]*(#.*)?$/\1/p" "$here/kernel/base.toml" | head -1; }
base=$(toml commit)
branch=$(toml branch)
clone=${SP11_LINUX_CLONE:-$here/sources/linux}

[[ -n $base && -n $branch ]] || { echo "FAIL: kernel/base.toml lacks commit or branch" >&2; exit 1; }
git -C "$clone" rev-parse --verify --quiet "$base^{commit}" >/dev/null || { echo "FAIL: base $base not in $clone" >&2; exit 1; }
git -C "$clone" rev-parse --verify --quiet "$branch^{commit}" >/dev/null || { echo "FAIL: branch $branch not in $clone" >&2; exit 1; }

tmp=$(mktemp -d)
cleanup() { git -C "$clone" worktree remove --force "$tmp" >/dev/null 2>&1 || rm -rf "$tmp"; }
trap cleanup EXIT
git -C "$clone" worktree add --quiet --detach "$tmp" "$base"
mapfile -t patches < <(grep -v '^#' "$here/kernel/series" | grep -v '^[[:space:]]*$')
for p in "${patches[@]}"; do
	if ! git -C "$tmp" apply --whitespace=nowarn "$here/$p" 2>/tmp/series-branch-apply.err; then
		echo "FAIL: series patch does not apply to the base: $p" >&2
		head -n3 /tmp/series-branch-apply.err >&2
		exit 1
	fi
done
git -C "$tmp" add -A
if git -C "$tmp" diff --cached --quiet "$branch"; then
	echo "PASS: kernel/series applied to $base equals branch $branch ($(git -C "$clone" rev-parse --short "$branch"))"
	exit 0
fi
echo "FAIL: the branch differs from the series:" >&2
git -C "$tmp" diff --cached --stat "$branch" | head -n 20 >&2
exit 1
