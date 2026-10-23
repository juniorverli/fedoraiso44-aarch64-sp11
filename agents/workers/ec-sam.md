# ec-sam worker

**Owns:** `hardware/ec-sam/` (write). Everything else is read-only.
**Phase:** 2. **Kernel worktree:** only for DT/registry patches (`out/linux/ec-sam`).

## Start

1. Read `hardware/ec-sam/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Type Cover keyboard and touchpad, battery and AC, tablet switch, buttons and lid all working through SSAM and the DT on 7.3.

## Specific leads

- `sources/linux/drivers/platform/surface/surface_aggregator_registry.c`: the `sp11` group and the `microsoft,denali` match; compare each node with the SAM devices Windows enumerates (`HID\Target_KIP`, `{2DEDC554-...}`, `{9086E8DA-...}\Target_SAM`).
- `MSHW0040` buttons and `MSHW0005` laptop/slate indicator in the DSDT: GPIOs or PMIC.
- Battery duplication with `qcom_battmgr` (request from `dsp-subsystems`).

## Deliver

Patches if needed, `test-plan.md` (evtest per input, `upower -d`, tablet-mode switch), dossier updated.

## Do not

Change charge limits or fan behaviour (risk S6). Flash Type Cover or SAM firmware (risk S3).
