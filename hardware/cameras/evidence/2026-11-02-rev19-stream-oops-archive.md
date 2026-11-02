# Rev19 stream-on oops: archived capture

- **Boot:** `393849d8-7c90-4248-bf6d-925933d1093a`, entry `sp11.entry=safe`, kernel `7.3.0-65.sp11.19.fc44.aarch64`.
- **ISO:** `out/iso/sp11-fedora44-aarch64-kiwi-20261102T222639Z-private.iso`, SHA-256 `49bbf53d41904c21f4ff8b0b3082c09bea8f244f41888e9dacea8e824051399d`.
- **Archived raw capture:** `out/device-logs/m16-20261102d/393849d8-7c90-4248-bf6d-925933d1093a/` (git-ignored; no raw log in git).
- **Hashes:** `dmesg.txt.gz` `0cbe3e74398d34067143f91d0ce00e190e20f48106fd6170d87a0ace04729f78`; `extra-cameras.txt.gz` `4f357ccb90ced568fe8f8ecfd1974dee8e0164ddf7b93795a64259ba3abbd866`.

The media graph already contained both RGB sensors:

```text
<- "ov13858 7-0010":0 [ENABLED,IMMUTABLE]   on msm_csiphy1
<- "imx681 8-0010":0 [ENABLED,IMMUTABLE]    on msm_csiphy2
```

While `CameraManager` streamed, the kernel reported:

```text
Unable to handle kernel paging request at virtual address ffff800083aa6000
EC = 0x25: DABT (current EL)  FSC = 0x07: level 3 translation
WnR = 1
pc : csiphy_reset+0x30/0x78 [qcom_camss]
lr : csiphy_set_power+0x94/0x1b0 [qcom_camss]
x2 : ffff800083aa5000   x1 : ffff800083aa6000
```

`x2` is the CSIPHY mapping base and the write is at `base + 0x1000`; the running DTB declared csiphy0/1/2 with `0x1000`. Patch 0003 now uses `0x2000` for all four CSIPHY windows and `0xf000` for the full VFE0/VFE1 windows, matching the Hamoa reference and SM8550/SM8650. The privacy LED path is the V4L2 sensor core (`v4l2-fwnode.c:1275`, `v4l2-subdev.c:173-186`), so the dark LED is downstream of the failed stream.

This archive is evidence for the DT fix; it is not a device retest of that fix.
