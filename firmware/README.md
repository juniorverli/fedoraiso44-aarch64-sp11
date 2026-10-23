# Firmware

Owner: firmware worker (`agents/workers/firmware.md`).

`manifest.toml` is the only list of firmware this project ships. Each entry says which kernel or userspace component asks for the file, under which Linux path, and where the bytes come from: the local DriverStore (with SHA-256) or Fedora's `linux-firmware`.

Rules:

1. No binary in git (`plan/risks.md` S5). The image worker copies DriverStore files into the ISO at build time, on this machine only.
2. A Linux path comes from the kernel or userspace that requests it, cited with `file:line`. Never guess a name.
3. When Fedora's `linux-firmware` already ships a file, prefer it and record the NEVRA.
4. Windows and Linux names may differ (`adsp_dtbs.elf` is requested as `adsp_dtb.mbn`). Record both.
5. Components declare their needs in `hardware/<component>/component.toml` `[firmware]`; this manifest resolves them.
