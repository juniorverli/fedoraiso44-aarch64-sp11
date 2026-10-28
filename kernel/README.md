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

`scripts/kernel-dtb-variants.sh [KVER]` builds the diagnostic variants with `scripts/kernel-dev.sh` in dev kernel trees into `out/dtb-variants/<kver>/qcom/`, each with a `.json` record (source commit, patches applied, overlay sha256, sha256). The directory follows the RPM kver (`7.3.0-65.sp11.3.fc44.aarch64`). The image worker ships them as extra DTBs.

| File | Content |
|:--|:--|
| `x1p64100-microsoft-denali-nobl.dtb` | display-lcd 0001+0002, no `backlight` node (tree `out/linux/m3nobl`) |
| `x1p64100-microsoft-denali-edponly.dtb` | the full M3 DT (0001-0003) with `&mdss_dp0` and `&mdss_dp1` set to `disabled` (H5: external DP chain blocking the msm bind). Source: `kernel/dtb-variants/x1p64100-microsoft-denali-edponly.dts`, a top-level DTS that includes the board DTS; not a patch. Built with `-@` like the packaged DTB |
| `x1p64100-microsoft-denali-parity.dtb` | the full M3 DT (0001-0003) plus the net DT differences of the previous project's final 7.3 DTB, which reached GNOME on this unit: (a) 10 CPUs, `cpu7` (`cpu@10300`) and `cpu11` (`cpu@20300`) deleted with their `cpu-map` `core3` entries and the PSCI domains `cpu_pd7`/`cpu_pd11`; (b) `domain-idle-states` deleted from `&system_pd`, so SS3 is unused while CL4 and CL5 stay. Source: `kernel/dtb-variants/x1p64100-microsoft-denali-parity.dts` |

Against the packaged DTB (`/lib/modules/<kver>/dtb/qcom/x1p64100-microsoft-denali.dtb`, byte-identical to the dev-tree build of the same series, sha256 `582725d5...`), `dtc -I dtb -O dts` shows for `edponly` exactly two differences: `status` `"okay"` becomes `"disabled"` in `mdss_dp0` and `mdss_dp1`. `nobl` lacks everything patch 0003 adds: the `backlight` (`pwm-backlight`) node, `vreg_edp_bl`, the `panel` `backlight` and `power-supply` properties, the two backlight pinctrl states, and the LPG PWM enable.

### M3 release build record (`kernel-7.3.0-65.sp11.3.fc44.aarch64`, `-j 6`, 3 series patches)

- `scripts/kernel-check` PASS: `vmlinux` `.BTF`, 5930/5930 modules with `.BTF`, config fragment holds, `CHECK_DTBS=y` rc 0 with 0 warnings.
- Packaged DTB (decompiled with `dtc`): `backlight` node with `compatible = "pwm-backlight"`; `mdss_dp3` (eDP, `status = "okay"`) has `pinctrl-0 = <&edp0_hpd_default>` (`gpio119`, `edp0_hot`); the `panel` under its `aux-bus` has `backlight = <&backlight>`.
- `panel-edp.ko.xz` contains the panel ID `0x30e4077b` (LGD 0x077b) once, and the name `LP129WT342166` once.
- Wall time 6328 s (105 min). The ccache did not shorten it: the `series_rev` change renamed the build tree (`linux-<kver>`) and the first build with `CCACHE_NOHASHDIR=1` hashes differently, so 24386 misses and 2218 direct hits. Later series_rev bumps reuse the cache. Peak memory: cgroup 9.8 GB (page cache included), anonymous 3.9 GB. Minimum headroom seen 104 GiB (start 128 GiB).

### Parity variant evidence

- (a) The Windows MADT of this unit (`sources/windows/live-inventory/acpi/apic.dat`, sha256 `50b032d6...38d0`, decoded with `iasl -d` in a Fedora 44 container) has 12 GICC entries. UID 7 (MPIDR `0x10300`) and UID 11 (MPIDR `0x20300`) have `Processor Enabled: 0`; the other ten are enabled. This agrees with the previous project's patch 0019 and answers Q1 of `hardware/soc-boot/README.md` (Verified; request to the orchestrator below).
- Diff against the packaged DTB, compared as source with labels (`gcc -E` + `dtc -I dts -O dts`, phandle numbers ignored, because they shift when nodes go): exactly the two CPU nodes, their two `cpu-map` `core3` nodes, `cpu_pd7`, `cpu_pd11`, and the `domain-idle-states` line of `system_pd`. Nothing else.
- `CHECK_DTBS=y` (dt-validate) on the variant: 0 warning lines (`dt_validate_warning_lines` in its JSON). The variants script now runs it for every top-level-DTS variant.
- sha256 of the parity DTB: `1db70aa9426f37885c96acce15a3b4b626a8b26c23fc24acd9d5946046c12f71`.

## Requests

- soc-boot (via orchestrator): Q1 is answered by the MADT: MPIDR `0x10300` (UID 7) and `0x20300` (UID 11) are disabled. A real patch for `hardware/soc-boot/patches/` would delete `cpu7`, `cpu11`, `cpu_pd7`, `cpu_pd11` and their `cpu-map` entries; `kernel/dtb-variants/x1p64100-microsoft-denali-parity.dts` shows the working form.
- soc-boot (via orchestrator, revision 4 prerequisite): also carry the parity deletion of `domain-idle-states` from `&system_pd` (no system SS3; retain CL4/CL5) in the component patch. Kernel will integrate it once delivered; no patch is invented in the component owner's folder.
- audio-speakers (via orchestrator, revision 4 prerequisite): deliver a board DT patch disabling both `/sound` and `&swr0`, matching the M5/M6 overrides, so the **packaged** DTB also enforces S1. Keep it disabled until speaker protection is evidenced; validate with `scripts/kernel-dtb-safety.py`.
- image (via orchestrator): ship `x1p64100-microsoft-denali-m6.dtb` and its JSON for the next default device entry at the unchanged M3 kver. `x1p64100-microsoft-denali-m6gpu.dtb` is staged for later GPU work and gets **no menu entry now**. No device test was performed by kernel; batch any read-only evidence collection in the image collector.

## M5 DTB variants (D21)

Both build on `x1p64100-microsoft-denali-parity.dts` (included by the file) with the speakers off (S1). Kver stays `7.3.0-65.sp11.3.fc44.aarch64`; DT-only.

| File | Content | sha256 |
|:--|:--|:--|
| `x1p64100-microsoft-denali-m5.dtb` | parity + `/sound` disabled + `&swr0` disabled + `&gpu` disabled | `7c5f8155248661ce11700cdf8ed5c126225fd597d38ab4bef83d867094e3074d` |
| `x1p64100-microsoft-denali-m5gpu.dtb` | parity + `/sound` disabled + `&swr0` disabled, GPU as in parity | `91dfcab143810907aaece65549b77d3c34c2357820723c7a28b9db9fe0773ffc` |

- Source diff against the parity DTS (`gcc -E` + `dtc -I dts -O dts`, phandle lines dropped), stored in each JSON under `checks.diff_vs_base`: only `status = "disabled"` lines (m5: swr0, gpu, `/sound`; m5gpu: swr0, `/sound`). `dt-validate` (`CHECK_DTBS=y`): 0 warning lines for both.
- S1 check (`scripts/kernel-dtb-safety.py`, in each JSON under `checks.s1_effective_status`): the DTB is decompiled with `dtc -I dtb -O dts`, the node tree is walked, and a node counts as enabled only if it and every ancestor has `status` absent or `okay`. Nodes watched: `compatible` containing `wsa884`, `sdw20217020400` (how the two WSA8845 speakers enumerate on SoundWire; the strings `wsa884` and `x1e80100-sndcard` do not appear in their `compatible`) or `x1e80100-sndcard`. Result in both: `/sound` own status disabled; `speaker@0,0` and `speaker@0,1` have no status of their own and are effectively disabled through `soundwire@6b10000` (`&swr0`, disabled); 3 nodes watched, none enabled. `scripts/kernel-dtb-variants.sh` records this for every M5 build.
- GMU and `gpu` (7.3 sources in `sources/linux/drivers/gpu/drm/msm/`): no driver binds the GMU node. The only `qcom,adreno-gmu*` string in the driver is `a6xx_gpu.c:2715` (`of_device_is_compatible(node, "qcom,adreno-gmu-wrapper")`), and the platform driver `adreno_driver` (`adreno/adreno_device.c:408`) matches the GPU compatibles only. The GMU is reached through the GPU node's `qcom,gmu = <&gmu>` (`hamoa.dtsi:4007`): `a6xx_gpu.c:2711` takes the phandle (`BUG_ON(!node)` if absent), `a6xx_gmu_init()` (`adreno/a6xx_gmu.c:2282`) calls `of_find_device_by_node()` on it. That lookup runs only from `adreno_load_gpu()`, which `msm_open()` calls (`msm_drv.c:271`, "load gpu on open"). With `&gpu` disabled, no GPU platform device exists, so nothing reaches the GMU. The GMU needs no disabling: it stays enabled as an inert platform device (effective status in the DTB: enabled, no driver). Disabling it too would only remove the `gmu@3d6a000` platform device and its power-domain/clock consumers.

## M6 DTB variants (2026-10-28)

DT-only, still `7.3.0-65.sp11.3.fc44.aarch64`, `series_rev = 3`. No RPM build or config change. The top-level `m6.dts` includes the M5 overrides: 10 CPUs, no system SS3, `/sound` and `&swr0` disabled (S1), GPU disabled. `m6gpu.dts` includes M6 and enables only the GPU, for later work with no menu entry now.

`scripts/kernel-dtb-m6.sh` builds just these variants; `scripts/kernel-dtb-variants.sh` also invokes it after M5. It exports the pinned v7.3 commit into disposable `out/linux/m6/` without git writes, applies display-lcd 0001–0003, then Wi-Fi 0001 and USB-C 0001. The build uses `scripts/kernel-dev.sh --check m6 variant ...`, which takes `out/.kernel-build.lock` and keeps both BTF config symbols enabled. The packaged `kernel/series`, config and revision remain unchanged.

Checks and logs live in `out/build/dtb-m6-checks/`; DTBs and JSON records live in `out/dtb-variants/7.3.0-65.sp11.3.fc44.aarch64/qcom/`. Records include all five patch hashes, included DTS hashes, the normalized `dtc` diff against M5/M5GPU, explicit `dt-validate` results, effective speaker/GPU status and DTB sha256. Source recompilation must be byte-identical to both the reference and new DTBs before accepting the labeled diff (generated numeric phandles can shift). The diff gate permits only Wi-Fi's PCIe4 pinctrl/PERST#/WAKE# and USB-C's second retimer reset state; the S1 gate requires `/sound`, `&swr0` and both speakers disabled.

| File (JSON record with the same stem) | sha256 |
|:--|:--|
| `x1p64100-microsoft-denali-m6.dtb` | `290d7f4957673822ad04c66a47724f1c21ca333948e24802b5cb42226c590ab6` |
| `x1p64100-microsoft-denali-m6gpu.dtb` | `59d023175a79be4e177b18d5106544326dec03f6428537896984d5d91fdc3bc4` |

Both built successfully (41 s / 11 s, excluding the shared-lock wait). `CHECK_DTBS=y` and explicit `dt-validate` passed with no diagnostics; `kernel-dtb-safety.py` returned 0 for both (three watched nodes, none enabled). The complete normalized diffs contain only the two component patches. BTF and BTF modules remain enabled in the dev config. These artifacts have not been run on the device.

## Planned series revision 4 (not built)

This is a future release plan only. Do not bump `kernel/base.toml`, modify `kernel/series` or `kernel/config/sp11.config`, or start an RPM build as part of M6.

1. Retain display-lcd 0001–0003; append `hardware/wifi/patches/0001-arm64-dts-qcom-denali-wire-pcie4-perst-wake.patch` and `hardware/usb-typec/patches/0001-arm64-dts-qcom-x1-microsoft-denali-add-the-second-re.patch` to `kernel/series`.
2. Integrate the audio-speakers S1 patch requested above so the packaged board DTB disables `/sound` and `&swr0`, rather than depending on an extra diagnostic DTB. Delivery and cross-check by the owner are prerequisites.
3. Once soc-boot delivers its patch, integrate the 10-CPU topology (remove CPU7/11, their CPU-map entries and PSCI domains) and no-system-SS3 change. Keep cluster CL4/CL5. Use the existing parity variant as the comparison reference.
4. Add `CONFIG_ATH12K_DEBUG=y` to `kernel/config/sp11.config` (Wi-Fi K2; symbol: `sources/linux/drivers/net/wireless/ath/ath12k/Kconfig`). **A config change invalidates the whole ccache**; budget for a full compilation even with the persistent cache and `CCACHE_NOHASHDIR=1`. Keep `CONFIG_DEBUG_INFO_BTF=y` and `CONFIG_DEBUG_INFO_BTF_MODULES=y`.
5. After the component patches arrive and the series order is final, set `series_rev = 4` and recompute `series_sha256` together. Expected kver: `7.3.0-65.sp11.4.fc44.aarch64`. Check patch application/checkpatch (without signoff), config survival, DT validation and S1 on the packaged DTB, then perform the authorized release build under the build lock and run `scripts/kernel-check` (including kernel/module BTF). The image default must continue to disable the GPU per D22.

## Log

- 2026-10-28: built and statically validated M6/M6GPU DT-only artifacts and JSON records; no RPM, series, revision or config change. Prepared the unbuilt revision 4 plan; component integration requests remain in Requests. Kernel is a service worker with no `component.toml`; hardware component status files are owned by their workers. Changes left uncommitted for the orchestrator (D24).
