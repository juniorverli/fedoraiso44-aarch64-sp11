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
| `SP11 debug` (default) | `clk_ignore_unused pd_ignore_unused rootdelay=10`, DTB `…-denali-parity.dtb` | M4 (D20): every difference the comparison with the previous project's GNOME boot found. Supersedes the D19 gate for the default only |
| `SP11 debug, M3 command line` | none, packaged DTB | M4: the M3 boot, for comparison |
| `SP11 debug, no early DSP` | as the default, plus `rd.driver.blacklist=qcom_q6v5_pas` | M4: the DSP remoteproc driver stays out of the initramfs (loads in the real root, as in M3) |
| `SP11 debug + DRM trace` | as the default, plus `drm.debug=0x1ff` | Display problems (very verbose) |
| `SP11 debug nomodeset` | as the default, plus `nomodeset` | Fallback when the panel goes dark; keeps the firmware framebuffer |
| `SP11 debug, stop in initramfs` | as the default, plus `rd.break=pre-mount` | Rescue shell before the root is mounted |
| `VM test (no devicetree)` | `console=ttyAMA0,115200`, no `devicetree` | L1 only, never default |

The `parity` DTB is the M3 DT with the 10-CPU topology (the two fused-off cores, MPIDR `0x10300` and `0x20300`, removed; the kernel worker checked the MADT) and no system SS3 idle (CL4/CL5 kept). The M3 DTBs `…-edponly.dtb` and `…-nobl.dtb` stay on the ISO unreferenced, for manual use at the GRUB prompt (`devicetree`). The D19 entries `keep firmware clocks`, `eDP only` and `DTB without PWM backlight` are not in the M4 menu.

Every entry also has `sp11.entry=<id>` (`debug`, `m3cmdline`, `nodsp`, `drm-trace`, `nomodeset`, `initramfs`, `vmtest`); the collector writes it to `entry.txt`, so a log says which entry booted. Any further argument needs a request from a component worker with a log that justifies it, and is listed with its reason in the build record. `clk_ignore_unused` never becomes a default without a log that shows H1 (D19).

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

### M3: display evidence and early collection (decision D19)

The first device boot with the kiwi `-d18` ISO printed the console on the firmware framebuffer and then the LCD went black. The M3 image is built to tell the hypotheses H1 (display clocks gated), H2 (eDP or panel fails after `msm` binds), H3 (backlight described wrong) and H5 (USB-C DP bridge chain never probes) apart on one stick. The build needs the M3 kernel RPMs (`7.3.0-65.sp11.3.fc44`) and refuses anything not newer than `7.3.0-65.sp11.fc44` (`image/kiwi/MIN_KERNEL_EXCLUSIVE`).

- **Kernel RPM selection** (`scripts/image-build-kiwi.sh`, step 0): only the top level of `out/rpms/` counts (`out/rpms/archive/` holds the M1 build); the build fails when more than one kernel NEVRA sits there; the five image RPMs all come from that one NEVRA.
- **Three DTBs on the ISO**, all in `/boot/dtb/qcom/`: the packaged `x1p64100-microsoft-denali.dtb` (from `kernel-core`), and `…-denali-edponly.dtb` and `…-denali-nobl.dtb` (from `out/dtb-variants/<kver>/qcom/`, written by the kernel worker). The build fails when a variant is missing; `--smoke` replaces it with a copy of the packaged DTB, names the ISO `…-kiwi-smoke-…` and sets `dtb_variants_smoke_copy` in the record (pipeline test only, never for the device). The record has `dtb_files` (SHA-256 of all three) and, when the kernel worker's JSON records exist, `dtb_variant_records`.
- **Early snapshot.** `sp11-log-collector run` first writes a small display snapshot and publishes it (retrying up to 30 s while the target is not mounted yet), then the first full snapshot, then at 20, 60, 120, 300 s and every 300 s. The unit has `DefaultDependencies=no` (after `local-fs.target`, journald, udev only) so it starts before `basic.target`. The early snapshot has no `COMPLETE` marker; `STATUS` says `cycle: 0 (early display snapshot)`.
- **Display files** (early and every full snapshot; `display_set` in the collector): `cmdline.txt`, `entry.txt` (the `sp11.entry`, clock and `nomodeset` arguments, DTB model and compatible), `devices_deferred.txt` (key for H5), `device_component.txt` (`/sys/kernel/debug/device_component/*`), `drm-class-ls.txt`, `lsmod.txt`, `fb-state.txt` (`/dev/fb*`, `/proc/fb`, simpledrm and simple-framebuffer drivers and modules, framebuffer dmesg lines), `clk-display.txt` (`clk_summary` filtered for disp, mdss, edp, dp), `clk_summary.txt`, `genpd_summary.txt`, `regulator_summary.txt`, `display-dmesg.txt` (msm, dpu, mdss, drm, dp, panel, edp, backlight, pwm, lpg, simpledrm, efifb, dispcc, pmic and clock/genpd lines), `drm-state.txt` (`dri/*/state`), `dp-link.txt` (`dp_debug`), `drm-connectors.txt` (status, enabled, dpms, modes, the `eDP-1` debugfs directory), `backlight.txt` (brightness, max_brightness, actual_brightness, bl_power), `pwm.txt`, `leds.txt`, `pinctrl-pmic.txt` (`/sys/kernel/debug/pinctrl/*pmic*`), `spmi-gpio-dmesg.txt`, `dpcd-tool.txt` and `dpcd-drm_dp_aux*-000.bin/-700.bin/.txt` (the display-lcd `collect-dpcd.py`, unchanged, run as root against every `/dev/drm_dp_aux*`: DPCD 0x000-0x0ff and 0x700-0x7ff, read only), and the shell reader `drm-dpcd.txt` as a second opinion. The publish step copies files, not directories, so the tool's output is flattened into `dpcd-*`.
- **ESP fallback** (`/EFI/sp11-logs` on the partition labelled `BOOT`): the ESP is 64 MiB FAT32 (D17) with the D18 layout; the kiwi collector config raises the cap to 32 MiB (`CAP_ESP_KIB=32768`), files on the ESP are gzip-compressed, the oldest boot is removed first. `scripts/image-test-qemu.sh --esp-fallback` tests it: no `SP11LOGS` disk, the ISO is attached as a writable copy, and the test reads `/EFI/sp11-logs/<boot-id>/` out of GPT partition 2 afterwards.

### M4: initramfs, parity and failure capture (decision D20), and the boot medium (risk S4)

- **Initramfs of the kiwi image** (`image/kiwi/overlay/root/etc/dracut.conf.d/`): `leds-qcom-lpg` is added (the M3 initramfs lacked the PMK8550 PWM provider; with display-lcd 0003 the panel references the backlight, and `panel_edp_probe()` returns the `drm_panel_of_backlight()` error before panel detection, so the panel could not probe there; Verified by CPIO inspection in `out/agents/surface-compare/report.md` 2d). `qcom_q6v5_pas` (F1 is superseded for the kiwi image) with `qcom_pd_mapper`, `pdr_interface`, `qrtr`, `qrtr-smd`; its other dependencies (GLINK, SMEM, sysmon, mdt_loader) come through `modules.dep`. The four staged DSP images (`qcadsp8380.mbn`, `adsp_dtb.mbn`, `qccdsp8380.mbn`, `cdsp_dtb.mbn` under `qcom/x1e80100/microsoft/Denali/`) are installed with dracut `install_items`. The GPU zap shader and `gen70500` stay out (`msm_open()` loads them at the first open). The kiwi overlay's `90-sp11.conf` replaces the shared one (which still carries the F1 `omit_drivers` for the lorax path).
- **L0 5.5** requires every module of the display chain (`msm panel_edp phy_qcom_edp drm_dp_aux_bus pwm_bl leds_qcom_lpg dispcc_x1e80100`) and the DSP set, and everything `modules.dep` says they need, to be in the actual initramfs CPIO (or built in); a missing one fails L0. The check was run against the M3 initramfs first and failed on exactly `leds_qcom_lpg`. **5.7** requires the four DSP images in the initramfs with the SHA-256 of `firmware/manifest.toml`; **5.8** requires the GPU zap shader and `gen70500` to be absent.
- **Failure capture in the initramfs** (dracut module `95sp11-initrd-log`, shipped by the kiwi overlay, added by `92-sp11-initrd-log.conf`): hooks `initqueue/timeout` (two thirds of `rd.retry`) and `emergency`. Each writes `/EFI/sp11-logs/initrd-<boot-id>/` on the ESP (label `BOOT`) with `journal-<reason>.txt.gz`, `dmesg-…`, `rdsosreport-…` (made with `/sbin/rdsosreport` when dracut has not yet), a state report (cmdline, `blkid`, `lsblk`, `/dev/disk/by-label`, initqueue hooks, modules, `devices_deferred`), `STATUS.<reason>`, `SEQ`, `COMPLETE`. Same cap (`CAP_ESP_KIB` from `/etc/sp11-log-collector.conf`, installed into the initramfs) and gzip rule as the collector; the oldest other boot directory goes first. The boot id is the collector's, so `initrd-<id>` and `<id>` belong together.
- **S4: write only to the boot medium.** The test device is also a Windows machine (internal NVMe with ESP, MSR, NTFS C:, WinRE). The collector and the initramfs hook find the boot medium by (1) the label of `root=live:CDLABEL=` (or `LABEL=`) on the command line, resolved with `blkid -L`, taking the parent disk from sysfs (the PKNAME); (2) the `/run/initramfs/live` mount source; (3) the label built into the ISO (`/etc/sp11-boot-medium`, `Fedora-WS-Live-44`, L0 checks it equals the ISO volume id), for the case that the command line label is the failure; the method that worked is logged and written to `boot-medium.txt`. They mount **only** a partition labelled `SP11LOGS` or `BOOT` whose parent disk is that disk. If no medium is found they write nothing outside `/run` and say so in the journal. They refuse a disk that carries an NTFS or BitLocker file system or a Microsoft reserved partition (GUID `e6d6d379-…`), found with `blkid -p`, not `lsblk`, because the udev database may not exist yet. The old rule ("any partition labelled `BOOT`" when the parent was unknown) is gone; L0 8.11-8.13 check both scripts. `image/tools/collector_selftest.sh` tests the guard and the rule with loop devices and a fake Windows disk; L1 `--decoy` attaches that disk (`image/tools/make-decoy-disk.sh`: FAT32 `BOOT` with the EFI type, FAT32 `SP11LOGS`, NTFS, MSR) and compares its md5sum before and after.
- **L1 additions:** `--decoy`; `--initrd-fail` (the VM entry is edited in GRUB with a wrong `root=live:CDLABEL=` last, `rd.retry=12 rd.shell=0`; this entry exists only in the test run, not in the ISO).

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
| 3 | GRUB 2: `grub-arm.cfg.iso-template` of the description is replaced by ours. Eight entries (D19, table in "GRUB 2 and the kernel command line"): seven device entries with `devicetree` (the packaged DTB, except `edponly` and `nobl`), and `VM test (no devicetree)` (no `devicetree`, never default, the only one with `console=ttyAMA0,115200`). Every entry has `--id sp11-<id>` and `sp11.entry=<id>` on its `linux` line. Menu always shown (`timeout_style=menu`, `timeout=10`). Removed from Fedora's template: `Test this media` and the `Troubleshooting` submenu. | `image/kiwi/overlay/grub-arm.cfg.iso-template` | D9, D10, D15 |
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
| 2.5-2.9 (D19) | the eight titles in the D19 order; entry count 8 | M3 menu |
| 2.12 (new) | every entry has `sp11.entry=<id>`, is verbose (`debug loglevel=8 ignore_loglevel`), and only the VM entry has `console=ttyAMA0` | D15 |
| 2.17 (D19) | `clk_ignore_unused pd_ignore_unused` only on `keepclk`; `edponly` and `nobl` load their own DTB, every other device entry the packaged one | M3 menu |
| 3.6-3.10 (D19) | each variant DTB is on the ISO, decompiles, has the Denali root compatible, differs from the packaged DTB, and equals both the build record hash and `out/dtb-variants/<kver>/qcom/` | M3 DTBs |
| 8.8-8.10 (D19) | `collect-dpcd.py` in the image equals `hardware/display-lcd/tools/collect-dpcd.py`; the collector unit has `DefaultDependencies=no`; `ESP_LABEL=BOOT`, `CAP_ESP_KIB=32768` | collector |
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

### M3 ISO (2026-10-25, decision D19)

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261025T160856Z.iso` (record `.json`, checksum `.iso.sha256`) |
| Size | 2,784,362,496 bytes (2.59 GiB) |
| SHA-256 | `2a7f7fc162501f8cc0d5c7b57be29c99bb6cf601d69be1a0392517112b42c195` |
| Build time | 1550 s for the kiwi run (about 26 min), 1969 packages |
| Kernel | `kernel-core-7.3.0-65.sp11.3.fc44.aarch64` (the only kernel NEVRA at the top of `out/rpms`; M1 is in `out/rpms/archive/`) |
| ESP | FAT32, label `BOOT`, 64 MiB, 129022 clusters, 52 MiB free (D17); `BOOTAA64.EFI` = `grubaa64.efi` (D18) |
| DTB, packaged | `/boot/dtb/qcom/x1p64100-microsoft-denali.dtb`, SHA-256 `582725d52d7ec5c9d71bae5f4847abada1633b9686e08d81be4e421375f2c9fd` (from `kernel-core`) |
| DTB, `edponly` | `/boot/dtb/qcom/x1p64100-microsoft-denali-edponly.dtb`, SHA-256 `eb41249b8419f4f904353e38268e0c1ee4bee321e0e4c3f0f497a2c6048a6fad` |
| DTB, `nobl` | `/boot/dtb/qcom/x1p64100-microsoft-denali-nobl.dtb`, SHA-256 `bc9463f8b72edede60fd1d349017129d2172cc3e8bcbdce29e5cd680debde896` |
| L0 | 103 passed, 0 failed, 0 skipped (`out/iso/<name>.l0.txt`) |
| L1 (`--esp-fallback`, no GDM) | PASS, see below |

GRUB entries, in menu order (every device entry: common arguments `debug loglevel=8 ignore_loglevel printk.devkmsg=on log_buf_len=16M rd.plymouth=0 plymouth.enable=0 systemd.show_status=1 rd.udev.log_level=info console=tty0 root=live:CDLABEL=Fedora-WS-Live-44 rd.live.image`, then):

| # | Title | `--id` / `sp11.entry` | DTB (`devicetree`) | Extra arguments |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | `denali.dtb` | — |
| 2 | `SP11 debug, keep firmware clocks` | `keepclk` | `denali.dtb` | `clk_ignore_unused pd_ignore_unused` |
| 3 | `SP11 debug, eDP only (USB-C DP off)` | `edponly` | `denali-edponly.dtb` | — |
| 4 | `SP11 debug, DTB without PWM backlight` | `nobl` | `denali-nobl.dtb` | — |
| 5 | `SP11 debug + DRM trace` | `drm-trace` | `denali.dtb` | `drm.debug=0x1ff` |
| 6 | `SP11 debug nomodeset` | `nomodeset` | `denali.dtb` | `nomodeset` |
| 7 | `SP11 debug, stop in initramfs` | `initramfs` | `denali.dtb` | `rd.break=pre-mount` |
| 8 | `VM test (no devicetree)` | `vmtest` | none | `console=ttyAMA0,115200` |

L1 of the M3 ISO (QEMU TCG, `neoverse-n1`, 8 threads, 4 GiB, `--esp-fallback`: no `SP11LOGS` disk, the ISO attached as a writable copy): the menu listed all 8 entries; `VM test (no devicetree)` (7 Down keys) booted the kernel with `sp11.entry=vmtest`; after 1053 s the collector had a complete `<boot-id>/` in `/EFI/sp11-logs/` on the embedded ESP (label `BOOT`, 64 MiB FAT32, D18 layout; `STATUS`: `target: esp`, `cycle: 1`), 70 files, gzip-compressed; BTF present; the 14 required D19 display files were there and `entry.txt` names `sp11.entry=vmtest`. Not run: GDM, the unit allow-list (`--early`), and the `SP11LOGS` disk path with the new collector (the earlier L1 runs covered that path with the previous collector). In QEMU `devices_deferred.txt` is empty (nothing deferred in the VM; an empty file means that), there is no `msm`, no AUX device (`dpcd-tool.txt`: "No AUX devices"), `backlight.txt` and `pinctrl-pmic.txt` are empty and `drm-state.txt` holds only a cat error: the display evidence itself can only come from the Surface.

Two defects of my test driver found by this run, fixed: with the fallback, `mdir -b` prints the whole path, so the boot directory was not recognised (the first run was stopped and judged by hand from the ESP of its disk copy, which already showed the complete directory; the run above is the clean rerun), and the "to SP11LOGS" label of the check now says "to the log target".

### M4 ISO (2026-10-25, decision D20)

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261025T183834Z.iso` (record `.json`, checksum `.iso.sha256`) |
| Size | 2,802,515,968 bytes (2.61 GiB) |
| SHA-256 | `0325c6f41b073781688b349f5ab4adfa9a880c2c18b82a504f6fee300eac4d9c` |
| Build time | 1595 s for the kiwi run, 1969 packages |
| Kernel | `kernel-core-7.3.0-65.sp11.3.fc44.aarch64` (same RPMs as M3) |
| ESP | FAT32, label `BOOT`, 64 MiB, 129022 clusters; `BOOTAA64.EFI` = `grubaa64.efi` (D17, D18) |
| DTBs on the ISO (`/boot/dtb/qcom/`) | packaged `582725d5…f9fd`; **`-parity` `1db70aa9426f37885c96acce15a3b4b626a8b26c23fc24acd9d5946046c12f71`** (used by entries 1, 3-6); `-edponly` `eb41249b…6fad` and `-nobl` `bc9463f8…e896` (unreferenced) |
| L0 | 131 passed, 0 failed, 0 skipped |
| L1 `--esp-fallback --decoy` | PASS (menu of 7, VM entry boots, collector writes `/EFI/sp11-logs` on the `BOOT` ESP, fake Windows disk unchanged) |
| L1 `--initrd-fail --decoy` | PASS (dracut failure capture, fake Windows disk unchanged) |

Menu (common arguments `debug loglevel=8 ignore_loglevel printk.devkmsg=on log_buf_len=16M rd.plymouth=0 plymouth.enable=0 systemd.show_status=1 rd.udev.log_level=info console=tty0 root=live:CDLABEL=Fedora-WS-Live-44 rd.live.image`, then):

| # | Title | `sp11.entry` | DTB | Extra arguments |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | parity | `clk_ignore_unused pd_ignore_unused rootdelay=10` |
| 2 | `SP11 debug, M3 command line` | `m3cmdline` | packaged | none |
| 3 | `SP11 debug, no early DSP` | `nodsp` | parity | as 1, plus `rd.driver.blacklist=qcom_q6v5_pas` |
| 4 | `SP11 debug + DRM trace` | `drm-trace` | parity | as 1, plus `drm.debug=0x1ff` |
| 5 | `SP11 debug nomodeset` | `nomodeset` | parity | as 1, plus `nomodeset` |
| 6 | `SP11 debug, stop in initramfs` | `initramfs` | parity | as 1, plus `rd.break=pre-mount` |
| 7 | `VM test (no devicetree)` | `vmtest` | none | `console=ttyAMA0,115200` |

L0 on this ISO (new or changed): 2.5/2.12/2.17 (the seven entries, the arguments per entry, the DTB per entry); 3.6-3.11 (the parity DTB: decompiles, Denali root compatible, differs from the packaged DTB, equals the build record, `out/dtb-variants/` and the kernel worker's JSON); **5.5** (display chain and DSP set with their `modules.dep` closure in the real initramfs: 14 modules and 52 dependency entries); 5.6 (failure capture hooks and tools in the initramfs); **5.7** (the four DSP images in the initramfs with the `firmware/manifest.toml` hashes); 5.8 (no GPU zap, no `gen70500` in the initramfs); 8.11-8.13 (S4: PKNAME restriction and the Windows guard in both scripts, no "any BOOT partition" fallback, `/etc/sp11-boot-medium` equals the ISO volume id). Defects of my own tests found on the way: the L0 entry id pattern had no digits (`m3cmdline`), and the first `--initrd-fail` runs typed the edit into the wrong line of the GRUB editor (the entry body starts with an empty line after `setparams`), which first booted the system normally and then stopped at a GRUB error; the run above is the third.

L1 with the fake Windows disk (`image/tools/make-decoy-disk.sh`: GPT, FAT32 `BOOT` with the EFI system type, FAT32 `SP11LOGS`, NTFS `WINDOWS`, Microsoft reserved): attached writable next to the stick; it enumerated as `sda` in one run and `sdb` in another, so both orders were exercised. `md5sum` before and after: identical in both runs (`4ebca9db…` and `76aa9aa2…`). In the first run the collector's `boot-medium.txt` says `boot_disk: sdb  method: cmdline label Fedora-WS-Live-44 -> /dev/sdb1` while the decoy was `sda`. In the second run (`--initrd-fail`, the cmdline label is wrong on purpose) the hook found the stick through the built-in ISO label: `boot_medium: sda (built-in ISO label Fedora-WS-Live-44 -> /dev/sda1)`, wrote `initrd-<boot-id>/` (journal 656,966 bytes, dmesg, rdsosreport with the wrong label, state, STATUS, SEQ, COMPLETE) to the stick's ESP 311 s after start, and no `<boot-id>/` of a real root exists. **Not tested:** the Windows guard on a boot medium that itself carries NTFS (only the function, with loop devices, in `collector_selftest.sh`); the collector with a real `msm`; GDM (no full L1).

### M5 ISO (2026-10-26, decision D21, risk S1)

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261026T192029Z.iso` (record `.json`, checksum `.iso.sha256`) |
| Size | 2,803,040,256 bytes |
| SHA-256 | `a106d5e16d6173045c9a68d026e2f6aff9ceecf686b2697bbadd59b1112bf933` |
| Build time | 1475 s for the kiwi run |
| Kernel | `kernel-core-7.3.0-65.sp11.3.fc44.aarch64` (same RPMs as M3 and M4; M5 is DT and image only) |
| DTB `m5` | `7c5f8155248661ce11700cdf8ed5c126225fd597d38ab4bef83d867094e3074d` (parity, sound and `&swr0` off, GPU off) |
| DTB `m5gpu` | `91dfcab143810907aaece65549b77d3c34c2357820723c7a28b9db9fe0773ffc` (parity, sound and `&swr0` off, GPU on) |
| Other DTBs on the ISO, unreferenced | packaged, parity, edponly, nobl: **all four enable the speakers** (`kernel-dtb-safety.py` says unsafe); never selectable from the menu |
| L0 | 148 passed, 0 failed, 0 skipped |
| L1 `--until-session --decoy` | PASS |
| L1 `--initrd-fail --decoy` | PASS |

Menu (every device entry: the verbose common arguments, `root=live:CDLABEL=Fedora-WS-Live-44 rd.live.image`, `clk_ignore_unused pd_ignore_unused rootdelay=10`, then):

| # | Title | `sp11.entry` | DTB | Extra |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m5 | none |
| 2 | `SP11 debug, GPU on` | `gpu` | m5gpu | none |
| 3 | `SP11 debug, GPU on + DRM trace` | `gpu-drm-trace` | m5gpu | `drm.debug=0x1ff` |
| 4 | `SP11 debug nomodeset` | `nomodeset` | m5 | `nomodeset` |
| 5 | `SP11 debug, stop in initramfs` | `initramfs` | m5 | `rd.break=pre-mount` |
| 6 | `VM test (no devicetree)` | `vmtest` | none | `console=ttyAMA0,115200` |

What M5 changes (the initramfs of M4 is unchanged: leds-qcom-lpg, the DSP remoteproc set and the four DSP images stay):

- **S1, L0 2.18:** every DTB that a `devicetree` line of a device entry points to is decompiled with `dtc` and judged by the kernel worker's `scripts/kernel-dtb-safety.py` (effective status: a node is enabled only if every ancestor is; watched: `x1e80100-sndcard`, `sdw20217020400` = WSA8845, `wsa884`). L0 fails if any of them is effectively enabled, or if no watched node exists at all. The check was run against the five DTBs of `out/dtb-variants/`: `m5` and `m5gpu` pass, `parity`, `edponly`, `nobl` fail.
- **The ESP is mounted only for each write** (`release_target` in the collector): `publish()` takes a lock, mounts, writes, `sync`, `umount`, and checks `/proc/mounts` (five tries); the `STATUS` file names the last target (`target: esp (the mount lasts only for each write)`). The initramfs hook does the same. No `fsck` of the boot ESP anywhere. L1 extracts the ESP of the stick after the run and runs `fsck.fat -n`: no dirty bit (22,221 of 129,022 clusters used, 92 files).
- **Evidence files:** `gpu-speed-bin.txt` (the qfprom nvmem device found under `/sys/bus/nvmem/devices`, exactly two bytes read with `dd bs=1 skip=$((0x119)) count=2`, the raw bytes and the decoded value `(u16 >> 7) & 0xff`; the cell is `gpu-speed-bin@119`, `reg = <0x119 0x2>`, `bits = <7 8>` in `hamoa.dtsi:8790`; the decode was tested on a fake nvmem file whose neighbouring bytes are `0xff`, and L0 8.16 checks the script reads nothing else, S5); `sound.txt` (`/proc/asound/cards`, `aplay -l`, `/dev/snd`, soundwire and WSA884x dmesg lines: in QEMU "no soundcards found"); `gpu.txt` (devfreq of the GPU: `available_frequencies`, `min_freq`, `max_freq`, `cur_freq`, `governor`; `/dev/dri`; dmesg lines `adreno|a6xx|gmu|zap|msm_gpu|speed bin`).
- **Cadence and session trigger:** after the early snapshot and the first full snapshot, 18 light display snapshots every 10 s (`FAST_COUNT`, `FAST_INTERVAL`), then the old 20, 60, 120, 300 s. Two systemd path units, installed, enabled and preset: `sp11-log-collector-session-first.path` (`DirectoryNotEmpty=/run/systemd/sessions`: any logind session, the greeter included) and `sp11-log-collector-session-user.path` (`PathExistsGlob=/run/systemd/sessions/[0-9]*`: the numbered autologin session of liveuser), each starting `sp11-log-collector-session@<name>.service`, which stops its path unit first and then writes `session-<name>-loginctl.txt`, `session-<name>-journal.txt` (journal tail) and `STATUS.session-<name>`, and then the display set. A lock serialises it with the running collector.

L1 evidence (QEMU TCG, `--until-session --decoy`, 1295 s): the menu listed 6 entries, the VM entry booted, the collector wrote to the `BOOT` ESP (no `SP11LOGS` disk), both session snapshots were in the log directory (`session-first-*`, `session-user-*`, `loginctl` shows the session), the fake Windows disk was byte-identical (md5 before and after), and the ESP was clean. `--initrd-fail --decoy` also passed (journal 658,167 bytes in `initrd-<boot-id>/`). Defects found by these runs, fixed before this ISO: `STATUS` said `target: none` (the mount is released after each write; now the last target is recorded); the session services, restarted by their own path units after a start timeout in a slow TCG run (the path unit is now stopped before the snapshot, the timeout is 600 s, and the logind state is published before the display set). **Not tested:** a real session start on the device, a real `qfprom`, the GPU (no `msm` in QEMU).

### Collector fixes after the M5 device log (2026-10-28)

- **Debugfs allow-list.** The M5 GPU-off boot's `dmesg.txt` has 36 NULL dereferences in `dpu_crtc_debugfs_state_show+0x4c [msm]` (process `head`, Oops up to `[#9]`, plus a WARNING in `dpu_crtc_get_intf_mode`): the collector's `dump_tree` walked all of `/sys/kernel/debug/dri` and read every `crtc-*/state`. From now on a file below `/sys/kernel/debug` is read only if `debugfs_allowed` in the collector names it: `devices_deferred`, `gpio`, `pwm`, `device_component/*`, `clk/clk_summary`, `pm_genpd/pm_genpd_summary`, `regulator/regulator_summary`, `devfreq/devfreq_summary`, the pinctrl summaries and per-controller `pins`, `pinmux-pins`, `pinmux-functions`, `pinconf-pins`, `pingroups`, `gpio-ranges`, and `dri/<N>/{name,clients,state}` (`state` is DRM core's atomic state, read on every snapshot of the M5 boot without a fault; it is not the DPU file). Every other file, every `crtc-*`, `plane-*`, `encoder-*`, connector and `dp_debug` file included, is skipped, and the skip is written into the log (`=== path (not read: not on the debugfs allow-list)`). `dp-link.txt` is now only a listing. The msm bug itself is for the display-lcd dossier. L0 8.18 runs the collector's own function against the crtc, plane, encoder, `dp_debug`, `..` and other paths (all refused) and the known-safe ones (allowed); 8.19 checks that `dump_tree` is gated and nothing reads `crtc-*` directly.
- **GPU speed bin.** The M5 log said `read of 2 bytes at 0x119 failed (got '')`: the nvmem core rejects reads not aligned to the provider's stride. The collector now makes one 4-byte read at `0x118` (`dd bs=4 skip=$((0x118 / 4)) count=1`), cuts the 2-byte cell (`<7 8>` of `0x119`) out of it, and writes only the two cell bytes and the decoded value; the other two bytes of the window are discarded unseen. Tested on a fake nvmem file with distinct neighbouring bytes (not in the output). L0 8.16 checks the single aligned read.
- Noted for the GPU work, no change: with the GPU on, `msm` probes in the initramfs and `qcom/gen70500_sqe.fw` fails with -2 there (the GPU firmware is not in the initramfs by D21); the devfreq `max_freq` was 1,250,000,000.
- No ISO was built for this. The M5 ISO still has the old collector, so L0 on it fails exactly 8.16, 8.18 and 8.19; the same checks pass against the repository's collector.

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
- 2026-10-25: D19/M3. ISO `sp11-fedora44-aarch64-kiwi-20261025T160856Z` (SHA-256 `2a7f7fc1...`): 8-entry menu, three DTBs, early display snapshot and the display evidence files, `collect-dpcd.py` in the image, 64 MiB FAT32 ESP with direct GRUB. L0 103/103; L1 `--esp-fallback` PASS (collector writes `/EFI/sp11-logs` on the `BOOT` ESP). Build refuses kernels not newer than 7.3.0-65.sp11 and more than one kernel NEVRA at the top of `out/rpms`.
- 2026-10-25: D20/M4 and S4. ISO `sp11-fedora44-aarch64-kiwi-20261025T183834Z` (SHA-256 `0325c6f4...`): seven-entry menu with the parity DTB as default, `leds-qcom-lpg` and the DSP remoteproc set with the four DSP images in the initramfs, failure capture to the ESP, collector and hook write only to the boot medium and refuse Windows disks. L0 131/131; L1 `--esp-fallback --decoy` and `--initrd-fail --decoy` PASS, fake Windows disk byte-identical.
- 2026-10-26: D21/M5 and S1. ISO `sp11-fedora44-aarch64-kiwi-20261026T192029Z` (SHA-256 `a106d5e1...`): six-entry menu with the sound-off DTBs `m5` and `m5gpu`; L0 2.18 fails if any device entry's DTB enables the speakers; the collector mounts the ESP per write, reads the GPU speed-bin cell only, records sound and GPU state, snapshots at the first logind session. L0 148/148, L1 `--until-session --decoy` and `--initrd-fail --decoy` PASS.
