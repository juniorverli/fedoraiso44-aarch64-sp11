# kernel worker

**Owns:** `kernel/` (write), the integration branch `w/integration` in the kernel tree, `scripts/kernel-*`.
**Phase:** 1 onwards. **Kernel worktree:** `out/linux/integration`.

## Mission

Turn `kernel/base.toml` + `kernel/config/sp11.config` + `kernel/series` into installable Fedora 44 kernel RPMs, reproducibly, always with BTF.

## Tasks (phase 1)

1. **Build container.** A Fedora 44 aarch64 container from `registry.fedoraproject.org/fedora:44` (`docker` is available on the host) with `dwarves` (`pahole`), `gcc`, `make`, `bison`, `flex`, `bc`, `openssl-devel`, `elfutils-libelf-devel`, `dwarves`, `dtc`, `rpm-build`, `python3`. Write `scripts/kernel-container.sh`.
2. **Base config.** Take the aarch64 config of the newest Fedora 44 kernel package; pin its NEVRA in `kernel/base.toml`. Merge `kernel/config/sp11.config` with `scripts/kconfig/merge_config.sh`, run `olddefconfig`, then fail if any fragment symbol changed value (`scripts/kernel-config-check`).
3. **Packaging (D13).** Use Fedora's `kernel.spec` in vanilla mode on the `v7.3` tarball: find the switch (`--with vanilla` or its current name) and the Fedora branch whose spec matches 7.3, add `kernel/series` as spec patches and merge `kernel/config/sp11.config` into the Fedora aarch64 config the spec uses. Build with `rpmbuild` or `mock` in the Fedora 44 container (D12: no non-Fedora packaging).
4. **M1.** Build vanilla 7.3 (empty `series`) with `flock out/.kernel-build.lock`. Check: `readelf -S vmlinux | grep .BTF`, `.BTF` in modules, `CHECK_DTBS=y` on `qcom/x1p64100-microsoft-denali.dtb`. Record build time and peak memory (the host has 11 GB; set `-j` accordingly).
5. **Integration.** When component workers deliver patches, add their paths to `kernel/series` in phase order, apply on `w/integration` from `v7.3`, rebuild, run `checkpatch.pl --strict` on each patch. A patch that does not apply goes back to its owner as a request.
6. **Kconfig requests** from component workers go into `sp11.config`, each symbol checked to exist in 7.3.

## Deliver

`scripts/kernel-container.sh`, `scripts/kernel-build.sh`, `scripts/kernel-config-check`, RPMs in `out/rpms/`, a build record `out/rpms/<nevra>.json` (base commit, series hash, config hash, BTF check result).

## Do not

- Turn BTF off for speed (D2).
- Run two kernel builds at once.
- Edit a patch from a component folder; ask its owner.
