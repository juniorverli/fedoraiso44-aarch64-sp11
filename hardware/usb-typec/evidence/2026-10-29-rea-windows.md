# Windows Type-C REA result: qcusbcucsi8380.sys

## Session record (protocol §9.2)

| Item | Value |
|:--|:--|
| Binary | `DriverStore/qcusbcucsi8380.inf_arm64_d09abbfbe1453cf0/qcusbcucsi8380.sys` (newer of the two packages, file dated 2025-06; the other, `..._d98e3aa1adc68c71`, is dated 2024-12 and was not opened) |
| SHA-256 | `01987fb04ef1528af9591da4a31d62efe93cae649c67a1fc00aa7884eedcea06`, equal to the REA result, `sha256sum` and the catalog in `2026-10-29-rea-access.md` |
| Format, architecture | PE, arm64 |
| Language | Auto-from-header (`loader` and `language_id` = `auto-from-header` in the REA analysis profile). It resolved to arm64 for this PE, which is correct. The `REA_GHIDRA_LANGUAGE_ID` override of §9.2 was not applied by the server; the outcome matches the catalog language `AARCH64:LE:64:v8A`. |
| Provider | Ghidra 12.1.4 |
| Evidence ids | search_strings `ev_9e63c1b5...`, `ev_0c2cb1a8...`; xrefs `ev_a2677f1b...`, `ev_4fe67220...`, `ev_418b16c2...`; pseudo-code `ev_09395ab4...` (role-switch registry function, entry 0x140020178), `ev_ae93871...` (I2C target setup, entry 0x140037e80) |
| Closed | yes, `close_binary` at the end; only this binary was opened |

## Findings

| # | Finding | Grade |
|:--|:--|:--|
| W1 | The string inventory has no match for orientation, PAN, retimer, mux, GPIO, polarity, pin assignment, USB3 or connector. Only the DMF I2C target (`I2cTarget`, `ZlDMF_CONTEXT_I2cTarget`), the context names `USBC_DMF_DEVICE_CONTEXT`, `USBC_DRIVER_CONTEXT`, `USBC_DEVICE_CONTEXT`, `USBC_PORT_CONTEXT`, `USBC_UCSI_CONTEXT`, and the registry names `RoleSwitchMode`, `OSDefaultRoleSwitchMode`, `USB4HREnumMode` appear. Ghidra lists only defined strings, so absence is not proof. | Verified (inventory), Unknown (completeness) |
| W2 | The only code that references `RoleSwitchMode` reads it per index from the registry device parameters of three ACPI devices (`QCOM0C8B` index 0, `QCOM0C8C` index 1, `QCOM0D07` index 2), falling back to `Control\USB`. This is role-switch policy for the URS controllers. It does not touch orientation, retimer or USB3 enable. | Verified |
| W3 | `USB4HREnumMode` has one reference, in a registry-policy routine. USB4 host-router enumeration policy, no lane or retimer action visible. | Verified (reference), Inference (purpose) |
| W4 | The I2C target is the generic DMF module configured with fixed sizes and callbacks. The setup routine contains no device address, register offset or command bytes. The PS8830 register traffic is therefore not in this binary's visible code; it is probably driven from the `UCS0.bin` PEP table or other drivers (not opened, S5/§8 forbids decoding the table here). | Inference |
| W5 | The driver structure (UCSI context, per-port context, role switch policy) is that of a UCSI client. Orientation, partner mux and PAN state therefore most likely arrive from ADSP/ACPI (`qcpmicglink8380`), consistent with the earlier README statement. | Inference |
| W6 | Not found: any orientation, USB3-enable, retimer-command or GPIO sequence. Not established: whether Windows enables the retimer before or after the orientation event. | Unknown |

## Comparison with Linux 7.3

Linux (`link-map` §3): the PS8830 is held in reset with supplies off after probe (`ps883x.c:454-455`) and is released only by `typec_retimer_set()` (`:152-167`) after a PAN notification handled by `pmic_glink_altmode.c:349-394`. Windows evidence from this binary neither confirms nor contradicts that ordering, and shows no extra GPIO or I2C step. The Denali DT already carries the reset, supply and orientation GPIOs (README §2). No behavioral difference was established, so no patch 0003 is proposed.

## Next step

Open `qcpmicglink8380.sys` (hashes in `2026-10-29-rea-access.md`, active version unconfirmed) to find the PAN enable/ack and mux-state handling. M9 `usbdbg` trace with patch 0002 remains the primary route.

## Second pass (2026-10-30): qcpmicglink8380.sys function bodies

Binary: `DriverStore/qcpmicglink8380.inf_arm64_a1a10dfa522d558c/qcpmicglink8380.sys`
(newer, dated 2025-05-20), SHA-256 `68b201a0...e46`, see catalog
`sources/binary-catalog.tsv` line 517 (`68b201a0b49a99d5...`); REA, `sha256sum`
and catalog agree. Ghidra 12.1.4, language auto-from-header arm64 (the section
9.2 forcing is still not applied by the server). One binary open, closed after.
Evidence ids: `ev_4a4ee4a7...` (RX dispatcher), `ev_bc73ccf0...` (platform
config), `ev_f6e727ce...` (strings), `ev_57d6b12e...`, `ev_130da267...` (owner id
constant search). Addresses are image-relative VAs.

Verified:

- The PMIC-GLINK RX dispatcher is `0x140001e50`. It takes a received message
  (header words: owner id, type, opcode, data) from five per-client buffers,
  accepts only type 2 (notify) and switches on the owner id. Owner ids seen:
  `0x800a` (battery manager), `0x800b` (USB-C), `0x800c` (USB-C pin assignment,
  PAN), `0x800e` (an OEM notification owner) and `0x8010` (a status owner). They
  equal the Linux `PMIC_GLINK_OWNER_BATTMGR/USBC/USBC_PAN` values for the first
  three. The movz constants for `0x800b` and `0x800c` occur only in this
  dispatcher, not in any other function.
- Owner `0x800b` notification: Windows does not parse a connector state or
  orientation here. If the second data word is zero it evaluates an ACPI method
  through the ACPI eval interface (signature `AeiIUSBN`, argument `0x80`), i.e.
  it forwards the USB-C change as an ACPI `Notify(0x80)` to the UCSI/USB-C
  device. UCSI traffic therefore runs over ACPI (shared memory), not through
  glink messages parsed in this driver.
- Owner `0x800c` (PAN) notification: the first byte of the 16-byte payload must
  be below 4, otherwise the message is dropped with an error trace. Windows
  stores the payload in two globals and evaluates an ACPI method through the
  same interface (signature `AeiCUPAN`), passing the 16 payload bytes. A failed
  or "busy" ACPI return is logged with error and propagated; there is no retry.
- Owner `0x800e` with the upper 16 bits not equal to 1 is forwarded to ACPI as
  `AeiIOEMN` with the data word; with upper bits 1 it goes to a kernel callback
  object instead.
- Registry: `PlatformConfig\UsbcPinAssignmentNotifyEn` is read by the platform
  config routine (`0x14000da20`) and the INF sets it to 1 (enabled). The same
  key family holds the ulog switches (`UlogInitEn`, `UlogLevel`, categories),
  which are pmic-glink logging, not USB-C data.

Inference:

- Windows uses ACPI as the retimer and mux consumer: the PAN payload (port,
  orientation, mux mode, pin assignment) is handed to an ACPI method, and the
  PS8830 programming is done by the platform firmware table or its PEP, not by
  this kernel driver. This matches the existing W4 and W5 findings.
- No PAN ack: no code path in the dispatcher builds a request with owner
  `0x800c` or opcode `0x11`; the only outbound traffic is the ACPI evaluation. Windows
  may acknowledge through another driver or the ACPI method itself (not
  decoded). Linux sends `ALTMODE_PAN_ACK` (`pmic_glink_altmode.c`) after setting
  the mux.
- The `0x13` (USBC notify) and `0x15` write ids used by Linux are not
  distinguishable in this binary because Windows moves the data through ACPI.

Unknown:

- The PAN payload bit layout as Windows reads it beyond the "byte 0 below 4"
  check, any USB3-enable or retimer-reset message, and where (if anywhere)
  Windows sends `PAN_EN` (`0x10`). The platform-config flag is read, but its use
  was not traced because the decompiled store looked unreliable.
- Which ACPI methods `AeiCUPAN`/`AeiIUSBN` resolve to (ACPI tables were not
  re-read in this pass).

### Comparison with Linux 7.3 and decision

Linux (`pmic_glink_altmode.c`: PAN notify `0x16`, enable `0x10`, ack `0x11`,
write request `0x15`; `ucsi_glink.c`: `0x11/0x12` buffer access, notify `0x13`)
already handles every message id that Windows' dispatcher handles for the
USB-C owners: connector change (via UCSI) and PAN. Windows shows no extra
message that enables USB3 or resets a retimer over pmic-glink. The visible
differences are architectural (ACPI consumes the notifications) and cannot be
turned into a minimal Linux patch without the ACPI/PEP data. No patch 0003 is
written. The ps883x handling is unchanged by this pass. The M9 `usbdbg` trace
from patch 0002 stays the next decisive step (check whether `PAN_ACK` is needed
by the ADSP before it reports the next state).
