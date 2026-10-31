# Based on the Fedora rawhide spec of iio-sensor-proxy 3.9 (src.fedoraproject.org/rpms/iio-sensor-proxy),
# which builds with -Dssc-support=disabled because libssc is not in Fedora. This local build enables it.
Name:           iio-sensor-proxy
Version:        3.9
Release:        1.sp11%{?dist}
Summary:        IIO accelerometer sensor to input device proxy (with Qualcomm SSC support)

# tests/unittest_inspector.py is LGPL-2.1-or-later but it is not packaged
License:        GPL-3.0-or-later
URL:            https://gitlab.freedesktop.org/hadess/iio-sensor-proxy
Source0:        %{url}/-/archive/%{version}/%{name}-%{version}.tar.bz2

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  pkgconfig(udev)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(polkit-gobject-1)
BuildRequires:  pkgconfig(libssc) >= 0.2.1
BuildRequires:  systemd
%{?systemd_requires}

%description
iio-sensor-proxy publishes accelerometer orientation, ambient light and compass
heading on D-Bus. This build includes the libssc drivers for the sensors of
Qualcomm SoCs (SSC, 3.9 and later). Version 3.9 enables the SSC light and
compass drivers from udev; the accelerometer needs the rule of the sp11-sensors
package.

%prep
%autosetup

%build
%meson -Dgtk_doc=false -Dgtk-tests=false -Dssc-support=enabled
%meson_build

%install
%meson_install

%post
%systemd_post %{name}.service

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun_with_restart %{name}.service

%files
%license COPYING
%doc README.md NEWS
%{_bindir}/monitor-sensor
%{_libexecdir}/%{name}
%{_unitdir}/%{name}.service
%{_udevrulesdir}/*-%{name}.rules
%{_datadir}/dbus-1/system.d/net.hadess.SensorProxy.conf
%{_datadir}/polkit-1/actions/net.hadess.SensorProxy.policy

%changelog
* Sat Oct 31 2026 SP11 sensors worker <sp11@localhost> - 3.9-1.sp11
- iio-sensor-proxy 3.9 (tag commit 0085ddf8ecb173a1c5fcf2344aa40e561125354f) with -Dssc-support=enabled
