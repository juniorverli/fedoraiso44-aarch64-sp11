# Revision 25 integration preparation — 2026-11-04

**Status: no-go for the release build until the kernel revision gates and the topology cleanup concern below are resolved.** This is a source and existing-artifact review, not an audio or camera fix claim. No kernel compilation, device operation, ISO build, Git write, or change outside `kernel/` was performed in this session.

## Inputs and ordered candidates

The pinned source's `HEAD` and `v7.3^{commit}` both resolve to `c03c1a14507dfaf8b856c2608f9ac216021fc222`. The next unused kernel release revision found in the existing RPM and DTB output directories is 25; the existing `rev25` menu name refers to an image using a revision-24 kernel and is not a kernel release.

After the revision-24 series, the staged order is:

1. `kernel/patches/0011-audio-speakers-guard-calibration-lifetime.patch`: **ASoC: qcom: bind SP11 calibration to the VI graph**, SHA-256 `7fe2881bcebff5ec7fa823ec9de71e87c92d3369100629bd285e982cd9f80551`.
2. `kernel/patches/0024-ASoC-qcom-validate-calibration-flags-report-VI-identity.patch`: **ASoC: qcom: validate SP11 flags and report VI identity**, SHA-256 `9b392f61658ba3edfd4d40064d4dd9bc6a7b5a062767996c1af59f12b17bf921`.
3. `kernel/patches/0025-ASoC-qcom-propagate-topology-widget-load-errors.patch`: **ASoC: qcom: propagate topology widget load errors**, SHA-256 `3f8f8ec68d6b42929b2d4c40bc28c9ff90ad06adf272bffe3753357f6f634cc2`.

The two audio-owner candidates are not present under `hardware/audio-speakers/patches/` in this worker checkout. Their integration copies above are byte-identical to the uncommitted component-worktree candidates; the corresponding files in the main checkout had the same hashes. Using local copies makes the series self-contained. If their contents or listed paths later change, recompute the ordered series hash before any build.

`kernel/base.toml` retains the v7.3 tag, Fedora spec and release convention, sets `series_rev = 25`, and records `series_sha256 = f0ff0ff24fe574dcb094bfeecfb5003e84dbb3a17cedd1876ab5f19e5fd18f5c`. This value was produced with `bash -c '. scripts/kernel-common.sh; kernel_series_hash'`; `kernel_series_check` passed. The resulting expected kver is `7.3.0-65.sp11.25.fc44.aarch64`.

Camera candidate `hardware/cameras/patches/0026-candidate-arm64-dts-qcom-denali-rear-camera-rotation.patch`, SHA-256 `fc5438b397f18e389917d3c7571f255a3a337f814f18bc1e7137d9205d3818f3`, also dry-runs without fuzz after the audio patches. It adds only rear `rotation = <180>` metadata. The camera worker's 2026-11-04 dossier says to use that mounting metadata only after physical confirmation, and the simple pipeline does not automatically rotate pixels. It is therefore a **separate camera request**, not in revision 25: identify the rear lens with an asymmetric target, verify orientation and userspace handling, and then reassess the metadata. The patch does not establish a camera correction.

## Apply and code review

The 93 revision-24 patches followed by 0011, 0024 and 0025 were dry-run and then applied sequentially with GNU `patch --batch --fuzz=0 -p1` to a disposable tree made from the affected files of the pinned commit. All 96 passed. Eleven pre-existing patches reported line offsets; none of the three added audio patches did. The camera candidate separately passed `--dry-run --fuzz=0` on the resulting tree. `scripts/checkpatch.pl --strict --no-signoff --no-tree` reported zero errors, warnings or checks for each of the four candidates.

The 0011 candidate invalidates calibration on VI lifecycle and error paths, rejects stale generations and requires calibration/VI graph identity before the existing closed-loop unmute decision. Candidate 0024 rejects unknown supplement/calibration flags and nonzero reserved calibration data and adds read-only identity reporting. Candidate 0025 propagates widget-loader errors. No new speaker-policy bypass was identified in these changes; the pre-existing, explicitly authorized D26 open-loop policy remains as it was. These observations do not establish DSP acceptance, valid VI samples, calibration safety, complete closed-loop protection, or device behavior.

**Topology cleanup concern:** in the unchanged loader, `audioreach_widget_load_module_common()` obtains or creates a subgraph and container before parsing a module, and assigns `dobj->private` only after successful module parsing (`sources/linux/sound/soc/qcom/qdsp6/topology.c:591-616`). If a duplicate module ID is encountered in a newly created container, the loader can return with that new container/subgraph indexed but no module in the widget's private field. The topology core removes the failed widget (`sources/linux/sound/soc/soc-topology.c:1243-1255`); `audioreach_widget_unload()` returns when that field is null, so that newly allocated state has no widget owner to free it. Candidate 0025 newly propagates this error and makes the failed-load rollback path reachable for those widget types. Stale state and retry effects have not been dynamically tested. Ask the audio owner to resolve or otherwise rigorously account for this path before a release build, and test actual public, closed-loop, duplicate-ID and truncated topologies after building, including rollback and retry. The prior host stubs and QEMU harness results in the audio completeness audit do not test candidate 0025's full allocation and unload path.

## Configuration and existing DTBs

`kernel/config/sp11.config` is unchanged and still sets `CONFIG_DEBUG_INFO_BTF=y` and `CONFIG_DEBUG_INFO_BTF_MODULES=y`. `scripts/kernel-config-check out/build/kernel/check/shipped.config` passed all 105 fragment symbols for the **existing revision-24** build. Its existing release record reports BTF in vmlinux and 5935/5935 modules, and `CHECK_DTBS=y` success with zero warning lines. Those are not revision-25 results.

The existing revision-24 packaged DTB and all six published variant DTBs were checked without recompilation. The current **main checkout's** `scripts/kernel-m8-check.py` passed the packaged DTB and `m15-nosnd`, `m15-safe`, `m15`, `m15-notouch`, `m15-spk`, and `m15-spectra` with the existing baselines and applicable M12 comparison. Their published DTB hashes match their JSON records and the records identify revision 24 and its series digest. The existing schema and S1 checks passed, with the existing D26-marker and Spectra diagnostic allowances. The PM8550 flash controller is disabled in each inspected DTB; no camera-flash compatible or named illuminator was found. These source/artifact checks do not prove physical LED or eye-safety behavior.

This kernel worker checkout predates the main checkout's uncommitted M15 orientation restoration and its matching `kernel-m8-check.py` change. Under the older worker check, the current published `m15` fails because it has both orientation switches present; the other five variants and packaged DTB pass. Under main's restored policy all seven pass. Preserve the main checkout's restoration and matching check when integrating; neither was changed here. The historical packaged-DTB/M12 comparison also remains unchanged.

`scripts/kernel-check` was invoked with an isolated scratch `SP11_MAIN` so that it could not delete the live check tree or run its DTB `make` step. It passed the series hash check and stopped at the expected missing `kernel-core-7.3.0-65.sp11.25.fc44.aarch64.rpm`. No revision-25 RPM exists in the current output. Consequently no revision-25 vmlinux, modules, shipped config, packaged DTB, `CHECK_DTBS=y`, or full release check has been validated.

## Required release and image gates

All following scripts are outside this session's authorized write scope and were left untouched. In the main checkout:

- `scripts/kernel-check:176,190,194,198`: include revision 25 in the existing outer packaged check, M15 setup, M16 milestone and CAMSS-window predicates. Without the outer inclusion a rev25 check can skip the packaged DTB safety, schema, wiring and RPM-payload block. Retain the existing M12 historical comparison and all its arguments.
- `scripts/kernel-dtb-variants.sh:23`: route revision 25 to the existing M15 publisher. `scripts/kernel-dtb-m15.sh:9,155`: accept revision 25 in its version guard and release-record assertion, updating the guard message. Retain the main checkout's M15 orientation restoration, all six variant checks, record/hash checks, and current safety policies.
- `scripts/image-build-kiwi.sh:106,117`: add `7.3.0-65.sp11.25.fc44.aarch64` to the kver allow-list and `25` to the variant JSON `series_rev` allow-list; update the stale range message if desired. Keep the hash, kver and model comparisons.
- `scripts/image-test-static.sh:416,451,452`: add `25` to the variant-record revision allow-list, `7.3.0-65.sp11.25.fc44.aarch64` to the kver allow-list, and `kernel-core-7.3.0-65.sp11.25.fc44.aarch64` to the installed NEVRA allow-list. Keep the embedded-record, image safety, orientation and packaged-DTB comparisons. In the older kernel worker checkout these image-test lines are 413, 448 and 449 respectively.

## Orchestrator build handoff

After the running L1 finishes, after resolving the blockers above and integrating these files into the checkout that retains the main orientation restoration, the release command is:

```sh
scripts/kernel-build.sh -j 6
```

The script takes `out/.kernel-build.lock`, enforces its release disk guard, builds the Fedora 44 RPMs and invokes `scripts/kernel-check`. Expected outputs include `out/rpms/kernel-7.3.0-65.sp11.25.fc44.aarch64.rpm`, matching `kernel-core`, `kernel-modules*`, `kernel-devel`, and `kernel-debuginfo*` RPMs, the packaged `qcom/x1p64100-microsoft-denali.dtb` inside kernel-core, `out/rpms/kernel-7.3.0-65.sp11.25.fc44.aarch64.json`, and `out/build/kernel/rpmbuild.log`. Require the release record to show the new series hash, successful fragment and packaged checks, BTF in vmlinux and every module, and a passing `CHECK_DTBS=y`.

After the revision gates are extended and the release check passes, `scripts/kernel-dtb-variants.sh` is expected to publish the six checked `m15*` DTB/JSON pairs under `out/dtb-variants/7.3.0-65.sp11.25.fc44.aarch64/qcom/`. If the image retains Spectra, rebuild its external module against the revision-25 devel/debuginfo packages under the shared build lock and verify vermagic and BTF; do not reuse the revision-24 module. Image composition and L0/L1 follow only after these artifacts and their owner gates pass.
