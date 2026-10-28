# Address diagnosis, source choices and validation (2026-10-28)

## Evidence boundary

Verified source chain: NVM address extraction is in `sources/linux/drivers/bluetooth/btqca.c:411-414`; comparison with the controller and the property quirk are at `:683-708`. `sources/linux/net/bluetooth/hci_sync.c:3745-3760` reads the parent's `local-bd-address`; `:5256-5320` leaves a controller unconfigured without a usable address. `sources/linux/net/bluetooth/mgmt.c:430-475` filters it out of the normal index list. Bluetooth daemon at the exact Fedora package commit listens for normal index events and reads that list ([BlueZ `8750129efca8`, `src/adapter.c:10466-10474`](https://raw.githubusercontent.com/bluez/bluez/8750129efca8/src/adapter.c)). Therefore this state can hide an otherwise initialized UART controller from GNOME.

M5 **does not capture this state**. Its healthy daemon and successful firmware setup eliminate some alternatives; the previous project's working-address service is supporting evidence only. Grade: Hypothesis for this boot's cause. Do not report the problem as solved until the helper journal/collector and GNOME confirm it.

## Source options

| Option | Evidence and limitation | Decision |
|:--|:--|:--|
| Controller/OTP address | Linux already reads it; a valid identity needs no override. Windows driver contains an OTP-address string, but this unit's OTP status is unknown. | Prefer automatically; helper leaves a configured controller alone. No new vendor commands. |
| ACPI or platform DPP | BTH0 `_DSM` returns NVM-selection/configuration data, not a public address (`sources/windows/live-inventory/acpi/dsdt.dsl:68612-68700`). Windows strings mention DPP, but no usable Linux accessor, key or byte order is established. | Investigate only with a documented source; no guessed offsets, UEFI-variable writes or provisioning. |
| Parse Windows registry directly at Linux boot | No exact address key/type has been evidenced. A Windows partition may be hibernated or BitLocker-encrypted (S4); an export still needs a defined schema. | Do not mount or scrape Windows on boot. A read-only Windows export can supply the local file offline. |
| Explicit operator file containing Windows-observed address | Private inventory already provides `BT_MAC`. Its provenance is observed Windows identity, not proven OTP. A small file is sufficient; no registry parser is needed in Fedora boot. | **Recommended.** Provision after writing the ISO; read at boot from the stick's ESP, or root-owned `/etc/sp11/bt-address` on installed Fedora. |
| UUID-derived or freshly random identity | No evidence that an Ethernet-style locally administered derivation supplies the required dual-mode public identity. Random changes also invalidate bonds. BlueZ's random-static path is for LE-only adapters (`src/adapter.c:9586`). | Removed from the interrupted helper. No automatic fallback. |
| Put `local-bd-address` in DT, embed a file at ISO build | Core supports the property, but this stores a unit identity in a reusable artifact. The earlier project embedded the file. | Rejected by the operator's requirement/S5. |

## Implementation

`userspace/sp11-bt-address` uses Fedora's `bluez` package. It checks the hci0 parent's `qcom,wcn7850-bt` compatible, retries setup-time queries, and requires exactly the `public-address` missing option plus advertised support. It makes no change to a controller with no missing options, another adapter, an unknown reply or an external-configuration requirement. BlueZ config callbacks can return process status zero after reporting a management error, so reply fields and post-change readiness are checked as well ([exact Fedora CLI commit, `client/mgmt.c:1169-1194`, `:1294`](https://raw.githubusercontent.com/bluez/bluez/8750129efca8/client/mgmt.c)).

Source precedence: explicit CLI file (for installed-system integration/testing), otherwise `/etc/sp11/bt-address` when present, otherwise `EFI/sp11/bt-address` on a FAT `BOOT` partition **of the disk backing `/run/initramfs/live`**. The reader requires that live source to be an ISO9660 partition, resolves its parent through sysfs, mounts only a sibling partition read-only with `nosuid,nodev,noexec`, and unmounts on success or failure. It does not search global labels, mount the Windows partition, source the file as code, or copy it into a build artifact. Missing/invalid input fails visibly without generating an identity. The systemd service uses a private mount namespace.

`btmgmt public-addr` invokes existing `MGMT_OP_SET_PUBLIC_ADDRESS`; the kernel rejects it on a powered controller and updates host state (`sources/linux/net/bluetooth/mgmt.c:8376-8426`). QCA's existing callback uses the runtime write-address command (`sources/linux/drivers/bluetooth/btqca.c:1005-1025`), with non-persistent setup (`sources/linux/drivers/bluetooth/hci_qca.c:2557`). This is controller runtime configuration, with no OTP, flash, persistent NVM update, firmware-file replacement or firmware-update utility. The helper does not force power-off or unblock rfkill. BlueZ sees the normal index-added event after configuration; no bluetoothd restart or ordering dependency is needed ([management API](https://bluez.readthedocs.io/en/latest/mgmt-api/#set-public-address-command)).

Six bounded query attempts precede the update, and six bounded indexed-info attempts verify that the supplied address is actually reported after asynchronous configuration. The helper logs only state, never addresses, command output or identifiers. Its first missing-option message provides diagnosis in the same boot that attempts the fix. No kernel/DT patch is proposed, so no kernel build or BTF setting changes are involved.

## Checks

Executed in `sp11-fedora-image:44` (Fedora 44 aarch64), with `bluez-5.87+1.git8750129efca8-1.fc44.aarch64`, `ShellCheck-0.11.0-4.fc44.aarch64`, systemd 259.10:

- `bash -n` and ShellCheck on both executables: pass.
- Install helper into the ephemeral container and `systemd-analyze verify .../sp11-bt-address.service`: pass.
- `python3 userspace/check.py`: 14 tests pass. Tests exercise setup races; configured-controller no-op; repeat invocation; invalid/default/missing identity; zero-exit management errors; another controller; post-write rejection/mismatch; collector masking; boot-source selection, read-only mount flags and cleanup. Fake block nodes/utilities are used; no hardware or real disk is touched.
- `scripts/index.py --check`: 21 components, 0 errors. `git diff --check`, component whitespace/local-link checks, and scanning for literal/private captured addresses: pass. No git write command was run.
- Fedora `atheros-firmware-20261019-1.fc44` confirms the listed firmware files. Compressed SHA-256: `hmtnv20.bin.xz` = `d7dc986ef9e089201d4ad4758efda1b1e00a8b34903d52956fa0145ebb892bc6`; `hmtbtfw20.tlv.xz` = `9668138dd3d360d2af5fd37c636ed5395f97161a9ed527e1aa5de5134387c516`.

Limitations: the tests emulate management replies and mounting; they do not prove real WCN7850 response, FAT mounting, systemd device activation, pairing or RF performance. The worker stays `designed` until image integration, independent cross-check and device evidence. The image owner must verify activation through first-boot presets and real loopback/L1 mounting before L3.
