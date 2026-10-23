# usb4 worker

**Owns:** `hardware/usb4/` (write). Everything else is read-only.
**Phase:** 4. **Kernel worktree:** yes (`out/linux/usb4`).

## Start

1. Read `hardware/usb4/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Scope the USB4 host-router work: register map, bring-up sequence, tunnels, and an estimate. Implementation only after the operator approves the scope.

## Specific leads

- REA of `QcUsb4Bus8380.sys` and `QcUsb4Filter8380.sys`; `qcppx8380.sys` for PCIe tunnel root complexes.
- `sources/linux/drivers/thunderbolt/` host interface expectations.

## Deliver

Scope note in `evidence/`, dossier updated.

## Do not

Flash dock or retimer firmware (risk S3).
