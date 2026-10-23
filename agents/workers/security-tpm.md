# security-tpm worker

**Owns:** `hardware/security-tpm/` (write). Everything else is read-only.
**Phase:** 4. **Kernel worktree:** yes (`out/linux/security-tpm`).

## Start

1. Read `hardware/security-tpm/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

A TPM 2.0 device on Linux through the QSEE TPM application, and a clear Secure Boot story for the ISO.

## Specific leads

- `sources/linux/drivers/firmware/qcom/qcom_qseecom*.c`, `qcom_qseecom_uefisecapp.c` as the model for a QSEE client.
- `live-inventory/acpi/tpm2.dsl` (start method), REA of `QcTrEE.sys` for the command transport.
- Upstream search for a QSEE TPM driver.

## Deliver

Design note, patches, `test-plan.md` (`tpm2_getcap`), dossier updated.

## Do not

Clear or provision the TPM. Change Secure Boot keys.
