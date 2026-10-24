# Firmware

Owner: firmware worker (`agents/workers/firmware.md`). Phase 1 map complete on 2026-10-24 (`soc-boot`, `display-lcd`, `gpu`, `dsp-subsystems`).

`manifest.toml` is the only list of firmware this project ships. Each entry says which kernel code asks for the file, under which Linux path, and where the bytes come from: the local DriverStore (with SHA-256) or Fedora's `qcom-firmware` package.

Rules:

1. No binary in git (`plan/risks.md` S5). `scripts/firmware-stage.sh` copies DriverStore files into `out/firmware-root/` at build time, on this machine only.
2. A Linux path comes from the kernel or userspace that requests it, cited with `file:line`. Never guess a name.
3. When Fedora's `linux-firmware` already ships a file, use the package (D12) and record the NEVRA. The image installs the package; the staging script never copies those files.
4. Windows and Linux names may differ (`adsp_dtbs.elf` is requested as `adsp_dtb.mbn`). Record both.
5. Components declare their needs in `hardware/<component>/component.toml` `[firmware]`; this manifest resolves them.
6. `status = "mapped"` means the requesting code and the source are both cited.

## 1. Phase 1 map

All code citations are lines in `sources/linux` (v7.3). Grades follow `agents/protocol.md` §5.

| Component | Kernel path requested under `/lib/firmware` | Requested by | Source | Status |
|:--|:--|:--|:--|:--|
| gpu | `qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn` | `x1-microsoft-denali.dtsi:723-725`, loaded at `adreno_gpu.c:82-87,141,156` | DriverStore `qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkmsuc8380.mbn` | mapped |
| gpu | `qcom/gen70500_sqe.fw` | `a6xx_catalog.c:1573-1578`, loaded at `adreno_gpu.c:634,543,554` | Fedora `qcom-firmware` `/usr/lib/firmware/qcom/gen70500_sqe.fw.xz` | mapped |
| gpu | `qcom/gen70500_gmu.bin` | same entry, consumed at `a6xx_gmu.c:864-868` | Fedora `qcom-firmware` `/usr/lib/firmware/qcom/gen70500_gmu.bin.xz` | mapped |
| dsp-subsystems | `qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn` | `x1-microsoft-denali.dtsi:1038-1043`, `qcom_q6v5_pas.c:838-842`, `remoteproc_core.c:1971` | DriverStore `surfacepro_ext_adsp8380.inf_arm64_3cc952aaca3564ae/qcadsp8380.mbn` | mapped |
| dsp-subsystems | `qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn` (Windows `adsp_dtbs.elf`) | same node, `qcom_q6v5_pas.c:844-849,245,252` | same package, `adsp_dtbs.elf` | mapped |
| dsp-subsystems | `qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn` | `x1-microsoft-denali.dtsi:1045-1050`, `qcom_q6v5_pas.c:838-842` | DriverStore `qcnspmcdm_ext_cdsp8380.inf_arm64_4a8c3ebe3aad408a/qccdsp8380.mbn` | mapped |
| dsp-subsystems | `qcom/x1e80100/microsoft/Denali/cdsp_dtb.mbn` (Windows `cdsp_dtbs.elf`) | same node, `qcom_q6v5_pas.c:844-849,245,252` | same package, `cdsp_dtbs.elf` | mapped |
| display-lcd | none | no `request_firmware()` in `drm/msm` outside adreno, `phy-qcom-edp.c`, `panel-edp.c`, `pwm_bl.c`, `leds-qcom-lpg.c` | | nothing to ship |
| soc-boot | none in this DT (`qupv3fw.elf` only if a DT node asks) | `qcom-geni-se.c:1553-1601`; no `firmware-name` on Denali `qupv3_*` (`x1-microsoft-denali.dtsi:1026-1037`) | Fedora has `qcom/x1e80100/qupv3fw.elf.xz` if ever needed | not shipped |
| dsp-subsystems | five `*.jsn` service maps | nobody (see 4) | DriverStore, kept in `[[not_shipped]]` | not shipped |

Seven blobs ship: five from the DriverStore (staged by the script, 25.4 MB) and two from Fedora (installed by the image).

## 2. Fedora 44 linux-firmware (Verified 2026-10-24, `registry.fedoraproject.org/fedora:44`, `dnf repoquery`)

- `linux-firmware` is split into subpackages. Everything Qualcomm for this project is in **`qcom-firmware`** (`noarch`). Fedora release repo: `qcom-firmware-0:20260309-1.fc44.noarch` (RPM SHA-256 `8fb8205f...2d1b`). Updates repo: `qcom-firmware-0:20261019-1.fc44.noarch` (RPM SHA-256 `b72830ac...48b8`). The two blobs we use have identical file digests in both.
- `linux-firmware` (meta package) does **not** recommend or require `qcom-firmware` (`--recommends`, `--whatrecommends`, `--whatrequires` all checked). The image must list `qcom-firmware` itself.
- Files are installed as `/usr/lib/firmware/qcom/...*.xz`. `/lib` is `/usr/lib` on Fedora, so the kernel path `qcom/gen70500_sqe.fw` resolves.
- **Compressed variants.** The kernel tries the plain name, then `.zst`, then `.xz`, in that order, for both `request_firmware()` and `request_firmware_direct()` (`drivers/base/firmware_loader/main.c:876-888`; `FW_OPT_PARTIAL` is not set by either call). Search path: `/lib/firmware/updates/<release>`, `/lib/firmware/updates`, `/lib/firmware/<release>`, `/lib/firmware` (`main.c:472-478`). The Fedora aarch64 config enables both decompressors: `CONFIG_FW_LOADER_COMPRESS_XZ=y`, `CONFIG_FW_LOADER_COMPRESS_ZSTD=y`, and sets neither `CONFIG_FW_LOADER_USER_HELPER` nor the fallback (`out/build/kernel/rpmbuild/SOURCES/kernel-aarch64-fedora.config:2945-2951`, the kernel worker's spec sources). The DriverStore files are staged uncompressed, which the kernel tries first.
- **Not in Fedora for this device.** Zap shader, ADSP, CDSP and their DT containers for the Surface Pro 11 are not in Fedora. Fedora ships other vendors' `qcdxkmsuc8380.mbn`, `qcadsp8380.mbn`, `qccdsp8380.mbn`, `adsp_dtbs.elf`, `cdsp_dtbs.elf` under `qcom/x1e80100/{LENOVO/21N1,LENOVO/83ED,dell/xps13-9345}/` and generic `qcom/x1e80100/{adsp,cdsp,adsp_dtb,cdsp_dtb,gen70500_zap}.mbn`. I extracted the 20261019 RPM and hashed the decompressed content of all 245 `.xz`, `.mbn`, `.elf` and `.jsn` files under `qcom/`: none equals the SHA-256 of the five DriverStore binaries. The Denali DT names `qcom/x1e80100/microsoft/...` paths that no Fedora package has. Whether another vendor's signed image would authenticate on this device is Hypothesis (signing is per OEM); the hashes differ, so it is not a drop-in anyway.
- **`qupv3fw.elf`.** Yes, `qcom/x1e80100/qupv3fw.elf.xz` is in `qcom-firmware` (packaged SHA-256 `448c37c8...3f62`). The Denali DT does not use it (section 5).

## 3. Windows to Linux renames (Verified for the format, Inference for equal content)

The two DT containers are requested as `adsp_dtb.mbn` and `cdsp_dtb.mbn` by `x1-microsoft-denali.dtsi:1038-1050`. The Windows files are `adsp_dtbs.elf` and `cdsp_dtbs.elf` (`sources/binary-catalog.tsv`: kind `data`, `CFGL` header with FDTs).

What the kernel needs from such a file is what `qcom_mdt_pas_load()` needs (`drivers/soc/qcom/mdt_loader.c:22-45` header check, `:296-319` split check, `:350-440` load): ELF32 with `e_phentsize` 32, `phdr[0]` not `PT_LOAD`, one hash segment, every segment inside the file. A local check script (not committed; it mirrors those conditions) on all five Windows files gave:

| File | phdrs | hash segment | split | first PT_LOAD `p_paddr` | DT region it must match |
|:--|--:|:--|:--|:--|:--|
| `adsp_dtbs.elf` | 3 | ph2 | no | `0x8b800000` | `q6_adsp_dtb_mem` `hamoa.dtsi:583-586` (memory-region[1], `:4301`) |
| `cdsp_dtbs.elf` | 3 | ph2 | no | `0x8d900000` | `q6_cdsp_dtb_mem` `hamoa.dtsi:593-596` (`:8973`) |
| `qcadsp8380.mbn` | 58 | ph57 | no | `0x87e00000` | `adspslpi_mem` `hamoa.dtsi:578-581` (`:4300`) |
| `qccdsp8380.mbn` | 16 | ph15 | no | `0x8b900000` | `cdsp_mem` `hamoa.dtsi:588-591` (`:8972`) |
| `qcdxkmsuc8380.mbn` | 3 | ph2 | no | `0x1000` relocatable, size 0x430 | `gpu_microcode_mem` `hamoa.dtsi:598-601` (size 0x2000 is enough) |

Conclusion: the rename is only the string in the DT. Nothing in the loader derives data from the file name of a non-split image (the name is used only to build `.bNN` segment names, `mdt_loader.c:70-85`). Other DTs ask for the same Windows file under its Windows name (`x1p42100-microsoft-sp12in.dts:910,917`, `x1e80100-lenovo-yoga-slim7x.dts:1249,1255`). The staging script renames at copy time through `linux_path`. Equal content is Inference: the checks above prove the format and the memory placement, not that the Windows file is the one Qualcomm's loader would have wanted.

## 4. The `*.jsn` service maps are not needed in phase 1

- **Fedora 44 has no `pd-mapper`.** `qrtr-1.2-2.fc44` contains `Obsoletes: pd-mapper < 1.0-6` and ships only `qrtr-cfg` and `qrtr-lookup`; its changelog says "Drop qrtr-ns, obsolete pd-mapper". No package owns `*/pd-mapper*` (Verified, `dnf repoquery --file`, `-l`, `--obsoletes`, `--changelogs`).
- **Linux 7.3 has the mapper in the kernel.** `drivers/soc/qcom/qcom_pd_mapper.c` carries `x1e80100_domains` (`:609-616`), chosen by root compatible `qcom,x1e80100` (`:666`); the Denali root compatible lists it (`x1p64100-microsoft-denali.dts:13-14`). It starts as an auxiliary device when the ADSP boots (`qcom_common.c:550-562`, `qcom_q6v5_pas.c:918`). Fedora builds it (`CONFIG_QCOM_PD_MAPPER=m`, `CONFIG_QRTR=m`, kernel config `:6868,6945`); the QRTR name service is in the kernel too (`net/qrtr/Makefile:3`).
- **The kernel table equals the Windows maps** (all five `.jsn` read): adsp `root_pd`, `sensor_pd`, `audio_pd` (with `avs/audio`), `charger_pd`, all instance 74; cdsp `root_pd`, instance 76 (`qcom_pd_mapper.c:253-312`). One difference: `adspr.jsn` also lists `tms/pdr_enabled`; the kernel adds that only through `adsp_root_pd_pdr` (`:280-287`), which `x1e80100_domains` does not use. No kernel code looks that service up (grep); the DSP side might. Hypothesis: harmless, as on other X1E laptops. A kernel with no match prints `PDM: no support for the platform` (`:690`).
- Same hash check on the five `.jsn`: each is byte-identical to the file of the same name in Fedora's `qcom/x1e80100/LENOVO/21N1/` (Verified). Inference: the maps are SoC-generic, not Surface-specific, so if a userspace mapper is ever needed, Fedora's copy is a source too.
- The five files stay in `manifest.toml` under `[[not_shipped]]` with their hashes, so a userspace mapper could be added later without searching again.

## 5. `qupv3fw.elf` for the GENI engines (soc-boot)

`geni_load_se_firmware()` (`qcom-geni-se.c:1553-1601`) is called only when an engine reports an invalid protocol (`i2c-qcom-geni.c:1083-1084`, `spi-geni-qcom.c:650-651`, `qcom_geni_serial.c:1359-1360`) and needs `firmware-name` on the `geniqup` node, otherwise it returns `-EINVAL` (`:1565-1568`). The Denali DT sets none (`x1-microsoft-denali.dtsi:1026-1037`); in v7.3 only `hamoa-iot-som.dtsi:450,456,462` sets it for X1E. So nothing requests the file now. Whether Windows' firmware leaves an engine unprogrammed is TBD until the M2 log. The DriverStore has no qupv3 file; Fedora's `qcom/x1e80100/qupv3fw.elf.xz` would be the source, and `qcom-firmware` is installed anyway. See `[[not_shipped]] geni-qupv3fw`.

## 6. Staging

```bash
scripts/firmware-stage.sh            # verify, then copy into out/firmware-root/
scripts/firmware-stage.sh --check    # verify only, write nothing
```

Result: `out/firmware-root/lib/firmware/<linux_path>` for each DriverStore blob plus `out/firmware-root/STAGED.sha256` (relative to `out/firmware-root`, usable with `sha256sum -c`). Behaviour:

1. Pass 1 checks every file and writes nothing: missing file, SHA-256 mismatch, a manifest hash that differs from `sources/windows/MANIFEST.sha256`, a bad or duplicate `linux_path` (absolute, `..`) all end with exit 1.
2. Pass 2 copies into a fresh sibling directory, re-verifies each copy, and swaps it in. The old tree is replaced, so files removed from the manifest disappear.
3. `linux-firmware` entries are listed, not copied. The script refuses an output directory that is not named `firmware-root`, or that lies inside the repository and is not git-ignored.

Run on 2026-10-24: 5 files verified and staged, final `sha256sum -c` passed. Negative runs with a corrupted hash, a missing source and a `../` path each exited 1 and left the previous output untouched.

## 7. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| F1 | Does the image have the five staged files when `qcom_q6v5_pas` probes? `rproc_trigger_auto_boot()` uses `request_firmware_nowait()` (`remoteproc_core.c:1698`), the Fedora config has no user-helper fallback, and I found no retry: a missing file leaves the DSP offline. If udev loads the module inside the initramfs, the files must be there. | Inference | M2 boot log: `remoteproc` state and `request_firmware failed` lines |
| F2 | Is the zap shader accepted by TrustZone with PAS id `GPU_PAS_ID` (`a6xx_gpu.c:1137`) and this region? | TBD | `dmesg` "Unable to authorize the image" or its absence on M2 |
| F3 | Do the Windows DT containers match the kernel's expected DSP DT content, not just its format? | Hypothesis | ADSP reaches `running` and `pmic_glink` binds |
| F4 | Does any DSP service need `tms/pdr_enabled`? | Hypothesis | ADSP and audio service logs on M2 |
| F5 | Fedora 44 NEVRA to pin for the ISO: release `20260309-1.fc44` or updates `20261019-1.fc44`? Both carry the same two blobs. | Decision | image worker / orchestrator |

## 8. Requests

- **image:** install `qcom-firmware` by name (it is not pulled by `linux-firmware`). Run `scripts/firmware-stage.sh` before composing the image, then copy `out/firmware-root/lib/firmware/` into `/usr/lib/firmware/` of the image (Fedora's `/lib` is a link to `/usr/lib`). Nothing else from `sources/windows` goes into the image. Do not look for `pd-mapper` or `qrtr-ns`: Fedora 44 has neither, the kernel provides both functions. Decide F1: either keep `qcom_q6v5_pas` out of the initramfs, or install the five staged files in it (dracut `install_items`).
- **kernel:** the Fedora aarch64 config already has `QCOM_PD_MAPPER=m`, `QRTR=m`, `QCOM_MDT_LOADER=m`, `QCOM_Q6V5_PAS=m`, `FW_LOADER_COMPRESS_XZ=y`; keep them in the series. Do not set `FW_LOADER_USER_HELPER`.
- **dsp-subsystems dossier (`hardware/dsp-subsystems/`):** the line "Userspace: `pd-mapper` (reads the `*.jsn` maps)" and the gap "JSON service maps consumer and path unknown" are resolved: no userspace mapper in Fedora 44, in-kernel mapper covers x1e80100 (section 4). The "Windows to Linux firmware names" gap is closed (section 3).
- **gpu dossier (`hardware/gpu/`):** `gen70500_sqe.fw` and `gen70500_gmu.bin` are in Fedora `qcom-firmware` (section 2); the gap "Fedora 44 linux-firmware versions unpinned" can cite the NEVRAs above. The zap shader citation is `x1-microsoft-denali.dtsi:723-725`.
- **soc-boot dossier (`hardware/soc-boot/`):** `needs = ["qcom/x1e80100/qupv3fw.elf ..."]` can become empty: no Denali node requests it (section 5).
- **orchestrator:** `.gitignore` has `/out/`, which does not match the `out` symlink of a worktree (`git status` shows `out` untracked). The pending `/out` change in the main checkout fixes it.

## 9. Log

- 2026-10-24: phase 1 map complete: 7 blobs and 7 `[[not_shipped]]` records with `file:line` citations; Fedora 44 `qcom-firmware` NEVRAs and file digests recorded; renames and MDT format checked; `*.jsn` and `qupv3fw.elf` decided; `scripts/firmware-stage.sh` written and run (5 files staged and verified).
