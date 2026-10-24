#!/usr/bin/env bash
# Developer helper: a TOY ISO from a minimal Fedora 44 install root (about 600 MB, a few
# minutes, ~2 GB RAM), to exercise scripts/image-test-static.sh while the real image is not
# buildable. It is NOT livemedia-creator and NOT the M2 image: Fedora's own kernel and
# SP11_DTB=qcom/x1e80100-crd.dtb, the SP11 overlay, no GNOME. Its record says smoke=true.
#   scripts/image-container.sh run /sp11/image/tools/toy_iso.sh
set -euo pipefail
OUT=${SP11_OUT:-/out}
B=$OUT/image-work/toy2
name=sp11-toy-$(date -u +%Y%m%dT%H%M%SZ)
rm -rf "$B"; mkdir -p "$B"/{root,work/images,sq/LiveOS}
dnf -q -y --installroot="$B/root" --use-host-config --releasever=44 --setopt=install_weak_deps=False \
	--setopt=tsflags=nodocs install kernel-core kernel-modules-core dracut-live systemd qcom-firmware \
	rpm util-linux dtc pciutils usbutils coreutils-single bash findutils gzip xz zstd procps-ng >/dev/null
root=$B/root
kver=$(ls "$root/lib/modules")
cp -a /sp11/image/overlay/. "$root/"
mkdir -p "$root/etc/systemd/system/multi-user.target.wants" "$root/usr/share/sp11"
ln -s /usr/lib/systemd/system/sp11-log-collector.service "$root/etc/systemd/system/multi-user.target.wants/sp11-log-collector.service"
chmod 0755 "$root/usr/libexec/sp11-log-collector"
rpm --root "$root" -q kernel-core --qf '%{name}-%{version}-%{release}.%{arch}\n' >"$root/usr/share/sp11/kernel-nevra.txt"
# initramfs for the toy
mkdir -p "$root"/{proc,sys,dev}
mount --bind /proc "$root/proc"; mount --bind /sys "$root/sys"; mount --bind /dev "$root/dev"
trap 'umount "$root/dev" "$root/sys" "$root/proc" 2>/dev/null || true' EXIT
chroot "$root" dracut -q --no-hostonly --add dmsquash-live --omit plymouth --zstd -f /boot/initramfs-$kver.img "$kver"
umount "$root/dev" "$root/sys" "$root/proc"
cp "$root/lib/modules/$kver/vmlinuz" "$root/boot/vmlinuz-$kver"
# rootfs.img inside squashfs.img, as livemedia-creator makes it
truncate -s 1800M "$B/sq/LiveOS/rootfs.img"
mkfs.ext4 -q -F -L rootfs -d "$root" "$B/sq/LiveOS/rootfs.img"
mksquashfs "$B/sq" "$B/work/images/install.img" -comp zstd -quiet -no-progress
# template run, as pylorax/creator.py make_livecd does
ln -s "$B/work/images" "$root/images"
mkdir -p "$root/tmp"; rm -rf "$root/tmp/config_files"
cp -a /sp11/image/lorax-templates/live/config_files "$root/tmp/config_files"
mkdir -p "$root/boot/efi/EFI/fedora" "$root/usr/share/grub"
for f in shimaa64.efi mmaa64.efi gcdaa64.efi; do cp /boot/efi/EFI/fedora/$f "$root/boot/efi/EFI/fedora/"; done
cp /usr/share/grub/unicode.pf2 "$root/usr/share/grub/"
export SP11_DTB=${SP11_DTB:-qcom/x1e80100-crd.dtb}
python3 - "$B" "$root" <<'PY'
import sys
from pylorax import ArchData, DataHolder
from pylorax.treebuilder import TreeBuilder
b, root = sys.argv[1:3]
tb = TreeBuilder(product=DataHolder(name="Fedora", version="44", release="toy", variant="", bugurl="", isfinal=False),
                 arch=ArchData("aarch64"), inroot=root, outroot=f"{b}/work", runtime="images/install.img",
                 isolabel="SP11-Fedora-44", domacboot=False, templatedir="/sp11/image/lorax-templates/live/", extra_boot_args="")
tb.build()
PY
mkdir -p "$OUT/iso"
cp "$B/work/images/boot.iso" "$OUT/iso/$name.iso"
sha=$(sha256sum "$OUT/iso/$name.iso" | cut -d' ' -f1)
mkdir -p "$B/grubcheck"
mcopy -n -i "$B/work/images/efiboot.img" ::EFI/BOOT/grub.cfg "$B/grubcheck/esp-grub.cfg"
cat >"$OUT/iso/$name.json" <<JSON
{"name":"$name","kind":"toy","smoke":true,"iso_sha256":"$sha","kernel_nevra":"$(cat "$root/usr/share/sp11/kernel-nevra.txt")","dtb":"$SP11_DTB"}
JSON
echo "toy ISO: $OUT/iso/$name.iso"
