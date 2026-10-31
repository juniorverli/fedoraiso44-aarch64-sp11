# NPU integration plan for Fedora (2026-10-31)

Sources: `out/ref/ubuntu-surface-pro-11/NPU.md`, `install.sh`, `udev/`, `scripts/test_*.sh`; `dnf repoquery` and package file lists in the Fedora 44 aarch64 container (`registry.fedoraproject.org/fedora:44`); `sources/windows/DriverStore` (file names, hashes via `sources/binary-catalog.tsv`). Nothing was run on the device. Grades: Verified, Inference, Unknown.

## 1. Hard dependency

Everything below needs a working CDSP: `/dev/fastrpc-cdsp` exists only when the `fastrpcglink-apps-dsp` GLINK channel binds. On our image it does not (M13: `OPEN_ACK` timeout, `failed to create endpoint`, no CDSP node). The plan is blocked on `dsp-subsystems` E1/E2 ([denisix comparison](../../dsp-subsystems/evidence/2026-10-31-denisix-comparison.md)). Verified from M13 dmesg.

## 2. The stack the reference runs (Inference until reproduced; it is their report)

| Layer | Piece | Source | Open source? | Fedora 44 |
|:--|:--|:--|:--|:--|
| Kernel | `misc/fastrpc`, `qcom_q6v5_pas`, `qcom_glink_smem` | mainline 7.3 | yes | in our kernel. Their "GLINK framing" and `gpi` hacks are unpublished; not adopted |
| CDSP firmware | `qccdsp8380.mbn` + `cdsp_dtb.mbn` | Windows package `qcnspmcdm_ext_cdsp8380` | no (Microsoft-signed Qualcomm) | private image only (S5) |
| Host FastRPC | `libcdsprpc.so` with `remote_handle64_open`, `remote_session_control` | `github.com/qualcomm/fastrpc` (BSD-3-Clause) | yes | `fastrpc` 1.0.8-1.fc44 (`libcdsprpc.so.1`, `libadsprpc`, `libsdsprpc`), `fastrpc-devel`, `fastrpc-services` (`cdsprpcd`, `adsprpcd`, systemd units, udev). Verified by repoquery. They built `development` branch because Ubuntu's library lacked the two symbols; whether 1.0.8 exports them: Unknown (check `nm -D` in the image) |
| DSP shell + user libs | `fastrpc_shell_3`, `fastrpc_shell_unsigned_3`, `libc++.so.1`, `libsysmon*_skel.so`, `version.so` | Windows package, or `hexagon-dsp-binaries-qualcomm-hamoa-iot-evk` | binaries; licence `LicenseRef-Callaway-Redistributable-no-modification-permitted` for the Fedora package | Fedora package exists (20260916-2.fc44, shells stamped `c1-00094`, installs to `/usr/share/hexagon-dsp/x1e80100/Qualcomm/Hamoa-IoT-EVK/dsp/cdsp`, selected by machine name in `conf.d`, which does not list Surface). Must match the firmware branch (their NPU.md). For `c1-00046.1` firmware use the shells of the same Windows package |
| Hexagon libc/libgcc | `libc.so`, `libgcc.so` (v73 G0 pic) | Hexagon SDK `target/hexagon/lib/v73/G0/pic/` | proprietary SDK | user download only |
| HTP skel | `libQnnHtpV73Skel.so` / `libQnnHtpV73SkelDrv.so` | QAIRT `lib/hexagon-v73/unsigned/` (they use 2.48.0.260626); Windows has `qcnspmcdm8380/HTP/libQnnHtpV73SkelDrv.so` (Hexagon v73, 9.8 MB, catalog row exists) | no | user download or private from Windows; version coupling with the host `libQnnHtp.so` Unknown |
| Host QNN | `libQnnHtp.so`, `libQnnCpu.so`, `libQnnSystem.so`, converters | QAIRT SDK, `aarch64-ubuntu-gcc9.4` build | no, Qualcomm licence; the SDK terms require acceptance and must be treated as non-redistributable | user download only |
| App | llama.cpp `GGML_HEXAGON` backend: `libggml-hexagon.so` (host) + `libggml-htp-v73.so` (DSP side) | `github.com/ggml-org/llama.cpp` (MIT) | host side yes; DSP side needs the Hexagon cross compiler and QuRT headers from the Hexagon SDK (proprietary) | Fedora `llama-cpp` b6153-3.fc44 ships only `libggml`, `libggml-base`, `libggml-cpu` (verified by file list): no Hexagon backend. Build locally; the built `libggml-htp-v73.so` embeds SDK material, so it is not redistributed |
| Daemon | `cdsprpcd` | `fastrpc-services` | yes | yes; `60-fastrpc.rules` starts it on `fastrpc-cdsp`, group `fastrpc` mode 0640 (reference used 0666) |
| udev bring-up | `59-fastrpc-remoteproc.rules` writes `start` to offline cdsp/adsp | `fastrpc-services` | yes | Our early PAS already starts both; the rule only acts on `offline` |

Open and packageable now: `fastrpc`, `fastrpc-services`, `hexagon-dsp-binaries*` (as an optional comparison set), `qrtr`, `qrtr-libs`, `llama-cpp` (CPU only). Proprietary and user-provided: QAIRT SDK, Hexagon SDK pieces, the Qualcomm/Windows DSP binaries and CDSP firmware.

## 3. Image design

| Item | Decision |
|:--|:--|
| Public ISO | `fastrpc`, `fastrpc-services`, `qrtr`, `llama-cpp` (CPU). No QAIRT, no Hexagon SDK, no Windows files, no Hexagon-built ggml skel |
| Private image (`--private`) | adds CDSP firmware (already part of the firmware tree), optional Windows CDSP user libs under `/usr/lib/dsp/cdsp/` (from the same package as the firmware) |
| User step | `userspace/sp11-npu-install-private.sh`: takes the operator's own QAIRT zip or directory plus an optional Hexagon-SDK-built `libggml-htp-v73.so`; checks that the QAIRT tree has the v73 skel and an aarch64 host runtime and that shell and firmware builds match; installs under `/opt/sp11-npu` (not in any package); never downloads anything; asks for explicit licence acknowledgement flag |
| Device nodes | `/dev/fastrpc-cdsp` (+`-secure`), owner `root:fastrpc`; users of the NPU join group `fastrpc` (Fedora default). No 0666 rule (reference sets 0666: rejected, S-safety) |
| Services | `cdsprpcd.service` from `fastrpc-services` (udev-activated). No custom unit. `ADSP_LIBRARY_PATH=/usr/lib/dsp/cdsp:/opt/sp11-npu/lib/dsp` exported by `/etc/profile.d/sp11-npu.sh` written by the installer |
| CDSP reset | Reference stops and starts `remoteproc` before each 3B+ run (heap fragmentation) and warns of a `dma_buf_release` bad page crash and a cold-boot requirement. Not automated by us; the operator script prints it, nothing is written to `state` by the installer (the ADSP reset warning in SENSORS.md shows a wrong `state` write kills the SoC) |
| Fedora-native (D12) | use `fastrpc` library and units; do not install their custom `libcdsprpc.so` into `/usr/lib` |

## 4. Open questions

| # | Question | Grade | Answer from |
|:--|:--|:--|:--|
| N1 | Does `fastrpc` 1.0.8 export `remote_handle64_open` and `remote_session_control`? | Unknown | `nm -D` in the image build container |
| N2 | Does the Windows `libQnnHtpV73SkelDrv.so` run under the Linux QAIRT host runtime? | Unknown | device test after CDSP works |
| N3 | Do the Windows shells of `c1-00078` work with `c1-00078` firmware (Windows pairing) and the Hamoa-EVK `c1-00094` shells with either? | Unknown | device test |
| N4 | QAIRT licence text: redistribution and use | Unknown | operator reads the licence on download; we assume no redistribution |
| N5 | Thermal limits for NSP (`QCOM0CF8`, `QCOM0CC3`) | Unknown | power-thermal worker |

## 5. Asks

- **dsp-subsystems (self)**: E1/E2 first.
- **image**: add `fastrpc fastrpc-services qrtr` to the package set (public), `fastrpc` group; no udev 0666 rule; leave `/opt` empty; ship `userspace/sp11-npu-install-private.sh` in the private mode only.
- **kernel**: confirm the final config has `CONFIG_QCOM_FASTRPC` (or the Fedora module) and `CONFIG_DMABUF_HEAPS_SYSTEM` (FastRPC and `fastrpc-services` udev use the `dma_heap` system node). Not stated in `kernel/config/*.config`.
- **sources**: none now; if the operator wants the Hamoa shells comparison, `hexagon-dsp-binaries-qualcomm-hamoa-iot-evk` is a Fedora package, no pin needed.
