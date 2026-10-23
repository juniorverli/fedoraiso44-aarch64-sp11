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
