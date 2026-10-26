# Decisions

Append-only. Each entry: number, date, decision, reason, consequence. A later entry may supersede an earlier one; the earlier one is never edited.

## D1 (2026-10-23): kernel base is vanilla Linux 7.3

- **Decision:** build from `github.com/juniorverli/sp11-linux` tag `v7.3`, commit `c03c1a14507dfaf8b856c2608f9ac216021fc222`. Our changes are a patch series on top.
- **Reason:** the operator chose 7.3. It already has the Denali DTS (`x1p64100-microsoft-denali.dts`), the Adreno X1-85 and the X1E display catalogue.
- **Consequence:** we do not use a distribution kernel source package. Fedora packaging is done by the kernel worker (D3).

## D2 (2026-10-23): BTF is always on

- **Decision:** every kernel build sets `CONFIG_DEBUG_INFO_BTF=y` and `CONFIG_DEBUG_INFO_BTF_MODULES=y`.
- **Reason:** operator requirement. Also needed by BPF tooling and by Fedora userspace that expects `/sys/kernel/btf/vmlinux`.
- **Consequence:** the build needs `pahole` (dwarves), which this host lacks, so builds run in a Fedora 44 container. Memory peak limits us to one build at a time.

## D3 (2026-10-23): packaging approach is open

- **Decision:** pending. Options for the kernel worker to evaluate: (a) `make binrpm-pkg` with the Fedora 44 config as base; (b) Fedora's `kernel.spec` fed with our tarball and patches.
- **Reason:** (a) is simple; (b) gives Fedora-native subpackages (`kernel-core`, `kernel-modules`, `kernel-devel`) that Anaconda and `dnf` expect.
- **Consequence:** M1 is not done until this is decided.

## D4 (2026-10-23): ISO builder is open

- **Decision:** pending. Options for the image worker: Kiwi (what Fedora uses for its own live media) or `livemedia-creator`.
- **Consequence:** M2 is not done until this is decided.

## D5 (2026-10-23): component-centred repository with one writer per folder

- **Decision:** layout in `README.md`, ownership in `agents/protocol.md` §3, git worktrees per worker for both the project and the kernel (§4).
- **Reason:** workers run in parallel on the same inputs. Disjoint write sets make merges conflict-free; generated aggregates remove the shared hand-edited table.

## D6 (2026-10-23): the local DriverStore is the reference input

- **Decision:** `~/sp11-windows-dumps/DriverStore` is accepted as original. See `sources/README.md` §2.
- **Reason:** all 243 catalogs are signed by "Microsoft Windows Hardware Compatibility Publisher" and all 778 listed files match their catalog hashes.
- **Consequence:** fetching the official Surface MSI is optional, used only to check that versions are current (sources worker).

## D7 (2026-10-24): boot media format

- **Decision:** pending, recommendation in `image/README.md` ("Media format"): a hybrid ISO written in DD mode only; logs to a `SP11LOGS` FAT partition, fallback to the embedded EFI partition.
- **Reason:** Fedora's live boot depends on the volume label and on its own GRUB configuration, which carries the `devicetree` line; file-copy writers and ISO chain-loaders break one or both.
- **Consequence:** the operator instructions for every test ISO say "DD mode"; Ventoy and Rufus ISO mode are unsupported.

## D8 (2026-10-24): two runtimes and cross-checks

- **Decision:** workers run on Claude Code (Sonnet 5.5, effort high) or Codex (Sol 6.1 `gpt-6.1-sol`, effort xhigh); assignment in `agents/README.md`. Values that reach a patch, a DT property or a safety decision are reproduced by an independent cross-check on the other runtime (`agents/protocol.md` §5.1).
- **Reason:** two independent reads of the same pinned sources catch hallucinated or misread values before they reach hardware.

## D9 (2026-10-24): GRUB 2, always verbose

- **Decision:** the bootloader is GRUB 2. Every entry of every test ISO boots verbose: no `quiet`, no `rhgb`, no Plymouth; `debug loglevel=8 ignore_loglevel`; GRUB menu always shown. Details in `image/README.md` ("GRUB 2 and the kernel command line").
- **Reason:** operator requirement; on a machine whose panel may go dark, the on-screen log is often the only evidence.
- **Consequence:** Secure Boot is off for test boots (unsigned kernel; GRUB lockdown blocks `devicetree`).

## D10 (2026-10-24): test levels before the device

- **Decision:** every ISO passes L0 (static checks) and L1 (QEMU TCG boot in the container) before it goes to the Surface; L2 (Hyper-V Gen2 ARM64 VM) when the operator approves; L3 is the device. Specification in `image/README.md` "Test levels".
- **Reason:** WSL2 has no `/dev/kvm`, so QEMU is emulated and slow but available; Hyper-V is installed on this Windows and gives native speed; the device boot cycle is the most expensive step and should only fail for SP11-specific reasons.
- **Consequence:** a non-default `VM test (no devicetree)` boot entry exists in every ISO.

## D11 (2026-10-24): ISO builder is livemedia-creator (supersedes D4)

- **Decision:** the ISO is built with `livemedia-creator` (lorax) from a kickstart, operator's choice.
- **Consequence:** WSL2 has no `/dev/kvm`, so the default mode (Anaconda inside a virt-install VM) cannot run. The build uses `livemedia-creator --no-virt --make-iso`, with Anaconda installing into a directory inside a privileged Fedora 44 container (loop devices and `--privileged` needed). The lorax templates must be adapted for: GRUB 2 entries of D9, the `devicetree` line, the `VM test (no devicetree)` entry of D10, and the embedded EFI image.

## D12 (2026-10-24): Fedora-native first

- **Decision:** whenever Fedora has a tool, package, format or convention for something, we use it instead of an alternative. Examples: `registry.fedoraproject.org/fedora:44` containers; `dnf`; `rpmbuild`/`mock`; Fedora's `kernel.spec`; `dracut`; Fedora `grub2-efi-aa64`; `lorax`/`livemedia-creator`; Fedora `linux-firmware`, Mesa, PipeWire and WirePlumber packages; Anaconda kickstarts; `kernel-install` and BLS entries for the installed system. A non-Fedora tool is allowed only where Fedora has none, with the reason written in the dossier or decision that introduces it.
- **Reason:** operator requirement; the result must behave like a Fedora system, update with `dnf` and be supportable by Fedora tooling.

## D13 (2026-10-24): kernel packaging is Fedora's kernel.spec (resolves D3)

- **Decision:** the kernel RPMs are built with Fedora's `kernel.spec`, in its vanilla mode (no Red Hat patch, `--with vanilla`), on the `v7.3` source of D1, with our series applied as spec patches and our Kconfig fragment merged into the Fedora aarch64 config. Built with `rpmbuild` (or `mock`) in the Fedora 44 container.
- **Reason:** D12. Gives `kernel-core`, `kernel-modules*`, `kernel-devel` and the Fedora install scripts (`kernel-install`, BLS, `dracut`) that Anaconda and `dnf` expect, while keeping the base vanilla.
- **To verify by the kernel worker:** the exact name and behaviour of the vanilla switch in the current Fedora `kernel.spec`, and which Fedora branch's spec builds a 7.3 tarball (Fedora 44 may not ship 7.3 yet).

## D14 (2026-10-24): fast kernel rebuilds

- **Decision:** the kernel build uses Fedora's `ccache` with a persistent cache in `out/ccache`; development iterations use incremental builds in the worker's kernel worktree (`scripts/kernel-dev.sh`): DT-only changes rebuild just the DTB, module changes just the module. Full RPMs are built only for ISOs that go to the device. A DT-only change can be tested by replacing the DTB in an existing ISO, since GRUB loads it as a file.
- **Reason:** `rpmbuild` re-extracts and recompiles the whole Fedora-config kernel every time; a one-line patch cost the same hours as the first build.

## D15 (2026-10-24): accepted deviations in test ISOs

- **Decision (operator accepted):**
  1. Test ISOs run SELinux `permissive`, not `enforcing`: labels written by a container build on WSL2 (no SELinux in that kernel) cannot be trusted, and `enforcing` with wrong labels would produce false failures. Denials are still logged and are collected as evidence. The final system returns to `enforcing`.
  2. Every GRUB entry carries `sp11.entry=<id>` so the L1 test and the log collector know from `/proc/cmdline` which entry booted. The kernel ignores it.
  3. Only the `VM test (no devicetree)` entry carries `console=ttyAMA0,115200`, the QEMU serial port the L1 test reads. Device entries never carry it.
- **Consequence:** the log collector should also capture SELinux AVC denials (`ausearch -m avc` or the journal) so label problems are visible before switching to `enforcing`.

## D16 (2026-10-24): ISO builder is kiwi with Fedora's f44 description (supersedes the builder part of D11)

- **Decision (operator):** from the first ISO after M2, the ISO is built with `kiwi-ng`, starting from Fedora's own Workstation live description: `pagure.io/fedora-kiwi-descriptions`, branch `f44`, pinned by commit. Our changes are limited to the following, each marked and documented:
  - kernel RPMs from `out/rpms`, with Fedora's kernel excluded;
  - DriverStore firmware from `out/firmware-root`;
  - GRUB 2 entries of D9/D10, including `devicetree` and the VM test entry;
  - verbose boot;
  - the log collector and `SP11LOGS` fallback space of D7;
  - D15 deviations;
  - extra test packages.
- **Reason:** D12. Fedora 44 live media are built with kiwi, and Fedora no longer publishes or maintains live kickstarts. The livemedia-creator kickstart is a flattened f43 file that drifts with every update. With the official f44 description, a difference from the official ISO is ours and is visible.
- **Consequence:** the M2 ISO (livemedia-creator) still goes to the device as is; the device logs do not depend on the builder. The image worker ports the lorax template changes to kiwi. L0 and L1 must pass on the kiwi ISO with the same checks, adapted only where the live layout legitimately differs, and each adaptation is documented. The livemedia-creator path is kept until the kiwi ISO passes L0 and L1, then removed. D11's container constraints still apply: WSL2 has no KVM, so kiwi runs in the privileged Fedora 44 container.

## D17 (2026-10-25): the stick's EFI partition is FAT32

- **Decision:** the EFI system partition of every ISO is FAT32, verified by cluster count ≥ 65525, not only by the "FAT32" label. Size is at least 64 MiB, created with `mkfs.fat -F 32 -s 1 -S 512`. L0 fails when the ESP is FAT12 or FAT16.
- **Reason:** the operator reports, and the previous project hit the same problem on 2026-10-18, that the Surface UEFI does not boot a USB EFI partition unless it is FAT32. It returns to the boot menu or Windows before GRUB. kiwi's ISO (30 MiB, 15321 clusters) and the lorax M2 ISO (27 MiB, 14011 clusters) were both FAT16, and both reached GRUB in QEMU, so L1 cannot catch this.
- **Evidence:** `out/iso/sp11-fedora44-aarch64-kiwi-20261025T001028Z-fat32esp.iso`. It repacks the kiwi ISO with a 64 MiB FAT32 ESP (129022 clusters) and changes nothing else; the El Torito UEFI entry points to the new partition. It reaches the GRUB menu in QEMU. Device result pending.

## D18 (2026-10-25): the stick boots Fedora's GRUB directly, without shim

- **Decision:** on the stick's ESP, `EFI/BOOT/BOOTAA64.EFI` is Fedora's `grubaa64.efi` from `grub2-efi-aa64`, not `shimaa64.efi`. The stub `grub.cfg` first prints `SP11: GRUB started (direct EFI boot, no shim)`. Shim stays on the ESP as `shimaa64.efi`, unused. L0 checks that `BOOTAA64.EFI` is byte-identical to `grubaa64.efi`.
- **Reason (operator evidence):** FAT32 alone (D17) did not help. The Surface still returns to its boot menu before GRUB with Fedora shim 16.1-7, Secure Boot off. The previous project hit the same problem: FAT32 with shim failed, and FAT32 with GRUB direct reached the Linux console on 2026-10-18. Why shim fails on this firmware is unknown (Hypothesis). Secure Boot is off anyway (D9: GRUB lockdown refuses `devicetree`), so shim does nothing for us.
- **Consequence:** an installed system will hit the same problem, because Anaconda installs shim and points the boot entry at it. The installer path must point the UEFI boot entry at `grubaa64.efi` (`efibootmgr`), or drop shim. Track this as risk R9.
- **Evidence:** `out/iso/sp11-fedora44-aarch64-kiwi-20261025T115940Z-directgrub.iso`, with SHA-256 `b4cb9024fc6e021361abdab66f54dafe2b5df9cb11aba2be9d1a46e09a9745c3`. It differs from the D17 ISO only in the ESP: `BOOTAA64.EFI` is GRUB, plus the marker line. In QEMU it shows the marker and the menu, and starts `SP11 debug`.

## D19 (2026-10-25): M3 display candidate after the first device boot

- **Observation (operator, kiwi `-d18` ISO):** GRUB works and `SP11 debug` starts the kernel. The console text scrolls on the firmware framebuffer, then the LCD goes black and stays black. No device logs have been read yet.
- **Hypotheses**, each tested by its own GRUB entry on one stick:
  - **H1:** `clk_disable_unused` (late_initcall_sync, `sources/linux/drivers/clk/clk.c:1627`) gates the built-in GCC display clocks, such as `gcc_disp_hf_axi_clk` (`sources/linux/drivers/clk/qcom/gcc-x1e80100.c:2991`, not critical). That kills the firmware framebuffer before `msm` binds. If `msm` then never binds or fails on eDP, the screen stays black.
  - **H2:** `msm` binds, but eDP or the panel fails (HPD mux, panel power or backlight).
  - **H5:** `msm` binds only after every enabled DP controller has its next bridge (`sources/linux/drivers/gpu/drm/msm/dp/dp_display.c:1081`). External DP0 and DP1 (USB-C, `x1-microsoft-denali.dtsi:877`, `:885`) need the qmp-combo, ps883x and pmic_glink altmode bridges. If one never probes, the eDP never lights.
  - **H3:** the LCD backlight is described wrong. In vanilla, `pmc8380_3` GPIO4, the LCD backlight enable, is the panel enable, and there is no PWM backlight.
- **Decision:**
  1. `kernel/series` gets display-lcd 0001 (panel ID), 0002 (HPD pinctrl) and 0003 (PWM backlight).
     - 0003 is released despite the display-lcd hold. Dale Whinham's series carries `Tested-by: Haipeng Lin` on the Surface Pro 11 LCD (openwall linux-kernel 2026/10/17/1002).
     - The PMK8550 GPIO5 pad subtype belongs to the PMIC part, not to the unit, so the func3 risk is reduced to Inference (strong).
     - `CONFIG_DRM_DP_AUX_CHARDEV=y` (display-lcd request, DPCD collection).
  2. The ISO also ships two DTB variants from the same tree: `…-nobl.dtb` without 0003, which isolates a backlight regression, and `…-edponly.dtb` with DP0 and DP1 disabled, which tests H5. The collector records `devices_deferred`.
  3. GRUB device entries: default `SP11 debug`; `SP11 debug, keep firmware clocks` (`clk_ignore_unused pd_ignore_unused`, diagnostic for H1, never default); `SP11 debug, eDP only (USB-C DP off)`; `SP11 debug, DTB without PWM backlight`; the existing DRM trace, nomodeset and initramfs entries; and the VM entry.
- **Exit:** the device logs (`EFI/sp11-logs` on the stick) decide which hypothesis holds. `clk_ignore_unused` never becomes the default without a log that shows H1.

## D20 (2026-10-25): M4 default entry follows the previous project's GNOME boot (operator: "work on the fixes")

- **Decision:** without waiting for device logs, the M4 default entry combines every difference the comparison found between M3 and the previous project's ISO, which was reported to reach GNOME (`out/agents/surface-compare/report.md`). It adds the one Verified M3 omission:
  1. `leds_qcom_lpg` in the initramfs, with an L0 assertion on the whole display module chain (Verified omission).
  2. `clk_ignore_unused pd_ignore_unused rootdelay=10` on the default entry. This supersedes the D19 gate for the default only. The minimal M3 command line stays as a separate entry for comparison.
  3. A `parity` DTB: the M3 DT, the 10-CPU topology (MADT-verified fused-off cores removed) and no system SS3 idle (CL4/CL5 kept).
  4. `qcom_q6v5_pas` and the staged ADSP/CDSP firmware pairs (`qcadsp8380.mbn`, `adsp_dtb.mbn`, `qccdsp8380.mbn`, `cdsp_dtb.mbn`) in the initramfs. This supersedes F1 for M4. One entry blacklists PAS in the initramfs (`rd.driver.blacklist=qcom_q6v5_pas`) to compare.
- **Kept:** the display wiring from Dale Whinham's LCD-tested patch 0003, not the previous project's GPIO4/always-on variant; BTF; verbose boot; FAT32 ESP with GRUB direct.
- **Exit:** device logs from M3 or M4 decide which of these changes are needed. Anything a log does not justify is removed again before the installed-system work.

## D21 (2026-10-26): M5, sound off on every device entry (S1) and GPU isolation

- **Observation (operator, M4):**
  - The boot reaches userspace (`User Manager for UID 1000`, `Session 1 of user liveuser`).
  - Then the machine reboots.
  - Earlier, `FAT-fs (sda2): Volume was not properly unmounted` is printed. `sda2` is the stick's ESP, left dirty by forced power-offs while the collector had it mounted.
- **Safety finding (S1):** the upstream Denali DT enables the sound card with both WSA8845 speaker amplifiers (`sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:309`, `&swr0` at `:1079`). M3 and M4 shipped it unchanged, and M4 even starts the ADSP in the initramfs. That breaks S1, so every device DTB from M5 on disables `/sound` and `&swr0`. L0 fails if any device entry's DTB has either enabled.
- **Decision (M5, DT and image only, same kernel `7.3.0-65.sp11.3`):**
  1. Default entry DTB `m5`: parity + sound off + GPU off (`&gpu { status = "disabled"; }`). GNOME on the LCD uses msm KMS with llvmpipe rendering.
  2. Entry DTB `m5gpu`: parity + sound off, GPU on. This isolates the GPU first open (zap shader, GMU, speed bin) as the reboot cause.
  3. The collector unmounts the ESP after every write, so it is never left dirty. It reads only the GPU speed-bin NVMEM cell (`qfprom` `0x119`, 2 bytes, bits 7–14; `hamoa.dtsi:8790`) and records whether any ALSA card exists.
- **GPU safety:** until the fuse is read on the device (gpu dossier Q1), accelerated GPU runs only in the `m5gpu` diagnostic entry.
