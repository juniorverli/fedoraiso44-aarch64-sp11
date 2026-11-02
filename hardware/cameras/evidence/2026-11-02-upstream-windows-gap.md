# Upstream and Windows streaming gap, 2026-11-02

Scope: review of pinned 7.3, camera patches and existing device/Windows evidence; online
series discovery, not a complete patch-by-patch diff against a locally pinned upstream
snapshot. No code, device, kernel or ISO build. Grades describe evidence, not successful
streaming. The sources owner must fetch and pin any external series before it is imported
(protocol §2).

## CAMSS and PHY

| Area | Grade and comparison | Next action |
|:--|:--|:--|
| CSIPHY C-PHY programming | **Verified in patch** 0009 adds legacy integrated CSIPHY v2.1.2 C-PHY init, trio masks, rate selection and settle; 0010 parses C-PHY endpoints. **TBD** exact sequence equivalence and physical operation. [Neacsu v3](https://lore.landau.one/lkml/db2fffdd-634c-4728-a2a6-2ab1816b07ba%40oss.qualcomm.com/T/) reports 2.4 Gsym/s tested on Surface, but targets the separate generic PHY provider and depends on other series. Review notes say v3 superseded, so do not claim this is current merged code. | Compare registers, lane mapping and computed settle at our exact rate after pinning; no direct cherry-pick into legacy architecture. |
| CSID and rate | **Verified in patch** 0007 tracks C-PHY and applies 57/25 equivalent bit-clock conversion, 0008 sets CSID 680 PHY type, 0010 validates lanes. [CAMSS rate discussion](https://lore.landau.one/lkml/20261017035221.3816464-3-anusha.nandi%40oss.qualcomm.com/T/) identifies CSID 680 select as necessary for X1E. **TBD** value and clock calculations on our live build; no capture proves them. | Inspect actual selected PHY/CSID timer/rates on failed front capture; do not combine incompatible PHY API and legacy units without a full conversion. |
| VFE, power domains and ICC | **Verified** pinned `sources/linux/drivers/media/platform/qcom/camss/camss.c:5729` selects X1E CSIPHY, CSID, VFE and ICC resources; 0003 adds named ICC paths and IFE/TITAN domains. CCI/CAMSS bind in M16. **TBD** actual bandwidth, clock votes and runtime domain transitions under frame load. | Compare SoC resource tables/DT with pinned upstream DT v7 and check clock, ICC and domain state during a gated stream; no particular missing VFE/ICC patch established. |
| PHY API rearchitecture | **Verified** [O'Donoghue v20 PHY API testing](https://lkml.iu.edu/2609.3/06803.html) and [X1E DT v7](https://lists.openwall.net/linux-kernel/2026/09/25/1821) describe separate PHYs; the latter reports Dell D-PHY streaming. It is a different graph/binding architecture from 0003 and 0006–0010. | Treat generic C-PHY PHY mode/configuration helpers, standalone Qualcomm PHY provider, CAMSS PHY API integration, PHY-node DT, and companion CSID/C-PHY rate patches as a **migration set missing from our tree**, not individually proven prerequisites for legacy capture. Pin exact latest versions and dependencies; check post-v20/v7 and merge status. |
| Sensor graph | **Verified** M16 binds two RGB sensors but registers neither sensor link nor subdev nodes; unbound IR remains a strong notifier-completion **Inference** ([M16 evidence](2026-11-02-m16-safe-camera-probe.md)). | Integrate RGB-only exclusion and inspect graph before introducing another driver. The exclusion exists as a DT include, not camera patch 0022 in this worktree; verify orchestrator's integration separately. |
| Rails | **Verified Windows vote** C and J pairs in [seven questions](2026-10-30-rea-seven-questions.md); Linux DT describes C pair. J-pair retention under all relevant runtime states and pm8010 input parents are **TBD**; previous claim that omission is harmless is unproven. | Observe rails safely; obtain board data, do not guess supplies. |

External searches found C-PHY v3 and X1E DT v7/PHY API v20; they do not establish
these are the latest versions everywhere or that their commits are merged. The claimed
Surface captures in those threads are other people's reports, not our device evidence.
Our exact patch-to-upstream line-by-line diff and the complete current dependency list
remain open. No independently justified additional CAMSS patch is established by probe
logs alone.

## Windows package and mode evidence

Catalog paths below are relative to `sources/windows/DriverStore/`; catalog contains full
SHA-256 and classifies `.sys` as ARM64 `AARCH64:LE:64:v8A`, module/resource `.bin`
as data, never disassemble. INF extension packages are configuration/data, not an
assumption that each contains executable sensor code.

| Sensor | Module and resource package, verified catalog | Linux coverage / remaining gap |
|:--|:--|:--|
| OV13858 | `surfacecamrearsensor_extension8380.inf_arm64_9e667d808f1a7021/`: `com.surface.sensormodule.rfc_ov13858.bin` SHA-256 `f8f60e79b77bd3d5896cb04167ee428455e1a241f1ff9e50abee6b4dacfe6b14`, `CAMS_RES_MSHW0491.bin` SHA-256 `2d356bbfaf07ced1e5c03014a5c496b12107f5dc489c4333052565d5a5a5dcc2`; `surfacecamrearsensor8380` is sensor kernel subdriver. | 0002 power/reset, 0011–0014 imported private modes; rear probe and three mode loads verified, transmission not. Built-in mode GRBG10 differs from Windows blob mode BGGR10. Missing autofocus and calibrated SoftISP; compare power and mode programming on device. |
| IMX681 | `surfacecamfrontsensor_extension8380.inf_arm64_5a4c66ce4812274e/`: `com.surface.sensormodule.ffc_imx681.bin` SHA-256 `f7dd81be64153fd3f0da8e6288ee1b9906b7bf51b773a98496934d76dc96a45c`, `CAMF_RES_MSHW0490.bin` SHA-256 `379a03154511922428ea27f56de625f579f39ca483fb97398953278b6b5f2851`; `surfacecamfrontsensor8380` is sensor kernel subdriver. | 0016 requires locally generated private init/mode/stream data and implements controls, power and reset. Probe alone does not prove ID read, C-PHY, mode timing, gain or live Bayer. Window data says RGGB10; verify image and timing. |
| VD55G0 | `surfacecamauxsensor_extension8380.inf_arm64_84ddd55dc933cac9/`: `com.surface.sensormodule.aux_vd55g0_MSHW0492.bin` SHA-256 `e574db7eb28231d3fa4f5eee5c1861919125d8ec7a753fc7a0708606e1f1a794`, `CAMI_RES_MSHW0492.bin` SHA-256 `fb058d3c966f4b48412d48c2de7f58b861103a8aa06f0bb8c1d198e12431d908`; `surfacecamauxsensor8380` is sensor kernel subdriver. | No driver in pinned 7.3; current 0017/0019 only describe it. Windows data has a 601-record mode (including polls), mono RAW10; generator rewrites an inferred strobe output to input, but has no bound consumer and does not prove hardware safety. |

The common `qccamplatform8380` is the platform/indicator driver; `surfacecamplatform_ext8380`
provides platform-specific configuration. `CAM*_RES`, `SCFG_*`, sensor modules and
`com.surface.tuned.*` are separate resource, identity, register/mode and tuning inputs,
respectively; offsets, hashes, sequence count and confidence are in
[format evidence](2026-10-30-module-data-format.md) and
[seven questions](2026-10-30-rea-seven-questions.md). Rear power timing has prior PEP
analysis; front clock-before-rails in 0016 and all exact front/IR rail order and delays
need a direct sequence comparison, not inference from successful binding. GPIO225 and
GPIO105 privacy mapping still needs independent reproduction and visible verification;
0020 implements shared LED accounting but has not had its KUnit suite run. ISP tuning
blobs are not decoded into validated libcamera calibration.

## VD55G0 driver path

New finding: Linux work exists outside the pinned base. [ST reference driver](https://github.com/STMicroelectronics/vd55g0-linux-driver/blob/a05627b0f6d8775aa54b6fa306e91f425f2cbf9e/vd55g0.c),
[Lebedev's posted driver and follow-up](https://lore.landau.one/lkml/20261020142641.24808-1-lsa.uz%40pm.me/T/),
and [vd55g1 extension discussion](https://lkml.iu.edu/hypermail/linux/kernel/2610.1/10208.html)
are candidates. [Surface low-rate fix](https://lore.landau.one/lkml/20261016102709.30467-1-geocausa%40gmail.com/T/) reports 840 Mbps needs a different minimum line length; the register-width correction applies only to its stated unmerged prerequisite. Verify exact revision and licensing and all follow-up corrections before choosing a backport. Reports and competing series are not proof of our sensor cut or working driver.

A driver is feasible, but not justified to implement from incomplete Windows decoding now:
it needs chip/revision identification, correct revision-specific firmware policy and license,
rails/reset/MCLK and delays, CCI register widths and byte order, supported RAW8/10 formats,
lane rate/blanking/timing and stream state/polls, runtime PM, V4L2 controls, graph and
privacy LED integration. It must force sensor strobe inactive and leave PMIC illuminator
and flash disabled; review every register/firmware side effect before any IR test. No
requirement to stream IR to resolve the RGB notifier.

## REA follow-up

REA MCP `open_binary` returned **“MCP tool call requires approval, but approval policy is never”**.
No new REA analysis was performed. Orchestrator: force `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`,
list procedures before decompilation, and retain hashes, function addresses and evidence IDs.
Prior REA used auto language and must be independently reproduced:

1. `qccamplatform8380.inf_arm64_16d44e9aca3becfb/qccamplatform8380.sys` SHA-256 `836714ec41f92f45af363d7bf3c9b9cfc2cccdbd19a1c57f355b471068648049`: `Get_PrivacyLED_ACPI_Info` at `0x140001884` and writer `FUN_140001b38`; trace sensor IDs from the front, rear and auxiliary driver callbacks through LED acquisition/release and polarity to corroborate mapping and stream lifecycle.
2. `surfacecamfrontsensor8380.inf_arm64_747e2ddb5eb5a22b/surfacecamfrontsensor8380.sys` SHA-256 `80a8e4a1ef8f0dacfbc2e8c6919cb269993057ffd3133c2ef7016ff742e46f03`, `FUN_140001b48` and its callers: resource/SCFG parsing; trace power sequencing and IMX681 ID, gain, clock and reset. List procedures to identify exact sequence executor if distinct.
3. `surfacecamauxsensor8380.inf_arm64_7d23cd8fdfa9b39f/surfacecamauxsensor8380.sys` SHA-256 `e5b6b064f39cf239ab07e22ca2434e3c08c93b691dc7d27cebb90861226efa75`: list procedures, locate `CameraSensorDriver_ProcessWaitCmd` and register-table execution/SCFG parser and stream callbacks; verify poll units, sensor GPIO/strobe side effects and auxiliary LED ID. Exact addresses are TBD until enumeration.
4. `surfacecamrearsensor8380.inf_arm64_8fbcacb272007d57/surfacecamrearsensor8380.sys` SHA-256 `b7d7a278c5e7b92ebf35f870a7e06cbad670ffb35bfaf40106e27b09bf33fabb`: list and trace stream/LED and resource-sequence consumers; compare 0002 ordering with `CAMS_RES_MSHW0491`. The PEP handler `qcpep8380.sys` `FUN_140128170` is the existing delay-unit lead.

These requests do not authorize emitter or flash operation. Sequence results must be
reported as evidence, never copied as proprietary binary data into git.
