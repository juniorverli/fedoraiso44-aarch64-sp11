# npu worker

**Owns:** `hardware/npu/` (write). Everything else is read-only.
**Phase:** 4. **Kernel worktree:** no.

## Start

1. Read `hardware/npu/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Establish what can run on the Hexagon NPU under Linux and document a working FastRPC path to the CDSP.

## Specific leads

- `sources/linux/drivers/misc/fastrpc.c`, the `fastrpc` node under `remoteproc_cdsp` in `hamoa.dtsi`.
- Windows: `qcnspmcdm8380` (driver and user libraries) to learn the session model, not to reuse binaries.
- Licensing of Qualcomm's Linux AI runtime.

## Deliver

Feasibility note in `evidence/`, `test-plan.md` for a FastRPC smoke test, dossier updated.

## Do not

Redistribute any QNN or Windows library (risk S5).
