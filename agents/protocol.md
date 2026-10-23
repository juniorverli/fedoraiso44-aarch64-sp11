# Agent protocol

Every AI session in this repository follows this file. It defines roles, who may write where, how facts are graded, and what a worker hands back.

## 1. Roles

| Role | Count | Job |
|:--|:--|:--|
| Orchestrator | 1 | Plans, starts workers, reviews and merges their branches, keeps `plan/`, `journal/` and `hardware/INDEX.md` current, talks to the operator |
| Component worker | 1 per `hardware/<component>/` | Investigates one component end to end: Windows behaviour, Linux 7.3 coverage, gaps, reverse engineering, patches, test plan |
| Service worker | kernel, firmware, image, sources | Owns a build artefact shared by all components |

A worker is started with its prompt file `agents/workers/<id>.md`. The prompt names the folder it owns.

## 2. Shared inputs (read-only for everyone)

| Input | Path | Pin |
|:--|:--|:--|
| Windows driver store, firmware, ACPI tables, live inventory | `sources/windows/` (link to `~/sp11-windows-dumps`) | `sources/windows/MANIFEST.sha256`; provenance in `sources/README.md` |
| Linux 7.3 tree | `sources/linux/` | tag `v7.3`, commit `c03c1a14507dfaf8b856c2608f9ac216021fc222` (`kernel/base.toml`) |
| Plan, decisions, risks | `plan/` | git |
| This protocol | `agents/protocol.md` | git |
| Other components' dossiers | `hardware/*/` | read, never write |

Nobody edits `sources/`. A new input (an official Microsoft package, a linux-firmware release, a lore series) is added by the sources worker and pinned in `sources/sources.toml` first.

## 3. Write ownership

| Path | Writer |
|:--|:--|
| `hardware/<component>/**` except `crosscheck/` | that component's worker |
| `hardware/<component>/crosscheck/` | that component's cross-check worker |
| `kernel/**` | kernel worker |
| `firmware/**` | firmware worker |
| `image/**` | image worker |
| `sources/*.md`, `sources/sources.toml`, `scripts/verify-*` | sources worker |
| `scripts/kernel-*`, `scripts/firmware-*`, `scripts/image-*` | kernel, firmware, image worker respectively |
| `plan/**`, `journal/**`, `hardware/INDEX.md`, `agents/**`, `scripts/index.py`, `scripts/worker.sh`, root files | orchestrator |

A worker that needs something outside its folder writes a **request** in its own `README.md` under "Requests" (for example "kernel: enable `CONFIG_SPI_HID_OF=m`"). The owner of the other path picks it up. Nobody edits another worker's files, even to fix a typo.

## 4. Git and worktrees

The repository and the kernel tree are both used through `git worktree`, so parallel workers never share a checkout.

### 4.1 Project repository

- `main` is changed only by the orchestrator, by merging worker branches.
- Each active worker has a branch `worker/<id>` and a worktree at `../sp11-fedora.worktrees/<id>/`:

  ```bash
  git worktree add -b worker/display-lcd ../sp11-fedora.worktrees/display-lcd main
  ```

- Because write ownership is disjoint (§3), merges into `main` cannot conflict. A conflict means a worker broke §3; the merge is refused.
- A worker rebases on `main` at the start of a session to see merged results of others.
- `sources/windows`, `sources/linux` and `out/` in a worktree are links to the main checkout (made by `scripts/worker.sh`). All builds, RPMs, ISOs and the build lock live in the main checkout's `out/`.

### 4.2 Kernel tree

- `sources/linux` stays at `v7.3` and is never edited.
- A worker that writes kernel code gets its own worktree and branch:

  ```bash
  git -C sources/linux worktree add -b w/display-lcd ../../out/linux/display-lcd v7.3
  ```

- Builds use a separate output directory: `make O=../../out/build/<id> ...`.
- Patches leave the worktree with `git format-patch v7.3..` into `hardware/<component>/patches/`. The kernel worker assembles `kernel/series` from those folders and builds the integrated kernel on its own branch `w/integration`.
- **One kernel build at a time.** The host has 10 cores and 11 GB RAM; a BTF build with `pahole` does not fit twice. Take the lock: `flock out/.kernel-build.lock make ...`.

## 5. Grading facts

Every hardware value (GPIO, address, clock, regulator, delay, ID, firmware name) carries one grade:

| Grade | Meaning | Required citation |
|:--|:--|:--|
| Verified | Read from data or decompiled code | Path, SHA-256, offset or function address, REA `evidence_id` when REA was used |
| Inference | Derived from verified facts | The reasoning, and the facts it rests on |
| Hypothesis | Plausible, not supported | What observation would confirm or kill it |
| TBD | Unknown | What would answer it |

Linux source facts cite `sources/linux/<path>:<line>`.

Before analysing any file, look it up in `sources/binary-catalog.tsv` (`sources/binary-formats.md`) and use the Ghidra language it gives. A file catalogued as data is never disassembled; a file with "NO GHIDRA LANGUAGE" is never decoded under a guessed CPU.

### 5.1 Cross-check

A value that ends up in a patch, a DT property or a safety decision (GPIOs, PMIC channels, regulator voltages, delays, speaker parameters, current limits) must be reproduced by an independent cross-check before the component reaches `sw-ready`:

1. The orchestrator starts `scripts/worker.sh <id> --crosscheck --runtime <other runtime>` on the runtime that did **not** produce the value.
2. The cross-check worker sees only the open questions, not the answers, and writes `hardware/<id>/crosscheck/<runtime>-<date>.md`.
3. The component worker compares: values that agree keep their grade; values that disagree drop to Hypothesis until resolved from `sources/`.

## 6. Component status

`component.toml` has one `status`:

| Status | Meaning |
|:--|:--|
| `survey` | Being investigated |
| `designed` | Gaps known, change proposed, not built |
| `sw-ready` | Patches build, `checkpatch --strict` clean, DT validates; never run on the device |
| `testing` | On a test ISO, waiting for device logs |
| `pass` | Device evidence in `hardware/<component>/evidence/` meets the component's acceptance criteria |
| `blocked` | Cannot progress; the blocker is written |
| `absent` | Evidence shows this unit does not have the hardware |

`pass` is set by the orchestrator only, after reading the evidence.

## 7. What a component worker produces

Inside `hardware/<component>/`:

| File | Content |
|:--|:--|
| `component.toml` | Machine-readable state: IDs, Windows packages, Linux drivers, status, gaps, firmware, dependencies. Read by `scripts/index.py` |
| `README.md` | The dossier, with the fixed sections in §8 |
| `evidence/` | One Markdown file per fact set or device log, named `YYYY-MM-DD-<topic>.md`. Raw decompiled code and binaries never go here |
| `patches/` | `git format-patch` output for this component, numbered locally |
| `test-plan.md` | Commands to run on the device and the expected results, before the ISO is built |

## 8. Dossier sections (fixed order)

1. **Summary**: what the component is, in two sentences; current status.
2. **Hardware**: chips, buses, addresses, GPIOs, supplies, with grades.
3. **Windows**: hardware IDs, driver packages (folder name in `DriverStore`), active version, what each driver does.
4. **Linux 7.3**: drivers and DT nodes that already exist, with `file:line`.
5. **Gaps**: what is missing for the component to work, each with the planned answer (upstream backport, new patch, firmware, userspace, nothing).
6. **Open questions**: each with grade and what would answer it.
7. **Acceptance**: how we will know it works on the device.
8. **Requests**: things other owners must do.
9. **Log**: dated one-line entries of what changed.

## 9. Reverse engineering

1. Look for the answer in this order: Linux 7.3 source; linux-next and lore; ACPI tables in `sources/windows/live-inventory/acpi/`; INF and registry data; only then the Windows binary in REA.
2. REA runs with the Ghidra provider and the language **forced** from the catalog: `REA_GHIDRA_LANGUAGE_ID=<ghidra_language of the row>` in the environment of the REA process (CLI or MCP server). Never let Ghidra auto-detect. For large images raise `GHIDRA_MAXMEM` (e.g. `4G`) and `REA_GHIDRA_STARTUP_TIMEOUT_MS` (default 330000). Record for each result: the binary path, its SHA-256, the language used, the function address, the `evidence_id`.
3. Address procedures that exist: list them with `rea search <path> . --kind procedures --mode regex --provider ghidra` (MCP: `list_procedures`) before decompiling. An ELF `e_entry` of 0 or a header address is not a function.
4. ARM32 entry points with the lowest bit set are Thumb code; decoding them as ARM produces garbage (seen on `qcsp8380/*.sig`). Set the Thumb context before trusting any output.
5. Decompiled code stays in REA snapshots outside git. Evidence files contain addresses and conclusions, not pasted pseudocode.
6. REA tool setup is the sources worker's job; workers report tool failures as requests.

## 10. Handing back

At the end of every session a worker:

1. Updates `component.toml` (`status`, `gaps`, `updated`).
2. Adds a line to the dossier's **Log**.
3. Runs `scripts/index.py --check` (fails if `component.toml` is invalid).
4. Commits on its branch with a message `<component>: <what changed>`.
5. Ends its reply to the orchestrator with: status, the three most important findings, open requests, and what it would do next.

Workers do not push, publish or contact anyone outside this machine.
