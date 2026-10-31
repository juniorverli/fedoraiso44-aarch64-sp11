Name:           sp11-sensors
Version:        1.0
Release:        1%{?dist}
Summary:        Surface Pro 11 sensor integration: units, udev rules, test and collector

License:        GPL-3.0-or-later
BuildArch:      noarch
# All sources live in hardware/sensors/userspace of the project repository (copied into SOURCES by the build script).
Source1:        hexagonrpcd-sensors.service
Source2:        hexagonrpcd-sensors-sleep.service
Source3:        iio-sensor-proxy-sp11.conf
Source4:        61-sp11-fastrpc-adsp.rules
Source5:        81-sp11-iio-sensor-proxy-ssc.rules
Source6:        sp11-sensors-test
Source7:        sensors.sh
Source8:        50-sp11-sensors.preset
Source9:        sp11-sensors-README

BuildRequires:  systemd-rpm-macros
Requires:       hexagonrpcd
Requires:       libssc-tools
Requires:       iio-sensor-proxy >= 3.9
Requires:       fastrpc-services
Requires:       qrtr
Requires:       python3
%{?systemd_requires}

%description
Glue for the Surface Pro 11 sensors: the hexagonrpcd unit for the ADSP sensors
protection domain, the optional sleep hook, udev rules (fastrpc group access to
the ADSP node, SSC accelerometer for iio-sensor-proxy), an opt-in read-only test
and a log-collector drop-in. The package contains no Windows or Qualcomm
material. The units do nothing until the private sensor tree is installed
(sp11-sensors-install-private.sh).

%prep

%build

%install
install -D -p -m 0644 %{SOURCE1} %{buildroot}%{_unitdir}/hexagonrpcd-sensors.service
install -D -p -m 0644 %{SOURCE2} %{buildroot}%{_unitdir}/hexagonrpcd-sensors-sleep.service
install -D -p -m 0644 %{SOURCE3} %{buildroot}%{_unitdir}/iio-sensor-proxy.service.d/10-sp11-sensors.conf
install -D -p -m 0644 %{SOURCE4} %{buildroot}%{_udevrulesdir}/61-sp11-fastrpc-adsp.rules
install -D -p -m 0644 %{SOURCE5} %{buildroot}%{_udevrulesdir}/81-sp11-iio-sensor-proxy-ssc.rules
install -D -p -m 0755 %{SOURCE6} %{buildroot}%{_libexecdir}/sp11/sp11-sensors-test
install -D -p -m 0644 %{SOURCE7} %{buildroot}%{_sysconfdir}/sp11-log-collector.d/sensors.sh
install -D -p -m 0644 %{SOURCE8} %{buildroot}%{_presetdir}/50-sp11-sensors.preset
install -D -p -m 0644 %{SOURCE9} %{buildroot}%{_docdir}/%{name}/README

%post
%systemd_post hexagonrpcd-sensors.service hexagonrpcd-sensors-sleep.service
%udev_rules_update

%preun
%systemd_preun hexagonrpcd-sensors.service hexagonrpcd-sensors-sleep.service

%postun
%systemd_postun hexagonrpcd-sensors.service hexagonrpcd-sensors-sleep.service
%udev_rules_update

%files
%doc %{_docdir}/%{name}/README
%{_unitdir}/hexagonrpcd-sensors.service
%{_unitdir}/hexagonrpcd-sensors-sleep.service
%dir %{_unitdir}/iio-sensor-proxy.service.d
%{_unitdir}/iio-sensor-proxy.service.d/10-sp11-sensors.conf
%{_udevrulesdir}/61-sp11-fastrpc-adsp.rules
%{_udevrulesdir}/81-sp11-iio-sensor-proxy-ssc.rules
%dir %{_libexecdir}/sp11
%{_libexecdir}/sp11/sp11-sensors-test
%config(noreplace) %{_sysconfdir}/sp11-log-collector.d/sensors.sh
%{_presetdir}/50-sp11-sensors.preset

%changelog
* Sat Oct 31 2026 SP11 sensors worker <sp11@localhost> - 1.0-1
- Units, udev rules, preset, read-only test and collector drop-in for the SSC sensors
