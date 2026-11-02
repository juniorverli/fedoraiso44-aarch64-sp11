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

## 4. Public Surface reference inputs (2026-11-02)

These inputs are read-only references, not evidence that a feature is safe or works on this unit. They do not replace the project's Linux 7.3 baseline. The extracted trees and original archives live under `out/reference-inputs/`, which is git-ignored; `sources.toml` pins the commits, archives and selected files. Run `python3 -I scripts/verify-reference-inputs.py` from any directory to verify them. Re-fetch the archive URLs at the pinned commits and extract with `tar -xzf ... --strip-components=1` into the corresponding directory if the ignored files are missing. GitHub-generated archive hashes are verified against the pinned local bytes; an upstream archive regeneration can require investigation.

- Kernel: `out/reference-inputs/linux-sp11/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi`, the `x1e80100-microsoft-denali-*.dts` and `x1p64100-microsoft-denali*.dts` variants, and `hamoa.dtsi` (GPU, GMU, OPPs and SMMU). Inspect the whole extracted tree for dependencies. The reference is GPL-2.0-only with file-specific SPDX exceptions; see its `COPYING` and `LICENSES/`.
- Packaging: `out/reference-inputs/archlinux-repo/linux-sp11/{PKGBUILD,config.aarch64}`, `sp11-grab-fw/{PKGBUILD,sp11-grab-fw.sh}`, `sp11-audioreach-topology/PKGBUILD`, `alsa-ucm-conf-sp11/{PKGBUILD,847.patch}`, `sp11-ath12k-board/`, `sp11-mac-fixup/`, and `packages.list`. Package metadata identifies BSD-3-Clause for grab-fw, topology, UCM, and MAC fixup; the kernel package is GPL-2.0-only and ath12k board output is `custom:qcom-linux-firmware`. Check individual files and upstream licenses before reuse.
- Audio: `out/reference-inputs/audioreach-topology/X1E80100-Microsoft-Surface-Pro-11.m4`, `audioreach/`, `util/`, and `CMakeLists.txt`. The archive matches the topology PKGBUILD's SHA-256. Its sources are BSD-3-Clause; that revision has no Python files, and the target uses m4 and `alsatplg`.
- Firmware reference: [Surface/8380_DEN](https://github.com/WOA-Project/Qualcomm-Reference-Drivers/tree/ad6e472836d40d6ba81855e57bbd3c7c0522735f/Surface/8380_DEN), observed latest directory `200.0.49.0` on 2026-11-02. `sp11-grab-fw` dynamically selects the highest version, so this observation is not a fixed choice in that script. It names `adsp_dtbs.elf` and `qcadsp8380.mbn` from `surfacepro_ext_adsp8380.cab`, `cdsp_dtbs.elf` and `qccdsp8380.mbn` from `qcnspmcdm_ext_cdsp8380.cab`, and `qcdxkmsuc8380.mbn` and `qcvss8380.mbn` from `qcdx8380.cab`. The CAB names were confirmed in that directory; their contents were not downloaded or verified. Firmware is proprietary and is not redistributed here (S5).

### Kernel reference queue

The reference commit is based on Arch kernel commit `64a90897d3c5`. In the 45-commit range from that base to the pinned head, audio-specific changes are `2db74c78d5f2433ac58db8580b3d800dedc2f415` (DisplayPort audio) and `d34ce0c788b53b25b7424cbf54f5123ee6e419ee` (microphone distortion). Display/video-adjacent changes include `a5eb6d9a0b75fbddba999e55691147f84cb93e77` (eDP HPD), `5ec8e2615864cebdb56835b7b2bcc750f62fe1fb` (LCD backlight), and `b915c5945cb51b5dabf9bddcb8b9f97437e6f674` (IRIS video codec). No GPU- or camera-specific commit appears by subject in this range; existing base-tree nodes and earlier history still require inspection. This is a queue inventory, not a claim of camera support. Review the [complete commit range](https://github.com/dwhinham/linux-sp11/compare/64a90897d3c5...d6333a45f9bc9a1fa82a90146dbc9c159e83cd1b) and apply safety rules in `plan/risks.md` before using any values.
