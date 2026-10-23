# storage worker

**Owns:** `hardware/storage/` (write). Everything else is read-only.
**Phase:** 2. **Kernel worktree:** no.

## Start

1. Read `hardware/storage/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Confirm NVMe works and define a safe dual-boot install procedure.

## Specific leads

- `x1-microsoft-denali.dtsi` `&pcie6a`; Anaconda behaviour with an existing Windows/BitLocker disk.

## Deliver

Install procedure in `evidence/`, `test-plan.md` (read-only `lsblk`, `nvme list`, `smartctl`), dossier updated.

## Do not

Write to the disk in any test (risk S4). Install only with the operator present.
