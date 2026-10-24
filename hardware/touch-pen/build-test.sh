#!/usr/bin/env bash
# Software-only, minimal ARM64 compatibility build; not the release RPM config.
set -euo pipefail

project=$(cd -- "$(dirname -- "$0")/../.." && pwd)
kernel=$(realpath "$project/out/linux/touch-pen")
output=$(realpath "$project/out")/build/touch-pen
mkdir -p "$output"

flock "$project/out/.kernel-build.lock" \
    docker run --rm -i --network=none --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$kernel,dst=/src" \
    --mount "type=bind,src=$output,dst=/build" \
    --workdir /src sp11-kernel-fc44:latest bash -s <<'BUILD'
set -euo pipefail
cat /etc/fedora-release
gcc --version | head -1
pahole --version
make O=/build/kbuild ARCH=arm64 allnoconfig
scripts/config --file /build/kbuild/.config \
    -e EXPERT -e MODULES -e BPF -e BPF_SYSCALL -e DEBUG_KERNEL \
    -e FTRACE -e FTRACE_SYSCALLS \
    -d DEBUG_INFO_NONE -e DEBUG_INFO_DWARF5 \
    -e DEBUG_INFO_BTF -e DEBUG_INFO_BTF_MODULES \
    -e ARCH_QCOM -e OF -e ACPI -e PCI -e EFI -e PM -e PM_SLEEP -e SUSPEND \
    -e INPUT -e HID_SUPPORT -m HID -m HID_GENERIC -m HID_MULTITOUCH \
    -e SPI -m SPI_HID -m SPI_HID_ACPI -m SPI_HID_OF \
    -e GPIOLIB -e REGULATOR -m REGULATOR_FIXED_VOLTAGE \
    -m DRM -e DRM_PANEL -m QCOM_GENI_SE -m SPI_QCOM_GENI
make O=/build/kbuild ARCH=arm64 olddefconfig
for setting in DEBUG_INFO_BTF=y DEBUG_INFO_BTF_MODULES=y SPI_HID_OF=m \
    SPI_HID_ACPI=m SPI_HID_CORE=m DRM=m DRM_PANEL=y SPI_QCOM_GENI=m \
    TRACEPOINTS=y TRACING=y; do
    if ! grep -qx "CONFIG_$setting" /build/kbuild/.config; then
        echo "Required config missing: CONFIG_$setting" >&2
        exit 1
    fi
done
make O=/build/kbuild ARCH=arm64 -j4 vmlinux modules
# Recompile the new transport/frontends with extra warnings and real tracepoints.
make O=/build/kbuild ARCH=arm64 -j4 W=1 drivers/hid/spi-hid/
readelf -SW /build/kbuild/vmlinux | grep '\.BTF'
for module in spi-hid spi-hid-of spi-hid-acpi; do
    readelf -SW "/build/kbuild/drivers/hid/spi-hid/$module.ko" | grep '\.BTF'
done
BUILD
