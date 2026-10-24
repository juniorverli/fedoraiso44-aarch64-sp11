# Binary formats in the Windows dumps

Owner: sources worker. Generated data: `binary-catalog.tsv` (one row per file, 1648 files), produced by `scripts/classify-binaries.py` from the **bytes** of each file, never from its extension.

## 1. Why this exists

A decompiler loaded with the wrong CPU still prints plausible-looking code. That is the main way an AI invents facts during reverse engineering. This catalog fixes, for every file, what it is and how it may be read:

| Column | Meaning |
|:--|:--|
| `container` | PE, ELF, signed Qualcomm MBN (ELF with a hash segment), UEFI FMP capsule, PKCS#7 catalog, JSON, XML, text, hex text, opaque blob |
| `machine` | CPU the header declares (PE `Machine`, ELF `e_machine`); ARM64X and CHPE hybrids are detected from the load configuration |
| `kind` | `code`, `data`, `data-in-ELF` (ELF with no executable segment), `gpu-firmware`, `config`, `text`, `signature`, `firmware-capsule`, `compressed` |
| `ghidra_language` | The only language the file may be loaded with in REA/Ghidra, or "none" / "NO GHIDRA LANGUAGE" |
| `details` | Sub-type, Hexagon architecture version from `e_flags`, segment counts, hand-checked `OVERRIDE` notes |
| `entropy` | Shannon entropy of the first MiB; above 7.9 means compressed or encrypted, so structure cannot be read directly |

## 2. Rules for every agent

1. Look the file up in `binary-catalog.tsv` before opening it in REA. Cite the catalog row (path and SHA-256) with the result.
2. Load code only with the `ghidra_language` of its row. Never let auto-detection or the file extension pick the CPU.
3. Never disassemble a row whose kind is not `code`. Data is decoded by its format (JSON, XML, FDT, a documented table), or reported as opaque.
4. "NO GHIDRA LANGUAGE" means the CPU is unknown or not trusted. Do not try ARM, Hexagon or x86 "to see what happens"; report it as TBD.
5. Hex text files (`*.hex`) are a textual dump of bytes: convert them to binary first, then classify the result.
6. If REA reports a different architecture than the catalog, or the decompiled output contains bad-instruction markers (`halt_baddata`, "Bad instruction"), stop and report. That result is not evidence.
7. Hybrid PE files (ARM64X, CHPE x86) contain code for two instruction sets. State which half (native ARM64 or ARM64EC/x64/x86) a function belongs to.

## 3. Totals by kind

| Kind | Files |
|:--|--:|
| `text` | 576 |
| `code` | 378 |
| `data` | 320 |
| `signature` | 240 |
| `config` | 87 |
| `data-in-ELF` | 25 |
| `firmware-capsule` | 19 |
| `gpu-firmware` | 2 |
| `compressed` | 1 |

## 4. Code by CPU

| Container | CPU (from the bytes) | Files | Ghidra language | Components | Examples |
|:--|:--|--:|:--|:--|:--|
| PE | ARM64 | 223 | `AARCH64:LE:64:v8A` | audio-mics, audio-speakers, bluetooth, cameras, display-lcd, dsp-subsystems, ec-sam, firmware-updates, gpu, npu, power-thermal, security-tpm, sensors, soc-boot, touch-pen, usb-typec, usb4, video-codec, wifi, wwan | `AcpiAudioCompositor.sys`, `AcxProxyAPO.dll`, `HIDI3C.dll`, `HdAudio.sys` |
| ELF | Hexagon (QDSP6) | 68 | `Hexagon:LE:32:default` | dsp-subsystems, npu | `AudioSphereModule.so.1`, `CFCM.so.1`, `SAPlusCmnModule.so.1`, `aac_dec_module.so.1` |
| PE | ARM64X | 41 | `AARCH64:LE:64:v8A` | display-lcd, dsp-subsystems, gpu, npu, video-codec | `CB.dll`, `HtpUsrDrv.dll`, `OpenCL.dll`, `OpenCL_adreno.dll` |
| PE | x86 | 16 | `x86:LE:32:default` | display-lcd, gpu, video-codec | `qcdx11chpeum.dll`, `qcdx11x86um.dll`, `qcdx12chpeum.dll`, `qcdx12x86um.dll` |
| ELF (signed MBN) | ARM | 13 | `ARM:LE:32:v8` | security-tpm, wifi | `asym1p.sig`, `asym1t.sig`, `crypt1p.sig`, `crypt1t.sig` |
| ELF (signed MBN) | Xtensa | 5 | `Xtensa:LE:32:default` | cameras, display-lcd, gpu, video-codec | `CAMERA_ICP.mbn`, `evass.mbn`, `qcvss8380.mbn`, `qcvss8380_pa.mbn` |
| ELF (signed MBN) | ARM64 | 4 | `AARCH64:LE:64:v8A` | security-tpm | `hdcp1.mbn`, `hdcp2p2.mbn`, `hdcpsrm.mbn`, `pr_3_wp.mbn` |
| ELF (signed MBN) | Hexagon (QDSP6) | 3 | `Hexagon:LE:32:default` | cameras, dsp-subsystems, npu | `libbitml_nsp_v2_skel.so`, `qcadsp8380.mbn`, `qccdsp8380.mbn` |
| ELF | ARM64 | 2 | `AARCH64:LE:64:v8A` | display-lcd, gpu, video-codec | `libqcdx12arm64wslum.so`, `qcgpuarm64compilercore.so` |
| ELF | Xtensa | 1 | `Xtensa:LE:32:default` | cameras | `CAMERA_ICP_AAAAAA.elf` |
| ELF (signed MBN) | elf-machine-106 | 1 | `NO GHIDRA LANGUAGE: unknown core (e_machine 106), do not guess` | display-lcd, gpu, video-codec | `qcav1e8380.mbn` |
| ELF | x86 | 1 | `NO GHIDRA LANGUAGE: e_machine 3 (x86) is implausible for WCN7850 PHY microcode, do not guess` | wifi | `phy_ucode20.elf` |

## 5. Files whose header misleads (hand-checked overrides)

| File | Header says | What it is | Rule |
|:--|:--|:--|:--|
| `qcdxkmsuc8380.mbn` | ELF, Hexagon (e_machine 164) | Adreno zap shader in a signed PIL container; the 0x430-byte segment is GPU code loaded through TrustZone (Inference) | Do not disassemble as Hexagon; ship as firmware |
| `qcdxkmsucpurwa.mbn` | same | Zap shader for the Purwa SoC | Not for this machine |
| `adsp_dtbs.elf`, `cdsp_dtbs.elf` | ELF, e_machine 1, executable segment | Device-tree container (`CFGL` header, holds FDTs, Verified) | Data; decode the FDTs with `dtc`, never disassemble |
| `bdwlan*.elf`, `bdwlan*.e*` | ELF, ARM | Wi-Fi board data (calibration tables), no executable segment | Data |
| `qcav1e8380.mbn` | ELF, e_machine 106 | AV1 encoder firmware for an unidentified core | NO GHIDRA LANGUAGE |
| `phy_ucode20.elf` | ELF, x86 | Wi-Fi PHY microcode; x86 is implausible | NO GHIDRA LANGUAGE |

## 6. Where each processor family lives

- **ARM64 (AArch64)**: Windows kernel drivers (`.sys`), user-mode DLLs, TrustZone apps (`hdcp*.mbn`, `pr_3_wp.mbn`). Ghidra `AARCH64:LE:64:v8A`.
- **ARM64X / ARM64EC / CHPE**: GPU, NPU and video user-mode DLLs that serve both native and emulated x64/x86 apps.
- **Hexagon (QDSP6)**: ADSP image (`qcadsp8380.mbn`, Hexagon v73), CDSP image (`qccdsp8380.mbn`, v73), and the `.so` modules loaded into the DSPs (audio, sensors, NPU skels). Ghidra `Hexagon:LE:32:default`.
- **Xtensa**: the **Spectra camera ICP** firmware (`CAMERA_ICP.mbn`, `CAMERA_ICP_AAAAAA.elf`), the **Iris video** firmware (`qcvss8380*.mbn`) and the **EVA** firmware (`evass.mbn`). Ghidra `Xtensa:LE:32:default`.
- **ARM32**: Secure Processor (SPSS) apps in `qcsp8380` (`*.sig`) and the WCN7850 Wi-Fi firmware `wlanfw20.mbn`. Ghidra `ARM:LE:32:v8`.
- **x86 (32-bit)**: x86 and CHPE user-mode DLLs of the GPU/video stack for emulated apps.

## 7. REA self-test (2026-10-24)

`scripts/rea-selftest.py` loaded one sample per CPU family with the catalog's Ghidra language forced (`REA_GHIDRA_LANGUAGE_ID`), listed procedures with `rea search --kind procedures`, and decompiled three real procedures (first, middle, last). REA 6.7.0-surface.xtensa.1, Ghidra 12.1.4, `GHIDRA_MAXMEM=4G`, `REA_GHIDRA_STARTUP_TIMEOUT_MS=2400000`. Outputs stay in `out/rea-selftest/` (not in git).

| CPU | Sample | Procedures | Clean / decompiled | Verdict |
|:--|:--|--:|:--|:--|
| ARM64 (PE) | `acpials.sys` | 32 | 3 / 3 | works |
| ARM64X (PE) | `libQCNspDxCoreUMDdrv.dll` | 241 | 2 / 3 | works; one procedure at a section start (`0x180008000`) hits bad data |
| ARM64 (signed MBN, TrustZone app) | `hdcpsrm.mbn` | 156 | 2 / 3 | works; one procedure (`0x10b108`) hits bad data |
| x86 (PE) | `qcvidencx86um.DLL` | 243 | 3 / 3 | works |
| Hexagon v73 (CDSP image) | `qccdsp8380.mbn` | 9996 | 3 / 3 | works |
| Hexagon v73 (ADSP image, 22 MB) | `qcadsp8380.mbn` | 39649 | 3 / 3 | works (needs the larger heap and deadline) |
| Hexagon (small `.so` skel) | `libQ6MSFR_manager_skel_intermediate.so` | 0 | — | Ghidra found no procedures; use a larger module or seed functions from the dynamic symbol table |
| Xtensa (Spectra camera ICP) | `CAMERA_ICP.mbn` | 190 | 2 / 3 | works; one procedure (`0x5de28`) hits bad data |
| Xtensa (Iris video) | `qcvss8380.mbn` | 901 | 2 / 3 | works; one procedure (`0xd9c68`) hits bad data |
| ARM32 (SPSS app) | `asym1p.sig` | 1 | 0 / 1 | not usable as decoded: entry `0x18a004dd` is Thumb; set the Thumb context first |

Conclusions:

1. REA + Ghidra decode every CPU family present in the dumps: ARM64, ARM64X, x86, Hexagon v73 and Xtensa (including the Spectra ICP firmware).
2. Bad-instruction markers appear per **procedure**, not per file: a procedure that Ghidra placed on data or on a section boundary decodes to garbage while its neighbours are clean. Rule: **any procedure whose output contains a bad-instruction marker is discarded as evidence**, even when the rest of the file decodes cleanly.
3. A clean decode is necessary, not sufficient: x86 decoding of `phy_ucode20.elf` produced no markers although x86 is implausible for that file (see §5). Only the catalog decides the CPU.
