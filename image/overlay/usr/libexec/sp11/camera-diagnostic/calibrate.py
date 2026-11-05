#!/usr/bin/python3
"""Measure white balance from a packed RAW10 frame and write it into the IPA tuning.

This is the deterministic correction path for a colour cast that survives the
automatic estimator:

  1. capture a capped-lens dark frame and a neutral (grey card) frame with
     camera-diagnostic, on the same sensor and mode;
  2. run this tool with both files and --install;
  3. close and reopen every camera client.

It measures the per-channel black from the dark frame, persists its mean as the
tuning's single `blackLevel` (the Software ISP subtracts one scalar), subtracts
that same scalar, measures the green-to-red and green-to-blue ratios over a
central ROI and writes `Awb: gains: [r, 1, b]` into the sensor's private YAML,
leaving the CCM, gamma and AGC entries untouched. `--restore` puts the original
file back.

The tool never opens a camera or a PCM. It refuses clipped pixels, a frame too
close to black, an out-of-bounds ROI, a flow-style Awb block it cannot edit
safely, a symlinked tuning path and any value outside the IPA's accepted range.
"""
import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

CFA = ('RGGB', 'GRBG', 'GBRG', 'BGGR')
GAIN_MIN = 0.25
GAIN_MAX = 16.0
CLIP = 1020
SENSOR_YAML = {
    'imx681': Path('/usr/share/libcamera/ipa/simple/imx681.yaml'),
    'ov13858': Path('/usr/share/libcamera/ipa/simple/ov13858.yaml'),
}
GAINS_LINE = re.compile(r'^[ \t]+gains[ \t]*:', re.M)


def unpack10(path, width, height, stride):
    """Decode a packed RAW10 frame (4 pixels in 5 bytes) into 16-bit samples."""
    data = path.read_bytes()
    if width <= 0 or height <= 0 or width % 4 or stride < width * 5 // 4:
        raise ValueError('invalid RAW10 width, height or stride')
    row_bytes = width * 5 // 4
    if len(data) < stride * height:
        raise ValueError('frame shorter than stride x height')
    out = []
    for y in range(height):
        base = y * stride
        row = data[base:base + row_bytes]
        values = [0] * width
        for x in range(0, row_bytes, 5):
            b0, b1, b2, b3, low = row[x:x + 5]
            values[x // 5 * 4 + 0] = (b0 << 2) | ((low >> 0) & 3)
            values[x // 5 * 4 + 1] = (b1 << 2) | ((low >> 2) & 3)
            values[x // 5 * 4 + 2] = (b2 << 2) | ((low >> 4) & 3)
            values[x // 5 * 4 + 3] = (b3 << 2) | ((low >> 6) & 3)
        out.append(values)
    return out


def channel(cfa, x, y):
    """Colour of a sample: 0 red, 1 green (either parity), 2 blue."""
    even_x, even_y = x % 2 == 0, y % 2 == 0
    if cfa == 'RGGB':
        return 0 if even_x and even_y else 2 if not even_x and not even_y else 1
    if cfa == 'BGGR':
        return 2 if even_x and even_y else 0 if not even_x and not even_y else 1
    if cfa == 'GRBG':
        return 0 if not even_x and even_y else 2 if even_x and not even_y else 1
    if cfa == 'GBRG':
        return 2 if not even_x and even_y else 0 if even_x and not even_y else 1
    raise ValueError('unsupported CFA')


def check_roi(roi, width, height):
    x0, y0, rw, rh = roi
    if rw <= 0 or rh <= 0 or x0 < 0 or y0 < 0 or x0 + rw > width or y0 + rh > height:
        raise ValueError(f'ROI {roi} does not fit inside {width}x{height}')
    return roi


def sums_counts(frame, cfa, roi, width, height):
    x0, y0, rw, rh = check_roi(roi, width, height)
    sums = [0, 0, 0]
    counts = [0, 0, 0]
    maxima = [0, 0, 0]
    for y in range(y0, y0 + rh):
        row = frame[y]
        for x in range(x0, x0 + rw):
            c = channel(cfa, x, y)
            value = row[x]
            sums[c] += value
            counts[c] += 1
            maxima[c] = max(maxima[c], value)
    if any(c == 0 for c in counts):
        raise ValueError('ROI has no samples for one channel')
    return sums, counts, maxima


def means(frame, cfa, roi, width, height):
    sums, counts, _ = sums_counts(frame, cfa, roi, width, height)
    return tuple(sums[c] / counts[c] for c in range(3))


def default_roi(width, height):
    rw, rh = width // 2, height // 2
    return ((width - rw) // 2, (height - rh) // 2, rw, rh)


def validate_neutral(frame, black, cfa, roi, width, height):
    sums, counts, maxima = sums_counts(frame, cfa, roi, width, height)
    if max(maxima) >= CLIP:
        raise ValueError(f'neutral frame has clipped pixels (>= {CLIP})')
    values = tuple(sums[c] / counts[c] for c in range(3))
    if min(values) - black < 8:
        raise ValueError('neutral frame signal too close to black; increase light')
    return values


def read_black(yaml_path):
    text = yaml_path.read_text()
    m = re.search(r'^\s+blackLevel:\s*(\d+)\s*$', text, re.M)
    if not m:
        raise ValueError('tuning file has no blackLevel')
    return int(m.group(1)) / 64.0  # 16-bit YAML value to the 10-bit frame scale


def atomic_write(path, text):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def set_black(yaml_path, value10):
    """Persist the measured scalar black so the ISP subtracts what the gains assume."""
    text = yaml_path.read_text()
    new = int(round(value10 * 64))
    updated, count = re.subn(r'(^\s+blackLevel:\s*)\d+(\s*)$', r'\g<1>%d\2' % new, text,
                             count=1, flags=re.M)
    if count != 1:
        raise ValueError('tuning file has no single blackLevel to update')
    atomic_write(yaml_path, updated)
    return new


def write_gains(yaml_path, red, blue):
    if yaml_path.is_symlink():
        raise ValueError(f'refusing symlinked tuning path {yaml_path}')
    text = yaml_path.read_text()
    lines = text.splitlines()
    awb = None
    for i, line in enumerate(lines):
        if line.strip().startswith('- Awb:'):
            if line.strip() != '- Awb:':
                raise ValueError('flow-style Awb block is not supported; edit the YAML manually')
            awb = i
            break
    if awb is None:
        raise ValueError('tuning file has no block-style - Awb: entry')
    start = awb + 1
    end = start
    while end < len(lines):
        stripped = lines[end].strip()
        if lines[end].startswith('  - ') or stripped in ('...', '---') or not stripped:
            break
        end += 1
    children = [l for l in lines[start:end] if not GAINS_LINE.match(l)]
    children.append('      gains: [ %.3f, 1.0, %.3f ]' % (red, blue))
    lines[start:end] = children
    result = '\n'.join(lines) + '\n'
    if len(GAINS_LINE.findall(result)) != 1:
        raise ValueError('refusing to write an ambiguous gains entry')
    backup = yaml_path.with_name(yaml_path.name + '.sp11-orig')
    if backup.is_symlink():
        raise ValueError(f'refusing symlinked backup {backup}')
    # Keep the first backup; refresh it only when the tuning was regenerated
    # (the current file no longer carries a gains entry we installed).
    if not backup.exists() or not GAINS_LINE.search(text):
        backup.write_text(text)
        os.chmod(backup, 0o600)
    atomic_write(yaml_path, result)
    return hashlib.sha256(result.encode()).hexdigest()


def restore(yaml_path):
    if yaml_path.is_symlink():
        raise ValueError(f'refusing symlinked tuning path {yaml_path}')
    backup = yaml_path.with_name(yaml_path.name + '.sp11-orig')
    if backup.is_symlink() or not backup.is_file():
        raise ValueError(f'no regular backup next to {yaml_path}')
    if not GAINS_LINE.search(yaml_path.read_text()):
        raise ValueError('the current tuning carries no installed gains; nothing to restore')
    atomic_write(yaml_path, backup.read_text())
    return hashlib.sha256(yaml_path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sensor', required=True, choices=sorted(SENSOR_YAML))
    ap.add_argument('--neutral', required=True, type=Path, help='packed RAW10 grey-card frame')
    ap.add_argument('--dark', type=Path, help='packed RAW10 capped-lens frame')
    ap.add_argument('--width', required=True, type=int)
    ap.add_argument('--height', required=True, type=int)
    ap.add_argument('--stride', required=True, type=int)
    ap.add_argument('--cfa', required=True, choices=CFA)
    ap.add_argument('--roi', help='x,y,w,h; default the central half')
    ap.add_argument('--yaml', type=Path, help='override the sensor tuning path')
    ap.add_argument('--install', action='store_true', help='write the measured gains')
    ap.add_argument('--restore', action='store_true', help='put the original tuning back')
    args = ap.parse_args()

    yaml_path = args.yaml or SENSOR_YAML[args.sensor]
    if not yaml_path.is_file() or yaml_path.is_symlink():
        sys.exit(f'calibrate: {yaml_path} is missing or a symlink')
    if args.restore:
        print(f'restored {yaml_path} sha256 {restore(yaml_path)[:16]}')
        return 0
    if not args.install:
        sys.exit('calibrate: pass --install to write the measured gains (or --restore)')

    roi = (tuple(int(v) for v in args.roi.split(',')) if args.roi
           else default_roi(args.width, args.height))
    if len(roi) != 4:
        sys.exit('calibrate: --roi needs x,y,w,h')
    check_roi(roi, args.width, args.height)

    black = read_black(yaml_path)
    neutral = unpack10(args.neutral, args.width, args.height, args.stride)
    measured_black = None
    if args.dark:
        dark = unpack10(args.dark, args.width, args.height, args.stride)
        per_channel = means(dark, args.cfa, roi, args.width, args.height)
        measured_black = sum(per_channel) / 3.0
        black = round(measured_black * 64) / 64.0

    r, g, b = validate_neutral(neutral, black, args.cfa, roi, args.width, args.height)
    r -= black
    g -= black
    b -= black
    if min(r, g, b) <= 0:
        sys.exit('calibrate: neutral frame has no signal above black')
    red, blue = g / r, g / b
    for name, value in (('red', red), ('blue', blue)):
        if not (GAIN_MIN <= value <= GAIN_MAX):
            sys.exit(f'calibrate: measured {name} gain {value:.3f} outside {GAIN_MIN}..{GAIN_MAX}')
    print('measured gains red %.3f green 1.000 blue %.3f' % (red, blue))
    write_gains(yaml_path, red, blue)
    if measured_black is not None:
        persisted = set_black(yaml_path, measured_black)
        print('black per CFA colour (10-bit): %.2f %.2f %.2f; persisted blackLevel %d'
              % (per_channel[0], per_channel[1], per_channel[2], persisted))
    digest = hashlib.sha256(yaml_path.read_bytes()).hexdigest()
    print(f'installed {yaml_path} sha256 {digest[:16]}; close and reopen every camera client')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, IndexError) as exc:
        sys.exit(f'calibrate: {exc}')
