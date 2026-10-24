#!/usr/bin/env python3
"""Build a toy ISO with the SP11 lorax templates (no package install, a few MB, seconds).

Proves that image/lorax-templates renders, that the DTB is found and copied, that
mk-efiboot.sh works without a vfat mount, and that xorrisofs produces the hybrid layout.
Run inside the container: scripts/image-container.sh run python3 /sp11/image/tools/template_selftest.py
Output: /out/image-work/toy/result/images/boot.iso
"""
import os
import shutil
import subprocess
import sys

from pylorax import ArchData, DataHolder
from pylorax.treebuilder import TreeBuilder

base = "/out/image-work/toy"
shutil.rmtree(base, ignore_errors=True)
inroot, outroot = f"{base}/inroot", f"{base}/work"
kver = "7.3.0-1.fc44.aarch64"
for d in (f"{inroot}/boot/efi/EFI/fedora", f"{inroot}/lib/modules/{kver}/dtb/qcom", f"{inroot}/usr/share/grub",
          f"{outroot}/images", f"{inroot}/tmp"):
    os.makedirs(d, exist_ok=True)
for f in ("shimaa64.efi", "mmaa64.efi", "gcdaa64.efi"):
    shutil.copy(f"/boot/efi/EFI/fedora/{f}", f"{inroot}/boot/efi/EFI/fedora/{f}")
shutil.copy("/usr/share/grub/unicode.pf2", f"{inroot}/usr/share/grub/unicode.pf2")
open(f"{inroot}/boot/vmlinuz-{kver}", "wb").write(b"\0" * 4096)
open(f"{inroot}/boot/initramfs-{kver}.img", "wb").write(b"\0" * 4096)
dts = f"{base}/denali.dts"
open(dts, "w").write('/dts-v1/; / { model = "toy"; compatible = "microsoft,denali-lcd"; };')
subprocess.check_call(["dtc", "-I", "dts", "-O", "dtb", "-o", f"{inroot}/lib/modules/{kver}/dtb/qcom/x1p64100-microsoft-denali.dtb", dts])
shutil.copytree("/sp11/image/lorax-templates/live/config_files", f"{inroot}/tmp/config_files")
open(f"{outroot}/images/install.img", "wb").write(b"\0" * 8192)
os.symlink(f"{outroot}/images", f"{inroot}/images")  # as make_livecd does

arch = ArchData("aarch64")
product = DataHolder(name="Fedora", version="44", release="toy", variant="", bugurl="", isfinal=False)
tb = TreeBuilder(product=product, arch=arch, inroot=inroot, outroot=outroot, runtime="images/install.img",
                 isolabel="SP11-Fedora-44", domacboot=False, templatedir="/sp11/image/lorax-templates/live/",
                 extra_boot_args="")
tb.build()
print("toy ISO:", f"{outroot}/images/boot.iso")
