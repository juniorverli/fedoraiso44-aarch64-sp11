# gpu worker

**Owns:** `hardware/gpu/` (write). Everything else is read-only.
**Phase:** 1. **Kernel worktree:** only if a patch turns out to be needed (`out/linux/gpu`, branch `w/gpu`).

## Mission

Accelerated OpenGL and Vulkan on the Adreno X1-85 under GNOME, at the correct frequency limits for the X1P64100, with no kernel patch unless one is proven necessary.

## Start

1. Read `hardware/gpu/README.md`, `component.toml`, `hardware/display-lcd/README.md` (shared `qcdx8380` package) and `firmware/manifest.toml`.
2. Answer the dossier's open questions in order. Q1 (speed bin) is the priority because it is the only thing that could need a kernel change.

## Specific leads

- **Speed bin (Q1).** In `sources/linux/drivers/gpu/drm/msm/adreno/a6xx_catalog.c`, read the `0x43050c01` entry and its `speedbins`; in `hamoa.dtsi`, the GPU OPP table and `opp-supported-hw`; in `a6xx_gpu.c`, how the fuse is read and what happens on an unknown value. Then decide which bin the X1P64100 should get. On the Windows side, find in `qcdxkm8380.sys` (REA) how one of `qcdxkmbase8380.bin`, `_68`, `_110`, `_150`, `_pa*` is chosen, and decode the chosen file's frequency table if possible.
- **Firmware.** Confirm `gen70500_sqe.fw` and `gen70500_gmu.bin` are in Fedora 44's `linux-firmware` (package file list) and give the NEVRA to the firmware worker as a request. Confirm the zap shader's PAS ID/format matches what `adreno_zap_shader_load` expects (`.mbn` header check only, no execution).
- **Mesa.** Find the Mesa version in Fedora 44 and check that freedreno and Turnip list chip `0x43050c01` (Mesa source `src/freedreno/common/freedreno_devices.py`).
- **Thermal coupling (Q3).** Note what `QCOM0CF7` (GPU limits policy) does in Windows and hand it to `power-thermal` as a request; do not implement it here.

## Deliver

1. `evidence/<date>-speedbin.md` with the decision and its grade.
2. A patch only if Q1 shows Linux would run the part above its rating.
3. `test-plan.md` covering the dossier's acceptance list (`glxinfo -B`, `vulkaninfo --summary`, `vkcube`, `glmark2-es2-wayland`, devfreq readout, `dmesg` filters).
4. Dossier and `component.toml` updated; status `designed` or `sw-ready`.

## Do not

- Ship the Purwa zap shader (`qcdxkmsucpurwa.mbn`); it is for a different SoC.
- Raise any GPU frequency above what Windows uses for this SKU.
