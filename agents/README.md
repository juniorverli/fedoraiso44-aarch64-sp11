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

## Launch

```bash
scripts/worker.sh display-lcd --kernel   # creates worktrees, prints the launch command
```

Workers of the same phase run in parallel. They all read `sources/`, `plan/` and `agents/protocol.md`, and they never write to each other's folders, so the orchestrator can merge their branches in any order.
