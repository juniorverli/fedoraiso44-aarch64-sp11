# sensors worker

**Owns:** `hardware/sensors/` (write). Everything else is read-only.
**Phase:** 4. **Kernel worktree:** no.

## Start

1. Read `hardware/sensors/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Orientation and ambient light available to GNOME through the SSC userspace stack.

## Specific leads

- `surfacepro_snscfgcrd8380.inf_arm64_*`: JSON registry files name candidate chips (`lsm6dsv`, `ak991x`, `tcs3430`, `tmd2755`, `lps22df`), both `crd` and `idp` variants. Find which set this board uses.
- Fedora 44 or Copr packages for `hexagonrpcd`, `libssc`, `iio-sensor-proxy` with SSC support.

## Deliver

Install plan for userspace and registry files, `test-plan.md` (`monitor-sensor`), dossier updated.

## Do not

Write to the sensor registry on the DSP beyond what the userspace stack does by design.
