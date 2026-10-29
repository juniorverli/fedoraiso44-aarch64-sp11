#!/usr/bin/env python3
"""Read-only SSAM requests through /dev/surface/aggregator (ec-sam collector tool).

Sends only the requests in ALLOW, all of which are reads that Windows or the Linux
drivers already send. Anything else is refused before the ioctl (risk S3: no writes
to the EC). Needs root and `modprobe surface_aggregator_cdev`. It captures no
keystrokes and prints no serial numbers.

  ssam-ro.py --list
  ssam-ro.py pos-sources | pos-posture [source] | kip-cover | kip-conn | fan-rpm
  ssam-ro.py all
"""
import ctypes
import fcntl
import struct
import sys

DEV = "/dev/surface/aggregator"
HAS_RESPONSE = 0x01

# name: (target_category, target_id, instance_id, command_id, payload_len, what)
ALLOW = {
    "pos-sources": (0x26, 0x01, 0x00, 0x01, 0, "POS: list of posture sources (le32 count, le32 ids)"),
    "pos-posture": (0x26, 0x01, 0x00, 0x02, 4, "POS: posture of source N (payload le32 source)"),
    "kip-cover":   (0x0E, 0x01, 0x00, 0x1D, 0, "KIP: cover state (u8)"),
    "kip-conn":    (0x0E, 0x01, 0x00, 0x2C, 0, "KIP: connection flag (u8)"),
    "fan-rpm":     (0x05, 0x01, 0x01, 0x01, 0, "FAN: speed in RPM (le16), surface_fan read request"),
}


def ioctl_number(size):
    # _IOWR(0xA5, 1, struct ssam_cdev_request)
    return (3 << 30) | (size << 16) | (0xA5 << 8) | 1


class Part(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("data", ctypes.c_uint64), ("length", ctypes.c_uint16), ("pad", ctypes.c_uint8 * 6)]


class Request(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("tc", ctypes.c_uint8), ("tid", ctypes.c_uint8), ("cid", ctypes.c_uint8),
                ("iid", ctypes.c_uint8), ("flags", ctypes.c_uint16), ("status", ctypes.c_int16),
                ("payload", Part), ("response", Part)]


assert ctypes.sizeof(Request) == 40


def send(fd, name, payload=b""):
    tc, tid, iid, cid, plen, _ = ALLOW[name]
    if len(payload) != plen:
        raise SystemExit(f"{name}: payload must be {plen} bytes")
    pbuf = ctypes.create_string_buffer(payload, max(plen, 1))
    rbuf = ctypes.create_string_buffer(256)
    req = Request(tc, tid, cid, iid, HAS_RESPONSE, 0,
                  Part(ctypes.addressof(pbuf), plen), Part(ctypes.addressof(rbuf), 256))
    try:
        fcntl.ioctl(fd, ioctl_number(ctypes.sizeof(req)), req)
    except OSError as e:
        return f"{name}: ioctl failed: {e}"
    if req.status:
        return f"{name}: request status {req.status}"
    if req.response.length > len(rbuf):
        return f"{name}: invalid response length {req.response.length}"
    return f"{name}: {rbuf.raw[:req.response.length].hex()} ({req.response.length} bytes)"


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--list":
        for k, v in ALLOW.items():
            print(f"{k:12} {v[0]:02x}/{v[1]:02x}/{v[2]:02x}/{v[3]:02x}  {v[5]}")
        return 0
    names = list(ALLOW) if argv[0] == "all" else [argv[0]]
    if any(n not in ALLOW for n in names):
        raise SystemExit(f"refused: {argv[0]} is not in the read-only allow-list (see --list)")
    with open(DEV, "rb", buffering=0) as f:
        for n in names:
            if n == "pos-posture":
                srcs = [int(argv[1])] if len(argv) > 1 else [0, 3]
                for s in srcs:
                    print(f"source {s}: " + send(f.fileno(), n, struct.pack("<I", s)))
            else:
                print(send(f.fileno(), n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
