# firmware worker

**Owns:** `firmware/` (write), `scripts/firmware-*`.
**Phase:** 1 onwards.

## Mission

One manifest that tells the image worker exactly which file goes to which `/lib/firmware` path, from where, verified by hash, for every component in scope.

## Tasks (phase 1)

1. For each `[firmware] needs` entry of the phase 1 components (`soc-boot`, `display-lcd`, `gpu`, `dsp-subsystems`), find the code that requests the file (kernel `firmware-name` in DT, `request_firmware` call, userspace loader) and cite `file:line`.
2. Resolve the source: Fedora 44 `linux-firmware` (give the NEVRA and the file's path in the package) or the DriverStore (path and SHA-256 from `MANIFEST.sha256`). Prefer `linux-firmware` when both exist and record both hashes.
3. Mark Windows-to-Linux renames (`adsp_dtbs.elf` to `adsp_dtb.mbn`) and check compressed variants (`.xz`, `.zst`) the kernel may try first.
4. Write `scripts/firmware-stage.sh`: copies DriverStore files into `out/firmware-root/lib/firmware/...` after checking each SHA-256, and fails on any mismatch or missing file.
5. Set `status = "mapped"` only when the requesting code and the source are both cited.

## Do not

- Commit any firmware file (risk S5).
- Invent a Linux path; if no code requests it, the file is not needed.
