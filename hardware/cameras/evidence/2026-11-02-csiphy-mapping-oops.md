# Camera stream-on oops and CAMSS register-window audit

## Device observation and cause

Revision 19 safe boot `393849d8` on kernel `7.3.0-65.sp11.19.fc44` reports `imx681 8-0010` linked to `msm_csiphy2` and `ov13858 7-0010` to `msm_csiphy1`, both links enabled and immutable. This and the following oops are **Verified as reported in** `plan/rev20.md:3-30`, from the operator's `C:\sp11-logs-2-5`; the raw device logs were not re-read in this session. While CameraManager streamed, the log reports:

```text
Unable to handle kernel paging request at virtual address ffff800083aa6000
ESR = 0x96000047  EC = 0x25 (DABT)  FSC = 0x07 (level 3 translation)
WnR = 1  (write)
pc : csiphy_reset+0x30/0x78 [qcom_camss]
lr : csiphy_set_power+0x94/0x1b0 [qcom_camss]
x2 : ffff800083aa5000   x1 : ffff800083aa6000
```

The reported running DT sizes were `0x1000` at `0x0ace4000`, `0x0ace6000`, `0x0ace8000`, and `0x4000` at `0x0acec000` (Verified as reported, same source). The fault address is the reported mapping base plus `0x1000`; its relationship to the resource bounds and reset write identifies the undersized mapping as the cause (Inference, not a new device test). The fault record does not by itself identify which sensor initiated the stream.

Pinned v7.3 `sources/linux/drivers/media/platform/qcom/camss/camss.c:4190-4257` uses `csiphy_ops_3ph_1_0` for all four X1E PHYs, and `camss-csiphy.c:602` maps each named DT resource. `camss-csiphy-3ph-1-0.c:1242-1245` sets X1E `regs->offset = 0x1000`; the common-control macro at line 45 and `csiphy_reset()` at lines 953-958 write common control 0 at that offset. The source line reported in the plan (`1217`) differs from the pinned tree: the X1E assignment is **line 1245**. A `0x1000` resource excludes that word. `0x2000` includes the common block; this is supported independently by the Qualcomm Hamoa map and the mainline SM8550/SM8650 nodes below. The shortened PHY4 window also removes the extra `0x2000` claimed beyond the Hamoa map.

## Corrected register list

Entries are in patch 0003 `reg`/`reg-names` order. Grades apply to the selected **base and window**, not proof that every byte is implemented. All names and original example values are Verified in `sources/linux/Documentation/devicetree/bindings/media/qcom,x1e80100-camss.yaml:20-40,193-230`; this example itself contains the erroneous PHY sizes. The driver resource names are Verified at `sources/linux/drivers/media/platform/qcom/camss/camss.c:4190-4537`. Qualcomm's Hamoa reference below is `out/ref/qcl-hamoa-camx-dts/hamoa-camera.dtsi`, SHA-256 `d44c9f6fa5ed743469d2beff0d6ce76601f1081a25691316da8823988d70e1c9`, `qcom-next` commit `17bbb4b37bbc4fc5827b4667445a0c43967c0f48` per its `SOURCE.txt`; it is an unpinned reference input, not a source pinned by the sources worker. SM8550 `sources/linux/arch/arm64/boot/dts/qcom/sm8550.dtsi:3846-3886` and SM8650 `.../sm8650.dtsi:5448-5485` provide comparisons, not proof of X1E layout.

| Name | Base | Size | Grade and audit |
|:--|:--|:--|:--|
| csid0 | `0x0acb7000` | `0x2000` | Inference: binding example; Hamoa reference :1307-1312 uses `0xd00` at this base; larger window contains it without overlap with next resource. |
| csid1 | `0x0acb9000` | `0x2000` | Inference: example; Hamoa :1354-1359 uses `0xd00`; containing window ends at csid2. |
| csid2 | `0x0acbb000` | `0x2000` | Inference: example and SM8550 same base; Hamoa reference has no corresponding CSID2 node. Confirm X1E hardware extent independently. |
| csid_lite0 | `0x0acc6000` | `0x1000` | Inference: example; Hamoa :1401-1404 describes `0xa00` at this base; containing window ends at VFE lite0. |
| csid_lite1 | `0x0acca000` | `0x1000` | Inference: example; Hamoa :1506-1509 describes `0xa00`; containing window ends at VFE lite1. |
| csid_wrapper | `0x0acb6000` | `0x1000` | Verified in Hamoa :1307-1311 (`csid_top`) and example; ends at csid0. |
| csiphy0 | `0x0ace4000` | `0x2000` | Verified in Hamoa :1611-1614; common-block need independently shown by driver. |
| csiphy1 | `0x0ace6000` | `0x2000` | Verified in Hamoa :1654-1657; same driver. |
| csiphy2 | `0x0ace8000` | `0x2000` | Verified in Hamoa :1697-1700; same driver. |
| csiphy4 | `0x0acec000` | `0x2000` | Verified in Hamoa :1740-1743; same driver. |
| csitpg0 | `0x0acf6000` | `0x1000` | Inference: example; Hamoa :1783-1787 has `0x400` at this base; the containing window ends at csitpg1. |
| csitpg1 | `0x0acf7000` | `0x1000` | Inference: example; Hamoa :1821-1825 has `0x400`; ends at csitpg2. |
| csitpg2 | `0x0acf8000` | `0x1000` | Inference: example; Hamoa :1859-1863 has `0x400`; ends at the next downstream RT-CDM at `0x0acf9000` (:1897-1901). |
| vfe0 | `0x0ac62000` | `0xf000` | Verified in Hamoa :1117-1122 and both comparison SoCs. Corrects the example's `0x4000`; ends at vfe1. |
| vfe1 | `0x0ac71000` | `0xf000` | Verified in Hamoa :1182-1187 and both comparison SoCs. Corrects the example's `0x4000`. |
| vfe_lite0 | `0x0acc7000` | `0x2000` | Inference: example's Linux subwindow lies inside Hamoa's combined `0x0acc6000`+`0x4000` IFE-lite window (:1453-1456), after its CSID-lite window; SM8650 has `0x2000` lite windows. |
| vfe_lite1 | `0x0accb000` | `0x2000` | Inference: example's Linux subwindow lies inside Hamoa's combined `0x0acca000`+`0x4000` window (:1558-1561); SM8650 has `0x2000` lite windows. |

No other names or bases were changed. Conservative CSID and TPG window sizes exceed the reference's functional blocks; the reference does not establish that all slack addresses are safe for access. The X1E example and reference are not independent hardware measurements, and CSID2 / exact subwindow bounds need an independent register-map cross-check. No omitted top-level block was invented. CCI resources are separate from this CAMSS audit.

## Privacy and safety

The sensor privacy path already exists: `sources/linux/drivers/media/v4l2-core/v4l2-fwnode.c:1275` gets the LED, `v4l2-subdev.c:173-186,490-500` controls it on stream, with shared-LED accounting in camera patch 0020. The reported DTB references the indicator on both sensors (`plan/rev20.md:32`). Physical illumination and wiring are not established by these software facts. Streaming requires the independent wiring cross-check and visible indicator test; stop immediately if it is off. IR remains excluded from the RGB graph and IR illuminator, flash and strobe stay off (S2).

## Validation

Validation results are recorded below after the DT-only build. This change has not been tested on the device; no successful stream, image or privacy LED behavior is claimed.

- `git -C sources/linux apply --check` succeeded on pinned `v7.3` (`c03c1a14507dfaf8b856c2608f9ac216021fc222`); a clean archive in `out/linux/cameras` accepted `patch --fuzz=0` without git writes. This is an archive, not a registered git worktree.
- Preprocessed `x1p64100-microsoft-denali.dts` from that archive and compiled with the previously built kernel `dtc` to `out/build/cameras-rev20/denali.dtb`; SHA-256 `0e8358193a1446b122c4fa87512da94efeba86f7c98748015f1889a5ab745a08`. Decompiled it and checked all 17 resource names, bases and sizes against the table above: pass. `dtc` emitted duplicate-unit-address warnings for existing GENI I2C/SPI/UART alternatives. The standalone DTB contains patch 0003 only and leaves CAMSS disabled; it is not the integrated RGB-only device image.
- A bounded `make` DTB build was attempted under the kernel build lock with a separate `O=out/build/cameras-rev20`, but configuration regeneration failed because `flex` is unavailable, including after reusing existing generated tools. `CHECK_DTBS` was not run: `dt-validate`/Python `dtschema` are unavailable. Kernel integration must repeat the build and schema check in its prepared environment.
