# QCOM0CF7: GPU limits policy hand-off

Date: 2026-10-24. Owner for the remaining policy work: `power-thermal`.
No thermal policy or kernel change is proposed here.

**Verified:** `sources/windows/live-inventory/pnp-present.json`, SHA-256
`7c6c4ab8a82ee2b5b1df32407ff69e1f7bf72fdda8ba4fe4c8adc550006e772b`,
entry `InstanceId = ACPI\QCOM0CF7\0`, identifies the present device as
`Qualcomm GPU limits Policy Device`, hardware ID
`ACPI\VEN_QCOM&DEV_0CF7&REV_008A`.

**Verified:** `sources/windows/live-inventory/acpi/dsdt.dsl`, SHA-256
`8a7b849b9ac2148a9806d967612eb0d5195020c3e29ffd834b837767256a8ede`,
lines **67096–67126**, defines `TZ20` with `_HID = QCOM0CF7`, `_TZD` pointing
to `\_SB.GPU0`, and `_DEP` pointing to PEP0 and PMIC. `_HRV` uses `PHRV()`
except for the SDFE 0x9A branch; this dump has SDFE 0x88 (line 276), FPID
0x8A (line 310), and `PHRV()` returns FPID (312–316). Those named values are
not a GPU speed-bin fuse read. This zone definition does not specify usable
trip temperatures or mitigation thresholds.

**Verified installer data, active package TBD:** the two catalogued
`qcpep.wd8380` INFs map the generic `ACPI\QCOM0CF7` at decoded line **158**
to `GpuLimitsTz_R2_Device`. The Purwa-specific revision 0100 entries are a
different install section and should not be copied to this REV 008A device.

| INF under `sources/windows/DriverStore/` | SHA-256 | Relevant decoded lines |
|:--|:--|:--|
| `qcpep.wd8380.inf_arm64_eb671871f8fef501/qcpep.wd8380.inf` | `4f93db0ae24ee5cd20fe34232c53d4ed85bc3acbf46a3bb36d2a2e8b6e192c0e` | 726–734: R2 install/HW/service; 731 applies `GpuLimits_R2`; 734 associates service `qcpep`; 806–808: `LimitsConfig`, CGLC/OGLC list |
| `qcpep.wd8380.inf_arm64_f72f4ad672197eb8/qcpep.wd8380.inf` | `e6cceb7dc3a49546e3f83ac87932b28d2ffd212a645e65683fcdf243c3797b47` | 707–715: same R2 binding; 787–789: `LimitsConfig`, CGLC/OGLC list |

Each file was looked up in `sources/binary-catalog.tsv` before text decoding.
The R2 hardware section installs a CGLC binary policy and lists CGLC/OGLC as
the limit configuration names. Their numeric meaning was **not** decoded in
this GPU session, and presence in an INF does not establish which version is
currently bound. No temperature/current/power values are inferred here.

**Inference:** Windows GPU throttling involves a separate PEP thermal policy
device; a correct maximum OPP alone does not establish equivalent Linux
thermal mitigation. Linux hamoa exposes GPU cooling cells at
`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:4008`, but this is not
evidence that a Surface-specific trip/cooling map exists or is correct.

**Request:** `power-thermal` should confirm the active qcpep package and bound
policy, decode the GPU limits configuration, establish its relationship to
thermal sensors/Surface policy, and decide what equivalent Linux cooling
binding is required. Keep risk S6 in force; do not raise thermal limits.
Provide the GPU load-test release condition before the 30-minute acceptance
tests are attempted.
