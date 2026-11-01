#!/usr/bin/env bash
# Prepare the worktrees of one worker and print how to launch it.
#   scripts/worker.sh <id> [--kernel] [--runtime claude|codex] [--model <model>] [--effort <effort>] [--crosscheck]
#
# Runtimes (agents/README.md "Runtimes"):
#   claude  Claude Code, Sonnet 5.5, effort high
#   codex   Codex, Terra 6.1 (gpt-6.1-terra), reasoning effort high (or Sol 6.1 xhigh)
# --crosscheck starts an independent second read of the same component on its
# own branch worker/<id>-x-<runtime>; it may write only hardware/<id>/crosscheck/.
set -euo pipefail
id=${1:?usage: scripts/worker.sh <id> [--kernel] [--runtime claude|codex] [--model <model>] [--effort <effort>] [--crosscheck]}
shift
kernel=0 runtime=claude cross=0 model="" effort=""
while [ $# -gt 0 ]; do
	case "$1" in
	--kernel) kernel=1 ;;
	--runtime) runtime=${2:?}; shift ;;
	--model) model=${2:?}; shift ;;
	--effort) effort=${2:?}; shift ;;
	--crosscheck) cross=1 ;;
	*) echo "unknown option $1" >&2; exit 1 ;;
	esac
	shift
done
# Always resolve the main checkout, even when run from inside a worktree, so
# every worker shares one sources/ and one out/ (RPMs, ISOs, build lock).
root=$(cd "$(git rev-parse --git-common-dir)/.." && pwd)
[ -f "$root/agents/workers/$id.md" ] || { echo "no prompt agents/workers/$id.md" >&2; exit 1; }
name=$id
[ $cross = 1 ] && name="$id-x-$runtime"
wt="$root/../sp11-fedora.worktrees/$name"
if [ ! -d "$wt" ]; then
	if git -C "$root" show-ref --quiet "refs/heads/worker/$name"; then
		git -C "$root" worktree add "$wt" "worker/$name"
	else
		git -C "$root" worktree add -b "worker/$name" "$wt" main
	fi
fi
# sources/windows, sources/linux and out/ are git-ignored: link them to the
# main checkout so the worktree reads the same pinned inputs.
for p in sources/windows sources/linux out; do
	[ -e "$wt/$p" ] || ln -s "$root/$p" "$wt/$p"
done
if [ $kernel = 1 ]; then
	kwt="$root/out/linux/$name"
	if [ ! -d "$kwt" ]; then
		mkdir -p "$root/out/linux"
		git -C "$root/sources/linux" worktree add -b "w/$name" "$kwt" v7.3
	fi
	echo "kernel worktree: $kwt (build with O=$root/out/build/$name, under flock $root/out/.kernel-build.lock)"
fi
if [ $cross = 1 ]; then
	task="You are the $id CROSS-CHECK worker. Read AGENTS.md, agents/protocol.md (section 5.1) and agents/workers/$id.md. From hardware/$id/README.md read only section 6 (Open questions); do not read its other sections, evidence/ or patches/ before you have written your own answers. Answer those questions independently, from sources/ only, with grades and citations, and write the result to hardware/$id/crosscheck/$runtime-$(date +%F).md. Write nothing else."
else
	task="You are the $id worker. Read AGENTS.md, agents/protocol.md and agents/workers/$id.md, then do the task in that file. Write only inside the folder it names. Finish with the hand-back of agents/protocol.md section 10."
fi
case "$runtime" in
claude)
	m=${model:-claude-sonnet-5-5}
	e=${effort:-high}
	cmd="claude --model $m --effort $e \"$task\""
	;;
codex)
	m=${model:-gpt-6.1-terra}
	e=${effort:-high}
	task="$task Codex sandbox: do not run git commands that write; leave changes uncommitted for the orchestrator. Ignore global skills such as bmad-build."
	cmd="codex exec -m $m -c model_reasoning_effort=\"$e\" -s workspace-write -c sandbox_workspace_write.network_access=true --add-dir $root/out -C $wt \"$task\""
	;;
*) echo "unknown runtime $runtime" >&2; exit 1 ;;
esac
echo "project worktree: $wt"
echo "launch ($runtime):"
echo "  cd $wt && $cmd"
