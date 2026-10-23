# power-thermal worker

**Owns:** `hardware/power-thermal/` (write). Everything else is read-only.
**Phase:** 4. **Kernel worktree:** yes (`out/linux/power-thermal`).

## Start

1. Read `hardware/power-thermal/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Linux thermal behaviour no hotter than Windows, fan control, and working s2idle.

## Specific leads

- `hamoa.dtsi` thermal zones versus Windows thermal policies (`QCOM0CF2`-`QCOM0CFC`, `MSHW0187/0188`).
- REA: `qcpep8380.sys` thermal tables, `surfacethermalpolicy`, SMF fan/thermal clients.
- Requests from `gpu` (GPU limits) and `npu` (NSP limits).

## Deliver

Mapping table in `evidence/`, DT patches, `test-plan.md` (stress with temperature logging), dossier updated.

## Do not

Raise any limit above the Windows value (risk S6).
