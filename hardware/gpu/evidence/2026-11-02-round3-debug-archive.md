# Round-3 debug boot: archived reset capture

- **Boot:** `b1c603b5-d523-4607-9aa6-3f7f978a1413`, entry `sp11.entry=debug`, kernel `7.3.0-65.sp11.19.fc44.aarch64`.
- **ISO:** `out/iso/sp11-fedora44-aarch64-kiwi-20261102T222639Z-private.iso`, SHA-256 `49bbf53d41904c21f4ff8b0b3082c09bea8f244f41888e9dacea8e824051399d`.
- **Archived raw capture:** `out/device-logs/m16-20261102d/b1c603b5-d523-4607-9aa6-3f7f978a1413/` (git-ignored).
- **Hash:** `kmsg-live-b1c603b5-d523-4607-9aa6-3f7f978a1413.txt` `9d95a8f29d3bce4510b11252ca23dd007b45e0498b456a52fd2a4a4471c0d598`; `dmesg.txt.gz` `3fb881e7a0ed9d3f4c6840e1e6b1dff7d7970b064af4579c06b3e2a6d87adab9`.

The debug boot started GMU firmware and HFI twice, at 30.3 s and 58.9 s, both returning 0. The 385 KiB live kmsg has no panic, oops or SMMU line; its last write is at 61.2 s. The reset follows the desktop appearing. The service's `power/control=on` write is not recorded, and it pins only `3d00000.gpu`; `3d6a000.gmu` is a separate platform device. The GPU inactivity delay is 66 ms (`a6xx_catalog.c:1580`).

Revision 20 keeps the lazy IOMMU configuration of this failing round, adds EFI-vars pstore and immediate kmsg publication, pins and logs both GPU and GMU, and requires a paired debug control boot without the pin plus repeats. A silent reset remains inconclusive, not proof of a firmware/power event.
