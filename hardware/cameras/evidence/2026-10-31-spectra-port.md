# Cameras: native Spectra port, stage 1 (kernel side, offline)

Date: 2026-10-31. Offline work only: no device access, no REA call, no full kernel build, no commit.
Grades follow `agents/protocol.md` §5: **Verified** (read from data/code or produced by a command that is
named), **Inference** (reasoning given), **Unknown**. Safety: S2 untouched (no flash/IR node anywhere), S5 kept
(Windows firmware named by file and hash prefix only; Qualcomm's own Linux packages stay in `out/ref/`, not git).

This file replaces the conclusion of `2026-10-30-camera-driver-reference.md` that the Spectra stack is "not usable
on Linux". That conclusion was about shipping a Fedora-native camera; the operator asked for the Spectra path to be
built for real, and the evidence below shows it is much closer than that file assumed: the downstream driver
compiles and links against v7.3 unmodified, Qualcomm publishes the hamoa devicetree, the hamoa userspace and the
ICP firmware, and every ISP interrupt in the Surface ACPI matches Qualcomm's devicetree.

## 1. Inputs (all pinned, none in git)

| Input | Identity | Where |
|:--|:--|:--|
| Downstream driver | `qualcomm-linux/camera-driver` `08171dd` (branch `camera-kernel.qclinux.0.0`), GPL-2.0-only. Same source as `qualcomm-linux/pkg-camx-dkms` (a newer snapshot, 42 files differ in `camera/`, `common/cam_compat.h`; `SUPPORTED_TARGETS` includes `x1e80100`, `BUILD_EXCLUSIVE_KERNEL_MIN="6.16"`) | `out/ref/camera-driver` |
| Kernel | `sources/linux` v7.3 + all 69 patches of `kernel/series` (worktree `out/linux/spectra`, branch `w/spectra`, `UTS_RELEASE 7.3.0-00069-g53433f4a03bb`) | `out/linux/spectra` |
| Config | `defconfig` + `kernel/config/sp11.config` + `dev.config` (BTF and BTF_MODULES `=y`, checked in `.config`) | `out/build/dev-spectra` |
| Qualcomm hamoa camera DT | `qualcomm-linux/kernel` branch `qcom-next` `17bbb4b37bbc4fc5827b4667445a0c43967c0f48`, BSD-3-Clause: `hamoa-camera.dtsi` (sha256 `d44c9f6f`), `hamoa-camera-regulators.dtsi` (`11220caa`), `hamoa-camera-sensor.dtsi` (`77ae4e6a`), `hamoa-evk-camx.dtso` (`127738b1`), `hamoa-camx-el2.dtso` (`74fcee53`) | `out/ref/qcl-hamoa-camx-dts` |
| Qualcomm prebuilt firmware | `camxfirmware_1.0.27_arm64.tar.gz` sha256 `1f054c47...`, from `qartifactory-edge.qualcomm.com/.../camx.qclinux.0.0/261026/prebuilt_resolute/` (anonymous download), licence `Qualcomm-Nologin-Binaries` | `out/ref/qcl-camx-prebuilt` |
| Qualcomm prebuilt userspace | `camx-hamoa_1.0.56_arm64.tar.gz` sha256 `b6627f33...` (242 MB), `camx-headers_1.1.1_arm64.tar.gz` sha256 `30cb702b...` | `out/ref/qcl-camx-prebuilt` |
| Surface Windows data | `sources/windows/DriverStore/qccamisp8380.inf_arm64_068a5d125dcec104/`, ACPI `dsdt.dsl` (`CAMP` 62436, `QCOM0C98` 62604, `QCOM0C33` 62717, `QCOM0C25` 62757, `QCOM0CCC` 62897) | read only |

## 2. Inventory of the downstream driver (task 1)

### 2.1 Build structure (Verified: `Kbuild`, `Makefile`, `config/x1e80100-camera.mk`)

- 1059 `.c/.h` files; `Kbuild` builds **one module per SoC**, not nine: `camera_x1e80100.ko` (`obj-m += camera_$(CAMERA_ARCH).o`).
  The names in the operator brief (cam_core, cam_cpas, cam_req_mgr, cam_smmu, cam_sync, cam_utils, cam_isp,
  cam_icp, cam_sensor_module, cam_jpeg) are source directories linked into that one object; `camera_main.c` registers
  every sub-driver from one `module_init`.
- `config/x1e80100-camera.mk` sets `CONFIG_SPECTRA_ISP/SFE/ICP/JPEG/SENSOR/SENSOR_SYSFS_UTIL`, `CONFIG_ENABLE_US_API`
  and `CONFIG_X1E80100`. **Not** enabled for this SoC: FD, LRME, CRE, OPE, TFE, custom. The Kbuild adds
  `-Wmissing-prototypes -Werror`.
- The Makefile wrapper passes `CAMERA_KERNEL_ROOT`, `KERNEL_ROOT`, and generates `cam_generated_h` (included by
  `camera_main.c:66`). Kbuild is read instead of the Makefile for `M=` builds, hence the two Kbuild patches in §4.
- Size by block (lines of `.c/.h`): cam_isp 184.6k, cam_sensor_module 61.0k, cam_cpas 41.1k, cam_icp 20.9k,
  cam_req_mgr 13.2k, cam_cdm 9.4k, cam_jpeg 7.5k, cam_utils 7.7k, cam_sync 6.7k, cam_smmu 6.4k, cam_core 6.0k,
  `common/` 6.7k, UAPI headers 8.2k.
- The module is already written for mainline: `common/cam_compat.[ch]` carries **28 `LINUX_VERSION_CODE` guards up
  to 7.3** (GPIO legacy API removal in 7.1, `gpiod_set_raw_value_cansleep` from 7.3, `of_gpio.h` removal,
  `MODULE_IMPORT_NS("DMA_BUF")`, the new `qcom_pas_*` API with `__symbol_get` fallbacks to `qcom_scm_pas_*`).

### 2.2 What each part needs from the kernel (Verified: `nm -u` of the objects, resolved against the tree)

| Part | Kernel APIs used | In v7.3 + our config |
|:--|:--|:--|
| cam_utils/cam_soc_util | clk, regulator, pinctrl, `dev_pm_domain_attach_by_id`, `dev_pm_genpd_set_performance_state`, OPP (`devm_pm_opp_set_config`, `dev_pm_opp_set_rate`), GPIO legacy (`gpio_request_one`, `gpio_to_desc`) | present; needs `CONFIG_GPIOLIB_LEGACY=y` (set in the dev config, **confirm in the Fedora release config**) |
| cam_cpas, `common/cam_soc_icc.c` | interconnect (`of_icc_get`, `icc_set_bw`), genpd + OPP + `required-opps` on `rpmhpd`, LLCC (`llcc_slice_*`), SMEM (`qcom_smem_get`) | present (`INTERCONNECT_QCOM_X1E80100=y`, `QCOM_RPMHPD=y`, `QCOM_LLCC=m`, `QCOM_SMEM=y`) |
| cam_smmu | `iommu_attach_device`, `iommu_get_domain_for_dev`, `iommu_map/unmap/map_sg`, `iommu_set_fault_handler`, dma-buf attach/map | present; `cam_smmu_util_iommu_custom()` is an empty stub in `cam_compat.c:494` (see §3.3) |
| cam_req_mgr, cam_sync | `dma_buf_export` (own allocator `cmm_alloc_buffer`, `CONFIG_ENABLE_US_API`), `dma_fence_*`, `sync_file_*`, V4L2 (`video_register_device`, `v4l2_subdev`), media controller | present; `dma_heap_find()` is **not exported** in v7.3 and `DMABUF_ALLOC_FIND_KERNEL_API` is correctly undefined, so the driver's own allocator is used (no `qcom,*` heaps needed) |
| cam_icp | `qcom_pas_*` (`devm_qcom_pas_context_alloc`, `prepare_and_auth_reset`, `shutdown`, `set_remote_state`), `qcom_mdt_get_size`, `request_firmware`, `iommu_map` | present (`QCOM_PAS=y`, `QCOM_SCM=y`, `QCOM_MDT_LOADER=m`) |
| cam_sensor_module | own CCI driver (not `i2c-qcom-cci`), `i2c_transfer`, `spi_sync`, GPIO legacy + `gpiochip_dup_line_label` (cam_res_mgr), LED triggers (flash) | present |
| cam_isp, cam_cdm, cam_jpeg | `devm_request_irq`, ioremap, clocks via cam_soc_util | present |
| tracing | module trace events: `bpf_trace_run2..7`, `trace_event_*`, `perf_trace_*` | present with BTF/BPF events on |

Downstream-only headers are all behind guards that are off here: `soc/qcom/secure_buffer.h`, `minidump.h`,
`cx_ipeak.h`, `crm.h`, `linux/msm-bus.h`, `msm_mmrm.h`, `qcom_tui_heap.h`, `qcom-dma-mapping.h`,
`msm_dma_iommu_mapping.h`. No `ion`, no `msm_drm` dependency.

### 2.3 Userspace ABI (Verified: `camera/include/uapi/camera/media/*.h`, 8186 lines)

Everything goes through `VIDIOC_CAM_CONTROL = _IOWR('V', BASE_VIDIOC_PRIVATE, struct cam_control)`
(`cam_defs.h:117`) on nodes registered with `video_register_device`/V4L2 subdev; `struct cam_control` carries
`op_code`, `size`, `handle_type`, `handle` (a user pointer). Two more ioctls: `CAM_PRIVATE_IOCTL_CMD =
_IOWR('V', BASE_VIDIOC_PRIVATE, struct cam_private_ioctl_arg)` on `cam-sync` (ops `CAM_SYNC_CREATE/DESTROY/SIGNAL/
MERGE/REGISTER_PAYLOAD/DEREGISTER_PAYLOAD/WAIT`, `cam_sync.h:431-440`) and `VIDIOC_CAM_CCI_CONTROL =
_IOWR('V', BASE_VIDIOC_PRIVATE + 23, struct cam_cci_ctrl)` (`cam_sensor.h:1287`).

| Layer | Op codes (the `op_code` of `cam_control`) |
|:--|:--|
| Common, every device node | `CAM_QUERY_CAP`, `CAM_ACQUIRE_DEV`, `CAM_START_DEV`, `CAM_STOP_DEV`, `CAM_CONFIG_DEV`, `CAM_RELEASE_DEV`, `CAM_FLUSH_REQ` (`CAM_COMMON_OPCODE_BASE + 1..8`) |
| Request manager node `cam-req-mgr-devnode` | `CAM_REQ_MGR_CREATE_DEV_NODES`, `CREATE_SESSION`, `DESTROY_SESSION`, `LINK`, `UNLINK`, `SCHED_REQ`, `FLUSH_REQ`, `SYNC_MODE`, `ALLOC_BUF`, `MAP_BUF`, `RELEASE_BUF`, `CACHE_OPS`, `LINK_CONTROL`, `REQUEST_DUMP`, `LINK_PROPERTIES`, `MEM_CPU_ACCESS_OP`, `QUERY_CAP` (`CAM_COMMON_OPCODE_MAX + 1..21`, `cam_req_mgr.h:366-386`) |
| Packet (CONFIG_DEV payload) | `struct cam_packet` + `cam_cmd_buf_desc` (command buffers, `cam_defs.h` `CAM_CMD_BUF_*`), `cam_buf_io_cfg` (output buffers, fences), `cam_patch_desc` (IOVA patching); ISP opcodes `CAM_ISP_PACKET_INIT_DEV=1`, `UPDATE_DEV=2`; ICP opcodes `CAM_ICP_OPCODE_IPE_UPDATE/BPS_UPDATE/IPE_SETTINGS/BPS_SETTINGS/OFE_*`; sensor opcodes `CAM_SENSOR_PACKET_OPCODE_SENSOR_STREAMON/UPDATE/INITIAL_CONFIG/PROBE/CONFIG/STREAMOFF/READ/PROBE_V2/...` |
| ISP blobs inside command buffers | `CAM_ISP_GENERIC_BLOB_TYPE_*` 0..34 (HFR, clock, bandwidth, UBWC, CSID clock, FE, IFE core, VFE out, SFE core/out/..., IRQ comp, FCG) |
| ISP resources | `CAM_ISP_IFE_OUT_RES_*` (FULL, DS4, DS16, RAW_DUMP, FD, PDAF, RDI_0..11, statistics BE/BHIST/BG/BF/AWB/..., 2PD, LCR, IR ...), `CAM_ISP_SFE_*` |
| ICP | device types `CAM_ICP_DEV_TYPE_ICP/IPE/BPS/IPE_CDM/BPS_CDM/OFE`; blobs `CAM_ICP_CMD_GENERIC_BLOB_CLK/CFG_IO/FW_MEM_MAP/FW_MEM_UNMAP/CLK_V2` (`cam_icp.h:93-101`) |
| Sensor node | `CAM_SENSOR_PROBE_CMD`, cmd types `CAMERA_SENSOR_CMD_TYPE_PROBE/PWR_UP/PWR_DOWN/I2C_INFO/I2C_RNDM_WR/RD/I2C_CONT_WR/RD/WAIT/RES_INFO/...` |
| CDM (inside command buffers) | `CAM_CDM_CMD_DMI, REG_CONT, REG_RANDOM, BUFF_INDIRECT, GEN_IRQ, WAIT_EVENT, CHANGE_BASE, PERF_CTRL, DMI_32/64, COMP_WAIT, NB_WAIT, NB_WAIT_GEN_IRQ` (`cam_cdm_util.h:17-36`) |

Reading the ABI: the **kernel builds most of the register programming itself** (`cam_isp_packet_parser`, hw managers
generate the CDM streams); userspace supplies packets with blobs, IO configs and fences. A sensor-less RDI/TPG
capture therefore needs no CamX: a small own tool using these headers can drive it (stage 1a).

### 2.4 Missing or different in mainline v7.3 (Verified: build + symbol check, §3)

| Downstream expectation | v7.3 | Effect |
|:--|:--|:--|
| QC dma-heaps (`dma_heap_find("qcom,camera")`, `mem_buf_lend`) | not exported | driver falls back to its own allocator by design |
| `soc/qcom/crm.h` (CRM/CESTA), `cx_ipeak`, MMRM, `msm-bus`, minidump | absent | guarded off; not used by Spectra 695 (CESTA is a newer-SoC feature) |
| Custom IOVA layout (`iova-region-discard`, `cam_smmu_util_iommu_custom`) | no equivalent | stub; the driver uses its own genalloc IOVA pool through `iommu_map`; runtime risk, see §3.3 |
| `qcom_scm_pas_*` | replaced by `qcom_pas_*` in 7.x | driver supports both |
| Legacy GPIO numbers | needs `GPIOLIB_LEGACY`; 7.0+ `CONFIG_GPIO_SHARED` can make the first `gpio_request_one` return `-EBUSY` | already worked around in `cam_compat.h:130-185` |

## 3. Build results (task 2)

### 3.1 What was built (Verified; commands in `spectra/scripts/`)

`prep-tree.sh tree|config|driver`, then `build-spectra.sh plain` (container `sp11-kernel-fc44`, gcc 16.2.1, under
the kernel build lock). Scratch tree `out/linux/spectra` = v7.3 + all 69 patches (three of them have no `From:`
header and are applied with `git apply`, see script header).

- **CAMERA_ARCH=x1e80100: all 149 objects compile with `-Wmissing-prototypes -Werror` and no warning, `camera_x1e80100.o`
  links, modpost passes strictly (no `KBUILD_MODPOST_WARN`), `camera_x1e80100.ko` is produced** (38.7 MB with
  DWARF; text 2.3 MB, data 0.9 MB, bss 1.5 MB). 236 OF aliases, among them `qcom,cam-cpas`, `qcom,csid695`,
  `qcom,vfe680`, `qcom,sfe680`, `qcom,cam-bps680`, `qcom,cam-ipe680`, `qcom,cam-icp_v2`, `qcom,csiphy`,
  `qcom,msm-cam-smmu`, `qcom,camera_x1e80100`. Logs: `out/build/spectra-build.log`, `spectra-build-final.log`.
- The scratch config is the project config (BTF, BTF_MODULES, PAS, SCM, SMMU, interconnect all on). BTF for the
  module itself was skipped ("vmlinux unavailable"): it needs a real vmlinux and will happen in a normal kernel build.
- **Undefined symbols**: 389 in the object; every one is exported by the v7.3 tree (`EXPORT_SYMBOL*`,
  `bpf_trace_run<N>` by macro) or by `__this_module`. The Module.symvers used for modpost was borrowed from an earlier
  dev build of the same series (`out/build/dev-touch-pen/Module.symvers`, a kernel without tracing); the 17 symbols
  that borrowed list lacks (trace/BPF events, `__dynamic_pr_debug`, `tracepoint_srcu`) were each proven exported
  and listed in `out/build/dev-spectra/extra.symvers` by `prep-tree.sh symvers`. Residual caveat: the symbol
  *CRCs* are not checked (no `MODVERSIONS`), and ABI agreement with the final kernel is confirmed only by building
  against that kernel's own Module.symvers.

### 3.2 Error classes

| Class | Result for the x1e80100 set | Where else |
|:--|:--|:--|
| API drift fixes needed | **none**: Qualcomm already carries the compat for 7.0 to 7.3 | |
| Missing downstream-only symbols | **none** at compile or link | guarded headers listed in §2.2 |
| Bigger design gaps | none at build time; runtime gaps in §3.3 | |
| Build-system | `Kbuild` needs `CAMERA_KERNEL_ROOT`, `KERNEL_ROOT`, `cam_generated_h` from the wrapper Makefile; `-Werror` is unconditional | fixed by the two patches in §4 |
| Blocks outside `CONFIG_X1E80100` (experiment with `extra-blocks.mk`) | **cam_lrme, cam_ope, TFE compile; cam_fd, cam_cre, cam_cust do not**: `cam_fd_dev.c` `cam_subdev_probe` called with 2 of 4 arguments, `cam_fd_hw_mgr.c:166` pointer-to-pointer, `cam_cre_dev.c:250` `.remove` returns `int` (needs `void` since 6.11), `cre_bus_rd.c:201` void expression, `cre_core.c:25` missing `cre_bus_wr.h`, `cre_bus_wr.c:554` misleading indentation, 11 missing prototypes in fd/cre/custom | bitrot of unmaintained blocks; not needed for Spectra 695 (Qualcomm itself leaves them off), **not patched** |

Log of the extra-blocks run: `out/build/spectra-build-extra.log` (27 error lines).

### 3.3 Runtime risks that compiling cannot settle (Unknown until the device runs it)

1. **Mutual exclusion with upstream CAMSS and CCI.** Both stacks claim the same CSID/VFE/CSIPHY/CCI registers,
   IRQs, clocks and GDSCs. Qualcomm's own overlay sets `&camss { status = "disabled"; }`; our DT must also disable
   `cci0/cci1` (patch 0003 nodes). One stack per boot, selected by the DTB variant.
2. **SMMU model.** `cam_smmu` attaches its own context banks (`qcom,msm-cam-smmu-cb`, streams `0x800/0x820/0x840/0x860`
   IFE+SFE, `0x18A0` CDM, `0x1800..0x19A0` ICP, `0x18E0` JPEG) with `iommu_attach_device()` on the default domain
   and maps at its own IOVAs. Untested against mainline's `arm-smmu-qcom` with `iommu.passthrough` and the default
   DMA domain. Mitigation: boot test first with TPG only.
3. **ICP firmware path.** DT `icp_use_pil` selects the secure path (`.mbn` through `qcom_pas_*`, PAS id 33 by default,
   `fw-pas-id` overrides, TZ authenticates). Without that property `cam_icp_hw_mgr.c:4013` takes the **non-secure
   path**: `request_firmware("...CAMERA_ICP.elf")`, `cam_icp_validate_fw(EM_XTENSA)`, `cam_icp_program_fw` copies the
   PT_LOAD segments into the firmware buffer and the driver boots the Xtensa core through the ICP CSR block (no TZ).
   Whether TZ on the Surface accepts PAS id 33, and whether XPU protection lets the non-secure path write the ICP
   CSRs, is Unknown. EL2 case: `hamoa-camx-el2.dtso` adds `camera-firmware { iommus = <&apps_smmu 0x1901 0x0>; }`.
4. **`camera_mem`**: ICP and firmware use `memory-region = <&camera_mem>`; upstream `hamoa.dtsi:608` has
   `camera@8e100000` 8 MB `no-map`. Whether the Surface firmware keeps that range free is Unknown.
5. **`cam_rpmh` region** `0xbbf0000+0x1F00` (CPAS third `reg`) is not described by any node of our tree; no overlap
   found, but not proven free. Inference only.
6. **LLCC**: `llcc_slice_getd` is called by CPAS when the DT asks for slices; whether the v7.3 table for X1E80100 has
   the camera slice is Unknown.
7. Module BTF and the out-of-tree flow: the kernel build must produce `camera_x1e80100.ko` after vmlinux
   (kernel worker request R-S1).

## 4. Patches against camera-driver (`spectra/patches/`)

Both are `git format-patch` against `08171dd`, `Assisted-by: Claude Sonnet 5.5`, no `Signed-off-by`, original
authors and licence headers untouched. Tested: a clean clone with both patches builds with only `M=` and
`CAMERA_ARCH=x1e80100` (no wrapper variables), 149 objects, `.ko` linked.

| Patch | Content |
|:--|:--|
| `0001-Kbuild-default-the-out-of-tree-root-variables-and-cr.patch` | `CAMERA_KERNEL_ROOT ?= $(abspath $(src))`, `KERNEL_ROOT ?= $(abspath $(srctree))`, create `cam_generated_h` from Kbuild when missing; the Makefile flow is unchanged |
| `0002-Kbuild-allow-building-without-Werror-CAMERA_WERROR-0.patch` | `-Werror` only when `CAMERA_WERROR` is not `0` (default unchanged) |

No source patch was needed: there was no compile or link error to fix (§3.2).

## 5. Devicetree (task 3)

### 5.1 Where it is (Verified)

Not in `qualcomm-linux/camera-driver` and not in the `quic`/`codelinaro` orgs (checked by GitHub API: `quic` has 41
repos, `codelinaro` 75, none camera-related). It is in **`qualcomm-linux/kernel`, branch `qcom-next`**, as overlay
sources: `arch/arm64/boot/dts/qcom/hamoa-camera.dtsi` (2477 lines), `hamoa-camera-regulators.dtsi`,
`hamoa-camera-sensor.dtsi` (EVK IMX577/OG0A1B/OV08X sensors), `hamoa-evk-camx.dtso`, `purwa-evk-camx.dtso` (X1P42100),
`hamoa-camx-el2.dtso`, listed in `qualcomm-linux/qcom-dtb-metadata` `qcom-next-fitimage.its`
(`fdt-hamoa-evk-camx.dtbo`, `fdt-hamoa-camx-el2.dtbo`). Raw URL pattern
`https://raw.githubusercontent.com/qualcomm-linux/kernel/qcom-next/arch/arm64/boot/dts/qcom/<name>`.
Also `qualcomm-linux/kernel-topics` branch `tech/mm/camss` carries Qualcomm's FROMLIST upstream work (C-PHY PHY driver,
PHY-API CAMSS, ISP params UAPI, **CAMSS OPE driver**, X1P42100, Glymur/Kaanapali/SM8750/Nord CAMSS): the upstream
direction for the offline engines.

### 5.2 Checked against our tree (Verified: `scripts/check-downstream-dt.sh`)

The Denali DTS, plus `hamoa-camera-regulators.dtsi` and `hamoa-camera.dtsi` (and with `hamoa-camera-sensor.dtsi`),
with `&camss` disabled, **compiles with dtc on v7.3 + series with no missing label** (every `CAM_CC_*`, `GCC_CAMERA_*`,
interconnect, `rpmhpd_opp_*`, `camera_mem`, `apps_smmu` reference resolves). Only `dt-bindings/camera/msm-camera.h`
comes from the driver tree (`camera/dt-bindings/msm-camera.h`). The compiled test DTB holds 24 `qcom,cam*` nodes.
This proves the node set fits our DT; it does not prove the driver probes (§3.3).

### 5.3 Downstream nodes against ACPI and our data (Verified by the arithmetic: ACPI GSIV minus 32 = SPI)

Every interrupt of the Surface camera devices is in Qualcomm's hamoa DT (`QCOM0C32` CPAS/CCI: 459, 460, 271;
`QCOM0C98` CSIPHY: 477, 478, 479, 122; `QCOM0C33` JPEG: 474, 475; `QCOM0C25` ISP: 456, 287, 463, 464, 465, 466, 467, 468,
469, 689, 764, 765; `QCOM0CCC` SecureISP: 359, 360 in the DT, **234 is not**). ACPI also gives memory for CPAS
`0xAC13000`, CAMNOC `0xAC19000`, CCI `0xAC15000`, `0xAC16000` (equal to the DT).

| Downstream node | Base / SPI (DT) | Source on our side | Fill from |
|:--|:--|:--|:--|
| `qcom,cam-cpas@ac13000` | `ac13000`, camnoc `ac19000`, `cam_rpmh` `bbf0000`; SPI 459 | ACPI `CAMP` (bases, IRQ); `bbf0000` only Qualcomm DT | **Verified** (ACPI + DT) except `cam_rpmh` (Inference) |
| `qcom,cci0/1` (`cam_cci0/1`) | `ac15000`/`ac16000`; 460/271 | ACPI, and upstream `cci0/cci1` of patch 0003 | **Verified** |
| `qcom,csid0/1`, `csid-lite0/1`, `ife0/1`, `ife-lite0/1`, `csiphy0/1/2/4`, `tpg13-15` | same bases as upstream `camss` regs; IRQs 464-469, 359/360, 477-479/122, 413/416/417 | upstream `hamoa.dtsi` camss node; IRQs from ACPI | **Verified** (three sources agree) |
| `qcom,icp@ac01000` (+`ac01800`, `ac04000`), SPI 463 | not in upstream | IRQ from ACPI `QCOM0C25`; bases from the DT only | IRQ **Verified**, bases Inference (same SoC) |
| `qcom,bps@ac2c000`, `qcom,ipe0@ac42000`, `qcom,sfe0@ac9e000` (689), `rt-cdm0..3` (456, 287, 764, 765), `jpegenc/jpegdma` (474/475) | DT | IRQs from ACPI; bases DT only | IRQ **Verified**, bases Inference |
| clocks, GDSC (`TITAN_TOP`, `IPE_0`, `BPS`, `IFE_0/1`, `SFE_0`), OPP tables, `cam-icc` paths | DT | `camcc-x1e80100` driver and `rpmhpd` (bindings compile) | Inference (Qualcomm's values, same SoC); the clock rates are Qualcomm's tuning |
| `qcom,cam-smmu` and child CBs (iommu streams) | DT | upstream CAMSS patch "describe iommu entries" uses the same `0x800..0x860` | Inference |
| `camera_mem` + `memory-region` of ICP | upstream `camera@8e100000` | `hamoa.dtsi:608` | Inference; Unknown for Surface firmware |
| Sensor nodes (`qcom,cam-sensor`) | EVK IMX577 uses **CSIPHY1, CCI0 master 1, MCLK1 (gpio97), reset gpio110** | our rear OV13858 (patch 0005, Windows data): **CSIPHY1, `cci0_i2c1`, MCLK1 gpio97, reset gpio110**, rails pm8010 L6 1.8 V, L1 1.2 V, L5 2.8 V | the wiring equals the EVK cam0 slot; rail currents, `sensor-position-*` and MCLK rate are Hypothesis until REA of the sensor extension data |
| TLMM pin states `cam_sensor_*`, `cci*_active` | DT (EVK pins: CCI0 on gpio101/102) | our `cci0_i2c1` is gpio103/104 | needs SP11 values (patch 0005 has them) |

The DT for the first test (TPG only, no sensor, no ICP) is therefore fully fillable from Verified data plus Qualcomm's
same-SoC values. A full SP11 DTB variant is a mechanical composition and is the next DT task (stage 1a).

## 6. Firmware (task 4)

What the driver requests (Verified: `common/cam_icp_util.c:62-125`, `cam_icp_v2_core.c:461-770`):
`request_firmware` candidates, in order: the DT `fw_name` (`qcom/x1e80100/CAMERA_ICP`) with the suffix; `qcom/<target>/<basename>`
(target `x1e80100` from CPAS); `<basename>` at the root; fallback `qcom/x1e80100/CAMERA_ICP` and `CAMERA_ICP`.
Suffix `.mbn` for the secure PIL path, `.elf` for the non-secure path. Nothing else: no CDM, JPEG, sensor, OIS or flash
firmware is requested. (CamX userspace loads its own DSP libraries via fastrpc, not through the kernel.)

| File | Where | Size | SHA-256 prefix | Note |
|:--|:--|:--|:--|:--|
| `CAMERA_ICP.mbn` | Windows `DriverStore/qccamisp8380.inf_arm64_068a5d125dcec104/` | 905880 | `c214e486` | ELF32 Xtensa, 21 phdrs, Qualcomm signed (catalog) |
| `CAMERA_ICP_AAAAAA.elf` | same folder | 4738507 | `ba4e95ac` | ELF32 Xtensa, 19 PT_LOAD, unsigned; the shape the **non-secure** path expects |
| `qcom/x1e80100/CAMERA_ICP.mbn` | Qualcomm Linux package `camxfirmware_1.0.27` (hamoa; purwa `x1p42100` is a symlink to it) | 541336 | `4a75fd1a` | ELF32 Xtensa, 21 phdrs; redistributable under `Qualcomm-Nologin-Binaries` in binary form on Qualcomm-chipset platforms |

Inference: the Windows `.mbn` and the Linux `.mbn` are different builds of the same firmware family (same machine,
same program-header count, different size and hash). Which one the Surface TZ accepts for PAS id 33 is Unknown.
Recommendation under S5: use Qualcomm's own Linux package first (S5-clean for the image); the Windows blobs would need an explicit
operator exception (S5 as written covers MAC and Wi-Fi board data only). The firmware worker owns the manifest.

## 7. Userspace (task 5)

Verified by GitHub listing and package contents:

- **Qualcomm publishes the Linux CamX stack as prebuilt Debian packages** for hamoa (`qualcomm-linux/pkg-camx-hamoa`,
  `pkg-camx-firmware-hamoa`, `pkg-camx-dev`, `pkg-camx-dkms`, `pkg-qti-camera-service`, `camx-metadata`
  (BSD-3-Clause-Clear), `pkg-gst-plugins-imsdk`/`pkg-qimsdk`). The CamX binaries are closed
  (`Qualcomm.nologin.binaries.license`), downloadable anonymously from `qartifactory-edge.qualcomm.com` (listing: 100 release
  folders, newest `261029`; hamoa `camx-hamoa_1.0.56` in `261026/prebuilt_resolute`).
- `camx-hamoa_1.0.56` (649 files): HAL `camera.qcom.hamoa.so` (60.6 MB, needs `libcdsprpc` and the CamX helper
  libs), CHI use-case and node libs (IPE/BPS striping, `isphwsetting`, `node.*`, `feature2.*`, `stats.*` AEC/AWB/AF),
  `settings.hamoa`, sensor drivers `com.qti.sensor.*.so` including **`ov13858`, `ov13858_rhodes`**, `imx577`, `imx688`,
  `og0va1b`, `ov08x`, `ov9282`, module and tuning data only for the EVK modules (`com.qti.sensormodule.*.bin` for
  IMX577, OG0VA1B, OV08X, IMX688, TPG; `com.qti.tuned.*.bin`), and a test app **`nativehaltest`** (1.6 MB, needs only
  `libcamera_hardware`, `libcamera_metadata`, `libcamxexternalformatutils`).
- `camx-headers_1.1.1`: Android camera3 HAL headers and the offline-camera/post-processing interfaces.
- `pkg-qti-camera-service`: the `qmmf` camera service daemon and client APIs (GStreamer apps use it).
- No libcamera pipeline handler for this ABI exists in these orgs; no `cam-test` in `camera-driver` (`scripts/` has only
  `sanitize_uapi.sh`). Qualcomm's upstream CAMSS-based work (`kernel-topics` `tech/mm/camss`) goes the V4L2/libcamera way.

Inference: a CamX HAL stack on Fedora would need packaging of these Debian-built binaries (glibc aarch64, fastrpc, URM) and
the SP11 sensor-module and tuning data. The EVK has no OV13858/IMX681/VD55G0 module `.bin` in the hamoa package, so the
Surface module data (Windows `com.surface.tuned.*.bin`, parsed by the quality worker) would have to be converted to the
CamX sensor-module format (Hypothesis; needs the format of `com.qti.sensormodule.*.bin`). Licence of the CamX binaries
(redistribution only in binary form on Qualcomm chipsets) is compatible with a private image; a public image needs a decision.

## 8. Staged plan (task 6)

**Stage 1a: RAW capture (CSIPHY + CSID + IFE RDI)**

| Step | Content | Offline-verifiable now |
|:--|:--|:--|
| 1a.0 | Two routes in parallel, because they are exclusive per boot: **A** upstream CAMSS RDI + libcamera SoftISP (patches 0001-0019, no new kernel code, the fast path), **B** Spectra | A: existing |
| 1a.1 | Kernel worker ships `camera_x1e80100.ko` (this driver + the two Kbuild patches) as an out-of-tree module of the kernel RPM, built after vmlinux (BTF) | build proven (§3) |
| 1a.2 | DTB variant `x1p64100-microsoft-denali-spectra`: Denali + Qualcomm's `hamoa-camera*.dtsi` (BSD-3, copied into the tree with licence) with `&camss`, `&cci0`, `&cci1` disabled, SP11 sensor node from patch 0005 | compiles today (§5.2) |
| 1a.3 | First device test, **no sensor**: load the module, check CPAS probe (`CAM_QUERY_CAP`), SMMU CBs, IRQ counts, `cam-req-mgr` nodes; then TPG13..15 into IFE RDI | device |
| 1a.4 | Own capture tool against the UAPI headers (session, buffers, link, IFE acquire, INIT/UPDATE packets, RDI out to a dma-buf), then the rear OV13858 through `cam_sensor` (probe, power, register blob, stream on) | tool can be written and unit-tested against the headers offline |
| Exit | RAW frame from OV13858 and from TPG with the same IFE path; privacy LED lit while streaming | |

**Stage 1b: full Spectra with ICP, BPS and IPE**

| Step | Content |
|:--|:--|
| 1b.1 | Firmware: try `CAMERA_ICP.mbn` through PAS (set `icp_use_pil`, PAS id per Windows evidence); if TZ refuses, try the non-secure ELF path (drop `icp_use_pil`, `CAMERA_ICP.elf`); record which succeeds |
| 1b.2 | ICP HFI handshake (`hfi.c`), `CAM_ICP_*` acquire of IPE and BPS, a pass-through BPS+IPE job from the raw RDI buffer |
| 1b.3 | Userspace: either Qualcomm's prebuilt CamX hamoa HAL with `nativehaltest` (needs the sensor-module and tuning `.bin` for the Surface modules), or an own tool that fills BPS/IPE settings blobs from the Windows Chromatix data (the quality worker already parses it) |
| 1b.4 | Quality parity against the libcamera SoftISP result of the quality worker; then the front IMX681 (C-PHY works in the downstream CSIPHY: `cam_csiphy_2_1_2_hwreg.h`, same tables as the reference file) and the IR VD55G0 |
| Exit | RGB/YUV frames with correct colours from the hardware ISP, both RGB cameras, under S2 (no IR emitter, no flash) |

Gating unknowns: ICP firmware authentication (§3.3 item 3), SMMU model (item 2), `camera_mem` ownership (item 4).

## 9. Requests and questions

- R-S1 (kernel): build `camera_x1e80100.ko` from `out/ref/camera-driver` + `hardware/cameras/spectra/patches/` as an out-of-tree
  module after vmlinux (BTF), and confirm `CONFIG_GPIOLIB_LEGACY=y`, `QCOM_PAS=y`, `QCOM_MDT_LOADER`, `QCOM_LLCC`, `ARM_SMMU_QCOM`
  in the Fedora release config. Do not load it together with `qcom-camss`/`i2c-qcom-cci` (DT-level exclusion).
- R-S2 (sources): pin `out/ref/camera-driver` `08171dd`, `qualcomm-linux/kernel` `qcom-next` `17bbb4b3` (the five camera DT files), and the three
  Qualcomm CamX packages above (names, versions, sha256) in `sources/sources.toml`.
- R-S3 (firmware): add `CAMERA_ICP.mbn` (Qualcomm Linux package, `4a75fd1a`) to the firmware manifest as `qcom/x1e80100/CAMERA_ICP.mbn`; the
  Windows variants (`c214e486`, `ba4e95ac`) only with an explicit S5 exception.
- For the Windows analyst (not asked of REA here): (a) does the Windows ISP path load `CAMERA_ICP.mbn` or the `.elf`, and through which
  secure call and PAS/service id; (b) what is the `QCOM0CCC` extra interrupt (SPI 234) used for; (c) the ICP load address and
  whether Windows reserves `0x8e100000` for it; (d) the format of the Surface sensor-module `.bin` against `com.qti.sensormodule.*.bin`.

## 10. Reproduce

```bash
cd hardware/cameras/spectra/scripts
./prep-tree.sh tree                     # git worktree out/linux/spectra + 69 patches
./prep-tree.sh config                   # .config like kernel/config + modules_prepare (container, build lock)
./prep-tree.sh driver                   # clone out/ref/camera-driver + our patches
./build-spectra.sh plain                # make M=... CAMERA_ARCH=x1e80100 modules
./prep-tree.sh symvers <path>/camera_x1e80100.o   # only if modpost lacks symbols
./check-downstream-dt.sh [sensor]       # downstream hamoa camera DT on the Denali DTS
```
