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

## Disk guard and profiles (2026-10-24)

Cause of the earlier WSL death: the ext4 root is a growing VHDX on the Windows C: drive; with C: full the VHDX could not grow, writes stalled and the VM died. Memory was not the cause.

- Real headroom = C: free (`df -B1 /mnt/c`) + (VHDX size - bytes used on `/`). VHDX found by glob `/mnt/c/Users/*/AppData/Local/Packages/*/LocalState/ext4.vhdx` (smallest one at least as large as the used bytes), or `SP11_VHDX=<path>`. Without a VHDX: `df /`.
- Start thresholds: release 60 GiB, dev 20 GiB (`SP11_MIN_HEADROOM_GIB` overrides with a loud warning). Watchdog every 15 s (`SP11_WATCHDOG_INTERVAL`); below 15 GiB (`SP11_STOP_HEADROOM_GIB`) it logs the reason, kills the named container and the script exits non-zero. Code: `scripts/kernel-common.sh`. The watchdog stop path was not triggered in practice; the minimum headroom seen in the release build was 145 GiB (start 148 GiB).
- ccache `max_size` is 15G.

| Profile | Script | Config | Output |
|:--|:--|:--|:--|
| dev | `scripts/kernel-dev.sh <id> [dtbs\|module <path>\|all]` | upstream arm64 `defconfig` + `sp11.config` + `config/dev.config` | `out/build/dev-<id>`, no RPM |
| release | `scripts/kernel-build.sh -j 6` | Fedora 44 config + `sp11.config` (Fedora `kernel.spec`, vanilla) | RPMs in `out/rpms/` |

`dev.config` exists because defconfig sets `DEBUG_INFO_REDUCED=y` (blocks BTF), lacks `FW_LOADER_COMPRESS`, and builds the xHCI platform glue in.

### Dev timings (display-lcd patch 0002 applied, `-j6`, ccache)

| Step | Time | Note |
|:--|:--|:--|
| `all` cold (Image, DTBs, modules) | 1932 s | 10995 ccache misses, `O=` 11 GB |
| `all` warm, nothing changed | 277 s | 2 misses (relinks, BTF) |
| `dtbs` after touching the DTSI | 3 s | |
| `module drivers/gpu/drm/panel` after touching panel-edp.c | 2 s | |

### Compressed DWARF (`CONFIG_DEBUG_INFO_COMPRESSED_ZSTD=y`), dev defconfig build, same tree

| | none | zstd |
|:--|--:|--:|
| `O=` dir | 11.6 GB | 8.0 GB (-31%) |
| `vmlinux` | 494 MB | 242 MB |
| all `.ko` (1724) | 2141 MB | 1387 MB |
| `msm.ko` | 51.9 MB | 32.3 MB |
| `.BTF` of `vmlinux` / `msm.ko` | 0x691fb0 / 0x3e6bd | identical sizes |
| cold build time | 1932 s | 1639 s (different cache state, not a clean comparison) |

pahole 1.32 reads BTF from the zstd build (`task_struct`, `drm_device` from `msm.ko` with `--btf_base vmlinux`). Toolchain: gcc 16.2.1, binutils 2.46.1. Enabled in `sp11.config`. The release build confirmed Fedora's `find-debuginfo` handles it: RPMs built, debuginfo RPM written, all 5930 modules carry `.BTF`.

### M1 release build (vanilla 7.3, empty series, `-j 6`, BTF), 2026-10-24

- Result: `kernel-7.3.0-65.sp11.fc44.aarch64`, `scripts/kernel-check` PASS: `vmlinux` `.BTF` present (0x76c806 bytes), 5930/5930 modules with `.BTF`, 61 fragment symbols hold (includes firmware and image requests), `CHECK_DTBS=y` on `qcom/x1p64100-microsoft-denali.dtb` rc 0 with 0 warnings, DTB in kernel-core at `/lib/modules/<kver>/dtb/qcom/x1p64100-microsoft-denali.dtb`. `bpftool` is not in the build container; BTF verified with the ELF section table and pahole.
- Wall time 5652 s (94 min), 24310 ccache misses, 2222 direct hits (cache was cold for the new flags).
- Peak memory: cgroup 10.1 GB (includes page cache), anonymous 3.9 GB.
- Disk: `out/build/kernel` 27 GB at the end; ccache 12 GB; minimum headroom seen 145 GiB. The build reused the partial tree of the failed run, so the peak is not a clean-start figure.
- RPM sizes: kernel-core 24 MB, kernel-modules 73 MB, kernel-modules-core 54 MB, kernel-modules-extra 2 MB, kernel-modules-internal 7 MB, kernel-uki-virt 87 MB, kernel-devel 53 MB, kernel-debuginfo 1944 MB, kernel-debuginfo-common 99 MB.
- `kernel-check` fixed: `cmd | grep -q` under pipefail failed with SIGPIPE (false negatives for vmlinux BTF and DTB in the package).

## Series revision and NEVRA (2026-10-25)

The RPM release carries the series revision through Fedora's `buildid`: `65.sp11.<series_rev>.fc44`.

| `series_rev` | Series | NEVRA |
|--:|:--|:--|
| 0 | empty (M1, vanilla 7.3) | `kernel-7.3.0-65.sp11.fc44.aarch64` (archived in `out/rpms/archive/7.3.0-65.sp11/`) |
| 3 | display-lcd 0001-0003 (M3, D19) | `kernel-7.3.0-65.sp11.3.fc44.aarch64` |

- `kernel/base.toml` holds `series_rev` and `series_sha256` (sha256 of the `<path> <patch sha256>` lines of `kernel/series`). Changing `kernel/series` or a patch in it without bumping both makes `scripts/kernel-build.sh` and `scripts/kernel-check` fail and print the new hash.
- A build that succeeds archives the RPMs of every other `series_rev` from `out/rpms/` into `out/rpms/archive/<ver>-<rel>.sp11[.<rev>]/` before it copies the new ones. The record `out/rpms/<nevra>.json` has `series_rev` and the series hash.
- ccache runs with `CCACHE_NOHASHDIR=1`: the rpmbuild tree is named `linux-<kver>`, so a new `series_rev` would otherwise miss the whole cache. The first build after this change still compiles everything, because the hash changed.

## M3 kernel (D19)

- `kernel/series`: display-lcd 0001, 0002, 0003, in this order. They apply cleanly in this order on v7.3 (checked with `git am` in a clean worktree). Change to `sp11.config`: `CONFIG_DRM_DISPLAY_DP_AUX_CHARDEV=y`. The brief named `CONFIG_DRM_DP_AUX_CHARDEV`, which does not exist in 7.3 (renamed; Fedora already had it `=y`). `DRM_MSM=m`, `DRM_PANEL_EDP=m`, `BACKLIGHT_PWM=m`, `LEDS_QCOM_LPG=m` and `PINCTRL_QCOM_SPMI_PMIC=y` are unchanged.

### DTB variants (diagnostic, DT-only)

`scripts/kernel-dtb-variants.sh [KVER]` builds both with `scripts/kernel-dev.sh` in dev kernel trees (seconds) into `out/dtb-variants/<kver>/qcom/`, each with a `.json` record (source commit, patches applied, overlay sha256, sha256). The directory follows the RPM kver (`7.3.0-65.sp11.3.fc44.aarch64`). The image worker ships them as extra DTBs.

| File | Content |
|:--|:--|
| `x1p64100-microsoft-denali-nobl.dtb` | display-lcd 0001+0002, no `backlight` node (tree `out/linux/m3nobl`) |
| `x1p64100-microsoft-denali-edponly.dtb` | the full M3 DT (0001-0003) with `&mdss_dp0` and `&mdss_dp1` set to `disabled` (H5: external DP chain blocking the msm bind). Source: `kernel/dtb-variants/x1p64100-microsoft-denali-edponly.dts`, a top-level DTS that includes the board DTS; not a patch. Built with `-@` like the packaged DTB |

Against the packaged DTB (`/lib/modules/<kver>/dtb/qcom/x1p64100-microsoft-denali.dtb`, byte-identical to the dev-tree build of the same series, sha256 `582725d5...`), `dtc -I dtb -O dts` shows for `edponly` exactly two differences: `status` `"okay"` becomes `"disabled"` in `mdss_dp0` and `mdss_dp1`. `nobl` lacks everything patch 0003 adds: the `backlight` (`pwm-backlight`) node, `vreg_edp_bl`, the `panel` `backlight` and `power-supply` properties, the two backlight pinctrl states, and the LPG PWM enable.

### M3 release build record (`kernel-7.3.0-65.sp11.3.fc44.aarch64`, `-j 6`, 3 series patches)

- `scripts/kernel-check` PASS: `vmlinux` `.BTF`, 5930/5930 modules with `.BTF`, config fragment holds, `CHECK_DTBS=y` rc 0 with 0 warnings.
- Packaged DTB (decompiled with `dtc`): `backlight` node with `compatible = "pwm-backlight"`; `mdss_dp3` (eDP, `status = "okay"`) has `pinctrl-0 = <&edp0_hpd_default>` (`gpio119`, `edp0_hot`); the `panel` under its `aux-bus` has `backlight = <&backlight>`.
- `panel-edp.ko.xz` contains the panel ID `0x30e4077b` (LGD 0x077b) once, and the name `LP129WT342166` once.
- Wall time 6328 s (105 min). The ccache did not shorten it: the `series_rev` change renamed the build tree (`linux-<kver>`) and the first build with `CCACHE_NOHASHDIR=1` hashes differently, so 24386 misses and 2218 direct hits. Later series_rev bumps reuse the cache. Peak memory: cgroup 9.8 GB (page cache included), anonymous 3.9 GB. Minimum headroom seen 104 GiB (start 128 GiB).
