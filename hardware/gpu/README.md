# gpu

## 1. Summary

The X1P64100's Adreno X1-85 (chip ID `0x43050c01`, "C512v2") has native Linux 7.3 support, and the captured Windows configuration selects a 1.25 GHz graphics ceiling. Status: `designed`; static speed-bin evidence needs no behavioral kernel patch, while the M15 debug boot now has an opt-in phase-trace patch for a controlled diagnostic build.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C36&SUBSYS_IDP08380&REV_008A`, "Qualcomm(R) Adreno(TM) X1-85 GPU" | Verified | PnP path, SHA-256 and entry in [speed-bin evidence](evidence/2026-10-24-speedbin.md) |
| DT compatible | `qcom,adreno-43050c01`, `qcom,adreno` | Verified | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:3991` |
| Driver entry | `ADRENO_CHIP_IDS(0x43050c01)`, family `ADRENO_7XX_GEN2`, SQE `gen70500_sqe.fw`, GMU `gen70500_gmu.bin`, GMEM 3 MB, IFPC, preemption | Verified | `sources/linux/drivers/gpu/drm/msm/adreno/a6xx_catalog.c:1573` |
| Zap shader | `qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn` | Verified (DT) | `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:723` |
| Zap shader source | `DriverStore/qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkmsuc8380.mbn`, SHA-256 `950f17eb439326548cba20603b30cda653d612d1564feb397ddbd92987f0e8ac` | Verified | `MANIFEST.sha256` |
| Windows GPU ceiling | 1250000000 Hz (1.25 GHz) | Inference from Verified configuration bytes and active base-file selection | [speed-bin evidence](evidence/2026-10-24-speedbin.md), BASE offset `0x17a45`; vendor specification agrees |
| Expected Linux fuse / logical bin / OPP mask | 7 / 2 / `0x04` | Inference; physical fuse TBD | `sources/linux/drivers/gpu/drm/msm/adreno/a6xx_catalog.c:1608`; `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:4041` |
| Zap container / PAS | Relocatable signed ELF32 container fits reserved memory; kernel uses PAS 13 | Inference (format compatibility); Verified (kernel PAS); runtime authentication TBD | [firmware evidence](evidence/2026-10-24-firmware-mesa.md) |

## 3. Windows

| Package | Role |
|:--|:--|
| `qcdx8380` | `qcdxkm8380.sys` (kernel driver), `qcdxkmbase8380*.bin` (per-SKU configuration), D3D/Vulkan/OpenCL user drivers, zap shader `qcdxkmsuc8380.mbn` and `qcdxkmsucpurwa.mbn` (the second is for the Purwa SoC, not this one) |
| `surface_dxext_8380` | Surface board configuration for the driver |

**Verified:** active driver version `31.0.148.0`, install section `QCDX_Inst_Base.NT`, matching ID REV `008A`, and `AcpiBaseFile = qcdxkmbase8380.bin` are recorded in `live-inventory/panel/gpu-class-key.txt` (SHA-256 and lines in [speed-bin evidence](evidence/2026-10-24-speedbin.md)). The INF independently maps this revision to the same unsuffixed file. REA function `0x140431488` corroborates the lookup/file-load path and the blob header checks; addresses, limitations and evidence IDs are in the evidence file. Its graphics core-clock table tops out at 1250000000; `_68`, `_110`, `_150` and `_pa*` are not this installation's selected base file. A bounded, hash-checking [data decoder](tools/read-clock-table.py) reproduces all eight tables without disassembly.

**Verified / Inference:** `QCOM0CF7` is a separate GPU thermal policy device bound by the available PEP INFs, rather than another GPU rendering function. See the [thermal policy evidence and hand-off](evidence/2026-10-24-thermal-policy-request.md); the active qcpep version and policy semantics remain TBD.

## 4. Linux 7.3

- **Verified:** chip, firmware, GMEM and quirks in `sources/linux/drivers/gpu/drm/msm/adreno/a6xx_catalog.c:1573`; fuse table at line 1608.
- **Verified:** NVMEM cell and OPP table in `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:3990`, `:4022`, `:8790`; filtering in `sources/linux/drivers/gpu/drm/msm/adreno/a6xx_gpu.c:2590` and `sources/linux/drivers/opp/of.c:500`. **Inference:** fuse 7 limits this table to 1.25 GHz; an unknown fuse falls back to a 1.5 GHz-capable mask. Missing-cell and failed-read cases differ; see the evidence.
- **Verified:** `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:719` enables GPU and line 723 supplies the Microsoft zap path. Clock provider: `sources/linux/drivers/clk/qcom/gpucc-x1e80100.c`.
- **Verified repository/source observations; Inference of static support:** Fedora 44 stable aarch64 currently offers Mesa `26.2.5-1.fc44`. Its common device table matches `0xffff43050c01` with wildcard fuse bits; both Gallium freedreno and Turnip use it. Fedora builds and packages both drivers. See [package queries, source hashes and line references](evidence/2026-10-24-firmware-mesa.md). Runtime operation remains untested.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Zap shader not in Fedora | Ship from the DriverStore (firmware worker, `firmware/manifest.toml`) |
| Firmware/image pin | Verified Fedora file lists: `qcom-firmware-0:20261019-1.fc44.noarch` supplies both `gen70500_*` as `.xz`; firmware/image owners must pin actual RPMs and verify initramfs plus XZ loader support |
| Physical fuse and safe initial GPU enablement | Read the fuse with msm blacklisted before accelerated boot, then verify 1.25 GHz ceiling; existing fuse-7 mapping suffices if observed. No kernel patch proposed |
| Independent cross-check | Orchestrator must reproduce the active config selection, clock table, fuse extraction and OPP arithmetic before using these safety values |
| Mesa/image pin | Verified available `mesa-{dri,vulkan}-drivers-0:26.2.5-1.fc44.aarch64`; sources/image owners pin the actual compose. No Mesa change indicated |
| M15 early DRM open and boot-stage failure | Stage-by-stage evidence is missing; use the default-off trace patch and fix the image firmware/hook ordering before a controlled retest |
| Thermal mitigation and device behavior | `power-thermal` establishes equivalent GPU cooling; device tests confirm PAS authentication, rendering and IFPC stability |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Will this unit's physical fuse select the established 1.25 GHz ceiling? | Inference: expected fuse 7; observed value TBD | Static selection/table answer is in [speed-bin evidence](evidence/2026-10-24-speedbin.md). Independent cross-check, pre-probe NVMEM read, then DRM chip/fuse and devfreq readout close the remaining gap; successful reads need not appear in dmesg |
| Q2 | Does the zap shader authenticate and run with PAS 13? | Inference: container/memory fit; runtime TBD | Header-only checks pass statically; [firmware evidence](evidence/2026-10-24-firmware-mesa.md). Device logs and hardware rendering still required |
| Q3 | Which Windows GPU thermal limits need an equivalent Linux binding? | Verified PEP/ACPI association; policy semantics TBD | [QCOM0CF7 hand-off](evidence/2026-10-24-thermal-policy-request.md) to `power-thermal` |
| Q4 | Is IFPC stable on this firmware? | TBD | 30 min load test; `dmesg` for GMU errors |

## 7. Acceptance

On the device, with logs in `evidence/`, following [test-plan.md](test-plan.md). First independently cross-check the safety values, read the fuse with msm blacklisted, and obtain the power-thermal load-test release:

1. `dmesg` shows the GPU bound, zap shader loaded, no GMU or hang errors.
2. `glxinfo -B` reports `FD` / freedreno with hardware rendering; `vulkaninfo --summary` lists Turnip for Adreno X1-85.
3. GNOME Shell renders with the GPU (not `llvmpipe`).
4. `vkcube` and `glmark2-es2-wayland` run 30 minutes without hang or `GPU fault`.
5. Identified GPU devfreq `available_frequencies` and `max_freq` never exceed 1250000000 Hz; DRM chip ID is `0x43050c01`, fuse is the expected 7 (Q1). Capture any lower thermal cap without overriding it.

## 8. Requests

- **orchestrator / cross-check:** independently reproduce REV 008A's selected base file, graphics clock table, fuse/OPP masks and pre-probe extraction before approving these safety values. Actual physical fuse remains TBD; no kernel patch has been written.
- **firmware:** mark `gen70500_*` package availability confirmed from `qcom-firmware-0:20261019-1.fc44.noarch` (source `linux-firmware-20261019-1.fc44.src.rpm`), pin the actual RPM, and retain the exact Microsoft zap mapping. See [query evidence](evidence/2026-10-24-firmware-mesa.md); no payload/signature or on-device verification is claimed.
- **sources / image:** pin Fedora repo/compose, the above firmware RPM and `mesa-{dri,vulkan}-drivers-0:26.2.5-1.fc44.aarch64`, plus matching Mesa source inputs cited in the evidence. Do not derive aarch64 updates from older release-specific Fedora Packages web pages.
- **kernel / image:** verify `CONFIG_NVMEM_SYSFS=y`, QFPROM and `CONFIG_FW_LOADER_COMPRESS_XZ=y` in the assembled config; include firmware in the initramfs when msm probes there. Provide the msm-blacklisted, multi-user diagnostic entry in the test plan for the first fuse read. For a controlled GPU boot only, opt into `CONFIG_DRM_MSM_GPU_BOOT_TRACE=m` from [patch 0001](patches/0001-drm-msm-add-opt-in-gpu-boot-phase-trace.patch); it is default-off and diagnostic only.
- **power-thermal:** confirm active qcpep binding for `QCOM0CF7`, decode `GpuLimits_R2` CGLC/OGLC policy, map GPU cooling, and give the condition for releasing sustained GPU load. [Evidence and exact INF hashes/lines](evidence/2026-10-24-thermal-policy-request.md).
- **image (M15 debug ordering):** the debug log records an early `msm_open()` firmware request at 5.197 s, before the GPU guard service starts at 29.462 s. `90-sp11.conf` currently omits `gen70500_*` based on the assumption that `msm_open()` happens after root is mounted. Stage and verify these files in initramfs, then test GDM/DRM open ordering with explicit markers immediately before and after the GPU hook plus a global deadline covering helper mount/sync/unmount. Do not expose working firmware to uncontrolled early opens: first isolate those opens and verify thermal safeguards, because an early successful load can proceed into GMU/zap before the diagnostic guard. See [M15 boot evidence](evidence/2026-11-01-m15-debug-step0.md).
- **image:** include `mesa-dri-drivers`, `mesa-vulkan-drivers`, `vulkan-tools`, `glx-utils`, `glmark2`; verify the named test binaries are present. Log collection needs the identified GPU's devfreq readings, DRM chip/fuse value, driver/firmware errors and GPU cooling state. Review/redact debug state before it enters git.

- **kernel (new, 2026-10-30):** build DTB variant `m13-gpu` from `kernel/dtb-variants/x1p64100-microsoft-denali-m13-gpu.dts` (written; M12 plus `&gpu` okay, speakers off) and add the script wiring listed in [two-step evidence](evidence/2026-10-30-two-step.md) section 2. Optional: marker patch or `CONFIG_DYNAMIC_DEBUG=y` (section 4). No speed-bin patch is needed (section 2).
- **image (new, 2026-10-30):** install `collector/gpu-two-step.sh` as `/usr/libexec/sp11-gpu-two-step`, `collector/sp11-gpu-two-step.service`, and the last menu entry in `collector/grub-entry.txt` (`SP11 debug, GPU diagnostic`, `sp11.gpu_diag=1`, multi-user target, never default). Collector must read the speed-bin as the aligned word at `0x118`.
- **orchestrator:** run the device test of [test-plan.md](test-plan.md) section 0 on the operator's go; the entry may reset the machine, so it is operator-initiated only.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: established REV 008A's active unsuffixed base file and 1.25 GHz clock table; mapped Linux fuse/OPPs and unsafe unknown-fuse fallback; confirmed Fedora firmware/Mesa availability, checked zap container and documented thermal hand-off plus staged device tests. Status designed; no kernel patch or git write operation.
- 2026-11-01: M15 debug capture confirms a DRM open reached firmware loading at 5.197 s, before the guard service, and stopped at `-ENOENT` before runtime PM/GMU; root cause of missing STEP1 remains unknown. Added default-off phase markers for a controlled follow-up; see [boot evidence](evidence/2026-11-01-m15-debug-step0.md) and [kernel patch 0001](patches/0001-drm-msm-add-opt-in-gpu-boot-phase-trace.patch).
- 2026-10-30: M5 GPU-on traced to DTB `m5gpu` (no `&gpu` override; patch 0002 later disabled it). Designed DTB `m13-gpu` and the reset-surviving two-step collector; found the GPU device's `power/control` is a no-op until the first render open, so step 1 powers the GMU device (CX GDSC) and step 2 is one `open()` (GMU boot and zap cannot be split from userspace). The M5 userspace speed-bin read failed on alignment, the kernel read worked (1.25 GHz ceiling, no patch). See [two-step evidence](evidence/2026-10-30-two-step.md).
