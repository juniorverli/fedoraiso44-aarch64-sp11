# Windows board-data selection and the Fedora board-2.bin

## Windows side (Verified)

- Binary: `DriverStore/qcwlanhmt8380.inf_arm64_f6c170edbe88d474/qcwlanhmt8380.sys`, SHA-256 `ca884ce1a22113194f3c467f36abc39afb0c137e5a7a8e2697420438b21e4115`, catalog `sources/binary-catalog.tsv` row: PE ARM64, Ghidra language `AARCH64:LE:64:v8A`. REA/Ghidra (provider ghidra, `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`, under `flock out/.ghidra.lock`, 2026-10-28), snapshot `out/rea/wifi/qcwlan.snap`.
- `wlfw_get_bdf` at `0x14014a478` (`evidence_id ev_c0c95236cb74085149c590051d97acac9f7dd984c39c3b53feead233172dffbf`): reads PCI IDs of the device (`0x17cb`, `0x1107`, subsystem vendor `0x17cb`); on that branch it calls the name builder, logs `try Load elf BDF file`, and finally `try to load default BDF file` (registry `BDFileName`, string at file `0x2f57c0`; `bdwlan.elf` per `live-inventory/wlan/class-wcn7850.txt` line 15). This unit has `SUBSYS_110717CB` (`live-inventory/wlan/registry-wcn7850.txt`).
- Name builder at `0x140147b80` (`ev_931be55bbc57d5ff644a3266652976731e8cd695e3fc8d98a2ecb81b82edfe21`), strings read from the file: `%s%s`, `.e`, `.elf`, `g`, `.g`.
  - `board_id == 0xff`: `bdwlan` + `.elf` (`bdwlang.elf` when flag bit 4 is set).
  - `board_id < 0xff`: `bdwlan` + `.e` + `%2.2x`.
  - `board_id > 0xff`: `bdwlan` + `%2.2x` (high byte) + `.e` + `%2.2x` (low byte).
- Device log: this unit reports `board_id 0xff` (Linux QMI target capability, `2026-10-28-m5-device-log.md` fact 6). **Inference (strong):** Windows asks for `bdwlan.elf`, which is the file in the package.
- DPP: the driver tries DPP board data before files (strings `WLAN_CLPC.PROVISION`, `elf BDF file was loaded from DPP`, previous project's `rea/sar` notes, not re-verified). `live-inventory/sar/sar-phase2-readonly.txt` shows no DPP-type partition on the disk (GPT scan) and no readable SAR UEFI variable. **TBD:** whether this unit holds DPP board data elsewhere (ESRT lists `WIFIDPP`, `live-inventory/firmware/esrt-devices.txt`).
- INF (`qcwlanhmt8380.inf`, DriverVer 07/14/2025,1.0.4374.1300): the device binds through the generic `PCI\VEN_17CB&DEV_1107` line (line 33) to `QcWlan_BERYLLIUM.ndi`; there is no `SUBSYS_110717CB` section. Section copies `QcWlan_BD_BERYLLIUM.CopyFiles` (lines 790-800): `bdwlan01.e02/e04/e05/e07/e08/e0b/e0f/e12`, `bdwlan.e36`, `bdwlan.e3b`; `bdwlan.elf` comes from `QcWlanFWFile.CopyFiles` (line 784). The `bdwlan_wcn785x_2p0_ncm*` files belong to OEM subsystem sections (lines 39-72), not to this device.
- No per-board variant string exists in the INF or in the registry for this device. Windows selects by QMI board id only.

## Linux side (Verified, `sources/linux` v7.3)

- Board name: `core.c:221-263`. For WCN7850 `bdf_search = BUS_AND_BOARD` (`wifi7/pci.c:135`), so the name is `bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=1107,qmi-chip-id=2,qmi-board-id=<id>` plus `,variant=<bdf_ext>` when a variant exists. The fallback name (`core.c:269-281`) is the same string without the variant: no `qmi-board-id=255` default is tried for this bus mode.
- Order (`core.c:524-580`): `board-2.bin` with the name; `board-2.bin` with the fallback name; `board.bin` (`hw.h:95`). Failure message: `failed to fetch board data for <name>`.
- `bdf_ext` comes only from SMBIOS type `0xF8` (`core.c:696-790`) or an ACPI `_DSM` string (`acpi.c:487`). Neither exists on this DT boot (no ACPI; the Surface `WLN._DSM` has no BDF-extension function, `dsdt.dsl:59169-59200`). **`qcom,calibration-variant` / `qcom,ath12k-calibration-variant` is not read by ath12k 7.3** (`grep` in `drivers/net/wireless/ath/ath12k/` finds none) and the binding `qcom,ath12k.yaml` (`pci17cb,1107`, `additionalProperties: false`) has no such property. Only `qcom,ath12k-wsi.yaml` (IPQ/AHB) does. Nothing to add to the DT. Whether `dmidecode -t 248` shows a variant on the device is still collected (cheap).
- Board file size limit: `board_size = 256 KiB` (`wifi7/hw.c:455`); the board ELFs are 88 KB.

## Fedora board-2.bin for WCN7850 (Verified, parsed from the RPMs)

`atheros-firmware` (not `qcom-firmware`) ships `ath12k/WCN7850/hw2.0/{amss.bin,board-2.bin,m3.bin}.xz` and `ncm865/`. No `board.bin`, no `regdb.bin`. RPM SHA-256: `atheros-firmware-20260309-1.fc44.noarch` `30c7a6ea398216302b218c096ddb2fc233e1c690746b98cd4432d13438bfbdef`; `-20261019-1.fc44` (updates) `5149e96e0377a7d3a9e1dea254d39fa5a46fd4903df839b3971de8ccfb75ed38`.

| File | 20260309 (SHA-256 of decompressed) | 20261019 |
|:--|:--|:--|
| `amss.bin` | `5660a1aa3db12716b42c687b0c88ef4f6ac80bd46e42cfe3636ed332d3f6e6ee` (6082624 B) | `43aadfd3df887f27de74020273aee484bac6a31dd53068f91baf2a9b094d6a68` (6090816 B, `WLAN.HMT.1.1.c7-00108`, the one the device ran) |
| `m3.bin` | `ff40c57556c2fac552ac192c6e2ad59689fd8f50c9f9bcc997d13623c2bcee86` = **Windows `phy_ucode20.elf`** (catalog SHA-256 equal) | `0e72f44df7defc269fe92dcea25d4d409046c04b77d41c510c52879b3dfc1055` |
| `board-2.bin` | `1abee7132dbccb523cca44a8de4e8968aa7bf5a5fcc032c338f687f94ea5bf4e` | `6a98237c743d864773a547e81e23f0c6dc721dcd7331926bee7381e2152e00fd` |

Entries for `subsystem-vendor=17cb,subsystem-device=1107,qmi-chip-id=2`: 20260309 has board ids 44 and 82; 20261019 adds **255**, 513 and 514 (payload of 255: `d4f92e9f11bc…`, shared with several OEM entries). One top-level IE can hold several name elements before one data element (`core.c:313-365`); `hardware/wifi/tools/wifi-board2.py list` prints every name. REGDB: one entry, `bus=pci`, 24310 bytes (both versions), used by `ath12k_core_fetch_regdb()` (`core.c:583-625`).

**Consequence:** with `board_id 0xff` Linux needs `atheros-firmware` 20261019 or later. With 20260309 the lookup misses and `board.bin` does not exist, so Wi-Fi bring-up fails at the BDF step.

## Windows `bdwlan.elf` against Fedora's id-255 entry (Verified)

- Same container: ELF32, OSABI `0x61`, one `PT_LOAD` of 87040 bytes at offset 1024 (`readelf`-level parse with a script, scratchpad only). Fedora's entries are 88760-89024 B, Windows files 88780-88936 B.
- Payloads differ: Windows `bdwlan.elf` (file SHA-256 `b24438910ff0383d299798a997d3ef3484be624ac013aec2ce7939ec32900c4f`, 88780 B, `PT_LOAD` hash prefix `497b73c53fa0`) equals no entry of either Fedora file. Only `bdwlan_wcn785x_2p0_ncm825_DE02.elf` and `…_LES790.elf` equal Fedora entries (OEM variants, not selected for this unit).
- **Inference:** Linux runs on generic reference board data (calibration, TX power, CTL) where Windows runs on `bdwlan.elf`. Whether `bdwlan.elf` is Surface-specific, and what the difference means for TX power and range, is TBD. The BDF is opaque (no readable board id field). A derived `board-2.bin` that carries `bdwlan.elf` for this unit's name is prepared (`tools/wifi-board2.py`) and held until basic connectivity works, so that one change is tested at a time.
- BT and WLAN board ids are **not** the same number space on this unit: Bluetooth requested `hmtnv20.bin`, Windows recorded `hmtnv20.b3b`, while WLAN reports `0xff`. (Earlier hypothesis of board id `0x3b` is dead.)
