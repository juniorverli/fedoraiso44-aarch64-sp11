# fedoraiso44-aarch64-sp11

Linux 7.3 kernel and Fedora 44 Workstation aarch64 ISO for the Microsoft Surface Pro 11, 13" LCD, Snapdragon X Plus X1P64100.

## How this repository is organised

The repository is built around **hardware components**. Each component is one folder under `hardware/` with one owner. Everything known about that component lives there: what it is, what Windows uses, what Linux 7.3 gives, what is missing, the evidence, the patches.

```
sources/      pinned, read-only inputs (Windows dumps, kernel tree)  -- everyone reads
hardware/     one dossier per component                              -- one owner each
agents/       how AI workers operate, and one prompt per worker
plan/         roadmap, decisions, risks                              -- orchestrator only
kernel/       base pin, Kconfig fragment, series file                -- kernel worker
firmware/     firmware manifest (paths and hashes, never binaries)   -- firmware worker
image/        ISO definition                                         -- image worker
scripts/      tools (index generator, DriverStore verifier, builds)
journal/      dated session log                                      -- orchestrator only
out/          generated files, ignored by git
```

Three rules make parallel work safe:

1. **Shared inputs are read-only.** `sources/`, `plan/` and `agents/protocol.md` are the same for every worker.
2. **One writer per folder.** A worker writes only inside the folder it owns.
3. **Aggregates are generated.** `hardware/INDEX.md` is produced by `scripts/index.py` from every `component.toml`. The kernel series and the firmware manifest point into the component folders.

## Start here

| You want | Read |
|:--|:--|
| The rules for AI | `AGENTS.md`, then `agents/protocol.md` |
| What is planned and in which order | `plan/roadmap.md` |
| The full hardware list and its state | `hardware/INDEX.md` |
| One component in depth | `hardware/<component>/README.md` |
| What happened last | `journal/` (newest file) |

## Current phase

Phase 1: internal LCD and Adreno GPU. Nothing has been tested on the device yet.

## Never in git

Windows binaries, extracted firmware, keys, MAC addresses, serial numbers. `sources/windows` and `sources/linux` are local links or checkouts and are ignored.
