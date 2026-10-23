# image worker

**Owns:** `image/` (write), `scripts/image-*`.
**Phase:** 1 onwards.

## Mission

A Fedora 44 Workstation aarch64 live ISO that boots the Surface Pro 11 from USB with our kernel, DTB and firmware, and always leaves logs on the stick, even when the screen is dark.

## Tasks (phase 1)

1. **Builder (decision D4).** Evaluate Kiwi (Fedora's own live-media tool) against `livemedia-creator`: aarch64 support, custom kernel RPMs from a local repo, adding local firmware files, GRUB `devicetree`, reproducibility, running inside a container on this host. Write the recommendation for the orchestrator.
2. **Boot.** UEFI boot with GRUB; every entry loads `x1p64100-microsoft-denali.dtb`. Entries: normal, `nomodeset`, debug (`drm.debug=0x1ff loglevel=7 ignore_loglevel`). Kernel command line from the `soc-boot` request; every argument documented.
3. **Log collector.** A systemd service ordered for `multi-user.target` (so it runs without GDM) that writes into `/EFI/sp11-logs/<boot-id>/` on the stick: `dmesg`, `journalctl -b`, `/proc/cmdline`, `lscpu`, `/sys/class/drm` tree, `/sys/kernel/debug/dri/*`, `/sys/class/backlight/*`, `/sys/class/remoteproc/*/state`, `/sys/class/power_supply`, `devfreq`, `regulator_summary`, `clk_summary`, debugfs `pinctrl`, `lspci -vv`, `lsusb -t`, firmware load failures, `/sys/kernel/btf/vmlinux` presence. Add the extra captures requested in each dossier's "Requests".
4. **Packages.** Fedora 44 Workstation set plus `mesa-dri-drivers`, `mesa-vulkan-drivers`, `vulkan-tools`, `glx-utils`, `glmark2`, `libdrm` tests (`modetest`), `pd-mapper`, `qrtr`, `edid-decode`. Pin the compose and NEVRAs in a build record.
5. **M2.** First ISO with the vanilla kernel from the kernel worker and phase 1 firmware.
6. **Build record** `out/iso/<name>.json`: ISO SHA-256, kernel NEVRA, `kernel/series` hash, firmware manifest hash, package list.

## Do not

- Put firmware in git or in any published artefact (risk S5); the ISO stays on this machine.
- Add command-line workarounds that no worker asked for.
