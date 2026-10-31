Name:           libssc
Version:        0.4.4
Release:        1.sp11%{?dist}
Summary:        Library to expose Qualcomm Sensor Core sensors to Linux

License:        GPL-3.0-or-later
URL:            https://codeberg.org/DylanVanAssche/libssc
Source0:        %{url}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  meson >= 1.4.0
BuildRequires:  gcc
BuildRequires:  pkgconfig(glib-2.0) >= 2.56
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(qmi-glib) >= 1.33.4
BuildRequires:  pkgconfig(libprotobuf-c)
BuildRequires:  protobuf-compiler
BuildRequires:  protobuf-c-compiler
# the build always generates the Python mocking server (not packaged here)
BuildRequires:  python3-devel

%description
libssc talks to the Qualcomm Sensor Core (SSC) on the ADSP or SDSP over QMI on
QRTR and exposes accelerometer, gyroscope, magnetometer, light, proximity and
compass sensors through a GObject API.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers and pkg-config file for building against libssc.

%package tools
Summary:        Command line client for libssc (ssccli)
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description tools
ssccli reads one SSC sensor and prints its measurements.

%prep
%autosetup -n libssc

%build
%meson
%meson_build

%install
%meson_install
# Mock SSC server and installed tests (need QRTR loopback and python protobuf): not shipped.
rm -rf %{buildroot}%{python3_sitelib}/ssc_server %{buildroot}%{_libexecdir}/installed-tests

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_libdir}/libssc.so.*

%files devel
%{_includedir}/libssc/
%{_libdir}/libssc.so
%{_libdir}/pkgconfig/libssc.pc

%files tools
%{_bindir}/ssccli

%changelog
* Sat Oct 31 2026 SP11 sensors worker <sp11@localhost> - 0.4.4-1.sp11
- Local build of libssc v0.4.4 (commit 0cf77b93b55752da34dca2dcecc06fca8665184b); not in Fedora 44
