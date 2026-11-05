#!/usr/bin/env python3
"""Manually capture private paired RAW/processed camera diagnostics in safe mode.

Run once per lens and target. This is interactive and never starts a stream
without an operator observing the physical privacy indicator. Ctrl-C stops it.
"""
import argparse
import datetime as dt
import fcntl
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time

CAMERAS = {
    'front': ('/base/soc@0/cci@ac16000/i2c-bus@1/camera@10', 3840, 2160),
    'rear': ('/base/soc@0/cci@ac15000/i2c-bus@1/camera@10', 2112, 1188),
}
FIELDS = ('ExposureTime', 'AnalogueGain', 'DigitalGain', 'ColourGains',
          'ColourTemperature', 'ColourCorrectionMatrix', 'SensorBlackLevels', 'Gamma')
FRAME = re.compile(r'^(\d+\.\d+)\s+\([^)]*\)\s+(.*\bseq:.*)$')
STREAM = re.compile(r'(cam\d+-stream\d+)\s+seq:\s*(\d+)\s+bytesused:\s*([\d/]+)')
VALUE = re.compile(r'^\s+([A-Za-z][A-Za-z0-9]+)\s*=\s*(.*)$')


def parse_metadata(lines):
    """Parse cam output without treating absent controls as observed values."""
    current = None
    for line in lines:
        frame = FRAME.match(line)
        if frame:
            if current is not None:
                yield current
            streams = [{'name': n, 'sequence': int(s), 'bytesused': b}
                       for n, s, b in STREAM.findall(frame.group(2))]
            current = {'timestamp_s': frame.group(1), 'streams': streams,
                       'metadata': {name: None for name in FIELDS}}
            continue
        val = VALUE.match(line)
        if current is not None and val and val.group(1) in FIELDS:
            current['metadata'][val.group(1)] = val.group(2).strip()
    if current is not None:
        yield current


def command(args, seconds=8):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=seconds, check=False)
        return result.returncode, result.stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, f'UNAVAILABLE: {exc}\n'


def dt_string(path):
    try:
        return path.read_bytes().split(b'\0')[0].decode('ascii')
    except (OSError, UnicodeError):
        return None


def preflight(sensor):
    if 'sp11.entry=safe' not in Path('/proc/cmdline').read_text().split():
        raise ValueError('This diagnostic requires sp11.entry=safe.')
    root = Path('/sys/firmware/devicetree/base')
    if b'microsoft,denali\0' not in (root / 'compatible').read_bytes():
        raise ValueError('Device tree is not Microsoft Denali.')
    sensor_node = root / CAMERAS[sensor][0].removeprefix('/base/')
    if (not (sensor_node / 'leds').is_file() or
            dt_string(sensor_node / 'led-names') != 'privacy'):
        raise ValueError('The selected sensor lacks its DT privacy LED reference.')
    # The disabled IR node may be absent, but it must not be enabled or routed.
    for compatible in root.rglob('compatible'):
        try:
            names = compatible.read_bytes().split(b'\0')
        except OSError:
            continue
        if b'st,vd55g0' in names:
            node = compatible.parent
            if dt_string(node / 'status') != 'disabled' or (node / 'port').exists():
                raise ValueError('IR sensor is enabled or has a media endpoint.')
            if (node / 'st,leds').exists():
                raise ValueError('IR sensor has an illuminator binding.')


def acquire_lock():
    flags = os.O_RDONLY | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open('/run/lock/sp11-camera-enumeration.lock', flags, 0o644)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError('Enumeration lock is not a regular file.')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise ValueError('Camera collector is running; wait for it to finish.')
    return fd


def enumeration(log):
    ids = [data[0] for data in CAMERAS.values()]
    for attempt in range(1, 4):
        rc, result = command(['cam', '-l'], 10)
        log.write(f'\nAttempt {attempt}; exit={rc}; UTC={dt.datetime.now(dt.timezone.utc).isoformat()}\n{result}')
        log.flush()
        listed = [line for line in result.splitlines() if re.match(r'^\d+:', line)]
        busy = re.search(r'resource busy|\bEBUSY\b|unable to setup link', result, re.I)
        if rc == 0 and not busy and all(any(f'({cid})' in line for line in listed) for cid in ids):
            return
        if attempt < 3:
            time.sleep(2)
    raise ValueError('Camera discovery remained busy or incomplete; see enumeration.log.')


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def provenance(out):
    record = {'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'uname': list(os.uname()), 'cmdline': Path('/proc/cmdline').read_text().strip(),
              'environment': {k: v for k, v in os.environ.items() if k.startswith('LIBCAMERA_')},
              'files_sha256': {}, 'note': 'Loaded tuning path is also recorded in capture.log; missing values are unknown.'}
    rc, record['packages'] = command(['rpm', '-q', 'libcamera', 'libcamera-ipa',
                                      'libcamera-tools', 'pipewire-plugin-libcamera', 'snapshot'])
    rc, files = command(['rpm', '-ql', 'libcamera', 'libcamera-ipa'])
    candidates = [p for p in files.splitlines() if 'libcamera.so' in p or
                  '/ipa_' in p or p.endswith('/simple/imx681.yaml') or p.endswith('/simple/ov13858.yaml')]
    candidates.append('/sys/firmware/fdt')
    for pattern in ['/usr/lib/firmware/updates/*mshw049*.bin', '/usr/lib/firmware/*mshw049*.bin']:
        candidates.extend(glob.glob(pattern))
    # Overrides can be directory lists or an explicit tuning file.
    for key in ('LIBCAMERA_IPA_CONFIG_PATH', 'LIBCAMERA_SIMPLE_TUNING_FILE'):
        for val in os.environ.get(key, '').split(':'):
            if not val:
                continue
            p = Path(val)
            candidates.extend(str(x) for x in ([p] if p.is_file() else p.glob('simple/*.yaml')))
    for name in sorted(set(candidates)):
        try:
            if Path(name).is_file():
                record['files_sha256'][name] = file_hash(name)
        except OSError:
            record['files_sha256'][name] = None
    (out / 'provenance.json').write_text(json.dumps(record, indent=2) + '\n')


def sample_state(out, done):
    with (out / 'state-live.log').open('w', buffering=1) as log:
        while not done.is_set():
            log.write(f'\nUTC={dt.datetime.now(dt.timezone.utc).isoformat()} uptime={Path("/proc/uptime").read_text().strip()}\n')
            for node in sorted(glob.glob('/dev/media*')):
                rc, text = command(['media-ctl', '-d', node, '-p'], 3)
                log.write(f'### {node} exit={rc}\n{text}')
            for path in sorted(glob.glob('/sys/class/leds/*indicator*/brightness')):
                try:
                    log.write(f'{path}: {Path(path).read_text().strip()}\n')
                except OSError as exc:
                    log.write(f'{path}: UNAVAILABLE {exc}\n')
            done.wait(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sensor', required=True, choices=CAMERAS)
    parser.add_argument('--target', required=True, choices=('occlusion', 'dark', 'flat', 'red', 'blue', 'orientation'))
    parser.add_argument('--out', required=True, type=Path, help='new private directory on a non-Windows filesystem')
    parser.add_argument('--frames', type=int, default=30, choices=range(1, 121), metavar='1..120')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error('an interactive terminal and an observer are required')
    try:
        preflight(args.sensor)
        parent = args.out.absolute().parent.resolve(strict=True)
        if args.out.exists() or args.out.is_symlink():
            raise ValueError('output directory must not already exist')
        rc, fstype = command(['findmnt', '-n', '-o', 'FSTYPE', '--target', str(parent)])
        if rc or fstype.strip() not in {'ext4', 'xfs', 'btrfs', 'tmpfs', 'overlay'}:
            raise ValueError(f'unsupported output filesystem {fstype.strip()!r}; use a non-Windows Linux filesystem')
        required = args.frames * 24 * 1024 * 1024 + 256 * 1024 * 1024
        if shutil.disk_usage(parent).free < required:
            raise ValueError(f'need at least {required} free bytes for this capture')
        lock = acquire_lock()
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    try:
        # Direct cam runs outside the WirePlumber safe wrapper. Force the
        # libcamera CPU path during enumeration and capture as well.
        os.environ['LIBCAMERA_SOFTISP_MODE'] = 'cpu'
        os.environ['GALLIUM_DRIVER'] = 'softpipe'
        os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
        print('Close Snapshot and other camera clients. Verify the independent LED wiring cross-check,')
        print('the IR/flash exclusion and that the sensor privacy indicator is visible. Do not cover it.')
        print('A person must watch throughout; press Ctrl-C immediately if the indicator is dark,')
        print('or on a fault, stall or reset. No automatic LED or exposure override is used.')
        if input('Type OBSERVING to continue: ').strip() != 'OBSERVING':
            print('Cancelled before streaming.')
            return 1
        os.umask(0o077)
        args.out.mkdir(mode=0o700)
        out = args.out.resolve()
        (out / 'capture-info.json').write_text(json.dumps({
            'sensor': args.sensor, 'target': args.target, 'camera_id': CAMERAS[args.sensor][0],
            'requested_frames': args.frames, 'requested_controls': 'automatic',
            'log_levels': '*:INFO,Debayer:DEBUG',
            'applied_control_note': 'Metadata is reported by IPA and may be delayed or inferred; not sensor readback.',
            'physical_led_note': 'Observer must record physical on/off and any interruption.'}, indent=2) + '\n')
        provenance(out)
        with (out / 'enumeration.log').open('w') as log:
            enumeration(log)
        camera_id, width, height = CAMERAS[args.sensor]
        cmd = ['stdbuf', '-oL', '-eL', 'cam', '--camera', camera_id, '--info',
               '--list-controls', '--list-properties',
               '--stream', f'role=raw,width={width},height={height}',
               '--stream', 'role=viewfinder,width=1920,height=1080',
               f'--capture={args.frames}', '--metadata', f'--file={out}/frame-#.bin']
        (out / 'command.json').write_text(json.dumps(cmd, indent=2) + '\n')
        env = os.environ.copy()
        env['LIBCAMERA_LOG_LEVELS'] = '*:INFO,Debayer:DEBUG'
        done = threading.Event()
        worker = threading.Thread(target=sample_state, args=(out, done), daemon=True)
        worker.start()
        status = 1
        try:
            with (out / 'capture.log').open('w', buffering=1) as log:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1, env=env)
                try:
                    for line in proc.stdout:
                        print(line, end='', flush=True)
                        log.write(line)
                    status = proc.wait()
                except KeyboardInterrupt:
                    try:
                        proc.send_signal(signal.SIGINT)
                    except ProcessLookupError:
                        pass
                    try:
                        status = proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        status = proc.wait()
        finally:
            done.set()
            worker.join(timeout=5)
        with (out / 'capture.log').open() as log:
            rows = list(parse_metadata(log))
        with (out / 'frames.jsonl').open('w') as result:
            for row in rows:
                result.write(json.dumps(row) + '\n')
        both_streams = sum(len(row['streams']) == 2 for row in rows)
        saved_files = len(list(out.glob('frame-*.bin')))
        result = {'cam_exit': status, 'frame_metadata_records': len(rows),
                  'records_with_two_streams': both_streams, 'saved_files': saved_files,
                  'missing_metadata_counts': {field: sum(row['metadata'][field] is None for row in rows)
                                              for field in FIELDS},
                  'note': 'Two-stream records and files do not by themselves prove matched settings or format.'}
        (out / 'capture-result.json').write_text(json.dumps(result, indent=2) + '\n')
        if len(rows) < args.frames or both_streams < args.frames or saved_files < args.frames * 2:
            print('INCOMPLETE: expected two stream buffers per recorded frame; inspect the logs.', file=sys.stderr)
            status = 1
        print(f'Capture exit={status}; private results: {out}')
        print('Record physical LED on/off, scene and lens identification separately; verify files,')
        print('negotiated mode/stride, both streams and metadata before treating frames as paired.')
        print('The automatically selected exposure/gain can differ between targets.')
        return 0 if status == 0 else 1
    except (OSError, ValueError) as exc:
        print(f'Diagnostic stopped: {exc}', file=sys.stderr)
        return 1
    finally:
        os.close(lock)


if __name__ == '__main__':
    sys.exit(main())
