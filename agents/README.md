# Agents

| File | Who reads it |
|:--|:--|
| `protocol.md` | Every AI session: roles, write ownership, git worktrees, evidence grades, hand-back |
| `orchestrator.md` | The orchestrator |
| `workers/<id>.md` | One worker each |
| `workers/_template.md` | Whoever adds a worker |

## Roster

| Worker | Owns | Phase | Kernel worktree |
|:--|:--|:--:|:--:|
| `sources` | `sources/` notes, `scripts/verify-*` | 0 | — |
| `kernel` | `kernel/` | 1 | integration |
| `firmware` | `firmware/` | 1 | — |
| `image` | `image/` | 1 | — |
| `soc-boot` | `hardware/soc-boot/` | 1 | yes |
| `display-lcd` | `hardware/display-lcd/` | 1 | yes |
| `gpu` | `hardware/gpu/` | 1 | if needed |
| `dsp-subsystems` | `hardware/dsp-subsystems/` | 1 | if needed |
| `touch-pen` | `hardware/touch-pen/` | 2 | yes |
| `ec-sam` | `hardware/ec-sam/` | 2 | if needed |
| `wifi` | `hardware/wifi/` | 2 | if needed |
| `bluetooth` | `hardware/bluetooth/` | 2 | — |
| `usb-typec` | `hardware/usb-typec/` | 2 | yes |
| `storage` | `hardware/storage/` | 2 | — |
| `audio-speakers` | `hardware/audio-speakers/` | 3 | yes |
| `audio-mics` | `hardware/audio-mics/` | 3 | if needed |
| `cameras` | `hardware/cameras/` | 4 | yes |
| `sensors` | `hardware/sensors/` | 4 | — |
| `npu` | `hardware/npu/` | 4 | — |
| `video-codec` | `hardware/video-codec/` | 4 | yes |
| `power-thermal` | `hardware/power-thermal/` | 4 | yes |
| `security-tpm` | `hardware/security-tpm/` | 4 | yes |
| `usb4` | `hardware/usb4/` | 4 | yes |

`firmware-updates` and `wwan` have dossiers but no worker: the first is out of scope until the operator asks, the second is absent on this unit.

## Runtimes

Every prompt is runtime-neutral: Claude Code reads `CLAUDE.md`, Codex reads `AGENTS.md`, both lead to `agents/protocol.md`. Both runtimes have the REA MCP server registered (Claude Code: local scope of this repository; Codex: `~/.codex/config.toml`).

| Runtime | Model | Effort | Launch |
|:--|:--|:--|:--|
| `claude` | Sonnet 5.5 (`claude-sonnet-5-5`) | high | `claude --model claude-sonnet-5-5 --effort high "<task>"` |
| `codex` | Terra 6.1 (`gpt-6.1-terra`) | high | `codex exec -m gpt-6.1-terra -c model_reasoning_effort="high" -s workspace-write -c sandbox_workspace_write.network_access=true --add-dir <main>/out -C <worktree> "<task>"` |

Codex workers run sandboxed (operator decision, 2026-10-24): `workspace-write` with network, writable roots limited to their worktree, `/tmp` and the shared `out/`. They cannot write to `/mnt/c` (Windows) or anywhere else. The sandbox keeps `.git` read-only, so **Codex workers never commit**: they leave changes uncommitted (patches as diff files in `hardware/<id>/patches/`), and the orchestrator reviews and commits them on `worker/<id>`. Global skills from `~/.agents/skills` (e.g. `bmad-build`) are not used in this repository; the prompt tells the worker to ignore them. Claude workers run as subagents of the orchestrator session and commit on their own branch.

Default assignment (the orchestrator may swap per session):

| Runtime | Workers | Why |
|:--|:--|:--|
| `codex` (Terra 6.1 high) | `display-lcd`, `gpu`, `touch-pen`, `audio-speakers`, `cameras`, `usb4`, `security-tpm`, `power-thermal` | Deep reverse engineering in REA, long reasoning chains over decompiled code |
| `claude` (Sonnet 5.5 high) | `sources`, `kernel`, `firmware`, `image`, `soc-boot`, `dsp-subsystems`, `ec-sam`, `wifi`, `bluetooth`, `usb-typec`, `storage`, `audio-mics`, `sensors`, `npu`, `video-codec` | Build plumbing, upstream research, DT work, documentation |
| the other one | every `--crosscheck` run | Independent second read (`agents/protocol.md` §5.1) |

## Launch

```bash
scripts/worker.sh display-lcd --kernel --runtime codex          # main worker
scripts/worker.sh display-lcd --crosscheck --runtime claude     # independent second read
```

Workers of the same phase run in parallel. They all read `sources/`, `plan/` and `agents/protocol.md`, and they never write to each other's folders, so the orchestrator can merge their branches in any order.
