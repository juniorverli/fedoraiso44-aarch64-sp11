# iptsd for Fedora 44 aarch64

## Availability and reference package

**Verified repository query, 2026-10-29:** a clean
`registry.fedoraproject.org/fedora:44` container enabled `fedora`, `updates`
and `fedora-cisco-openh264`. The following exact-name query succeeded with
no matches:

```sh
dnf -q repoquery --available --queryformat '%{name}-%{evr}.%{arch}' iptsd
```

A second query for `*ipts*` returned unrelated packages (including `iptstate`),
not `iptsd`. Output is private build/research material at
`out/agents/touch-ref/f44-iptsd-query.txt`. Therefore there is **no Fedora f44
package/version to name** in those official aarch64 repositories. Do not
confuse the linux-surface third-party repository with Fedora's repositories.

The actual working reference packages unmodified **iptsd 3.1.0-1** for aarch64:
[`dwhinham/archlinux-repo/iptsd/PKGBUILD`](https://github.com/dwhinham/archlinux-repo/blob/b11dffd3686e542609843405314731abae3c60e0/iptsd/PKGBUILD).
It builds the release tarball with no SP11 patch or extra preset. Its source
SHA-256 is
`af0aab95387a5107dfa8ac1ef90a29289f6b9d06e1a59121c9e5e732b27a266c`.

## Fedora-native request

Build **iptsd-3.1.0-1.fc44.aarch64.rpm** locally with Fedora's
`rpmbuild`/`mock` and dependency packages; install it through the image's
normal RPM transaction. This is a proposed local NEVRA, not an official
Fedora package claim. Use upstream's
[`iptsd.spec`](https://github.com/linux-surface/iptsd/blob/a83bc1232f7096f8b33b50fdbda249cd640de670/iptsd.spec)
as the packaging base, replacing its CI-only `Source: {{{ create_tarball }}}`
with the pinned v3.1.0 source archive. Sources must centrally pin it first.

Upstream source commit: `a83bc1232f7096f8b33b50fdbda249cd640de670`.
Retain Meson build/test macros, the udev rule, template service, default
configuration and presets. Use Fedora build dependencies, disable fallback
network downloads, and let the image worker resolve any Fedora dependency
version incompatibility. Do not install an Arch binary or an x86_64 RPM.
The [upstream README](https://github.com/linux-surface/iptsd/blob/a83bc1232f7096f8b33b50fdbda249cd640de670/README.md)
explains that RPM installs carry the proper service/SELinux file integration;
manual `ninja install` is unnecessary here.

## Device configuration

**Verified reference:** no SP11-specific configuration is added by the Arch
package. Start with the upstream `/etc/iptsd.conf` defaults and packaged udev
rule. Do **not** invent a vendor/product match, orientation, dimensions or
contact thresholds from the Windows extension package names.

**Verified upstream implementation:**

- `src/ipts/device.hpp:135–160` reads metadata through the HID metadata
  feature report. `:163–184` selects multitouch/heatmap mode using a HID
  feature request; this is runtime input configuration, not firmware flashing.
- `src/core/linux/config-loader.hpp:35–42` initializes width, height and
  axis inversion from that metadata, then reads presets and local overrides.
- `etc/udev/50-iptsd.rules.in` uses `iptsd-check-device`, then starts
  `iptsd@<escaped-hidraw-path>.service`. No standalone `iptsd.service` or
  manual hidraw number should be hardcoded.
- `src/core/generic/config.hpp` enables touchscreen and stylus processing
  by default. The v3.1.0 preset list contains no Surface Pro 11 entry.

**Inference for our unit:** default metadata-driven configuration should
match the working reference. Device confirmation is pending. Collect the
iptsd service journal, libinput device dimensions/orientation and evtest
capabilities; if metadata is absent or dimensions are zero, leave that as an
explicit configuration blocker and derive a narrowly matched override from
actual HID/device evidence. No speculative preset is supplied.

The image needs `uinput` available (`CONFIG_INPUT_UINPUT=m` plus the normal
module loading; if necessary, `/etc/modules-load.d/iptsd.conf` containing
`uinput`), `CONFIG_HIDRAW=y`, the SPI-HID OF module alias, and Fedora's
`libinput-utils` and `evtest` packages. HID rebind after a reset is necessary
so the udev-started daemon can restore its lost heatmap mode. That behavior
is in patch 0019. No iptsd command that changes modes is part of the read-only
collector.
