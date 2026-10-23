# dsp-subsystems worker

**Owns:** `hardware/dsp-subsystems/` (write). Everything else is read-only.
**Phase:** 1 (boot of ADSP and CDSP), 3-4 (services). **Kernel worktree:** no, unless a patch is proven necessary.

## Mission

ADSP and CDSP reach `running` on every boot with the right firmware under the paths Linux requests, and the protection-domain and QRTR services that battery, USB-C, audio and sensors rely on are present.

## Start

1. Read `hardware/dsp-subsystems/README.md`, `component.toml`, `firmware/manifest.toml`.
2. Answer the dossier's open questions.

## Specific leads

- Compare the ELF program headers of `qcadsp8380.mbn`, `adsp_dtbs.elf`, `qccdsp8380.mbn`, `cdsp_dtbs.elf` with what `qcom_q6v5_pas` expects (`sources/linux/drivers/remoteproc/qcom_q6v5_pas.c`, x1e80100 resource tables): PAS IDs, DTB PAS ID, memory regions in `hamoa.dtsi`. Header reading only.
- Find which program reads the `*.jsn` service maps (`pd-mapper` in Fedora 44?), the path it searches, and whether all five files are needed.
- Note what `qcpmicglink8380` exposes on Windows (battery, charger, UCSI) and whether `qcom_battmgr` and SSAM would both register a battery; hand the conclusion to `ec-sam` as a request.

## Deliver

1. Firmware entries confirmed or corrected, as a request to the firmware worker.
2. `test-plan.md`: remoteproc states, `qrtr-lookup`, `power_supply` listing.
3. Dossier and `component.toml` updated.

## Do not

- Load an image built for another board (no `adsp` files from other X1 laptops).
