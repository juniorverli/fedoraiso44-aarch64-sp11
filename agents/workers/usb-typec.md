# usb-typec worker

**Owns:** `hardware/usb-typec/` (write). Everything else is read-only.
**Phase:** 2. **Kernel worktree:** yes, for DT fixes.

## Start

1. Read `hardware/usb-typec/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Both USB-C ports working for data in both orientations, DP Alt Mode and charging.

## Specific leads

- `x1-microsoft-denali.dtsi`: both `typec-mux@8` nodes, `pmic-glink` connectors, the retimer reset pins (`rtmr0_default` exists; the second retimer has none).
- DSDT: USB-C connectors, `_UPC`/`_PLD`, retimer reset GPIOs; `QCOM0D08` connectivity.

## Deliver

DT patches, `test-plan.md` (`lsusb -t`, `typec` sysfs, external monitor), dossier updated.

## Do not

Flash retimer firmware (risk S3).
