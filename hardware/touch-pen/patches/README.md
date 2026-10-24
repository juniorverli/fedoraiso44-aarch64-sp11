# Touch/pen patch exports

`series` lists the 11 unchanged spi-hid v6 patches, in upstream order.
Original decoded mail bodies are unchanged. Provenance, SHA-256 hashes,
application and build/checkpatch results are in
[series evidence](../evidence/2026-10-24-spi-hid-v6.md).

`0012-denali-touch-draft.patch` is a separate unsigned, disabled DT RFC.
It is deliberately excluded from `series`. The transport still needs quad
support and board sequencing; these exports are not an enabled-device
integration series. Sources pins and independent cross-check are pending.
