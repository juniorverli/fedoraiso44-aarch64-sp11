# Image

Owner: image worker (`agents/workers/image.md`).

Produces the Fedora 44 Workstation aarch64 live ISO that boots the Surface Pro 11 from a USB stick and can install to the NVMe.

## Contract

| Input | From |
|:--|:--|
| Kernel RPMs and DTB | `out/rpms/` (kernel worker) |
| Firmware | `firmware/manifest.toml`, copied from `sources/windows` at build time |
| Fedora packages | Fedora 44 repositories, pinned in `sources/sources.toml [fedora]` |

| Output | Where |
|:--|:--|
| ISO and its SHA-256 | `out/iso/` |
| Build record: kernel NEVRA, series, firmware list, package list | `out/iso/<name>.json` |

## Must have, every ISO

1. **Device tree loading.** The machine boots through UEFI and Linux needs `x1p64100-microsoft-denali.dtb`. GRUB `devicetree` line (or an equivalent) on every entry.
2. **Boot entries:** normal; `nomodeset` fallback; serial-free debug entry with `drm.debug=0x1ff loglevel=7 ignore_loglevel`.
3. **Log collector.** A systemd unit that, on every boot, writes `dmesg`, the journal, `/sys/kernel/debug/dri`, `/sys/class/drm`, `/sys/class/backlight`, `regulator_summary`, `clk_summary`, `pinctrl` and `devfreq` into `/EFI/sp11-logs/<boot-id>/` on the stick. It must run even if GDM never starts (`multi-user.target`).
4. **Kernel with BTF** (check `/sys/kernel/btf/vmlinux` in the collector).
5. Kernel command-line additions are recorded in the build record with the reason for each.

ISO builder choice (Kiwi or livemedia-creator) is decision D4 in `plan/decisions.md`.
