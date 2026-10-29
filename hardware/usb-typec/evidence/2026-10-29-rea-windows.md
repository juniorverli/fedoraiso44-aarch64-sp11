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
