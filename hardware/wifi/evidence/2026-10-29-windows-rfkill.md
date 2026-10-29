# Windows WLAN policy reproduced through REA MCP

## Target and method

Catalog row: `DriverStore/qcwlanhmt8380.inf_arm64_f6c170edbe88d474/qcwlanhmt8380.sys`,
PE ARM64 code, SHA-256
`ca884ce1a22113194f3c467f36abc39afb0c137e5a7a8e2697420438b21e4115`.
Read Linux v7.3, upstream/lore, captured ACPI, INF and registry first.

On 2026-10-29, started a separate local REA **MCP** stdio server (`rea mcp`)
under `flock out/.ghidra.lock`, with
`REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`, `GHIDRA_MAXMEM=4G`,
`REA_GHIDRA_STARTUP_TIMEOUT_MS=660000`. Provider explicitly `ghidra`.
`open_binary` reports ARM64 and the catalog hash. `list_procedures` was
called before decompilation; it returned 7320 procedures, including every
entry below. Analysis reports Ghidra 12.1.4, language selection
`configured-v1`, language `AARCH64:LE:64:v8A`, profile digest
`34d7ce5b71bd3a8e2d8fdc489bffd930ec03bd3ff41b91af5ee8a596322ac6f7`.
Procedure-list evidence:
`ev_081054c6fb7cd2bb26e913304ff682db20af543e2417f790e45370b739437841`.

All raw MCP responses/pseudocode stay in `out/rea/wifi/m9/`.
`close_binary` saved `out/rea/wifi/m9/qcwlan.snap` (21 retained evidence
records) and closed Ghidra; the MCP process then exited, releasing the lock.
No target bytes or pseudocode enter git. Original PDB names/types are not
established: function labels below are inferred from their own log strings,
not claimed as loaded debug symbols. This is static shipped-driver analysis,
not an observed Windows execution trace.

## Hardware rfkill policy

All rows are **Verified** static-code observations in the target above.

| Entry | Observation | REA evidence ID |
|:--|:--|:--|
| `0x140028700` (`MpAcpiGetFuncDisableFlag`) | Calls the ACPI helper with function 2 and copies the returned 32-bit integer into adapter offset `0x8d5c` | `ev_78d31f4453d7f241b12bbc93fbb29e72bdd32f04913e8653d78ad133b35cc326` |
| `0x14002dbf0` (`MpAcpiInitApply`) | Fetches ACPI data and enables the NIC hardware-rfkill configuration flag at parameter-block offset `0x6c` only when bit 2 of the returned disable/control flags is set | `ev_f5ad09da02ed892145e25791696075a43a8dc6e0236c13213ba254f347330704` |
| `0x14000afb0` (`Hw11NicInitialize`) | Returns without calling hardware-rfkill setup when that parameter-block flag is zero | `ev_306add319ad5fedf5871e7d2a3a78c16b37080d9a60eb4e7d7881123c213fec6` |
| `0x14000bbd8` (`Hw11RFKillCfg`) | If setup is enabled, registers an rfkill event handler, then calls the config function with pin `0x30` (48), config 0, on-level 1 | `ev_f990e5fd5707d2daef2ce3e50cafa01f08fe971eefbc670f35afde8a53db1126` |
| `0x14018aae8` (`wmi_hw_rfkill_cfg`) | Packs the supplied pin/config/on-level and sends WMI pdev parameter `0x31` (HW_RFKILL_CONFIG); it does not use a different magic GPIO to fix the Surface | `ev_45966b5a82bae2ecde321ff7d4777ef2db7715759272270361f9b9fb34bd53b2` |

Captured Surface firmware returns support bitmap `0x85` for function 0 and
control flags `0x60` for function 2
(`sources/windows/live-inventory/acpi/dsdt.dsl:59169-59200`). Thus function 2
is supported and its hardware-rfkill enable bit is clear. Linux already
interprets that same bit as opt-out on ACPI (`acpi.c:375-388`), while
`core.c:75-99` has no corresponding Surface DT check in pinned v7.3.

**Inference (strong):** Windows policy leaves this unusable hardware input
disabled on the Surface; the DT Linux path misses that opt-out and turns it
on when firmware advertises capability. This explains the M8 sequence of
setup, OFF event, hard block. No claim is made that an arbitrary registry
override or every other code path was exhaustively ruled out. The minimum
port is upstream patch 0002's board/hardware quirk, not a new GPIO value,
GPIO polarity guess, ACPI emulation, or userspace hard-block bypass.

## Board-file selection reproduced

The same MCP session reproduced the previous results:

- `0x140147b80`: id `0xff` takes the default `bdwlan` + `.elf` branch (unless
  the separate `.g` flag applies), evidence
  `ev_931be55bbc57d5ff644a3266652976731e8cd695e3fc8d98a2ecb81b82edfe21`.
- `0x14014a478` (`wlfw_get_bdf`): cache/DPP is attempted first; the generic
  Qualcomm `17cb:1107` / subsystem-vendor `17cb` branch uses that builder,
  then falls back to the configured default filename, evidence
  `ev_c0c95236cb74085149c590051d97acac9f7dd984c39c3b53feead233172dffbf`.
- INF default and captured device registry both name `bdwlan.elf`
  (`qcwlanhmt8380.inf:896`, `live-inventory/wlan/class-wcn7850.txt:15`).
  M8 reports board id `0xff`.

The filename conclusion remains **Inference (strong)** for actual Windows
runtime because cache/DPP precedence exists. F2 is an explicitly requested
parity candidate, not a claim that its opaque calibration/TX tables or
Windows SAR state were completely decoded. `bdwlan.elf` is catalogued as
**data-in-ELF**, language none; it was never disassembled.

## Memory allocation observation and limit

`0x140007988` calls the Windows address-bounded contiguous-memory allocator
and obtains the physical address when successful, evidence
`ev_b926d930698554b8c3f496436b99d4297cfe5b6b0f7f3142a0282370f27d40d0`.
This is **Verified** allocator code, but its callers' effective address bounds
for the live QMI host-DDR request were not established. Do not infer a
Windows carveout address or port the wrapper's constants as hardware limits.
Linux patch 0003 is instead justified by Linux's actual coherent DMA mask,
the M8 CMA address and the buddy-order limit (M8 evidence). Neither a Windows
binary blob nor a guessed reserved-memory region is required for that fix.
