#!/usr/bin/env python3
"""Compare identity and a recorded frame CCM on the same saved packed RAW10 ROI.

This offline diagnostic uses a simple bilinear demosaic, measured four-parity
black levels and fixed R/B white-balance gains. It is not the libcamera ISP and
cannot establish a calibrated colour correction. All numbers are supplied by
the operator from the same controlled data set; no calibration is embedded.
"""
import argparse
import json
import math
from pathlib import Path


def numbers(value, count):
    try:
        result = [float(part) for part in value.split(',')]
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected comma-separated numbers') from exc
    if len(result) != count or not all(math.isfinite(v) for v in result):
        raise argparse.ArgumentTypeError(f'expected {count} finite comma-separated numbers')
    return result


def compare(data, width, height, stride, roi, cfa, black, wb, matrix, gamma):
    if width <= 0 or height <= 0 or width % 4 or stride < width * 5 // 4 or len(data) < stride * height:
        raise ValueError('invalid packed RAW10 dimensions, stride or file length')
    if cfa not in ('RGGB', 'GRBG', 'GBRG', 'BGGR'):
        raise ValueError('unsupported CFA')
    if len(black) != 4 or not all(math.isfinite(x) and 0 <= x < 1023 for x in black):
        raise ValueError('four measured black levels must be finite and in [0, 1023)')
    if len(wb) != 2 or not all(math.isfinite(x) and x > 0 for x in wb):
        raise ValueError('two measured WB gains must be finite and positive')
    if len(matrix) != 9 or not all(math.isfinite(x) for x in matrix):
        raise ValueError('CCM must have nine finite coefficients')
    if not math.isfinite(gamma) or gamma <= 0:
        raise ValueError('display gamma must be finite and positive')
    x0, y0, rw, rh = roi
    if rw <= 0 or rh <= 0 or x0 < 1 or y0 < 1 or x0 + rw >= width or y0 + rh >= height:
        raise ValueError('ROI must fit inside a one-pixel frame border')

    def colour(x, y):
        return cfa[(y % 2) * 2 + x % 2]

    def sample(x, y):
        pos = y * stride + (x // 4) * 5
        value = (data[pos + x % 4] << 2) | ((data[pos + 4] >> (2 * (x % 4))) & 3)
        pedestal = black[(y % 2) * 2 + x % 2]
        return max(0.0, value - pedestal) / (1023.0 - pedestal)

    def channel(x, y, target):
        if colour(x, y) == target:
            return sample(x, y)
        neighbours = [sample(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                      if (dx or dy) and colour(x + dx, y + dy) == target]
        return sum(neighbours) / len(neighbours)

    images = [bytearray(), bytearray()]
    sums = [[0.0, 0.0, 0.0] for _ in range(2)]
    clipped = [0, 0]
    for y in range(y0, y0 + rh):
        for x in range(x0, x0 + rw):
            rgb = [channel(x, y, 'R') * wb[0], channel(x, y, 'G'), channel(x, y, 'B') * wb[1]]
            transformed = [sum(matrix[3 * i + j] * rgb[j] for j in range(3)) for i in range(3)]
            for arm, values in enumerate((rgb, transformed)):
                for i, value in enumerate(values):
                    sums[arm][i] += value
                    clipped[arm] += value < 0 or value > 1
                    encoded = max(0.0, min(1.0, value)) ** (1.0 / gamma)
                    images[arm].append(round(255 * encoded))
    count = rw * rh
    return images, {'identity': {'linear_mean_rgb': [x / count for x in sums[0]],
                                  'fraction_channels_clipped': clipped[0] / (3 * count)},
                    'recorded_ccm': {'linear_mean_rgb': [x / count for x in sums[1]],
                                     'fraction_channels_clipped': clipped[1] / (3 * count)}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('raw', type=Path)
    p.add_argument('--width', type=int, required=True)
    p.add_argument('--height', type=int, required=True)
    p.add_argument('--stride', type=int, required=True)
    p.add_argument('--roi', required=True, help='x,y,width,height with a one-pixel border')
    p.add_argument('--cfa', required=True, choices=('RGGB', 'GRBG', 'GBRG', 'BGGR'))
    p.add_argument('--black', required=True, help='four measured pedestal levels: y0x0,y0x1,y1x0,y1x1')
    p.add_argument('--wb', required=True, help='fixed measured red,blue gains')
    p.add_argument('--ccm', required=True, help='nine same-frame recorded CCM values, row major')
    p.add_argument('--display-gamma', type=float, default=2.2)
    p.add_argument('--out', type=Path, required=True, help='new private output directory')
    args = p.parse_args()
    try:
        roi = numbers(args.roi, 4)
        if any(not x.is_integer() for x in roi):
            raise ValueError('ROI coordinates must be integers')
        roi = [int(x) for x in roi]
        black, wb, ccm = numbers(args.black, 4), numbers(args.wb, 2), numbers(args.ccm, 9)
        data = args.raw.read_bytes()
        images, stats = compare(data, args.width, args.height, args.stride, roi,
                                args.cfa, black, wb, ccm, args.display_gamma)
        args.out.mkdir(mode=0o700)
        for name, image in zip(('identity.ppm', 'recorded-ccm.ppm'), images):
            (args.out / name).write_bytes(f'P6\n{roi[2]} {roi[3]}\n255\n'.encode() + image)
        result = {'source': str(args.raw), 'width': args.width, 'height': args.height,
                  'stride': args.stride, 'roi': roi, 'cfa_assumption': args.cfa,
                  'black': black, 'wb_red_blue': wb, 'matrix': ccm,
                  'display_gamma': args.display_gamma, 'statistics': stats,
                  'note': 'Offline approximation; frame CCM may not include every live ISP adjustment.'}
        (args.out / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    except (OSError, ValueError, argparse.ArgumentTypeError) as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
