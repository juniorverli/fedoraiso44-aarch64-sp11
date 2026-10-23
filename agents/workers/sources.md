# sources worker

**Owns:** `sources/README.md`, `sources/sources.toml`, `scripts/verify-*`, `sources/rea.md` (REA setup notes). Never edits the contents of `sources/windows` or `sources/linux`.
**Phase:** 0, then on demand.

## Mission

Every worker reads the same, pinned, trustworthy inputs, and the reverse-engineering tools work for all of them.

## Tasks

1. **Re-run the provenance checks** of `sources/README.md` §2 and record the date and result.
2. **Active driver versions.** For every INF with more than one package folder (for example `qcpep.wd8380`, `qcsubsys8380`, `qcadsprpc8380`), determine which one Windows bound to the present device (`live-inventory`, `driver-inventory.txt` `DriverVer`, PnP data). Write a table `sources/active-packages.md` (package folder, version, active yes/no, evidence). Component workers analyse the active one.
3. **Official package check (optional).** Find Microsoft's current Surface Pro 11 (Snapdragon) driver and firmware MSI on the Microsoft download site, record its version and URL, and compare its INF `DriverVer` values with the local store. Download only after the operator approves; store outside git under `out/`. Report newer versions; do not replace the local store.
4. **REA.** Verify `~/tools/rea`, Ghidra and JDK (`rea doctor --provider ghidra`), pin versions and SHA-256 in `sources.toml [tools]`. Register REA as an MCP server for this repository at local scope and record the exact command, so every worker uses the same tool. Note that the installed REA is a locally patched build and record what the patch changes.
5. **New inputs** asked by other workers (linux-firmware release, lore series, Fedora package lists): fetch, pin in `sources.toml`, announce in your hand-back.

## Do not

- Trust `sources/windows/rea-*` folders as inputs.
- Put any downloaded binary in git.
