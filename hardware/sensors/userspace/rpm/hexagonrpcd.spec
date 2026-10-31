Name:           hexagonrpcd
Version:        0.5.0
Release:        1.sp11%{?dist}
Summary:        FastRPC file and memory server for Qualcomm Hexagon DSPs

# COPYING is GPL-3.0; every source header says "either version 3 of the License, or (at your option) any later version"
License:        GPL-3.0-or-later
URL:            https://github.com/linux-msm/hexagonrpc
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/hexagonrpc-%{version}.tar.gz
Source1:        hexagonrpcd.sysusers
# SP11: the ADSP sensor framework writes its registry through FastRPC; upstream serves everything read-only.
Patch0001:      hexagonrpc-0001-apps_std-write-support.patch
# sscregistrygen crashes on a truncated vendor JSON file (the Surface Pro 11 package has one).
Patch0002:      hexagonrpc-0002-sscregistrygen-skip-invalid-json.patch

BuildRequires:  meson >= 1.1
BuildRequires:  gcc
BuildRequires:  pkgconfig(json-c)
BuildRequires:  systemd-rpm-macros

%description
hexagonrpcd serves files (sensor configuration and registry, SoC identity, DSP
libraries, audio calibration) and memory to the remote processors of Qualcomm
SoCs over the FastRPC kernel interface. With -s it attaches to the sensors
protection domain of the ADSP, which the Qualcomm Sensor Core (SSC) uses.

This build carries a local patch that lets the SSC framework write its registry
files below the served registry directory (open for writing, write, sync, remove),
and installs sscregistrygen, the upstream tool that generates the registry files
from the vendor JSON configuration.

%prep
%autosetup -n hexagonrpc-%{version} -p1

%build
%meson
%meson_build

%install
%meson_install
# Upstream installs three units into %%{_libdir}/systemd/system (wrong directory on Fedora, user and root
# directory not configurable). The unit of this image is in the sp11-sensors package.
rm -rf %{buildroot}%{_libdir}/systemd
# No headers are installed, so the unversioned library link has no use.
rm -f %{buildroot}%{_libdir}/libhexagonrpc.so
# Upstream builds sscregistrygen but does not install it.
install -D -p -m 0755 %{_vpath_builddir}/tools/sscregistrygen %{buildroot}%{_bindir}/sscregistrygen
install -D -p -m 0644 %{SOURCE1} %{buildroot}%{_sysusersdir}/hexagonrpcd.conf

%check
%meson_test

%files
%license COPYING
%doc README.md
%{_bindir}/hexagonrpcd
%{_bindir}/sscregistrygen
%{_libdir}/libhexagonrpc.so.0.5
%{_libexecdir}/hexagonrpc/
%{_mandir}/man1/hexagonrpcd.1*
%{_sysusersdir}/hexagonrpcd.conf

%changelog
* Sat Oct 31 2026 SP11 sensors worker <sp11@localhost> - 0.5.0-1.sp11
- Local build of linux-msm/hexagonrpc v0.5.0 (commit 435ed1cd68e20f8a9fe4871233ed1f8ce7ccf9e8)
- Patch 0001: writable registry files for the ADSP sensor framework
- Patch 0002: sscregistrygen skips invalid JSON; install sscregistrygen
- Drop the upstream units; add sysusers file for the hexagonrpcd user
