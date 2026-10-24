# Resumed-session software validation

Scope: vanilla v7.3 (`c03c1a14507dfaf8b856c2608f9ac216021fc222`) plus
patches **0001/0002 only**, in `out/linux/display-lcd` (`w/display-lcd`).
The prior worktree had all three patches applied as uncommitted source changes.
Saved its diff as `out/rea/display-lcd/resume-before.diff`, then reversed
only patch 0003 with `patch --batch --fuzz=0 -R -p1`. No git index, commit,
branch, or shared `sources/linux` file was changed. Final kernel diff is
one panel-table line and three HPD-pinctrl lines; 0003 remains only as a held
patch file for review.

## Environment and build

Reused the stopped worker container `display-lcd-verify`, running Fedora 44
from local image `sp11-kernel-fc44`, image ID
`sha256:b2415bd08bda2f47d81fd341efb308192b25167918c56734dd3e5dda10db4b3b`.
Its persistent mounts map this worker's kernel tree to `/linux`,
`out/build/display-lcd` to `/build`, and `out/rea/display-lcd` to `/evidence`.
The container was stopped again after verification.

Observed installed tools (not inferred from the image name):

- `gcc-16.2.1-2.fc44.aarch64`
- `make-4.4.1-12.fc44.aarch64`
- `dwarves-1.32-1.fc44.aarch64` (`pahole v1.32`)
- `dt-schema-2026.09-1.fc44.noarch`
- `which-2.25-1.fc44.aarch64`

Reused the prior arm64 defconfig-based `.config`, checking both required
options **before** make: `CONFIG_DEBUG_INFO_BTF=y` and
`CONFIG_DEBUG_INFO_BTF_MODULES=y`. `CONFIG_DRM_PANEL_EDP=m`.
Executed from the project worktree:

```bash
flock /home/juniormverli/repositories/fedora44iso-aarch64-sp11/out/.kernel-build.lock \
    docker exec display-lcd-verify bash -c '
set -eu
test "$(sed -n s/^CONFIG_DEBUG_INFO_BTF=//p /build/.config)" = y
test "$(sed -n s/^CONFIG_DEBUG_INFO_BTF_MODULES=//p /build/.config)" = y
touch /linux/drivers/gpu/drm/panel/panel-edp.c
make -C /linux O=/build ARCH=arm64 -j4 drivers/gpu/drm/panel/panel-edp.o
make -C /linux O=/build ARCH=arm64 -j4 CHECK_DTBS=y qcom/x1p64100-microsoft-denali.dtb
' > out/rea/display-lcd/resume-build-check.log 2>&1
```

**Result: exit 0**, no compiler or schema diagnostics. The log contains an
actual `CC [M] ...panel-edp.o`, `SCHEMA ...processed-schema.json` and
`DTC [C] ...x1p64100-microsoft-denali.dtb`. The generated DTB command records
`dt-validate -m -u /linux/Documentation/devicetree/bindings -p
./Documentation/devicetree/bindings/processed-schema.json ...dtb`.
The schema file is nonempty (28085255 bytes).

This is an **object compile and checked DTB build**, not a full kernel,
module link, RPM, BTF generation, ISO or device test. Both BTF options were
enabled, but no `vmlinux` or module BTF artifact is claimed. The kernel owner
still must perform the integrated build with BTF.

| Artifact | SHA-256 |
|:--|:--|
| `out/build/display-lcd/.config` | `96fdc862476429947acc440ea76552b9dd20aa478b7aa091a93953ac08bb93a4` |
| `out/build/display-lcd/drivers/gpu/drm/panel/panel-edp.o` (AArch64 ELF object) | `3d725f5d7de11977ffa2fc9a780081db5ac0520d2a664bb74f2f2e9cf62af246` |
| `out/build/display-lcd/arch/arm64/boot/dts/qcom/x1p64100-microsoft-denali.dtb` | `bc9463f8b72edede60fd1d349017129d2172cc3e8bcbdce29e5cd680debde896` |
| `out/rea/display-lcd/resume-build-check.log` | `c9aaa6f453d0e9f371982c41bbc95def5ad66e60995c20e5b9da437becbd38db` |

## Patch and dossier checks

Ran for all three patch files, via stdin to ensure patch mode for files
tracked by the project repository:

```bash
set -e
for patch in hardware/display-lcd/patches/*; do
    printf '%s\n' "$patch"
    perl sources/linux/scripts/checkpatch.pl --strict --no-signoff --no-tree - < "$patch"
done > out/rea/display-lcd/resume-checkpatch.log
```

**Result: 0 errors, 0 warnings, 0 checks for each patch.** `--no-signoff`
is intentional: all AI-added `Signed-off-by: juniorverli` trailers were
removed, replaced with `Assisted-by: Codex gpt-6.1-sol`; only the operator
can supply their DCO statement. This check makes no DCO-completeness claim.

Replayed 0001/0002 with `patch --batch --fuzz=0 -p1` over copies of the four
affected files obtained with read-only `git show HEAD:<path>`. All four files
matched the final kernel worktree byte for byte. Then applied held 0003
in the temporary replay directory only: it still applies with no fuzz.
No new compile or DT validation of 0003 is claimed. Temporary copies were
removed; logs remain outside git.

- `out/rea/display-lcd/resume-patch-replay.log`, SHA-256
  `70aa3381908ba1768698007cdd5c27e2358991a45a37d1f55772df34c835c967`.
- `out/rea/display-lcd/resume-checkpatch.log`, SHA-256
  `863f9b57ee763b1d31f831b8f351a3fa6865f390a5fba453ab7590e8811135fb`.
- `python3 scripts/index.py --check`: **21 components, 0 errors**.
- `git diff --check` in both project and kernel worktrees: **exit 0**.
- Re-ran the existing static decoder against the catalogued EDID and both
  extension blobs; all structure assertions passed, with the same pinned
  hashes and selected records. No REA/Ghidra command ran this session.

All project edits are under `hardware/display-lcd/`. The pre-existing
untracked `out` symlink is unchanged. Changes remain uncommitted for the
orchestrator, as required by the session's read-only git constraint.
