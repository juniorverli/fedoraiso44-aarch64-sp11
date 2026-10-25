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

Our kernel is not signed by Fedora, so shim rejects it with Secure Boot on. GRUB 2 in Secure Boot lockdown also refuses the `devicetree` command: **Verified in the source of `grub2-2.12-66.fc44`** (`devicetree` is registered with `grub_register_command_lockdown`, and lockdown is entered whenever UEFI Secure Boot is enabled); evidence and line numbers in `image/evidence/2026-10-24-grub-devicetree-lockdown.md`. A runtime demonstration is TBD (the unsigned kernel would stop at shim first). The operator therefore disables Secure Boot in the Surface UEFI before booting test ISOs. Signing with our own key (MOK) is a later option, and does not lift the `devicetree` restriction.

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

## How to build and test (image worker, 2026-10-24)

Everything runs in the Fedora 44 aarch64 container (`registry.fedoraproject.org/fedora:44`, D12); nothing is installed on the host.

```bash
scripts/image-container.sh build        # once: image sp11-fedora-image:44 from image/Containerfile
scripts/firmware-stage.sh               # firmware worker: out/firmware-root/
scripts/image-build.sh                  # kiwi ISO (D16) -> out/iso/<name>.iso + .json; --builder lmc for the M2 path
                                        # (needs out/rpms/, out/firmware-root/)
scripts/image-test-static.sh            # L0 on the newest ISO -> out/iso/<name>.l0.txt
scripts/image-test-qemu.sh              # L1, 30-90 min under TCG -> out/iso/<name>.l1.txt
```

`scripts/image-build.sh` and `scripts/image-test-qemu.sh` refuse to start while `out/.kernel-build.lock` is held, and cap the container memory (`--mem GiB` / `SP11_DOCKER_MEMORY`). `image-build.sh --smoke` uses Fedora's own kernel and no firmware, only to exercise the pipeline; a smoke ISO's record says `"smoke": true`, its Denali checks are reported as SKIP, and it never goes to the device.

| File | Role |
|:--|:--|
| `image/Containerfile` | Build and test container: lorax, livemedia-creator (`lorax-lmc-novirt`), anaconda, pykickstart, dracut, `grub2-efi-aa64`, `shim-aa64`, xorriso, mtools, isomd5sum, dtc, `qemu-system-aarch64-core`, `edk2-aarch64`, `edid-decode` (from `v4l-utils`) |
| `image/sp11-live.ks` | Kickstart template (placeholders are resolved by `image-build.sh`) |
| `image/overlay/` | Files copied into the image: log collector and its unit, dracut and GRUB defaults |
| `image/lorax-templates/live/` | Our copy of the lorax live templates for aarch64 (see "Lorax template changes") |
| `image/expected-dtb.txt`, `expected-modules.txt` | Inputs of L0 checks 3 and 5 |
| `image/l1-allowed-failed-units.txt` | L1 allow-list of hardware-only units (empty until a run shows which) |
| `image/tools/` | `qemu_boot_test.py` (L1 driver), self-tests: `template_selftest.py`, `toy_iso.sh`, `collector_selftest.sh`, `qemu_driver_selftest.sh` (+ `fake_qemu.py`) |

### Kickstart origin (D11, D12)

Fedora no longer publishes kickstarts for Workstation live media. Pagure `fedora-kickstarts` was retired and moved to `forge.fedoraproject.org/releng/spin-kickstarts`, which was retired on 2025-12-17; Fedora 44 live media are built with kiwi (`pagure.io/fedora-kiwi-descriptions`, branch `f44`, commit `dfc49a5a10f69941179fdadd96aa6a5984f7c677`). D11 asks for livemedia-creator, so `sp11-live.ks` is the flattened union of three files of the **f43 branch of spin-kickstarts (commit `d1bbfe1211ead018371627991c529b4910f1bbd1`, 2025-09-30), the newest Fedora kickstart**: `fedora-live-workstation.ks`, `fedora-live-base.ks`, `fedora-workstation-common.ks` (plus the repo include). The kiwi f44 GNOME description was read to confirm the package set. Differences, each marked `SP11:` in the file:

| Change | Reason |
|:--|:--|
| Repos hard-coded to Fedora 44 (no `$releasever`), `arch=aarch64` | one pinned release |
| `sp11-local` repo `file:///out/repo` (created from `out/rpms/` by `image-build.sh`), cost 10; Fedora's kernels excluded with `--excludepkgs` on `fedora` and `updates` | only our vanilla kernel RPMs (D13) can be installed; `--smoke` leaves Fedora's kernel in |
| `kernel-core`, `kernel-modules-core` added to the kernel package lines | D13 subpackage names |
| `grub2-efi-aa64`, `-cdboot`, `shim-aa64`, `efibootmgr`, `grub2-tools*` added | lorax `live/aarch64.tmpl` makes no ISO unless `boot/efi/EFI/*/gcdaa64.efi` exists; the install needs GRUB |
| `qcom-firmware` named explicitly | firmware worker request 1: `linux-firmware` does not pull it in; it carries `qcom/gen70500_sqe.fw.xz` and `gen70500_gmu.bin.xz` |
| `mesa-dri-drivers`, `mesa-vulkan-drivers`, `vulkan-tools`, `glx-utils`, `glmark2`, `drm-utils` (provides `modetest`), `v4l-utils` (provides `edid-decode`), `qrtr`, `dtc`, `pciutils`, `usbutils`, `bpftool`, `mtools`, `dosfstools` | task list and dossier requests; collector needs the tools |
| `pd-mapper`, `qrtr-ns` **not** installed | Fedora 44 has no `pd-mapper` (Verified, `dnf repoquery`; `qrtr-1.2-2.fc44` obsoletes it and ships only `qrtr-cfg`/`qrtr-lookup`), and the kernel has an in-kernel mapper and name service (firmware README section 4); the dsp-subsystems dossier request is answered |
| Plymouth packages excluded | D9; a dry-run resolution of the package set with these exclusions succeeded on Fedora 44 (they are weak dependencies only) |
| `selinux --permissive` instead of `--enforcing` | the WSL2 build kernel has no vfat and an unverified SELinux state; labels cannot be trusted to be written in the container. TBD: check whether labels are written; if yes, go back to `--enforcing` |
| `%post --nochroot`: copy `image/overlay/` and `out/firmware-root/lib/firmware/` into `/usr/lib/firmware` of the image; record the installed firmware listing and package list in `out/image-work/` | collector, services, firmware (firmware request 2) |
| `%post`: enable `sp11-log-collector.service`, mask Plymouth units, write `/etc/dracut.conf.d/91-sp11-drivers.conf` with the early display drivers the kernel really has | dracut aborts the whole initramfs on an unknown `add_drivers` name (seen in a toy build) |
| livemedia-creator is run with `--compression zstd` (level 15) | decompression speed under TCG; L0 checks `CONFIG_SQUASHFS_ZSTD=y` |

### Initramfs and firmware (firmware worker decision F1)

`qcom_q6v5_pas` requests the DSP firmware once with `request_firmware_nowait` and has no user-helper fallback. **Decision: the driver is kept out of the initramfs** (`omit_drivers+=" qcom_q6v5_pas "` in `image/overlay/etc/dracut.conf.d/90-sp11.conf`), so udev loads it after switch-root, when `/usr/lib/firmware` of the root file system is readable. The five staged files are therefore not added to the initramfs. L0 check 5 fails the image if the driver is in the initramfs. Open (Inference): the GPU zap shader and `gen70500_*` are requested by `msm` when the GPU is first opened, which is after switch-root; if `msm` requests them during probe in the initramfs they would be missing there. M2 logs will show it (`firmware-failures.txt` of the collector).

### Lorax template changes

livemedia-creator is run with `--lorax-templates image/lorax-templates`. Our `live/` directory is a copy of `lorax-templates-generic-44.7-1.fc44` `/usr/share/lorax/templates.d/99-generic/live/` (upstream SHA-256: `aarch64.tmpl` `48e4f662...`, `efi.tmpl` `f018c29d...`, `config_files/aarch64/grub2-efi.cfg` `71b383ad...`). Every difference:

1. `live/aarch64.tmpl`
   - **DTB lookup.** Finds `qcom/x1p64100-microsoft-denali.dtb` (override with `SP11_DTB`, used by `--smoke`) in `/lib/modules/<kver>/dtb/` (Fedora `kernel.spec` layout) or `/boot/dtb-<kver>/`, and fails the build when it is missing or when the image holds other than exactly one kernel.
   - **DTB on the ISO.** Installs it as `/images/pxeboot/dtb/qcom/x1p64100-microsoft-denali.dtb`, next to kernel and initrd. This differs from the `devicetree /boot/dtb-<kver>/...` line of "Must have" item 1: that path exists only on an installed system (BLS); on the ISO GRUB's root is the ISO file system.
   - **Hybrid ISO (D7).** `xorrisofs` gets `-appended_part_as_gpt`, `-append_partition 2 C12A7328-... images/efiboot.img`, `-iso_mbr_part_type EBD0A0A2-...` and the El Torito entry `-e '--interval:appended_partition_2:all::'`, the options lorax uses in `x86.tmpl`. Upstream `aarch64.tmpl` makes a plain El Torito ISO without a partition table.
   - Passes `dtbpath` to `efi.tmpl`.
2. `live/efi.tmpl`
   - `dtbpath` argument and `replace @DTBPATH@ ...` (the DTB path in `grub.cfg`).
   - `mkefiboot` replaced by `config_files/aarch64/mk-efiboot.sh` (item 4).
3. `live/config_files/aarch64/grub2-efi.cfg`: rewritten for D9 and D10, see "GRUB 2 configuration". Upstream has `set default="1"`, `timeout=60` (menu hidden by default style), `quiet rhgb` on every entry and no `devicetree`.
4. `live/config_files/aarch64/mk-efiboot.sh` (new): builds `images/efiboot.img` with `mkfs.vfat` + `mtools` (no mount), FAT label `ANACONDA`, with **16 MiB free** inside for `/EFI/sp11-logs`. Reason: `mkefiboot` loop-mounts a vfat image and the WSL2 kernel of the build host has no vfat driver (`modprobe vfat`: not found, `/proc/filesystems` has no vfat); also gives the logs fallback its free space. Tested: toy ISO has 19.9 MB free in the embedded ESP.

To list the differences mechanically: `scripts/image-container.sh run diff -ru /usr/share/lorax/templates.d/99-generic/live /sp11/image/lorax-templates/live`.

### GRUB 2 configuration

Five entries, in this order, default is the first, menu always shown (`timeout_style=menu`, `timeout=10`). Common arguments: those of "GRUB 2 and the kernel command line" (`$sp11_common`, taken from this README, not trusted from any default). Differences against that table, each recorded in the build record:

| Addition | Where | Reason |
|:--|:--|:--|
| `sp11.entry=<id>` (`debug`, `drm-trace`, `nomodeset`, `initramfs`, `vmtest`) | every entry | The L1 test checks that its menu selection booted (`sp11.entry=vmtest`); the logs show which entry the operator chose. The kernel ignores it (dotted parameter of no module). |
| `console=ttyAMA0,115200` after `console=tty0` | `VM test` only | QEMU `virt` serial console, last so `/dev/console` and systemd status go to it |

Entries `SP11 debug`, `+ DRM trace` (`drm.debug=0x1ff`), `nomodeset`, `stop in initramfs` (`rd.break=pre-mount`) have a `devicetree` line; `VM test (no devicetree)` has none and is never the default. No `quiet`, `rhgb` or `splash` appears in any non-comment line; `image-build.sh` (after the ISO exists) and L0 check 2 fail the build otherwise. The installed system gets the same verbose arguments through `/etc/default/grub` (`GRUB_CMDLINE_LINUX`), L0 check 9.

### Log collector

`image/overlay/usr/libexec/sp11-log-collector` and `sp11-log-collector.service` (`WantedBy=multi-user.target`, no ordering on GDM). It writes `<boot-id>/` (plus `SEQ`, `STATUS`, and `COMPLETE` after the first full snapshot) to the first target that works: partition labelled `SP11LOGS` (cap 256 MiB), else the embedded EFI partition of the boot disk (FAT label `ANACONDA`, `/EFI/sp11-logs/`, every file gzipped, cap 6 MiB and never below 512 KiB free), else only `/run/sp11-logs`. Snapshots at start, +20 s, +60 s, +120 s, then every 300 s; SIGTERM at shutdown writes a last one. Old boots are deleted oldest-first by `SEQ` (the clock may be wrong), then optional files of the current boot, to honour the cap. It only reads the system. Contents: everything in `agents/workers/image.md` task 3, plus the requests: display-lcd (`/sys/class/drm`, `/sys/kernel/debug/dri/*` including `eDP-1`, DPCD `0x000-0x0ff` and `0x700-0x7ff` through `/dev/drm_dp_aux*` by read-only `dd`, EDID hex, `backlight`), dsp-subsystems (`remoteproc` attributes, `power_supply`), gpu (`dri/*/gpu`, `devfreq`), soc-boot (`/proc/cpuinfo`, `cpufreq`, `cpuidle`, `clk_summary`, `regulator_summary`, debugfs `pinctrl`), display-lcd gate for the backlight patch (`pinctrl-pins.txt`: `pins`, `pinmux-pins`, `pinconf-pins` of every pin controller, so the spmi-gpio of PMK8550 and PMC8380_3 are covered; `spmi-gpio-dmesg.txt`: `dmesg | grep -i 'subtype|func3|spmi-gpio'`; DPCD of every `/dev/drm_dp_aux*` in `drm-dpcd.txt`, read errors are written into the file; debugfs is mounted when missing, a failure is logged and not fatal), plus `devicetree.dts` (`dtc -I fs`), `devices_deferred`, `gpio`, `pm_genpd_summary`, `lspci -vv`, `lsusb -t`, firmware-load failures, `btf.txt`, `gdm-status.txt`, `units-failed.txt`, `vulkaninfo`. A component worker can add its own capture as `/etc/sp11-log-collector.d/<name>.sh` (sourced, output goes to `extra-<name>.txt`); that is the way to extend it without a new ISO format. Settings: `/etc/sp11-log-collector.conf`.

Tested (2026-10-24): snapshot, publish, `SEQ` and cap logic on a plain directory (`image/tools/collector_selftest.sh`, passes); one snapshot on the WSL2 host (all files written, 40 s). **Not tested:** mounting `SP11LOGS` and the embedded ESP (the WSL2 build kernel has no vfat); that path is first exercised by L1.

### L1 details

`scripts/image-test-qemu.sh`: `qemu-system-aarch64 -machine virt,gic-version=3 -accel tcg,thread=multi -cpu neoverse-n1 -smp 8 -m 4096`, edk2 `QEMU_EFI-silent-pflash.raw` with a copy of `vars-template-pflash.raw`, the ISO as a read-only raw USB disk (`usb-storage`, boot index 1), a 128 MiB FAT disk labelled `SP11LOGS` as a second USB disk, `virtio-gpu-pci`, `virtio-net-pci`, serial on a pty driven by `image/tools/qemu_boot_test.py` (pexpect). It waits for the menu with all five entries, presses Down four times and Enter, watches for fatal messages (panic, emergency mode, dracut shell), polls the logs disk with mtools every 120 s, then powers the VM off through the QEMU monitor (`system_powerdown`, then `quit`) and reads the logs back. Timeouts: 150 min total, 25 min without serial output.

CPU model `neoverse-n1` (Inference): of QEMU's TCG models (`qemu-system-aarch64 -cpu help`: a64fx, cortex-a35/a53/a55/a57/a72/a76/a78ae/a710, neoverse-n1/n2/v1, max), it is a 64-bit Armv8.2-A core with LSE atomics, dot product, fp16 and crypto and no SVE. The project has no CPU feature data of the X1P64100 in `sources/` (Hypothesis: Oryon cores, Armv8.x, no SVE); `-cpu max` would add features this SoC may not have and slow TCG down. `--cpu` overrides it.

### What was run on 2026-10-24 and what was not

| Item | Result | Grade |
|:--|:--|:--|
| Container `sp11-fedora-image:44` builds | yes | Verified (docker build) |
| Lorax templates render, hybrid ISO, `mk-efiboot.sh` | toy ISO from a minimal install root: valid GPT, partition 2 EF00 identical to `efiboot.img`, El Torito UEFI entry, `checkisomd5` PASS | Verified on a **toy**, not on the M2 image |
| L0 (`image-test-static.sh`) | 43 passed, 0 failed, 8 skipped on the toy ISO (Fedora kernel 7.2.11, `x1e80100-crd.dtb`; Denali, SP11 config, SP11 module and DriverStore firmware checks skipped by design). Firmware check 6 also run against the real staged tree: positive and negative cases behave | Verified on the toy |
| L1 driver (`qemu_boot_test.py`) | passes against `fake_qemu.py`, which is not QEMU | Verified for the control flow only |
| **L1 on a real boot** | **not run**: `out/.kernel-build.lock` was held, so no QEMU was started | not run |
| **Livemedia-creator build of the M2 ISO** | **not run**: no kernel RPMs in `out/rpms/` yet and the lock was held | not run |
| Collector mounting `SP11LOGS` / ESP | not run (needs vfat) | not run |

### Open points

- First real `image-build.sh` run: unknown how `livemedia-creator --no-virt` behaves in the WSL2 container (`selinux`, `INSTALL_ROOT` in `%post --nochroot`, `part / --size`); fix on first failure.
- `selinux --permissive` (above).
- Kernel worker: the DTB must be installed by `kernel-core` as `/lib/modules/<kver>/dtb/qcom/x1p64100-microsoft-denali.dtb` (Fedora `kernel.spec` layout), and the RPM names must be `kernel`, `kernel-core`, `kernel-modules`, `kernel-modules-core`, `kernel-modules-extra` (D13).
- D7: the hybrid ISO is kept (recommendation accepted); a raw development disk image is not produced.
- Pinning "the compose": Fedora 44 has no compose ID for a GA release plus updates; the build record stores the repository metadata revisions (`fedora`, `updates`), the container image ID, the full NEVRA list and the lorax/anaconda/grub2/shim versions.

## M2 ISO (2026-10-24)

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-m2-20261024T190049Z.iso` (record `.json`, checksum `.iso.sha256`) |
| Size | 2,531,727,360 bytes (2.36 GiB) |
| SHA-256 | `9dea93bead1123a863c8b942969bf8ec398bba8c3715ff51c03ec98fc86828b4` |
| Build time | 1011 s of `livemedia-creator` (about 17 min), 1961 packages |
| Kernel | `kernel-core-7.3.0-65.sp11.fc44.aarch64`, vanilla 7.3, BTF on |
| Live layout | `LiveOS/squashfs.img` holds the root tree directly (no inner `rootfs.img`); dracut `dmsquash-live` accepts it and the L1 boot confirms |
| L0 | 76 passed, 0 failed (`out/iso/<name>.l0.txt`) |
| L1 | FAIL on one criterion, caused by TCG; everything else passes (below) |

Fixes needed to get here, each one a real defect found by running it:

1. `livemedia-creator` needs `--nomacboot` on aarch64 (no `hfsplus-tools`).
2. `rootpw --lock --iscrypted locked` fails: shadow-utils 4.19 `chpasswd -e` rejects the placeholder hash ("invalid password hash"). Now `rootpw --lock`.
3. `%post` `systemctl disable network` fails under `set -e`: Fedora 44 has no `network.service`. Now `|| true`.
4. L0: the live root is a plain squashfs, not `rootfs.img`; the script mounts the squashfs. Check 6.3 normalises `/lib` to `/usr/lib` (b43-openfwwf). Check 7.2 scans only files no RPM owns (the `file` magic database mentions `DriverStore`).
5. L1 container lacked `qemu-device-display-virtio-gpu-pci` and `qemu-device-usb-host` (QEMU: "'virtio-gpu-pci' is not a valid device model name"); added to the Containerfile.
6. L1 matcher flagged `dracut-emergency` because the `debug` argument makes systemd list `dracut-emergency.service` at every boot; it now matches the start of the emergency shell only.

### L1 result

QEMU TCG, `neoverse-n1`, 8 threads, 4 GiB, entry `VM test (no devicetree)`. Passes: GRUB menu shows all 5 entries; entry selected; the kernel command line has `debug` and no `quiet`/`rhgb`; the collector wrote a complete `<boot-id>/` (COMPLETE marker) to `SP11LOGS`; `btf.txt` says `btf: present`; GDM started (after 1336 s of test time). Fails: "no failed unit outside the allow-list": `firewalld`, `gssproxy`, `tuned`, `udisks2`.

Evidence that TCG is the cause (journal of `<boot-id>` on `SP11LOGS`): each of the four has `start operation timed out. Terminating.` followed by `result=failed`, for example `udisks2.service: start operation timed out` at 441 s and `firewalld.service` at 524 s after kernel start. `polkit`, `accounts-daemon` and `chronyd` hit the same timeout at 414-650 s. The units' own error output shows no crash. This is consistent with the 90 s default start timeout against an emulated CPU, but not proven: a run with a longer `DefaultTimeoutStartSec` would prove it, not done here. L2 (Hyper-V, native speed) is the real test of these four.

SELinux (D15): the collector now writes `selinux-avc.txt` (`ausearch -m AVC,USER_AVC -ts boot`, journal grep when audit is absent). In this boot, permissive: one AVC, `systemd-resolved` `write` on `io.systemd.Machine` (`systemd_machined_var_run_t`).

## kiwi layer (decision D16)

The ISO is built with `kiwi-ng` from Fedora's own description, and every difference from it is ours, marked and listed here. `scripts/image-build.sh` builds with kiwi by default; `--builder lmc` is the livemedia-creator path of M2 (D11), kept until the kiwi ISO passes L0 and L1.

### Source of the description and how Fedora builds it

| Item | Value | Source |
|:--|:--|:--|
| Description | `https://pagure.io/fedora-kiwi-descriptions.git`, branch `f44`, commit `dfc49a5a10f69941179fdadd96aa6a5984f7c677` ("Container-Toolbox: mesa-va-drivers doesn't exist any more") | pinned in `image/kiwi/DESCRIPTION_COMMIT`; it was still the head of `f44` on 2026-10-24 and again at build time (the build script prints pin and head and builds the pin either way) |
| Kiwi file and profile | `Fedora.kiwi`, profile `Workstation-Live`, image type `iso` | `VARIANTS.md` of the description ("Workstation Edition, `iso`, `Workstation-Live`"); `tmt/plans/desktop/workstation/build-live.fmf` |
| Fedora release engineering | pungi `kiwibuild` section, `'^Workstation$'` variant: `'kiwi_profile': 'Workstation-Live'`, `'arches': ['aarch64', 'ppc64le', 'x86_64']`, `'failable': ['aarch64', 'ppc64le']`; `kiwibuild_description_scm = 'git+https://pagure.io/fedora-kiwi-descriptions.git?#HEAD'`, `kiwibuild_description_path = 'Fedora.kiwi'`; ISO `volid=Fedora-WS-Live-<ver>`, `application_id=Fedora-Workstation-Live-<ver>` | `pungi-fedora`, `fedora.conf` at commit `51d60b56b496f06950423138f2eb07829709a9a2` (branch `main`: pungi-fedora has no `f44` branch yet; its kiwi config names `f44-kiwi` as target) |
| Kiwi version | `kiwi-cli 11.1.1-2.fc44` (Fedora package, D12), package manager `dnf5 5.4.6` | the container |
| Command | `kiwi-ng --type=iso --profile=Workstation-Live --kiwi-file=Fedora.kiwi --color-output system build --description DIR --target-dir DIR-build --set-type-attr=application_id=Fedora-WS... --set-type-attr=volid=Fedora-WS-Live-44` | the description's own wrapper `kiwi-build`, called as in `tmt/tests/build-image.fmf`; `scripts/image-build-kiwi.sh` calls that wrapper, so the arguments and the ISO label come from Fedora's `scripts/fedora-live-iso-label-generator` |

Fedora's profile on aarch64 is: erofs live root (`erofscompression="lzma,level=6"`), `flags="dmsquash"` (dracut `dmsquash-live`), `firmware="uefi"`, `efiparttable="gpt"`, 30 MiB embedded ESP, `mediacheck`, GRUB 2 with `grub2-efi-aa64-cdboot` and `shim-aa64`. The repositories are Fedora `fedora` and `updates-released` through metalink at build time: there is no compose to pin, so the build record stores the repository revisions, the full NEVRA list and the description commit.

### What the layer changes

| # | Change | Where | Why |
|:--|:--|:--|:--|
| 1 | Our kernel RPMs, Fedora's kernel out. `kernel`, `kernel-core`, `kernel-modules`, `kernel-modules-core`, `kernel-modules-extra` of `out/rpms` go into `out/repo` (`createrepo_c`); the repository is `sp11-local` with `priority="10"` (Fedora's default is 99). dnf5 then takes the local package for every name it provides, even when Fedora's is newer (Fedora's updates carry `kernel-7.2.11-200.fc44`, ours is `7.3.0-65.sp11.fc44`). | `image/kiwi/overlay/sp11.xml`, `scripts/image-build-kiwi.sh` | Task 1 of D16 |
| 1b | `kernel-uki-dtbloader` is no longer requested for aarch64. Fedora's `components/boot.xml` installs it for the aarch64 live ISO; we boot a plain kernel with the GRUB 2 `devicetree` command (D9). Patch 0003. | `image/kiwi/patches/0003-no-uki-dtbloader.patch` | D9 |
| 2 | Firmware: `out/firmware-root/lib/firmware` is copied into the description's `root/usr/lib/firmware` (kiwi's root overlay, applied after the packages); `qcom-firmware` and `linux-firmware` are requested. | `scripts/image-build-kiwi.sh`, `sp11.xml` | D16, firmware worker request 1-2 |
| 3 | GRUB 2: `grub-arm.cfg.iso-template` of the description is replaced by ours. Five entries: `SP11 debug` (default), `SP11 debug + DRM trace`, `SP11 debug nomodeset`, `SP11 debug, stop in initramfs` (all four with `devicetree`), `VM test (no devicetree)` (no `devicetree`, never default, the only one with `console=ttyAMA0,115200`). Every entry has `--id sp11-<id>` and `sp11.entry=<id>` on its `linux` line. Menu always shown (`timeout_style=menu`, `timeout=10`). Removed from Fedora's template: `Test this media` and the `Troubleshooting` submenu. | `image/kiwi/overlay/grub-arm.cfg.iso-template` | D9, D10, D15 |
| 3b | Verbose command line: patch 0002 changes `kernelcmdline="quiet rhgb"` of the aarch64 live type to `debug loglevel=8 ignore_loglevel printk.devkmsg=on log_buf_len=16M rd.plymouth=0 plymouth.enable=0 systemd.show_status=1 rd.udev.log_level=info console=tty0` (reasons per argument: "GRUB 2 and the kernel command line" above). kiwi appends `root=live:CDLABEL=Fedora-WS-Live-44 rd.live.image` itself. The same string is also kiwi's `GRUB_CMDLINE_LINUX_DEFAULT` in the installed system's `/etc/default/grub`. | `image/kiwi/patches/0002-verbose-kernel-cmdline.patch` | D9 |
| 3c | No Plymouth: not removed, switched off. Excluding the package makes dnf5 fail ("Argument 'plymouth' matches only excluded packages", Fedora's package groups request it). It is omitted from the initramfs (`omit_dracutmodules+=" plymouth "`), `rd.plymouth=0 plymouth.enable=0` is on every entry, and its nine units are masked in `/etc/systemd/system`. L0 check 9.2 therefore checks the masks in a kiwi image and the package absence in an lmc image; check 5.4 (no Plymouth in the initramfs) is the same for both. | `sp11.xml` (comment), `image/overlay/etc/dracut.conf.d/90-sp11.conf`, `scripts/image-build-kiwi.sh` | D9 |
| 4 | Log collector, its unit and `/usr/lib/systemd/system-preset/80-sp11.preset`. The preset is needed with kiwi: the image ships `/etc/machine-id` as `uninitialized`, systemd then runs `preset-all` at first boot, and Fedora's `90-default.preset` (`disable *`) removed the unit's `multi-user.target.wants` symlink (first L1 run: `Removed '/etc/systemd/system/multi-user.target.wants/sp11-log-collector.service'` at 379 s; the collector never ran). Collector setting `ESP_LABEL=BOOT` (kiwi names the embedded ESP `BOOT`). | `image/overlay/` (shared with lmc), `image/kiwi/overlay/root/etc/sp11-log-collector.conf` | D7, D15 |
| 5 | SELinux permissive (`/etc/selinux/config`), AVC capture in the collector, `audit` package; extra test packages of the M2 kickstart (`mesa-dri-drivers`, `mesa-vulkan-drivers`, `vulkan-tools`, `glx-utils`, `glmark2`, `drm-utils`, `v4l-utils`, `qrtr`, `dtc`, `pciutils`, `usbutils`, `bpftool`, `mtools`, `dosfstools`). Early display drivers for the initramfs: `image/kiwi/overlay/root/etc/dracut.conf.d/91-sp11-drivers.conf` (static list, dracut fails when a name does not exist). | `sp11.xml`, overlay | D15 |
| 6 | GRUB template drops `efi_uga`, `video_bochs`, `video_cirrus` from `load_video` (not arm64-efi modules; QEMU printed "file not found" for each); `efi_gop` and `all_video` stay. | template | D17 follow-up |
| 7 | DTB: `config-cdroot.tar` (kiwi's hook for extra ISO files) puts `boot/dtb/qcom/x1p64100-microsoft-denali.dtb`, taken from the `kernel-core` RPM, on the ISO file system. The `devicetree` lines read `($root)/boot/dtb/qcom/...` (the M2 path was `/boot/dtb-<kver>/qcom/`). | `scripts/image-build-kiwi.sh` | D9 |

Fedora files changed: three patches (`Fedora.kiwi` gets one `<include>`, `components/liveinstall.xml` one attribute, `components/boot.xml` one package line) and one replaced file (the GRUB template). `patch` fails the build when the pinned description drifts.

### Media layout and `SP11LOGS` (D7)

- Hybrid, verified with `sgdisk -p` and `xorriso -report_el_torito`: GPT with partition 1 `ISO9660` (0700) and partition 2 `Appended2` (EF00, 64 MiB FAT32, the embedded ESP, FAT label `BOOT`); El Torito UEFI image identical to partition 2 (L0 1.1-1.3). DD mode is therefore the same as for the M2 ISO.
- Differences from the lorax ISO that the operator procedure and the collector must know:
  1. The GRUB menu lives in `/boot/grub2/grub.cfg` on the ISO 9660 file system. The ESP and `/EFI/BOOT/grub.cfg`, `/EFI/fedora/grub.cfg` only `search --file --set=root /boot/<mbrid>` and `configfile` to it. L0 checks all of them for forbidden words and checks the stubs are only chains.
  2. The ESP is `BOOT`, **FAT32, 64 MiB, 129022 clusters, about 55 MiB free** (decision D17; kiwi's own 30 MiB FAT16 ESP had 15321 clusters, M2's `ANACONDA` one 14011). The fallback `/EFI/sp11-logs/` has far more room than before (collector cap `CAP_ESP_KIB` is still 6144 KiB, raise it in `/etc/sp11-log-collector.conf` if wanted); `SP11LOGS` (FAT partition created by the operator after the ISO) is unchanged and preferred.
  3. Live root: `LiveOS/squashfs.img` is an erofs image (lzma), not squashfs. The WSL2 kernel (6.6) cannot mount lzma erofs ("Failed to mount erofs: Operation not supported"), so L0 unpacks it with `fsck.erofs --extract`.
  4. `/boot` of the image holds a 250 MB rescue initramfs and BLS entries (`dracut-config-rescue`; Fedora's description does not remove them, and I did not check the official ISO). Their paths point into the build directory `/var/tmp/sp11-kiwi/...`.

### FAT32 ESP (decision D17)

The Surface UEFI boots only from a FAT32 USB ESP. kiwi 11.1.1 has no setting for it: the embedded ESP is made by `mkdosfs -n BOOT FILE` (`bootloader/config/grub2.py`, `_create_embedded_fat_efi_image`, no `-F`), so mkfs.fat picks FAT16 for 30 MiB; `efifatimagesize` only sets the size. `scripts/image-build-kiwi.sh` therefore replays the finished ISO: the `EFI/` tree of the kiwi ESP goes into `mkfs.fat -C -F 32 -s 1 -S 512 -n BOOT esp32.img 65536`, then `xorriso -indev ISO -outdev ISO.new -boot_image any replay -append_partition 2 0xef esp32.img -commit` (the El Torito UEFI entry follows partition 2), then `implantisomd5` again (the replay changes the bytes kiwi's media tag covers; without it `checkisomd5` fails). L0 1.5-1.7 fail the build when the ESP is not FAT32 by BPB cluster count (>= 65525) or smaller than 64 MiB, or when the El Torito image and GPT partition 2 differ. The lorax path is not changed and its ISO is FAT16.

### Direct GRUB boot (decision D18, risk R9)

The Surface returned to its boot menu before GRUB with shim 16.1-7 as `BOOTAA64.EFI`, also with a FAT32 ESP and Secure Boot off (why: unknown, Hypothesis). The previous project reached the Linux console only with GRUB as `BOOTAA64.EFI`. The ESP step of `scripts/image-build-kiwi.sh` (the same one as for D17) therefore leaves `EFI/BOOT/` as:

| File | Content |
|:--|:--|
| `BOOTAA64.EFI` | Fedora's `grubaa64.efi` (`grub2-efi-aa64`), byte-identical |
| `grubaa64.efi` | the same file, the name shim and the stub expect |
| `shimaa64.efi` | kiwi's shim 16.1-7, kept, unused (it was `bootaa64.efi`) |
| `mmaa64.efi` | shim's MokManager, kept, unused |
| `grub.cfg` | stub; first line `echo "SP11: GRUB started (direct EFI boot, no shim)"`, then `search` and `configfile` to `/boot/grub2/grub.cfg` |

`bootx64.efi` is removed. kiwi writes the aa64 shim under that x86 name too; no arm64 firmware looks for it, and it would be a shim at a fallback path. The ISO 9660 tree (partition 1, not read by the firmware when booting the DD-written stick) is unchanged and still has kiwi's `/EFI/BOOT` files. L0 2.13-2.16 check: `BOOTAA64.EFI` equals `grubaa64.efi`, shim is kept and is not the fallback loader, the marker is the first line, no `bootx64.efi`. The marker tells the operator on the panel whether GRUB ran.

Build status of the ISO `sp11-fedora44-aarch64-kiwi-20261025T115940Z-d18.iso`: made by the ESP step on the finished kiwi output of build `20261025T115940Z` (`image-build-kiwi.sh --post-only`), not by a second kiwi run; the kiwi stage is the same bytes as the D17 ISO, only the ESP step differs.

### L0 on the kiwi layout

`scripts/image-test-static.sh` reads `"builder"` from the build record; kiwi differs from lmc only where the layout does. Each adaptation:

| Check | Adaptation | Reason |
|:--|:--|:--|
| extraction | kernel, initrd, DTB and menu from `/boot/aarch64/loader/{linux,initrd}`, `/boot/dtb/...`, `/boot/grub2/grub.cfg`; the ESP image from `xorriso -extract_boot_images` | no `/images/pxeboot`, no `/images/efiboot.img` |
| 0.2 | erofs unpacked with `fsck.erofs`, not mounted | WSL2 kernel, above |
| 2.1-2.4 | forbidden-word check on all four `grub.cfg` (ISO main, ISO `EFI/BOOT`, ISO `EFI/fedora`, ESP); the three EFI ones must be chain stubs; `loopback.cfg` must only `source` the main one | kiwi's stub layout |
| 2.5-2.9 | read from the main `grub.cfg`; `devicetree ($root)/boot/dtb/...` accepted | template |
| 2.12 (new) | every entry has `sp11.entry=<id>`, is verbose (`debug loglevel=8 ignore_loglevel`), and only the VM entry has `console=ttyAMA0` | D15 |
| 9.2 | Plymouth units masked instead of package absent | change 3c |
| 4.8 | `grep -c`, not `grep -q`, under `pipefail` | defect of my own check: `grep -q` closes the pipe, `xz` gets SIGPIPE, the check failed at random (it had passed by luck on the M2 ISO) |
| 7.2 | scans only files no RPM owns | unchanged from the M2 fix |
| 7.4 (new) | `rpm -Va` on the image; every RPM-owned file whose content changed gets the MAC and private-string scan | orchestrator's follow-up of the M2 report (RPM-owned files modified in `%post` or by the overlay) |

### kiwi ISO (2026-10-25)

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261025T001028Z.iso` (record `.json`, checksum `.iso.sha256`) |
| Size | 2,748,110,848 bytes (2.56 GiB) |
| SHA-256 | `e675159a4c7a7da2e07c06e575e26d7a3671edd3dd968594bbeb72ebae1055a3` |
| Build time | 1384 s for the whole `kiwi-ng` run (about 23 min: bootstrap, package install, initrd, erofs, ISO), 1969 packages, kiwi `11.1.1-2.fc44`, container memory 9 GiB (6 GiB: `mkfs.erofs` was OOM-killed at 3 GB resident) |
| Kernel | `kernel-core-7.3.0-65.sp11.fc44.aarch64`, the only kernel (L0 0.3). `kernel-tools` and `kernel-tools-libs` are Fedora's `7.2.11-200.fc44` (user space, not a kernel) |
| Description | `fedora-kiwi-descriptions` `f44` at `dfc49a5a10f69941179fdadd96aa6a5984f7c677`, profile `Workstation-Live`, three patches and the layer above |
| L0 | 80 passed, 0 failed (`out/iso/<name>.l0.txt`) |
| L1 | FAIL on one criterion, as for M2; all others pass (below) |

Defects found by running the kiwi build and tests, each fixed:

1. `<ignore>` of a package that Fedora's description also requests makes dnf5 fail (`kernel-uki-dtbloader`, `plymouth`): patch 0003 and "Plymouth switched off" (change 3c) instead.
2. `mkfs.erofs` OOM-killed at a 6 GiB container cap: 9 GiB for kiwi.
3. The first kiwi ISO carried the host path (with the user name) in `/boot/loader/entries/*.conf`: `/out` is a bind mount and kernel-install derives the path from the mount source. L0 7.2 caught it. kiwi now builds in the container's own file system (`/var/tmp/sp11-kiwi`) and the ISO is copied out.
4. First L1 run: the collector never ran. First boot `preset-all` removed its symlink (change 4); fixed with `80-sp11.preset`, L0 8.7 added. The run was stopped after GDM had started (739 s of guest time): `out/image-work/l1-kiwi-run1-serial.log`.
5. L0 4.8 failed at random because of `pipefail` (above).

### L1 result of the kiwi ISO

QEMU TCG, `neoverse-n1`, 8 threads, 4 GiB, entry `VM test (no devicetree)`; 1579 s from start to the collector report. Passes: GRUB menu with all 5 entries; entry booted (`sp11.entry=vmtest`); command line `BOOT_IMAGE=(hd0)/boot/aarch64/loader/linux debug loglevel=8 ignore_loglevel ... root=live:CDLABEL=Fedora-WS-Live-44 rd.live.image sp11.entry=vmtest console=ttyAMA0,115200`, no `quiet`/`rhgb`; the collector wrote a complete `<boot-id>/` with 58 files to `SP11LOGS` (`STATUS`: `target: logs`, 2 cycles, uptime 976 s; the `dmsquash-live` initramfs started and mounted the erofs root); `btf: present`; GDM started; SELinux permissive, `selinux-avc.txt` has `<no matches>` (0 AVC; the lorax ISO had 1).

Fails (same criterion as M2, different units): **abrtd, avahi-daemon, NetworkManager-wait-online, switcheroo-control, tuned, udisks2**.

| Unit | Journal evidence (guest seconds) | Same as M2? |
|:--|:--|:--|
| `switcheroo-control` | `start operation timed out. Terminating.` 601.8, `result=failed` 602.9 | new |
| `abrtd` | `start-pre operation timed out. Terminating.` 603.6, `result=failed` 603.8 | new |
| `avahi-daemon` | `start operation timed out. Terminating.` 606.1 | new |
| `udisks2` | `start operation timed out. Terminating.` 607.0 | yes (M2: 441 s) |
| `tuned` | `start operation timed out. Terminating.` 748.5, `Failed with result 'timeout'` | yes (M2: 599 s) |
| `NetworkManager-wait-online` | `Failed with result 'exit-code'` 699.7, not a start timeout | new |

So two of the four M2 units (`tuned`, `udisks2`) time out again under TCG; `firewalld` and `gssproxy` did not fail this time, and four other units did. Five of the six are the 90 s start timeout, as in M2 (consistent with TCG, not proven: no run with a longer timeout). `NetworkManager-wait-online` is different: its exit code is a failure, not a timeout. I did not find why (QEMU user-mode network under TCG is the obvious suspect, unproven). L2 on Hyper-V is the real test for all six.

Because L1 failed on this criterion, the livemedia-creator path (`--builder lmc`, `image/sp11-live.ks`, `image/lorax-templates/`) is **not** removed yet; that is the orchestrator's decision.

## Requests

- installer path (R9, future): the installed system must boot `grubaa64.efi` directly. Anaconda installs shim and points the UEFI boot entry at it, and this firmware does not run shim. The installer step (kickstart `%post` of the installed system, or an Anaconda addon / `efibootmgr` call after install) must (a) create the boot entry for `\\EFI\\fedora\\grubaa64.efi` with `efibootmgr -c -d <disk> -p <esp partition> -L Fedora -l '\\EFI\\fedora\\grubaa64.efi'`, and (b) copy `grubaa64.efi` to `EFI/BOOT/BOOTAA64.EFI` on the installed ESP, for firmware that only reads the fallback path. Both must leave `EFI/fedora/shimaa64.efi` in place. Not implemented: this image has no installer step yet; verify on the device (R9).
- kernel: install `x1p64100-microsoft-denali.dtb` under `/lib/modules/<kver>/dtb/qcom/` in `kernel-core`; build `kernel-modules-core`/`kernel-modules` with `CONFIG_SQUASHFS_ZSTD=y`, `CONFIG_VFAT_FS=m` (or `y`; the collector mounts the FAT log partition), `CONFIG_USB_STORAGE`, `CONFIG_VIRTIO_GPU`, xHCI and virtio drivers for the L1 `VM test` entry (the Fedora config has them; keep them).
- firmware: none open; request 1-4 are done (see "Kickstart origin" and "Initramfs and firmware").
- orchestrator: dossiers of `dsp-subsystems` (pd-mapper, qrtr) and `gpu` can cite this file for the answers above.

## Log

- 2026-10-24: container, kickstart, lorax templates, collector, `image-build.sh`, L0 and L1 scripts written. L0 passes on a toy ISO; L1 driver verified against a fake QEMU; no ISO build and no QEMU run because the kernel build held `out/.kernel-build.lock`.
- 2026-10-24 (later): M2 ISO built (SHA-256 above), L0 76/76, L1 reaches GDM with the collector complete, fails only on four TCG start timeouts. Six defects fixed (list in "M2 ISO").
- 2026-10-25: D16. kiwi builds the ISO from Fedora's `f44` Workstation-Live description (pin `dfc49a5`) plus the SP11 layer; L0 80/80; L1 reaches GDM and a complete collector log, fails on six unit start failures (five TCG timeouts, one `NetworkManager-wait-online` exit code). `image-build.sh` uses kiwi by default; lmc kept. Privacy scan 7.4 (`rpm -Va`) added.
- 2026-10-25: D17. kiwi ISO rebuilt with a 64 MiB FAT32 ESP (xorriso replay, 129022 clusters), L0 83/83 (new checks 1.5-1.7), GRUB menu and kernel start seen in QEMU (5 min, no `file not found`); full L1 not rerun.
- 2026-10-25: D18. ESP step makes `BOOTAA64.EFI` Fedora's GRUB, shim kept as `shimaa64.efi`, `bootx64.efi` removed, marker line first; L0 87/87 (new checks 2.13-2.16); QEMU shows the marker, the menu and the kernel start (4 min run, no full L1).
