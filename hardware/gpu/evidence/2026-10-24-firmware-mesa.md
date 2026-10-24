# Fedora 44 GPU firmware, Mesa and zap container

Date: 2026-10-24. Repository queries and static source/header checks; no
installation into an image and no device execution.

## Fedora package queries

**Verified repository metadata:** Fedora 44 aarch64, enabled stable repositories,
queried with Fedora's DNF in the already available official container image
`registry.fedoraproject.org/fedora:44`, local image ID
`sha256:b7e5ccd4fe73ede1c962d6e51e3d9362cc7573b1f88e56c0c7f02ffb1b4bb05e`.
The disposable containers used a read-only root and tmpfs caches; no running
image/kernel worker container was modified. No RPM payloads were downloaded.

Commands run (the full prefix was repeated for each query):

```sh
docker run --rm --read-only --tmpfs /var/cache --tmpfs /var/lib/dnf \
  --tmpfs /var/lib/dnf5 --tmpfs /var/log --tmpfs /tmp \
  registry.fedoraproject.org/fedora:44 \
  dnf -q repoquery --latest-limit=1 \
  --queryformat '%{name}-%{epoch}:%{version}-%{release}.%{arch}\n%{sourcerpm}\n%{location}\n' \
  qcom-firmware mesa-dri-drivers mesa-vulkan-drivers

# Inside an equivalent disposable container (rg is absent there):
dnf -q repoquery --latest-limit=1 --list \
  qcom-firmware mesa-dri-drivers mesa-vulkan-drivers |
  grep -E 'gen70500|qcdxkmsuc8380|msm_dri|libgallium|libvulkan_freedreno|freedreno_icd'
```

Relevant returned values:

| NEVRA (epoch 0) | Source RPM | Relevant file-list entries (Verified) |
|:--|:--|:--|
| `qcom-firmware-0:20261019-1.fc44.noarch` | `linux-firmware-20261019-1.fc44.src.rpm` | `/usr/lib/firmware/qcom/gen70500_sqe.fw.xz`, `/usr/lib/firmware/qcom/gen70500_gmu.bin.xz` |
| `mesa-dri-drivers-0:26.2.5-1.fc44.aarch64` | `mesa-26.2.5-1.fc44.src.rpm` | `/usr/lib64/dri/msm_dri.so`, `/usr/lib64/libgallium-26.2.5.so` |
| `mesa-vulkan-drivers-0:26.2.5-1.fc44.aarch64` | `mesa-26.2.5-1.fc44.src.rpm` | `/usr/lib64/libvulkan_freedreno.so`, `/usr/share/vulkan/icd.d/freedreno_icd.aarch64.json` |

The first query also returned `linux-firmware-0:20261019-1.fc44.noarch`.
The files of interest are owned by its **qcom-firmware subpackage**; merely
pinning the source package name does not record the installed owner.
The selected RPM locations were under
`http://mirror.in2p3.fr/pub/fedora/linux/updates/44/Everything/aarch64/Packages/`,
with `q/qcom-firmware-20261019-1.fc44.noarch.rpm` and
`m/mesa-{dri,vulkan}-drivers-26.2.5-1.fc44.aarch64.rpm`.
The [Fedora updates repository](https://dl.fedoraproject.org/pub/fedora/linux/updates/44/Everything/aarch64/)
is the authoritative repository location. These are observations on the date
above, not immutable compose pins or RPM signature/hash verification.

**Inference:** the standard Fedora firmware package supplies the two filenames
requested by the chip entry at
`sources/linux/drivers/gpu/drm/msm/adreno/a6xx_catalog.c:1575`.
Compressed firmware requires `CONFIG_FW_LOADER_COMPRESS_XZ=y`; the assembled
kernel config and initramfs contents still need verification by their owners.

The file-list filter also returned Lenovo and Dell zap shaders and
`qcom/x1e80100/gen70500_zap.mbn.xz`, but did not return the DT's
`qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn`. Do not substitute a differently
signed board's zap shader. The manifest's Microsoft DriverStore mapping is
still required.

The Fedora Packages release-specific web pages returned older base-release
builds (Mesa 26.0.3, qcom-firmware 20260309); their release overview also lagged
the live DNF query. The NEVRAs above come from the current aarch64 DNF metadata,
not from those x86_64-oriented web file lists. Sources/image owners must pin
the exact packages and repository snapshot they actually assemble.

## Mesa chip matching and enabled drivers

Remote source files were read over HTTPS into memory and hashed; no new source
checkout was added to the shared inputs. **Verified source observations** are
listed below. They require sources-worker pins under `sources/sources.toml`
before becoming reproducible shared build inputs.

| Source | SHA-256 | Relevant lines / observation |
|:--|:--|:--|
| [Fedora f44 mesa.spec](https://src.fedoraproject.org/rpms/mesa/raw/f44/f/mesa.spec) | `e60bac6e248f2bc1d79aa025b4e1ef4fbb7053493cfbe5500a4aaf7b0975e7d0` | 83: version 26.2.5; 40–55 enable freedreno for aarch64; 435 enables Gallium freedreno; 606–609 package msm DRI; 734–736 package Turnip library/ICD |
| [Mesa mesa-26.2.5 freedreno_devices.py](https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.2.5/src/freedreno/common/freedreno_devices.py) | `c15a9af47e83a92b82581e66890471eaad107ec27c7ed9a9b6770c3769279a96` | 1108: `GPUId(chip_id=0xffff43050c01, name="Adreno X1-85")`; 1110–1111: A7xx/gen2 |
| [Mesa mesa-26.2.5 freedreno_dev_info.c](https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.2.5/src/freedreno/common/freedreno_dev_info.c) | `c26ac1937306ac15d5537ca8e3cfed1517cd644783ce88f7afbc75352175e6f7` | 45–54: wildcard fuse matching in bits 47–32 |
| [Mesa mesa-26.2.5 tu_device.cc](https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.2.5/src/freedreno/vulkan/tu_device.cc) | `f70cb51cbd8f5cde788cdf747a1c8dbc2a9bc8780d46e003ee1b5d2873a602df` | 1681–1689: Turnip obtains name and device info from the common table |
| [Mesa mesa-26.2.5 freedreno_screen.c](https://gitlab.freedesktop.org/mesa/mesa/-/raw/mesa-26.2.5/src/gallium/drivers/freedreno/freedreno_screen.c) | `ecfd792560fe435966a86126718ab96afa9368164ded9762b1db9355fc3df393` | 97: common name; 1056–1058: common device info and unsupported-chip check |

**Inference, supported statically:** both Fedora Gallium freedreno and Turnip
recognize chip **0x43050c01**, including a nonzero speed-bin prefix. Mesa's
`0xffff` prefix is a wildcard, not a requirement for Linux to hide the fuse.
Linux exports it in the upper 32 bits at
`sources/linux/drivers/gpu/drm/msm/adreno/adreno_gpu.c:390`. No Mesa patch or
development build is indicated. This does not establish rendering stability
or Vulkan conformance on this Surface; those remain device acceptance tests.

## Microsoft zap shader header and PAS contract

Input: `sources/windows/DriverStore/qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkmsuc8380.mbn`,
SHA-256 **950f17eb439326548cba20603b30cda653d612d1564feb397ddbd92987f0e8ac**.
Catalog kind **gpu-firmware**, explicitly not Hexagon code. No disassembly,
signature execution or device upload was performed.

**Verified bytes**, decoded with Python `struct`:

| Header location | Observed value |
|:--|:--|
| ELF identification, file offset 0 | ELF32, little endian; total file length 12088 bytes |
| ELF machine / program header fields | machine 164; `e_phoff=0x34`, `e_phentsize=0x20`, `e_phnum=3`; no section headers |
| Program header 0, file offset `0x34` | non-LOAD; offset 0, file size `0x94`, flags `0x07000000` |
| Program header 1, file offset `0x54` | PT_LOAD; file offset `0x1000`, physical address `0x1000`, file/memory size `0x430`, flags `0x08000007` |
| Program header 2, file offset `0x74` | non-LOAD hash segment; file offset `0x2000`, file/memory size `0xf38`, flags `0x02000000` |

**Verified source:** `GPU_PAS_ID` is **13** in
`sources/linux/drivers/gpu/drm/msm/adreno/a6xx_gpu.c:17`, passed to
`adreno_zap_shader_load()` at line 1137. DT requests this Microsoft filename at
`sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:723`; hamoa
lines 4018–4019 reference `gpu_microcode_mem`, whose range is
`0x8d9fe000`, size `0x2000`, at hamoa lines 598–600.

**Inference from header and loader:** the monolithic ELF has the format
expected by `qcom_mdt_load()`. `mdt_header_valid()` checks ELF magic and header
bounds, not `e_machine` (`sources/linux/drivers/soc/qcom/mdt_loader.c:22`).
The hash segment is recognized by flags (lines 186–215). The single loadable
segment is relocatable and fully inside the file, and its aligned memory span
is **0x1000**, fitting the **0x2000** reservation (lines 110–138, 252–284).
`adreno_gpu.c:110` checks the memory size, line 141 passes PAS ID to MDT load,
and line 156 requests PAS authentication/reset.

**TBD:** successful TrustZone authentication for PAS 13, signing policy and
runtime load. The ELF header does not itself certify a PAS ID or a matching
device signature; a header-only check cannot prove that. Confirm with device
logs and successful protected GPU operation. Never ship `qcdxkmsucpurwa.mbn`
or replace this blob based only on a matching ELF machine field.
