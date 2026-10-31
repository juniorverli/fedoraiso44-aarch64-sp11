#!/usr/bin/env python3
"""
Qualcomm Device Provisioning Partition (DPP / RWFS) Safe Reader.

Analyzes Qualcomm Device Provisioning Partition (GUID f97b8793-3abf-4719-896b-7c3e9b85e104)
from a raw partition or GPT disk image (e.g. /dev/nvme0n1).

Security and Safety:
- Block device and file inputs are opened strictly read-only (os.O_RDONLY).
- Never writes, modifies, or mounts any partition.
- In default listing mode, prints ONLY record names, sizes, and CRC verification status.
  NEVER outputs payload data, MAC addresses, or binary contents (S5 compliance).
- When --emit <path> is specified, outputs the parsed Bluetooth address directly to a
  root-restricted file (mode 0600) under /run/ for local consumption without console logging.
- When --emit-wifi <path> is specified, outputs the parsed Wi-Fi station MAC address directly
  to a root-restricted file (mode 0600).
"""

import argparse
import binascii
import os
import struct
import sys
from typing import Dict, List, Optional, Tuple

# Qualcomm DPP Partition Type GUID: f97b8793-3abf-4719-896b-7c3e9b85e104
# UEFI Mixed-Endian byte representation:
DPP_GUID_BYTES = bytes([
    0x93, 0x87, 0x7B, 0xF9,  # Data1: LE 0xf97b8793
    0xBF, 0x3A,              # Data2: LE 0x3abf
    0x19, 0x47,              # Data3: LE 0x4719
    0x89, 0x6B,              # Data4[0..1]: BE 0x896b
    0x7C, 0x3E, 0x9B, 0x85, 0xE1, 0x04  # Data4[2..7]: BE 0x7c3e9b85e104
])

RWFS_MAGIC = b"RWFS"
GPT_SIGNATURE = b"EFI PART"


class DPPRecord:
    def __init__(
        self,
        namespace: str,
        name: str,
        allocated_size: int,
        data_size: int,
        data_offset: int,
        stored_crc: int,
        calculated_crc: int,
        payload: bytes,
    ):
        self.namespace = namespace
        self.name = name
        self.full_path = f"{namespace}\\{name}" if namespace else name
        self.allocated_size = allocated_size
        self.data_size = data_size
        self.data_offset = data_offset
        self.stored_crc = stored_crc
        self.calculated_crc = calculated_crc
        self.crc_valid = (stored_crc == calculated_crc)
        self.payload = payload


class DPPReader:
    def __init__(self, target_path: str, verbose: bool = False):
        self.target_path = target_path
        self.verbose = verbose
        self.fd: Optional[int] = None
        self.partition_offset: int = 0
        self.partition_size: Optional[int] = None
        self.records: Dict[str, DPPRecord] = {}

    def __enter__(self):
        # Open strictly O_RDONLY (S4: no write access)
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            self.fd = os.open(self.target_path, flags)
        except OSError as e:
            sys.stderr.write(f"Error: failed to open '{self.target_path}' read-only: {e}\n")
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _read_exact(self, offset: int, length: int) -> bytes:
        if self.fd is None:
            raise RuntimeError("Device not open")
        os.lseek(self.fd, offset, os.SEEK_SET)
        data = bytearray()
        while len(data) < length:
            chunk = os.read(self.fd, length - len(data))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) != length:
            raise IOError(f"Unexpected EOF reading {length} bytes at offset {offset} (got {len(data)})")
        return bytes(data)

    def locate_dpp_partition(self) -> bool:
        """
        Detects whether target_path is a raw RWFS partition or a GPT disk containing DPP.
        """
        # 1. Test if target is already a raw RWFS partition at offset 0
        try:
            head = self._read_exact(0, 4)
            if head == RWFS_MAGIC:
                if self.verbose:
                    sys.stderr.write(f"Target '{self.target_path}' is a raw RWFS partition.\n")
                self.partition_offset = 0
                return True
        except Exception:
            pass

        # 2. Check GPT partition table on disk
        # Probe sector sizes 512 and 4096
        for sector_size in (512, 4096):
            try:
                # GPT Header is at LBA 1
                gpt_hdr_bytes = self._read_exact(sector_size * 1, 92)
                if gpt_hdr_bytes[:8] != GPT_SIGNATURE:
                    continue

                (
                    sig, revision, hdr_size, hdr_crc, res,
                    current_lba, backup_lba, first_usable, last_usable,
                    disk_guid, part_entries_lba, num_part_entries, part_entry_size, entries_crc
                ) = struct.unpack("<8sIIIIQQQQ16sQIII", gpt_hdr_bytes[:92])

                if self.verbose:
                    sys.stderr.write(
                        f"Found GPT header: sector_size={sector_size}, "
                        f"entries_lba={part_entries_lba}, entries={num_part_entries}, entry_size={part_entry_size}\n"
                    )

                entries_table_size = num_part_entries * part_entry_size
                entries_bytes = self._read_exact(part_entries_lba * sector_size, entries_table_size)

                for i in range(num_part_entries):
                    e_off = i * part_entry_size
                    entry = entries_bytes[e_off: e_off + part_entry_size]
                    if len(entry) < 128:
                        continue
                    type_guid = entry[0:16]
                    if type_guid == b"\x00" * 16:
                        continue

                    start_lba = struct.unpack("<Q", entry[32:40])[0]
                    end_lba = struct.unpack("<Q", entry[40:48])[0]
                    name_raw = entry[56:128]
                    name_str = name_raw.decode("utf-16le", errors="ignore").split("\x00")[0]

                    is_dpp_guid = (type_guid == DPP_GUID_BYTES)
                    is_dpp_name = (name_str.strip().upper() == "DPP")

                    if is_dpp_guid or is_dpp_name:
                        self.partition_offset = start_lba * sector_size
                        self.partition_size = (end_lba - start_lba + 1) * sector_size
                        if self.verbose:
                            sys.stderr.write(
                                f"Located DPP partition entry index {i}: name='{name_str}', "
                                f"offset={self.partition_offset}, size={self.partition_size}\n"
                            )
                        # Verify RWFS magic at partition start
                        p_head = self._read_exact(self.partition_offset, 4)
                        if p_head == RWFS_MAGIC:
                            return True
                        else:
                            if self.verbose:
                                sys.stderr.write(
                                    f"Partition found at {self.partition_offset} but magic is not RWFS.\n"
                                )
            except Exception as e:
                if self.verbose:
                    sys.stderr.write(f"GPT probe sector {sector_size} failed: {e}\n")
                continue

        return False

    def parse_rwfs(self) -> bool:
        """
        Parses the Qualcomm RWFS filesystem directory table and verifies record CRCs.
        """
        # Read RWFS partition header (first 128 bytes)
        hdr = self._read_exact(self.partition_offset, 128)
        if hdr[:4] != RWFS_MAGIC:
            return False

        # Header structure:
        # +0x14: Sector/block size (uint32)
        # +0x18: Total table/partition size (uint32)
        # +0x4C: Directory table offset (uint32, relative to partition base)
        # +0x54: Directory entry count (uint32)
        # +0x58: Data area base offset (uint32, relative to partition base)
        block_size, total_size = struct.unpack("<II", hdr[0x14:0x1C])
        dir_offset = struct.unpack("<I", hdr[0x4C:0x50])[0]
        dir_count = struct.unpack("<I", hdr[0x54:0x58])[0]
        data_base_offset = struct.unpack("<I", hdr[0x58:0x5C])[0]

        if self.verbose:
            sys.stderr.write(
                f"RWFS Header: block_size={block_size}, dir_offset={dir_offset}, "
                f"dir_count={dir_count}, data_base={data_base_offset}\n"
            )

        if dir_count == 0 or dir_count > 4096:
            sys.stderr.write(f"Warning: suspicious RWFS directory entry count: {dir_count}\n")
            return False

        # Each directory entry is 244 bytes (0xF4)
        ENTRY_SIZE = 244
        table_bytes = self._read_exact(self.partition_offset + dir_offset, dir_count * ENTRY_SIZE)

        for i in range(dir_count):
            e_buf = table_bytes[i * ENTRY_SIZE: (i + 1) * ENTRY_SIZE]
            if len(e_buf) < ENTRY_SIZE:
                break

            # +0x00..+0x5F: Item Name (UTF-16LE, up to 96 bytes)
            # +0x62..+0xC1: Namespace (UTF-16LE, up to 96 bytes)
            # +0xC4: Allocated size (uint32)
            # +0xC8: Data size (uint32)
            # +0xD0: Data offset relative to data_base_offset (uint32)
            # +0xD4: Stored CRC-32 (uint32)
            raw_name = e_buf[0x00:0x60].decode("utf-16le", errors="ignore").split("\x00")[0].strip()
            raw_ns = e_buf[0x62:0xC2].decode("utf-16le", errors="ignore").split("\x00")[0].strip()
            alloc_size, data_size = struct.unpack("<II", e_buf[0xC4:0xCC])
            data_offset, stored_crc = struct.unpack("<II", e_buf[0xD0:0xD8])

            if not raw_name:
                continue

            # Read record payload
            payload_abs = self.partition_offset + data_base_offset + data_offset
            try:
                payload = self._read_exact(payload_abs, data_size)
            except IOError:
                payload = b""

            calc_crc = binascii.crc32(payload) & 0xFFFFFFFF

            rec = DPPRecord(
                namespace=raw_ns,
                name=raw_name,
                allocated_size=alloc_size,
                data_size=data_size,
                data_offset=data_offset,
                stored_crc=stored_crc,
                calculated_crc=calc_crc,
                payload=payload,
            )
            self.records[rec.full_path] = rec

        return True

    def list_records(self):
        """
        Prints record metadata. NEVER prints payload content or addresses (S5).
        """
        print(f"{'RECORD NAME':<35} {'SIZE':>8}   {'CRC STATUS':<10}")
        print("-" * 58)
        for name, rec in sorted(self.records.items()):
            status = "OK" if rec.crc_valid else "CRC_MISMATCH"
            print(f"{name:<35} {rec.data_size:>8}   {status:<10}")

    def emit_bt_address(self, output_path: str) -> bool:
        """
        Parses QCOM\\BT.PROVISION, extracts reversed Bluetooth address (bytes 2-7),
        and safely writes to output_path with mode 0600.
        Never logs or prints the address.
        """
        rec = self.records.get("QCOM\\BT.PROVISION")
        if not rec:
            sys.stderr.write("Error: record 'QCOM\\BT.PROVISION' not found in DPP.\n")
            return False

        if not rec.crc_valid:
            sys.stderr.write("Error: 'QCOM\\BT.PROVISION' failed CRC-32 validation.\n")
            return False

        if len(rec.payload) < 8:
            sys.stderr.write(f"Error: 'QCOM\\BT.PROVISION' payload too short ({len(rec.payload)} < 8).\n")
            return False

        # Bytes 0-1: header/tag
        # Bytes 2-7: 6-byte BD_ADDR in Little-Endian (reversed) byte order
        # Windows driver qcbluetooth8380 reverses bytes 2-7 to form standard BD_ADDR
        b = rec.payload[2:8]
        addr_str = f"{b[5]:02X}:{b[4]:02X}:{b[3]:02X}:{b[2]:02X}:{b[1]:02X}:{b[0]:02X}\n"

        self._write_restricted_file(output_path, addr_str.encode("ascii"))
        return True

    def emit_wifi_address(self, output_path: str) -> bool:
        """
        Parses QCOM\\WLAN.PROVISION, extracts primary station MAC address,
        and safely writes to output_path with mode 0600.
        Never logs or prints the address.
        """
        rec = self.records.get("QCOM\\WLAN.PROVISION")
        if not rec:
            sys.stderr.write("Error: record 'QCOM\\WLAN.PROVISION' not found in DPP.\n")
            return False

        if not rec.crc_valid:
            sys.stderr.write("Error: 'QCOM\\WLAN.PROVISION' failed CRC-32 validation.\n")
            return False

        if len(rec.payload) < 9:
            sys.stderr.write(f"Error: 'QCOM\\WLAN.PROVISION' payload too short ({len(rec.payload)} < 9).\n")
            return False

        # Bytes 0-1: flags/version
        # Byte 2: MAC count
        # Bytes 3-8: Primary station MAC address in canonical network order
        count = rec.payload[2]
        if count < 1:
            sys.stderr.write("Error: 'QCOM\\WLAN.PROVISION' indicates zero MAC addresses.\n")
            return False

        b = rec.payload[3:9]
        mac_str = f"{b[0]:02X}:{b[1]:02X}:{b[2]:02X}:{b[3]:02X}:{b[4]:02X}:{b[5]:02X}\n"

        self._write_restricted_file(output_path, mac_str.encode("ascii"))
        return True

    def _write_restricted_file(self, path: str, content: bytes):
        """
        Writes data to path with strict 0600 permissions.
        """
        dirname = os.path.dirname(os.path.abspath(path))
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, mode=0o700, exist_ok=True)

        # Open with O_WRONLY | O_CREAT | O_TRUNC, mode 0600
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(path, flags, 0o600)
        try:
            # Ensure permissions are strictly 0600 regardless of umask
            os.fchmod(fd, 0o600)
            os.write(fd, content)
        finally:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(
        description="Safe Read-Only Qualcomm DPP / RWFS Partition Reader"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="/dev/nvme0n1",
        help="Path to block device, disk image, or partition image (default: /dev/nvme0n1)",
    )
    parser.add_argument(
        "--emit",
        metavar="PATH",
        help="Safely extract Bluetooth address and write to root-restricted file (mode 0600)",
    )
    parser.add_argument(
        "--emit-wifi",
        metavar="PATH",
        help="Safely extract Wi-Fi station MAC and write to root-restricted file (mode 0600)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose parsing diagnostics to stderr",
    )

    args = parser.parse_args()

    try:
        with DPPReader(args.target, verbose=args.verbose) as reader:
            if not reader.locate_dpp_partition():
                sys.stderr.write(
                    f"dpp-reader: No Qualcomm DPP partition (GUID f97b8793-3abf-4719-896b-7c3e9b85e104) "
                    f"or RWFS signature found on '{args.target}'.\n"
                )
                return 2

            if not reader.parse_rwfs():
                sys.stderr.write(f"dpp-reader: Failed to parse RWFS directory structure on '{args.target}'.\n")
                return 2

            if args.emit:
                if not reader.emit_bt_address(args.emit):
                    return 3
            if args.emit_wifi:
                if not reader.emit_wifi_address(args.emit_wifi):
                    return 3

            # If no emit options specified, list records
            if not args.emit and not args.emit_wifi:
                reader.list_records()

            return 0

    except PermissionError:
        sys.stderr.write(f"dpp-reader: Permission denied accessing '{args.target}' (requires root).\n")
        return 1
    except FileNotFoundError:
        sys.stderr.write(f"dpp-reader: Device or file not found: '{args.target}'\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"dpp-reader error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
