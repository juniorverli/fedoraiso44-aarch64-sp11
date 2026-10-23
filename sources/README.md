# Sources

Pinned, read-only inputs shared by every worker. Owner: sources worker. Pins are in `sources.toml`.

| Link / folder | What | Pin |
|:--|:--|:--|
| `windows/` | `~/sp11-windows-dumps`: Windows 11 driver store, firmware capsules, ACPI tables, live device inventory, all taken from this unit | `MANIFEST.sha256` SHA-256 `3fd57d73e423a6c64210d440a0f254c596b3763f7ffd5e0b9b74d4923cba69c8` |
| `linux/` | `github.com/juniorverli/sp11-linux` at tag `v7.3` (shallow clone) | commit `c03c1a14507dfaf8b856c2608f9ac216021fc222` |

Both are ignored by git. Recreate `linux/` with:

```bash
git clone --branch v7.3 --depth 1 https://github.com/juniorverli/sp11-linux.git sources/linux
```

## 1. What is in `windows/`

| Path | Content |
|:--|:--|
| `DriverStore/` | 281 driver package folders (`<inf>_arm64_<hash>`) and 131 `.ini` file lists |
| `Firmware/` | UEFI capsule payloads: TCON (LCD Wi-Fi, LCD cellular, OLED), USB4 retimers 0 and 1 |
| `System32_drivers/` | `qcude.sys`, inbox TPM files |
| `live-inventory/acpi/` | DSDT, SSDT and the other ACPI tables (`.aml`/`.dat` and disassembled `.dsl`) |
| `live-inventory/pnp-present.json` | 393 present PnP devices with hardware IDs (SHA-256 `7c6c4ab8a82ee2b5b1df32407ff69e1f7bf72fdda8ba4fe4c8adc550006e772b`) |
| `live-inventory/<topic>/` | Registry, WMI and event-log captures per topic (display, panel, audio, camera, sensors, thermal, usb4, ...) |
| `driver-inventory.txt` | INF provider, class, version and hardware IDs per package |
| `MANIFEST.sha256` | SHA-256 of every file under `DriverStore/`, `Firmware/`, `System32_drivers/` |
| `rea-*` | Earlier reverse-engineering output. **Not an input**: treat as untrusted until reproduced |

Several INFs exist in two or three versions (for example `qcpep.wd8380`, `qcsubsys8380`). The active one is the version Windows bound to the present device; confirm it with `live-inventory` before analysing a binary.

## 2. Is the DriverStore original? Yes (Verified, 2026-10-23)

Three independent checks:

1. **Catalog signatures.** All 243 `.cat` files carry a PKCS#7 signature whose leaf is `CN = Microsoft Windows Hardware Compatibility Publisher`, issued by `Microsoft Windows Third Party Component CA 2012` under `Microsoft Root Certificate Authority 2010`. This is the WHQL chain. Command:

   ```bash
   for c in sources/windows/DriverStore/*/*.cat; do
     openssl pkcs7 -inform DER -in "$c" -print_certs -noout | grep -m1 '^subject'
   done | sort | uniq -c
   ```

   The 38 package folders without a `.cat` are Windows inbox drivers (`hidi2c`, `usbaudio2`, `c_camera`, ...), whose catalogs live in the system catalog store, not in the package.

2. **File hashes.** Each `.ini` lists the files of its package with a SHA-1. Non-PE files match the plain SHA-1; PE files (`.sys`, `.dll`, `.exe`) match the Authenticode SHA-1, which is the hash a catalog signs. `scripts/verify-driverstore.py` checks both: **778 of 778 files match, 0 mismatches, 0 missing.**

   ```bash
   python3 -I scripts/verify-driverstore.py sources/windows/DriverStore
   ```

3. **Manifest.** `sha256sum -c MANIFEST.sha256` passes for every entry, so nothing changed since extraction.

Conclusion: the packages are the signed originals. Downloading Microsoft's Surface Pro 11 driver MSI is not needed for authenticity. It is only useful to check whether a newer release exists (open task for the sources worker).

## 3. What not to trust

- `windows/rea-evidence/`, `windows/rea-derived/`, `windows/rea-snapshots/`: outputs of an earlier effort. Reproduce before use.
- Any repository other than this one. Values found elsewhere enter as **Hypothesis** (`agents/protocol.md` §5).
