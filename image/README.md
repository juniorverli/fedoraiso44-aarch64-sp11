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

1. **Bootloader: GRUB 2** (Fedora `grub2-efi-aa64`), and nothing else. Every entry loads the DTB with the GRUB 2 `devicetree` command: `devicetree /boot/dtb-<kver>/qcom/x1p64100-microsoft-denali.dtb`.
2. **Always boot in debug, never quiet.** See "GRUB 2 and the kernel command line" below.
3. **Log collector.** A systemd unit that, on every boot, writes `dmesg`, the journal, `/sys/kernel/debug/dri`, `/sys/class/drm`, `/sys/class/backlight`, `regulator_summary`, `clk_summary`, `pinctrl` and `devfreq` into `/EFI/sp11-logs/<boot-id>/` on the stick. It must run even if GDM never starts (`multi-user.target`).
4. **Kernel with BTF** (check `/sys/kernel/btf/vmlinux` in the collector).
5. Kernel command-line additions are recorded in the build record with the reason for each.

ISO builder: **livemedia-creator** (lorax), decision D11 in `plan/decisions.md`. It runs as `livemedia-creator --no-virt --make-iso --ks image/<name>.ks` inside a privileged Fedora 44 container, because WSL2 has no KVM for the default virt-install mode.

## GRUB 2 and the kernel command line

Rule (decision D9): every boot of every test ISO is verbose. `quiet`, `rhgb` and Plymouth are removed from all entries, including the ones the ISO builder generates by default.

GRUB 2 itself:

- `set timeout_style=menu`, `set timeout=10`: the menu is always shown, never hidden.
- Entries are written explicitly in our GRUB 2 configuration; the builder's defaults are not trusted to drop `quiet`.
- Each entry: `linux` + `devicetree` + `initrd`.

Kernel command line, common to all entries:

| Argument | Why |
|:--|:--|
| *(no `quiet`, no `rhgb`)* | Kernel and systemd messages stay on screen |
| `debug` | Kernel console log level to debug |
| `loglevel=8 ignore_loglevel` | Print every printk level on the console |
| `printk.devkmsg=on log_buf_len=16M` | Keep early messages from being dropped or rate-limited, for the log collector |
| `rd.plymouth=0 plymouth.enable=0` | No splash screen in the initramfs or the system |
| `systemd.show_status=1 rd.udev.log_level=info` | Unit start/fail lines visible |
| `rd.live.image root=live:CDLABEL=<label>` | Fedora live boot |
| `console=tty0` | Panel console |

Entries:

| Entry | Extra arguments | Use |
|:--|:--|:--|
| `SP11 debug` (default) | — | Normal test boot |
| `SP11 debug + DRM trace` | `drm.debug=0x1ff` | Display problems (very verbose) |
| `SP11 debug nomodeset` | `nomodeset` | Fallback when the panel goes dark; keeps the firmware framebuffer |
| `SP11 debug, stop in initramfs` | `rd.break=pre-mount` | Rescue shell before the root is mounted |

Any further argument (for example `clk_ignore_unused`) needs a request from a component worker with a log that justifies it, and is listed with its reason in the build record.

### Secure Boot

Our kernel is not signed by Fedora, so shim rejects it with Secure Boot on. GRUB 2 in Secure Boot lockdown also refuses the `devicetree` command (Inference: lockdown blocks DTB loading; the image worker confirms on the Fedora 44 GRUB 2 build). The operator therefore disables Secure Boot in the Surface UEFI before booting test ISOs. Signing with our own key (MOK) is a later option, and does not lift the `devicetree` restriction.

## Test levels before the device

Nothing reaches the Surface until levels 0 and 1 pass. Host facts (2026-10-24): WSL2 Ubuntu 24.04 aarch64, 10 cores, 12 GB RAM, **no `/dev/kvm`** (so QEMU runs emulated, TCG), Docker 28 aarch64, Windows 11 Home with Hyper-V installed (`New-VM` present, `vmms` running). QEMU, edk2, `xorriso`, `mtools`, `dtc`, `isomd5sum`, `dracut` and `edid-decode` are missing on the host: every test runs inside the Fedora 44 build container, nothing is installed on the host.

| Level | Where | What it proves | When |
|:--|:--|:--|:--|
| L0 static | container | ISO is well formed and contains exactly what the build record says | every build |
| L1 emulated boot | QEMU `virt`, TCG, edk2 aarch64, in the container | GRUB 2 menu, kernel + initramfs + live root, systemd, GDM on virtio-gpu, log collector | every build |
| L2 virtual machine | Hyper-V Gen2 ARM64 VM on this Windows | Same as L1 at native speed; Anaconda install to a virtual disk | before each device boot; needs operator approval to create the VM |
| L3 device | the Surface, USB stick in DD mode | Everything SP11-specific: DTB, LCD, GPU, all components | after L0-L2 |

### Why this works from WSL2

- L0 and L1 run inside the Fedora 44 container on WSL2. L1 needs no `/dev/kvm`: QEMU TCG emulates the CPU in software. WSL2 is itself a Hyper-V VM and does not get nested virtualization here, which is why there is no KVM and why L1 is slow.
- L2 does not run inside WSL2. The Hyper-V VM is a sibling of the WSL2 VM on the same Windows hypervisor, with hardware virtualization. It is driven from Windows (PowerShell as an administrator), not from the container.
- Memory: the machine has 16 GB and WSL2 sees about 12 GB. An L2 VM with 4 GB plus a running kernel build will not fit together; run L2 when no kernel build is running, or cap WSL2 in `.wslconfig`.
- The kernel carries the Hyper-V guest drivers for arm64 (`CONFIG_HYPERV` depends on `ARM64 && !CPU_BIG_ENDIAN`, `sources/linux/drivers/hv/Kconfig`), added to `kernel/config/sp11.config`. Whether `hyperv_drm` gives a graphical console on an ARM64 Gen2 VM is TBD; if not, L2 checks GDM through the log collector instead of the screen.

### L0 static checks (fail the build on any miss)

1. Hybrid layout: ISO 9660 + GPT/MBR with the EFI partition (`xorriso -indev ... -report_el_torito`, `sgdisk -p`); `checkisomd5` passes.
2. GRUB 2: every `grub.cfg` (ISO and embedded EFI image) has no `quiet`/`rhgb`, shows the menu, and every `SP11` entry has a `devicetree` line pointing at a file that exists.
3. DTB: present, decompiles with `dtc`, root compatible is `microsoft,denali-lcd`; the nodes our patches add or change are present (`fdtget`).
4. Kernel: `vmlinux`/`vmlinuz` NEVRA equals the build record; BTF present; every symbol of `kernel/config/sp11.config` has its value in the shipped `config-*`.
5. Modules: `msm`, `panel-edp`, `phy-qcom-edp` and the rest of phase 1 present in the squashfs and, where needed early, in the initramfs (`lsinitrd`).
6. Firmware: every `firmware/manifest.toml` entry in scope is at its Linux path with the expected SHA-256; nothing else from `sources/windows` is in the image.
7. Privacy: no MAC address, serial number or `sources/windows` path in any file of the image, except the local Bluetooth address file when D-bluetooth is active.
8. Log collector unit present and enabled for `multi-user.target`.

### L1 emulated boot

- QEMU `virt` machine with edk2 firmware, the ISO as a USB disk, a second small FAT disk labelled `SP11LOGS`, serial console captured by the test script.
- A boot entry **`VM test (no devicetree)`**, never the default, boots the same kernel with the firmware-provided description instead of the SP11 DTB (the SP11 DTB describes hardware a VM does not have).
- Pass: GRUB menu shows all entries; boot reaches `multi-user.target` and GDM; `/sys/kernel/btf/vmlinux` exists; the collector wrote a complete `<boot-id>/` to `SP11LOGS`; no unit in `failed` state other than an allow-list of hardware-only units.
- TCG is slow: budget 30-45 min per boot; run it unattended.

### L2 Hyper-V VM

- Gen2 ARM64 VM, Secure Boot off, ISO attached, a VHDX for the install test and a small VHDX formatted FAT `SP11LOGS`.
- Same pass criteria as L1, plus a full Anaconda install to the VHDX and a reboot into the installed system.
- Creating or changing VMs on Windows is an operator-approved action (`scripts/image-test-hyperv.ps1` prints the commands; the operator runs them).

### What only the device (L3) can answer

The DTB itself, LCD, backlight, GPU, touch, audio, cameras, battery, every SP11 component. L0-L2 only prove the image, the packaging and the collector.

## Media format and how the stick is written

The deliverable is a **hybrid ISO** (ISO 9660 plus a GPT/MBR partition table with an embedded EFI system partition), the same layout as Fedora's own live media. It must be written **as a raw image (DD mode)**: `dd`, Fedora Media Writer, or Rufus in "DD image" mode.

Why the writing mode is not indifferent:

1. Fedora's live boot finds its root by volume label (`root=live:CDLABEL=...`). Tools that extract the ISO onto a FAT stick (Rufus "ISO image" mode, copying files by hand) can change the label or the layout, and the boot fails.
2. GRUB, its `devicetree` line and the DTB live in the embedded EFI partition. File-copy modes and boot managers that chain-load ISOs (Ventoy) may bypass that GRUB configuration, so the kernel would start without our DTB. Ventoy and file-copy modes are **unsupported**.
3. The log collector needs a known, writable place on the stick.

Logs on a DD-written stick:

- The embedded EFI partition is small (a few MB free) and writing to it changes the ISO checksum (`checkisomd5` fails afterwards; harmless for booting).
- So the collector writes to a FAT partition labelled `SP11LOGS` when one exists, and falls back to `/EFI/sp11-logs/` on the embedded EFI partition with a size cap (newest boot first, compressed).
- Operator procedure, once per stick: after `dd`, create a FAT32 partition labelled `SP11LOGS` in the free space after the ISO (or use a second stick with that label).

Open decision **D7** for the image worker: keep the hybrid ISO (recommended, matches Fedora tooling and Anaconda), or also produce a raw disk image with a large EFI partition and a persistent logs partition for development boots.
