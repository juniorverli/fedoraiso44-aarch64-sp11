# sp11-live.ks: Fedora 44 Workstation live image for the Surface Pro 11 (X1P64100, Denali LCD).
#
# Built by scripts/image-build.sh with
#   livemedia-creator --no-virt --make-iso --ks <resolved copy of this file> ...
# inside the Fedora 44 aarch64 container of scripts/image-container.sh (/sp11 = this
# repository, /out = shared out/ directory). It does not run anywhere else.
#
# ORIGIN (Fedora-native, D12). Fedora no longer ships kickstarts for Workstation live media:
# the Pagure project fedora-kickstarts was retired and its content moved to
# https://forge.fedoraproject.org/releng/spin-kickstarts, which was itself retired on
# 2025-12-17 (last commit of the f43 branch: d1bbfe1211ead018371627991c529b4910f1bbd1,
# 2025-09-30). Fedora 44 live media are built with kiwi
# (https://pagure.io/fedora-kiwi-descriptions, branch f44, commit
# dfc49a5a10f69941179fdadd96aa6a5984f7c677). Decision D11 asks for livemedia-creator, so
# this file is the flattened union of three files of the f43 branch of spin-kickstarts,
# the newest kickstart Fedora published:
#   fedora-live-workstation.ks  (gnome-initial-setup, anaconda-webui, livesys session)
#   fedora-live-base.ks         (live basics, anaconda, dracut-live, livesys-scripts)
#   fedora-workstation-common.ks (@^workstation-product-environment and exclusions)
# plus fedora-repo.ks / fedora-repo-not-rawhide.ks. Differences against those files are
# marked "SP11:" below. The kiwi f44 description was read to check the package set
# (GNOME live: components/desktops/gnome.xml, teams/workstation.xml); no package was taken
# from it that the kickstart does not already select.
#
# Placeholders replaced by scripts/image-build.sh (never edit the resolved copy):
#   @SP11_KERNEL_REPO@       the local repository line for out/rpms (empty for a --smoke build)
#   @SP11_EXCLUDE_KERNEL@    --excludepkgs=... on the Fedora repos (empty for a --smoke build)
#   @SP11_REQUIRE_FIRMWARE@  1 = fail when /out/firmware-root is missing, 0 = skip (--smoke)

lang en_US.UTF-8
keyboard us
timezone US/Eastern
# SP11: see image/README.md "Open points": labels cannot be written inside the WSL2 build container.
selinux --permissive
firewall --enabled --service=mdns
xconfig --startxonboot
zerombr
clearpart --all
part / --size 8576 --fstype ext4
services --enabled=NetworkManager,ModemManager --disabled=sshd
network --bootproto=dhcp --device=link --activate
rootpw --lock --iscrypted locked
shutdown

# Repositories. SP11: Fedora 44 hard-coded (no $releasever), Fedora's kernels are excluded
# when our own RPMs are used, and the local repository of our kernel RPMs is added.
repo --name=fedora --mirrorlist=https://mirrors.fedoraproject.org/mirrorlist?repo=fedora-44&arch=aarch64 @SP11_EXCLUDE_KERNEL@
repo --name=updates --mirrorlist=https://mirrors.fedoraproject.org/mirrorlist?repo=updates-released-f44&arch=aarch64 @SP11_EXCLUDE_KERNEL@
@SP11_KERNEL_REPO@
url --mirrorlist=https://mirrors.fedoraproject.org/mirrorlist?repo=fedora-44&arch=aarch64

%packages
# --- fedora-live-base.ks
kernel
kernel-core
kernel-modules
kernel-modules-core
kernel-modules-extra

# The point of a live image is to install
anaconda-install-env-deps
anaconda-live
@anaconda-tools
# Anaconda has a weak dep on this and we don't want it on livecds
-fcoe-utils
-device-mapper-multipath
-sdubby

# Need aajohan-comfortaa-fonts for the SVG rnotes images
aajohan-comfortaa-fonts

# Without this, initramfs generation during live image creation fails: #1242586
dracut-live

# anaconda needs the locales available to run for different locales
glibc-all-langpacks

# provide the livesys scripts
livesys-scripts

# --- fedora-workstation-common.ks
# Exclude unwanted groups that fedora-live-base.ks pulls in
-@dial-up
-@input-methods
-@standard

# Install workstation-product-environment to resolve RhBug:1891500
@^workstation-product-environment

# Exclude unwanted packages from @anaconda-tools group
-gfs2-utils
-reiserfs-utils

# Exclude extra unwanted packages
-python3-botocore

# --- fedora-live-workstation.ks
gnome-initial-setup
anaconda-webui

# --- SP11: what livemedia-creator's live templates need to make the ISO
# (lorax live-install.tmpl, aarch64.tmpl: boot/efi/EFI/*/gcdaa64.efi, shim, grub for the install)
grub2-efi-aa64
grub2-efi-aa64-cdboot
shim-aa64
efibootmgr
# SP11: ausearch for the SELinux AVC capture of the log collector (D15)
audit
grub2-tools
grub2-tools-extra

# --- SP11: task list of agents/workers/image.md and the "Requests" of the dossiers
# firmware worker request 1: linux-firmware does not pull in qcom-firmware; it carries
# qcom/gen70500_sqe.fw.xz and qcom/gen70500_gmu.bin.xz (GPU).
qcom-firmware
linux-firmware
mesa-dri-drivers
mesa-vulkan-drivers
vulkan-tools
glx-utils
glmark2
# modetest
drm-utils
# edid-decode (Fedora ships it inside v4l-utils); qrtr-lookup and qrtr-cfg
v4l-utils
qrtr
# Collector and debugging tools (read-only use)
dtc
pciutils
usbutils
bpftool
mtools
dosfstools
# pd-mapper and qrtr-ns do not exist in Fedora 44 (firmware worker request 4): the kernel has
# an in-kernel protection domain mapper and QRTR name service. Not installed on purpose.

# --- SP11: no splash screen anywhere (D9). Soft dependencies only; the dry-run resolution of
# this package set with these exclusions succeeded on Fedora 44.
-plymouth
-plymouth-scripts
-plymouth-system-theme
-plymouth-graphics-libs
-plymouth-core-libs
-plymouth-plugin-label
-plymouth-plugin-two-step
-plymouth-theme-spinner
%end

# ---------------------------------------------------------------------------
# SP11: files that come from the repository and from out/ (copied from outside the chroot).
%post --nochroot --erroronfail --log=/tmp/sp11-post-nochroot.log
set -eu
root=${INSTALL_ROOT:-${ANACONDA_ROOT_PATH:-/mnt/sysroot}}
[ -d "$root/usr" ] || { echo "SP11: cannot find the install root (got $root)" >&2; exit 1; }

# collector, services, dracut and GRUB defaults
cp -a /sp11/image/overlay/. "$root/"

# firmware: staged tree of scripts/firmware-stage.sh (firmware worker request 2)
if [ -d /out/firmware-root/lib/firmware ]; then
    mkdir -p "$root/usr/lib/firmware"
    cp -a /out/firmware-root/lib/firmware/. "$root/usr/lib/firmware/"
    ( cd /out/firmware-root/lib/firmware && find . -type f | sort | xargs sha256sum ) \
        > /out/image-work/firmware-installed.sha256
elif [ "@SP11_REQUIRE_FIRMWARE@" = 1 ]; then
    echo "SP11: /out/firmware-root/lib/firmware is missing; run scripts/firmware-stage.sh" >&2
    exit 1
else
    echo "SP11: smoke build, no staged firmware" >&2
fi
%end

%post --erroronfail --log=/root/sp11-post.log
set -eu

# livesys: GNOME session (fedora-live-workstation.ks)
sed -i 's/^livesys_session=.*/livesys_session="gnome"/' /etc/sysconfig/livesys

# --- fedora-live-base.ks %post (unchanged except where marked)
systemctl enable livesys.service
systemctl enable livesys-late.service
systemctl enable tmp.mount
cat >> /etc/fstab << EOF
vartmp   /var/tmp    tmpfs   defaults   0  0
EOF
rm -f /var/lib/rpm/__db*
rpm -qa --qf '%{size}\t%{name}-%{version}-%{release}.%{arch}\n' | sort -rn
rm -f /var/lib/rpm/__db*
/usr/bin/mandb
rm -f /core*
rm -f /var/lib/systemd/random-seed
echo 'File created by kickstart. See systemd-update-done.service(8).' \
    | tee /etc/.updated >/var/.updated
rm -f /boot/*-rescue*
systemctl disable network
rm -f /etc/machine-id
touch /etc/machine-id

# --- SP11
chmod 0755 /usr/libexec/sp11-log-collector
systemctl enable sp11-log-collector.service
systemctl mask plymouth-start.service plymouth-quit.service plymouth-quit-wait.service \
    plymouth-read-write.service plymouth-switch-root.service plymouth-halt.service \
    plymouth-reboot.service plymouth-poweroff.service plymouth-kexec.service 2>/dev/null || true

# Early display drivers (names = Kbuild object names of the symbols in kernel/config/sp11.config;
# verified against sources/linux v7.3). dracut aborts when an add_drivers name does not exist,
# so only modules this kernel has are listed; check 5 of image-test-static.sh looks them up.
kver=$(ls /lib/modules | head -n1)
early=
for m in msm panel-edp phy-qcom-edp drm_dp_aux_bus pwm_bl dispcc-x1e80100; do
    modinfo -k "$kver" "$m" >/dev/null 2>&1 && early="$early $m"
done
echo "add_drivers+=\" $early \"" > /etc/dracut.conf.d/91-sp11-drivers.conf

# Package list of this image, kept in the image and read by scripts/image-build.sh
mkdir -p /usr/share/sp11
rpm -qa --qf '%{name}-%{epochnum}:%{version}-%{release}.%{arch}\n' | sort > /usr/share/sp11/packages.txt
rpm -q kernel-core --qf '%{name}-%{version}-%{release}.%{arch}\n' > /usr/share/sp11/kernel-nevra.txt
%end

# SP11: hand the package list to the build script (outside the chroot)
%post --nochroot --log=/tmp/sp11-post-nochroot2.log
root=${INSTALL_ROOT:-${ANACONDA_ROOT_PATH:-/mnt/sysroot}}
cp -f "$root/usr/share/sp11/packages.txt" /out/image-work/packages.txt || true
cp -f "$root/usr/share/sp11/kernel-nevra.txt" /out/image-work/kernel-nevra.txt || true
%end
