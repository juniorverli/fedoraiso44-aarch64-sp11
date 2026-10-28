# Windows driver behaviour and the previous project (2026-10-28)

Binary: `sources/windows/DriverStore/qcbluetooth8380.inf_arm64_7ba98f6549b1f227/qcbluetooth8380.sys`, sha256 `39dba3b50deb257aa5410db0de508227d353e2c75d2508616dd1235496b072d6`, catalogued as `PE ARM64 code AARCH64:LE:64:v8A` (`sources/binary-catalog.tsv`). Only `strings` (ASCII and UTF-16) was used; nothing was decompiled, so there is no REA evidence id. Active package: INF `DriverVer 07/16/2025,1.0.4374.1301`, `sar-query.txt` shows `oem112.inf` bound to `ACPI\QCOM0C6B`. The older package `38c0031acff6bd96` (1.0.4111.7400) is not bound.

Key ASCII string file offsets, rechecked during the Codex continuation (byte offsets in the SHA-pinned `.sys`, no decompilation):

| String | Offset |
|:--|:--|
| `CheckDefaultAddress` | `0x5e690` |
| `OTP programmed BT address.` | `0x611a0` |
| `bt_hci_qca_get_system_preallocated_bd_addr` | `0x60ad0` |
| `no BT Addr in the DPP` | `0x609a0` |
| `try to read the BT Addr from registry` | `0x609b8` |
| `no BT Addr in the registry, generate a random BT Addr` | `0x60a20` |
| `RandomBTAddrEnabled` | `0x5df60` |
| `bt_hci_qca_get_board_id` | `0x595a8` |

## Windows: files and names

- INF copies `hmtbtfw20.tlv`, `hmtnv20.bin`, `hmtnv20.b3b`, `b105`, `b107`, `b108`, `b10f`, `b112` and the `hpbtfw21`/`hpnv21*` set (another chip) (`qcbluetooth8380.inf` `[BTUART.Files]`).
- Hash groups of the active package (sha256 prefix): `hmtnv20.bin` = `hmtnv20.b3b` (`facca00c`); `b105` = `b107` = `b108` (`48c66943`); `b10f` (`5f439c6b`); `b112` (`1aaef0b2`). Fedora generic `hmtnv20.bin` decompresses to 9508 bytes (sha256 prefix `c26b340b`), Windows `hmtnv20.b3b` has 9656 bytes. Both have the same 95 TLV tags; 21 tag payloads differ, including tags 1, 35, 36, 64, 85, 87, 177, 178, 213, 214, 220 and 226. Their detailed semantics and RF effect have not been established; byte differences alone do not prove degraded RF. Fedora's `b10f` differs from Windows `b3b` in 13 tags.
- Registry on this unit: `ACPI\QCOM0C6B\...\Device Parameters\UserNvmFile = hmtnv20.b3b`, `FirmwareIdentified = 1` (`live-inventory/sar/sar-query.txt:231-236`). The ACPI `_DSM` function 1 returns `"default"` (`dsdt.dsl:68664-68668`), so ACPI does not override the file.
- Driver strings: `hmtnv20.b`, `bt_hci_qca_get_board_id`, `boardIDMSB=0x%x, boardIDLSB=0x%x`, `failed to get the board id`, `Can't find the board id's nvm file, Open the dafault .bin file`, `UserNvmFile = %S`, `BTAcpiDsmGetNvm`. Inference: Windows reads the board ID, builds `hmtnv20.b<id>`, writes it to `UserNvmFile`. Because `b3b` is byte-identical to Windows `hmtnv20.bin`, either name identifies the same `facca00c` input in the captured package; actual Windows loading has not been traced.
- Linux on the same hardware requested `hmtnv20.bin` (M5 log), so the selected board-ID variable was 0 or 0xffff (including a failed/discarded reply), while Windows' registry says `b3b`. The recorded filename selections differ; the registry alone does not prove the raw Windows board-ID reply; the Linux read (`btqca.c:193-235`) may be failing silently or the controller may answer differently before/after a state change. TBD: the conditional focused dynamic-debug collection in test-plan step 4 can distinguish a valid ID from many failure cases; a too-short reply can remain silent.

## Windows: BD address logic (strings only, ordering is Inference)

Strings: `CheckDefaultAddress`, `Read the BT Addr: [default masked]` (the NVM default), `OTP programmed BT address.`, `bt_hci_qca_get_system_preallocated_bd_addr`, `no BT Addr in the DPP`, `try to read the BT Addr from registry`, `no BT Addr in the registry, generate a random BT Addr`, `use the default BT addr in the NVM file`, `Registry/Randomly generate BT address`, `RandomBTAddrEnabled`; INF `HKR,Parameters,RandomBTAddrEnabled,0x10001,1`.

Inference from strings (not verified control flow): Windows also treats the Qualcomm default address as "not set" and then takes an address from the platform provisioning data (DPP), from the registry, or generates a random one and keeps it. Windows reports a real (non-default) address for this unit (`sources/windows/live-inventory/macs.txt`, `sp11-mac.conf`, not quoted). Where that address comes from (OTP, DPP, registry, random) is not established. The Windows-observed value must not be described as a proven factory/OTP identity. For Linux: if the chip holds a valid OTP address Linux needs nothing; if it reads the default, the address must be supplied by us.

## Previous project (`/home/juniormverli/repositories/surface`, read only)

- Status 2026-10-23 (`docs/status.md:13`): "Operator report, relayed in chat and not checked against `/EFI/sp11-logs/` ... Bluetooth works." Grade: operator report, no log.
- What it shipped for BT in that ISO (`d47a67ba`, 28-patch kernel):
  1. Fedora `hmtbtfw20.tlv` and Windows `qca/hmtnv20.b3b` (`firmware/blobs.toml`, source DriverStore 1.0.4374.1301, sha256 `facca00c...`). With the M5 evidence that btqca asks for `hmtnv20.bin`, this `b3b` was most likely never requested; the generic Fedora NVM was in use.
  2. `sp11-bt-address.service` and `/usr/libexec/sp11-bt-address`: waits for `hci0`, reads `/etc/sp11/bt-address`, runs `btmgmt --index N public-addr`; the file was **written into the ISO at build time** from `BT_MAC` in `sp11-mac.conf` (`userspace/integration/prepare.py:24-60,156-160`). That conflicts with S5 and with the current requirement (no address in the ISO).
  3. Patches 0027/0028 (`firmware-name` for the `geniqup` wrappers and loading GENI firmware for protocol 0). Not needed for the UART here: M5 shows `a98000.serial` probes without them.
  4. DT: the stock Denali `bluetooth` node, no `local-bd-address`, no `firmware-name`.
- Inference (not proven): Bluetooth worked there because of (2): the controller left unconfigured was given the address, then BlueZ saw it. The unchanged DT and the successful M5 UART setup weaken those alternative explanations. The NVM difference remains an RF/functional question; absent earlier device logs, this comparison cannot exclude it as a contributor.

## NVM comparison reproduced during continuation

The data parser follows `sources/linux/drivers/bluetooth/btqca.h:134-145`: a 4-byte type/length header followed by little-endian 12-byte tag headers and bounded tag payloads. It validates the overall length and tag boundaries and never prints address payloads. No firmware is disassembled or copied into git.

| Data input | Size | SHA-256 of uncompressed data | Tags |
|:--|--:|:--|--:|
| Active Windows `hmtnv20.b3b` (also generic `.bin`) | 9656 | `facca00c7cbc988d843776f8b8f8f7926f24007a1cfc540d2219a005f596114f` | 95 |
| Fedora `atheros-firmware-20261019-1.fc44` `hmtnv20.bin` | 9508 | `c26b340bbc8b617304610c774627ac4879194705eea7a7c7b13e3593903befd9` | 95 |
| Same Fedora RPM, `hmtnv20.b10f` | 9556 | `f8d027c5f0ea54456d23b903c55e1a87b06df97ff26b83e3fd02ac6b265b5264` | 95 |

The tag-ID sets are equal. Generic Fedora versus Windows differs in tags 1, 32, 35, 36, 64, 83, 85, 87, 177, 178, 213, 214, 220, 226, 228, 233, 234, 235, 236, 237 and 238 (21). Fedora `b10f` versus Windows differs in 1, 32, 35, 64, 83, 85, 87, 177, 178, 213, 214, 220 and 226 (13). Tag 2's default address is equal in all checked inputs. These are byte-level facts, not a decoded RF calibration or a reason to replace the current Fedora NVM before the address test.
