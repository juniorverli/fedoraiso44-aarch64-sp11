# Round-3 audio capture: archived values and baseline correction

- **Boot:** `393849d8-7c90-4248-bf6d-925933d1093a`, entry `sp11.entry=safe`, kernel `7.3.0-65.sp11.19.fc44.aarch64`.
- **ISO:** `out/iso/sp11-fedora44-aarch64-kiwi-20261102T222639Z-private.iso`, SHA-256 `49bbf53d41904c21f4ff8b0b3082c09bea8f244f41888e9dacea8e824051399d`.
- **Archived raw capture:** `out/device-logs/m16-20261102d/393849d8-7c90-4248-bf6d-925933d1093a/` (git-ignored).
- **Hashes:** `extra-audio.txt.gz` `2a8722f8fbc113badb5ac8b7a15d30a9e1f91d1bda485a3680e9913b997a3627`; `dmesg.txt.gz` `0cbe3e74398d34067143f91d0ce00e190e20f48106fd6170d87a0ace04729f78`.

The snapshot (taken before the graphical session) reported `Speakers Volume` and both `Spkr* PA Volume` at max 6, value 0 (-9 dB by the declared scale), and both `WSA_RX* Digital Volume` at max 81, value 72 (-12 dB). The UCM files in effect were:

```text
3cd05b43… MICROSOFT-Surface-Pro-11.conf
ba24e854… Surface11-HiFi.conf
052f84e6… Surface11-SpeakerSeq.conf
ca9d2725… Surface11-WsaInit.conf
```

## Baseline correction

The rev18 capture (`out/device-logs/m16-20261102b/55d1ef37…`, kernel `7.3.0-65.sp11.18`) shows PA max 31, value 6; the rev19 capture above shows PA max 6, value 0. The 9 dB difference is real. However, the operator's **working** audio and microphone report was on the rev19 D28 ISO (`journal/2026-11-02.md`, "Device test round 2 and final ISO"), not on the rev18 capture, and the failing round 3 is also rev19 with the same kernel and lazy IOMMU. The round-2-to-round-3 loss is therefore **not** proven to be a rev18-to-rev19 kernel difference. It is confounded by the image change between the two rev19 ISOs (ceiling 0.251 to 1.0) and by the camera `csiphy_reset` oops in the same round-3 boot.

The PA 6 write on enable is still a correct restoration of the 0 dB operating point after a disable wrote 0, but it is a correction, not a proven root cause of the round-3 silence. Revision 20 must test audio and microphone first, on a clean safe boot with no camera application, and keep the D28 fail-safe: `device.routes.default-sink-volume = 0.0`, startup mute, 30 % helper level and `api.acp.max-volume = 0.251` (-12 dBFS).
