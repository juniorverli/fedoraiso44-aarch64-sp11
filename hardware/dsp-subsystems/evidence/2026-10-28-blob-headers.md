# Staged DSP images versus what DT and driver request

2026-10-29 correction: section 4's claim that `RADS.bin` is consumed by Windows userspace is unproven. It is registered as a subsystem resource input. No Linux firmware request is known; equivalence of its resource operations remains TBD. See `2026-10-29-windows-loader-inputs.md`. The header/hash results below remain valid.

Reproduced independently of the firmware worker with `hardware/dsp-subsystems/tools/mdtcheck.py` (ELF and program-header fields only; it mirrors `drivers/soc/qcom/mdt_loader.c:22-45,296-319,350-440`, v7.3; no code is decoded, so no Ghidra language applies; `sources/binary-catalog.tsv` rows: the two `.mbn` are `code, Hexagon:LE:32:default`, the two `*_dtbs.elf` are `data, never disassemble`). Run: `python3 -I hardware/dsp-subsystems/tools/mdtcheck.py sources/windows`.

## 1. Names and paths (Verified)

| DT string (`x1-microsoft-denali.dtsi`) | Requested by | Staged file (`firmware/manifest.toml`) | In the M5 initramfs |
|:--|:--|:--|:--|
| `qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn` (`:1039`) | `rproc_boot()` `request_firmware(rproc->firmware)` (`remoteproc_core.c:1971`); name from `qcom_q6v5_pas.c:838-842` | `adsp-image`, from `surfacepro_ext_adsp8380.inf_arm64_3cc952aaca3564ae/qcadsp8380.mbn` | yes, SHA-256 equal (image L0 check 5.7) |
| `.../adsp_dtb.mbn` (`:1040`) | `qcom_pas_load()` `request_firmware(dtb_firmware_name)` (`qcom_q6v5_pas.c:245`); name from `:844-849` | `adsp-dtb`, from `adsp_dtbs.elf` | yes |
| `.../qccdsp8380.mbn` (`:1046`) | same as ADSP | `cdsp-image`, from `qcnspmcdm_ext_cdsp8380.inf_arm64_4a8c3ebe3aad408a/qccdsp8380.mbn` | yes |
| `.../cdsp_dtb.mbn` (`:1047`) | same as ADSP DTB | `cdsp-dtb`, from `cdsp_dtbs.elf` | yes |

- `.mbn` versus `.mdt`: the driver tables name `adsp.mdt`, `adsp_dtb.mdt`, `cdsp.mdt`, `cdsp_dtb.mdt` (`qcom_q6v5_pas.c:1246-1247,1267-1268`) but both are replaced by the DT `firmware-name` (`:839-849`). Every image is a single-file MDT (no `.bNN` segment files): `split = False` below, so `mdt_load_split_segment()` is never reached and the file name is never used to derive another name.
- DTB handling: there is no `qcom,dtb-firmware-name`; the DTB image is `firmware-name` index 1 (binding `qcom,sm8550-pas.yaml:68-71`), read with `of_property_read_string_index(..., 1, ...)` (`qcom_q6v5_pas.c:846`). `dtb_pas_id` is `0x24` (ADSP) and `0x25` (CDSP), set only when the table has a `dtb_firmware_name` (`:880-883`), so the DT must give two strings: it does.
- Compression: the staged files are plain; the loader tries the plain name first (`drivers/base/firmware_loader/main.c:876-888`).
- Result: names, paths and hashes match the DT and the driver exactly. The firmware worker's four entries (`adsp-image`, `adsp-dtb`, `cdsp-image`, `cdsp-dtb`) are confirmed; no correction is needed.

## 2. Hashes (Verified, `sha256sum` of `sources/windows`)

| File | SHA-256 | Size |
|:--|:--|--:|
| `qcadsp8380.mbn` | `921870a839ee2aba647b04598d62ed96f3d2d5dfbb2499fc842f9a6ff0e0da13` | 22092168 |
| `adsp_dtbs.elf` | `544bd795cb06cf8dee8119ede2a667f01066b2f1b9e4348f1772d080e2026ff4` | 73528 |
| `qccdsp8380.mbn` | `4a67a03367f2eff2f8a0e867ca25d2bf2fcd5aee3e41e2c9f436c804e257c789` | 3195304 |
| `cdsp_dtbs.elf` | `93941f040da14b8305d39579686d886706d22954a538b03da676c1aaa191797f` | 40760 |

All four equal `firmware/manifest.toml`.

## 3. Program headers against the DT memory regions (Verified)

| Image | ELF32 LE | `e_machine` | phdrs | `phdr[0]` | hash segment | split | loadable | `MDT_RELOCATABLE` | paddr span | DT region |
|:--|:--|--:|--:|:--|--:|:--|--:|:--|:--|:--|
| ADSP image | yes | 164 (Hexagon) | 58 | not PT_LOAD | ph57, inside file | no | 56 | yes | `0x87e00000`-`0x8b800000` (`0x3a00000`) | `adspslpi_mem` `0x87e00000` size `0x3a00000`: exact fit |
| ADSP DTB | yes | 1 | 3 | not PT_LOAD | ph2, inside file | no | 1 | yes | `0x8b800000`-`0x8b810e6c` (page-rounded span `0x11000`) | `q6_adsp_dtb_mem` `0x8b800000` size `0x80000`: fits |
| CDSP image | yes | 164 (Hexagon) | 16 | not PT_LOAD | ph15, inside file | no | 14 | yes | `0x8b900000`-`0x8d900000` (`0x2000000`) | `cdsp_mem` `0x8b900000` size `0x2000000`: exact fit |
| CDSP DTB | yes | 1 | 3 | not PT_LOAD | ph2, inside file | no | 1 | yes | `0x8d900000`-`0x8d908bec` (span `0x9000`) | `q6_cdsp_dtb_mem` `0x8d900000` size `0x80000`: fits |

- `e_flags` is `0x73` on both Hexagon images (V73) and `0x5` on the containers. `e_phentsize` is 32 and `e_shnum` 0 on all, so `mdt_header_valid()` accepts them.
- All four are relocatable, so `__qcom_mdt_pas_init()` calls `qcom_pas_mem_setup(pas_id, mem_phys, max_addr - min_addr)` (`mdt_loader.c:280-290`); the span equals the region size for the two images and is smaller for the DTBs. `qcom_mdt_load_no_init()` then uses `min_addr` as the relocation base, which equals the region start, so no segment falls outside (`:393-399`).
- The spans match the Windows reservations in the INFs: ADSP `0x3A00000`, ADSP_DTB `0x11000` (`surfacepro_ext_adsp8380.inf:195-196`), CDSP `0x2000000` (CDSP INF). Inference: Windows and Linux place the images in the same carve-outs.
- The Windows INF also loads a "lite" ADSP image in UEFI (TZ ids `0x1F`, `0x29`, `:139-143`); Linux handles it: `qcom_pas_load()` calls `qcom_pas_shutdown()` on `lite_pas_id` and `lite_dtb_pas_id` (`qcom_q6v5_pas.c:239-242`, ids at `:1250-1251`). Inference: the two numbers agree, so the table row for x1e80100 is the right one for this firmware.

## 4. Not loaded by Linux (Verified that nothing requests them)

`RADS.bin` (Windows "Resources BinaryPath", 1401 bytes, `data`) and the `ADSP/` and `CDSP/` user-space libraries (`fastrpc_shell_0`, `fastrpc_shell_3`, audio modules, `libsysmon*_skel.so`; catalogued `code, Hexagon`) are read by Windows user-mode services, not by `qcom_q6v5_pas`. They matter only to a FastRPC user-space daemon (NPU, sensors), which is outside D22. The manifest keeps them out; the previous project shipped four CDSP user payloads (surface-compare 2g), which the `npu` worker may request later.
