# Windows Type-C REA task: tooling blocker

## Catalog and read-only references

Paths below are relative to `sources/windows/`. Catalog lookup preceded any
binary interpretation. SHA-256 was reproduced from the local driver bytes.

| Target | SHA-256 | Catalog language | State |
|:--|:--|:--|:--|
| `DriverStore/qcusbcucsi8380.inf_arm64_d09abbfbe1453cf0/qcusbcucsi8380.sys` | `01987fb04ef1528af9591da4a31d62efe93cae649c67a1fc00aa7884eedcea06` | `AARCH64:LE:64:v8A` | Active package established by the earlier Windows evidence; not opened in REA |
| `DriverStore/qcpmicglink8380.inf_arm64_283fc4d99dc4bd56/qcpmicglink8380.sys` | `00a73e2b050d2299a33ee6823756dc94ce2a5f9e70948fc563a05938803cae2b` | `AARCH64:LE:64:v8A` | Candidate; confirm active version before opening |
| `DriverStore/qcpmicglink8380.inf_arm64_a1a10dfa522d558c/qcpmicglink8380.sys` | `68b201a0b49a99d551c05dd3968800b90cb95e490d98227877c57aec0f71fe46` | `AARCH64:LE:64:v8A` | Candidate; confirm active version before opening |

`qcusbcucsi.../UCS0.bin` is catalogued as data, SHA-256
`c97973369a4408fcd262a1d8d50e9e6848683c0cf9ac8a01c86929b9ea92150c`;
do not disassemble it. The SurfaceRetimer0/1 payloads are catalogued as UEFI
FMP capsules, not ARM64 programs. Their INFs were read as UTF-16 text:
both declare version 128.3.6.0 and a firmware filename. There is no separate
SurfaceRetimer runtime `.sys` here to treat as an initialization driver.
Capsules remain unopened, unmodified and unflashed (S3).

The PMIC GLINK UTF-16 INFs declare 1.0.4175.2700 (2024-11-20) for
`..._283fc4d99dc4bd56` and 1.0.4111.7400 (2024-09-02) for
`..._a1a10dfa522d558c` (Verified, each INF's `DriverVer`; catalog hashes
`df44cd04c3c5a9828611a48d7cef6bdfc09ba092c4f7b8645cd9f33a593e87e3`
and `6526df13bc8b14d15d611cf018a814ec232e9e12e9e0581ef0f67556ded877e8`).
`live-inventory/pnp-present.json` confirms the `QCOM0C8E` device, but that
record has no bound-driver version/INF field; selecting the newer folder
as active from its date alone would be an inference. The Type-C driver's
active folder was established separately in the 2026-10-28 evidence.

The established ACPI observations still apply: `PMGK.UPAN` passes ADSP port,
orientation and mux data to `UCS0`; the latter declares retimer I2C, reset
and enable resources. See `2026-10-28-windows-and-charging.md`, with DSDT
locations and input hash. This does not reveal the driver's runtime sequence.

## Exact blocker

The read-only REA MCP `binary_session({})` call returned an error:

> MCP tool call requires approval, but approval policy is never

This occurred before opening a binary. No REA analysis ran; no function was
listed or decompiled. There is **no function address or evidence_id** to cite
and the MCP server's forced-language environment could not be verified.
No CLI fallback was used to bypass this policy. Protocol §9.6 assigns REA
setup failures to the sources worker; request R-S1 is in the dossier.

## Resume procedure for the sources worker/orchestrator

1. Make the REA MCP callable within the authorized read-only analysis scope.
   Run its Ghidra provider with
   `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A` in the **server process**;
   setting a shell variable in an unrelated exec does not configure MCP.
   Keep snapshots and any derived data under `out/rea/usb-typec/`.
2. Hold `flock out/.ghidra.lock` for the full open/list/decompile/close session.
   Confirm active PMIC GLINK package from the existing Windows inventory.
   Open each driver with provider `ghidra`, check hash/architecture, and call
   `list_procedures` before selecting actual function addresses.
3. Follow the Type-C driver's I2C target, PAN dispatch and per-port power
   callbacks: order of reset/supplies/XO, VDDIO-to-reset delay, status-register
   mapping for USB3 and orientation, and any initial-state query/replay.
   Compare GLINK PAN enable/ack ordering and UCSI startup with Linux.
4. Record input path, full SHA-256, forced language, function address and
   evidence_id per result. Keep pseudocode only in local REA snapshots.
   Do not decode data/capsule files as code, flash firmware, or publish blobs.
5. Only then choose the smallest supported behavioral patch and request an
   independent Claude cross-check under protocol §5.1 before `sw-ready`.

No Windows-derived power/reset/orientation fix is claimed by this session.
