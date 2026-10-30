# M10: firmware crash with the derived Windows board file

Grades: Verified (read in a log, source or binary), Inference (reasoned, not proven), TBD.
Private device values (addresses, serials) are not recorded here.

## What the M10 log shows (Verified)

Kernel `7.3.0-65.sp11.7.fc44`, ath12k `debug_mask=48` (0x30).

1. The derived `board-2.bin` (2520880 B) was requested, name `...qmi-chip-id=2,qmi-board-id=255` matched, `using board api 2`.
2. About 180 ms later the firmware raised `mhi notify status reason MHI_CB_EE_RDDM` (twice), then `qmi failed to load bdf file` and `qmi failed to load board data file:-110` (timeout, about 10 s later). No interface was created, `iw dev` is empty.
3. In M8 the same `amss.bin`, `m3.bin` and Fedora's id-255 payload brought the interface up. The only change on this path is the board payload. Verified as a difference, Inference (strong) as the cause: the payload crashes this firmware.
4. `debug_mask` was 0x30, not the 0x70 asked for in I4, so no `qmi bdf_type` or segment lines exist. It is not provable from the log whether the BDF transfer completed before the crash.

## How Windows delivers the board data (Verified, REA)

Binary `qcwlanhmt8380.sys`, SHA-256 `ca884ce1a22113194f3c467f36abc39afb0c137e5a7a8e2697420438b21e4115` (matches `sources/binary-catalog.tsv`), Ghidra, language auto-detected from the PE header (AARCH64), session closed afterwards.

- `wlfw_get_bdf` `0x14014a478` (cached decompile): reads the file whole into memory, no conversion. Order: DPP, then `bdwlan*.elf`/`.eNN` named by board id, then `BDFileName`.
- `wlfw_get_bdf_type` `0x14014ab10` (`evidence_id ev_5eed7c98b607a1bdd4874c51aff27e24d69c5a3dd3c76d04492431b05f632c0e`): extension `.b*` gives type 0 (BIN), extension `.e*` (including `.elf`, `.e0f`, `.e02`) gives type 1 (ELF), default 1.
- `wlfw_send_bdf_download_req` `0x14014dcc0` (`ev_a5624ee345275aac73dd313f8b903337b1016c946e1ae577d6f448c307dce433`): QMI message 0x25 with the file bytes unchanged, chunks of 4000 B, incrementing segment id, `total_size` = file size, `end` set on the last chunk, `bdf_type` as above. `file_id` is 0 on the Windows side; Linux sends the board id. The firmware accepted both in M8 (Linux), so this is not shown to matter.
- Conclusion: `bdwlan.elf` goes to the firmware raw, as type ELF. No segment extraction, no conversion.

## Linux 7.3 (Verified, `drivers/net/wireless/ath/ath12k/qmi.c:3078-3130`)

`ath12k_qmi_load_bdf_qmi(ATH12K_QMI_BDF_TYPE_ELF)` fetches the matched payload and sends type ELF when it starts with `\x7fELF`, else BIN. Chunks follow `QMI_WLANFW_MAX_DATA_SIZE_V01`. So Linux also delivers the payload raw, type ELF. Transport does not differ from Windows.

## Our derived file (Verified, `wifi-board2.py`)

- Same container as Fedora: one BOARD top IE per entry with a NAME and a DATA sub-IE, one REGDB IE, no other IE types. The new entry is first, its payload is byte-identical to `bdwlan.elf` (SHA-256 `b24438910ff0...`, 88780 B), starts with `\x7fELF`, ELF32, one `PT_LOAD` of 87040 B at 1024, inside the 256 KiB `board_size`. All 21+ Fedora names are retained. The structure is correct and equals what Fedora ships for other boards (Fedora's own entries are the same ELF container, 88760-89024 B). `verify` now confirms this and the file is unchanged byte for byte after the rebuild (SHA-256 `74d0f9f9...`).
- We did not embed an ELF where a BIN is expected and did not wrap it wrongly. The ELF-versus-BIN question is answered: ELF is right.
- Payload header words (`0x7f123456` block): Fedora id-255 has `6c000000 00000401`, Windows `bdwlan.elf` has `00000000 00000001`. `0x6c` equals the fw_version low byte of the running firmware (`0x1103006c`, `WLAN.HMT.1.1.c7-00108`). Fedora ships both header variants (21 with 0x6c/0x401, 4 with 0/0x01), so the difference alone is not proof. Inference only.

## e0f / e02 variants (Verified)

Windows selects by QMI board id only (`evidence/2026-10-28-windows-board-selection.md`). Board id 0xff gives `bdwlan.elf`. `bdwlan01.e0f` (board id 0x0f) and `bdwlan01.e02` (board id 0x02) are other boards: they differ from `bdwlan.elf` in 15062 and 11819 bytes and from each other. SHA-256 prefixes: `elf` `b24438910ff0`, `e0f` `18ab5b6ef0f5`, `e02` `30b1785cc574`. None equals Fedora's id-255 payload (`d4f9...` family or the 17cb:1107 entry); the id-255 name for 17cb:1107 in Fedora has no Windows file counterpart. There is no reason to use e0f or e02 for this unit (chip reports board id 0xff) and using them would be a guess.

## Why it crashes (Inference, not proven)

- Windows ships firmware `wlanfw20.mbn` `WLAN.HMT.1.1.c5-00310` (6082624 B); the device ran Fedora's newer `c7-00108`. `bdwlan.elf` is board data matched to the Windows firmware, not to c7. A content mismatch (calibration/feature fields) crashing the newer firmware at board init fits the timing (180 ms after board selection). Transport, framing, type and size are ruled out.
- Not testable offline. The BDF is opaque. Editing it (for example the header word) would be guesswork on signed-by-vendor data and is not done.

## Do the M9 patches show an effect? (M10 log)

- 0003 CMA: Verified yes. CMA pool at `0xf2c00000`, 128 MiB (below 4 GiB), `alloc_pages_fail 0`, `consistent_dma_mask_bits 32`. No `qmi dma allocation failed`, no large-allocation fallback warning in dmesg or journal.
- 0002 rfkill: TBD. The firmware crashed before the rfkill event could occur, no ath12k rfkill message and no WLAN rfkill device exists (`rfkill list` shows only `hci0`). Not testable until the board crash is removed.
- Side findings: `sp11-rfkill-events.service` still has `Before=NetworkManager.service` (I3 not applied in M10); `debug_mask` is 48, not 0x70 (I4).

## Recommendation

1. Derived board file is NOT trustworthy: structurally correct, functionally crashes the firmware. Drop it from the image for now. With Fedora's generic file Wi-Fi reached the interface in M8; 0002 and 0003 then decide scanning.
2. If the operator wants to retest the Windows board data later, only with Windows-matching firmware (`wlanfw20.mbn` c5-00310 as `amss.bin`, private, with its `m3.bin`) in a separate boot, never combined with a changed firmware set.

## Image behaviour required (written to README Requests I7, I9)

- Default: do not install the derived board file.
- Private mode with `SP11_WIFI_BOARD2` explicitly set: run `python3 -I hardware/wifi/tools/wifi-board2.py verify <file> --fedora <Fedora board-2.bin[.xz]> --sha256 <Windows SHA-256>`. Install to `updates/` only on exit 0, else leave Fedora's file and print a warning (do not fail the image).
- Verification is structural. It does not prove firmware acceptance, so the file also stays off by default until a boot shows no `MHI_CB_EE_RDDM`.
- Test-boot detector (L0/collector): the strings `MHI_CB_EE_RDDM` or `qmi failed to load board data` with an `updates/` override present means remove the override.
