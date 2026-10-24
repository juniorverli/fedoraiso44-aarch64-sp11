# Q2: panel timing requirements and provisional Linux profile

## What is established

The relevant input paths, hashes and catalog languages are listed in
[Windows/backlight evidence](2026-10-24-windows-backlight.md). REA was invoked
through the prescribed CLI with Ghidra 12.1.4, forced
`AARCH64:LE:64:v8A`, `GHIDRA_MAXMEM=4G`, and the shared `.ghidra.lock`.
Every invocation checked for the REA self-test after taking the lock. Snapshots
and detailed outputs remain in `out/rea/display-lcd/`, not git.

| Observation | Grade | Citation |
|:--|:--|:--|
| DX has recovered procedures available for address-based work | Verified | DX SHA `46237eba1c2c0a51d700cdf14730aae3f41b0a55775a185b87e618cab8285814`, REA `ev_78013e131ee03b25faa492292a40ef22ece74fa4f0f743a09aef50b3b39e3e3a`, `qcdxkm-procedures.json` (CLI TOON text despite suffix) |
| DX has the parser strings `EDPPowerTiming0` through `EDPPowerTiming12`, plus custom AUX timing keys | Verified | Same DX SHA; addresses 0x140312c03 through 0x140312f3f, custom keys 0x140312f84 / 0x140312fc9; REA trace `ev_9bbcecdc5c9251464595027423dee9bb3e5650053ec3b6073badcde8dc13a5c1` |
| The literal timing-key trace reports no references | Verified observation of that query | Same trace; this is not proof that no code consumes the table |
| An exact-address query for 0x140329c34 also returns no references | Verified observation of that query | DX SHA above; REA `ev_1e8bb7d52e78fe5838b119d913581641358d884f9bff1a309c22bb6ac91a6d41`, `qcdxkm-timing-global-xrefs.txt` |
| PEP has recovered procedures available for address-based work | Verified | PEP SHA `e5bdeb8c0fb8823990f7520a19c00807711cf909f91f8d67db78ffb18c1b2277`; REA `ev_a0dd212bebe4d2b254dcaebb1d0c893e0e516db6fe0bebacb26e4b028b42c2c0`, `qcpep-procedures.txt` |
| IDP contains a `DELAY` record with integer 500 immediately after its TLMM GPIO70 ENTER record | Verified raw record | IDP SHA `581d11553cc9961da63b301ee81228f9495acad16983218b45d6329b1982fa47`, package offset 0x0fd5, integer argument header 0x0fe7 / payload 0x0feb |

The delay record's unit and relation to panel timing are **TBD**. In particular,
the raw integer 500 must not be called T12=500 ms without following PEP's
handler. Generic GPU FSTATE entry/exit is not necessarily the panel/backlight
sequence, and the output pin configuration is not evidence of the duration
between transitions.

The reference `_ROM` XMLs are for other panels and the extension blobs are
method/rail overrides, not a recovered LP129WT342166 timing specification.
No verified values for T3, T8, T9, T10 or T12 have yet been recovered from
this Windows stack. Parser key names alone do not identify values or map
the key suffixes to eDP timing labels.

## Patch 0001 fallback, explicitly graded

**Inference, provisional:** use Linux's existing common LGD profile, shared by
the related LP129WT232166 and all current LGD table entries, for the new
LP129WT342166 identity. The source facts are Verified at
`sources/linux/drivers/gpu/drm/panel/panel-edp.c:1853` and `:2179`–`:2190`.
The observed panel identity is Verified from the unit's EDID at offsets
0x08–0x0b and the 0x6c descriptor (SHA in EDID evidence).

| Linux field | Proposed value | Relationship and limitation |
|:--|--:|:--|
| `hpd_absent` | 200 ms | T3 maximum / wait budget; with functioning native HPD the driver polls instead of sleeping the full interval |
| `enable` | 200 ms | Delay after link training before backlight; aggregate T6 + max(T7, T8), not an isolated measured T8 |
| `disable` | 200 ms | Backlight-off to video-end delay, analogous to T9 minimum |
| `pre_unprepare` | unset (zero extra delay) | No new T10 requirement claimed or encoded |
| `unprepare` | 500 ms | Off dwell before another prepare, analogous to T12 minimum |

Field definitions are in `sources/linux/drivers/gpu/drm/panel/panel-edp.c:61`,
`:124`, `:138`, `:148`, `:158`; HPD wait behavior is at `:475`–`:495`.
The fallback is justified by the exact LGD family precedent and by keeping
EDID-provided modes rather than inventing a timing override. It is **not** a
datasheet confirmation or a proof of safety/correctness on this panel.
It shortens the unknown-panel driver's generic 2000 ms off dwell to 500 ms
(`sources/linux/drivers/gpu/drm/panel/panel-edp.c:755`). This specific change
needs the independent cross-check and device cold-boot evidence before the
component can be treated as ready. If the family assumption is rejected,
hold patch 0001 rather than claiming the Windows timing question is solved.

## Next trace targets

A data-only PE mapping inspection found pointers preceding the DX timing
strings: the `EDPPowerTiming1` record points to 0x140329c34; following keys
point to successive four-byte locations through 0x140329c60. `EDPPowerTiming0`
points elsewhere, 0x140329b30. These pointers are **Verified raw bytes** in
DX (same SHA), at file offsets 0x310c39 through 0x310f30 and 0x310bf4;
their role as parser destinations is an **Inference**. The target addresses
are in the zero-initialized tail of `.data`, so reading file bytes there
cannot recover initialized panel defaults. Trace code references to those
locations and their initialization/copying before assigning units or values.

PEP has `DELAY` text at file offset 0x284e24 / VA 0x140287424 and the digital
output IOCTL name at offset 0x38ae90 / VA 0x14038e090 (Verified raw bytes,
same PEP SHA above). Follow their handler selection after confirming procedure
addresses against the saved inventory. Decompiled listings remain outside git.
