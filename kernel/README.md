# Kernel

Owner: kernel worker (`agents/workers/kernel.md`).

| File | Content |
|:--|:--|
| `base.toml` | Pinned base: `sp11-linux` tag `v7.3`, commit `c03c1a14507d` |
| `config/sp11.config` | Kconfig fragment merged on the Fedora 44 aarch64 config. Carries BTF (D2) |
| `series` | Ordered component patch paths plus `kernel/patches/` for kernel-owned integration changes |

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
| 4 | M7: display 0001–0003, Wi-Fi 0001, USB-C 0001, SAM 0001/0003, touch diagnostic 0014, S1 | `kernel-7.3.0-65.sp11.4.fc44.aarch64` |
| 5 | M8: retained M7 fixes/S1, GPU off, spi-hid v7 0001–0011 and touch 0016–0020; RFC 0014 retired | `kernel-7.3.0-65.sp11.5.fc44.aarch64` |
| 6 | M9: retain M8; Surface ath12k rfkill workaround, DMA32 CMA window, PMIC-GLINK/PS8830 diagnostics | `kernel-7.3.0-65.sp11.6.fc44.aarch64` |
| 7 | M10: retain M9; read-only GLINK OPEN_ACK diagnostic (R-K1) | `kernel-7.3.0-65.sp11.7.fc44.aarch64` |
| 8 | M11: retain M10; FIFO diagnostic, packaged parity, audio safety and opt-in fragments | `kernel-7.3.0-65.sp11.8.fc44.aarch64` |

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

- image (M11): consume revision-8 RPMs and the `m11`, `m11-notouch`, `m11-audio` DTBs only after the release/variant checks below pass. Default remains touch on, GPU off, speakers and `/sound` off; microphone entry alone enables the card with no WSA link and `swr0` off. Keep D19–D24, the fixed/touch module chain, D23 blacklist and image L0/L1 gates. Adapt the image S1 check to the same narrow microphone exception; speaker-enabled entries must fail. No `m11-audio-spk` build or boot is authorized by this delivery.
- dsp-subsystems (M11, R-K1 format follow-up): the retained 0001 diagnostic emits the same three compiler format warnings as M10: two `%#x` arguments are `unsigned long` (lines 407/422), and `size=%u` receives `size_t` (line 754). Correct the diagnostic types in an owner patch or retire 0001 after evidence; no component patch was modified by kernel. Full-size printed intent values must not be inferred from a truncated log field.
- dsp-subsystems (M11, R-K3 via orchestrator): FIFO diagnostic 0002 is integrated after R-K1. Collect its ratelimited FIFO line with the existing OPEN_ACK log during the next scheduled boot, using the owner's read-only collector requests; remove both temporary diagnostics once sufficient evidence exists. No functional CDSP fix is claimed.
- audio-speakers / orchestrator (M11): triage patch 0003's generic new-file MAINTAINERS warning. Preserve S1: the gain/volume patches do not authorize speaker output. Independent gain/port-map and soc-boot/touch cross-checks remain required for component promotion; this build supplies static evidence only.

- soc-boot (fulfilled by M11 patch 0001): MADT-disabled CPU7/CPU11, their CPU-map entries and PSCI domains are now removed by the component patch in the packaged LCD board. The historical parity variant remains available for old source snapshots.
- soc-boot (fulfilled by M11 patch 0001): the packaged LCD DT now excludes the system SS3 reference and retains CL4/CL5. New-series variants use the staging shim described in the M11 section, so the parity deletions are applied once.
- audio-speakers (via orchestrator): take ownership of `kernel/patches/0001-arm64-dts-qcom-denali-lcd-disable-unprotected-speakers.patch`. The operator explicitly authorized kernel to write this integration patch for M7. It copies the M5/M6 overrides into the packaged LCD DTB: `/sound` and `&swr0` disabled. Preserve both in packaged/default DTBs; M11 permits the microphone-only exception described below. Arrange the independent safety cross-check, and validate with `scripts/kernel-dtb-safety.py`.
- gpu (via orchestrator): take ownership of `kernel/patches/0002-arm64-dts-qcom-denali-lcd-disable-gpu.patch`. It carries the existing D22 GPU-off policy into the packaged LCD DTB; M8 and its fallback inherit it. No GPU operating point, limit or firmware change is introduced.
- image (historical M9 delivery; superseded by M11): M9 superseded M8 after the checks below. Use revision-6 RPMs with `x1p64100-microsoft-denali-m9.dtb` by default and `x1p64100-microsoft-denali-m9-notouch.dtb` as the touch-disabled fallback. Ship the rebuilt `ath12k`, `ps883x` and `pmic_glink_altmode`; replace matching early USB-C modules in the initramfs, and assert the 2–4 GiB CMA allocation range in every shipped device DTB. Retain M8 artifacts for rollback. Include `fixed` in the initramfs and its L0 display-chain assertion: M8 follows the touch development fragment's `CONFIG_REGULATOR_FIXED_VOLTAGE=m`, while M7 had it built in. Ensure the SPI-HID/OF, GENI, GPI, fixed-regulator and uinput runtime chain is available; stage native iptsd per the touch dossier. Preserve D19–D24 policy, including the qcom_battmgr blacklist. Run image L0/L1 before a device boot. Stage the collector and call exactly `shsnap touch-pen.txt 'bash /usr/libexec/sp11-touch-pen-collect'`. Kernel performed no device test.
- orchestrator: the M9 checkout started clean at `1e52dce`, already equal to main, so no rebase was needed. Review and commit these worker changes under D24. Triage the unchanged spi-hid v7 strict findings (6 warnings, 11 checks, 0 errors) and commission the touch owner's pending independent Claude cross-check of QSPI constants/TREs and the v7 rebind port before clearing the component/device gates. Retain the Wi-Fi owner's independent DMA32-window/wiring cross-check and sources pin request SRC1, and the USB-C owner's wiring cross-check/Windows-comparison requests. M9 integration and static checks do not close hardware acceptance gates.

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

## M7 series revision 4 (2026-10-29)

The operator authorized the M7 release, superseding the M6-only plan. The nine patches in `kernel/series` retain display-lcd 0001–0003 and add Wi-Fi 0001, USB-C 0001, ec-sam 0001/0003, temporary touch diagnostic RFC 0014 and the kernel-owned S1 patch. SAM `hold/` patches, spi-hid and the touch child remain excluded. `CONFIG_ATH12K_DEBUG=y` is the sole added config symbol; both BTF symbols remain enabled.

- Series SHA-256: `3650a885706d4ced42f9391ee0f9535ef10108428df42066b3a21837a703f75c`.
- All nine patches pass `perl sources/linux/scripts/checkpatch.pl --strict --no-signoff - < PATCH` (0 errors/warnings/checks). Passing patch content on stdin avoids checkpatch treating tracked project patch files as source files.
- S1 source facts: the inherited card and speaker routes are in `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:309` and its speaker controller at `:1079` (Verified from pinned v7.3). The new patch disables only the LCD board's card and `swr0`; no amplifier parameters or firmware are changed. Ownership transfer is requested above.
- The initial guard refused the build with 37 GiB real headroom. Under `out/.kernel-build.lock`, removed only reproducible M3 RPM build output and duplicate build-tree RPMs after checking their hashes against preserved `out/rpms/` copies. Historical logs, BTF/config checks and timings are retained in `out/build/kernel/history/m3/`. No guard threshold override was used.
- A first 11 s attempt failed in `%prep` because the S1 hunk used context changed by display 0003. The corrected hunk dry-runs on the other eight patches; the failed attempt is retained in `out/build/kernel/history/m7-prep-fail/`. The build wrapper now replaces Fedora spec's `git apply` with Fedora `patch --batch --fuzz=0 -p1`, and always stops/reaps its watchdog after a failed build.
- Build warnings: one transient 0.78 s `modules.order` clock-skew warning; the unchanged Myricom `myri10ge_dummy_rdma` uninitialized-buffer warning; unprivileged dracut `ldconfig`; and optional `gdb-add-index` failures because BFD lacks zstd support. The latter three also occur in the preserved successful M3 log. GDB indexes are therefore not claimed; the separate ELF BTF audit remains mandatory. The completed module build and forced DT schema check are recorded below.
- Release `scripts/kernel-build.sh -j 6`: **PASS**, UTC `2026-10-29T00:56:08+00:00` to `2026-10-29T01:50:47+00:00`, **3279 s (54 min 39 s)**, rpmbuild rc 0. `scripts/kernel-check` completed at `2026-10-29T01:53:22Z` and returned **PASS**.
- BTF: `vmlinux` `.BTF` size `0x76c7e2`; **5930/5930** packaged modules have valid BTF (zero missing, zero bad magic). All **63** fragment symbols hold, including ATH12K_DEBUG and both BTF settings. Forced `CHECK_DTBS=y`: rc 0, zero warning lines.
- Packaged DTB: SHA-256 `57264ad0188cebc9c284624edc2e387d54e3a5b5317f2a94608e5c4f25aa8414`. S1 passes: `/sound` and `swr0` explicitly disabled; the card and both WSA8845 speakers effectively disabled. Wi-Fi: PCIe4 `pcie4_default`, active-low PERST# GPIO146 and WAKE# GPIO148. USB-C: the second retimer consumes `rtmr1_default` (GPIO176, GPIO function, drive strength 2, bias disabled).
- RFC 0014: the full `touch-pen-diag: proto=...` format string is present in the RPM-extracted `kernel/drivers/spi/spi-geni-qcom.ko.xz`. Compressed module SHA-256 `444271a8f857fc7e4f25a6699d0f1e946cbb2fc0a7f2efa94bcbd86cd4f0655d`; decompressed ELF SHA-256 `aba05e29f947ed2e96b863459c9d6d7aea7e74e099f11d78b49d27b8ce7b7eac`.
- Resource accounting: peak cgroup **9496682496 bytes (9.50 GB)** including file cache; peak anonymous **3387310080 bytes (3.39 GB)** sampled every 3 s; minimum real headroom **37 GiB**. Cache: 2242 direct + 24244 preprocessed hits, 130 misses, **99.51%** hit rate. This config change did not invalidate the entire cache.
- Config SHA-256: fragment `3bf10e3ee53a1568bbe9b74e5c91372116ae8308f586a378a041d401afeb1ef7`; shipped config `15be3d2bbe1fc57ef16ac5a953228c64bf5898bdefc0432e2c0bf7150f92517d`.
- Build record: [`out/rpms/kernel-7.3.0-65.sp11.4.fc44.aarch64.json`](../out/rpms/kernel-7.3.0-65.sp11.4.fc44.aarch64.json), SHA-256 `8abc7fc04c9fa19df60abd2a5b9eb202807322515796e9d2103cb90662d2e704`. It contains the base/spec pins, config and series hashes, exact build times, BTF audit, packaged S1/wiring/message evidence and all 15 RPM hashes. Detailed log: `out/build/kernel/m7-driver.log`.

| RPM (all revision 4, aarch64) | SHA-256 |
|:--|:--|
| `kernel-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `9f712f276d0c12b90f48478df212b92d2b967207f6d6cbce7f5cd5aff8f38761` |
| `kernel-core-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `426cc65fbc6a16a59a359c36a273a31a13f4ae217d5b1db141dc358e8e5654a0` |
| `kernel-debuginfo-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `76328e8f1f3bf24ab2ad469cfb8d2c05075b60e27044c7ab83c612a72b412be6` |
| `kernel-debuginfo-common-aarch64-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `293325927d38f5a053e4995724053ac884484595a88c88725ab9d7c8e915d930` |
| `kernel-devel-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `d02fd64c3ce2852e1a572a60416df000b57bd1cfb38f3f1b28dae58cfd29892b` |
| `kernel-devel-matched-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `740d32ceb34aa3cc3fef0c1e23699ebf228f01030e163f913de970457148c0d0` |
| `kernel-kmap-internal-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `3dcd24e9d290c260197cf9a6ac7131cc63bb40555bcaea5e8050054faef290c7` |
| `kernel-modules-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `81849fda0475f65bb4e1d532e47b56e8238961f92e59986f39595479d3d2a05e` |
| `kernel-modules-core-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `e54e0aa81515ad080cfb5f3d131b28262cf19d454a7671167710cf0bf899d2be` |
| `kernel-modules-extra-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `7190f561bf5e4014e448b99cdeff2dfe9f7fd34fb826da0e3a71e41dcd06eea0` |
| `kernel-modules-extra-matched-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `1d19034d16bc53091abff66819adc683716fc370d4a849e95bee56dc694463c7` |
| `kernel-modules-internal-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `92ffac9d575236cb56785f17a249fe870d06e26bc24b55b439d28564e656230e` |
| `kernel-uki-dtbloader-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `89fff973c8aef4a4600093a7771922cb7221f46283a6147c5ef15af427131e81` |
| `kernel-uki-virt-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `86c8c7dc9e5870e4c7e88bf8b5ac1f56a7c268671a6cd818512b88f646449df0` |
| `kernel-uki-virt-addons-7.3.0-65.sp11.4.fc44.aarch64.rpm` | `bc2fe273205a3abc4484cc51bafbed4c06bdeb7b1e64d6d0edcce5321b04e8ed` |

### M7 DTB variants

`scripts/kernel-dtb-m7.sh` (also selected by `scripts/kernel-dtb-variants.sh` for revision 4) exports the pinned source into disposable `out/linux/m7/`, applies exactly `kernel/series` with `patch --fuzz=0`, and builds through `scripts/kernel-dev.sh --check` under the shared lock. It requires the checked RPM release and compares a standalone source recompilation byte-for-byte with the packaged DTB and each new variant. DTBs and JSON records go to `out/dtb-variants/7.3.0-65.sp11.4.fc44.aarch64/qcom/`.

- `m7`: the rev-4 packaged DT plus the existing parity include (10 CPUs; no system SS3; keep CL4/CL5), with GPU disabled.
- `m7-touchdiag`: M7 plus the complete body of `hardware/touch-pen/touch-pen-state.dts`, with only its redundant board include removed into a generated `.dtsi`. This enables QUP1 SE2 (`spi10`, `spi@a88000`), retains stock GPIO40–43 pinctrl and deletes wrapper `firmware-name`. It adds no HID child or supply. The source file and transformation are recorded in JSON.

The variant checks require zero schema diagnostics, S1 effective status, Wi-Fi PERST#/WAKE# and USB-C retimer pinctrl, ten CPUs with the fused-off PSCI/map nodes absent, no system SS3 reference, cluster idle states retained, GPU off, no enabled HID child and no enabled touch supply/consumer. The diagnostic DT must differ from M7 in exactly the SE2 `status` property. Logs and source-form diffs live in `out/build/dtb-m7-checks/`. No hardware behavior is claimed from these static checks.

Both variants **PASS** `CHECK_DTBS=y`, explicit `dt-validate` (zero diagnostic lines), byte-identical standalone source recompilation, S1, wiring and touch exclusion gates. The reconstructed base DTB also matches the packaged DTB byte for byte. Full variant-run UTC `2026-10-29T01:53:42.667744+00:00` to `2026-10-29T01:56:19.581096+00:00`: **164.110 s**, including source export, patching, dev configuration, compilation and checks. Individual build times below exclude preparation and lock waits.

| DTB | Build time | SHA-256 |
|:--|--:|:--|
| `x1p64100-microsoft-denali-m7.dtb` | 43 s | `290d7f4957673822ad04c66a47724f1c21ca333948e24802b5cb42226c590ab6` |
| `x1p64100-microsoft-denali-m7-touchdiag.dtb` | 12 s | `3b97decd8bde2831e725b22ed80c038cdf5bf043ea81f438de9aa46850bb3554` |

JSON record SHA-256:

- [`x1p64100-microsoft-denali-m7.json`](../out/dtb-variants/7.3.0-65.sp11.4.fc44.aarch64/qcom/x1p64100-microsoft-denali-m7.json): `96a466706ed4235fd08a9cee79492fc3ea93f8a50620a6b9300ce0659d916420`.
- [`x1p64100-microsoft-denali-m7-touchdiag.json`](../out/dtb-variants/7.3.0-65.sp11.4.fc44.aarch64/qcom/x1p64100-microsoft-denali-m7-touchdiag.json): `076f2668c1cf63594417c03d1dcaedb8b827565816e140debbc30e7bb0429d71`.

The complete labeled source diff of M7 against the packaged DT contains only deletion of CPU7/CPU11, their CPU-map entries and PSCI domains, deletion of the system SS3 reference, and GPU disable. M7 is byte-identical to the M6 default DTB (`290d7f49...`); the new kernel code/config are in the revision-4 RPMs. The diagnostic differs from M7 in exactly `/soc@0/geniqup@ac0000/spi@a88000:status` (`disabled` to `okay`). Both have ten CPUs, retain cluster CL4/CL5, disable the GPU/card/speaker bus, and contain no touch supply node or enabled HID child/consumer. The diagnostic retains only stock SE2 data/clock/CS pinctrl; wrapper `firmware-name` is absent.

Verification of the new DT checker also rejected three modified fixtures: sound enabled, HID child enabled, and touch supply enabled. Logs stay in `out/build/dtb-m7-checks/negative/`. `scripts/index.py --check`: 21 components, zero errors. Shell syntax and `git diff --check` pass. No kernel/release/dev container remains; both build/source locks are free. No device test was performed. All tracked changes remain uncommitted for the orchestrator under D24.

## M8 series revision 5 (2026-10-29)

The clean worker checkout already matched `main` at `bd657c2`; no rebase or other git write was needed. The release has 25 patches: the revision-4 display, Wi-Fi, USB-C, SAM and S1 changes, a kernel-owned LCD GPU-disable patch, and the exact 16-entry order from `hardware/touch-pen/kernel-series.list` (unchanged v7 0001–0011, then 0016–0020). No component patch was edited. Series SHA-256: `406324e9a22a7dea0bb162e344d14531b620e74088e4366cbf33986bd23dbe0a`.

RFC 0014 is retired because its temporary controller-only probe dump is superseded by the selected QSPI implementation and normal SPI/HID/GPI diagnostics. It is not a driver dependency. All 25 patches apply to the pinned v7.3 export in `out/linux/m8/` with `patch --batch --fuzz=0 -p1`, without conflicts or fuzz. Removing its eight lines causes six 0018 hunks to apply with a -8 line offset; the GPU override causes two 0020 hunks to apply with a +4 offset. The pre-existing Wi-Fi offset is unchanged. The release module check requires the old diagnostic string to be absent. Application log: `out/build/dtb-m8-checks/series-apply.log`.

The fragment pins SPI_MEM, SPI_HID/OF/ACPI, SPI_QCOM_GENI, QCOM_GPI_DMA, REGULATOR_FIXED_VOLTAGE, HID_MULTITOUCH, HIDRAW and INPUT_UINPUT, while retaining both BTF symbols. Patch 0020 enables touch only in the LCD board DTS. All three delivered M8 LCD DTBs (packaged, `m8`, `m8-notouch`) must keep `/sound`, `swr0` and the GPU disabled; the packaged board gains the same GPU isolation as the variants. Display KMS remains enabled. The fixed-regulator driver is modular in this fragment (`=m`, matching the touch development fragment) rather than M7's built-in `=y`; the image request above requires `fixed` in the initramfs and L0 chain check. There is no touch firmware request, limit change or device test.

Strict checkpatch was run on patch content, in Fedora, with `--strict --no-signoff` against the composed source tree: **0 errors, 6 warnings, 11 checks**. All findings are the unchanged v7 baseline's documented new-file/MAINTAINERS, short-help and trace-style findings; all other selected patches are clean. The full-series strict lint gate remains open for orchestrator triage. Logs: `out/build/dtb-m8-checks/checkpatch.{log,json}`. The touch owner's pending independent cross-check of QSPI constants/TREs and the v7 rebind port remains an orchestrator gate; this release build does not promote the hardware component's status.

Before release, `scripts/kernel-dev.sh --check m8 dtbs` completed in **45 s**. All development fragment symbols hold; explicit `dt-validate` has zero diagnostics. Compiled-DTB S1/GPU, Wi-Fi/USB-C and QSPI/touch wiring checks pass. Five modified fixtures are rejected: sound enabled, GPU enabled, touch disabled in the active DT, incorrect GPI DMA selector, and a wrapper firmware request (`out/build/dtb-m8-checks/negative/results.json`).

The release disk guard was retained unchanged. Under the shared build lock, preserved M7 logs/stats/checks in `out/build/kernel/history/m7/`, verified every M7 RPM against its release-record hash, and removed only its reproducible RPM build tree and duplicate build-tree RPMs. All M7 release RPMs and JSON remain in `out/rpms/` until the successful revision-5 build archives them. No other owner's output was removed and no threshold override was used.

### M8 release artifacts

`scripts/kernel-build.sh -j 6` and its automatic `scripts/kernel-check`: **PASS**. RPM build UTC `2026-10-29T15:51:23+00:00` to `2026-10-29T16:46:36+00:00`, **3313 s (55 min 13 s)**; verification record completed `2026-10-29T16:50:22Z`. All 15 delivered RPM copies match the build record's SHA-256 values.

- BTF: `vmlinux` `.BTF` size `0x76c5c4`; **5934/5934** RPM-extracted modules have BTF, zero missing and zero bad magic. All **73** fragment symbols hold in the shipped config, including both BTF settings. Forced `CHECK_DTBS=y`: rc 0, zero warning lines; explicit packaged-DTB `dt-validate`: zero diagnostics.
- Packaged LCD DTB SHA-256: `005397721c30b4bd6beffd67e50f09f7a2845252292d0e58b1f558899d133ad6`. S1 effective status, explicit card/speaker-bus disablement, GPU off, Wi-Fi/USB-C wiring, QSPI selector4, four-lane touch, IRQ/reset/supply pins and 500 ms cold-power delay pass. No touch-path `firmware-name` is present. The packaged DT retains 12 CPUs and system SS3; the device variants add parity below.
- `spi-hid`, `spi-hid-of`, `spi-hid-acpi`, `spi-geni-qcom`, `gpi`, `fixed`, `hid-multitouch` and `uinput` are all present in **kernel-modules-core**. The extracted SPI-HID OF module has MSHW0484 SPI/OF aliases; GENI has the QSPI compatible and preloaded-protocol guard; GPI has the QSPI TRE path. The retired RFC logger is absent. Each compressed module hash, ELF hash, alias list and owning RPM is recorded under `m8.touch_modules` in the release JSON.
- Resource accounting: peak cgroup **9563340800 bytes (9.56 GB)** including file cache; peak anonymous **3283501056 bytes (3.28 GB)** sampled every 3 s. Minimum real headroom: **46 GiB**. Cache: 2242 direct + 24056 preprocessed hits, 325 misses, **98.78%** hit rate.
- Config SHA-256: fragment `4a34894d4e50150bede28a45c937c2a63fd9fa96724f2291c022a2a8d857ee98`; shipped config `29e8acabb7993605d28cae6a64ebad09ce0e371197f38f6573d4e20dd5b35148`.
- Nonfatal build diagnostics match the preserved M7 log: 0.35/0.33 s file timestamp skew, unchanged Myricom uninitialized-buffer warning, bpftool compiler-flag probe, debugedit `.debug_names`, and optional `gdb-add-index` failures because BFD lacks zstd support. GDB indexes are not claimed. Fedora also reports its normal absolute `build` symlink. These do not replace the separate successful BTF audit.
- Release record: [`out/rpms/kernel-7.3.0-65.sp11.5.fc44.aarch64.json`](../out/rpms/kernel-7.3.0-65.sp11.5.fc44.aarch64.json), SHA-256 `1e930020a269c1104bcd0682f1bd463886089e3846b6babdc594f9bb25a1d007`. It contains all input pins, exact build times, resource/cache statistics, BTF/config/schema checks, packaged DT safety/wiring and module payload evidence, and all RPM hashes. Detailed log: `out/build/kernel/m8-driver.log`. M7 RPMs and records are archived in `out/rpms/archive/7.3.0-65.sp11.4/`; preserved build evidence is in `out/build/kernel/history/m7/`.

| RPM (all revision 5, aarch64) | SHA-256 |
|:--|:--|
| `kernel-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `eb535ac9e974865174a612e5d004bd93185b3e21a3e18050f394fdfab324d245` |
| `kernel-core-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `fcd3e00ad38802e828cf35bb36b406971c792ee43358c144fee22ff69da9e2a5` |
| `kernel-debuginfo-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `0ea7e72f9b147f1f5019229e9178a60b620ca661bce0f2095c578f7750cf384e` |
| `kernel-debuginfo-common-aarch64-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `de4a8f1d429f0217dadb7192d6c6c7a6c06c6d6f4a28399ecc161f2e329226c3` |
| `kernel-devel-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `1375cadcfbba69e4b72a1e36e8ed94a21c657f7b4bea40e4c1b3acc606db794f` |
| `kernel-devel-matched-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `4ba788252fc2bf587263729f4edfc604d13c814220d12638ff02ae5e14e64571` |
| `kernel-kmap-internal-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `22ede175e253b73eb343d4a9f0785ac7b4ad4f00ab256226e1957f031f52f3f2` |
| `kernel-modules-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `28d1e9509301588f90e753d5265cd670d4bfe2bbdc19bc293cdf0a29b303afe9` |
| `kernel-modules-core-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `8ee791a0a44c5d5af94de9304352dffe4c6a98d5dc211003a4326fc9ba417010` |
| `kernel-modules-extra-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `6f16cbc70e4b15f90a1a69c489005b44112c228472750cf037535814b7a9e964` |
| `kernel-modules-extra-matched-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `bc279cc1484866625a29a15dc1290e4ef596d56f576f0bcdf2123de200f077a8` |
| `kernel-modules-internal-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `6411171bf1d9f50b3a41a61cc73e79f99c95e7dea6c3f58133ac6195f66beea5` |
| `kernel-uki-dtbloader-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `9c79e98b18febe1aab258b98252f12224df9927a3ebed713f886587ee3f1e109` |
| `kernel-uki-virt-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `40b452cd9d85f9c85ab59e139a7f61bf22536266b96d35d313a6cd055f29ada4` |
| `kernel-uki-virt-addons-7.3.0-65.sp11.5.fc44.aarch64.rpm` | `ac26d655d97f602777588ab655a122db9c465c1df99425874047757f4145bcd3` |

### M8 DTB variants

`scripts/kernel-dtb-variants.sh` dispatches revision 5 to `scripts/kernel-dtb-m8.sh`. It exports pinned v7.3 without git writes into `out/linux/m8/`, applies the full series with zero fuzz, and builds both variants through `scripts/kernel-dev.sh --check` under the shared lock. Output: `out/dtb-variants/7.3.0-65.sp11.5.fc44.aarch64/qcom/`; logs and normalized source diffs: `out/build/dtb-m8-checks/`.

- **m8:** the packaged LCD DT plus the existing parity include: delete CPU7/CPU11, their PSCI domains and CPU-map entries, and the system SS3 reference. Keep cluster CL4/CL5. Touch stays enabled by 0020; GPU and speakers inherit the packaged disablement.
- **m8-notouch:** exactly m8 with `/soc@0/geniqup@ac0000/spi@a88000/touchscreen@0:status = "disabled"`. The controller, supply description and pinctrl remain identical. The disabled child is not an active supply consumer, and the regulator has neither boot-on nor always-on.

Both **PASS** `CHECK_DTBS=y`, explicit `dt-validate` with zero diagnostics, S1 effective status, GPU-off, Wi-Fi/USB-C wiring, parity and QSPI/touch checks. Each built DTB matches a standalone recompilation byte for byte, and the reconstructed baseline matches the RPM DTB byte for byte. The complete label-preserving diff confirms only the parity deletions above for m8. The strict compiled-DTB comparison for m8-notouch finds exactly one changed property. A sixth negative fixture (extra root model change in the fallback) is rejected; its log joins the five earlier safety/wiring fixtures under `negative/`.

Full run UTC `2026-10-29T16:50:31.960498+00:00` to `2026-10-29T16:53:55.398864+00:00`; elapsed **214.464 s** measured with the monotonic clock, including preparation, configuration and checks. Individual helper times below exclude preparation and lock waits. Every JSON records the base commit, all patch/overlay/include hashes, the checked release record/hash, BTF config, schema/safety/wiring results and the full source diff. No device behavior is inferred from these static checks.

| DTB | Build time | SHA-256 |
|:--|--:|:--|
| `x1p64100-microsoft-denali-m8.dtb` | 63 s | `1ad30d3e3f928a6db5c5b8bf2649bed8f85baaba3cf2adc6ed542bafe502a0e6` |
| `x1p64100-microsoft-denali-m8-notouch.dtb` | 14 s | `6dbac355db7f081b5f77db4558e646efaef14eff7d90a51ed9afcdd44b4eebb7` |

JSON record SHA-256:

- [`x1p64100-microsoft-denali-m8.json`](../out/dtb-variants/7.3.0-65.sp11.5.fc44.aarch64/qcom/x1p64100-microsoft-denali-m8.json): `4f8cfeede57a6a1b0fed9d568ed83cf8cb723e44e344598b47195ec4797c070c`.
- [`x1p64100-microsoft-denali-m8-notouch.json`](../out/dtb-variants/7.3.0-65.sp11.5.fc44.aarch64/qcom/x1p64100-microsoft-denali-m8-notouch.json): `f07b0f52487a4ed68e095781c7a3bfd4b30f5d4a628cfba3fb0f652c2e58b8b5`.

Final hand-back checks: `scripts/index.py --check` reports **21 components, 0 errors**; tracked whitespace, shell syntax and new Python blocks pass. Both the shared build lock and M8 source lock are free. No task container, build, sampler or watchdog remains running. Kernel is a service worker and has no `component.toml`; hardware component status remains owner-managed. Changes remain uncommitted for orchestrator review under D24. Image L0/L1, the fixed-module initramfs addition, v7 lint triage and the pending independent touch cross-check remain the open requests above. No device boot was performed.



## M9 series revision 6 (2026-10-29)

The clean worker checkout already matched `main` at `1e52dce5c23e52130aab3374187c41b0d756d168`; no rebase or other git write was needed. Revision 6 retains all 25 M8 patches in their original order and appends only these three patches after touch 0020:

| Position | Patch | Ordering reason |
|--:|:--|:--|
| 26 | `hardware/wifi/patches/0002-wifi-ath12k-skip-broken-surface-rfkill.patch` | Add the upstream Surface/WCN7850 hardware-rfkill setup bypass in ath12k; independent of touch. Software airplane mode remains available. |
| 27 | `hardware/wifi/patches/0003-arm64-dts-qcom-denali-keep-cma-in-dma32.patch` | Keep the existing reusable 128 MiB CMA pool within 2–4 GiB; follows the Wi-Fi code fix and preserves DT context from the earlier series. Dynamic placement remains with memblock. |
| 28 | `hardware/usb-typec/patches/0002-usb-typec-log-pmic-glink-and-ps8830-state.patch` | Add successful-path state diagnostics to PMIC-GLINK altmode and PS8830 after the existing USB-C patch; independent driver files. This is diagnostic only, with no SuperSpeed fix claimed. |

All 28 patches apply to the pinned v7.3 export with `patch --batch --fuzz=0 -p1`; the three additions have no offsets. Existing M8 offsets are unchanged. Application log: `out/build/dtb-m9-checks/series-apply.log`. Strict checkpatch on the three added patches (patch content via stdin, `--strict --no-signoff`) reports **0 errors, 0 warnings, 0 checks**; log: `out/build/dtb-m9-checks/new-checkpatch.log`. The unchanged v7 baseline findings and independent component cross-check gates recorded for M8 remain open. No component patch or configuration fragment is changed. Series SHA-256: `3955c66bbdd1ba988b95387d02fbf409fc62fee6274dc88707c48a327f176cac`.

M8 release RPM hashes were verified before removing its reproducible RPM BUILD tree and duplicate build-tree RPMs under the shared lock. Its release RPMs, DTBs and JSON remain available for rollback; build logs, statistics and extracted checks are preserved in `out/build/kernel/history/m8/`. The release disk guard and watchdog are unchanged, with no threshold override.

Before release, `scripts/kernel-dev.sh --check m9 dtbs` completed in **46 s**; all **75** development fragment symbols hold. Explicit `dt-validate` gives zero diagnostic lines. Compiled-DTB S1/GPU/touch/Wi-Fi/USB-C gates pass, and comparison with the preserved RPM-extracted M8 DTB finds exactly the CMA `alloc-ranges` addition. Two negative fixtures (CMA above 4 GiB and CMA enlarged to 256 MiB) are rejected. Evidence: `out/build/dtb-m9-checks/preflight-*`, `preflight.*` and `negative/`.

### M9 release artifacts

`scripts/kernel-build.sh -j 6` rpmbuild: rc 0, UTC `2026-10-29T22:37:24+00:00` to `2026-10-29T23:50:14+00:00`, **4370 s (72 min 50 s)**. The worker session ended before the post-build steps; they were completed afterwards by running the archive/collect block of `scripts/kernel-build.sh` step 6 and `scripts/kernel-check` under the shared build lock (check: 142 s, **PASS**, record `built_utc` 2026-10-29T23:54:23Z). The sp11.5 RPMs and records were archived to `out/rpms/archive/7.3.0-65.sp11.5/`, as M8 did for M7. All 15 delivered RPM copies match the record's SHA-256 values.

- BTF: `vmlinux` `.BTF` size `0x76c5c4`; **5934/5934** modules have BTF, zero missing, zero bad magic. All **73** fragment symbols hold in the shipped config, including both BTF settings. `CHECK_DTBS=y`: rc 0, zero warning lines; `dt-validate` zero diagnostics.
- Packaged LCD DTB SHA-256 `784de3eb644bc6a169cbe0c6da51cef0f984984493a44e6fbfd00b18cd792709`. S1 effective status (speakers, soundwire, sound card), GPU off, Wi-Fi/USB-C wiring and touch wiring pass. CMA node `/reserved-memory/linux,cma`: 128 MiB, reusable, allocation range 0x80000000 to 0x100000000 (below 4 GiB), dynamic placement.
- `ath12k` carries the Surface broken-rfkill table and the machine-compatible match call (module SHA-256 `2edc4bcd0215c38f7a3ebc8c7d7df0bf44cae75c8970c2b175511fb3706f56c5`). `ps883x` and `pmic_glink_altmode` carry the new state diagnostic strings (module SHA-256 `40f849863b8cd5a622ef64c745c8ee58104ee4ebd0f7209948c407af536e3f82` and `98ba7d000fe8ee57d35e73068734959a1a83ad35288d2a3a277b0eb61ef5900d`). Touch modules are present as in M8; the retired RFC 0014 logger is absent.
- Resource accounting: peak cgroup **9508179968 bytes**; peak anonymous **3354456064 bytes**. ccache hit rate **99.64%** (2239 direct + 24285 preprocessed hits, 95 misses).
- Config SHA-256: fragment `4a34894d4e50150bede28a45c937c2a63fd9fa96724f2291c022a2a8d857ee98`; shipped `ee7943f72297bb7cee3dd6b167c4017ff3891fe630503b355621050fb70b7906`.
- Release record: [`out/rpms/kernel-7.3.0-65.sp11.6.fc44.aarch64.json`](../out/rpms/kernel-7.3.0-65.sp11.6.fc44.aarch64.json), SHA-256 `988dee251c7b3240d25595cbf64d07529d6aada939db257150c228960425ff2b`. Logs: `out/build/kernel/rpmbuild.log`, `m9-driver.log`, `m9-post.log`.

| RPM (revision 6, aarch64) | SHA-256 |
|:--|:--|
| `kernel-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `cd61d31ff42ad5fe1c20c13073d1f2f6abc07d8603b776ae5792552e61ad9f86` |
| `kernel-core-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `e5365c2a4d4eb01c0cb85082d51fc05dd321585b7b48a4399715fc3bd3212f1e` |
| `kernel-debuginfo-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `fdfdc9bb3f1561f9f51a46ce84da7feb77300f371f2aad024bd7925e48d2c380` |
| `kernel-debuginfo-common-aarch64-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `5d7186eac04579b5ec791d6bd447e21c3e9e0d011623d9c36039459ecc67b8c8` |
| `kernel-devel-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `8c8aa14a71a21353ab012566d3b3f262831a92a2b95d2b0fde201a41956b7856` |
| `kernel-devel-matched-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `d896aedc022740e9c66705d37cba037c75be2440208d6398aa162bb02a9102a1` |
| `kernel-kmap-internal-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `a3e63cd3c50f882681b67839bba7c1b525920f19a8bb4aeb768651aad7fdc71a` |
| `kernel-modules-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `95c151d8e953d247003c7b5f3d0fdba1cdf6f8f05a73080e90f77fbeaa6b6824` |
| `kernel-modules-core-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `0b1f4ed2962f7d652c8591b79eb0d47e06cd548d4b8b4a0f643507e76d2d8d6d` |
| `kernel-modules-extra-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `2ec0fd9207f2b8a06b4f9f0833f4932427d49a49915e5dc91466f67f96d646c0` |
| `kernel-modules-extra-matched-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `6c3dbb80f4c9c1b0e1d0934714d6248a467d3c9e57578c46af71cfea1ab15b01` |
| `kernel-modules-internal-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `c1a406c4305e993833c2201b91f73dda9e9c6eef49dcdbb2f117f57ff3a2034d` |
| `kernel-uki-dtbloader-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `310a357e276a40c512c6a7fa68f7ab078db556ba2ef035526dc9834525e77459` |
| `kernel-uki-virt-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `310dcb9de551363892ded3f67603ae70f41528ec7742a757dbfe11d890ee530e` |
| `kernel-uki-virt-addons-7.3.0-65.sp11.6.fc44.aarch64.rpm` | `b486d19d16b807667e755d1a35d8a25a0a1674a3ba4882f1a669d1818805dfc3` |

### M9 DTB variants

`scripts/kernel-dtb-variants.sh` (dispatching to `scripts/kernel-dtb-m9.sh`) ran under the shared lock after the release check; output `out/dtb-variants/7.3.0-65.sp11.6.fc44.aarch64/qcom/`, logs in `out/build/dtb-m9-checks/` and `out/build/kernel/m9-dtb.log`. Complete run **155 s** (wall clock). Both variants pass `CHECK_DTBS=y`, `dt-validate` (zero diagnostics) and the script's S1, GPU-off, wiring, parity and touch checks. `m9-notouch` differs from `m9` only in the touchscreen status property.

| DTB | Build time | SHA-256 |
|:--|--:|:--|
| `x1p64100-microsoft-denali-m9.dtb` | 45 s | `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` |
| `x1p64100-microsoft-denali-m9-notouch.dtb` | 12 s | `5704f68668538f6dd3e6fc37f67e8e9830f771124c57475c0ebca81d8c750519` |

JSON record SHA-256: `x1p64100-microsoft-denali-m9.json` `5e8452a4c95c7878d00211f24c4c030d526f82b32d245f720403d84c523f6c6b`; `x1p64100-microsoft-denali-m9-notouch.json` `0edb7a9a707dbcc20d914cde7d4d6044eb5dc562cd31e54aadbb9114035426d3`. No device boot was performed.

## M10 series revision 7 (2026-10-30)

Revision 7 retains all 28 M9 patches and appends one patch after PMIC-GLINK/PS8830 diagnostics (position 29): `hardware/dsp-subsystems/patches/0001-rpmsg-glink-log-open-ack-timeout.patch`. It is the read-only GLINK OPEN_ACK diagnostic (request R-K1 in `hardware/dsp-subsystems/README.md`): `sp11-glink:` log lines, no behaviour change. Remove it after the evidence is collected. Series SHA-256: `1720dd674bc69f90f0a3003645076c7a0d62954d436e34f6fa512e52b6c4b06f`. No DT change: M10 DTBs are byte-identical to M9 (same SHA-256).

Script changes: `scripts/kernel-dtb-m10.sh` (copy of the M9 script; compares against the M9 variant DTBs and requires zero DT difference via the new `--previous-unchanged` flag of `scripts/kernel-m8-check.py`), `scripts/kernel-dtb-variants.sh` dispatch for revision 7, `scripts/kernel-check` milestone `m10`, `scripts/kernel-m8-rpm-check.py` milestone `m10` (adds the `qcom_glink` module with its `sp11-glink:` strings). New variant sources `kernel/dtb-variants/x1p64100-microsoft-denali-m10{,-notouch}.dts`.

Disk guard: the first launch was refused (headroom 53 GiB < 60 GiB, WSL C: free 18 GiB). Freed 23 GiB by deleting the finished M9 rpmbuild scratch `out/build/kernel/rpmbuild/BUILD` (M9 RPMs, record and checks stay published); headroom then 78 GiB. No threshold override. Nothing archived was deleted.

### M10 release artifacts

`scripts/kernel-build.sh -j 6` rpmbuild: rc 0, UTC `2026-10-30T07:34:57+00:00` to `2026-10-30T08:26:22+00:00`, **3085 s (51 min 25 s)**. Step 6 (archive sp11.6 RPMs to `out/rpms/archive/7.3.0-65.sp11.6/`, collect, `scripts/kernel-check`) ran inside the script: **PASS**, record `built_utc` 2026-10-30T08:29:05Z.

- BTF: `vmlinux` `.BTF` size `0x76c5c4`; **5934/5934** modules have BTF, zero missing. All 73 fragment symbols hold. `CHECK_DTBS=y` rc 0; `dt-validate` zero diagnostics.
- Packaged LCD DTB SHA-256 `784de3eb644bc6a169cbe0c6da51cef0f984984493a44e6fbfd00b18cd792709` (unchanged from M9). S1, GPU off, Wi-Fi/USB-C/touch wiring and the 2-4 GiB CMA window pass.
- `qcom_glink.ko.xz` (RPM `kernel-modules-core`, module SHA-256 `2d6a9811e7b079ac10a523131006e910eb89f2ada3016fb14c96a0a30a28bf38`) contains `sp11-glink: tx VERSION`, `tx OPEN` and `tx OPEN_ACK`. `qcom_glink_native` is part of this module (`CONFIG_RPMSG_QCOM_GLINK=m`), not vmlinux. `ath12k` (`0bd74f4b52c2e6aa24cc71004eb938b3e2d5ab40870045b967b5a82f7f177afb`), `ps883x` (`ca3ab1db966362c9ff57d54971afb1ba85d70c250400932acc79502696fd12dc`), `pmic_glink_altmode` (`1e6c9f4a7aa916945701f68ec326c87e1fa2ff5a01ea5a2aa5df4b7086931d0c`) and the touch modules keep their M9 effects.
- Resource accounting: peak cgroup 9674182656 bytes; peak anonymous 3336982528 bytes. ccache hit rate 99.65% (2239 direct + 24287 preprocessed hits, 93 misses).
- Config SHA-256: fragment `4a34894d4e50150bede28a45c937c2a63fd9fa96724f2291c022a2a8d857ee98`; shipped `e25b1f099a471321d37e84816d773785d5cd075046ac6d66a317f4fdfa549d23`.
- Release record: `out/rpms/kernel-7.3.0-65.sp11.7.fc44.aarch64.json`, SHA-256 `34d945f5c749e739d2bc141a08ff8fa0945a79a9331b13e919fe88764313cc27`.

| RPM (revision 7, aarch64) | SHA-256 |
|:--|:--|
| `kernel-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `d2b679f4c471361658f2205d3bb5d23f63037eb84ef46441550f326a6856079d` |
| `kernel-core-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `59e5ecd1d8cbc085f2fee5341b6f462bd313dbf01da8df541a476eb0319efb5f` |
| `kernel-debuginfo-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `bff0c4e795549d0b6a7d405aaf87b65156a5d2c91b2872f4baa45b5a351f0960` |
| `kernel-debuginfo-common-aarch64-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `c86096c6ccc72b782bbd64e758eab0f485b74bb8cfb862522dc1a45aaa200c95` |
| `kernel-devel-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `6bd54d39f81e8edbe392cd42a60c73482c63bf9db4c5b7c4d0addf3f2994acff` |
| `kernel-devel-matched-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `78b1c31b7c7463d09b232f69c402aa309836f9331f8cb82b6c2b5a9582a6a8b9` |
| `kernel-kmap-internal-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `f40109f36643fa8904dd6fe394fa8a7d4e82b5117a199d34dbe047513ea104c0` |
| `kernel-modules-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `43d134650d95926fd90bbb007e58170bc6092b0b7e1f053a68c33478906ae862` |
| `kernel-modules-core-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `e2c41e52ba85ed1b8e0c986f6d3ee346f3b72a7fa8c141c122a45095747131bc` |
| `kernel-modules-extra-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `8b0b79fbfaeff046e9a58b7ddd7c8f38410f126e0cbf58c02e189c3b0da53fc3` |
| `kernel-modules-extra-matched-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `dc2c8fb0ac2300533bbd1496e90c06ca88c51583a4663ff9b589c2267f1923de` |
| `kernel-modules-internal-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `8e232938f25ab52da7867564b6eb3e740a56c870552d5fff209cdbccedb41713` |
| `kernel-uki-dtbloader-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `2b33b418b937d665b4da5464ada86d7c69f77f77750870e6de6c9d12ea35fe29` |
| `kernel-uki-virt-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `c10ca4367721b4ed20055fa10c36c38efd78ee821fe8af2bac6424aadfdf2b34` |
| `kernel-uki-virt-addons-7.3.0-65.sp11.7.fc44.aarch64.rpm` | `b2e0684e51c314be6a4a6904888168c4412310b847dff40e011d6a651d534413` |

### M10 DTB variants

`scripts/kernel-dtb-variants.sh` (dispatching to `scripts/kernel-dtb-m10.sh`) ran after the release check; output `out/dtb-variants/7.3.0-65.sp11.7.fc44.aarch64/qcom/`, checks in `out/build/dtb-m10-checks/`. Both variants pass `CHECK_DTBS=y`, `dt-validate`, S1, GPU-off, wiring, parity and zero-difference-from-M9 checks.

| DTB | Build time | SHA-256 |
|:--|--:|:--|
| `x1p64100-microsoft-denali-m10.dtb` | 45 s | `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` |
| `x1p64100-microsoft-denali-m10-notouch.dtb` | 12 s | `5704f68668538f6dd3e6fc37f67e8e9830f771124c57475c0ebca81d8c750519` |

JSON record SHA-256: `x1p64100-microsoft-denali-m10.json` `3b22b47bfd05cde7923e992707b90a1caac627bf19e0d072d9910138d515079d`; `x1p64100-microsoft-denali-m10-notouch.json` `318516c0c7598068f92d37d4f4bdb7acb1f151f4f94d0f16263007f40fb44e5b`. No device boot was performed.

## M11 series revision 8 (2026-10-30)

The clean worker checkout already matched `main` at `d09469e`; no rebase or git write was needed. Revision 8 retains the 29 M10 patches and appends the following five patches, in this order. Series SHA-256: `f4360a491d178d56c26b1f3d45df388071c461037d4df870b914957b30136cc5`.

| Position | Patch | Integration reason |
|--:|:--|:--|
| 30 | dsp-subsystems 0002 | R-K3: read-only FIFO head/tail logging on OPEN_ACK timeout distinguishes an unread TX FIFO from an unacknowledged request. Temporary diagnostic; remove after evidence together with R-K1 |
| 31 | soc-boot 0001 | Carry the existing D20 ten-CPU/no-system-SS3 parity into the packaged LCD DTB, retaining cluster CL4/CL5 |
| 32 | audio-speakers 0001 | Reset the PA gain field to mixer value 6 (0 dB), register `0x34b1 = 0x32`, with GAIN_EN clear; no amplifier enable |
| 33 | audio-speakers 0002 | Apply the existing digital-volume ceiling 81 (-3 dB) to the four WSA MIX controls; a cap does not replace protection |
| 34 | audio-speakers 0003 | Add include-only audio fragments. Neither is included by the packaged board; only the microphone fragment is selected by an M11 variant |

All 34 patches apply sequentially to the pinned v7.3 export with `patch --batch --fuzz=0 -p1`; all five new patches apply without offsets. Retained patches have only their previously recorded line offsets. Log: `out/build/dtb-m11-checks/variant-series-apply.log`. No component patch was edited.

The historical parity DTS remains unchanged for old series. The M11 builder replaces only its staging copy with the documented board-include shim before `kernel-dev.sh variant` copies sibling DTS files. Both M11 default and the new packaged DT therefore inherit the parity patch exactly once. The microphone variant is an exact copy of the audio owner's requested DTS and retains its M10 include through that same staging shim. No `m11-audio-spk` source is staged, built or published.

`scripts/kernel-dtb-safety.py` permits an enabled x1e80100 card only when it contains no WSA link and `swr0` is effectively disabled; every watched amplifier must still be effectively disabled. The parser computes ancestor status after reading the complete tree, including status properties placed after children. Regression tests cover the disabled default, accepted microphone card, rejected WSA links (including disabled/renamed links), enabled speaker bus/amplifier, disabled ancestor, missing bus and empty tree. The wiring checker keeps explicit `/sound` and `swr0` disablement for packaged/default/fallback DTBs, and additionally requires microphone-only routing for `m11-audio`. Packaged-parity mode requires ten CPUs and the existing CPU/map/PSCI/SS3 exclusions while preserving the old revisions' twelve-CPU packaged expectation.

DT preflight (`scripts/kernel-dtb-m11.sh --preflight`) passed before the RPM build: all three variants pass `CHECK_DTBS=y`, explicit `dt-validate` with zero diagnostics, S1, GPU isolation, 2–4 GiB CMA and touch/Wi-Fi/USB-C wiring. The reconstructed packaged board and M11 default equal M10 default byte for byte; the no-touch variant equals M10 no-touch byte for byte. Its only changed property is touchscreen status. Preflight publishes no DTBs or release records.

Strict full-series checkpatch (`--strict --no-signoff`): **0 errors, 7 warnings, 11 checks**, with no tool errors. Six warnings and eleven checks are the unchanged spi-hid v7 baseline covered by the touch owner's lint triage; the new warning is the generic MAINTAINERS prompt for audio patch 0003's new include files. Logs: `out/build/dtb-m11-checks/checkpatch.{log,json}`. Fedora `python3-ply` and `python3-GitPython` were added to container dependencies for the SPDX helper. During lint only, a temporary read-only reference to the pinned source's git metadata supplied its LICENSES index to the disposable export; the reference was removed and no git command wrote anything. Lint disposition and independent component cross-checks remain owner/orchestrator gates.

Disk: the release guard initially refused at 29 GiB. After inspecting each candidate, verifying all 15 M10 published RPM hashes and preserving M10 logs/stats/checks in `out/build/kernel/history/m10/`, removed only the finished M10 `rpmbuild/BUILD` scratch and archived RPM sets `7.3.0-65.sp11` and `7.3.0-65.sp11.5`. Their JSON records were retained under `history/retired-archive-records/`; sp11.6 stayed intact. Headroom was then 58 GiB, still below 60 GiB. Windows free space subsequently increased; the release guard passed at 74 GiB. No threshold override or unrelated cleanup was used.

### M11 release artifacts

`scripts/kernel-build.sh -j 6` and automatic `scripts/kernel-check`: **PASS**. RPM build UTC `2026-10-30T11:03:20+00:00` to `2026-10-30T11:58:09+00:00`, **3289 s**. Step 6 archived revision 7 into `out/rpms/archive/7.3.0-65.sp11.7/`, copied all 15 revision-8 RPMs into `out/rpms/` and checked them. The existing sp11.6 archive is preserved; all 15 of its RPM hashes were verified against its record. A second `scripts/kernel-build.sh --check-only`, under `flock out/.kernel-build.lock`, also **PASS** in **45.493 s** (monotonic). Published RPM hashes match the final release record.

- BTF: `vmlinux` has `.BTF` (size `0x76c5c4`); **5934/5934** extracted modules have valid BTF, zero missing or bad magic. All **73** fragment symbols hold, including both BTF settings. `CHECK_DTBS=y` rc 0, zero warning lines; explicit packaged-DTB `dt-validate` has zero diagnostics.
- Packaged LCD DTB SHA-256 `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a`. It equals the validated M11/M10 default parity DTB byte for byte: ten CPUs, no system SS3, CL4/CL5 retained, touch on, GPU off, `/sound` and `swr0` off. Wi-Fi/USB-C/QSPI/touch wiring and the reusable 128 MiB, 2–4 GiB CMA allocation window pass.
- All eight touch modules are in the checked payload, with SPI/OF aliases, preloaded-QSPI guard and GPI TRE path; RFC 0014 is absent. The Surface ath12k rfkill table and match call, PS8830/PMIC-GLINK diagnostics and retained GLINK logs pass. `qcom_glink` additionally contains the exact new `sp11-glink: FIFO tx head=%u tail=%u rx head=%u tail=%u` format string.
- Both release audio objects and RPM-extracted modules pass. `wsa884x_defaults` sets register `0x34b1` to `0x32` (PA mixer value 6, 0 dB, GAIN_EN off). The machine object has eight digital ceilings at 81, including all four MIX controls. Object/module/ELF hashes and owning RPMs are in `m11.new_modules` of the record. These checks do not establish speaker protection or authorize output.
- Nonfatal diagnostics match preserved M10 evidence: Myricom uninitialized-buffer warning, three retained R-K1 GLINK format warnings (owner follow-up above), optional GDB index failures from BFD without zstd, Rust pseudo-path cpio notices and Fedora's absolute build symlink. GDB indexes are not claimed; the separate BTF audit passes.
- Resource accounting: peak cgroup **8864464896 bytes**, sampled peak anonymous **3438952448 bytes**. Cache: 2239 direct + 24283 preprocessed hits, 97 misses; **99.64%** hit rate. Minimum release headroom **28 GiB**.
- Config SHA-256: fragment `4a34894d4e50150bede28a45c937c2a63fd9fa96724f2291c022a2a8d857ee98`; shipped `82746c52c4d239c832078fa6739edbf03c1c414e41a81a32137b99e5c4c32b5f`.
- Release record: [`out/rpms/kernel-7.3.0-65.sp11.8.fc44.aarch64.json`](../out/rpms/kernel-7.3.0-65.sp11.8.fc44.aarch64.json), SHA-256 `d3ff02d032fe904a0b6fd4d2870a1914f41f78f3c62f78219ed20ce2997914be`. Logs: `out/build/kernel/m11-driver.log`, `m11-check-only.log` and `rpmbuild.log`.

| RPM (revision 8, aarch64) | SHA-256 |
|:--|:--|
| `kernel-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `8077131b1d2f4343bbf87a5e0a4c8b273bb73248de2d44ffb2c3a959247d27f5` |
| `kernel-core-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `1254627af590b3124b82f335f20646bacbc05b6d14576688f9fca8b315e79b80` |
| `kernel-debuginfo-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `e0e6d6317039f89a0753fcbd06437ffcd00d7ae38bcbd6c4d44cabd936561d85` |
| `kernel-debuginfo-common-aarch64-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `1a2ec89be169c59deb2547491526cb293ec1388b3dfc4cac1693dce343f28722` |
| `kernel-devel-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `482bcdc0483277bce126e57741558b71a8029dd7074fc6a3a6bda5ea38e0290e` |
| `kernel-devel-matched-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `f53b468c27899956d21c4a0600c9d28525748aa33ec1ff81d9904638d9d5e4e4` |
| `kernel-kmap-internal-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `84c2b46aab738584ac91469ec870ae5bba794f3e495bc5cdff7d08c3be628230` |
| `kernel-modules-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `4109d622b1cb70dc13e32f4c3f6ef66286f6b7efbd5e2a2c98953a56868a7017` |
| `kernel-modules-core-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `f6861c2358586515c806266a2306e77a7ae7ce3164f9f33f6c06275020fe3a4a` |
| `kernel-modules-extra-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `7c22921ce86fd5260253bdf7f1e1a813f2c43b63b823020533cdbd64e48c3150` |
| `kernel-modules-extra-matched-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `05a04f6efc6b97af61278ebf76cf38119f1ac9c854310edede51d3d966815fd1` |
| `kernel-modules-internal-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `06b792f6fa4fabf91c78577cd4120b16fb3250ad8a5ae4552bad186a12673b53` |
| `kernel-uki-dtbloader-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `4d9be384e604c91195c57562d19bcc304819c4283c12fa94b8223e2be605cfc5` |
| `kernel-uki-virt-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `e9762de779d90d30aab5c3a5f3c86cd13a5194d4b8794d022a07d9be37489d70` |
| `kernel-uki-virt-addons-7.3.0-65.sp11.8.fc44.aarch64.rpm` | `48154642ec19cd1ae7b96c24b3e2beb2b87275604255f4e82aa71afdfeadb647` |


### M11 DTB variants

`scripts/kernel-dtb-variants.sh` dispatches revision 8 to `scripts/kernel-dtb-m11.sh`; builds use `scripts/kernel-dev.sh --check` and the shared lock. Final run UTC `2026-10-30T12:02:13.921756+00:00` to `2026-10-30T12:05:17.154492+00:00`, **163.711 s** (monotonic) including source export, staging, configuration, compilation and checks. Output: `out/dtb-variants/7.3.0-65.sp11.8.fc44.aarch64/qcom/`; logs/source diffs: `out/build/dtb-m11-checks/`.

All three DTBs pass `CHECK_DTBS=y`, explicit `dt-validate` with zero diagnostics, S1 with the narrow microphone exception, GPU-off, parity, CMA and touch/Wi-Fi/USB-C wiring. Source recompilation matches each DTB byte for byte; the reconstructed base and M11 default match the packaged DTB. M11 default/no-touch also match M10 byte for byte, and the fallback changes only touchscreen status. The microphone source diff changes only the card status, DMIC routing and removal of the WSA playback link; phandle renumbering explains the additional numeric DTB differences. No speaker variant was built.

| DTB | Build time | SHA-256 |
|:--|--:|:--|
| `x1p64100-microsoft-denali-m11.dtb` | 46 s | `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` |
| `x1p64100-microsoft-denali-m11-notouch.dtb` | 12 s | `5704f68668538f6dd3e6fc37f67e8e9830f771124c57475c0ebca81d8c750519` |
| `x1p64100-microsoft-denali-m11-audio.dtb` | 11 s | `4515442e5531544c60bb416b4c3206bdb152cbf4f1ecf0248a571a446879b6ca` |

JSON record SHA-256:

- `x1p64100-microsoft-denali-m11.json`: `44093906fd750c37c2a595908ac835967b3bae969d6f8bddcf8f155d82c22df0`.
- `x1p64100-microsoft-denali-m11-notouch.json`: `c5f043902b7ecc864f0c0da3b8ad36304a3413fcceabc9ff09b35ec7e597ad28`.
- `x1p64100-microsoft-denali-m11-audio.json`: `1b44ac199aca2198b1f116bc17204ca0dd1ddd68893db9edcb90fb11de25cbff`.

Nine Python regression cases and nine compiled-DTB safety/parity cases pass. The compiled cases accept the disabled default and microphones and reject full-card/WSA-link, enabled-bus and enabled-amplifier fixtures; old packaged parity is rejected while old mode remains supported. Evidence: `out/build/dtb-m11-checks/negative/results.json`. No device boot was performed.

Final hand-back checks: `scripts/index.py --check` reports **21 components, 0 errors**; Python/shell syntax, regression and whitespace checks pass. The published sp11.8 RPMs/DTBs/records and the sp11.6/sp11.7 RPM archives match their recorded hashes. Both the shared build lock and M11 source lock are free; no task build, container, sampler or watchdog remains. The temporary git-metadata reference is absent. Kernel is a service worker with no `component.toml`; hardware status files remain owner-managed. All worker changes remain uncommitted for orchestrator review under D24. Image L0/L1, component cross-checks, lint disposition and diagnostic retirement remain the Requests above.


## M12 series revision 9 (2026-10-30)

Revision 9 keeps the 34 M11 patches and adds three, for 37 in total. Series SHA-256: `e3a9dbac6f7efbb10e7b3105e13787e60726f92d4048dab010ac7d967bfdc49e`. All 37 apply sequentially to the pinned v7.3 export with `patch --batch --fuzz=0 -p1`; the three new patches apply with zero offset and zero fuzz. `hardware/ec-sam/patches/hold/0006` stays out (held).

| Position | Patch | Integration reason |
|--:|:--|:--|
| after touch 0020 | touch-pen 0021 | Verified fix F-09: `spi-hid-of` still cuts the supply when asserting the reset line fails. Touches only `spi-hid-of.c`, after the v7 series that creates it |
| 36 | audio-speakers 0004 | `wsa884x`: write the cached PA gain (0 dB) when the slave attaches, so the amplifier never keeps its +34.5 dB power-on gain |
| 37 | audio-speakers 0005 | `lpass-wsa-macro`: keep the EAR/SPKR PA gain below the machine-driver limit. Both are required in any kernel that boots a speaker-enabled DTB; speakers stay off in every DTB (S1) |

The amended dsp-subsystems 0001 (GLINK format fixes) is picked up through the series; this changes the series hash. No DT change: the three M12 DTBs equal their M11 counterparts byte for byte.

Script changes: `scripts/kernel-dtb-m12.sh` (M11 builder; compares every variant against the sp11.8 M11 DTB byte for byte), dispatch in `scripts/kernel-dtb-variants.sh`, milestone `m12` in `scripts/kernel-check`, `scripts/kernel-m8-rpm-check.py` (adds the `snd-soc-lpass-wsa-macro` module and object, and checks `wsa884x` for the explicit `0x34b1` write) and variant names in `scripts/kernel-m8-check.py`. Sources: `kernel/dtb-variants/x1p64100-microsoft-denali-m12{,-notouch,-audio}.dts`.

Disk guard: the first launch was refused (headroom 52 GiB < 60 GiB, C: free 15 GiB). Preserved the M11 logs/stats in `out/build/kernel/history/m11/`, then deleted only the finished M11 scratch `out/build/kernel/rpmbuild/BUILD/kernel-7.3.0-build` (23 GiB). Nothing archived was deleted; no threshold override. Step 6 archived revision 8 into `out/rpms/archive/7.3.0-65.sp11.8/` (sp11.6 and sp11.7 sets remain).

### M12 release artifacts

`scripts/kernel-build.sh -j 6`: rc 0, UTC `2026-10-30T15:26:59+00:00` to `2026-10-30T16:16:52+00:00`, **2993 s (49 min 53 s)**. `scripts/kernel-check` ran inside the script: **PASS**.

- BTF: `vmlinux` `.BTF` size `0x76c5c4`; **5934/5934** modules have BTF, none missing, no bad magic. All 73 fragment symbols hold. `CHECK_DTBS=y` rc 0, 0 warning lines; packaged DTB `dt-validate` clean.
- Packaged LCD DTB SHA-256 `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` (unchanged). S1, GPU off, wiring and CMA window pass.
- Touch modules, glink strings (including the FIFO format), `ath12k`, `ps883x` and `pmic_glink_altmode` pass. Release objects and modules for `wsa884x` (with 0004), `x1e80100` and `lpass-wsa-macro` (with 0005) are built and recorded under `m12.new_modules`. These checks do not establish speaker protection.
- Peak cgroup 9689481216 bytes; peak anonymous 3336876032 bytes. ccache 99.64% (2239 direct + 24284 preprocessed hits, 96 misses).
- Release record `out/rpms/kernel-7.3.0-65.sp11.9.fc44.aarch64.json`, SHA-256 `ea7c2a4aedf96c993f7897e455e290e9bc049d2c95ff0206dd4af39613676bd9`. Logs: `out/build/kernel/m12-driver.log`, `rpmbuild.log`.

| RPM (revision 9, aarch64) | SHA-256 |
|:--|:--|
| `kernel-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `1024f6bc0bb31f60be4d638b0f5cc1223c734de710e47302b08201bcdad16cd3` |
| `kernel-core-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `796e5de470d70bfb4338998d638e15ca4610c56907353865e6d3793925c775ca` |
| `kernel-debuginfo-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `7a0847c3db4cde1b5ee3d2b8696e30ee4e0f34d7d5d99309333e1a32266eb5c5` |
| `kernel-debuginfo-common-aarch64-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `d1a87cbbbd6a43008a18ce50c3048344509b41d083aa7d2c751d13659582c78b` |
| `kernel-devel-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `f680a4c755be5fe86d910aa2140b1c4a8e13c97c2fafa7e32d7c1e0b33bb71b9` |
| `kernel-devel-matched-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `f3c887572f63b5c330820b4122bd907a3976061bbeb61d134c41483a61203af3` |
| `kernel-kmap-internal-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `0375a96d504d2617d197736c7ff30b24f6c0c2a67c334b46d943bf51b68cdce5` |
| `kernel-modules-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `2ab2fd150fe75b56a8f7af4e7edb0bad7444d99e07a66ff30d92928cf21c13c8` |
| `kernel-modules-core-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `1ec5e9359ec356e926e3affda70bc226c9fe7267e70ee2fc8c4eb47154c1d5b8` |
| `kernel-modules-extra-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `84d734e5319d6ab3190ef9b28da8460aafb7f5f4fd2925bcc96e9f9b0a72ea6f` |
| `kernel-modules-extra-matched-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `3e8e8f288fb74826a4869de1d7a590a9c6158051fdc454b00a999ea60a44e948` |
| `kernel-modules-internal-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `d8d93927181cdfbea1ef63ce246a66ae21440efa840e458245181e8e6de6808b` |
| `kernel-uki-dtbloader-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `5156d650f3b10920e0920dd4b5b8a03a6bfc227f52cdf384d9d91f8f886952dc` |
| `kernel-uki-virt-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `1f16d3a8dba272a6f555000aa758131231bb5367ff1b31a5419737370d8436c0` |
| `kernel-uki-virt-addons-7.3.0-65.sp11.9.fc44.aarch64.rpm` | `6f204724dddee56383c004e2fddb1662c519666ac7297b56fb677aacbca3582b` |

### M12 DTB variants

`scripts/kernel-dtb-variants.sh` (dispatching to `scripts/kernel-dtb-m12.sh`); output `out/dtb-variants/7.3.0-65.sp11.9.fc44.aarch64/qcom/`, checks in `out/build/dtb-m12-checks/`, log `out/build/kernel/m12-variants.log`. All three pass `CHECK_DTBS=y`, `dt-validate`, S1 (microphone-only exception for audio), GPU-off, wiring and the byte-identical-to-M11 check.

| DTB | Build time | SHA-256 |
|:--|--:|:--|
| `x1p64100-microsoft-denali-m12.dtb` | 43 s | `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` |
| `x1p64100-microsoft-denali-m12-notouch.dtb` | 12 s | `5704f68668538f6dd3e6fc37f67e8e9830f771124c57475c0ebca81d8c750519` |
| `x1p64100-microsoft-denali-m12-audio.dtb` | 11 s | `4515442e5531544c60bb416b4c3206bdb152cbf4f1ecf0248a571a446879b6ca` |

JSON record SHA-256: `m12.json` `cbc247ce36d962ac7f96d10f7e8d760983b981370c1a406085c57cd97ac8c183`; `m12-notouch.json` `272086024a0c2541fec900c3674fd6b589e0b2f789647989bb7fd6d3c66316f3`; `m12-audio.json` `a8529a7ffb8a3ffb5444c979428d575f9ed2aad4944f16800a451138b4ee5280`. No device boot. No speaker variant built.


## Log

- 2026-10-29: built M8 revision 5 (25 patches; RFC 0014 retired; spi-hid/QSPI touch and packaged GPU isolation). Release 3313 s; kernel-check PASS with BTF in vmlinux and all 5934 modules, 73 config symbols, packaged schema/S1/GPU/wiring and eight RPM module payload checks. M8/M8-notouch DTBs and JSON pass (63/14 s; complete run 214.464 s). Final index/syntax/whitespace checks pass; build/source locks are free and no task process remains. Recorded hashes/times and explicit image/owner requests; no device test. Changes remain uncommitted for the orchestrator (D24).

- 2026-10-29: built and statically validated M7 revision 4 (nine patches, ATH12K_DEBUG, packaged S1): RPM build 3279 s; BTF in vmlinux and all 5930 modules; config, schema, S1, wiring and RFC message pass. M7/M7-touchdiag DTBs and JSON records pass (43/12 s; complete run 164.110 s). Recorded times/hashes and owner requests; no device test or task process left running. Work remains uncommitted under D24; orchestrator rebase/review/commit and image L0/L1 are next.
- 2026-10-28: built and statically validated M6/M6GPU DT-only artifacts and JSON records; no RPM, series, revision or config change. Prepared the unbuilt revision 4 plan; component integration requests remain in Requests. Kernel is a service worker with no `component.toml`; hardware component status files are owned by their workers. Changes left uncommitted for the orchestrator (D24).
- 2026-10-30: built M10 revision 7 (29 patches; GLINK OPEN_ACK diagnostic). Release 3085 s; kernel-check PASS; M10/M10-notouch DTBs pass and equal M9. Freed 23 GiB of finished M9 rpmbuild scratch for the disk guard. No device test, no commit.

- 2026-10-30: built M11 revision 8 (34 patches; FIFO diagnostic, packaged parity, audio safety/fragments). Release 3289 s; automatic and repeated kernel-check PASS, BTF in vmlinux/all 5934 modules; all three DTB variants and JSON pass. Recorded times/hashes, regression evidence and owner requests. No device test or git write; changes remain uncommitted for the orchestrator (D24).
- 2026-10-30: built M12 revision 9 (37 patches; touch F-09, audio 0004/0005, amended GLINK 0001). Release 2993 s; kernel-check PASS, BTF in vmlinux/all 5934 modules; m12, m12-notouch, m12-audio DTBs equal M11. Freed 23 GiB of finished M11 scratch. No device test, no commit.
