# Revision 21: IMX681 C-PHY clocks and CSID capture

Static analysis and ARM64 object compilation, 2026-11-02. No device was tested. This supersedes the **clock-domain inference** in `2026-10-30-cphy-port.md`; it does not establish a working stream. `patches/0003` and the image were not changed.

## Inputs and grades

**Verified, source contents:** Linux `v7.3`, commit `c03c1a14507dfaf8b856c2608f9ac216021fc222`; `sources/linux/drivers/media/platform/qcom/camss/camss.c:2980,3123,3331,3436,4190,4309`, `camss-csiphy.c:137-198`, `camss-csid.c:539-601`, `camss-csid-680.c:98-129,186-212,236-315`; `sources/linux/drivers/clk/qcom/camcc-x1e80100.c:600-626,660-672,720-739,1597-1629,1669-1685` and `include/media/mipi-csi2.h:40`. Local camera patches 0007-0010, 0016 and 0018 provide the additional C-PHY code and front endpoint.

**Verified, reference contents, not yet sources-pinned:** Qualcomm Hamoa `out/ref/qcl-hamoa-camx-dts/hamoa-camera.dtsi`, SHA-256 `d44c9f6fa5ed743469d2beff0d6ce76601f1081a25691316da8823988d70e1c9`, upstream `qualcomm-linux/kernel` qcom-next commit `17bbb4b37bbc4fc5827b4667445a0c43967c0f48` per `SOURCE.txt`: lines 1307-1352, 1697-1734, 1778-1800. [Pinned-commit reference](https://github.com/qualcomm-linux/kernel/blob/17bbb4b37bbc4fc5827b4667445a0c43967c0f48/arch/arm64/boot/dts/qcom/hamoa-camera.dtsi). Qualcomm `out/ref/camera-driver`, commit `08171ddc9d6ad81c13e6f1b362248d4736b0e804`: `camera/drivers/cam_sensor_module/cam_csiphy/cam_csiphy_soc.c:205-245,405-441` SHA-256 `63c849da90c7766b1c13b58acd3e808d1d89a24d929800eef80d3185a6e4d834`; `cam_isp/isp_hw_mgr/isp_hw/ife_csid_hw/cam_ife_csid680.h:1122-1147`, SHA-256 `d61c0025995f289f234056b1e44b58ddaa33c1e36b35c0c8079d7dc76ce7c3c4`; `cam_ife_csid_hw_ver2.c:5382-5430,5835`, SHA-256 `eafb3658e8d8b4e58fa974527e800c8c80d6c08e97af0d7ea33e83800be449e0`. The clock and register choices themselves need independent cross-check before `sw-ready` (protocol §5.1).

A posted [X1E CSI2 PHY C-PHY RFC v3](https://lists.openwall.net/linux-kernel/2026/10/16/2163) explicitly keeps link frequency equal to half symbol rate for its PHY clock scaling and reports a separate author's SP11 IMX681 2.4 Gsym/s test. That report concerns another kernel and patch stack and is **not** a test of this patch or this device. The Qualcomm reference is the basis for our nominal votes; the posted RFC does not prove a CSID clock formula.

## Arithmetic and domain decision

| Quantity | Derivation / value | Grade |
|:--|:--|:--|
| Link frequency | Front DT control `1,200,000,000 Hz`, one C-PHY trio (patch 0018) | Verified, configured; actual sensor signaling TBD |
| Symbol rate | `2 × 1.2 GHz = 2.4 Gsym/s` under the V4L2 C-PHY UI convention (patch 0007 and posted RFC) | Inference |
| Equivalent payload bit rate | Qualcomm approximation `2.4 × 57/25 = 5.472 Gbit/s` per trio; ideal 16/7 gives `5.485714... Gbit/s` before protocol overhead. Patch 0007's `2.736 GHz` is **half** the approximate bit rate, not the bit rate | Inference |
| Old failed clock | `2.736 GHz / 4 × 1.05 = 718.2 MHz`, exceeding the 480 MHz X1E maximum. Both PHY core and timer are rate-selected by the old loop, and timer maximum is only 400 MHz | Inference from code and tables, not a device observation |
| CSIPHY2 core | **480 MHz nominal vote**, supported by reference and v7.3 table | Inference for this mode; rounded/applied device rate TBD |
| CSIPHY2 timer | **400 MHz nominal vote**, separately supported by reference and timer table | Inference for this mode; actual rate TBD |
| CSID and CSID CSIPHY RX | **480 MHz nominal vote each**; RX shares the PHY CPHY_RX parent, CSID has its own parent | Inference for this mode; actual rates and concurrent-clock arbitration TBD |

Hamoa describes CSIPHY v2.1.2's `cphy_rx_clk_src` at 480 MHz and timer source at 400 MHz in its sole nominal row. CSID's own source has 300/400/480 MHz levels, and its CSIPHY RX gate belongs to the shared CPHY_RX parent. The pinned v7.3 X1E PHY table has core 300/400/480 and timer 266.666667/400 MHz; all five CSIDs list `csid` and `csid_csiphy_rx` each at 300/400/480. The clock-controller tables implement these rates and show the PHY2 and CSID RX branches share `cam_cc_cphy_rx_clk_src`; CSID itself uses `cam_cc_csid_clk_src`. Setting two gates is not evidence of two independent sources. The ref nominal row supports the selected votes, not a proven minimum or an observation at this exact sensor mode.

For comparison, pinned SM8550 has PHY core 400/480 and timer 400 MHz, and full CSID and RX 400/480 MHz; SM8650 has PHY core and timer 400 MHz, full CSID 400 MHz and RX 400/480 MHz. These are different SoCs and cannot prove an X1E minimum. Downstream dynamic voting divides its supplied C-PHY `data_rate` by 32 for v2.1.2 (`cam_csiphy_soc.c:205-245,435-441`), unlike D-PHY's division by 8; treating 5.472 Gbit/s as that input gives 171 MHz before its +1 and vote selection. This arithmetic is illustrative: Hamoa has one nominal row and the provenance/units of the userspace value and the CSID core requirement have not been independently established. Do not infer a general PHY or CSID divisor from this example.

**Decision:** the patch 0007 `57/25` equivalent-bit-rate conversion followed by `/4` belongs in **neither** of these X1E hardware clock selections. Its 57/25 approximation remains only in the pixel-rate-to-link-frequency fallback. The patch deliberately selects the existing Hamoa nominal rates for C-PHY rather than claiming a derived universal formula. It rejects an unknown link frequency and a symbol rate above 2.5 Gsym/s, the class covering the front mode; this is a conservative scope limit pending clock validation for faster modes, not a statement of hardware capability. Patch 0009's table continues through 6 Gsym/s. `2.4 Gsym/s` selects its 2.5 Gsym/s class. D-PHY retains its original frequency calculation, clock names, rate selection and capture behavior. Runtime effects of the shared RX clock with simultaneous front/rear streams remain TBD.

## CSID capture fields

The 680 reference configures `capture_ctrl` during RX enable, selecting the first active CID's VC and data type; it sets long-packet capture and, for C-PHY, the C-PHY packet capture enable and matching VC/DT (`cam_ife_csid_hw_ver2.c:5382-5430,5835`). These select **diagnostic captured headers** and do not establish that the field is necessary for RDI payload delivery. Patch 0023 matches those fields on a C-PHY RDI enable, clears them on disable, and corrects the pre-existing reversed `GENMASK(20, 25)` to `GENMASK(25, 20)`. Multiple RDIs share this one diagnostic selector; the last configured wins. D-PHY writes remain unchanged.

For VC 0 and RAW10 DT `0x2b`, the expected C-PHY capture-control write is `0x02b002b5`: bit 0 long, bit 2 C-PHY, `0x2b << 4` and `0x2b << 20`, VC fields zero. It is **not** a hardware readback. Patch 0023 emits dynamic-debug lines for its clock requests and capture writes. Stream routing, CFG0 PHY type, actual capture register state, and frame delivery still require device evidence.

## Patch and build verification

- `patches/0023-media-qcom-camss-use-hamoa-cphy-clock-votes.patch`, SHA-256 `1e7828da9fdab2ed2c98250dbc310954c454f3772f005337ce414603e7382b36`; apply after the full rev20 camera series. `patch --dry-run --batch --fuzz=0 -p1` against copies of the five pre-0023 files succeeded. `scripts/checkpatch.pl --strict --no-tree` reported **1 error: missing Signed-off-by**, 0 warnings, 0 checks; missing signoff is accepted for local patches.
- `patches/0003` SHA-256 before and after: `1575edb32c3665e55f0e4b695371bbe2869258f00478e06da4d4e47d5ad8f861`.
- The local `out/linux/cameras` snapshot already contained corrected 0003, and its CAMSS `camss.c` matched `sources/linux` byte-for-byte. To respect camera-only write ownership, copied that snapshot into a disposable `hardware/cameras/.rev21-work/linux`, applied 0001-0002 and 0004-0022 in order with `patch -p1`, then applied the 0023 edits; no git writes or shared lock. 0003 was already present and was not reapplied. This is a copy of the camera kernel worktree/snapshot, not the kernel owner's integrated revision-20 tree.
- Copied `out/build/cameras-rev20/.config`, then ran `make -C "$TASK_ROOT/linux" O="$TASK_ROOT/build" ARCH=arm64 olddefconfig`; confirmed `CONFIG_VIDEO_QCOM_CAMSS=m`, `CONFIG_DEBUG_INFO_BTF=y`, `CONFIG_DEBUG_INFO_BTF_MODULES=y`. Native ARM64 GCC 13.3.0. Missing host prerequisites were extracted locally from Ubuntu `pahole 1.25`, `flex 2.6.4`, `bison 3.8.2`, `m4 1.4.19`, `libelf-dev` and `zlib1g-dev`; no system packages installed. First attempts exposed missing flex/m4 and libelf headers/link dependencies; after supplying them locally the following succeeded:

```sh
TASK_ROOT="$PWD/hardware/cameras/.rev21-work"
PATH="$TASK_ROOT/tool/usr/bin:$PATH" CPATH="$TASK_ROOT/tool/usr/include" \
LIBRARY_PATH="$TASK_ROOT/tool/usr/lib/aarch64-linux-gnu" \
M4="$TASK_ROOT/tool/usr/bin/m4" BISON_PKGDATADIR="$TASK_ROOT/tool/usr/share/bison" \
make -C "$TASK_ROOT/linux" O="$TASK_ROOT/build" ARCH=arm64 W=1 -j4 \
    drivers/media/platform/qcom/camss/
```

The complete CAMSS directory compiled and `qcom-camss.o` linked, exit 0 and no warnings. After adding the C-PHY capture debug line, the same command rebuilt `camss-csid-680.o` and relinked successfully. A subsequent change corrected only a source comment and patch description about the 2.5 Gsym/s scope; executable code was unchanged. No `vmlinux`, `.ko`, full kernel or BTF generation was requested. Object compilation with BTF options enabled does not validate final BTF generation or integration. Scratch files were removed after recording results.
