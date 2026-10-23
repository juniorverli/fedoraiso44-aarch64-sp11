# gpu

## 1. Summary

The Adreno X1-85 GPU (chip ID `0x43050c01`, "C512v2") of the X1P64100. Linux 7.3 supports it natively in `drm/msm`, and the Denali DT already enables it with the Surface zap shader path. The work is firmware, speed bin and userspace. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C36&SUBSYS_IDP08380&REV_008A`, "Qualcomm(R) Adreno(TM) X1-85 GPU" | Verified | `pnp-present.json` |
| DT compatible | `qcom,adreno-43050c01`, `qcom,adreno` | Verified | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:3991` |
| Driver entry | `ADRENO_CHIP_IDS(0x43050c01)`, family `ADRENO_7XX_GEN2`, SQE `gen70500_sqe.fw`, GMU `gen70500_gmu.bin`, GMEM 3 MB, IFPC, preemption | Verified | `sources/linux/drivers/gpu/drm/msm/adreno/a6xx_catalog.c:1573` |
| Zap shader | `qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn` | Verified (DT) | `x1-microsoft-denali.dtsi` (`&gpu_zap_shader`) |
| Zap shader source | `DriverStore/qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkmsuc8380.mbn`, SHA-256 `950f17eb439326548cba20603b30cda653d612d1564feb397ddbd92987f0e8ac` | Verified | `MANIFEST.sha256` |
| Speed bin / max frequency of this SKU | TBD | TBD | §6 Q1 |

## 3. Windows

| Package | Role |
|:--|:--|
| `qcdx8380` | `qcdxkm8380.sys` (kernel driver), `qcdxkmbase8380*.bin` (per-SKU configuration), D3D/Vulkan/OpenCL user drivers, zap shader `qcdxkmsuc8380.mbn` and `qcdxkmsucpurwa.mbn` (the second is for the Purwa SoC, not this one) |
| `surface_dxext_8380` | Surface board configuration for the driver |

The `qcdxkmbase8380_*.bin` variants (`_68`, `_110`, `_150`, `_pa*`) are selected per SoC/SKU; which one is loaded for REV `0x8A` tells us the frequency plan (Q1).

## 4. Linux 7.3

- `drm/msm/adreno/a6xx_gpu.c`, `a6xx_gmu.c`, `a6xx_catalog.c:1573` (the entry above).
- `drivers/clk/qcom/gpucc-x1e80100.c`; GPU OPP table in `hamoa.dtsi`.
- `x1-microsoft-denali.dtsi`: `&gpu { status = "okay"; }`, `&gpu_zap_shader`.
- Userspace: Mesa freedreno (OpenGL ES/GL) and Turnip (Vulkan) for a7xx.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Zap shader not in Fedora | Ship from the DriverStore (firmware worker, `firmware/manifest.toml`) |
| `gen70500_sqe.fw`, `gen70500_gmu.bin` | Confirm they are in Fedora 44 `linux-firmware`; otherwise pin an upstream `linux-firmware` release |
| Speed bin of X1P64100 | Read the fuse on the device; compare with the speed bins and OPPs in `a6xx_catalog.c` / `hamoa.dtsi`; patch only if the SKU would run above its rating |
| Mesa version | Confirm Fedora 44 Mesa supports `0x43050c01` in Turnip and freedreno; record NEVRA |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | What is the maximum GPU frequency on the X1P64100, and how does Linux pick it (speed-bin fuse, OPP `opp-supported-hw`)? | TBD | `a6xx_catalog.c` speed bins for this chip, `hamoa.dtsi` OPP table, `qcdxkmbase8380*.bin` selection in `qcdxkm8380.sys` (REA), fuse value in `dmesg` on the device |
| Q2 | Does the zap shader load with the kernel's PAS ID and memory region? | TBD | `dmesg` on M2 |
| Q3 | Do GPU limits from Windows (`QCOM0CF7`) need a Linux equivalent for thermals? | TBD | Hand to `power-thermal` |
| Q4 | Is IFPC stable on this firmware? | TBD | 30 min load test; `dmesg` for GMU errors |

## 7. Acceptance

On the device, with logs in `evidence/`:

1. `dmesg` shows the GPU bound, zap shader loaded, no GMU or hang errors.
2. `glxinfo -B` reports `FD` / freedreno with hardware rendering; `vulkaninfo --summary` lists Turnip for Adreno X1-85.
3. GNOME Shell renders with the GPU (not `llvmpipe`).
4. `vkcube` and `glmark2-es2-wayland` run 30 minutes without hang or `GPU fault`.
5. `/sys/class/devfreq/*gpu*/max_freq` matches the SKU's rating (Q1).

## 8. Requests

- firmware: entries for the zap shader and `gen70500_*` (already drafted in `firmware/manifest.toml`).
- image: include `mesa-dri-drivers`, `mesa-vulkan-drivers`, `vulkan-tools`, `glx-utils`, `glmark2`; log collector dumps `/sys/kernel/debug/dri/*/gpu` state and `devfreq`.

## 9. Log

- 2026-10-23: dossier created from the static survey.
