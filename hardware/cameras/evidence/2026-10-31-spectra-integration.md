# Cameras: Spectra integration, stage 1a (DTB variant, module RPM, first-test plan), offline

Date: 2026-10-31. Offline work only: no device access, no REA call, no kernel release build, no commit.
Builds the three pieces the first device test of the Spectra path needs, on top of
`2026-10-31-spectra-port.md` (which proved the downstream driver builds against v7.3 and that Qualcomm publishes the
hamoa DT). Grades follow `agents/protocol.md` §5: **Verified** (produced by a named command or read from named
data), **Inference** (reasoning given), **Unknown**. Safety: S1 (speakers stay off, no GPU), S2 (no flash, no IR
emitter node), S3 (nothing is written to a device), S5 (Qualcomm's own binary is fetched at image build, never put in
git; no Windows data used here).

## 1. DTB variant `x1p64100-microsoft-denali-m15-spectra`

Files: `kernel/dtb-variants/x1p64100-microsoft-denali-m15-spectra.dts` (the variant),
`hardware/cameras/spectra/dt/qcl/` (Qualcomm's DT, unmodified, `SOURCE.txt` and `../SHA256SUMS`),
`hardware/cameras/spectra/dt/include/dt-bindings/camera/msm-camera.h` (from camera-driver `08171dd`),
`hardware/cameras/spectra/scripts/build-dtb-spectra.sh`.

### 1.1 Pinned inputs (Verified)

| Input | Pin |
|:--|:--|
| `qualcomm-linux/kernel` branch `qcom-next` | commit `17bbb4b37bbc4fc5827b4667445a0c43967c0f48` (`git ls-remote` on 2026-10-31 still returns it as head) |
| `hamoa-camera.dtsi` (2477 lines, BSD-3-Clause) | sha256 `d44c9f6fa5ed743469d2beff0d6ce76601f1081a25691316da8823988d70e1c9`; fetched with `curl` from `raw.githubusercontent.com/.../<commit>/arch/arm64/boot/dts/qcom/`, byte-identical to the copy in `out/ref/qcl-hamoa-camx-dts` |
| `hamoa-camera-sensor.dtsi` | `77ae4e6a2daeb1b1c2b52f4af27d9df97e53bf9550d66d0dd3d6b15083809e64` (reference only) |
| `hamoa-camera-regulators.dtsi` | `11220caa5c6324170f789416fd0ce6cade94929043c17284943d3409523f09d3` (reference only, not included) |
| `hamoa-evk-camx.dtso` | `127738b16b216dae07d2c8a5db9f09e6e1a8244f372f65f4719c0d50b097ff88` (reference only) |
| `msm-camera.h` (camera-driver `08171dd`, GPL-2.0-only) | `dc83de4ee696a3af01a311dd3c33dffbad279760a17198612077d8b80928fc8d` |
| Scratch kernel tree | `out/linux/spectra-dt`: v7.3 + the 69 patches of `kernel/series` (series hash `9308d93a14683237f0ce298a73551ef4f15c787dca2108bc06272a548c4e61b0`) + `hardware/ec-sam/patches/0005` (volume keys), HEAD `91c66c5f3` |
| Base content | `m15-safe` does not exist yet in `kernel/dtb-variants` (kernel worker, series_rev 12). The script stages a stand-in with the content of `m14-safe` (m12 + digital microphones, GPU off, speakers off) and a pass-through `parity` shim, exactly as `scripts/kernel-dtb-m14.sh` does |

### 1.2 Result (Verified: `build-dtb-spectra.sh`, `kernel-dev.sh --check ... variant`, log `out/build/dtb-spectra.log`)

- **It compiles**: `qcom/x1p64100-microsoft-denali-m15-spectra.dtb`, **sha256
  `a9937580f02aa6a57399b1c3ee87a823b9aa0a90e8fe447e5a0ccf96bd200469`** (published for the test, not for the release,
  as `out/dtb-variants/spectra-test/qcom/` with a `.json` record).
- **dtc: zero warnings and zero errors** (`-@`, the same flags as the packaged base DTB). `CHECK_DTBS=y`: 637
  diagnostic lines, **all** about Qualcomm's downstream nodes, which have no binding: `failed to match any schema`
  for the `qcom,cam-*`/`qcom,cci`/`qcom,csid*` compatibles, non-standard property types (`icp-version`,
  `reg-cam-base`, `clock-cntl-level`, `iova-region-*`, `hw-thigh` ...), `'ranges' is a required property` for the
  childless `qcom,cam-*` nodes under the `simple-bus` `soc@0`, and `Unevaluated properties` for Qualcomm's TLMM pin
  states. No diagnostic about our own nodes (regulators, leds, cci, camss, sound, GPU). These cannot be fixed without
  rewriting Qualcomm's DT, and the downstream driver reads exactly those properties; the kernel worker must accept
  this class of lines for this variant only.
- **Difference to the base** (semantic compare of the two effective DTS): 282 nodes added (Qualcomm's), none
  removed, and three property changes on existing nodes: `regulators-8` (pm8010 "m") `disabled` -> `okay`,
  `camera-leds` `disabled` -> `okay`, `led-camera-indicator` (front/IR, GPIO225) stays `disabled` explicitly.
- Effective state: `camss` (`isp@acb7000`), `cci@ac15000`, `cci@ac16000` **disabled**; Qualcomm's `qcom,cam-cpas@ac13000`,
  `qcom,cci0@ac15000`, `qcom,cam-req-mgr`, `qcom,camera-main`, ICP, BPS, IPE, IFE0/1, IFE-lite, CSID, CSIPHY0/1/2/4,
  TPG13-15, JPEG, SFE, RT-CDM, SMMU contexts `okay`; Qualcomm's `cam_cci1` (`ac16000`) **disabled** (see 1.4).
- **S1/S2/GPU (Verified, `scripts/kernel-dtb-safety.py --profile default`)**: both WSA speaker nodes
  `effective_enabled: false`, SoundWire `swr0` disabled, sound card `okay` (microphones only, as m14-safe), GPU
  `disabled`. No `qcom,cam-flash`, `qcom,led-flash`, actuator, OIS or EEPROM node exists; the PMIC flash LED
  `pm8550_flash` is `disabled`. The IR emitter is not described anywhere.

### 1.3 Values filled from verified data

| Value | Where | Grade |
|:--|:--|:--|
| Register bases `ac13000` (CPAS), `ac19000` (CAMNOC), `ac15000`/`ac16000` (CCI) | ACPI `CAMP` (earlier evidence §5.3) = Qualcomm DT | Verified |
| CSID `acb7000/acb9000/acc6000/acca000`, VFE `ac62000/ac71000`, CSIPHY `ace4000/ace6000/ace8000/acec000`, TPG `acf6000-acf8000` | equal to the `reg` list of the upstream `camss` node (`hamoa.dtsi:5573`), which Qualcomm wrote | Verified (two sources); TPG block presence also from upstream |
| Interrupts | recomputed from the compiled DTB against the ACPI list of the earlier evidence: CPAS 459, CCI 460/271, CSIPHY 477/478/479/122, JPEG 474/475, ISP 456/287/463-469/689/764/765 all present; **234 (SecureISP) is the only ACPI interrupt not in the DT**; the DT adds TPG 413/416/417 that ACPI does not list | Verified (match), TPG IRQs Inference (same SoC, Qualcomm DT) |
| Rear camera slot | `qcom,cam-sensor1` under `cam_cci0`: `csiphy-sd-index = 1`, `cci-master = 1` (Qualcomm's `cci1_active` state = GPIO103/104, the Denali `cci0_i2c1_default` pins), MCLK1 GPIO97, reset GPIO110 | Verified (Denali DT lines 924-970, Windows data via patches 0005/0014) |
| Rails | `cam_vio` = `vreg_l6m_1p8` 1.8 V, `cam_vdig` = `vreg_l1m_1p2` 1.2 V, `cam_vana` = `vreg_l5m_2p8` 2.8 V (pm8010, regulators-8 of the Denali DT; min = max so the driver's `regulator_set_voltage` is inside the constraint) | Verified (existing Denali DT) |
| MCLK1 pad drive 4 mA | override of Qualcomm's 2 mA state, as the Denali `cam_mclk1_default` | Verified (patch 0005 data) |
| MCLK rate 19.2 MHz | same as the upstream node's `assigned-clock-rates`; CamX's sensor power setting overrides it at probe time | Inference |
| Reset level | `<&tlmm 110 0>`: the downstream driver sets **raw** levels (`gpiod_set_raw_value_cansleep`, `cam_compat.h:177-199`), so the flag is irrelevant on 7.3; the electrical reset stays active low and the level sequence comes from userspace | Verified (source) |
| I2C address 0x10 (7-bit) | **not a DT property in the downstream stack**: userspace sends the slave address in `CAM_SENSOR_PROBE`; the Denali DT keeps `reg = <0x10>` for the upstream driver, unused here | Verified (Denali DT) / Unknown for the CamX `ov13858` sensor `.so` (not read) |
| `sensor-position-roll/pitch/yaw` 0/0/180, `rgltr-load-current` 120000 | copied from the EVK cam0 slot | Hypothesis |
| Privacy LED GPIO105 | **the downstream sensor node has no LED property** (`grep` of `camera/drivers/cam_sensor_module`: only `cam_flash` drives LED triggers, and the flash is S2). Kept as the board's `gpio-leds` node `led-camera-indicator-rear` (GPIO105), the only enabled LED child, `default-state = "off"`; userspace must switch it while a stream runs. GPIO225 (front/IR) is not claimed | Verified (source), design decision |

### 1.4 Why Qualcomm's `cam_cci1` is disabled

`cam_cci1` (`0xac16000`, the always-on CCI) selects `cci2_active`/`cci3_active`, which mux **GPIO105/106 and 107/108**
as `cci_i2c`. GPIO105 is the Surface rear privacy LED, and the Surface front camera sits on GPIO235/236 (`aon_cci`),
which Qualcomm's node does not describe. Enabling it would put the wrong pins on the CCI and take GPIO105 from the LED.
It is left off for the first test (no front or IR camera node exists) and needs a Surface pin state before the front
camera is brought up. (Verified: `hamoa-camera.dtsi` lines 2418-2476 and the Denali pin states.)

### 1.5 Not in the DT, on purpose

- No sensor node for the front IMX681 and IR VD55G0 (first test).
- No `qcom,cam-flash`, `qcom,led-flash`, actuator (the L16B rail node stays `disabled`), EEPROM or OIS node (S2).
- SecureISP SPI 234: no node; the downstream driver does not use it (Unknown whether Windows needs it for secure camera).

## 2. The module as an RPM

Files in `hardware/cameras/spectra/rpm/`: `sp11-camera-spectra.spec`, `build-spectra-rpm.sh`,
`test-install-spectra-rpm.sh`, `sp11-camera-spectra-guard`, `sp11-camera-spectra.modprobe.conf`,
`sp11-camera-spectra-README`, `fetch-camera-icp.sh`.

- **Built** (Verified: `build-spectra-rpm.sh`, container `sp11-fedora-image:44`, `rpmbuild -ba`): out of tree against
  `kernel-devel-uname-r = 7.3.0-65.sp11.11.fc44.aarch64` (the published kernel; M15's kernel is not built), source
  `git archive` of camera-driver `08171ddc9d6ad81c13e6f1b362248d4736b0e804` (tarball sha256
  `e19279b3b67b6d5c6642deb55d2ebfe3784dbd1043f4af0dd19f167f6f13f728`) plus the two Kbuild patches, `CAMERA_ARCH=x1e80100`,
  `CAMERA_WERROR=0` (warnings printed; the earlier strict build with gcc 16.2.1 had none). Outputs in
  `out/rpms-local/` (not `out/rpms`, which holds the kernel release only): the RPM, the SRPM and a `.json` record with
  hashes: `sp11-camera-spectra-1.0-1.git08171dd.sp11.fc44.aarch64.rpm` sha256
  `b9b95c5b5f801f0616b9359f478c96405af40375ab0d264a21b1b21eae76c1ea` (1.29 MB module inside), SRPM sha256
  `250814dcdce4d22b6f4db23256b44a6e950bafbe3db410fe286240892cd90995` (they change with every rebuild of the spec).
- **BTF (Verified)**: the build copies kernel-devel, links the kernel's `vmlinux` from `kernel-debuginfo` into the copy,
  so kbuild's `btf_ko` step runs (`BTF [M] camera_x1e80100.ko` in the log); the installed module has a `.BTF` section
  after `strip --strip-debug`. 38.7 MB with DWARF becomes about 1.3 MB as `.ko.xz` (xz, crc32, like the kernel's own
  modules, `CONFIG_MODULE_COMPRESS_XZ=y`).
- **Install location and signing**: `/lib/modules/7.3.0-65.sp11.11.fc44.aarch64/extra/camera_x1e80100.ko.xz`, **unsigned**.
  The kernel has `CONFIG_MODULE_SIG=y` but not `MODULE_SIG_FORCE` (kernel-devel `.config`), so an unsigned module loads
  and taints the kernel; with Secure Boot off (R9) lockdown does not refuse it. If Secure Boot is ever on, this
  module will not load (Inference).
- **Requires** `kernel-uname-r = <kver>` (strict) and `kmod`; `%post/%postun` run `depmod -a <kver>`.
- **Conditional loading (what works and what does not)**:
  - The module's OF aliases (`modinfo -F alias`, 236 + the `C*` twins) include `qcom,cam-req-mgr`, `qcom,cam-sync`,
    `qcom,cci`, `qcom,csid695`, `qcom,csiphy`, `qcom,cam-sensor`, ... Those nodes exist only in the Spectra DTB, so
    udev autoloads the module there and never on another DTB (test below). **Correction to the earlier evidence**: the
    module has **no** alias for `qcom,cam-cpas` and `qcom,camera_x1e80100` (their match tables have no
    `MODULE_DEVICE_TABLE`), so those two nodes cannot trigger the load by themselves; the other nodes do.
  - A `modules-load.d` drop-in cannot be conditioned on the DT (systemd conditions apply to units, not to drop-in
    lines), so it is not used. Instead `/usr/lib/modprobe.d/sp11-camera-spectra.conf` has `install` lines that call
    `/usr/libexec/sp11-camera-spectra-guard`: `camera_x1e80100` loads only when
    `/proc/device-tree/soc@0/qcom,cam-cpas*` exists and is not disabled; `qcom_camss` and `i2c_qcom_cci` are refused
    (return success, message in the journal) exactly then. This also covers manual `modprobe` and dependency loads, which
    a plain `blacklist` line cannot do conditionally. `softdep camera_x1e80100 pre: camcc_x1e80100`.
  - On the Spectra DTB the upstream CAMSS/CCI nodes are disabled, so udev would not load those modules anyway; the guard
    is the second layer (and the reason for the DT-independent `module_blacklist=` suggestion in §4).
- **rpmlint (Verified, rpmlint 2.8.0)**: remaining items are spelling of technical words (`camss`, `cci`, `mbn`),
  `no-binary`/`only-non-binary-in-usr-lib` (a kernel module is a data file for rpmlint), and
  `incorrect-fsf-address` in Qualcomm's own `LICENSE.txt`; no error about files, scriptlets, dependencies or the
  licence field (`GPL-2.0-only`).
- **`rpm -qlp`**: the module, the modprobe conf, the guard, a README, the licence; no firmware.
- **Install test in a scratch root (Verified: `test-install-spectra-rpm.sh`)**: `rpm -i` into a scratch root (scriptlets
  skipped, the root has no `/bin/sh`; scriptlet text checked), `depmod -b root -a`, `modules.dep` lists the module,
  OF aliases of the Spectra nodes resolve to the module and the upstream camera nodes (`qcom,x1e80100-camss`,
  `qcom,x1e80100-cci`, `ovti,ov13858`, `sony,imx681`) resolve to nothing, `.BTF` present, `vermagic` equals the kernel,
  license `GPL v2`, unsigned, the guard allows/refuses correctly for four DT situations (Spectra active, node disabled,
  node absent, camss on the Spectra DT), `rpm -e` removes the file. The exact PASS/FAIL list is printed by the script.
  Module dependencies: `videodev, mc, llcc-qcom, qcom_smem, mdt_loader`.

## 3. Firmware: `qcom/x1e80100/CAMERA_ICP.mbn`

`fetch-camera-icp.sh [DEST]` (default `out/firmware-private/cameras/spectra`), run by the private image build:

1. Download (or reuse `out/ref/qcl-camx-prebuilt/` when it matches) `camxfirmware_1.0.27_arm64.tar.gz` from
   `https://qartifactory-edge.qualcomm.com/artifactory/qsc_releases/software/chip/component/camx.qclinux.0.0/261026/prebuilt_resolute/`
   (anonymous; the path is from `qualcomm-linux/pkg-camx-firmware-hamoa` README, HTTP 200 and the server's
   `X-Checksum-Sha256` was checked on 2026-10-31).
2. Pin 1: tarball sha256 `1f054c4700a3d936924f94a1fa3bbd7a51e15df8d86de9ea332c5d2533d04437`.
3. Extract `camxfirmware-1.0.27/camxfirmware-hamoa/arm64/usr/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn` and `LICENSE.qcom-2`.
4. Pin 2: `CAMERA_ICP.mbn` sha256 `4a75fd1ae5b47960698e3b5bd614a0484f05c068144f4e603332ab6e746ef4c8`, 541336 bytes.
5. Install to `DEST/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn` and `DEST/lib/firmware/LICENSE.qcom-2`, write `SHA256SUMS`.

Verified by running it (both pins pass; a wrong pin aborts with nothing written). The image copies
`DEST/lib/firmware/` to `/usr/lib/firmware/`. The licence (`Qualcomm-Nologin-Binaries`) allows binary redistribution on
Qualcomm-chipset platforms; the file stays out of git and out of the RPM. Whether the Surface TZ accepts this build for
PAS id 33 is Unknown (stage 1b). The driver requests the file only when a client acquires ICP/IPE/BPS.

## 4. First-test plan (TPG only, no sensor, no ICP)

Collector: `hardware/cameras/spectra/collector/spectra.sh` (read-only; output `extra-spectra.txt`). It reports: kernel,
cmdline, DT state (Spectra nodes, `camera-main`, upstream camss/cci status, sensor node), the RPM and the firmware file,
module state, refcount and taint for `camera_x1e80100`, `qcom_camss`, `i2c_qcom_cci`, `camcc_x1e80100`, `llcc_qcom`,
`qcom_mdt_loader`, bound drivers of the `qcom,cam-*` platform devices, `/dev/video*`, `/dev/media*`, `/dev/v4l-subdev*`,
`v4l2-ctl`/`media-ctl` listings, `/proc/interrupts` lines of the camera IRQs and their count, dmesg filtered for `CAM_*`,
`cam_*`, probe results, errors, the `CAMERA_ICP` firmware result, conflicts with CAMSS/CCI/camcc/SMMU/GDSC, genpd/clk
summaries when debugfs is readable, the pm8010 rail states, the privacy LED and S2 checks (no flash/torch LED class device,
no driver on the PMIC flash node). It does not load or unload anything, send ioctls, stream, or power a sensor.

Procedure (two boots, to separate "does this DTB boot" from "does the module run"):

| Boot | Entry | Module | What it answers | Pass |
|:--|:--|:--|:--|:--|
| 1 | `m15-spectra` DTB, M15 diagnostic arguments, **`module_blacklist=camera_x1e80100`** | not loaded | Does the DTB boot to the usual M15-safe state with 282 inert camera nodes, `camcc` probing, no SMMU or pinctrl complaints; collector shows no `qcom_camss` | Boots; same services as m15-safe; collector clean |
| 2 | same, marker file on the boot medium (image pattern `sp11-boot-state`) `sp11/enable-spectra-load` | `modprobe camera_x1e80100` by an image service | Module init, CPAS probe, SMMU context banks, IRQ registration, `cam-req-mgr` nodes, CSID/IFE/CSIPHY/TPG probe | Module loaded, no oops/SError/hang; `/dev/video*` for req-mgr and sync; the camera IRQs listed in `/proc/interrupts` (CPAS 459, ISP 463-469 ...) |

Stop criteria: any `Internal error`, `SError`, `synchronous external abort`, SMMU fault, a hang during module load or a
reset. Then the logs on the boot medium are the result and the next step is boot 1 again. A hang during boot 2 is the most
likely failure (§5): the module is never loaded in boot 1 and never on another entry.

Exit of stage 1a.3 (TPG/CPAS/SMMU/IRQ bring-up): the module stays loaded, no kernel error from `cam_*`, and the
collector lists req-mgr/sync nodes and the camera IRQs. TPG streaming and the OV13858 need the capture tool (stage 1a.4,
not written here); the ICP is untouched.

## 5. Risks and Unknowns (honest)

| # | Item | Grade / consequence |
|:--|:--|:--|
| 1 | Module init may hang or reset the SoC: CPAS enables GDSC and clocks and touches registers of blocks whose power state, SMMU stream setup or NoC state the Surface firmware may differ in | Unknown; mitigated by the two-boot procedure |
| 2 | `camera_mem` (`0x8e100000`, 8 MB `no-map`), `cam_rpmh` `0xbbf0000+0x1F00`, LLCC camera slice: ownership by the Surface firmware not proven | Unknown (earlier evidence §3.3) |
| 3 | Qualcomm's SMMU model (own context banks, `iova-region-*`) against `arm-smmu-qcom` with the default DMA domain | Unknown |
| 4 | TPG: ACPI does not list the TPG interrupts (413/416/417) or blocks; the blocks exist in the upstream camss node and Qualcomm's DT | Inference; a TPG-only capture is not proven possible on this unit |
| 5 | The module has no OF alias for `qcom,cam-cpas`/`qcom,camera_x1e80100`; autoload relies on the other nodes. If udev does not load it, the image service in boot 2 loads it | Verified (aliases), behaviour on the device Unknown |
| 6 | `CONFIG_MODULE_SIG=y`: the module is unsigned; fine with Secure Boot off (R9), refused otherwise | Inference |
| 7 | The RPM is tied to one `kver` and to the kernel's own `vmlinux`/Module.symvers; there is no `MODVERSIONS`, so a wrong-kernel load is stopped only by `vermagic`. M15's kernel (series_rev 12) needs a rebuild: `build-spectra-rpm.sh <kver>` | Verified |
| 8 | `CAMERA_WERROR=0` hides new warnings with another compiler | Low |
| 9 | CHECK_DTBS reports 637 lines for Qualcomm's unbound nodes; they are not errors, but any kernel gate that requires zero diagnostics fails for this variant | Known, needs a kernel-worker decision |
| 10 | Sensor values (`sensor-position-yaw`, load current), the I2C address in CamX's OV13858 driver, the privacy LED sequence | Hypothesis / Unknown (stage 1a.4) |
| 11 | Both camera stacks cannot coexist; the variant is the only place that decides, and the guard is the second layer | Design |

## 6. Requests

**kernel worker**
1. Carry `hardware/cameras/spectra/dt/qcl/hamoa-camera.dtsi` into `arch/arm64/boot/dts/qcom/` and `dt/include/dt-bindings/camera/msm-camera.h`
   into `include/dt-bindings/camera/` of the build tree (or stage them as `build-dtb-spectra.sh` does) and add the variant
   `m15-spectra` next to `m15-safe` (the variant `#include`s `x1p64100-microsoft-denali-m15-safe.dts`). Accept the 637 schema
   lines for this variant only; keep the S1/S2 profile checks (`kernel-m8-check.py` needs the variant name).
2. Confirm in the release config: `CONFIG_GPIOLIB_LEGACY=y` (**found `=y` in the 7.3.0-65.sp11.11 kernel-devel `.config`**),
   `QCOM_PAS=y`, `QCOM_MDT_LOADER=m`, `QCOM_LLCC=m`, `ARM_SMMU_QCOM=y`, `CLK_X1E80100_CAMCC=m`, `MODULE_SIG` without `FORCE`.
3. Publish `kernel-devel` and `kernel-debuginfo` for the M15 kver (series_rev 12) so the RPM can be rebuilt; this RPM does
   not need to be part of the kernel RPM.

**image worker** (private image only)
1. New menu entry `SP11 debug, Spectra camera test`: DTB `x1p64100-microsoft-denali-m15-spectra.dtb`, the M15 safe arguments,
   verbose (no `quiet`), plus `module_blacklist=camera_x1e80100` for boot 1; it is a test entry, never the main entry.
   Optionally also `module_blacklist=qcom_camss,i2c_qcom_cci` (independent of the guard).
2. Install `out/rpms-local/sp11-camera-spectra-*.rpm` built for the **same kver as the image's kernel**; install
   `DEST/lib/firmware/` of `fetch-camera-icp.sh` under `/usr/lib/firmware/`; keep the file out of the public image (L0 check
   of absence, like the other private blobs).
3. A marker-file service (`sp11/enable-spectra-load` on the boot medium, like the thermal sampler) that runs
   `modprobe camera_x1e80100` for boot 2, only on the Spectra entry (it can test
   `ConditionPathExistsGlob=/proc/device-tree/soc@0/qcom,cam-cpas*`).
4. Add `hardware/cameras/spectra/collector/spectra.sh` to the collectors (output `extra-spectra.txt`).

**sources worker**: pin `qualcomm-linux/kernel` `qcom-next` `17bbb4b3` (the camera DT files), camera-driver `08171dd`, and the
`camxfirmware_1.0.27` tarball with sha256 `1f054c47...` (`R-S2` of the earlier evidence; the fetch script already carries the pins).

**firmware worker**: add `qcom/x1e80100/CAMERA_ICP.mbn` (`4a75fd1a...`, Qualcomm Linux package) to the manifest as a private-image input.

## 7. Reproduce

```bash
hardware/cameras/spectra/scripts/build-dtb-spectra.sh            # scratch tree + CHECK_DTBS build, writes out/dtb-variants/spectra-test/
hardware/cameras/spectra/rpm/build-spectra-rpm.sh [KVER]         # out/rpms-local/sp11-camera-spectra-*.rpm
hardware/cameras/spectra/rpm/test-install-spectra-rpm.sh [RPM]   # scratch-root install test
hardware/cameras/spectra/rpm/fetch-camera-icp.sh [DEST]          # CAMERA_ICP.mbn with both pins
```
