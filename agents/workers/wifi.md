# wifi worker

**Owns:** `hardware/wifi/` (write). Everything else is read-only.
**Phase:** 2. **Kernel worktree:** only if a DT change is needed.

## Start

1. Read `hardware/wifi/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Wi-Fi working with the right board data and within Windows SAR limits.

## Specific leads

- `sources/linux/drivers/net/wireless/ath/ath12k/` board-data selection (board name string, `qcom,calibration-variant` / `qcom,ath12k-calibration-variant` in DT).
- `qcwlanhmt8380.inf`: which `bdwlan_*.elf` variant the INF selects for this SKU.
- `surfacesarmanager` and ACPI SAR methods.

## Deliver

DT variant property if needed, firmware request, `test-plan.md` (`iw dev`, `iw reg get`, throughput), dossier updated.
