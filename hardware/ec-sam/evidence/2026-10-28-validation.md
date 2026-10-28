# Off-device validation, 2026-10-28 (Codex continuation)

No git-writing command was run. The inherited kernel worktree HEAD already
contained four Claude candidate commits; they are not new commits from this
session. Project changes remain uncommitted for the orchestrator (D24).
No device test, firmware write or charging/thermal-policy write was performed.

## Candidate scope

- Active proposals: patch 0001 (two optional HID endpoints omitted for this
  tested unit/cover), patch 0003 (existing fan read client).
- Held: 0002 (POS switch), 0004 (power/volume DT). Neither is requested for
  the next image without its stated evidence/cross-check gate.
- `patch --batch --fuzz=0 -p1` applied 0001 and 0003 to copies of the pinned
  source in a temporary directory, then both held patches. All succeeded. The final patch metadata/hunks were aligned to active
  0001/0003 followed by held 0002/0004; the repeat had no offset or fuzz.
  Active files exactly match the final build source; with both held patches
  the resulting files match the inherited source. Output:
  `out/ec-sam/codex-patch-apply.log`. This verifies source correspondence,
  not hardware validity.

## Checks completed

| Check | Result |
|:--|:--|
| `sources/linux/scripts/checkpatch.pl --strict --no-signoff <patch>` on all four candidates | Exit 0 each; zero errors/warnings/checks. Full output: `out/ec-sam/codex-checkpatch.log` |
| `bash -n hardware/ec-sam/tools/*.sh` | Pass |
| SSAM read tool `--list` and mocked ABI/payload checks | Pass: 40-byte request, ioctl `c028a501`, only five allowlisted read commands, bad payload rejected before ioctl; no real device access |
| evtest output-boundary fixture | Pass: capabilities retained; synthetic event after `Testing ...` discarded |
| Power/UPower filter fixture | Pass: status, energy, percentage, online context retained; synthetic serial/model/vendor/charge-control fields excluded |
| `python3 scripts/index.py --check` | 21 components, 0 errors |
| `git diff --check` | Pass for tracked changes; no git write |

The fixture checks were temporary commands, not installed tests. They
validate collector output boundaries without reading a real input device.
They do not substitute for live UPower or keyboard acceptance.

## Kernel and DT

The interrupted worker had launched a leaf-module build through
`scripts/kernel-dev.sh` using `out/ec-sam/dev-leaf.config`. It was still
compiling vmlinux when this continuation began; its partial log was **not**
a successful module-build result. The configuration has
`CONFIG_DEBUG_INFO_BTF=y` and `CONFIG_DEBUG_INFO_BTF_MODULES=y`.

The continuation queued:

```bash
SP11_DEV_FRAGMENT="$PWD/out/ec-sam/dev-leaf.config" scripts/kernel-dev.sh --check ec-sam dtbs
```

The script itself takes `flock out/.kernel-build.lock`, uses the Fedora
container and preserves BTF. The inherited source contains all four
candidates, including held 0004. DT validation of that candidate, if it
passes, establishes schema/build correctness only; pin mapping, polarity,
power source and debounce still require evidence and cross-check.

The inherited directory build completed in 1316 s, producing a BTF-enabled
vmlinux and the Surface module objects, but no linked `.ko` files. The held
button DT candidate passed the queued `--check ec-sam dtbs` run (exit 0,
15 s, `DTC [C]`, no schema warning). Full DT output is
`out/ec-sam/codex-dt-check.log`.

The active-only source was then prepared from the pinned source plus 0001
and 0003; held POS and button changes were removed using ordinary file/patch
operations, without git writes. To try linking only registry.ko, a temporary
dev fragment built the transport in. The helper correctly rejected that
experiment because `kernel/config/sp11.config` pins the transport to `m`.
No weakened config check or modpost warning bypass was used. A first attempt
also failed before configuration because its fragment was not yet prepared;
no build result is claimed from either attempt. Their log is
`out/ec-sam/codex-registry-ko.log` (the config rejection).

The stale config hash from the rejected attempt was removed so the helper
would regenerate its standard modular profile. The continuation then ran:

```bash
SP11_DEV_FRAGMENT="$PWD/out/ec-sam/dev-leaf.config" scripts/kernel-dev.sh ec-sam all
```

This is an incremental development build of the active-only source, not an
RPM/ISO build. It is needed to link modules with the complete symbol set;
the helper's directory mode only compiled objects. Output:
`out/ec-sam/codex-active-all.log`. Final results are recorded below when it
finishes.
Component status remains `designed`; no blind protocol §5.1 cross-check has
been commissioned by the orchestrator in this session.
