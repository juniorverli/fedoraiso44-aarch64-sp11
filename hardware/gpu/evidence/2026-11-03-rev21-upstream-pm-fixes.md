# Revision 21: upstream GPU PM and RPMH fixes

Date: 2026-11-03. Static source audit, upstream commits and a Windows REA cross-check. No device test yet.

## Defects present in the pinned v7.3 tree

| # | Source before the fix | Upstream fix | Why it matches the reset |
|:--|:--|:--|:--|
| 1 | `a6xx_pm_resume()` calls `dev_pm_opp_put(opp)` and then `dev_pm_opp_set_opp(&gpu->pdev->dev, opp)` (`sources/linux/drivers/gpu/drm/msm/adreno/a6xx_gpu.c:2181-2189`). | `8128ae7af6b4dc95e486c5c0a80839a069df578e` "drm/msm/a6xx: fix use-after-free of OPP in a6xx_pm_resume" (2026-09-29), <https://github.com/torvalds/linux/commit/8128ae7af6b4dc95e486c5c0a80839a069df578e> | The GPU autosuspends after 66 ms (`msm_gpu.h:235`) and runtime-resumes with every desktop interaction. If the OPP reference count reaches zero, the OPP can be freed before `dev_pm_opp_set_opp()` dereferences it. A use-after-free in this path can corrupt the GPU/PM state and lead to a hard reset. |
| 2 | `a6xx_gmu_rpmh_votes_init()` calls `a6xx_gmu_rpmh_dep_votes_init(gmu->dev, ...)` while iterating `gmu->gpu_freqs` (`a6xx_gmu.c:1867`). | `eab0aff8965ee17cf972a37eb6456032c45b7acd` "drm/msm/a6xx: Fix RPMH dependency votes" (2026-09-23), <https://github.com/torvalds/linux/commit/eab0aff8965ee17cf972a37eb6456032c45b7acd> | The dependency table must be resolved against the device that owns the GPU OPP table (`gpu->pdev->dev`). Resolving with the GMU device produces wrong MX/CX votes, which can under-voltage or mis-sequence the GPU rails under load. |
| 3 | The secondary ARC rail is matched with `sec[j] >= level` (`a6xx_gmu.c:1767`). | `128a0edde50780ed9eb93ab5d2e18ca24c1f1c43` "drm/msm/a6xx: Fix secondary rail vote in ARC votes" (2026-09-23), <https://github.com/torvalds/linux/commit/128a0edde50780ed9eb93ab5d2e18ca24c1f1c43> | The secondary rail depends on the selected primary rail; matching the requested level instead of the quantized primary voltage can pick a lower secondary corner and under-vote the dependent rail. |
| 4 | `a6xx_pm_resume()` ignores the return values of both `pm_runtime_resume_and_get()` calls. | `e2f57c576f14f96449cfee840860cb9707501d23` "drm/msm/a6xx: check pm_runtime_resume_and_get during resume" (2026-09-29), <https://github.com/torvalds/linux/commit/e2f57c576f14f96449cfee840860cb9707501d23> | A failed resume must not continue into register access or leak PM references; this makes the resume failure path deterministic instead of touching suspended hardware. |
| 5 | `adreno_gpu_cleanup()` does not call `pm_runtime_dont_use_autosuspend()`. | `6fbbf1e152f34ad3913e4a6476680aba672c5068` (2026-08-08) | Teardown leaves an autosuspend reference; relevant to reload/unbind and repeated probe cycles. |
| 6 | The MX dependency vote can fail when the GPU arc level exceeds the highest MX corner. | `86f80884fb7f4601a49444a3c36df894b218336e` "drm/msm/a6xx: Clamp MX dependency vote" (2026-09-23) | The clamp keeps GMU initialization from failing on chips with a lower MX ceiling; our X1E may not need it, but it is part of the same series. |

The three core patches (1-3) apply cleanly to pinned v7.3 with `patch --fuzz=0`; patch 4 was adapted to the v7.3 context. The 100 ms GMU firmware initialization timeout is already present (`ba970587a0`); the a750 CX AO counter fix does not apply because this GPU is `ADRENO_7XX_GEN2`.

## Windows cross-check (REA)

`qcdxkm8380.sys`, SHA-256 `46237eba1c2c0a51d700cdf14730aae3f41b0a55775a185b87e618cab8285814`, ARM64 PE, Ghidra 12.1.4, evidence `ev_e8cad493b737a821892fd71db7518e0d13393f25cd40318a01204d90eb8a1174` and `ev_9ab34d83eef1f6a94ee0aae9c48c3749fb3fe58e7295795c44095b9c5dcd368b`.

The Windows KMD reads the platform's GPU feature keys `DisableGmuACD`, `Preemption`, `PreemptionCounter`, `SleepMode`, `PreventPowerCollapse`, `ForceActive` and `ForceMaxPerf`. With the keys absent, ACD is enabled and `Preemption` defaults to `0x1a`; power-collapse prevention defaults to off. This does not justify a blanket ACD/preemption disable on Linux, but it confirms that the platform has the same power-collapse features and that the Linux PM/rail programming must be correct.

## Status

Revision 21 integrates the fixes as kernel integration copies and is building `7.3.0-65.sp11.21.fc44.aarch64` with BTF and `CHECK_DTBS`. The rev21 debug entry carries `sp11.gpu_pin=0` so the device test evaluates these kernel fixes rather than the userspace pin. No device result is claimed.

## Path correction after the rev21 source review

Chip `0x43050c01` selects `a7xx_gpu_funcs` (`a6xx_catalog.c:1573-1585`), and that table's PM resume is `a6xx_gmu_pm_resume` (`a6xx_gpu.c:2866-2873`). The OPP use-after-free and the unchecked `pm_runtime_resume_and_get()` are in the separate `a6xx_pm_resume` wrapper (`a6xx_gpu.c:2832-2839`), used by the non-GMU-wrapper A6xx path. They are valid upstream fixes and are included for the tree, but they are **not evidence that they ran on this GPU** and must not be called the primary cause of the observed reset. The RPMH dependency-vote and secondary-rail fixes do affect `a6xx_gmu_rpmh_votes_init()`/the GMU path used here; whether wrong votes cause the silent reset is plausible but unproven until the device test. The single-init change (GPU firmware kept on the rootfs but removed from the initramfs) follows the working reference and removes the early DRM-client initialization; it is part of the same test, not a proven fix.

## Firmware placement correction (D38)

Removing the GPU firmware from the initramfs was considered to match the reference live ISO and then rejected: the reference live ISO does not bring the GPU up; its README installs `sp11-grab-fw` after installation. In our image `msm` probes from the initramfs and does not retry after rootfs mount, so removing the blobs could leave the live GPU unavailable. Revision 21 keeps the three GPU firmware files in the initramfs. The single-init hypothesis is not part of the test; the applicable kernel changes remain the GMU RPMH vote fixes, tested with `sp11.gpu_pin=0`.
