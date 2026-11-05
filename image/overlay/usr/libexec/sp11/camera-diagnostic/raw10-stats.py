#!/usr/bin/env python3
"""Report CSI-2 packed RAW10 statistics per sensor pixel parity in five ROIs.

Supply the accepted capture size and row stride, not the requested values. The
four parity positions are not assigned colours: use separate red/blue targets
to verify the physical CFA. This reads a saved file and never opens a camera.
"""
import argparse
import json
import math
from pathlib import Path


def unpack_pixel(data, stride, x, y):
    start = y * stride + (x // 4) * 5
    return (data[start + x % 4] << 2) | ((data[start + 4] >> (2 * (x % 4))) & 3)


def statistics(data, width, height, stride, roi):
    if width <= 0 or height <= 0 or width % 4 or stride < width * 5 // 4:
        raise ValueError('invalid dimensions or stride for packed RAW10')
    if len(data) < stride * height:
        raise ValueError('file is shorter than stride times height')
    x0, y0, rw, rh = roi
    if min(x0, y0) < 0 or min(rw, rh) < 2 or x0 + rw > width or y0 + rh > height:
        raise ValueError('ROI outside frame or smaller than 2x2')
    accum = [[0, 0, 0, 1023, 0, 0] for _ in range(4)]  # n, sum, sum squares, min, max, clipped
    for y in range(y0, y0 + rh):
        for x in range(x0, x0 + rw):
            val = unpack_pixel(data, stride, x, y)
            a = accum[(y % 2) * 2 + x % 2]
            a[0] += 1
            a[1] += val
            a[2] += val * val
            a[3] = min(a[3], val)
            a[4] = max(a[4], val)
            a[5] += val == 1023
    result = {}
    for i, (n, total, squares, low, high, clipped) in enumerate(accum):
        mean = total / n
        result[f'y{i // 2}x{i % 2}'] = {
            'count': n, 'mean': mean, 'stddev': math.sqrt(max(0, squares / n - mean * mean)),
            'min': low, 'max': high, 'fraction_at_1023': clipped / n}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('raw', type=Path)
    p.add_argument('--width', type=int, required=True)
    p.add_argument('--height', type=int, required=True)
    p.add_argument('--stride', type=int, required=True)
    p.add_argument('--roi-size', type=int, default=128)
    args = p.parse_args()
    w, h, size = args.width, args.height, args.roi_size
    if size < 2 or size > min(w, h):
        p.error('ROI size must be at least 2 and fit within the frame')
    try:
        data = args.raw.read_bytes()
        rois = {'top_left': (0, 0), 'top_right': (w - size, 0),
                'centre': ((w - size) // 2, (h - size) // 2),
                'bottom_left': (0, h - size), 'bottom_right': (w - size, h - size)}
        result = {'file': str(args.raw), 'file_bytes': len(data), 'width': w, 'height': h,
                  'stride': args.stride, 'packing': 'CSI-2 RAW10 assumed from caller',
                  'note': 'Parity is relative to the captured buffer origin, not verified colour.',
                  'rois': {name: {'rectangle': [x, y, size, size],
                                  'parity': statistics(data, w, h, args.stride, (x, y, size, size))}
                           for name, (x, y) in rois.items()}}
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
