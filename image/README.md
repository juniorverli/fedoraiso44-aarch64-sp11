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

ISO builder: **kiwi-ng**, using Fedora's pinned f44 Workstation-Live description (D16), inside a privileged Fedora 44 container. The historical livemedia-creator path (D11) is documented below and remains available as `--builder lmc`.

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

The current M11 menu is recorded in [M11 private integration](#m11-private-integration-2026-10-30). Default `debug` uses `m11`; `touch off` uses `m11-notouch`; the optional microphone entry uses `m11-audio`. All eight device entries keep `clk_ignore_unused pd_ignore_unused rootdelay=10 rd.driver.blacklist=qcom_battmgr modprobe.blacklist=qcom_battmgr` (the no-early-DSP entry adds `qcom_q6v5_pas` to the rd blacklist). Every selectable DTB keeps the GPU and speakers off; only the microphone entry enables a card without a WSA link and with `swr0` disabled. The VM entry has no device DTB or clock/rootdelay overrides and adds `console=ttyAMA0,115200`.

Default `debug`, `touch off` and `microphones` carry `qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink,smp2p:*,remoteproc:* trace_buf_size=8M` (DSP R-I2/R-K3), so tracing starts before DSP probe. `usbdbg` retains M10's `pmic_glink_altmode.dyndbg=+p ps883x.dyndbg=+p phy_qcom_qmp_combo.dyndbg=+p ucsi_glink.dyndbg=+p typec_ucsi.dyndbg=+p dwc3.dyndbg=+p dwc3_qcom.dyndbg=+p qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink trace_buf_size=8M`. D23 keeps `qcom_battmgr` blocked. The collector writes the selected `sp11.entry` to `entry.txt`; the build record contains the exact arguments for every entry. The packaged DTB remains on the ISO for RPM comparison and is unreferenced by the menu.

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
7. Privacy: no MAC address, serial number or `sources/windows` path in any file of the image, including the operator Bluetooth address file (provision it only after DD-writing the stick).
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

- **Debugfs allow-list.** The M5 GPU-off boot's `dmesg.txt` has 36 NULL dereferences in `dpu_crtc_debugfs_state_show+0x4c [msm]` (process `head`, Oops up to `[#9]`, plus a WARNING in `dpu_crtc_get_intf_mode`): the collector's `dump_tree` walked all of `/sys/kernel/debug/dri` and read every `crtc-*/state`. From now on a file below `/sys/kernel/debug` is read only if `debugfs_allowed` in the collector names it: `devices_deferred`, `gpio`, `pwm`, `device_component/*`, `clk/clk_summary`, `pm_genpd/pm_genpd_summary`, `regulator/regulator_summary`, `devfreq/devfreq_summary`, the pinctrl summaries and per-controller `pins`, `pinmux-pins`, `pinmux-functions`, `pinconf-pins`, `pingroups`, `gpio-ranges`, and `dri/<N>/{name,clients}`. All DRM `state` files are refused: DRM core atomic-state dumping calls the driver print hooks too (`sources/linux/drivers/gpu/drm/drm_atomic.c:2124`, `:2202`), so successful earlier reads do not establish safety. Every other file, every `crtc-*`, `plane-*`, `encoder-*`, connector and `dp_debug` file included, is skipped, and the skip is written into the log (`=== path (not read: not on the debugfs allow-list)`). `dp-link.txt` is now only a listing. The msm bug itself is for the display-lcd dossier. L0 8.18 runs the collector's own function against the crtc, plane, encoder, `dp_debug`, `..` and other paths (all refused) and the known-safe ones (allowed); 8.19 checks that `dump_tree` is gated and nothing reads `crtc-*` directly.
- **GPU speed bin.** The M5 log said `read of 2 bytes at 0x119 failed (got '')`: the nvmem core rejects reads not aligned to the provider's stride. The collector now makes one 4-byte read at `0x118` (`dd bs=4 skip=$((0x118 / 4)) count=1`), cuts the 2-byte cell (`<7 8>` of `0x119`) out of it, and writes only the two cell bytes and the decoded value; the other two bytes of the window are discarded unseen. Tested on a fake nvmem file with distinct neighbouring bytes (not in the output). L0 8.16 checks the single aligned read.
- Noted for the GPU work, no change: with the GPU on, `msm` probes in the initramfs and `qcom/gen70500_sqe.fw` fails with -2 there (the GPU firmware is not in the initramfs by D21); the devfreq `max_freq` was 1,250,000,000.
- No ISO was built for this. The M5 ISO still has the old collector, so L0 on it fails exactly 8.16, 8.18 and 8.19; the same checks pass against the repository's collector.

### Debugfs read rationale after M5

The generic collector and image-owned USB-C hook use exact debugfs file patterns; other paths are refused, including every `dri/*/state`, `crtc-*`, connector, `dp_debug` and test attribute. The component-owned DSP/Wi-Fi drop-ins retain their explicit bounded readers; neither reads DRM state. `drm-state.txt` records a refusal. These permitted files are established framework/port readers, do not invoke DPU atomic-state printing, and do not change configuration. This is a bounded source-based safety assessment, not a claim that debugfs can never contain a driver defect. Source paths below are under `sources/linux/` (v7.3).

| Allowed file(s), below `/sys/kernel/debug/` | Why retained |
|:--|:--|
| `dri/<N>/name` | `drivers/gpu/drm/drm_debugfs.c:54`: prints identity/bookkeeping under the master mutex, no modeset/atomic print hooks. |
| `dri/<N>/clients` | `drivers/gpu/drm/drm_debugfs.c:75`: locked client list and process metadata, no modeset/atomic print hooks. |
| `devices_deferred` | `drivers/base/dd.c:244`: locked deferred-probe list; prints names/reasons. |
| `device_component/*` | `drivers/base/component.c:83`: locked component binding list; no component driver callback. |
| `gpio`, `pwm` | `drivers/gpio/gpiolib.c:5418`, `drivers/pwm/core.c:2634`: GPIO read/status and PWM cached/current-state queries, previously captured in M5 without a reported fault; no configuration setter. |
| `clk/clk_summary` | `drivers/clk/clk.c:3422`: clock topology/rate/status queries under framework locks; does not set rates or enables. |
| `pm_genpd/pm_genpd_summary` | `drivers/pmdomain/core.c:3877`: locked power-domain status/accounting query; no power transition. |
| `regulator/regulator_summary` | `drivers/regulator/core.c:6744`: regulator status/voltage/load queries; no voltage/current setter. |
| `devfreq/devfreq_summary` | `drivers/devfreq/devfreq.c:1965`: device/governor/frequency summary, no governor/target change. |
| `pinctrl/{pinctrl-devices,pinctrl-handles,pinctrl-maps}` | `drivers/pinctrl/core.c:1894`, `:1937`, `:1974`: framework registrations and mappings; no mux selection. |
| `pinctrl/<controller>/{pins,pinmux-pins,pinmux-functions,pinconf-pins,pingroups,gpio-ranges}` | `drivers/pinctrl/core.c:1735`, `:1809`, `:1860`, `drivers/pinctrl/pinmux.c:576`, `:619`, `drivers/pinctrl/pinconf.c:304`: pin descriptions/configuration queries needed for the PMIC backlight, previously captured in M5; no configuration write. |
| `usb/devices`, `usb/xhci/<controller>/ports/port<N>/portsc` | `drivers/usb/core/devices.c:510` device listing and `drivers/usb/host/xhci-debugfs.c:327` port-status show: USB descriptor/topology and PORTSC register reads requested by USB-C; no reset/test/port-control write. |

### Bluetooth operator file and ec-sam tools (M6)

Payloads from merged `main` were read with `git show main:<path>` into `image/component-inputs/`, with commit and file hashes in `sources.json`. The builder stages the Bluetooth helper/service/masked collector unchanged and enables the hci0-triggered service through its wants link and Fedora preset. The hook runs `timeout -k 1 80 /usr/libexec/sp11-bt-collect` into `extra-bluetooth.txt`. Fedora BlueZ startup and generic NVM stay in place. No controller means no helper activation in QEMU. L0 checks actual installed bytes, activation, packages and absence of private inputs.

The operator adds the Windows-observed address **after DD-writing the ISO**, as exactly one colon-formatted address plus an optional newline at **`BOOT:/EFI/sp11/bt-address`**, on the boot stick's FAT32 ESP (not `SP11LOGS`, not the ISO filesystem). The boot helper finds only that ESP as a sibling of the mounted live ISO, mounts it read-only in a private namespace, and unmounts on success/failure. The image, intermediate overlays, build records and git contain no address input. On installed Fedora only, `/etc/sp11/bt-address` may instead be provisioned locally, root-owned mode 0600. Keep the stick and full journals private.

To read the address while Windows is running, use this exact read-only collector from PowerShell in the repository (no administrator rights or reboot required). Disconnect external Bluetooth adapters first so there is exactly one local radio:

```powershell
$btAddress = & .\image\tools\read-windows-bt-address.ps1
if ($btAddress -notmatch '^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$') { throw 'No single valid local radio address' }
```

The script calls Microsoft's documented [BluetoothFindFirstRadio](https://learn.microsoft.com/en-us/windows/win32/api/bluetoothapis/nf-bluetoothapis-bluetoothfindfirstradio) / next / close functions and [BluetoothGetRadioInfo](https://learn.microsoft.com/en-us/windows/win32/api/bluetoothapis/nf-bluetoothapis-bluetoothgetradioinfo); the returned [BLUETOOTH_RADIO_INFO.address](https://learn.microsoft.com/en-us/windows/win32/api/bluetoothapis/ns-bluetoothapis-bluetooth_radio_info) is the local radio address. It performs no discovery, registry query, pairing, power or firmware operation. It refuses multiple radios and sentinel values. The script has been checked statically here; executing it on Windows remains operator evidence. Keep `$btAddress` private and do not echo it or paste it into a task, command literal or git file.

Once the operator has DD-written the ISO and identified/mounted **the stick's** `BOOT` ESP, replace `E:` below with that ESP's drive letter. This separate provisioning step writes only that local stick:

```powershell
$usbEsp = 'E:' # replace only after checking this is the USB stick's BOOT ESP
New-Item -ItemType Directory -Force -Path "$usbEsp\EFI\sp11" | Out-Null
[System.IO.File]::WriteAllText("$usbEsp\EFI\sp11\bt-address", $btAddress + "`n", [System.Text.Encoding]::ASCII)
Remove-Variable btAddress
```

Alternatively, the existing private `sources/windows/live-inventory/sp11-mac.conf` can be converted offline as in `hardware/bluetooth/image-request.md` on main; never mount the Windows partition to get it and never run that conversion during the ISO build. Provisioning modifies the written stick's checksum, which is expected; it does not change the validated ISO file.

The ec-sam R3 early chain is `surface_aggregator`, `surface_aggregator_registry`, `surface_aggregator_hub`, `surface_hid`, `surface_hid_core`, `hid`, `hid_generic` with dracut-resolved dependencies. The modular transport/registry/hub/HID drivers are also in `force_drivers`; built-in UART/serdev, GENI and pinctrl need no module file. `hid_multitouch` stays a root driver: only the keyboard is promised in an initramfs shell. L0 uses `lsinitrd` and checks every early module's `modules.dep` closure or built-in equivalent. Device confirmation at `rd.break=pre-mount` is still required. Fedora `libinput-utils`/`evtest` and unchanged tools are installed under `/usr/libexec/sp11/ec-sam/{collect-input-capabilities.sh,collect-power.sh,ssam-ro.py}`. Manual read-only evidence commands are `sudo /usr/libexec/sp11/ec-sam/collect-input-capabilities.sh` and `sudo /usr/libexec/sp11/ec-sam/collect-power.sh`; they capture capabilities/power fields, never keyboard events or limit writes.

### M6 preparation (2026-10-28, D22–D24)

- D23: `/etc/modprobe.d/50-sp11-battery.conf` contains both `blacklist qcom_battmgr` and `install qcom_battmgr /usr/bin/false`; both dracut configurations omit it and explicitly install the blacklist into the initramfs. Every device menu entry also has the rd/modprobe blacklists (R4). L0 invalidates its extracted-root cache when the ISO SHA-256 changes, so a replaced ISO cannot inherit stale policy checks. `ucsi_glink` stays in the early USB-C bridge chain. L0 5.9–5.11 verifies actual kmod resolution, no built-in/initramfs battery driver, the initramfs policy and a fail-closed audit of threshold references in image text policy (documentation, firmware and modules excluded). The audited DSP collector only reads the thresholds; Fedora's UPower rules only test their existence. Packaged binary APIs are outside the text audit: preventing qcom_battmgr from loading is the enforcement for its writable attributes.
- DP regression: the allow-list refuses `msm_dp_test_active`, `test_active`, `test_data` and `test_type`, both directly under connectors and below `dp_debug`; L0 8.18 exercises all forms. `dp-link.txt` lists paths only. This covers the M5 `msm_dp_test_active_show` NULL dereference without repeating private log lines.
- DSP R-I1 and Wi-Fi I1: the original component drop-ins are staged unchanged at build time. USB-C test-plan B is an image-owned drop-in, with USB debugfs reads routed through the allow-list (`usb/devices` and per-port `portsc` only). L0 8.20 verifies the installed scripts.
- Wi-Fi I3/I4: `sp11-rfkill-events.service` is enabled and preset before NetworkManager; `systemd-modules-load` loads `rfkill` first so the listener can open `/dev/rfkill` even without a radio in QEMU. `options ath12k debug_mask=0x30` is valid without `CONFIG_ATH12K_DEBUG`: the parameter is unconditional at `sources/linux/drivers/net/wireless/ath/ath12k/core.c:28–31`; only its output helpers are conditional (`debug.h:43–64`). L0 checks the shipped module parameter. Existing M6 RPMs may still lack debug output until the kernel worker supplies K2.
- Wi-Fi I2: the original unblock probe is installed outside the automatic drop-in directory. Only `sp11.wifi_unblock=1` permits sourcing it during full snapshots; its own once-per-boot and 90-second guards remain. L0 checks the gate and the menu disallows that flag on every other entry. It changes only transient radio state.
- Build scripts read the cached pinned Fedora description without cloning/fetching or any Git writes. They refuse an unpublished M6 DTB before building. Only the M6 variant is copied (historical variants remain outside this ISO).
- Validation during preparation: shell/Python syntax; S6 fixtures reject direct shell redirection, a separate path variable, `tee`, udev writes and Python writes; menu fixtures reject default Wi-Fi unblocking, a GPU DTB and modified trace arguments. `scripts/index.py --check`: 21 components, 0 errors. L0 and QEMU results follow when the DTB is available.


### M6 replacement ISO (2026-10-29, D22–D24)

The earlier `out/iso/sp11-fedora44-aarch64-kiwi-m6-20261028T191900Z.iso` is invalid (142 PASS, 2 FAIL: 5.10 and 8.18). It is retained for the orchestrator to remove after accepting this replacement.

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-m6-20261028T233509Z.iso` |
| Record / checksum | `out/iso/sp11-fedora44-aarch64-kiwi-m6-20261028T233509Z.json` / `.iso.sha256` |
| Size | 2,802,581,504 bytes |
| SHA-256 | `871b1a4d184670f33411c24665c46d42e34f2556f333760212037cc570aec215` |
| Kernel | `kernel-core-7.3.0-65.sp11.3.fc44.aarch64`; both BTF options enabled |
| Build | Fresh kiwi compose, 1763 seconds, 1972 packages |
| ESP | 64 MiB FAT32, 129022 clusters, direct Fedora GRUB (D17–D18) |
| L0 | **161 passed, 0 failed, 0 skipped**; report `out/iso/sp11-fedora44-aarch64-kiwi-m6-20261028T233509Z.l0.txt` |
| QEMU | **PASS, 18/18 checks**, `--until-session --decoy`, 1780 seconds to complete session captures; reports `.l1.txt` / `.l1.json` |

Menu verified from the ISO's build record. Every device entry uses `denali-m6.dtb` (GPU/speakers off) and the common verbose/live arguments plus `clk_ignore_unused pd_ignore_unused rootdelay=10 rd.driver.blacklist=qcom_battmgr modprobe.blacklist=qcom_battmgr`:

| # | Title | `sp11.entry` | DTB | Extra |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m6 | none |
| 2 | `SP11 debug, USB + DSP trace` | `usbdbg` | m6 | USB/DSP trace arguments listed above |
| 3 | `SP11 debug, no early DSP` | `nodsp` | m6 | rd blacklist is `qcom_battmgr,qcom_q6v5_pas` |
| 4 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | m6 | `sp11.wifi_unblock=1` |
| 5 | `SP11 debug nomodeset` | `nomodeset` | m6 | `nomodeset` |
| 6 | `SP11 debug, stop in initramfs` | `initramfs` | m6 | `rd.break=pre-mount` |
| 7 | `VM test (no devicetree)` | `vmtest` | none | common verbose/live arguments and `console=ttyAMA0,115200`; no device overrides |


QEMU evidence: the menu showed all seven entries, `vmtest` booted, GDM was active/running, BTF was present, the complete collector capture and both logind session snapshots were written to the boot stick's `BOOT` ESP. After shutdown `fsck.fat -n` found no dirty bit (106 files, 22499/129022 clusters); the fake Windows disk's MD5 remained `bada24dbb8920a71f5854569082197cd`. No QEMU or image-build container remains running. This session-scoped run does not perform the full L1 failed-unit allow-list audit. The Bluetooth capture reports both BlueZ and the address helper inactive with `Result=success`, as expected without a WCN7850 in QEMU; real address application and the SAM keyboard still require device evidence.

Additional checks: Bluetooth's 14 Fedora mock tests passed (including boot-sibling selection, read-only mount options and cleanup); the QEMU driver self-test passed; menu negative fixtures reject a missing D23 flag, a GPU-enabled DTB and default Wi-Fi unblocking. These mock tests do not establish real controller/FAT provisioning behavior. The Windows reader is statically checked and still awaits execution by the operator. All changes remain uncommitted under D24.


### M7 preparation (2026-10-29)

M7 uses `kernel-core-7.3.0-65.sp11.4.fc44.aarch64` (series revision 4). The kernel dossier records nine integrated patches: the retained display patches, Wi-Fi and second USB-C retimer wiring, two ec-sam registry fixes, RFC 0014 GENI pre-initialization diagnostics, and packaged speaker disable. `CONFIG_ATH12K_DEBUG=y` adds Wi-Fi debug output; both BTF options stay enabled. SAM hold patches and spi-hid stay excluded.

The builder requires that exact release and both DTB/JSON pairs under `out/dtb-variants/7.3.0-65.sp11.4.fc44.aarch64/qcom/`. It checks each DTB hash, release, revision and ordered patch-content digest before composing. The build record retains `kernel_series_sha256` for the series file itself and adds `kernel_patch_series_sha256` for the kernel worker's ordered path/content digest. These are different hashes by design.

| DTB | SHA-256 |
|:--|:--|
| `x1p64100-microsoft-denali-m7.dtb` | `290d7f4957673822ad04c66a47724f1c21ca333948e24802b5cb42226c590ab6` |
| `x1p64100-microsoft-denali-m7-touchdiag.dtb` | `3b97decd8bde2831e725b22ed80c038cdf5bf043ea81f438de9aa46850bb3554` |

The normal variant is byte-identical to the M6 default but is consumed under its M7 name and record. The diagnostic differs only in SE2 `status` (enabled); it has no HID child, touch supply or consumer and requests no QUP wrapper firmware. The added menu entry follows the six M6 device entries, with identical `debug` arguments except its `sp11.entry` marker. VM test remains last. The packaged DTB is retained for RPM comparison and is unreferenced by the menu.

The unchanged touch owner's `hardware/touch-pen/collect-read-only.sh` is installed as `/usr/libexec/sp11-touch-pen-collect`, mode 0755, with its hash in the build record. After debugfs setup, each full collector snapshot runs exactly `shsnap touch-pen.txt 'bash /usr/libexec/sp11-touch-pen-collect'`. It only reads and prints; absent DT/controller state is not a zero-valued hardware sample. M6's D23 battery policy, Bluetooth address helper and provisioning procedure, SAM tools/early modules, debugfs allow-list, radio probe gate and USB/DSP diagnostic arguments are retained.

L0 now requires the M7 release/milestone (4.9), actual ath12k debug output functions and printk format in the installed module (4.10), and RFC 0014's message in the installed GENI module (4.11). Both variants must match their published and embedded JSON (3.9–3.11, 3.14) and pass the kernel owner's wiring/parity/controller-only checker (3.13), including an exact SE2-only diff. S1 still checks every selectable device DTB (2.18). The installed touch helper, executable mode, hash and exact collector invocation are checked (8.27); QEMU also requires its kernel/DT/pinctrl/firmware capture sections.

Before composing: both published DTBs passed hash/S1/wiring/touch exclusion checks; the menu passed its positive case and rejected wrong diagnostic DTB, diagnostic argument drift, missing battery blacklist, GPU DTB and default Wi-Fi unblocking. The QEMU driver self-test selected the eighth entry successfully. An initial preflight attempt stopped before composing because it compared the series-file hash to the patch-content digest; that comparison was corrected without changing kernel inputs or producing an ISO.

### M7 ISO (2026-10-29)

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-m7-20261029T090813Z.iso` |
| Record / checksum | `out/iso/sp11-fedora44-aarch64-kiwi-m7-20261029T090813Z.json` / `.iso.sha256` |
| Size | 2,802,188,288 bytes |
| SHA-256 | `fa8aaf016afb9eb83265a0498a6c18cd7d1c5be90469427a13aa4ae5f3b93015` |
| Kernel | `kernel-core-7.3.0-65.sp11.4.fc44.aarch64`; both BTF options and ATH12K_DEBUG enabled |
| Build | One fresh kiwi compose, 1576 seconds, 1971 packages; build id `20261029T090903Z` |
| ESP | 64 MiB FAT32, direct Fedora GRUB (D17–D18) |
| L0 | **176 passed, 0 failed, 0 skipped**; report `out/iso/sp11-fedora44-aarch64-kiwi-m7-20261029T090813Z.l0.txt` |
| QEMU | **PASS, 19/19 checks**, `--until-session --decoy`, 1900 seconds to session captures; reports `out/iso/sp11-fedora44-aarch64-kiwi-m7-20261029T090813Z.l1.txt` / `.l1.json` |

Menu read from the built ISO. All seven device entries retain the common verbose/live arguments and `clk_ignore_unused pd_ignore_unused rootdelay=10 rd.driver.blacklist=qcom_battmgr modprobe.blacklist=qcom_battmgr`, with the `nodsp` replacement noted below:

| # | Title | `sp11.entry` | DTB | Extra |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m7 | none |
| 2 | `SP11 debug, USB + DSP trace` | `usbdbg` | m7 | USB/DSP trace arguments listed above |
| 3 | `SP11 debug, no early DSP` | `nodsp` | m7 | rd blacklist is `qcom_battmgr,qcom_q6v5_pas` |
| 4 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | m7 | `sp11.wifi_unblock=1` |
| 5 | `SP11 debug nomodeset` | `nomodeset` | m7 | `nomodeset` |
| 6 | `SP11 debug, stop in initramfs` | `initramfs` | m7 | `rd.break=pre-mount` |
| 7 | `SP11 debug, touch SE2 diagnostic` | `touchdiag` | m7-touchdiag | Same arguments as `debug` except entry marker |
| 8 | `VM test (no devicetree)` | `vmtest` | none | Common verbose/live arguments and `console=ttyAMA0,115200`; no device overrides |

M6 policy and component payloads are retained, including all seven prior entries' argument tails and every pinned Bluetooth/SAM input hash. The fresh Fedora transaction updated 14 non-kernel package versions (Broadcom board firmware/overlays, Firefox, GDB, rabbitmq, Pillow and Unbound) and removed `libbabeltrace`, in addition to replacing the five kernel RPMs. The package count changed from 1972 to 1971. The full NEVRA list is in the build record; the exact comparison is `out/image-work/m7-package-delta.json`. No package-selection or firmware-staging policy was changed for these repository updates.

The first M7 QEMU run reached both sessions in 1414 seconds and passed 18/19 assertions, including touch output, clean ESP (108 files, 22317/129022 clusters) and unchanged decoy. The destination assertion failed because a session collector starts with `CYCLE=0` and can replace `STATUS` with its early snapshot after the main collector writes `COMPLETE`; early `STATUS` has no `target:` field. The complete capture and both session snapshots were physically present on the boot copy's ESP, and GDM was active. That run is preserved as `out/iso/sp11-fedora44-aarch64-kiwi-m7-20261029T090813Z.l1-status-metadata.{txt,json}` and `out/image-work/l1-sp11-fedora44-aarch64-kiwi-m7-20261029T090813Z-status-metadata/`.

The QEMU verifier now checks the actual capture source: the boot copy's identity, GPT partition 2's EFI type and byte offset, FAT label `BOOT`, and `/EFI/sp11-logs`. For the dedicated log image it checks the `SP11LOGS` label and no partition offset/subdirectory. A contradictory explicit `target:` still fails. The regression matrix in `image/tools/qemu_driver_selftest.sh` accepted early/full status and rejected another disk, wrong offset, contradictory target, wrong log directory, partition-offset SP11LOGS input and wrong label; the fake-QEMU driver run also passed. This changes only host-side validation; the single ISO is unchanged. The fresh QEMU run of that same ISO passed all 19 checks in 1900 seconds to session captures, with no fatal message or console stall.


Final QEMU evidence: all eight menu entries displayed; the VM entry booted the M7 kernel; BTF, the full collector capture, touch helper sections and both logind session snapshots were present on the boot copy's GPT ESP. GDM started. The read-only `fsck.fat -n` check found no dirty bit (107 files, 22508/129022 clusters); decoy MD5 before/after was `1f302d2e52d77eee6fd0469bbd583e5e`. This is the requested session-scoped run; the full failed-unit allow-list audit and device behavior were not tested. The ISO checksum remained unchanged after both QEMU runs. No image/QEMU process or task container remains. Changes are uncommitted under D24.

### M8 integration (2026-10-29)

M8 pins the revision-5 kernel `7.3.0-65.sp11.5.fc44.aarch64` and the published `m8` / `m8-notouch` DTB/JSON pairs. The packaged DTB remains available for RPM comparison. Menu order follows the M7 table with the old `touchdiag` entry replaced in place by `SP11 debug, touch off` (`notouch`). All other device entries use `m8`, including the touch-on default. Existing verbose arguments, clock/domain overrides, root delay, D23 blacklists, USB/DSP trace spelling and opt-in Wi-Fi unblock gate remain.

The Fedora-native iptsd spec in `image/iptsd/iptsd.spec` is based on the upstream 3.1.0 spec; it replaces the CI source placeholder, disables Meson fallback downloads and adds standard Fedora systemd/udev package macros. `scripts/image-build-iptsd.sh` requires the central source pin, verifies archive/spec hashes, rechecks the official Fedora repositories and builds `iptsd-3.1.0-1.fc44.aarch64.rpm`. The image installs that RPM through its normal local-repository transaction, with upstream `/etc/iptsd.conf`, presets, udev rule and static `iptsd@.service`. Service activation is enabled by the packaged `SYSTEMD_WANTS` rule for the detected escaped hidraw path; there is no hardcoded device instance. Dimensions/orientation remain metadata-driven, with no speculative SP11 preset.

`fixed`, `gpi`, `spi-geni-qcom`, `spi-hid`, `spi-hid-of`, `hid-multitouch` and `uinput` are explicitly included/forced in dracut and listed in the live modules-load policy. `fixed` is also required by the existing display supply path now that M8 makes it modular. L0 checks the complete early dependency closure, all eight touch module hashes against the kernel release JSON, the M8 release/variant JSON, iptsd RPM/config/presets/udev activation, and installed capture code. The Bluetooth helper, early SAM chain and DRM atomic-state read refusal remain.

Each full snapshot still runs exactly `shsnap touch-pen.txt 'bash /usr/libexec/sp11-touch-pen-collect'`. It adds `iptsd-journal.txt` (the journal for `iptsd@*.service`) and `libinput-device-names.txt` (only `Device:` values from `libinput list-devices`, without properties, serial fields, kernel paths, groups or seats). The shared helper masks address patterns and labeled serial/unique identifiers before exporting either new capture. Privacy fixtures exercise the actual installed helper. QEMU requires these files and loaded uinput/SPI-HID modules, in addition to the existing menu/VM/session/ESP/decoy checks.

Preflight: both DTBs pass the kernel owner's compiled wiring/S1/GPU/parity checker, including the exact one-property fallback difference. Menu fixtures pass and reject a wrong fallback DTB, missing battery blacklist, default radio unblock and trace drift. The QEMU driver regression passes with the eighth entry selected.

The continuation starts at `3cd9c9f`, already equal to main, with the centrally pinned iptsd inputs available. The interrupted RPM run had completed: `out/rpms/iptsd-3.1.0-1.fc44.aarch64.rpm`, SHA-256 `e253b72b0a8fe41910ef8d8f113ccfb515509974cb49a7fd7fc3f78ceade134a`. Its archive, upstream spec, local spec and central pin-file hashes were rechecked against the build record; the RPM is aarch64 and includes the upstream config, presets and udev/template service. Fedora's query found no official package. `%check` completed successfully but upstream defines no Meson tests, so no upstream test coverage is claimed. L0 also verifies the central pin-file hash, archive URL/hash, upstream spec hash and commit against the embedded iptsd record.

### M8 ISO (2026-10-29)

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-m8-20261029T172500Z.iso` |
| Record / checksum | `out/iso/sp11-fedora44-aarch64-kiwi-m8-20261029T172500Z.json` / `.iso.sha256` |
| Size | 2,801,991,680 bytes |
| SHA-256 | `dda2e2a78024bbb8b3d61451641ababc55a279bf2ac915ef75f3f17c0b1fb8c4` |
| Kernel | `kernel-core-7.3.0-65.sp11.5.fc44.aarch64`; series revision 5, both BTF options enabled |
| Build | One fresh kiwi compose, 1840 seconds, 1975 packages; build id `20261029T171659Z` |
| iptsd | Local Fedora-native `iptsd-3.1.0-1.fc44.aarch64`; upstream config/presets and udev-activated template service |
| DTB `m8` | `1ad30d3e3f928a6db5c5b8bf2649bed8f85baaba3cf2adc6ed542bafe502a0e6` |
| DTB `m8-notouch` | `6dbac355db7f081b5f77db4558e646efaef14eff7d90a51ed9afcdd44b4eebb7` |
| ESP | 64 MiB FAT32, 129022 clusters; direct Fedora GRUB (D17–D18) |
| L0 | **197 passed, 0 failed, 0 skipped**; report `out/iso/sp11-fedora44-aarch64-kiwi-m8-20261029T172500Z.l0.txt` |
| QEMU (L1) | **21 PASS, 0 FAIL** (`out/iso/…m8-20261029T172500Z.l1.txt`, rerun 2026-10-29 19:03 after the verifier fix); the earlier 20/21 run is kept as `.l1-empty-iptsd.txt`. Clean ESP (110 files, 22528/129022 clusters), decoy unchanged |

Menu from the built ISO. Every device entry retains the common verbose/live arguments and `clk_ignore_unused pd_ignore_unused rootdelay=10 rd.driver.blacklist=qcom_battmgr modprobe.blacklist=qcom_battmgr`, with the `nodsp` replacement noted below. Every selectable device DTB keeps speakers and GPU off.

| # | Title | `sp11.entry` | DTB | Extra |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m8 | none; touch on |
| 2 | `SP11 debug, USB + DSP trace` | `usbdbg` | m8 | USB/DSP trace arguments listed above |
| 3 | `SP11 debug, no early DSP` | `nodsp` | m8 | rd blacklist is `qcom_battmgr,qcom_q6v5_pas` |
| 4 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | m8 | `sp11.wifi_unblock=1` |
| 5 | `SP11 debug nomodeset` | `nomodeset` | m8 | `nomodeset` |
| 6 | `SP11 debug, stop in initramfs` | `initramfs` | m8 | `rd.break=pre-mount` |
| 7 | `SP11 debug, touch off` | `notouch` | m8-notouch | Same arguments as `debug` except entry marker |
| 8 | `VM test (no devicetree)` | `vmtest` | none | Common verbose/live arguments and `console=ttyAMA0,115200`; no device overrides |

Compared with M7, the Fedora transaction replaced the five kernel packages with revision 5 and added only `iptsd`, `cairomm`, `libsigc++20` and `spdlog`; no package was removed and no other NEVRA changed. The complete delta is `out/image-work/m8-package-delta.json`; the complete NEVRA list is in the ISO build record. Before composing, only reproducible M6/M7 L0 extracted roots/images were removed for disk headroom; their ISOs, reports and collected evidence remain.

L0 verifies both published/embedded DTB JSON records and hashes, S1 on every selectable device DTB, the exact one-property touch-off difference, all eight touch-module payload hashes against the release JSON, and **34 early modules with 104 dependency entries** in the actual initramfs or built in. This includes the modular `fixed` supply provider. The native iptsd package/config/presets, unmodified RPM payload, udev activation, current central source pins, forced early/live touch modules, exact touch helper invocation, userspace capture code and privacy fixtures all pass. Bluetooth, the early SAM chain, the DRM-state read refusal and D23 policy retain their passing checks.

The first QEMU run reached both sessions and the complete capture at 1861 seconds; it passed 20/21 checks, including loaded uinput/SPI-HID modules, clean ESP (109 files, 22476/129022 clusters) and unchanged decoy. The userspace-capture assertion failed because the dedicated journal helper reports `<capture failed: exit 1>` when no iptsd instance exists. Fedora `journalctl` returns ENODATA for a unit glob with no match. A populated native journal fixture made with `systemd-journal-remote-259.10-1.fc44.aarch64` confirms exit 0 for its matching fixture service and exit 1 with `Failed to add filter for units: No data available` for `iptsd@*.service` (`out/image-work/m8-journal-unit-fixture/`, `m8-journal-filter-fixtures.log`). The original reports are retained as `.l1-empty-iptsd.{txt,json}` and the work directory as `out/image-work/l1-sp11-fedora44-aarch64-kiwi-m8-20261029T172500Z-empty-iptsd/`.

The host verifier accepts that exact exit-1 capture only for `sp11.entry=vmtest`, with both SP11 controller paths explicitly absent in the captured DT, a valid full boot journal and no iptsd instance/daemon in that journal. Other exit codes, unavailable captures, device entries, missing controller/journal evidence, existing iptsd instances, failed input capture, leaked input properties and addresses still fail; ten negative fixtures exercise these cases. Normal nonempty iptsd journals remain accepted. This corrects only host-side interpretation of an expected hardware absence; the collector and single ISO remain unchanged. The helper's exit-1 marker is retained as evidence, and actual iptsd activation/processing remains a device gate.

### M9 private ISO (2026-10-30)

One private ISO for the operator's own device (decision D25, S5 exception), built with `scripts/image-build.sh --private`. It contains this device's addresses and the derived Wi-Fi board file in its root file system: never share it, upload it, or boot it on another device. Delete it together with `out/image-work/l0-<name>/` (the L0 `root` directory, which held the values, was removed after validation).

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-m9-private-20261030T034021Z.iso` |
| Record / checksum | `out/iso/sp11-fedora44-aarch64-kiwi-m9-private-20261030T034021Z.json` / `.iso.sha256`; the record holds hash prefixes only and `distribution: forbidden` |
| Size | 2,801,532,928 bytes |
| SHA-256 | `aef6790996d2b0fe3ef98c7485e661ea42a75b13ca80ba6913f67cbf8070a88d` |
| Kernel | `kernel-core-7.3.0-65.sp11.6.fc44.aarch64`; series revision 6, both BTF options enabled |
| Build | One fresh kiwi compose, 1664 seconds, 1975 packages; build id `20261030T034024Z` |
| DTB `m9` | `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` |
| DTB `m9-notouch` | `5704f68668538f6dd3e6fc37f67e8e9830f771124c57475c0ebca81d8c750519` |
| Packaged LCD DTB | `784de3eb644bc6a169cbe0c6da51cef0f984984493a44e6fbfd00b18cd792709` |
| L0 | **202 passed, 0 failed, 0 skipped**, including private checks 7.6-7.10 and 8.33; report `out/iso/sp11-fedora44-aarch64-kiwi-m9-private-20261030T034021Z.l0.txt` (no address value) |
| QEMU (L1) | **21 PASS, 0 FAIL** with `--until-session --decoy`, 2160 seconds to the session captures; `.l1.txt` / `.l1.json`. Clean ESP (113 files, 22811/129022 clusters), decoy md5 unchanged |

Menu: the M8 entry list and order are unchanged. Every device entry keeps the common verbose/live arguments and `clk_ignore_unused pd_ignore_unused rootdelay=10 rd.driver.blacklist=qcom_battmgr modprobe.blacklist=qcom_battmgr`, with the `nodsp` replacement of the rd blacklist. Every selectable device DTB keeps speakers and GPU off.

| # | Title | `sp11.entry` | DTB | Extra |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m9 | DSP trace arguments (R-I2); touch on |
| 2 | `SP11 debug, USB + DSP trace` | `usbdbg` | m9 | USB/DSP trace arguments |
| 3 | `SP11 debug, no early DSP` | `nodsp` | m9 | rd blacklist is `qcom_battmgr,qcom_q6v5_pas` |
| 4 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | m9 | `sp11.wifi_unblock=1` |
| 5 | `SP11 debug nomodeset` | `nomodeset` | m9 | `nomodeset` |
| 6 | `SP11 debug, stop in initramfs` | `initramfs` | m9 | `rd.break=pre-mount` |
| 7 | `SP11 debug, touch off` | `notouch` | m9-notouch | Same arguments as `debug` except the entry marker |
| 8 | `VM test (no devicetree)` | `vmtest` | none | Common arguments and `console=ttyAMA0,115200` |

What changed against M8:

- Kernel and DTBs: revision 6 RPMs and the published `m9`/`m9-notouch` DTBs. The builder refuses another kernel, a DTB or JSON that differs from the kernel worker's record, and a series revision other than 6. L0 re-checks both DTBs (S1, GPU off, wiring, CMA allocation range, the one-property touch-off difference), JSON hashes and all eight touch module payload hashes against the release record. `kernel-m8-check.py` is the shared checker; it accepts the `m9` variants.
- DSP (R-I1/R-I2): the refreshed collector is installed unchanged (L0 8.20, S6 audit hash updated in `image/tools/check-charge-writes.py` for its audited threshold read). The `debug` and `touch off` entries now carry `qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink trace_buf_size=8M` so tracing starts at module load; `check-m8-menu.py` enforces that `touch off` equals `debug` except for the marker.
- Bluetooth: the three userspace files and `check.py` were refreshed from main `9bdb845` in `image/component-inputs/bluetooth/userspace/` (pins in `sources.json`); the nine-command collector and the soft-skip of `sp11-bt-address` (exit 0 without an address file) come with them. In this private ISO `/etc/sp11/bt-address` is present, so the helper configures the controller without the boot-ESP file.
- Wi-Fi: the M9 collector is installed unchanged. Not done from the Wi-Fi requests: I2 (retire the unblock probe), I3 (listener ordering) and I4 (`debug_mask=0x70`); the M8 menu entry and `0x30` stay as asked, so these remain open for the orchestrator.
- USB-C: the overlay collector gained `usb-typec-bindings.txt`, `usb-typec-config.txt`, `usb-typec-partner.txt` and `usb-lsusb-tree.txt` (read-only; no retimer register read, no debugfs write), and `/usr/share/sp11/usb-typec-m9-matrix.txt` holds the four-row port/orientation matrix with the decoding rule from test-plan F.
- Collector units: `sp11-log-collector-session@.service` `TimeoutStartSec` 600 to 1500 and `sp11-log-collector.service` `TimeoutStopSec` 90 to 300 (L0 8.33). An earlier L1 without `--until-session --decoy` was run in error (no boot-disk log target) and its session snapshots hit the 600 s limit; the cause was the wrong test flags, so these two limits are a precaution, not a proven fix. Revert them if the shutdown delay is unwanted.
- L0 fixes for private mode: 6.3 allows only the derived board file path, 7.1 skips only the three private files, and 7.1/7.4 print file names, never matched values. A first L0 pass printed one matched Wi-Fi address in 7.1 into the work log and report; both were redacted at once, the report regenerated, and 7.10 now passes.

### M10 private ISO (2026-10-30)

One private ISO for the operator's own device (D25, S5 exception), built with `scripts/image-build.sh --private`. It contains this device's addresses and the derived Wi-Fi board file: never share it or boot it on another device. The L0 `root` directory was deleted after the run.

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-m10-private-20261030T084338Z.iso` |
| Record / checksum | `...m10-private-20261030T084338Z.json` / `.iso.sha256` (hash prefixes only, `distribution: forbidden`) |
| Size | 2,801,401,856 bytes |
| SHA-256 | `96825b56d7813cac41aa678e2dbeef36db9cb76134e0ee314461bb0bb6ebf458` |
| Kernel | `kernel-core-7.3.0-65.sp11.7.fc44.aarch64`; series revision 7 (adds the read-only `sp11-glink:` GLINK OPEN_ACK diagnostic), BTF on |
| Build | One fresh kiwi compose, 1927 seconds, 1975 packages; build id `20261030T084341Z` |
| DTB `m10` | `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` (byte-identical to `m9`) |
| DTB `m10-notouch` | `5704f68668538f6dd3e6fc37f67e8e9830f771124c57475c0ebca81d8c750519` |
| L0 | **203 passed, 0 failed, 0 skipped**, including private checks 7.6-7.10 and new 8.34; report `...m10-private-20261030T084338Z.l0.txt` |
| QEMU (L1) | **21 PASS, 0 FAIL** with `--until-session --decoy`; `.l1.txt` / `.l1.json`. Clean ESP (113 files, 22802/129022 clusters), decoy md5 unchanged |

Menu: identical to M9 with `m10` in place of `m9` (same eight entries, order and arguments; `debug` is the default and carries the DSP trace arguments; `touch off` uses `m10-notouch`; `vmtest` has no devicetree).

| # | Title | `sp11.entry` | DTB |
|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m10 |
| 2 | `SP11 debug, USB + DSP trace` | `usbdbg` | m10 |
| 3 | `SP11 debug, no early DSP` | `nodsp` | m10 |
| 4 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | m10 |
| 5 | `SP11 debug nomodeset` | `nomodeset` | m10 |
| 6 | `SP11 debug, stop in initramfs` | `initramfs` | m10 |
| 7 | `SP11 debug, touch off` | `notouch` | m10-notouch |
| 8 | `VM test (no devicetree)` | `vmtest` | none |

Changes against M9:

- Kernel/DTB gates: the builder and L0 now require kver `7.3.0-65.sp11.7.fc44.aarch64`, series revision 7, milestone `M10`, the `m10`/`m10-notouch` DTB and JSON pairs (hashes against the JSON, S1, GPU off, wiring, one-property touch-off difference) and the eight touch module hashes from the release record's `m10` entry (L0 3.x, 4.9, 4.12).
- DSP collector: `/etc/sp11-log-collector.d/dsp-subsystems.sh` is now the owner's collector (R-I1, unchanged in `hardware/`) followed by `image/component-inputs/dsp-glink-append.sh`, so the output stays in `extra-dsp-subsystems.txt`. The append runs the owner's section 7.4 commands: `dmesg | grep sp11-glink`, `journalctl -k -b --no-pager | grep sp11-glink`, the OPEN_ACK-timeout, IPCRTR/FASTRPCGLINK OPEN/OPEN_ACK and create_ept greps, the two counts, and a closing remoteproc name/state block. It is read only and enables or clears nothing. L0 8.20 compares the installed file with that concatenation and 8.34 checks the commands. The S6 audit hash in `image/tools/check-charge-writes.py` covers the concatenated file.
- Private checks 7.6-7.10 and S5 rules are unchanged; L0 prints file names only. A scan of the repository, the L0/L1 reports and the work logs for the address values found none.
- Disk guard passed (45 GiB headroom, C: free 14 GiB); nothing was deleted.

### M11 private integration (2026-10-30)

One private ISO for the operator's device (D25/S5); never share it. The extracted L0 `root` and private staging tree have been removed.

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-m11-private-20261030T121406Z.iso` |
| Record / checksum | `out/iso/sp11-fedora44-aarch64-kiwi-m11-private-20261030T121406Z.json` / `.iso.sha256`; hashes only, distribution forbidden |
| Size | 2,802,319,360 bytes |
| SHA-256 | `5c6a0a118fca87abb429d8e369f6818fcbd60850bf2665f879023b08675019e1` |
| Kernel | `kernel-core-7.3.0-65.sp11.8.fc44.aarch64`; revision 8, both BTF settings enabled |
| Build | One fresh kiwi compose, 1448 s, 1975 packages; build id `20261030T121409Z` |
| Menu | 9 entries: 8 device entries using 3 selectable DTBs, plus the VM entry |
| Wi-Fi board | Fedora generic; no derived override installed |
| L0 | **215 passed, 0 failed, 0 skipped**, including private checks 7.6–7.10; `.l0.txt` |
| QEMU L1 | **21 PASS, 0 FAIL** with `--until-session --decoy` (`out/iso/…m11-private-20261030T121406Z.l1.txt`, verified by the orchestrator after the Codex usage limit cut the worker off) |

Menu checked in the built ISO. All device entries keep the M10 verbose/live arguments, clock/domain overrides, root delay and D23 blacklists; `nodsp` replaces the rd blacklist as below. Every selectable DTB keeps the GPU and WSA speaker bus/amplifiers off.

| # | Title | `sp11.entry` | DTB | Extra diagnostics |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m11 | GLINK, SMP2P and remoteproc trace |
| 2 | `SP11 debug, USB + DSP trace` | `usbdbg` | m11 | M10 USB/DSP trace arguments |
| 3 | `SP11 debug, no early DSP` | `nodsp` | m11 | rd blacklist `qcom_battmgr,qcom_q6v5_pas` |
| 4 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | m11 | `sp11.wifi_unblock=1` |
| 5 | `SP11 debug nomodeset` | `nomodeset` | m11 | `nomodeset` |
| 6 | `SP11 debug, stop in initramfs` | `initramfs` | m11 | `rd.break=pre-mount` |
| 7 | `SP11 debug, touch off` | `notouch` | m11-notouch | Same arguments as `debug`, except entry marker |
| 8 | `SP11 debug, microphones` | `audio` | m11-audio | Same arguments as `debug`, except entry marker |
| 9 | `VM test (no devicetree)` | `vmtest` | none | Common verbose/live arguments and `console=ttyAMA0,115200` |

The single M11 compose uses revision-8 kernel `7.3.0-65.sp11.8.fc44.aarch64` and the published `m11`, `m11-notouch` and `m11-audio` DTB/JSON pairs. The first seven M10 menu entries keep their order, followed by `SP11 debug, microphones` (`audio`) and the VM entry. The microphone entry uses `m11-audio`; `debug` uses `m11`, and `touch off` uses `m11-notouch`. No speaker or GPU entry exists. The default, touch-off and microphone entries add `smp2p:*,remoteproc:*` to the existing GLINK `trace_event=` argument; the USB/DSP entry retains its M10 diagnostic arguments.

- Wi-Fi I9/I3/I4: the derived board file that crashed firmware in M10 is omitted by default, including in private mode. Fedora's packaged generic board file stays intact. An explicit `SP11_WIFI_BOARD2` is accepted only after the owner's structural verifier exits zero against a Fedora reference and the Windows payload hash; failure warns and retains Fedora's file. This build leaves the override off. `ath12k debug_mask=0x70` is installed before module load; the rfkill listener no longer orders NetworkManager. Persistent Wi-Fi identity remains in the private NetworkManager configuration and `.link` file.
- SAM R10: `sp11-ssam-shutdown.service` is enabled/preset for `sysinit.target` but skipped unless `sp11.ssam_shutdown` appears on the command line (opt-in since the flash review, `hardware/ec-sam/evidence/2026-10-30-flash-review-verdicts.md`: the kernel `.shutdown` already sends display-off and D0-exit, so the unit is an unproven experiment); when enabled it unbinds the actual SAM serdev device during shutdown/reboot after the log collector stops (`Before=sp11-log-collector.service`). `sp11-ssam-rebind.service` is enabled/preset but skipped unless `sp11.ssam_rebind` appears on the command line; its script checks the argument again and uses only the device already bound to `surface_serial_hub`. Add that argument manually in GRUB for an operator-chosen test. The owner's example `After=multi-user.target` would cycle with `WantedBy=multi-user.target`, so it is omitted; the unit retains udev-settle ordering. The read-only R10 collector is snapshotted from the ec-sam worker's unmerged dossier, hash-pinned in `image/component-inputs/m11.json` and installed unchanged. No input events are read.
- DSP R-K3: retain the M10 DSP/USB-C hooks and the sp11-glink greps; the DSP append now reads remoteproc debugfs `trace0` and `resource_table`, bounded to 256 KiB and five seconds per file. Nothing enables/clears tracing or restarts a remoteproc.
- Microphones/S1: install only `hardware/audio-speakers/userspace/overlay`, including the UCM alias, microphone capture profile, WirePlumber default sink volume 0.05, and locked GNOME above-100-percent setting. Fedora's `config.sh` runs `dconf update` before exiting. `overlay-speakers` is never copied. The local topology artefact is the audio owner's public upstream build from `aab5c37c4fb9d9daed2dc789b8b7ca91c4133899`, 22856 bytes, SHA-256 `b192044f01e97eabe7f6df9ae0d394086badb3c30124573210bc781093da8c03`; staged at `out/image-inputs/audio/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin`. The source recipe remains `hardware/audio-speakers/userspace/build-topology.sh`; no Git-writing recipe was run here. It has no speaker protection and does not authorize speaker output.
- L0: check every selectable DTB with the kernel owner's narrow microphone exception. The microphone card must have `swr0` disabled, no WSA playback link and only DMIC routes. The default now equals the packaged parity DTB, so 3.8 requires equality for `m11`; other variants must differ. New 6.4 allows only the exact public topology path and hash in the firmware inventory. New 8.35 validates actual UCM/topology/policy bytes, effective compiled dconf value and lock, SAM activation/scripts, bounded DSP reads, and the audio-volume module payload hashes against the checked kernel release record. New 8.36 validates the installed SAM/rfkill units and ordering. Private checks 7.6–7.10 remain mandatory and print names only.

Preflight passed: three compiled DTB wiring/S1/parity/CMA checks, positive nine-entry menu and four negative fixtures, private staging 27/27 plus actual valid/invalid board override cases, QEMU driver/target/capture regressions, and systemd unit verification. The disk guard initially refused at 26 GiB headroom. After inspecting each candidate, only the superseded M8/M9 ISOs/checksums, L0/L1 reports and corresponding L0/L1 work directories were deleted (`out/image-work/m11-cleanup.txt`). Headroom at compose start was 75 GiB. M10, device logs, firmware/private board inputs, DTB variants, reference trees, sources and all RPM archives were retained.

### M12 private ISO (2026-10-30)

One private ISO for the operator's device (D25/S5); never share it. Same nine-entry menu and content as M11 with the M12 kernel and DTBs. The extracted L0 `root` and the private staging tree were removed. Two earlier compose attempts were discarded: a WSL crash on a full C: and a menu-checker miss (`check-m8-menu.py` still named the M11 default DTB). Both partial work directories (they held private files) were deleted.

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261030T185301Z-private.iso` (the name has no milestone token) |
| Record / checksum | `out/iso/sp11-fedora44-aarch64-kiwi-20261030T185301Z-private.json` / `.iso.sha256`; hashes only, distribution forbidden |
| Size | 2,802,253,824 bytes |
| SHA-256 | `cfb772e05939ace425f6646477b6803873c8afd6e33ce4c46f48cf3303f54ac1` |
| Kernel | `kernel-core-7.3.0-65.sp11.9.fc44.aarch64`; series revision 9, both BTF settings enabled |
| Build | One fresh kiwi compose, 1281 s, build id `20261030T185301Z` |
| Menu | Unchanged from the M11 table above with `m12`, `m12-notouch`, `m12-audio` in place of the `m11` DTBs |
| L0 | **215 passed, 0 failed, 0 skipped**, including private checks 7.6-7.10, 4.9, 4.12, 3.14, 8.35, 8.36; `.l0.txt` |
| QEMU L1 | **21 PASS, 0 FAIL** with `--until-session --decoy` (`.l1.txt` / `.l1.json`); ESP clean, decoy disk checked |

Changes against M11: the builder, L0 and the L1 touch-helper check require kver `7.3.0-65.sp11.9.fc44.aarch64`, series revision 9, milestone `M12`, the `m12*` DTB/JSON pairs and the `m12` entries of the kernel release record (touch modules, new modules). The shutdown unit stays opt-in (`sp11.ssam_shutdown`, `Before=sp11-log-collector.service`) and `ssam-unbind.sh` is shipped; L0 8.35/8.36 check both. Private-stage trap and checks 7.6-7.10 unchanged; no value is printed or recorded. Not verified: anything on hardware (touch, microphones, SAM shutdown, Wi-Fi/Bluetooth). The pinned `m11.json` input record and `check-m11-payload.py` keep their M11 names.

### M13 private ISO (2026-10-31)

One private ISO for the operator's device (D25/S5); never share it. Kernel M13 (series revision 10) with six DTB variants and a sixteen-entry menu. The extracted L0 `root` and the private staging tree were removed after the checks. No disk cleanup was needed: the guard passed (headroom above 30 GiB).

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261030T234013Z-private.iso` |
| Record / checksum | `out/iso/sp11-fedora44-aarch64-kiwi-20261030T234013Z-private.json` / `.iso.sha256`; hashes only, distribution forbidden |
| Size | 2,798,321,664 bytes |
| SHA-256 | `0020e3843298a6ecccdcbea8d32d497252f41d1f4eafcd69aaaee520729b872d` |
| Kernel | `kernel-core-7.3.0-65.sp11.10.fc44.aarch64`; series revision 10, both BTF settings enabled |
| Build | One fresh kiwi compose, 1761 s, 1976 packages; build id `20261030T234013Z` |
| Wi-Fi board | Fedora generic; no derived override (`SP11_WIFI_BOARD2` unset) |
| libcamera | `libcamera`, `libcamera-tools` (with `libcamera-ipa`) 0.7.2-2.fc44 installed from Fedora; a dnf test transaction of the two packages completed before the compose and the compose installed them (cameras R4: RGB software ISP, no tuning file, no Windows data) |
| L0 | **250 passed, 0 failed, 0 skipped** (`.l0.txt`), including private checks 7.6-7.10, 2.18, 3.15 (six variants), 4.9, 4.12, 5.11, 8.35-8.38 |
| QEMU L1 | **21 PASS, 0 FAIL** with `--until-session --decoy` (`.l1.txt` / `.l1.json`, 2304 s to both session snapshots in the first run); menu 16 of 16 titles seen while scrolling to the VM entry, ESP clean, decoy disk byte-identical. A first run failed one check, the touch helper section, because the driver still named the sp11.9 kernel; fixed in `image/tools/qemu_boot_test.py` and rerun on the same ISO |

Menu (checked in the built ISO by the builder, by `image/tools/check-m8-menu.py` and by L0 2.5/2.12/2.17). Every device entry keeps the verbose arguments, `clk_ignore_unused pd_ignore_unused rootdelay=10` and the `qcom_battmgr` blacklists. "Diagnostics" means: USB dynamic debug (`pmic_glink_altmode ps883x phy_qcom_qmp_combo ucsi_glink typec_ucsi dwc3 dwc3_qcom`), `qcom_pd_mapper`/`pdr_interface` dynamic debug and the corrected DSP trace string `trace_event=:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg,power:power_domain_target trace_buf_size=16M`.

| # | Title | `sp11.entry` | DTB | Arguments beyond the common ones |
|--:|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | m13 (microphones) | Diagnostics |
| 2 | `SP11 debug, no sound` | `nosnd` | m13-nosnd (M12 behaviour) | Diagnostics |
| 3 | `SP11 debug, touch off` | `notouch` | m13-notouch | Diagnostics |
| 4 | `SP11 debug, CDSP keep proxy votes` | `cdsp-keep` | m13 | Diagnostics + `qcom_q6v5_pas.keep_proxy_pds=1` (C4 test) |
| 5 | `SP11 debug, SAM shutdown quiet` | `ssam-quiet` | m13 | Diagnostics + `surface_aggregator.shutdown_mode=quiet` |
| 6 | `SP11 debug, SAM shutdown clean` | `ssam-clean` | m13 | Diagnostics + `surface_aggregator.shutdown_mode=clean` |
| 7 | `SP11 debug, SAM shutdown silent` | `ssam-silent` | m13 | Diagnostics + `surface_aggregator.shutdown_mode=silent` |
| 8 | `SP11 debug, speakers (gated; kernel gate still refuses playback)` | `spk` | m13-spk | Diagnostics; the speaker UCM overlay is installed at boot |
| 9 | `SP11 debug, rear camera diagnostic` | `cam` | m13-cam | Diagnostics |
| 10 | `SP11 debug, USB + DSP trace` | `usbdbg` | m13 | USB and PDR dynamic debug, `trace_event=:mod:qcom_glink trace_buf_size=8M` (as in M12) |
| 11 | `SP11 debug, no early DSP` | `nodsp` | m13 | rd blacklist `qcom_battmgr,qcom_q6v5_pas` |
| 12 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | m13 | `sp11.wifi_unblock=1` |
| 13 | `SP11 debug nomodeset` | `nomodeset` | m13 | `nomodeset` |
| 14 | `SP11 debug, stop in initramfs` | `initramfs` | m13 | `rd.break=pre-mount` |
| 15 | `VM test (no devicetree)` | `vmtest` | none | `console=ttyAMA0,115200` |
| 16 | `SP11 debug, GPU diagnostic (WARNING: may reset the machine)` | `gpu-diag` | m13-gpu | `printk.devkmsg=on log_buf_len=16M systemd.unit=multi-user.target sp11.gpu_diag=1`, entry text of `hardware/gpu/collector/grub-entry.txt` |

The old microphone entry (`audio`) is gone: the default is the microphone DTB. The forbidden-argument check now looks at kernel arguments only (a `linux` line word equal to `quiet`, `rhgb` or `splash`), because `SAM shutdown quiet` and `shutdown_mode=quiet` are legitimate text; this applies to the builder (step 7) and L0 2.1.

S1 and D26. L0 2.18 judges the DTB of every entry with `scripts/kernel-dtb-safety.py`: profile `default` for all of them, profile `d26` only for `m13-spk`, which must be used by the entry `spk` and nowhere else and must fail the default profile. L0 3.15 repeats this per DTB on the ISO, 3.13 runs `kernel-m8-check.py` per variant with the baselines and `--previous-m12` DTBs of `scripts/kernel-dtb-m13.sh`, 3.12 requires the GPU node disabled everywhere except `m13-gpu`, and 3.8 requires `m13-nosnd` to equal the packaged DTB byte for byte. The microphone UCM profile stays the only one in the UCM search path; the speaker profile (`hardware/audio-speakers/userspace/overlay-speakers`, unchanged) is stored in `/usr/share/sp11/ucm-speakers/` and `sp11-speaker-ucm.service` (condition `sp11.entry=spk`) copies it over the microphone profile only on entry 8. The kernel gate (audio-speakers 0009) still refuses WSA playback, so nothing becomes audible; WirePlumber cap 0.05 and the locked GNOME setting apply on every entry.

First speaker test (documented only, nothing here runs it; audio-speakers evidence `2026-10-30-d26-audio.md` section 7): boot entry 8 at no volume, desk quiet; read the automatic snapshot (`extra-audio.txt`: `amixer -c 0 contents`, `aplay -l`, `arecord -l`, dmesg of q6apm/wsa884x/swr0, no `CMD timeout for [1001021]`); then by hand `aplay -D hw:0,0 /dev/zero -d 1` must fail with `Operation not supported`; if playback starts, power off at once. Microphone check: `arecord -D hw:0,1 -f S32_LE -r 48000 -c 2 -d 5 /tmp/x.wav`. Never raise a control.

Collectors (all read-only, installed byte for byte from the owner files unless noted, checked by L0 8.20 and 8.37):

| Collector | Output | Notes |
|:--|:--|:--|
| ec-sam `collector/ec-sam.sh` (hash-pinned snapshot) | `extra-ec-sam.txt` | unchanged owner file |
| image drop-in `ssam-shutdown-mode.sh` | `extra-ssam-shutdown-mode.txt` | cmdline `surface_aggregator.*`, `/sys/module/surface_aggregator/parameters/shutdown_mode`, dmesg `shutdown mode` (the owner collector does not record it) |
| usb-typec R-I1 (`usb-typec.sh`) | `xhci-ports.txt` (portsc and portli), `usb-typec-dyndbg.txt`, `usb-typec-config.txt` (with `/proc/cmdline`), `usb-pd-partner.txt` | `portli` and `dynamic_debug/control` added to the debugfs allow-list; the matrix note is `/usr/share/sp11/usb-typec-m13-matrix.txt` (four rows, from test-plan G) |
| dsp-subsystems (owner file plus the image append) | `extra-dsp-subsystems.txt` | owner file now has the SMP2P, AOSS, genpd and handover sections; L0 8.37 requires them |
| image drop-in `cameras.sh` | `extra-cameras.txt` | commands of `hardware/cameras/test-plan.md`; no `i2cdetect`, no stream, no IR or flash; `cam -l` listing only |
| image drop-in `audio.sh` | `extra-audio.txt` | `arecord -l`, `aplay -l`, `amixer -c 0 contents`, UCM hashes, `wpctl status` as the session user |
| gpu two-step | on the boot medium, `EFI/sp11-logs/gpu-two-step/` | `/usr/libexec/sp11-gpu-two-step` plus `sp11-gpu-two-step.service` (condition `sp11.gpu_diag=1`, so only entry 16); image change: the label list gains `BOOT`, because this ISO's ESP is not labelled `SP11LOGS` or `ANACONDA` (owner request below) |
| upower | `charge.txt` | queried only when `upower.service` is active; the M12 error was a D-Bus refusal at an early snapshot |
| GPU speed bin | `gpu-speed-bin.txt` | already one aligned 4-byte read at `0x118` (L0 8.16); the cell is bytes 1-2 of the window |

Other changes: builder, L0 and the QEMU driver require kver `7.3.0-65.sp11.10.fc44.aarch64`, series revision 10 and milestone `M13`; `check-m11-payload.py` reads the `m13` entries of the kernel release record; `m11.json` re-pins the audio owner's comment-only edit of the microphone UCM file; `image/component-inputs/m13.json` pins the M13 inputs; `check-charge-writes.py` re-pins the audited DSP drop-in hash (one read-only `charge_control_*` attribute list, no write); the QEMU driver now scrolls a menu longer than one screen. New L0 checks: 2.18 (per-entry profile), 3.15, 8.37, 8.38.

Not verified here: everything on hardware (microphones, speakers, the CDSP proxy-vote and SAM shutdown tests, the rear camera, the GPU two-step, USB-C ports); that GRUB shows all sixteen entries on the Surface screen; that `:mod:smp2p` is accepted by the kernel (the next dmesg must be checked for `Failed to enable trace event`); that libcamera finds the sensor (no tuning file exists).

### M14 private ISO (2026-10-31)

One private ISO for the operator's device (D25/S5); never share it. Kernel M14 (series revision 11, `7.3.0-65.sp11.11.fc44.aarch64`), five DTB variants, a two-line menu. The extracted L0 `root` was removed after the checks. No disk cleanup was needed (guard 150 GiB headroom).

| Item | Value |
|:--|:--|
| ISO | `out/iso/sp11-fedora44-aarch64-kiwi-20261031T133710Z-private.iso` |
| Record / checksum | `...private.json` / `.iso.sha256`; hashes and counts only, distribution forbidden |
| Size | 2,800,484,352 bytes |
| SHA-256 | `56b0ead20837efb7f01cdff6e2c7e19bd3fd794421cf4afbbc74954cd7579411` |
| Build | One fresh kiwi compose, 1895 s, 1978 packages; build id `20261031T133710Z` |
| L0 | **245 passed, 0 failed, 0 skipped** (`.l0.txt`), including private checks 7.6-7.10, the new 7.11 (private files by hash), 2.17 (menu and grubenv logic), 8.37-8.42. The first run failed four checks, all checker-side (menu entry count with indented submenu lines, a needle in the SAM rotor check, the firmware allow-list for private files); fixed in the scripts, same ISO rerun (the second rerun needed a fresh extraction because the container chowns the work tree to the host user) |
| QEMU L1 | **21 PASS, 0 FAIL** with `--until-session --decoy` (`.l1.txt` / `.l1.json`, 2465 s to both session snapshots; the driver opens the submenu and selects `VM test` inside it; menu titles seen: 9 of 9; ESP clean; decoy disk byte-identical) |
| GRUB logic on the real ISO | **25 PASS, 0 FAIL** (`.grublogic.txt`, `image/tools/grub_logic_test.py`): real `grubaa64.efi` in QEMU/edk2, the shipped ESP `EFI/BOOT/grubenv` pre-set per case, first menu line left to time out, the three `SP11:` echo lines read from the serial console, the block read back from the FAT ESP. Cases: empty block (m14, variant 0, block becomes variant 1), `ok` with a kept SAM counter (variant 1, then 2), `testing` (previous boot died: GRUB saves `failed` and uses `m14-safe`, variant 2 then 3), `failed` (stays failed, variant 3 then 0), garbage variant (counts as 0), garbage state (boots m14). The same cases passed first on a small hybrid ISO with the kiwi layout (`image/tools/make-grub-test-iso.sh`). `grub2-script-check` accepts the main `grub.cfg` (L0 8.42) |
| menu2 patched ISO (2026-10-31) | `...20261031T133710Z-private-menu2.iso`, SHA-256 `f1c84fdb6f492c92d8b7a0d35d3bd7d711f5b27e5e3207a3bd83bdab4d5f82ae`, patched from menu1 (see "menu2" above); L0 **247 passed, 0 failed, 0 skipped**; rotor self-test 32 PASS on `image/overlay`; QEMU driver self-test 33 PASS; read-only GRUB logic test and `--until-session --decoy` L1 started last in the background: results in `...menu2.grublogic.txt` and `...menu2.l1.txt` (the line 921 row above is the M14 write-based test, superseded) |
| Rotor and hook self-test | `image/tools/rotor-selftest.sh` (L0 8.39), run on the installed scripts with fake sysfs, command lines and a fake boot medium: 27 PASS (SAM order and wrap, override, CDSP texts including the power-off warning, GPU hook report/arm/ok/skip/retry, `sp11-esp-env` round trip on a real block and its S4 refusal) |


**Menu (operator requirement: the bench uses only the FIRST line).** Line 1 is `SP11 debug` (default), the main entry with every test argument inline. Line 2 is `SP11 debug, safe (no GPU, no cameras)` (top level since menu1, same kernel with the `m14-safe` DTB, so the operator can isolate DTB from kernel without opening a submenu). Line 3 is one GRUB `submenu` "Recovery and tests", whose first two entries are the menu2 bisect pair. The long M13 list is gone (`cdsp-keep`, the three SAM entries, `cam`, `usbdbg`, `nodsp`, `wifi-unblock` and `gpu-diag` no longer exist; their jobs are the rotors below). Checked by the builder, `image/tools/check-m8-menu.py` and L0 2.5/2.12/2.17.

| # | Title | `sp11.entry` | DTB | Arguments beyond the common ones |
|--:|:--|:--|:--|:--|
| 1 | `SP11 debug` (default) | `debug` | `m14` (microphones, GPU/GMU/zap, rear/front/IR camera chains) or `m14-safe`, chosen by GRUB | `clk_ignore_unused pd_ignore_unused rootdelay=10`, the `qcom_battmgr` blacklists, USB dynamic debug (`pmic_glink_altmode ps883x phy_qcom_qmp_combo ucsi_glink typec_ucsi dwc3 dwc3_qcom`), PDR dynamic debug, `trace_event=:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg trace_buf_size=16M` (`power:power_domain_target` removed, the kernel rejected it again in M13), `sp11.gpu_diag=1`, then from GRUB: `qcom_q6v5_pas.keep_proxy_pds=<0\|1>`, `firmware_class.path=/usr/lib/firmware-sp11-cdsp46` (alternate variants), `sp11.cdsp_variant=<n>`, `sp11.gpu_dtb=<m14\|m14-safe>` |
| 2 | `SP11 debug, safe (no GPU, no cameras)` (top level) | `safe` | `m14-safe` (the M13 `m13` content) | same diagnostics, no rotor argument |
| 3 | submenu `Recovery and tests` | | | eight entries below |
| 3.1 | `bisect A: m14.dtb with safe arguments` | `bisect-a` | `m14` (literal, static line) | the safe entry's arguments, nothing else |
| 3.2 | `bisect B: m14-safe.dtb with main arguments` | `bisect-b` | `m14-safe` (static line) | the main entry's arguments with fixed values: `sp11.gpu_diag=1 qcom_q6v5_pas.keep_proxy_pds=0 sp11.cdsp_variant=0 sp11.gpu_dtb=m14-safe` (default CDSP variant, no firmware path) |
| 3.3 | `SP11 debug, no sound` | `nosnd` | `m14-nosnd` (M12 behaviour, equals the packaged DTB) | same diagnostics |
| 3.4 | `SP11 debug, touch off` | `notouch` | `m14-notouch` | same diagnostics |
| 3.5 | `SP11 debug, speakers (gated)` | `spk` | `m14-spk` (d26 profile only) | same diagnostics plus `sp11.allow_nominal=1` (this entry only): the speaker FIRST TEST, below |
| 3.6 | `SP11 debug, nomodeset` | `nomodeset` | `m14-safe` | `nomodeset` |
| 3.7 | `SP11 debug, stop in initramfs` | `initramfs` | `m14-safe` | `rd.break=pre-mount` |
| 3.8 | `VM test (no devicetree)` | `vmtest` | none | `console=ttyAMA0,115200` (L1 only) |

**menu2: write-free GRUB, bisect pair, patched test ISO (2026-10-31, second device report).** Device facts (private logs `out/device-logs/m14-20261031/`, `m13-20261031/`): on the M14 ISO line 1 `SP11 debug` fails with `UEFI Firmware failed to start the Linux Kernel Image 0x8000000000000001 (EFI_LOAD_ERROR)` AFTER GRUB printed its three `SP11:` lines; line 2 `SP11 debug, safe` (static: same kernel, same initrd, `m14-safe.dtb`, no GRUB function) boots. `m14.dtb` and `m14-safe.dtb` differ only in ten `status = "disabled"` to `"okay"` lines (GPU and camera nodes), so the DT content is an unlikely cause. The remaining differences of line 1 are (a) the function, which did `load_env` and `save_env` on the ESP `grubenv`, a WRITE to the USB stick through the firmware right before GRUB reads the 17 MB zboot kernel and the 110 MB initrd from the same device (Hypothesis: corrupted reads, a zboot zstd failure is `EFI_LOAD_ERROR`), (b) the command line (`sp11.gpu_diag=1 $sp11_cdsp_args sp11.gpu_dtb=...`), (c) `m14.dtb`. Nothing proves (a); menu2 removes it and adds two static entries that separate (b) and (c).

*Design.* GRUB NEVER WRITES: no `save_env` in any executable line (the builder, L0 2.19 and `check-m8-menu.py` fail otherwise) and exactly one read-only `load_env -f FILE sp11_gpu_state sp11_cdsp_variant` (function `sp11_main_read`, still run by line 1). All transitions moved to Linux on the boot medium (S4: only that medium, `sp11-esp-env`, `grub2-editenv` with an explicit path): the GPU service writes `testing` before step 1 and `ok` after both steps (unchanged); a boot that reads `testing` or `failed` gets `m14-safe` and Linux turns `testing` into `failed` and reports `died during step N` (`gpu-state-hooks.sh`, `sp11_gpu_hook_skip`); `sp11-cdsp-variant.service` advances the rotor for the NEXT boot (main entry only, `sp11.entry=debug`). The SAM rotor was already Linux-side. Changed files: `image/kiwi/overlay/grub-arm.cfg.iso-template`, `image/component-inputs/gpu-state-hooks.sh` (pins in `m14.json` updated), `image/overlay/usr/libexec/sp11/cdsp-variant`, `.../gpu-retry` and `sp11-esp-env` (comments), `image/tools/{check-m8-menu.py,rotor-selftest.sh,grub_logic_test.py,qemu_boot_test.py,fake_qemu.py}`, `scripts/image-test-static.sh` (2.5, 2.12, 2.17, new 2.19, 8.37, 8.39, new 8.43 for patched ISOs), `scripts/image-build-kiwi.sh`. The fresh-build path (M15) renders the same template.

*Read-only logic test* (`image/tools/grub_logic_test.py`, real `grubaa64.efi` in QEMU, 10 cases: missing block, empty, rotor 0..3 with `ok`, `testing`, `failed`, garbage variant, garbage state): per case the DTB and the variant are the expected ones AND the block is byte for byte the preset AND partition 2 has the same SHA-256 before and after the run. The text check `check-m8-menu.py` rejects `save_env`, `editenv`, any assignment that advances the rotor or the state, and a second `load_env`.

*Bisect decision table* (one boot each; line 1 is the write-free main entry):

| Line 1 | Bisect A (`m14.dtb`, safe args, static) | Bisect B (`m14-safe.dtb`, main args, static) | Conclusion |
|:--|:--|:--|:--|
| boots | any | any | the GRUB write was the cause (or a transient read error: repeat once) |
| fails | boots | boots | the GRUB logic itself (the function, `load_env` or the variable expansion) |
| fails | boots | fails | the main command line (`sp11.gpu_diag=1`, `qcom_q6v5_pas.keep_proxy_pds`, `sp11.cdsp_variant`, `sp11.gpu_dtb`) |
| fails | fails | boots | the `m14.dtb` content (GPU and camera nodes enabled) |
| fails | fails | fails | not DT, not arguments: the kernel/initrd read or zboot on this medium; compare with line 2 and reflash the stick |

*Patched test ISO `...-private-menu2.iso`* (built NOW, no kiwi rebuild, by `image/tools/make-menu2-iso.sh` from the menu1 ISO, as the menu1 ISO was made from the M14 ISO): the template is rendered with the values of the base ISO's own `/boot/grub2/grub.cfg` (rendering the menu1 template reproduces the menu1 file byte for byte), `grub2-script-check` and `check-m8-menu.py` pass, then `xorriso -indev OLD -outdev NEW -boot_image any replay -map grub.cfg /boot/grub2/grub.cfg` and `implantisomd5 --force --supported-iso`. Preservation proofs (script output in `out/image-work/menu2/preservation.txt`): partition 2 (the ESP) has the identical SHA-256; `diff -r` of the two mounted trees shows exactly one file, `boot/grub2/grub.cfg`; the El Torito and system-area reports are identical except for the position of the ESP (the ISO grew by one 2 KiB block, LBA 1334473 to 1334474, and the El Torito LBA equals the start of GPT partition 2), the ISO size and the random GPT GUIDs; the GPT has the same partitions and sizes. The record `...menu2.json` carries `patched_from` and `menu2_patch.linux_side_repo`: L0 judges the INSTALLED Linux side (8.37, 8.39, the M11 payload) against a `git archive HEAD` snapshot of the repository the squashfs was built from, and 8.43 runs the repository's NEW rotor self-test on `image/overlay`.

**What the patched ISO cannot do.** The squashfs is the M14/menu1 Linux side and cannot be patched here, so in this ISO the Linux-side transitions of menu2 do not exist: the CDSP rotor does not advance (every boot of line 1 uses the variant stored in the block, normally variant 0), a `testing` state is never turned into `failed`, and the GPU service of the old Linux side still writes `testing` before step 1 and `ok` after (its writes through Linux are the design and are kept). The effect on the test: GRUB boots `m14-safe` while the state is `testing`/`failed` and never leaves it by itself; to run the GPU test again clear it with `/usr/libexec/sp11/gpu-retry` or on any computer with `grub2-editenv <ESP>/EFI/BOOT/grubenv unset sp11_gpu_state`. The first boot (empty block) is the interesting one: `m14`, variant 0, nothing written by GRUB.

**Why the first line carries everything.** The operator only ever boots line 1, so everything that was a separate entry became a boot-time rotor or a self-healing rule on that line. The values GRUB needs live in one GRUB environment block on the boot medium's ESP, `EFI/BOOT/grubenv` (FAT label `BOOT`, GPT partition 2 of the disk GRUB started from; shipped empty, exactly 1024 bytes, L0 8.41). GRUB only READS it, with `load_env -f` (menu2: GRUB never writes, there is no `save_env` anywhere, see "menu2" below); Linux reads and writes it with `/usr/libexec/sp11-esp-env` (`grub2-editenv`, S4: only the ESP of the boot medium, refused on a disk with NTFS/BitLocker/MSR, mounted read-write for one call). The environment block holds `sp11_gpu_state`, `sp11_cdsp_variant` and `sp11_sam_counter` and nothing else. Without a usable block (optical medium, missing file) the main entry boots `m14` with CDSP variant 0.

**GPU self-healing** (the GPU ON resets the machine at the first DRM open that loads the zap shader and GMU, M5 evidence). The gpu worker's two-step collector (`hardware/gpu/collector/gpu-two-step.sh`) now runs on EVERY boot of the main entry (`sp11.gpu_diag=1` is inline), ordered before GDM (owner unit byte for byte plus the drop-in `sp11-gpu-two-step.service.d/10-sp11-image.conf`: `Before=gdm.service display-manager.service graphical.target`), so GNOME cannot be the first DRM opener. Image changes to the owner script, pinned in `image/component-inputs/m14.json` and required exactly by L0 8.37: the label list gains `BOOT`; the hook functions of `image/component-inputs/gpu-state-hooks.sh` are inserted before the main section; four one-line calls. The flow:

1. GRUB (function `sp11_main_read`, read only since menu2): `testing` or `failed` in the block selects `m14-safe` for that boot and every later boot of the main line, WITHOUT changing the value. Any other value (empty, `ok`, garbage) selects `m14`. `sp11.gpu_dtb=<m14|m14-safe>` is passed to the kernel. Linux marks the death: on the main entry (`sp11.entry=debug`) booted with `sp11.gpu_dtb=m14-safe` and state `testing`, the skip hook (`sp11_gpu_hook_skip`) writes `failed` and reports `GPU test: died during step N` (N from the previous-boot report); `failed` stays `failed`; a bisect entry never touches the state.
2. Linux, before step 1 (the first step that can reset the machine; earlier than the brief's "before step 2", so a death in step 1 is caught too): `sp11-esp-env set sp11_gpu_state=testing`, synced and unmounted before the step starts.
3. After step 1 and step 2 both ended in this boot (checked in `state.log`): `sp11_gpu_state=ok`. A step that aborted leaves `testing`, so the next boot falls back to `m14-safe`.
4. On an `m14-safe` boot the collector does not wait 90 s for a GPU that is not there: it reports and exits at once.
5. The next boot's collector reports one line, `GPU test: died during step N`, `GPU test: survived` (or `no earlier test recorded`), in `gpu-test-result.txt` next to the GPU logs, in `/run/sp11/gpu-test`, the journal, the operator notice and `extra-rotors.txt`.
6. Re-arm: `/usr/libexec/sp11/gpu-retry` (clears `sp11_gpu_state`), or `sp11.gpu_retry=1` on one boot's command line (press `e` in GRUB), or on any computer `grub2-editenv <ESP>/EFI/BOOT/grubenv unset sp11_gpu_state`.
7. Loop guard: nothing in the menu halts, reboots, waits for a key or chains configfiles (L0 2.17 checks the text); the main line always ends in a booting system; a garbage or missing value never selects a missing file (both `m14` and `m14-safe` are on the ISO, L0 2.7).

**SAM shutdown mode rotor** (`sp11-sam-mode-rotor.service`, early at every boot, before the collector): the mode of this boot is the next one of `/usr/share/sp11/sam-mode-order`, **silent, clean, quiet, default**, then repeat. The brief gave two different orders; this is the newest ec-sam evidence (`2026-10-31-m13-keyboard.md`: "`silent`, then `clean`, then `quiet`"), `default` last as the control, and the order is one data file. The counter is `sp11_sam_counter` in the environment block. The mode is written to `/sys/module/surface_aggregator/parameters/shutdown_mode`, read back, recorded in `/run/sp11/sam-mode` (collector file `extra-rotors.txt`, plus the existing `extra-ssam-shutdown-mode.txt`), and shown as `SAM shutdown mode for this boot: <mode>` (journal tag `sp11-notice`, `/usr/share/sp11/operator-notice.txt` linked as `/etc/motd.d/50-sp11-notice`, and one critical desktop notification through `notify-send`, XDG autostart `sp11-operator-notice.desktop`). A `surface_aggregator.shutdown_mode=` typed into GRUB wins and does not advance the counter. The mode acts at the next poweroff: test with `systemctl poweroff`, then boot Windows (ec-sam evidence `2026-10-30-windows-transition.md` section 6). Never combine `sp11.suspend_diag` with a SAM cycle (ec-sam request).

**CDSP experiment rotor** (dsp-subsystems R-I6, denisix comparison): `sp11_cdsp_variant` cycles every boot of the main line (GRUB only applies the value it reads; since menu2 `sp11-cdsp-variant.service` stores `(used + 1) mod 4` for the NEXT boot, on the main entry only) through (fw `c1-00078`, `keep_proxy_pds=0`), (`c1-00046.1`, 0), (`c1-00078`, 1), (`c1-00046.1`, 1); the previous fixed `keep_proxy_pds=1` is replaced. GRUB passes `qcom_q6v5_pas.keep_proxy_pds=<0|1>` and, for the alternate firmware, `firmware_class.path=/usr/lib/firmware-sp11-cdsp46`. `sp11-cdsp-variant.service` records and shows `CDSP variant for this boot: fw=<...> keep_proxy_pds=<..>` and what the NEXT boot loads; when the next boot loads the alternate firmware the text says: **do a FULL POWER-OFF (shut down, wait 10 s, power on), NOT a reboot**. The alternate pair (`out/firmware-private/dsp-subsystems/cdsp-c1-00046.1-woa-200.0.49.0/`, hashes in its `SHA256SUMS`) is installed in private mode only, under `/usr/lib/firmware-sp11-cdsp46/qcom/x1e80100/microsoft/Denali/` and in the initramfs through a private dracut file (`/etc/dracut.conf.d/93-sp11-cdsp46.conf`, `install_items`; absence in a public image is asserted by L0 7.12, hash equality and initramfs presence in a private one by L0 7.11). In a public image the variant service warns that the kernel falls back to the default firmware. Method (the brief asked to verify early whether dracut and the loader accept a custom path; no initramfs hook was needed): the kernel parameter `firmware_class.path` is a built-in parameter of the firmware loader, read before any driver probes (`sources/linux/drivers/base/firmware_loader/main.c:471-485` and `:514`, `fw_path_para` is the first entry searched, 256 bytes), the early PAS driver runs from the initramfs (D20), and `install_items` puts the two files at that path in the initramfs, which L0 7.11 lists with `lsinitrd`. Not run on the device: whether the DSP then loads that file is the experiment itself.

**Speaker FIRST TEST** (submenu entry 3.5; audio-speakers `2026-10-31-topology-rfc.md` sections 4, 6 and 7). Private mode installs the generated closed-loop topology `X1E80100-Microsoft-Surface-Pro-11-tplg.bin` over the public file of the same name, `...-sp11cl.bin`, and the nominal calibration `...-sp11cal.bin` (made for this entry by `build-closedloop.sh --nominal-cal`), all in `/usr/lib/firmware/qcom/x1e80100/`; the public ISO has none of them (L0 7.12) and keeps the public topology. The nominal file is only honoured by the kernel guard with `sp11.allow_nominal=1`, which is on this entry and nowhere else (the menu checker fails on any other entry, and on the main line); the main line keeps the speakers OFF (`m14`, no speaker UCM). Tools installed everywhere, never run automatically and never units: `/usr/libexec/sp11/speaker-supervisor` (holds the MultiMedia5 capture PCM, index 4, open and started without ever reading it, before any playback) and `/usr/libexec/sp11/speaker-first-test` (refuses outside `sp11.entry=spk` with `sp11.allow_nominal=1`, refuses with `sp11.nospk`, refuses without `/sys/kernel/debug/sp11/guard`; at most 10 tones of 2 s, 180 s of silence between tones, stops at any guard fault latch or refusal; it sets no control, the operator keeps the volume at the minimum and the kernel caps stay). Kill switch: press `e` in GRUB and add `sp11.nospk`, or power off. The entry's own menu text says: minimum volume, tones of at most 2 s, 3 minutes of silence, at most 10 tones, any fault ends the session. **Two ADSP behaviours are unproven**: the cross-graph control link (H3) and the capture graph with an unconnected input (H10). If either fails the guard stays closed and the speakers stay muted; that is a result, not a failure of the image. The guard file format is not verified: the script's latch detection is deliberately crude and stops on doubt. UCM must not start playback by itself (audio-speakers owner).

**Other inputs.** Microphone UCM fix from `hardware/audio-mics/userspace/overlay-ucm-fix/` (Fedora's `x1e80100.conf` with a Surface Pro 11 DMI branch; without it alsa-ucm never finds a profile; L0 8.40 runs `alsaucm` from Fedora against the ISO's own files: list only). Camera blobs `ov13858-mshw0491.bin`, `imx681-mshw0490.bin`, `vd55g0-mshw0492.bin` in `/usr/lib/firmware/updates/`, private only, verified at staging and by L0 with the owner's `verify_blob` and `MANIFEST.json` hashes. Public packages added: `fastrpc`, `fastrpc-services` (with the existing `qrtr`; a dnf test transaction completed; Fedora's `60-fastrpc.rules` already gives the nodes to `root:fastrpc` 0640 and the sysusers file creates the group, so no image rule exists and none is 0666; add a user with `usermod -aG fastrpc`); no QAIRT, no `hexagonrpcd`/`libssc` builds (documented follow-up). Private only: `/usr/libexec/sp11/sp11-npu-install-private` (installs from the operator's own QAIRT download; nothing is shipped) and the 78 staged sensor files (`hardware/sensors/userspace/sp11-sensors-stage.sh`) under `/usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/sensors/`; the two sensor units are not installed because they need the unpackaged `hexagonrpcd`. Power-thermal: the owner overlay (opt-in suspend ladder `sp11.suspend_diag` OFF on every entry, opt-in lid/wakeup policy, default-on s2idle cpuidle guard in the sleep hook that is suspend-only and restores the previous values, opt-in thermal sampler) and its read-only collector (`extra-power-thermal.txt`); no suspend entry exists. Collector additions: image drop-in `rotors.sh` (`extra-rotors.txt`: the three rotors, the environment block, the GPU result, the notices, and the cpufreq finding: `scmi_cpufreq` is absent in the M13 logs, so no cpufreq and no cooling; the collector records the module, devices and dmesg lines, the kernel is not changed), `audio.sh` (UCM verbs, PCM list, speaker guard file, private speaker file names and sizes), the DSP collector refreshed from main (loaded firmware build ids, no hidden AOSS `load_state` lines; `check-charge-writes.py` re-audited and re-pinned).


### M15 menu and Linux-side experiments (prepared 2026-10-31, no ISO built)

**Why.** (Corrected twice by the operator the same day; this is the final M15 design.) The M13 ISO had a FULLY STATIC `grub.cfg` (only the standard `load_video` function; no `load_env`, no `save_env`, no variable, a fixed DTB per entry) and it booted on the device. M14 line 1 (a GRUB function, `load_env`/`save_env` on the ESP `grubenv`, variable DTB and arguments) failed with `EFI_LOAD_ERROR`, even in menu2 where GRUB did not write; the static `safe` entry booted. Operator decision: go back to the M13 style. M15 has NO GRUB function beyond `load_video`, NO grubenv, NO variable, NO submenu. Everything that used GRUB state moved to Linux userspace, with its state in plain files on the boot medium only (S4). The sections "M14 private ISO" and "menu2" above describe the retired design; the M14 ISO is the only one built with it.

**Menu (flat, static, 12 entries; `image/kiwi/overlay/grub-arm.cfg.iso-template`).** Every entry carries the M13 main-entry arguments with the corrected trace string (no `power:power_domain_target`) unless stated; `sp11.entry=<id>` is the only per-entry mark; nothing is variable.

| Line | Title | `sp11.entry` | DTB | Arguments |
|:--|:--|:--|:--|:--|
| 1 | `SP11 debug` | `debug` | `m15` (microphones, rear/front/IR camera nodes ON, GPU/GMU/zap ON = the former m14.dtb) | diagnostics (USB and PDR dyndbg, DSP trace) plus the CONSTANT `sp11.gpu_diag=1` (on this line only) |
| 2 | `SP11 debug, safe (no GPU, no cameras)` | `safe` | `m15-safe` (microphones only, cameras and GPU OFF; the M13/M14-safe content) | same as line 1 without `sp11.gpu_diag`: the always-booting fallback |
| 3 | `SP11 debug, no sound` | `nosnd` | `m15-nosnd` | same |
| 4 | `SP11 debug, touch off` | `notouch` | `m15-notouch` | same |
| 5 | `SP11 debug, speakers (gated)` | `spk` | `m15-spk` (d26 profile only) | same plus `sp11.allow_nominal=1`; the first-test notice and `sleep 3` (static `echo`) |
| 6 | `SP11 debug, USB + DSP trace` | `usbdbg` | `m15-safe` | M13 arguments (`:mod:qcom_glink`, 8M buffer) |
| 7 | `SP11 debug, no early DSP` | `nodsp` | `m15-safe` | `qcom_q6v5_pas` blacklisted |
| 8 | `SP11 debug, Wi-Fi unblock probe` | `wifi-unblock` | `m15-safe` | `sp11.wifi_unblock=1` |
| 9 | `SP11 debug nomodeset` | `nomodeset` | `m15-safe` | `nomodeset` |
| 10 | `SP11 debug, stop in initramfs` | `initramfs` | `m15-safe` | `rd.break=pre-mount` |
| 11 | `SP11 debug, Spectra camera test` | `spectra` | `m15-spectra` (Qualcomm Spectra camera path, 282 inert Qualcomm nodes) | the `safe` arguments plus `module_blacklist=camera_x1e80100` |
| 12 | `VM test (no devicetree)` | `vmtest` | none | `console=ttyAMA0,115200` (L1 only) |

There is no separate GPU entry and no camera entry except the Spectra test. `sp11.gpu_diag=1` appears on line 1 only, as a constant; there is no CDSP, SAM, identity, cpufreq or GPU-DTB argument on any line (L0 2.17 and `check-m8-menu.py` fail otherwise).

**Line 1 may reset the machine; line 2 is the way to a stable session.** Line 1 enables the GPU. The first DRM open loads the zap shader and the GMU and can reset the machine at session start (M5 evidence). Linux userspace cannot prevent that reset: there is no step the image can take before the open that makes it safe. The two-step diagnostic (`sp11-gpu-two-step.service`, enabled, runs only through the owner unit's `ConditionKernelCommandLine=sp11.gpu_diag=1`, ordered before `gdm.service` and `display-manager.service` so GNOME never opens the node first) writes its markers to the boot medium before the risky step and syncs them. On the next boot the hook reports `GPU test: died during step N` or `survived` from those markers, and the operator notice on every line-1 boot starts with the same plain warning: line 1 may reset the machine, boot line 2 for a stable session. The loop guard of the two steps themselves is the owner's: a step that killed the previous boot is skipped. GRUB carries no GPU logic and no state. The VM test is a top-level line again; the QEMU driver navigates by position (10 Down keys). If line 1 fails with `EFI_LOAD_ERROR` again, line 2 has the same kernel, initrd and arguments with only the DTB (and `sp11.gpu_diag`) differing; the DTBs differ in the ten GPU and camera status lines.

**GRUB logic tests are trivial.** `image/tools/grub_logic_test.py` renders the template, runs `grub2-script-check` (local binary, else the build container) and the policy checker, and runs eleven mutants (a function, `load_env`, `save_env`, a variable DTB, a submenu, a GPU DTB, a rotor argument, `firmware_class.path`, `m15` on a second entry, `allow_nominal` elsewhere, `quiet`) that must each be rejected. No QEMU, no ISO. The policy checker also requires `sp11.gpu_diag=1` on line 1 and nowhere else. L0 8.42 runs `grub2-script-check` on the real file; 8.41 requires that the ESP carries no `grubenv`.

**What moved to Linux, and the guards.** The state helper is `/usr/libexec/sp11-boot-state` (replaces `sp11-esp-env`): `get`/`set`/`unset`/`list` on one plain file per value, `sp11/state/NAME`, and `marker NAME` / `markers` for operator marker files `sp11/NAME`. Medium: the `SP11LOGS` partition of the disk the live system booted from, else that disk's ESP (label `BOOT`); a disk with NTFS, BitLocker or a Microsoft reserved partition, or any other disk, is refused (S4); mounted read-only for reads, read-write for one `set`, then synced and unmounted. Test hook `SP11_STATE_ROOT`.

| Experiment | Mechanism | Guards |
|:--|:--|:--|
| SAM shutdown mode rotor | `sp11-sam-mode-rotor.service` (sysinit): mode `silent`, `clean`, `quiet`, `default`, repeat, from `usr/share/sp11/sam-mode-order`; counter `sp11_sam_counter` in `sp11/state/`; writes `/sys/module/surface_aggregator/parameters/shutdown_mode`; operator notice. `silent` is first because the Type Cover keyboard freezes at the start of Windows after a default-mode Linux shutdown (ec-sam evidence `2026-10-31-m13-keyboard.md`) | an explicit `surface_aggregator.shutdown_mode=` on the line wins and the counter does not advance; counter not saved is reported |
| CDSP experiment | `sp11-cdsp-experiment.service` (multi-user, asynchronous): after ADSP running and CDSP stable, one variant per boot. Since kernel sp11.12 `keep_proxy_pds` is a tri-state whose default (-1) keeps the proxy votes for the Surface CDSP, so the variants are: 0 `c1-00078` with keep forced 0, 1 `c1-00046.1` with the default (-1), 2 `c1-00046.1` with keep forced 0, 3 `c1-00078` with the default (what a plain boot does); the parameter is written -1 to select the default and restored afterwards. It stops the `cdsp` remoteproc (found by its `name` attribute), sets `keep_proxy_pds`, the remoteproc `firmware` file and, for the alternate pair, `/sys/module/firmware_class/parameters/path` to `/usr/lib/firmware-sp11-cdsp46` (both the `mbn` and the `cdsp_dtb.mbn` come from that directory), starts it, restores the loader path and the parameter, waits, and records the variant, the remoteproc state and the `sp11-glink` lines (`rx OPEN_ACK`, FIFO) in `/run/sp11/cdsp-experiment` (collector file `extra-rotors.txt`). Counter `sp11_cdsp_counter`, advanced BEFORE the restart. The notice says a FULL power-off (not a reboot) is needed before a boot whose variant uses the alternate firmware, and says what the next boot will do | main entry only (`sp11.entry=debug`); once per boot (`mkdir` lock in `/run`); off with the marker `sp11/disable-cdsp-experiment`; skipped when the ADSP is not running, the CDSP is not `running`/`offline`, or its state changes during a 5 s settle; every wait has a timeout and `stop`/`start` are background writes; a variant that cannot be realised (no alternate pair on a public image, `keep_proxy_pds` read-only) is skipped and the counter moves on |
| cpufreq | `/etc/modules-load.d/sp11-cpufreq.conf` (`scmi_cpufreq`, soc-boot R-I2) loads the driver every boot; `sp11-cpufreq-cap.service` records every policy and applies BY DEFAULT governor `schedutil` and `scaling_max_freq` = the median of `scaling_available_frequencies` per policy; the marker `sp11/cpufreq-uncapped` lifts the cap | never `performance`/`ondemand`; never raises a limit; capped unless the operator creates the marker (S6); the collector prints the table |
| Identity experiment (private ISO) | the wifi and bluetooth workers' collectors and units are installed unchanged (`sp11-wifi-identity`, `sp11-identity-bt`, `sp11-identity-bt-pre.service`, drop-ins `wifi-identity.sh`, `bluetooth-identity.sh`; the refreshed `sp11-bt-address` is the pinned snapshot). The switch `sp11.identity=none` cannot be on the static command line, so the marker `sp11/identity-none` does it: `sp11-identity-switch.service` (before udev trigger, the consumers and NetworkManager) bind-mounts a copy of the command line with ` sp11.identity=none` appended over `/proc/cmdline`; the real line stays in `/run/sp11/cmdline-kernel` | private ISO only (`usr/share/sp11/image-mode`, which private mode now writes together with `identity-ref.sha256`, mode 0600, hashes only); the `.link` has `KernelCommandLine=!sp11.identity=none`; the collectors print MATCH/NO MATCH only, never an address; `/proc/cmdline` shows the appended word on those boots |
| Touch profile | iptsd profile B (Activation 20, Deactivation 16, Neutral average, NeutralValue 10, scoped to 045E:0C80, upstream Surface Laptop Studio 2 values) is the DEFAULT, installed by the image-owned `sp11-touch-conf-select` (the owner's selector read the grubenv) as `iptsd@.service` ExecStartPre; the marker `sp11/touch-conf-A` selects A (iptsd defaults); `sp11-touch-tap-diag` is installed as an on-demand tool and the drop-in `touch-conf.sh` only records the profile; nothing runs the diagnostic automatically | reversible by removing a file |
| GPU two-step | the gpu worker's `sp11-gpu-two-step` with the image hooks, the `Before=gdm` drop-in and `gpu-retry`; ENABLED, active only on line 1 through `sp11.gpu_diag=1`; markers `sp11_gpu_state` in `sp11/state/` through `sp11-boot-state` (S4), no grubenv, no GRUB logic; the reset cannot be prevented from Linux (see above) | never active on `safe` or any other line (no argument); L0 8.37 requires the enable symlink, the owner unit byte for byte and `sp11.gpu_diag=1` on line 1 only |

Kept unchanged from M14: the microphone UCM fix, private-mode firmware (closed-loop topology, camera blobs, sensor staging, NPU installer, alternate CDSP pair), the speaker first-test tooling (manual, entry-gated), the suspend ladder (opt-in, off), the collectors, the thermal collector. `sp11-thermal-sample.service` is enabled by the marker file `sp11/enable-thermal-sample` on the boot medium: the image drop-in `10-sp11-marker.conf` resets the owner's `ConditionKernelCommandLine=sp11.thermal_log` and uses `ExecCondition` on the marker (tsens, cpufreq and battery mode; the SAM/fan mode still needs `sp11.thermal_log=sam` on an edited line). Camera blobs: the regenerated set in `out/firmware-private/cameras/` (Bayer OV13858 BGGR, IMX681 RGGB, VD55G0 mono) passes the owner's `verify_blob` and the manifest hash (checked 2026-10-31); `private-m14.py` verifies again at build and in L0 7.11.

**Tests run without an ISO (2026-10-31).** `image/tools/rotor-selftest.sh image/overlay`: 64 PASS, 0 FAIL (boot-state, SAM order and wrap, CDSP variants and guards and timeouts against a fake kernel, cpufreq default cap and uncapped marker, thermal marker, identity switch, touch selector, GPU hooks including the reset warning); `image/tools/private-stage-selftest.sh`: 29 PASS; `image/tools/grub_logic_test.py`: all PASS with `grub2-script-check` from the container; QEMU driver self-test (`qemu_driver_selftest.sh`, fake QEMU): PASS, 11 titles seen, VM test selected by 10 Down keys; `bash -n` on every script; ShellCheck warnings reviewed (style only). Not run: L0 and L1 (need an ISO).

**Inputs a build needs.** The five kernel-worker DTB/JSON pairs `m15`, `m15-safe`, `m15-nosnd`, `m15-notouch`, `m15-spk` for `7.3.0-65.sp11.12.fc44.aarch64` with `series_rev` 12 in `out/dtb-variants/<kver>/qcom/`; the revision-12 kernel RPMs alone at the top of `out/rpms/` (the release JSON has a `touch_modules` section under `m15` or `m14`, and `new_modules` for L0); the existing `iptsd` RPM, `out/firmware-root`, `out/firmware-private`, and `scripts/image-build.sh --private` for the operator ISO. L0 3.13 calls `scripts/kernel-m8-check.py --variant m15*`, which needs the kernel worker's `--variant` choices (request below).

### M15 private ISO and integration of the finished pieces (2026-10-31)

Nothing here changes the static menu logic. Pins: `image/component-inputs/m15-integration.json` (L0 8.44), `m15.json` (UCM fix re-pinned).

| Piece | What the image carries | Private-only part |
|:--|:--|:--|
| Sensors | local RPMs `hexagonrpcd` 0.5.0, `libssc` 0.4.4, `libssc-tools`, `iio-sensor-proxy` 3.9 (SSC) and `sp11-sensors` from `out/rpms-local` through the local repository; the units are enabled by the package preset and by explicit symlinks; the ADSP node rule is `fastrpc` 0660 (no 0666); `adsprpcd*` is not masked | `sp11-sensors-install-private.sh --stage out/firmware-private/sensors --registry seed`: 70 config files, 6 identity files, `sns_reg.conf`, the `registry` symlink and the 293-file seed in `/var/lib/hexagonrpcd/registry`, all checked against the stage `SHA256SUMS` |
| Audio | `overlay-ucm-fix` (re-pinned) and `overlay-audio-routes` (DisplayPort HDMI0/HDMI1, SP11-Audio, capture gain step 98 = +14 dB capped at 108, WirePlumber priorities, dconf, collector); packages `alsa-ucm-utils`, `ladspa-swh-plugins` (Fedora's name for the swh plugins), `webrtc-audio-processing`; the speaker entry stays the first-test policy | `sp11q.bin` and `sp11q-dyn.bin` next to `sp11cl`; the microphone PipeWire configs in `/etc/pipewire/pipewire.conf.d/` (a PipeWire start with them loaded in the Fedora 44 container logged no module error); the speaker EQ is stored UNLOADED in `/usr/share/sp11/pipewire-gated/`; `sp11q-spk.bin` (GATED) is not installed (no owner README releases it, and the kernel has no loader for any `sp11q` file yet, so the installed files are inert) |
| Cameras | libcamera: local build of Fedora's 0.7.2 source package with `libcamera-sp11.patch` and `libcamera-sp11-imx681-helper.patch` (`scripts/image-build-libcamera.sh`, release `2.sp11`, built and installed); the owner collectors `cameras.sh` and `spectra.sh`; `sp11-camera-spectra` rebuilt against the M15 kernel-devel (L0 checks vermagic) | camera blobs (owner's `verify_blob` and manifest), tuning YAMLs under `/usr/share/libcamera/ipa/simple/` (hash against `libcamera-tuning.manifest.json`), `CAMERA_ICP.mbn` (both pins) with its licence under `/usr/share/licenses/sp11-camera-icp/` |
| Spectra entry | `sp11-spectra-load.service` and `/usr/libexec/sp11/spectra-load` (entry `spectra` plus the DT node `qcom,cam-cpas*`, marker `sp11/spectra-load` on the boot medium); output `/run/sp11/spectra-load`, notice `30-spectra` | none |
| Volume buttons | `/usr/libexec/sp11/ec-sam/collect-volume-buttons.sh`, on demand, never run by a unit | none |

**Known contradiction of the Spectra entry.** The entry carries `module_blacklist=camera_x1e80100` as specified. The kernel refuses every load of a module named there (`kernel/module/main.c:3405`, `early_mod_check`; the parameter is a core param with mode 0400), also an explicit `modprobe`. So with the argument on the line the marker cannot cause a load: the service records that and tells the operator to press `e`, delete the argument for that boot and keep the marker. Switching the argument to `modprobe.blacklist=camera_x1e80100` (which only stops udev autoloads) would make the marker work unedited; the menu check and L0 pin the current text.

**Public builds** carry none of the private material (camera blobs, tuning YAMLs, sensor registry and configuration, audio quality files and PipeWire configs, closed-loop topology files, `CAMERA_ICP.mbn`, the alternate CDSP pair, identity files); L0 7.12 asserts absence, L0 7.11 asserts presence and hash equality in private mode.


## Private build mode (operator device only)

`scripts/image-build.sh --private` (or `SP11_PRIVATE=1`) builds an ISO for the operator's own Surface Pro 11 with device identities embedded, avoiding the post-write address provisioning of the M6 procedure. This does not establish radio functionality; the M10 board crash requires the I9 fallback below. Kiwi builder only. The default build stays public: no address, no derived blob, L0 checks 7.5 unchanged.

**Threat model.** A private ISO contains this device's Wi-Fi and Bluetooth addresses, and Windows-derived Wi-Fi board data only after explicit opt-in and successful structural verification. It must not be shared, uploaded, attached to a ticket or used on another device. Values stay out of git, logs, the JSON build record and every README; those hold only "present", SHA-256 prefixes (8 hex digits for an address) and the board file hash. The values exist only in the staging tree (removed after the build, also on failure), in the ISO root file system, and in the L0 work directory `out/image-work/l0-<name>/root`, which the operator deletes with the ISO. The ISO name carries `-private`, the record has a `private` object and `distribution: forbidden`.

| Input | Default | Override |
|:--|:--|:--|
| Addresses `WIFI_MAC`, `BT_MAC` | `~/sp11-windows-dumps/live-inventory/sp11-mac.conf` (git-ignored; also `sources/windows/live-inventory/sp11-mac.conf`) | `SP11_MAC_CONF` |
| Derived board file (Wi-Fi I9, supersedes F2/I7 default) | omitted; Fedora generic | explicit `SP11_WIFI_BOARD2`, optional pin `SP11_WIFI_BOARD2_SHA256` |
| Fedora reference for optional board verification | `out/image-inputs/wifi/fedora-board-2.bin.xz` | `SP11_WIFI_FEDORA_BOARD2` |

The host side of `image-build.sh` runs `image/tools/private-stage.py stage` (the container cannot see the dumps). It validates the addresses (six bytes, not a sentinel, unicast) and fails closed on invalid addresses. Without an explicit board input it warns and leaves Fedora firmware in place. An explicit board must pass `wifi-board2.py verify --fedora <reference> --sha256 <Windows payload hash>` as well as magic and optional hash checks; a missing/invalid/unverifiable board warns and is omitted without failing the build. It stages these files, handed to the kiwi root overlay and chowned to root:

| Image path | Mode | Content |
|:--|:--|:--|
| `/etc/sp11/bt-address` | 0600 | one upper-case colon address and a newline; the format `/usr/libexec/sp11-bt-address` reads, so the controller is configured without the boot-ESP file |
| `/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf` | 0600 | `wifi.cloned-mac-address=` for `driver:ath12k*`, `wifi.scan-rand-mac-address=no` |
| `/etc/systemd/network/10-sp11-wifi.link` | 0600 | `[Match] Driver=ath12k* Type=wlan`, `MACAddress=`; persistent from the first udev event (Fedora-native replacement of the reference's `sp11-mac-fixup` udev rules, D12) |
| `/usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin` | 0644 | optional, verified opt-in derived board file; the kernel firmware loader searches `updates/` first, so it wins over Fedora's packaged `board-2.bin.xz`, which stays intact (the Fedora path itself must hold no override) |

L0 for a private ISO (`scripts/image-test-static.sh`, which mounts the address file read-only for this check only): 7.6 name has `-private`; 7.7 the artefacts exist with these modes, formats and root ownership, values equal the source file and the board override is absent or matches its structurally verified record (all by hash, nothing printed), the record holds hashes only; 7.8 no value in the JSON record, ISO boot tree or embedded ESP; 7.9 no value in the repository; 7.10 none in the L0 report. Public ISOs skip 7.6-7.10 and keep 7.5 (no address input in root, boot tree or ESP). Selftests: `image/tools/private-stage-selftest.sh` (stage, verify, leak and refusal cases, public default retained).

Rollback: rebuild without `--private`. Q3 of the wifi dossier (is the OTP address the factory one) is not decided by this mode; it only makes the userspace address persistent.

## Requests

- kernel (M15): (1) `scripts/kernel-m8-check.py` must accept `--variant m15 m15-safe m15-nosnd m15-notouch m15-spk` (L0 3.13 passes them; m15 = camera nodes and GPU/GMU/zap ON, m15-safe = microphones only; L0 3.12 requires the GPU node `okay` in m15 only) and the release JSON should keep `touch_modules` and `new_modules` under the key `m15`; (2) make the `qcom_q6v5_pas` parameter `keep_proxy_pds` writable at runtime (`0644`, dsp-subsystems patch 0003 has `0444`): the CDSP experiment sets it between `stop` and `start`, and without it variants 2 and 3 are skipped; (3) per-mode camera bus codes (patches 0002/0013) are in the kernel brief, nothing for the image.
- soc-boot (M15, R-I2): done (`modules-load.d/sp11-cpufreq.conf`, collector, L0 8.37). Following the operator correction the cap applies by default (S6) and the marker `sp11/cpufreq-uncapped` lifts it.
- touch-pen / wifi / bluetooth (M15): the image installs your files unchanged except the touch selector (image-owned `usr/libexec/sp11-touch-conf-select`, marker `sp11/touch-conf-A` instead of the grubenv variable); the identity switch is the marker `sp11/identity-none` through a bind mount of `/proc/cmdline`, because the command line is static.
- orchestrator/operator (M14): review and commit the uncommitted image work. Bench procedure on the ONE line you boot (`SP11 debug`): read the operator notice at the first desktop (SAM shutdown mode, CDSP variant and what the next boot loads, GPU test result of the previous boot); power off with `systemctl poweroff`; when the notice says the next boot loads the ALTERNATE firmware, shut down completely and wait 10 s before powering on (not a reboot). If a boot died during the GPU test, the next boot of the same line uses `m14-safe` by itself and says so (`GPU test: died during step N`); `/usr/libexec/sp11/gpu-retry` re-arms the test. The speaker first test is submenu entry `SP11 debug, speakers (gated)` only, after the V/I stream is confirmed (audio-speakers evidence section 8); `sp11-speaker-first-test --dry-run` first. Never boot the speaker entry from the main line.
- gpu owner (M14): `collector/gpu-two-step.sh` still lists only the labels `SP11LOGS` and `ANACONDA`; the image applies three changes (label `BOOT`, the hooks of `image/component-inputs/gpu-state-hooks.sh`, four calls) and pins them. Please adopt the label and hook calls or tell the image owner which hook names to expect. The collector now runs on every boot of the main line, about 40 s of sampling before GDM.
- audio-speakers owner (M14): the shared overlay still ships the dead link `conf.d/x1e80100/X1E80100-Microsoft-Surface-Pro-11.conf` (never probed, audio-mics request); the image adds the UCM fix on top. The guard file format under `/sys/kernel/debug/sp11/guard` is not documented: `speaker-first-test` stops on any text containing a latch or fault word, please state the format. UCM must not start playback by itself.
- kernel (M14): `scmi_cpufreq` is absent in the M13 logs (no cpufreq, no cooling); the new `extra-rotors.txt` records it. Please confirm `CONFIG_ARM_SCMI_CPUFREQ` and the SCMI protocol devices in the next build (no change made here).
- dsp-subsystems (M14): the early-PAS path is checked only up to the initramfs content and the loader source; whether the DSP loads the alternate pair from `firmware_class.path` is the experiment. Variant order and the `CDSP variant for this boot:` line are as requested.
- ec-sam / power-thermal (M14): the SAM rotor order is silent, clean, quiet, default (newest evidence; the brief had two orders). `sp11.suspend_diag` is OFF on every entry (no suspend entry exists; add it by editing the line in GRUB).
- sensors / npu (M14): public set `fastrpc fastrpc-services qrtr` installed; private mode installs the NPU installer and the staged sensor files only. `hexagonrpcd`, `libssc` and the two sensor units are NOT in this image (not trivially packageable): follow-up for a local RPM.

- orchestrator/operator (M11): review and commit the uncommitted image work after L0/L1 validation. The next already-planned boot can compare default `debug`, `touch off` and `microphones`; keep speakers/GPU off. Keyboard recovery remains an untested hypothesis: the first reboot test runs with no mitigation (baseline); the shutdown unbind needs `sp11.ssam_shutdown` and a boot rebind needs `sp11.ssam_rebind`, both added manually in GRUB (the rebind is known broken on DT until the platform-hub leak is fixed). No separate reboot is requested here. Exact read-only collectors for that planned boot:

  ```bash
  sudo bash -c '. /etc/sp11-log-collector.d/ec-sam.sh'
  sudo /usr/libexec/sp11/ec-sam/collect-input-capabilities.sh
  sudo /usr/libexec/sp11/ec-sam/collect-power.sh
  sudo bash -c '. /etc/sp11-log-collector.d/wifi.sh'
  sudo /usr/libexec/sp11-bt-collect
  sudo /usr/libexec/sp11-log-collector once
  ```

  These outputs can contain private device data; keep them under `out/device-logs/` and send owners sanitized conclusions. Device microphone capture and warm-reboot behavior remain owner test-plan gates.


- sources/orchestrator (M8 prerequisite): fulfilled by main `3cd9c9f`. The native RPM consumes the `[iptsd]` table from `sources/sources.toml`; archive/spec hashes and the upstream commit match. The earlier `image/iptsd/source-pin-request.patch` is historical and must not be applied again.

- orchestrator (S5, private mode): fulfilled by D25 and the operator-authorized exception now in `plan/risks.md`. Wi-Fi I9 supersedes the derived board default; private identities remain allowed only for the operator device. Nothing in `plan/` was edited by image.

- orchestrator/operator (M8): review and commit the uncommitted image work after validation. Provision `BOOT:/EFI/sp11/bt-address` only after DD-writing, as documented above. The next already-planned GPU-off/speakers-off boot can use the touch-on default, with `SP11 debug, touch off` as the fallback. No additional reboot is requested solely for evidence. Automatic full snapshots include touch, iptsd and input names. Exact read-only manual collectors, if needed:

  ```bash
  sudo bash /usr/libexec/sp11-touch-pen-collect
  sudo /usr/libexec/sp11-touch-userspace-collect journal
  sudo /usr/libexec/sp11-touch-userspace-collect devices
  sudo /usr/libexec/sp11-bt-collect
  sudo /usr/libexec/sp11/ec-sam/collect-input-capabilities.sh
  sudo /usr/libexec/sp11/ec-sam/collect-power.sh
  ```

  For ec-sam R3 during an already-planned initramfs boot, confirm the attached keyboard can type this read-only command and then use `exit` to continue:

  ```bash
  awk '$1 ~ /^(surface_aggregator|surface_aggregator_registry|surface_aggregator_hub|surface_hid|surface_hid_core|hid|hid_generic)$/ {print $1, "refs=" $3}' /proc/modules
  ```

  Built-in modules are absent from `/proc/modules`; L0 checks their built-in equivalents. Keep full journals and all device identifiers outside git. Functional touch/metadata/orientation, keyboard, Bluetooth and radio/power behavior remain device gates.

- installer path (R9, future): the installed system must boot `grubaa64.efi` directly. Anaconda installs shim and points the UEFI boot entry at it, and this firmware does not run shim. The installer step (kickstart `%post` of the installed system, or an Anaconda addon / `efibootmgr` call after install) must (a) create the boot entry for `\\EFI\\fedora\\grubaa64.efi` with `efibootmgr -c -d <disk> -p <esp partition> -L Fedora -l '\\EFI\\fedora\\grubaa64.efi'`, and (b) copy `grubaa64.efi` to `EFI/BOOT/BOOTAA64.EFI` on the installed ESP, for firmware that only reads the fallback path. Both must leave `EFI/fedora/shimaa64.efi` in place. Not implemented: this image has no installer step yet; verify on the device (R9).
- kernel: install `x1p64100-microsoft-denali.dtb` under `/lib/modules/<kver>/dtb/qcom/` in `kernel-core`; build `kernel-modules-core`/`kernel-modules` with `CONFIG_SQUASHFS_ZSTD=y`, `CONFIG_VFAT_FS=m` (or `y`; the collector mounts the FAT log partition), `CONFIG_USB_STORAGE`, `CONFIG_VIRTIO_GPU`, xHCI and virtio drivers for the L1 `VM test` entry (the Fedora config has them; keep them).
- kernel (Wi-Fi K2): addressed by M7 revision 4; L0 checks `CONFIG_ATH12K_DEBUG=y` and the shipped debug output functions/format as well as `debug_mask=0x30`. Keep future DTB/JSON publication atomic.
- firmware: none open; request 1-4 are done (see "Kickstart origin" and "Initramfs and firmware").
- orchestrator: dossiers of `dsp-subsystems` (pd-mapper, qrtr) and `gpu` can cite this file for the answers above.

## Log

- 2026-10-31: menu2. GRUB never writes (no `save_env`), only reads the environment block; GPU state and CDSP rotor transitions moved to Linux; two static bisect entries first in the submenu; patched test ISO `...private-menu2.iso` from the menu1 ISO without a kiwi rebuild (`image/tools/make-menu2-iso.sh`); L0 247/247.
- 2026-10-31: built the M14 private ISO `sp11-fedora44-aarch64-kiwi-20261031T133710Z-private` (kiwi 1895 s, SHA-256 `56b0ead2...`): revision-11 kernel, five M14 DTBs, a two-line menu (main entry `SP11 debug` plus one submenu), GRUB environment block on the ESP with GPU self-healing (`testing`/`failed` to `m14-safe`), CDSP experiment rotor (four combinations, alternate firmware pair private and in the initramfs), SAM shutdown mode rotor (silent, clean, quiet, default), operator notices (journal, motd, desktop), speaker first-test entry and tools with the private closed-loop topology, camera blobs, sensor staging and NPU installer (private), microphone UCM fix, power-thermal overlay and collector, FastRPC packages. L0 245/245, QEMU L1 21/21, GRUB logic on the real ISO 25/25. No git writes; nothing left running.
- 2026-10-31: built the M13 private ISO `sp11-fedora44-aarch64-kiwi-20261030T234013Z-private` (kiwi 1761 s, SHA-256 `0020e384...`): revision-10 kernel, six M13 DTBs, sixteen-entry menu (default m13 with USB dynamic debug and the corrected DSP trace; CDSP keep-proxy-votes, three SAM shutdown modes, gated speakers with an entry-switched UCM overlay, rear camera, GPU diagnostic last), new collectors (SAM shutdown mode, cameras, audio, USB-C R-I1, GPU two-step), libcamera from Fedora, upower collector error fixed. L0 250/250. No git writes; nothing left running.
- 2026-10-30: built the M10 private ISO `sp11-fedora44-aarch64-kiwi-m10-private-20261030T084338Z` (kiwi 1927 s, SHA-256 `96825b56...`): revision-7 kernel with the `sp11-glink:` diagnostic, `m10`/`m10-notouch` DTBs, DSP collector with sp11-glink and remoteproc capture. L0 203/203, QEMU `--until-session --decoy` 21/21. No git writes; nothing left running.
- 2026-10-30: built the M9 private ISO `sp11-fedora44-aarch64-kiwi-m9-private-20261030T034021Z` (kiwi 1664 s, SHA-256 `aef67909...`): revision-6 kernel, `m9`/`m9-notouch` DTBs, DSP trace arguments in the default entry, refreshed Bluetooth/DSP/Wi-Fi/USB-C collectors, device addresses and derived board file embedded. L0 202/202, QEMU `--until-session --decoy` 21/21. Disk: removed superseded M6/M7 ISOs, work directories and sp11.3/sp11.4 RPM archives. No git writes; nothing left running.
- 2026-10-29: prepared M8 revision-5 release/DTB gates, touch-on default and touch-off fallback, early fixed/QSPI/HID/uinput modules, native iptsd spec/build path and masked userspace captures. Compiled DTB/menu/privacy/QEMU-driver preflight and index/syntax/whitespace checks pass. Fresh official Fedora query still finds no iptsd. Blocked before RPM/source consumption and the single ISO compose because the required central iptsd source pin is absent; exact source-owner patch recorded under Requests. No ISO/L0/L1 result claimed, no git writes, and no task process left running. Resume with the pin, native RPM, one compose, L0 and QEMU session/ESP/decoy checks.

- 2026-10-29: built one M7 ISO (`sp11-fedora44-aarch64-kiwi-m7-20261029T090813Z`, kiwi 1576 s): revision-4 kernel, published m7/m7-touchdiag DTBs and exact touch collector; M6 policy/helpers retained. L0 176/176; final QEMU `--until-session --decoy` 19/19 in 1900 s to captures, clean ESP and unchanged decoy. Preserved the first run's STATUS-metadata false failure; added physical capture-target verification and GPT/FAT regression fixtures, then reran the same ISO successfully. No device test, git writes or task process left running; orchestrator review/commit and planned touchdiag evidence are next.

- 2026-10-29: completed the M6 replacement from a fresh kiwi compose: all DRM state reads refused, explicit D23 initramfs policy and every-device-entry blacklists, pinned main Bluetooth/ec-sam payloads, operator-only post-DD address provisioning. ISO `sp11-fedora44-aarch64-kiwi-m6-20261028T233509Z`: L0 161/161, QEMU `--until-session --decoy` 18/18 (menu, VM boot/GDM, sessions, clean ESP, unchanged decoy), Bluetooth mocks 14/14. Invalid earlier ISO retained; all work uncommitted and no task process left running.

- 2026-10-28: Codex continued image under D24; prepared M6 collector requests, DP test-read regression, D23 battery enforcement, combined diagnostics and opt-in Wi-Fi probe; build and QEMU pending the kernel worker DTB.

- 2026-10-24: container, kickstart, lorax templates, collector, `image-build.sh`, L0 and L1 scripts written. L0 passes on a toy ISO; L1 driver verified against a fake QEMU; no ISO build and no QEMU run because the kernel build held `out/.kernel-build.lock`.
- 2026-10-24 (later): M2 ISO built (SHA-256 above), L0 76/76, L1 reaches GDM with the collector complete, fails only on four TCG start timeouts. Six defects fixed (list in "M2 ISO").
- 2026-10-25: D16. kiwi builds the ISO from Fedora's `f44` Workstation-Live description (pin `dfc49a5`) plus the SP11 layer; L0 80/80; L1 reaches GDM and a complete collector log, fails on six unit start failures (five TCG timeouts, one `NetworkManager-wait-online` exit code). `image-build.sh` uses kiwi by default; lmc kept. Privacy scan 7.4 (`rpm -Va`) added.
- 2026-10-25: D17. kiwi ISO rebuilt with a 64 MiB FAT32 ESP (xorriso replay, 129022 clusters), L0 83/83 (new checks 1.5-1.7), GRUB menu and kernel start seen in QEMU (5 min, no `file not found`); full L1 not rerun.
- 2026-10-25: D18. ESP step makes `BOOTAA64.EFI` Fedora's GRUB, shim kept as `shimaa64.efi`, `bootx64.efi` removed, marker line first; L0 87/87 (new checks 2.13-2.16); QEMU shows the marker, the menu and the kernel start (4 min run, no full L1).
- 2026-10-25: D19/M3. ISO `sp11-fedora44-aarch64-kiwi-20261025T160856Z` (SHA-256 `2a7f7fc1...`): 8-entry menu, three DTBs, early display snapshot and the display evidence files, `collect-dpcd.py` in the image, 64 MiB FAT32 ESP with direct GRUB. L0 103/103; L1 `--esp-fallback` PASS (collector writes `/EFI/sp11-logs` on the `BOOT` ESP). Build refuses kernels not newer than 7.3.0-65.sp11 and more than one kernel NEVRA at the top of `out/rpms`.
- 2026-10-25: D20/M4 and S4. ISO `sp11-fedora44-aarch64-kiwi-20261025T183834Z` (SHA-256 `0325c6f4...`): seven-entry menu with the parity DTB as default, `leds-qcom-lpg` and the DSP remoteproc set with the four DSP images in the initramfs, failure capture to the ESP, collector and hook write only to the boot medium and refuse Windows disks. L0 131/131; L1 `--esp-fallback --decoy` and `--initrd-fail --decoy` PASS, fake Windows disk byte-identical.
- 2026-10-26: D21/M5 and S1. ISO `sp11-fedora44-aarch64-kiwi-20261026T192029Z` (SHA-256 `a106d5e1...`): six-entry menu with the sound-off DTBs `m5` and `m5gpu`; L0 2.18 fails if any device entry's DTB enables the speakers; the collector mounts the ESP per write, reads the GPU speed-bin cell only, records sound and GPU state, snapshots at the first logind session. L0 148/148, L1 `--until-session --decoy` and `--initrd-fail --decoy` PASS.
- 2026-10-29: private build mode (`--private`): host-side staging of bt-address, Wi-Fi address (NetworkManager conf and .link) and the derived ath12k board file; private L0 checks 7.6-7.10; selftest `image/tools/private-stage-selftest.sh`. Not built: kernel M9/M10 pending and disk headroom below the guard. Not committed.
- 2026-10-31: M15 prepared (no ISO): flat static 11-entry menu (M13 style, no GRUB function but `load_video`, no grubenv, no variable), line 1 `m15` with cameras and GPU and the constant `sp11.gpu_diag=1`, line 2 `m15-safe` fallback; SAM rotor, CDSP experiment, cpufreq cap, identity switch and touch profile moved to Linux with plain-file state on the boot medium (`sp11-boot-state`); GPU two-step enabled on line 1 only (plain-file markers, reset cannot be prevented), cpufreq cap by default, thermal sampler by marker; L0 menu checks, QEMU driver and GRUB logic test rewritten; rotor self-test 64/64, private-stage self-test 29/29.
