# Qualcomm Spectra camera driver (downstream) built out of tree for the SP11 kernel.
# Build: hardware/cameras/spectra/rpm/build-spectra-rpm.sh [KVER]   (container, nothing on the host)
%{!?kver:%global kver 7.3.0-65.sp11.11.fc44.aarch64}
%global kverrel %(echo %{kver} | sed 's/\.aarch64$//')
%global cdrv_commit 08171ddc9d6ad81c13e6f1b362248d4736b0e804
%global cdrv_short 08171dd
# BTF for the module (project rule): needs the kernel's vmlinux with BTF (kernel-debuginfo).
%bcond_without btf
%global vmlinux_path /usr/lib/debug/lib/modules/%{kver}/vmlinux
# One out-of-tree module; stripped by hand (keeps .BTF), debuginfo of a kernel module is not split here.
%global debug_package %{nil}
%global __strip /bin/true

Name:           sp11-camera-spectra
Version:        1.0
Release:        1.git%{cdrv_short}%{?dist}
Summary:        Qualcomm Spectra camera driver for the Surface Pro 11
License:        GPL-2.0-only
URL:            https://github.com/qualcomm-linux/camera-driver
Source0:        camera-driver-%{cdrv_short}.tar.gz
Source1:        sp11-camera-spectra-guard
Source2:        sp11-camera-spectra.modprobe.conf
Source3:        sp11-camera-spectra-README
Patch0:         0001-Kbuild-default-the-out-of-tree-root-variables-and-cr.patch
Patch1:         0002-Kbuild-allow-building-without-Werror-CAMERA_WERROR-0.patch
ExclusiveArch:  aarch64

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  xz
BuildRequires:  elfutils-libelf-devel
BuildRequires:  kernel-devel-uname-r = %{kver}
%if %{with btf}
BuildRequires:  dwarves
BuildRequires:  kernel-debuginfo = %{kverrel}
%endif
Requires:       kernel-uname-r = %{kver}
Requires:       kmod
Requires(post):   kmod
Requires(postun): kmod
Provides:       kmod-camera_x1e80100 = %{version}-%{release}

%description
The downstream Qualcomm camera stack (CPAS, request manager, SMMU, sync,
CSIPHY, CSID, IFE, SFE, ICP, IPE, BPS, JPEG, sensor and CCI modules) as the
single kernel module camera_x1e80100, built against the kernel
%{kver}.

It binds only to the m15-spectra device tree (Qualcomm qcom,cam nodes) and
is mutually exclusive with the upstream CAMSS and CCI stack: a modprobe guard
refuses qcom_camss and i2c_qcom_cci when that device tree is active.

The module is not signed. The firmware qcom/x1e80100/CAMERA_ICP.mbn is not
part of this package.

%prep
%autosetup -n camera-driver-%{cdrv_short} -p1

%build
cp -a /usr/src/kernels/%{kver} %{_builddir}/kdev
%if %{with btf}
ln -sf %{vmlinux_path} %{_builddir}/kdev/vmlinux
%endif
# CAMERA_WERROR=0: warnings are printed but do not stop the build when the compiler differs from the kernel's
# (the verified build with gcc 16.2.1 is warning-free under -Werror).
make -C %{_builddir}/kdev M=$PWD CAMERA_ARCH=x1e80100 CAMERA_WERROR=0 modules
%if %{with btf}
readelf -S camera_x1e80100.ko | grep -q ' \.BTF' || { echo "no .BTF section in camera_x1e80100.ko"; exit 1; }
%endif

%install
install -d %{buildroot}/lib/modules/%{kver}/extra
strip --strip-debug -o camera_x1e80100.stripped.ko camera_x1e80100.ko
# xz like the kernel's own modules (CONFIG_MODULE_COMPRESS_XZ=y); crc32 is what the kernel-side xz build uses.
xz --check=crc32 --lzma2=dict=1MiB -c camera_x1e80100.stripped.ko > %{buildroot}/lib/modules/%{kver}/extra/camera_x1e80100.ko.xz
install -Dpm0755 %{SOURCE1} %{buildroot}%{_libexecdir}/sp11-camera-spectra-guard
install -Dpm0644 %{SOURCE2} %{buildroot}%{_prefix}/lib/modprobe.d/sp11-camera-spectra.conf
install -Dpm0644 %{SOURCE3} %{buildroot}%{_docdir}/%{name}/README

%post
/usr/sbin/depmod -a %{kver} >/dev/null 2>&1 || :

%postun
/usr/sbin/depmod -a %{kver} >/dev/null 2>&1 || :

%files
%license LICENSE.txt
%doc %{_docdir}/%{name}/README
/lib/modules/%{kver}/extra/camera_x1e80100.ko.xz
%{_libexecdir}/sp11-camera-spectra-guard
%{_prefix}/lib/modprobe.d/sp11-camera-spectra.conf

%changelog
* Sat Oct 31 2026 SP11 cameras worker <noreply@localhost> - 1.0-1.git08171dd.sp11
- First Spectra test build: camera-driver 08171dd + Kbuild patches 0001/0002, module for the SP11 kernel
