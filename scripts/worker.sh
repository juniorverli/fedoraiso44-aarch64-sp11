#!/usr/bin/env bash
# Prepare the worktrees of one worker and print how to launch it.
#   scripts/worker.sh <id> [--kernel]
# Project worktree: ../sp11-fedora.worktrees/<id>, branch worker/<id> (from main).
# Kernel worktree (--kernel): out/linux/<id>, branch w/<id> (from v7.3).
set -euo pipefail
id=${1:?usage: scripts/worker.sh <id> [--kernel]}
root=$(git rev-parse --show-toplevel)
[ -f "$root/agents/workers/$id.md" ] || { echo "no prompt agents/workers/$id.md" >&2; exit 1; }
wt="$root/../sp11-fedora.worktrees/$id"
if [ ! -d "$wt" ]; then
	if git -C "$root" show-ref --quiet "refs/heads/worker/$id"; then
		git -C "$root" worktree add "$wt" "worker/$id"
	else
		git -C "$root" worktree add -b "worker/$id" "$wt" main
	fi
fi
if [ "${2:-}" = "--kernel" ]; then
	kwt="$root/out/linux/$id"
	if [ ! -d "$kwt" ]; then
		mkdir -p "$root/out/linux"
		git -C "$root/sources/linux" worktree add -b "w/$id" "$kwt" v7.3
	fi
	echo "kernel worktree: $kwt (build with O=$root/out/build/$id, under flock $root/out/.kernel-build.lock)"
fi
cat <<MSG
project worktree: $wt
launch:
  cd $wt && claude "You are the $id worker. Read AGENTS.md, agents/protocol.md and agents/workers/$id.md, then do the task in that file. Write only inside the folder it names. Finish with the hand-back of agents/protocol.md section 10."
MSG
