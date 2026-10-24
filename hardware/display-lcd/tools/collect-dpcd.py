#!/usr/bin/env python3
"""Read DPCD capability ranges on a future device boot; never write AUX.

Usage: sudo python3 collect-dpcd.py /path/to/logs/display-lcd
Dump every AUX adapter because MSM uses the same name for multiple ports.
The saved sysfs paths allow the eDP adapter to be identified afterwards.
"""

import os
from pathlib import Path
import sys


def collect(destination):
    destination.mkdir(parents=True, exist_ok=True)
    adapters = sorted(Path("/dev").glob("drm_dp_aux*"))
    if not adapters:
        raise SystemExit("No AUX devices; check CONFIG_DRM_DP_AUX_CHARDEV and driver probe logs")
    for adapter in adapters:
        info = [f"adapter: {adapter}"]
        sysfs = Path("/sys/class/drm_dp_aux_dev") / adapter.name
        info.append(f"sysfs: {sysfs.resolve()}")
        try:
            info.append(f"name: {(sysfs / 'name').read_text().strip()}")
            descriptor = os.open(adapter, os.O_RDONLY | os.O_CLOEXEC)
        except OSError as error:
            info.append(f"open/name error: {error}")
        else:
            try:
                for offset in (0x000, 0x700):
                    try:
                        data = os.pread(descriptor, 256, offset)
                        if len(data) != 256:
                            info.append(f"{offset:#05x}: short read, {len(data)} / 256 bytes")
                        (destination / f"{adapter.name}-{offset:03x}.bin").write_bytes(data)
                        info.append(f"{offset:#05x}: {len(data)} bytes")
                    except OSError as error:
                        info.append(f"{offset:#05x}: read error: {error}")
            finally:
                os.close(descriptor)
        (destination / f"{adapter.name}.txt").write_text("\n".join(info) + "\n")
        print("\n".join(info))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    collect(Path(sys.argv[1]))
