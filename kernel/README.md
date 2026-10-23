# Kernel

Owner: kernel worker (`agents/workers/kernel.md`).

| File | Content |
|:--|:--|
| `base.toml` | Pinned base: `sp11-linux` tag `v7.3`, commit `c03c1a14507d` |
| `config/sp11.config` | Kconfig fragment merged on the Fedora 44 aarch64 config. Carries BTF (D2) |
| `series` | Ordered list of patch paths. Patches live in `hardware/<component>/patches/`, not here |

## Build contract

1. Inputs: `base.toml`, `config/sp11.config`, `series`. Nothing else.
2. Base config: Fedora 44 aarch64 kernel config of the newest Fedora 44 kernel, pinned by NEVRA in `base.toml` once chosen.
3. Merge: `scripts/kconfig/merge_config.sh -m fedora.config kernel/config/sp11.config`, then `make olddefconfig`. The build fails if any symbol of the fragment did not survive (`scripts/kernel-config-check`, to be written).
4. Environment: Fedora 44 container with `dwarves` (`pahole`), `gcc`, `bison`, `flex`, `openssl-devel`, `elfutils-devel`, `dtc`, `rpm-build`. The host has no `pahole`.
5. One build at a time: `flock out/.kernel-build.lock` (`agents/protocol.md` §4.2).
6. Output: `out/rpms/kernel-*.sp11.fc44.aarch64.rpm` and the DTB `qcom/x1p64100-microsoft-denali.dtb`.
7. Checks after build:
   - `readelf -S vmlinux | grep -q .BTF`
   - `scripts/checkpatch.pl --strict` on every patch in `series`
   - `make CHECK_DTBS=y qcom/x1p64100-microsoft-denali.dtb`
   - on the device: `/sys/kernel/btf/vmlinux` exists

Packaging: Fedora's `kernel.spec` in vanilla mode with our patches and fragment (D13, under the Fedora-native rule D12).
