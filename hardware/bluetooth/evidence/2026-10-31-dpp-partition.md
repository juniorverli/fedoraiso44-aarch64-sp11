# REA Findings: Qualcomm DPP Partition Architecture, IOCTL Interface, and Linux Factory Identity Feasibility

- **Date**: 2026-10-31
- **Target Device**: Microsoft Surface Pro 11 (Qualcomm Snapdragon X Elite X1E-80-100 / SC8380XP, WCN7850 Wi-Fi 7 / Bluetooth 5.4)
- **Host OS**: Fedora 44 aarch64 (Linux kernel 7.3)
- **Binary Sources**:
  - `QcSOCPartition.sys` (SHA256: `a73546cf...`)
  - `qcwlanhmt8380.sys` (SHA256: `ca884ce1...`)
  - `qcbluetooth8380.sys` (SHA256: `382a5a32...` / `39dba3b5...`)
- **Status & Compliance**: REA Rules applied: `flock` discipline, S3 (no firmware writes), S4 (Windows partition read-only / no BitLocker access), S5 (no MAC addresses, Bluetooth addresses, serial numbers, or binary hex dumps recorded).

---

## 1. Executive Summary & Core Question Answer

**Core Question**: *Can Linux obtain the device's factory Wi-Fi MAC and Bluetooth public address by itself, WITHOUT copying them from Windows?*

### Verdict:
1. **Wi-Fi Factory MAC**: **YES (Verified)**.
   - Linux does **not** need to read Windows or a DPP partition for Wi-Fi.
   - The Qualcomm WCN7850 Wi-Fi hardware supplies its factory station MAC address directly from internal chip OTP to the host kernel during the WMI service ready initialization event (`ath12k_wmi_ready_event` in [`drivers/net/wireless/ath/ath12k/wmi.c`](file:///home/juniormverli/repositories/fedora44iso-aarch64-sp11/drivers/net/wireless/ath/ath12k/wmi.c#L7066)).
2. **Bluetooth Public Address**: **NO (Verified)**.
   - The Qualcomm Device Provisioning Partition (DPP) with Partition Type GUID `f97b8793-3abf-4719-896b-7c3e9b85e104` is **physically absent** on the Surface Pro 11 NVMe SSD.
   - On Surface Pro 11, the Windows Bluetooth driver (`qcbluetooth8380.sys`) fails IOCTL `0xECAF32C2` to `\DosDevices\QcSOCPartitionDevice` (returning `0xC000000E` / `STATUS_NO_SUCH_DEVICE`), passes the OTP check, and falls back to reading `Device Parameters\BdAddr` (under `HKLM\SYSTEM\...`) from the Windows Registry.
   - The Windows Registry resides on the Windows OS partition (`/dev/nvme0n1p3`), which is **BitLocker-encrypted**.
   - Accessing or mounting the BitLocker partition from Linux is strictly prohibited by **Safety Rule S4** (*"The Windows partition is read-only. Never mount it read-write; never touch it while hibernated or BitLocker-encrypted"*).
   - Therefore, Linux cannot obtain the Windows Bluetooth public address autonomously from disk. It must be provided via an unencrypted operator channel (such as the FAT32 EFI System Partition via `sp11-bt-address`) or run with an unconfigured/locally administered controller.

---

## 2. Reverse Engineering: QcSOCPartitionDevice & IOCTL 0xECAF32C2

### 2.1 Driver Identity & Storage Target (Verified)
- **Service & Device**: ACPI device `QCOM06DD`, service name `QcSOCPartition`, driver binary `QcSOCPartition.sys` (`a73546cf...`).
- **Physical Disk Probing**:
  - In procedure `FUN_1400037a8`, `QcSOCPartition.sys` opens physical disks 0 through 9 using object names `\Device\Harddisk%u\Partition0`.
  - It issues `IOCTL_DISK_GET_DRIVE_LAYOUT_EX` (`0x00070050`) to retrieve the drive layout.
  - It validates the GPT header signature `EFI PART` (`0x5452415020494645`) and verifies the header CRC32 via procedure `FUN_14002cfe8`.
  - It iterates GPT partition entry records looking for:
    - Partition Type GUID matching `f97b8793-3abf-4719-896b-7c3e9b85e104`.
    - Partition Name matching `L"DPP"`.
  - When located, it binds access to `\Device\Harddisk%u\Partition%u`.
- **Hardware Storage on Surface Pro 11**:
  - Live hardware inventory (`sar-phase2-readonly.txt`, `partitions-gpttype.txt`) confirms that Disk 0 is the single internal NVMe SSD (`HFM512GD83CJ085N`).
  - There is no UFS storage (`SUFS = 0xFFFFFFFF`), no eMMC, and no raw SPI NOR partition visible to the OS.
  - Disk 0 GPT table contains only four partitions:
    1. `Partition 1` (ESP): GUID `c12a7328-f81f-11d2-ba4b-00a0c93ec93b`
    2. `Partition 2` (MSR): GUID `e3c9e316-0b5c-4db8-817d-f92df00215ae`
    3. `Partition 3` (Windows Basic Data): GUID `ebd0a0a2-b9e5-4433-87c0-68b6b72699c7` (BitLocker-encrypted)
    4. `Partition 4` (Windows Recovery): GUID `de94bba4-06d1-4d40-a16a-bfd50179d6ac`
  - Partition Type GUID `f97b8793-3abf-4719-896b-7c3e9b85e104` is **ABSENT** (`DPP-type partition present: False`).

### 2.2 IOCTL 0xECAF32C2 Interface (Verified)
- **Control Code**: `0xECAF32C2` (`METHOD_BUFFERED`, `FILE_READ_DATA | FILE_WRITE_DATA`, `FILE_DEVICE_UNKNOWN`).
- **Input Buffer Layout (`0x128` = 296 bytes)**:
  - `+0x00..+0x0F` (16 bytes): Partition Type GUID (`f97b8793-3abf-4719-896b-7c3e9b85e104`).
  - `+0x10..+0x127` (280 bytes): UTF-16LE null-terminated record path string (e.g. `L"QCOM\BT.PROVISION"`, `L"QCOM\WLAN.PROVISION"`, `L"QCOM\WLAN_CLPC.PROVISION"`).
- **Output Buffer Layout**:
  - `+0x00..+0x03` (4 bytes, uint32): Execution Status.
  - `+0x04..+0x07` (4 bytes, uint32): NTSTATUS completion code (0 = `STATUS_SUCCESS`).
  - `+0x08..+0x0B` (4 bytes, uint32): Expected buffer size.
  - `+0x0C..+0x0F` (4 bytes, uint32): Reserved / alignment padding.
  - `+0x10..+0x13` (4 bytes, uint32): Returned payload byte count.
  - `+0x14..+0x14+N`: Raw payload data bytes.

---

## 3. Qualcomm Device Provisioning Partition (DPP) & RWFS Format

### 3.1 RWFS Partition Header (Verified)
The DPP partition uses Qualcomm's proprietary `RWFS` format:
- `+0x00..+0x03`: Magic ASCII `b"RWFS"` (`0x53465752` LE).
- `+0x04..+0x07`: Filesystem version / revision flags (`0x00010000`).
- `+0x14..+0x17`: Block/sector size in bytes (uint32, typically 512).
- `+0x18..+0x1B`: Total partition table size in bytes (uint32).
- `+0x4C..+0x4F`: Directory table byte offset from partition base (uint32).
- `+0x54..+0x57`: Directory entry count (uint32).
- `+0x58..+0x5B`: Data area base byte offset from partition base (uint32).

### 3.2 Directory Entry Structure (Verified)
Each directory entry in RWFS is exactly 244 bytes (`0xF4`):
- `+0x00..+0x5F` (96 bytes): Item Name as UTF-16LE string (up to 48 characters, null-terminated).
- `+0x60..+0x61` (2 bytes): Flags / entry attributes.
- `+0x62..+0xC1` (96 bytes): Namespace / Directory Name as UTF-16LE string (e.g. `L"QCOM"`).
- `+0xC4..+0xC7` (4 bytes, uint32): Allocated size.
- `+0xC8..+0xCB` (4 bytes, uint32): Actual data size.
- `+0xD0..+0xD3` (4 bytes, uint32): Data offset relative to data area base offset.
- `+0xD4..+0xD7` (4 bytes, uint32): Stored IEEE 802.3 CRC-32 (polynomial `0xEDB88320`, verified via `FUN_14002be28`).

### 3.3 Provisioning Record Layouts (Verified)
1. **Bluetooth Address (`QCOM\BT.PROVISION`)**:
   - Total payload size: 8 bytes.
   - `bytes[0..1]`: Header / tag bytes (`0x0001`).
   - `bytes[2..7]`: 6-byte Bluetooth device address in **Little-Endian (reversed) byte order**.
   - Address extraction: `reversed(payload[2:8])` yields `XX:XX:XX:XX:XX:XX`.
2. **Wi-Fi Multi-MAC Address (`QCOM\WLAN.PROVISION`)**:
   - Read by `ol_readMultiMacAddress` (`0x14018a130`) / `get_macaddress_from_DPP` (`0x1401862f4`) in `qcwlanhmt8380.sys`.
   - `bytes[0..1]`: Version / flags.
   - `byte[2]`: Number of MAC addresses (1 or 4).
   - `bytes[3..8]`: Primary station MAC address in canonical network order (`XX:XX:XX:XX:XX:XX`).
   - `bytes[9..14]`: Second MAC address (e.g. P2P device address), if present.
3. **Wi-Fi Calibration Data (`QCOM\WLAN_CLPC.PROVISION`)**:
   - Contains Closed Loop Power Control (CLPC) and board data calibration parameters (BDF).

---

## 4. Safe Read-Only Linux Reader (`dpp-reader.py`)

### 4.1 Design & Safety Guarantees (Verified)
- **Location**: [`hardware/bluetooth/userspace/dpp-reader.py`](file:///home/juniormverli/repositories/sp11-fedora.worktrees/bluetooth/hardware/bluetooth/userspace/dpp-reader.py).
- **Execution Rules**:
  - Opens target block device or image strictly with `os.O_RDONLY`. Never requests write access.
  - Does not invoke filesystem mounting or kernel partition table modifications.
  - Probes sector sizes (512 and 4096), parses GPT headers, checks GUID `f97b8793-3abf-4719-896b-7c3e9b85e104` and name `DPP`, and validates `RWFS` signature and entry CRC-32 checksums.
  - **S5 Compliance**: Default output displays only table of record names, data lengths, and CRC status (`OK` / `CRC_MISMATCH`). Never logs or displays address octets or payload hex dumps.
  - When `--emit <path>` is requested, parses `QCOM\BT.PROVISION`, extracts and reverses bytes 2–7 into standard hex format, and writes directly to `<path>` with strict `0600` permissions (`os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600`).
  - When `--emit-wifi <path>` is requested, parses `QCOM\WLAN.PROVISION` and writes the station MAC to `<path>` with strict `0600` permissions.
- **Verification on Synthetic Fixtures**:
  - Tested against synthetic raw RWFS image (`raw_dpp_partition.bin`) and synthetic GPT disk image (`synthetic_disk.img`).
  - Successfully parsed all 3 records (`QCOM\BT.PROVISION`, `QCOM\WLAN.PROVISION`, `QCOM\WLAN_CLPC.PROVISION`) with `CRC STATUS: OK`.
  - Successfully verified `--emit` and `--emit-wifi` output files created with exact mode `0600` (`-rw-------`).
  - Tested against non-DPP image / device: cleanly returns exit code 2 ("No Qualcomm DPP partition found").

---

## 5. Wi-Fi MAC & Board Data Analysis

| Provisioning Source | Windows Driver Path (`qcwlanhmt8380.sys`) | Linux Kernel Path (`ath12k`) | Surface Pro 11 Behavior |
|:---|:---|:---|:---|
| **Station MAC Address** | Tries `QCOM\WLAN.PROVISION` via DPP; on failure, falls back to chip OTP via WMI ready event. | Reads directly from WCN7850 chip OTP via WMI ready event (`ath12k_wmi_ready_event`). | **Linux obtains factory MAC autonomously via OTP without Windows.** |
| **Calibration / Board Data** | Tries `QCOM\WLAN_CLPC.PROVISION` via DPP; on failure, loads `bdwlan.elf` file from DriverStore. | Loads board data ELF file (`board-2.bin` / `bdwlan.elf`) from `/lib/firmware/ath12k/WCN7850/`. | **Supplied via standard firmware package.** |

---

## 6. Security, BitLocker, & Safety Rule S4 Analysis

1. **BitLocker Encryption Scope**:
   - BitLocker operates at the volume level on partition 3 (`/dev/nvme0n1p3`, NTFS).
   - If a DPP partition had existed as a GPT raw partition, it would have been unencrypted and safely readable by Linux.
2. **Absence of DPP on Surface Pro 11**:
   - Because DPP does not exist on disk, Windows drivers store device state in the Windows Registry (`HKLM\SYSTEM\...` / `Device Parameters\BdAddr`) on the BitLocker partition.
3. **Safety Rule S4 Boundary**:
   - Rule S4 explicitly commands: *"The Windows partition is read-only. Never mount it read-write; never touch it while hibernated or BitLocker-encrypted."*
   - Reading the registry from Linux would require unlocking/decrypting the BitLocker volume, which modifies TPM PCR measurements and risks triggering BitLocker Recovery key prompts on Windows reboot.
   - Consequently, Linux must not touch partition 3. The only safe and supported method to acquire the Windows Bluetooth public address is via operator export to the FAT32 ESP.

---

## 7. Findings & Evidence Grading Matrix

| Finding | Grade | Evidence / Source |
|:---|:---|:---|
| `QcSOCPartitionDevice` exposes raw GPT partition via `\Device\Harddisk%u\Partition0` | **Verified** | `QcSOCPartition.sys` (`a73546cf...`) at `FUN_1400037a8` issuing `IOCTL_DISK_GET_DRIVE_LAYOUT_EX` |
| DPP Partition Type GUID is `f97b8793-3abf-4719-896b-7c3e9b85e104` | **Verified** | `QcSOCPartition.sys` at `FUN_1400037a8`, `qcbluetooth8380.sys` (`382a5a32...`) at `0x1400cbe90` |
| IOCTL `0xECAF32C2` input buffer is 296 bytes (GUID + UTF-16LE path) | **Verified** | `QcSOCPartition.sys` at `FUN_140001f54`, `FUN_1400021b0` |
| DPP filesystem uses `RWFS` format with 244-byte directory entries and CRC-32 | **Verified** | `QcSOCPartition.sys` at `FUN_1400014b0`, `FUN_140002be28`, `FUN_140003058` |
| `QCOM\BT.PROVISION` payload bytes 2-7 are reversed BD_ADDR | **Verified** | `qcbluetooth8380.sys` decompilation at `FUN_1400cbd04` |
| `QCOM\WLAN.PROVISION` provides station and multi-MAC addresses | **Verified** | `qcwlanhmt8380.sys` (`ca884ce1...`) at `0x14018a130` (`ol_readMultiMacAddress`) and `0x1401862f4` (`get_macaddress_from_DPP`) |
| DPP partition is ABSENT on Surface Pro 11 Disk 0 GPT | **Verified** | `sar-phase2-readonly.txt`, `partitions-gpttype.txt` (`DPP-type partition present: False`) |
| Linux `ath12k` retrieves factory Wi-Fi MAC from chip OTP | **Verified** | Linux kernel source [`ath12k/wmi.c:7066`](file:///home/juniormverli/repositories/fedora44iso-aarch64-sp11/drivers/net/wireless/ath/ath12k/wmi.c#L7066) (`ath12k_wmi_ready_event`) |
| Surface Pro 11 Bluetooth driver falls back to Windows registry on BitLocker OS partition | **Verified** | REA trace `hardware/bluetooth/evidence/2026-10-29-m8-and-rea.md`, Windows Registry `Device Parameters\BdAddr` |
| Linux reading BitLocker partition violates Safety Rule S4 | **Verified** | `plan/risks.md` §1 S4: Windows partition read-only, never touch while BitLocker-encrypted |
