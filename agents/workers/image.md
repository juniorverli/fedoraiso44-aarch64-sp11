# image worker

**Owns:** `image/` (write), `scripts/image-*`.
**Phase:** 1 onwards.

## Mission

A Fedora 44 Workstation aarch64 live ISO that boots the Surface Pro 11 from USB with our kernel, DTB and firmware, and always leaves logs on the stick, even when the screen is dark.

## Tasks (phase 1)

1. **Builder (D16): kiwi.** `kiwi-ng` with Fedora's Workstation live description (`pagure.io/fedora-kiwi-descriptions`, branch `f44`, pinned commit) inside a privileged Fedora 44 container (no KVM in WSL2). Keep Fedora's description as the base and layer our changes on top, each marked and documented: a local repository in `out/repo/` serves our kernel RPMs with Fedora's kernel excluded; firmware comes from the staged tree; GRUB 2 entries of D9/D10; the log collector; the `SP11LOGS` fallback space. The livemedia-creator path (D11, used for M2) stays until the kiwi ISO passes L0 and L1, then it is removed.
2. **Boot (D9).** GRUB 2 only. Write the GRUB 2 configuration explicitly: menu always shown, every entry with `devicetree` for `x1p64100-microsoft-denali.dtb`, and **every entry verbose**: no `quiet`, no `rhgb`, no Plymouth, `debug loglevel=8 ignore_loglevel`, as listed in `image/README.md`. Verify on the built ISO that no `quiet`/`rhgb` survives in any `grub.cfg` (`grep -r` inside the ISO and its EFI image) and fail the build if one does. Extra arguments from the `soc-boot` request, each documented.
3. **Log collector.** A systemd service ordered for `multi-user.target` (so it runs without GDM) that writes into `<boot-id>/` on the `SP11LOGS` partition of the stick, falling back to `/EFI/sp11-logs/` on the embedded EFI partition (D7): `dmesg`, `journalctl -b`, `/proc/cmdline`, `lscpu`, `/sys/class/drm` tree, `/sys/kernel/debug/dri/*`, `/sys/class/backlight/*`, `/sys/class/remoteproc/*/state`, `/sys/class/power_supply`, `devfreq`, `regulator_summary`, `clk_summary`, debugfs `pinctrl`, `lspci -vv`, `lsusb -t`, firmware load failures, `/sys/kernel/btf/vmlinux` presence. Add the extra captures requested in each dossier's "Requests".
4. **Packages.** Fedora 44 Workstation set plus `mesa-dri-drivers`, `mesa-vulkan-drivers`, `vulkan-tools`, `glx-utils`, `glmark2`, `libdrm` tests (`modetest`), `pd-mapper`, `qrtr`, `edid-decode`. Pin the compose and NEVRAs in a build record.
5. **Tests (D10).** Implement L0 (`scripts/image-test-static.sh`), L1 (`scripts/image-test-qemu.sh`, QEMU TCG + edk2 in the Fedora 44 container) and the L2 helper (`scripts/image-test-hyperv.ps1`, prints the Hyper-V commands for the operator), as specified in `image/README.md` "Test levels". Add the `VM test (no devicetree)` boot entry, never default.
6. **M2.** First ISO with the vanilla kernel from the kernel worker and phase 1 firmware; L0 and L1 must pass, L2 if the operator approves, before it goes to the device.
7. **Build record** `out/iso/<name>.json`: ISO SHA-256, kernel NEVRA, `kernel/series` hash, firmware manifest hash, package list.

## Do not

- Put firmware in git or in any published artefact (risk S5); the ISO stays on this machine.
- Add command-line workarounds that no worker asked for.
- Ship any entry with `quiet` or a splash screen.
