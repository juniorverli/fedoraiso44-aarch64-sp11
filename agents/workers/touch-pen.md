# touch-pen worker

**Owns:** `hardware/touch-pen/` (write). Everything else is read-only.
**Phase:** 2. **Kernel worktree:** yes (`out/linux/touch-pen`, branch `w/touch-pen`).

## Start

1. Read `hardware/touch-pen/README.md`, `component.toml` and the dossiers in `depends_on`.
2. Work the dossier's open questions in order (`agents/protocol.md` §9).
3. Fill the Role column of the dossier's Windows table for every package you open.

## Mission

Touch and pen working through a HID-over-SPI transport on 7.3, with the device node built from the ACPI description of `MSHW0484`.

## Specific leads

- Upstream first: the HID-over-SPI (`spi-hid`) series on lore (linux-input), its newest revision, and how much of it applies to 7.3. Prefer backporting the newest posted revision unchanged.
- ACPI: the `MSHW0484` device and its SPI controller `QCOM0C0E` (`SUBSYS_MSHW0489`) in `live-inventory/acpi/dsdt.dsl`: `_CRS` (SpiSerialBus speed/mode/CS, GpioInt), `_PS0`, `_PS3`, `_RST`, `_DSM` (HID descriptor address, opcodes).
- GENI: check `sources/linux/drivers/soc/qcom/qcom-geni-se.c` and `spi-geni-qcom.c` for what happens when the engine reports protocol 0, and whether `qcom/x1e80100/qupv3fw.elf` is needed.

## Deliver

Patches (backport + DT node), `test-plan.md` (evtest, libinput list-devices, pen pressure), dossier updated.

## Do not

Flash touch or pen firmware (risk S3).
