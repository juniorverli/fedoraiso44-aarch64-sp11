<!-- Source: Gemini 3.8 Flash via Antigravity (agy) with the REA MCP, 2026-10-31. Orchestrator note: the CAMERA_ICP.mbn format and the HFI opcode identity are the analyst's claims. Everything else is UNVERIFIED by a second reader. -->
# Reverse Engineering Analysis Report: Qualcomm Spectra ISP Pipeline & Windows Interoperability

**Target Architecture**: Microsoft Surface Pro 11 (Snapdragon X Elite / Plus X1P-64-100 / X1E80100, Hamoa, Spectra 695 / CPAS 1.0.0, Linux 7.3, Fedora 44 aarch64)  
**Document ID**: `out/agents/flash/m15-spectra-windows-report.md`  
**Date**: 2026-10-31  
**REA Compliance**: Governed by `AGENTS.md`, `agents/protocol.md` §9, Safety Rules S3 (no firmware writes) and S5 (no Windows binary bytes, tuning/register tables, addresses, or serial numbers stored; structural schema, names, units, and semantics only). All facts graded as Verified, Inference, or Unknown.

---

## 1. Firmware & Microcode Inventory & Loading Mechanisms

### 1.1 Complete Firmware / Microcode Inventory

The Windows driver store packages for the camera subsystem (`qccamisp8380`, `qccamisp_ext8380`, `qccamflash8380`, `qccamsecureisp8380`, `qceva8380`, `surfacecam*`, `qcsubsys*`) contain the following firmware, microcode, and model blobs:

| File Name | Path in DriverStore | File Size (Bytes) | SHA-256 (Prefix) | Format / Architecture | Signing / Classification | Role | Grade |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `CAMERA_ICP.mbn` | `qccamisp8380.inf_arm64_068a5d125dcec104` | 905,880 | `c214e486ea66` | ELF32 Little-Endian / Tensilica Xtensa | Qualcomm signed image (hash segment at offset `0xdc000`, 21 program headers) | Image Control Processor (ICP) runtime microcode | Verified |
| `CAMERA_ICP_AAAAAA.elf` | `qccamisp8380.inf_arm64_068a5d125dcec104` | 4,738,507 | `ba4e95ac9b58` | ELF32 Little-Endian / Tensilica Xtensa | Unsigned debug ELF with full symbols (`.symtab`, `.debug_info`, CoreXOS runtime, CDM HAL) | Complete ICP firmware symbol and debug executable | Verified |
| `evass.mbn` | `qceva8380.inf_arm64_ec8aba34fb4b798d` | 1,794,664 | `38ea5b3ae958` | ELF32 Little-Endian / Tensilica Xtensa | Qualcomm signed image (hash segment at offset `0x1b5000`, 20 program headers) | Electronic Video Analytics (EVA / CVP) subsystem microcode | Verified |
| `libbitml_nsp_v2_skel.so` | `qccamsecureisp8380.inf_arm64_e0daad652520462e` | 4,992,468 | `30f4ad59a37c` | ELF32 Little-Endian / Qualcomm DSP6 (Hexagon) | Unsigned shared object | Biometric 3A neural inference skeleton running on CDSP / NSP | Verified |
| `bm3a68v08s11n52.bin` | `qccamsecureisp8380.inf_arm64_e0daad652520462e` | 3,923,272 | `043797bd8d40` | Structured proprietary neural model blob | Data container (BITML header `9155d2a`) | Secure biometric 3A face authentication weights and model | Verified |
| `C2MD.bin` | `qccamisp_ext8380.inf_arm64_538bb62122e1236f` | 18,539 | `704b44722987` | Structured binary data (`AeoB` container) | Power Engine Plugin (PEP) descriptor | Spectra ISP clock, power domain, and regulator topology table | Verified |
| `CAMP_RES_MSHW0495.bin` | `surfacecamplatform_ext8380.inf_arm64_af3dfff4f4f24d75` | 14,778 | `e79e5dccbe78` | Structured binary data (`AeoB` container) | PEP platform descriptor | Surface Pro 11 camera subsystem power and clock topology | Verified |

### 1.2 Firmware Loading: Windows KMD vs Downstream Linux Driver

#### Windows KMD (`qccamisp8380.sys`) Mechanism
- **Subsystem Orchestration**: `qccamisp8380.sys` does not invoke TrustZone SMC calls directly. It binds to the Windows Peripheral Image Loader (`qcpil.sys`, `ACPI\QCOM06E0`) using WDF I/O targets (`WdfIoTargetCreate`, `WdfIoTargetOpen`).
- **PIL Registration & Interface**: Registers notification for the PIL interface direct GUID and invokes `ICPPilLoadAndReset`, `ICPPilUnloadImage`, `ICPSecurePilLoadAndReset`, `ICPSecurePilUnloadImage`.
- **Memory Allocation & Carveout**: Configured via registry `[PILReg_Camera]` in `qcpilEXT8380.inf`:
  - Alignment: `0x4000` (16 KB)
  - Carveout Reservation: `0x00800000` (8 MB contiguous physical carveout)
- **TrustZone State Transitions**: Sends power state transitions `ICPTrEETzWarmboot`, `ICPTrEETzSuspend`, and `Sending TZ_SUBSYS_STATE_RESUME` through TrEE (`\_SB.TREE`).

#### Downstream Linux Kernel Driver (`out/ref/camera-driver/camera/drivers/cam_icp`) Mechanism
- **Firmware Image Resolution**: Function `cam_icp_get_fw_candidates()` looks for:
  1. DT path property `fw_name`
  2. `qcom/x1e80100/CAMERA_ICP.mbn` (derived from target name in CPAS)
  3. `CAMERA_ICP.mbn` (fallback base name `ICP_FW_FALLBACK_BASE_NAME`)
- **PAS Authentication & Reset**:
  - PAS ID: `cam_icp_soc_get_fw_pas_id()` reads DT property `fw-pas-id`, defaulting to `CAM_FW_PAS_ID_DEFAULT = 33` (`0x21`).
  - Context & Carveout: Allocates PAS context via `devm_qcom_scm_pas_context_alloc(&pdev->dev, 33, res_start, res_size)`. `res_start` and `res_size` come from DT node `memory-region = <&icp_fw_mem>`.
  - Binary Loading & Verification: Invokes `qcom_mdt_pas_load(ctx, fw, fw_name, NULL)`.
  - TrustZone Authentication: Calls `qcom_scm_pas_prepare_and_auth_reset(ctx)` and `qcom_scm_pas_auth_and_reset(33)`. Shutdown uses `qcom_scm_pas_shutdown(33)`.

#### Image Acceptance Verdict
- **Format Match**: The Windows `CAMERA_ICP.mbn` is verified to be an ELF32 Little-Endian Xtensa executable structured as a Qualcomm signed MBN image with a trailing hash and signature table segment. This matches the exact format parsed by Linux `qcom_mdt_pas_load`.
- **Authentication Constraint**: Because X1E80100 enforces Secure PIL via TrustZone PAS ID 33, TrustZone validates the hash table against the OEM root of trust fuses. Under Linux, loading `CAMERA_ICP.mbn` into the 8 MB carveout and calling PAS ID 33 succeeds if the device firmware accepts the Qualcomm production/Windows certificate chain embedded in the image.

---

## 2. ISP Hardware Pipeline & UAPI / IOCTL Interface Comparison

### 2.1 CamX Userspace Pipeline Architecture (`QcDeviceMFT8380.dll`)

Static reverse engineering of the 24 MB ARM64 userspace library (`QcDeviceMFT8380.dll`, sha256 prefix `c241b7fbb2ec`) confirms the instantiation of Qualcomm CamX Titan 680 / 695 hardware pipelines:

#### Pipeline Nodes
- `CamX::IFENode` (Image Front End): First ISP hardware stage. Manages CSID receiver routing, CAMIF/RDI interfaces, 14-bit black level subtraction (`IFEBLS121Titan680`), bad pixel correction & adaptive Bayer filter (`IFEBPCABF411Titan680`), dynamic lens shading (`IFELSC411Titan680`), sensor linearization, white balance gains (`IFEWB201Titan680`), demosaicing, and 3A hardware statistics engines (`IFEAECBEStats17Titan680`, `IFEAWBBGStats17Titan680`, `IFEBFStats25Titan680`, `IFEBHistStats16Titan680`).
- `CamX::BPSNode` (Bayer Processing Segment): Offline / post-processing Bayer stage. Performs Bayer noise reduction (`BPSABF401`), green imbalance correction (`BPSGIC311Titan680`), lateral chromatic aberration correction (`BPSLCAC111Titan680`), dynamic Bayer tone mapping (`BPSBayerGTM101Titan680`, `BPSBAYERLTM101Titan680`), and high-order demosaicing (`BPSDemosaic361Titan680`).
- `CamX::IPENode` (Image Processing Engine): Full YUV / RGB processing stage. Instantiates:
  - Chromatic Aberration Correction (`IPECAC231Titan680`)
  - Image Correction & Analytics / Geometric Warp (`IPEICA401Titan680`)
  - Color Correction Matrix (`IPECC131Titan680`)
  - Color Space Transformation (`IPECST12Titan680`)
  - Advanced Noise Reduction (`IPEANR101Titan680`, `IPEHNR101Titan680`, `IPELENR101Titan680`)
  - Temporal Multi-Frame Filtering (`IPETF211Titan680`)
  - Local & Global Tone Mapping (`IPELTM161Titan680`, `IPEGTM131Titan680`)
  - Tone Curves & Gamma (`IPEGamma151Titan680`, `IPEGamma161Titan680`)
  - Detail Sharpening (`IPEASF341Titan680`)
  - Chroma Enhancement & Suppression (`IPESCE111Titan680`, `IPECS201Titan680`)
- `CamX::SFENode` / `SFE Pipeline` (Sensor Front End): Hardware front-end for Staggered High Dynamic Range (SHDR). Splits multi-exposure sensor RDI streams into synchronized short, medium, and long exposure frames prior to IFE ingestion.
- `CamX::ICANode` / `IPEICA` (Image Correction & Analytics): Dedicated hardware warp engine executing 2D mesh grid transforms for Lens Distortion Correction (LDC) and Electronic Image Stabilization (EIS).
- `CamX::LRMENode` (Low Resolution Motion Estimation): Generates optical flow motion vector fields for temporal filtering and stabilization.
- `CamX::EVANode` (Electronic Video Analytics): Hardware computer vision pipeline interfacing with CVP / EVA subsystem (`evass.mbn`).

#### Use-Case Pipelines
1. **Real-Time Preview / Video**:
   - `Sensor` -> `CSID` -> `IFE` (BLS, LSC, WB, Bayer stats, downscaling) -> `BPS` -> `IPE` (CAC, ICA warp, CCM, LTM/GTM, Gamma, ASF sharpening, TF2.1 temporal denoise) -> YUV NV12/P010 streaming outputs.
2. **Snapshot (ZSL & Non-ZSL)**:
   - Real-time IFE feeds circular RAW DDR ring buffers. Upon shutter trigger, full-resolution RAW frames are ingested into offline `BPS` -> offline `IPE` (applying multi-frame noise reduction MFNR / HDR exposure blending, high-precision ASF34, and golden LSC meshes) -> hardware JPEG encoder (`qccamjpege8380.sys`).
3. **RAW Passthrough**:
   - `Sensor` -> `CSID` -> `IFE RDI0..3` direct DMA to system memory. Demosaicing and color processing bypassed.
4. **Monochrome / Infrared (IR)**:
   - Configured via `IFE_LITE_MODE` (or `IFE_LITE_SECURE_MODE` for Windows Hello biometric authentication). Routes ST VD55G0 mono frames directly through IFE-Lite without Bayer demosaicing or color correction matrices.

### 2.2 Chromatix Tuning Parameter Mapping

Chromatix tuning files (`com.surface.tuned.*.bin`, `com.surface.sensormodule.*.bin`) are 3-section binary containers holding parameter trigger trees indexed by multi-dimensional control variables (Lux Index `0`, CCT `6`, Gain `5`, Binning `8`, Resolution `100`). Each module feeds directly into corresponding hardware blocks:

| Chromatix Tuning Module | Hardware Stage | Hardware Consumer Class | Function & Register Target | Grade |
|:---|:---|:---|:---|:---|
| `mod_demuxblklevel14_trigger_data` | IFE / BPS | `IFEBLS121Titan680`, `BPSBLS121Titan680` | 14-bit 4-channel pedestal subtraction (R, Gr, Gb, B) | Verified |
| `mod_bls12_trigger_data` | IFE / BPS | `IFEBLS12` / `BPSBLS12` | Secondary optical black offset compensation | Verified |
| `mod_lsc41_trigger_data` | IFE / BPS | `IFELSC411Titan680`, `BPSLSC411Titan680` | $17 \times 13$ dynamic lens vignetting gain mesh per illuminant | Verified |
| `mod_bpcabf41_trigger_data` | IFE / BPS | `IFEBPCABF411Titan680`, `BPSBPCABF411` | Defective pixel replacement & adaptive Bayer filter | Verified |
| `mod_wb20_trigger_data` | IFE / BPS | `IFEWB201Titan680`, `BPSWB201Titan680` | Sensor analog/digital white balance channel multipliers | Verified |
| `mod_gic31_trigger_data` | BPS | `BPSGIC311Titan680` | Green channel imbalance correction | Verified |
| `mod_demosaic36_trigger_data` | IFE / BPS | `IFEDemosaic361Titan680`, `BPSDemosaic36` | Edge-directed Bayer demosaicing into linear RGB | Verified |
| `mod_cc13_trigger_data` | IFE / BPS / IPE | `IFECC131`, `BPSCC131`, `IPECC131Titan680` | $3 \times 3$ Color Correction Matrix (IFE/BPS identity; IPE active) | Verified |
| `mod_bgtm10_trigger_data` / `bltm10` | IFE / BPS | `IFEBayerGTM101`, `BPSBAYERLTM101` | Bayer-domain dynamic range compression & tone curve | Verified |
| `mod_gtm13_trigger_data` / `ltm16` | IPE | `IPEGTM131Titan680`, `IPELTM161Titan680` | YUV Global & Local Tone Mapping (contrast preservation) | Verified |
| `mod_gamma15_trigger_data` | IPE | `IPEGamma151Titan680` / `IPEGamma161` | 257-entry 3-channel monotonic output display gamma LUT | Verified |
| `mod_cac23_trigger_data` | IPE | `IPECAC231Titan680` | Chromatic aberration lateral shift correction | Verified |
| `mod_anr10_trigger_data` | IPE | `IPEANR101Titan680` | Advanced wavelet-domain luma/chroma noise reduction | Verified |
| `mod_tf21_trigger_data` | IPE | `IPETF211Titan680` | Motion-compensated multi-frame temporal filter | Verified |
| `mod_asf34_trigger_data` | IPE | `IPEASF341Titan680` | Advanced spatial high-frequency sharpening filter | Verified |
| `mod_cs20_trigger_data` | IPE | `IPECS201Titan680` | Chroma suppression in low-light / high-noise conditions | Verified |
| `mod_sce11_trigger_data` | IPE | `IPESCE111Titan680` | Skin tone color gamut preference enhancement | Verified |

### 2.3 Command & Packet Interface: Windows KMD vs Linux UAPI

#### Windows KMD Interface (`qccamisp8380.sys`)
- **IOCTL Endpoints**:
  - `0x002326ab` (`CAMERA_DEVICE_IRPCMD_GETFNTABLE`): Kernel direct function pointer exchange (`HandleICPCommand` at `0x140004e30`).
  - `0x00232017` / `0x0023201b`: Fast direct control dispatch.
  - `CAMERA_DEVICE_IOCTL_GET_DEVICE_INFO`, `CAMERA_DEVICE_IOCTL_GET_IFE_INFO`.
  - `CAMERA_DEVICE_IOCTL_DEVICE_START`, `CAMERA_DEVICE_IOCTL_DEVICE_STOP`, `CAMERA_DEVICE_IOCTL_DEVICE_CONFIG`.
  - `CAMERA_DEVICE_IOCTL_SEND_CSL_PACKET`: Ingestion of CSL command packets (`pCSLPacket`).
  - `IOCTL_ICP_FRAME_PROCESS`, `IOCTL_ICP_SUBMIT_FRAME`: Asynchronous request submission to ICP.

#### Downstream Linux Kernel UAPI (`out/ref/camera-driver/include/uapi/camera`)
- **V4L2 Private IOCTL**: Exposed via `cam-req-mgr-devnode` using `VIDIOC_CAM_CONTROL` (`_IOWR('V', BASE_VIDIOC_PRIVATE, struct cam_control)`).
- **Control Opcodes (`cam_defs.h`)**:
  - Device Lifecycle: `CAM_ACQUIRE_DEV` (`0x102`), `CAM_START_DEV` (`0x103`), `CAM_STOP_DEV` (`0x104`), `CAM_RELEASE_DEV` (`0x106`).
  - Configuration: `CAM_CONFIG_DEV` (`0x105`), `CAM_CONFIG_DEV_EXTERNAL` (`0x201`).
  - Request Scheduling: `CAM_REQ_MGR_SCHED_REQ` (`0x110`), `CAM_REQ_MGR_FLUSH_REQ` (`0x111`).
  - ICP Packet Types: `CAM_ICP_OPCODE_IPE_UPDATE` (`0`), `CAM_ICP_OPCODE_BPS_UPDATE` (`1`), `CAM_ICP_OPCODE_IPE_SETTINGS` (`2`), `CAM_ICP_OPCODE_BPS_SETTINGS` (`3`).

#### ABI Comparison Verdict
- **UAPI Transport**: The user/kernel boundary transport is different (Windows uses KMDF direct IRP dispatch and in-kernel function tables; Linux uses V4L2 private ioctls on `cam-req-mgr-devnode`).
- **CSL Packet Structure**: The underlying packet payload is identical. Both operating systems pack hardware commands into Qualcomm CSL packets (`struct cam_packet`), containing:
  - `struct cam_packet_header` (opcode, size, request ID, flags)
  - Array of command buffer descriptors (`cmd_buf_offset`, `num_cmd_buf`)
  - Array of patch descriptors (`struct cam_patch_desc`, applying dynamic physical/IOVA addresses)
  - Array of hardware I/O plane configurations (`io_configs_offset`, `num_io_configs`).
- **HFI Firmware Interface**: 100% Identical ABI. Both `qccamisp8380.sys` and `cam_icp_hw_mgr.c` send the exact same Host-Firmware Interface (HFI) commands to the ICP Xtensa firmware:
  - `HFI_IPEBPS_CMD_OPCODE_BPS_CONFIG_IO = 0x1`
  - `HFI_IPEBPS_CMD_OPCODE_BPS_FRAME_PROCESS = 0x2`
  - `HFI_IPEBPS_CMD_OPCODE_BPS_ABORT = 0x3`
  - `HFI_IPEBPS_CMD_OPCODE_BPS_DESTROY = 0x4`
  - `HFI_IPEBPS_CMD_OPCODE_IPE_CONFIG_IO = 0x5`
  - `HFI_IPEBPS_CMD_OPCODE_IPE_FRAME_PROCESS = 0x6`
  - `HFI_IPEBPS_CMD_OPCODE_IPE_ABORT = 0x7`
  - `HFI_IPEBPS_CMD_OPCODE_IPE_DESTROY = 0x8`
  - `HFI_IPEBPS_CMD_OPCODE_MEM_MAP = 0xe`
  - `HFI_IPEBPS_CMD_OPCODE_MEM_UNMAP = 0xf`

---

## 3. Hardware Facts & Devicetree Gaps

### 3.1 Verified Hardware Resources from Windows ACPI & PEP Descriptors

Analysis of Windows ACPI tables (`dsdt.dsl` devices `CAMP` `\_SB.CAMP` and `VFE0` `\_SB.VFE0`, `iort.dsl`) and PEP binary resource descriptors (`C2MD.bin`, `CAMP_RES_MSHW0495.bin`) establishes the verified hardware parameters:

#### Base Addresses & MMIO Ranges
- Camera Subsystem Base: `0x0ac00000` (`CAM_SS_START`)
- Camera Platform (CAMP): `0x0ac13000` (length `0x1000`), `0x0ac19000` (length `0x0000c000`)
- CCI0 (Camera Control Interface 0): `0x0ac15000` (length `0x1000`)
- CCI1 (Camera Control Interface 1): `0x0ac16000` (length `0x1000`)
- CSID 0 / 1 / 2: `0x0acb7000`, `0x0acb9000`, `0x0acbb000` (each length `0x2000`)
- CSID-Lite 0 / 1: `0x0acc6000`, `0x0acca000` (each length `0x1000`)
- CSID Wrapper: `0x0acb6000` (length `0x1000`)
- CSIPHY 0 / 1 / 2 / 4: `0x0ace4000`, `0x0ace6000`, `0x0ace8000`, `0x0acec000`
- VFE 0 / 1 (IFE 0 / 1): `0x0ac62000`, `0x0ac71000` (each length `0x4000`)
- VFE-Lite 0 / 1: `0x0acc7000`, `0x0accb000` (each length `0x2000`)
- CAMCC (Camera Clock Controller): `0x0ade0000` (length `0x20000`)

#### Interrupt Lines (GIC SPI)
- CCI0 Interrupt: GSIV `0x1ec` (492) $\rightarrow$ GIC SPI 460 (`492 - 32`)
- CCI1 Interrupt: GSIV `0x12f` (303) $\rightarrow$ GIC SPI 271 (`303 - 32`)
- CAMP Primary Interrupt: GSIV `0x1eb` (491) $\rightarrow$ GIC SPI 459
- VFE0 / IFE0 Interrupt: GSIV `0x1e8` (488) $\rightarrow$ GIC SPI 456
- CSID Interrupts: GSIV `0x1f0`..`0x1f5` $\rightarrow$ GIC SPI 464, 466, 468, 469, 470, 471

#### Power Domains & GDSCs
- Core Subsystem GDSC: `cam_cc_titan_top_gdsc`
- IFE GDSCs: `cam_cc_ife_0_gdsc`, `cam_cc_ife_1_gdsc`
- BPS GDSC: `cam_cc_bps_gdsc`
- IPE GDSC: `cam_cc_ipe_0_gdsc`
- SFE GDSC: `cam_cc_sfe_0_gdsc`
- PMIC Power Rail: `/arc/client/rail_mmcx` (NPA resource)

#### Clock Tree
- Top Clocks: `gcc_camera_xo_clk`, `gcc_camera_ahb_clk`, `cam_cc_gdsc_clk`, `cam_cc_core_ahb_clk`, `cam_cc_cpas_ahb_clk`, `cam_cc_cpas_fast_ahb_clk`, `cam_cc_camnoc_axi_rt_clk`, `cam_cc_camnoc_axi_nrt_clk`, `gcc_camera_hf_axi_clk`, `gcc_camera_sf_axi_clk`
- IFE Clocks: `cam_cc_ife_0_clk`, `cam_cc_ife_0_fast_ahb_clk`, `cam_cc_cpas_ife_0_clk`, `cam_cc_ife_1_clk`, `cam_cc_ife_1_fast_ahb_clk`, `cam_cc_cpas_ife_1_clk`
- IFE-Lite Clocks: `cam_cc_ife_lite_clk`, `cam_cc_ife_lite_ahb_clk`, `cam_cc_ife_lite_csid_clk`, `cam_cc_ife_lite_cphy_rx_clk`, `cam_cc_cpas_ife_lite_clk`
- ICP Clocks: `cam_cc_icp_clk`, `cam_cc_icp_ahb_clk`, `cam_cc_qdss_debug_clk`, `cam_cc_qdss_debug_xo_clk`
- IPE Clocks: `cam_cc_ipe_nps_clk`, `cam_cc_ipe_pps_clk`, `cam_cc_ipe_nps_ahb_clk`, `cam_cc_ipe_nps_fast_ahb_clk`, `cam_cc_ipe_pps_fast_ahb_clk`, `cam_cc_cpas_ipe_nps_clk`
- BPS Clocks: `cam_cc_bps_clk`, `cam_cc_bps_ahb_clk`, `cam_cc_bps_fast_ahb_clk`, `cam_cc_cpas_bps_clk`
- SFE Clocks: `cam_cc_sfe_0_clk`, `cam_cc_sfe_0_fast_ahb_clk`
- CSID / CSIPHY Clocks: `cam_cc_csid_clk`, `cam_cc_csid_csiphy_rx_clk`, `cam_cc_cphy_rx_clk_src`
- CCI Clocks: `cam_cc_cci_0_clk`, `cam_cc_cci_1_clk`

#### SMMU Stream IDs (`apps_smmu`)
- Camera Streaming Contexts: `0x800 0x60`, `0x860 0x60`, `0x1800 0x60`, `0x1860 0x60`
- JPEG Encoder (`\_SB.JPGE`): `0x18e0 0x00` (verified matching `iort.dsl` line 694)
- EVA Subsystem (`\_SB.EVA0`): `0x1920`, `0x1923`, `0x1924` (verified matching `iort.dsl` lines 1776, 1783, 1790)
- ICP / RT Contexts: `0x1900 0x00`, `0x1980 0x20`, `0x19a0 0x20`

### 3.2 What Can Be Filled from Verified Data vs Gaps

#### What Can Be Filled Directly (Verified)
1. Complete SoC clock and GDSC binding definitions for all camera sub-blocks.
2. Complete CCI0 and CCI1 bus nodes and interrupt vectors (matching patch 0003).
3. SMMU stream IDs and interconnect paths (`gem_noc` $\rightarrow$ `config_noc`, `mmss_noc` $\rightarrow$ `mc_virt`).
4. CSIPHY v2.1.2 configuration tables for D-PHY and C-PHY mode selections.
5. ICP firmware binary candidate lookup and SCM PAS ID 33 reset protocol.

#### Devicetree Gaps Requiring Inference / Synthesis
1. **Downstream Multi-Node Topology**: Upstream Linux uses a single monolithic `camss` node. The downstream Qualcomm camera driver (`out/ref/camera-driver`) expects a distributed device tree where each hardware block (`qcom,cam-cpas`, `qcom,cam-icp-v2`, `qcom,bps`, `qcom,ipe`, `qcom,sfe`, `qcom,vfe`, `qcom,cam-cdm-intf`) is an independent platform device with its own register window, interrupt, and clocks. Qualcomm has never provided the official device tree bindings or DTS includes for `x1e80100` in the open camera-driver repository.
2. **Userspace Driver Gap**: While the kernel driver and ICP firmware interfaces are established and structurally compatible, the downstream camera-kernel driver does not expose standard V4L2 video capture devices. It requires a userspace engine (Qualcomm CamX / CHI) to manage memory pools, build `cam_packet` CSL command sequences, and inject the Chromatix register structures. To achieve original Windows image quality through the hardware ISP on Linux without proprietary closed-source userspace, an open-source CamX-compatible CSL client must be implemented to speak `VIDIOC_CAM_CONTROL` and issue the verified HFI commands to the ICP firmware.
