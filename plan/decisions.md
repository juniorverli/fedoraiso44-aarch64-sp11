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
