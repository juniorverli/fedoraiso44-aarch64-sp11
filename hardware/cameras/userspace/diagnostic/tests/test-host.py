#!/usr/bin/env python3
"""No-device checks for the camera diagnostic, RAW parser and collector retry."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CAMERAS = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture = load('capture', HERE.parent / 'capture.py')
raw = load('raw10_stats', HERE.parent / 'raw10-stats.py')
comparison = load('comparison', HERE.parent / 'compare-ccm.py')
experiment = load('experiment', CAMERAS / 'userspace' / 'quality' / 'prepare-rev25-agc.py')


class HostChecks(unittest.TestCase):
    def test_cam_metadata_and_missing_fields(self):
        lines = ['warning: no values here\n',
                 '1.234567 (30.00 fps) cam0-stream0 seq: 000012 bytesused: 50 cam0-stream1 seq: 000012 bytesused: 80\n',
                 '\tExposureTime = 10000\n', '\tColourGains = [ 1.1, 2.2 ]\n',
                 '[libcamera] interleaved message\n', '\tColourCorrectionMatrix = [1, 0, 0]\n',
                 '1.267900 (30.00 fps) cam0-stream0 seq: 000013 bytesused: 50 cam0-stream1 seq: 000013 bytesused: 80\n',
                 '\tAnalogueGain = 2.0\n']
        result = list(capture.parse_metadata(lines))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['streams'][0]['sequence'], 12)
        self.assertEqual(result[0]['metadata']['ExposureTime'], '10000')
        self.assertEqual(result[0]['metadata']['ColourCorrectionMatrix'], '[1, 0, 0]')
        self.assertIsNone(result[1]['metadata']['ExposureTime'])
        self.assertEqual(result[1]['metadata']['AnalogueGain'], '2.0')
        self.assertIsNone(result[0]['metadata']['DigitalGain'])

    def test_raw10_packing_stride_parity_and_rejection(self):
        width, height, stride = 8, 4, 13
        values = [[(y * width + x) * 4 + (x % 4) for x in range(width)] for y in range(height)]
        values[2][6] = 1023
        data = bytearray([0xff] * (stride * height))
        for y in range(height):
            for group in range(width // 4):
                vals = values[y][group * 4:group * 4 + 4]
                base = y * stride + group * 5
                data[base:base + 4] = bytes(v >> 2 for v in vals)
                data[base + 4] = sum((v & 3) << (i * 2) for i, v in enumerate(vals))
        for y in range(height):
            for x in range(width):
                self.assertEqual(raw.unpack_pixel(data, stride, x, y), values[y][x])
        result = raw.statistics(data, width, height, stride, (0, 0, width, height))
        expected = [values[y][x] for y in range(0, height, 2) for x in range(0, width, 2)]
        self.assertAlmostEqual(result['y0x0']['mean'], sum(expected) / len(expected))
        self.assertEqual(result['y0x0']['fraction_at_1023'], 1 / len(expected))
        with self.assertRaises(ValueError):
            raw.statistics(data[:-1], width, height, stride, (0, 0, width, height))
        with self.assertRaises(ValueError):
            raw.statistics(data, width, height, 9, (0, 0, width, height))

    def test_offline_ccm_compares_identical_raw_and_fixed_controls(self):
        # A constant Bayer field, padded stride and an ROI with a real border.
        width, height, stride = 8, 6, 13
        data = bytearray(stride * height)
        for y in range(height):
            for x in range(width):
                value = 200 + 4 * ((y % 2) * 2 + x % 2)
                base = y * stride + (x // 4) * 5
                data[base + x % 4] = value >> 2
                data[base + 4] |= (value & 3) << (2 * (x % 4))
        roi = (1, 1, 6, 4)
        identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
        images, stats = comparison.compare(data, width, height, stride, roi, 'RGGB',
                                           [10, 10, 10, 10], [1, 1], identity, 2.2)
        self.assertEqual(images[0], images[1])
        self.assertEqual(stats['identity'], stats['recorded_ccm'])
        images, stats = comparison.compare(data, width, height, stride, roi, 'RGGB',
                                           [10, 10, 10, 10], [1, 1], [0] * 9, 2.2)
        self.assertTrue(any(images[0]))
        self.assertFalse(any(images[1]))
        with self.assertRaises(ValueError):
            comparison.compare(data, width, height, stride, (0, 1, 2, 2), 'RGGB',
                               [10] * 4, [1, 1], identity, 2.2)

    def test_agc_staging_transformation(self):
        import yaml
        source = 'version: 1\nalgorithms:\n  - Awb:\n  - Agc:\n  - Adjust:\n      gamma: 1.0\n'
        variant = experiment.experiment(source)
        self.assertEqual(variant.replace('      exposureTarget: 3.5\n', ''), source)
        self.assertEqual(yaml.safe_load(variant)['algorithms'][1]['Agc']['exposureTarget'], 3.5)
        for bad in ('version: 1\n', source.replace('  - Agc:\n', '  - Agc:\n      exposureTarget: 3\n'),
                    source + '  - Agc:\n', source.replace('\n', '\r\n')):
            with self.assertRaises(ValueError):
                experiment.experiment(bad)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(experiment.private_path(Path(tmp) / 'ok', Path(tmp)), Path(tmp) / 'ok')
            with self.assertRaises(ValueError):
                experiment.private_path(Path(tmp) / '..' / 'outside', Path(tmp))

    def test_private_staging_for_each_sensor(self):
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_script = root / 'hardware/cameras/userspace/quality/prepare-rev25-agc.py'
            baseline_root = root / 'out/firmware-private/cameras/libcamera'
            baseline_root.mkdir(parents=True)
            source = 'version: 1\nalgorithms:\n  - Awb:\n  - Agc:\n'
            baseline = baseline_root / 'imx681.yaml'
            baseline.write_text(source)
            destination = baseline_root.parent / 'test-agc'
            original_file, original_argv = experiment.__file__, sys.argv
            try:
                experiment.__file__ = str(fake_script)
                sys.argv = ['prepare', '--baseline', str(baseline), '--output-dir', str(destination)]
                with contextlib.redirect_stdout(io.StringIO()):
                    experiment.main()
                baseline_output = destination / 'imx681-rev25-agc-2.5/simple/imx681.yaml'
                variant_output = destination / 'imx681-rev25-agc-3.5/simple/imx681.yaml'
                self.assertEqual(baseline.read_text(), source)
                self.assertEqual(baseline_output.read_text(), source)
                self.assertEqual(yaml.safe_load(variant_output.read_text())['algorithms'][1]['Agc']['exposureTarget'], 3.5)
                manifest = json.loads((destination / 'manifest.json').read_text())
                self.assertTrue(manifest['private'])
                self.assertEqual(manifest['baseline_sha256'], hashlib.sha256(source.encode()).hexdigest())
                self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    experiment.main()
            finally:
                experiment.__file__, sys.argv = original_file, original_argv

    def test_collector_retries_after_busy_and_requires_both_ids(self):
        text = (CAMERAS / 'collector/cameras.sh').read_text()
        section = text[text.index('echo "== 6 libcamera'):text.index('sh_ "rpm -q libcamera')]
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            section = section.replace('/run/lock/sp11-camera-enumeration.lock', str(temp / 'lock'))
            (temp / 'cam').write_text('''#!/bin/sh
n=0
[ ! -e "$COUNT" ] || n=$(cat "$COUNT")
n=$((n+1))
printf '%s' "$n" > "$COUNT"
if [ "$n" -eq 1 ]; then
  echo 'Failed to setup link: Device or resource busy'
  echo '1: Internal front camera (/base/soc@0/cci@ac16000/i2c-bus@1/camera@10)'
else
  echo '1: Internal back camera (/base/soc@0/cci@ac15000/i2c-bus@1/camera@10)'
  echo '2: Internal front camera (/base/soc@0/cci@ac16000/i2c-bus@1/camera@10)'
fi
''')
            (temp / 'sleep').write_text('#!/bin/sh\nexit 0\n')
            for name in ('cam', 'sleep'):
                (temp / name).chmod(0o755)
            env = dict(os.environ, PATH=f'{temp}:' + os.environ['PATH'], COUNT=str(temp / 'count'))
            result = subprocess.run(['bash', '-c', section], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('attempt 1', result.stdout)
            self.assertIn('attempt 2', result.stdout)
            self.assertIn('INCOMPLETE:', result.stdout)
            self.assertIn('COMPLETE: both expected IDs', result.stdout)
            self.assertEqual((temp / 'count').read_text(), '2')

    def test_calibrate_raw10_math_and_yaml_round_trip(self):
        cal = load('calibrate', HERE.parent / 'calibrate.py')
        # CFA mapping: red, green, blue positions per pattern.
        expected = {'RGGB': (0, 1, 1, 2), 'BGGR': (2, 1, 1, 0),
                    'GRBG': (1, 0, 2, 1), 'GBRG': (1, 2, 0, 1)}
        for cfa, order in expected.items():
            got = tuple(cal.channel(cfa, x, y) for x, y in ((0, 0), (1, 0), (0, 1), (1, 1)))
            self.assertEqual(got, order, cfa)

        def pack(width, height, values):
            row_bytes = width * 5 // 4
            out = bytearray()
            for y in range(height):
                row = bytearray()
                for x in range(0, width, 4):
                    v = [values[y][x + i] for i in range(4)]
                    row += bytes([v[0] >> 2, v[1] >> 2, v[2] >> 2, v[3] >> 2,
                                  (v[0] & 3) | ((v[1] & 3) << 2) | ((v[2] & 3) << 4) | ((v[3] & 3) << 6)])
                out += row + bytes(row_bytes - len(row))
            return bytes(out)

        width = height = 16
        stride = width * 5 // 4
        black = 40
        channels = (200, 400, 300)
        values = [[channels[cal.channel('RGGB', x, y)] for x in range(width)] for y in range(height)]
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            raw = temp / 'neutral.raw'
            raw.write_bytes(pack(width, height, values))
            yaml = temp / 'imx681.yaml'
            yaml.write_text('version: 1\n'
                            'algorithms:\n'
                            '  - BlackLevel:\n'
                            '      blackLevel: %d\n'
                            '  - Awb:\n'
                            '      maxGains: [ 9.83, 1.0, 4.71 ]\n'
                            '  - Adjust:\n'
                            '      gamma: 1.882\n' % (black * 64))
            tool = HERE.parent / 'calibrate.py'
            result = subprocess.run([sys.executable, '-I', str(tool), '--sensor', 'imx681',
                                     '--neutral', str(raw), '--width', str(width), '--height', str(height),
                                     '--stride', str(stride), '--cfa', 'RGGB', '--yaml', str(yaml), '--install'],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('red 2.250', result.stdout)
            self.assertIn('blue 1.385', result.stdout)
            text = yaml.read_text()
            self.assertIn('gains: [ 2.250, 1.0, 1.385 ]', text)
            self.assertIn('maxGains: [ 9.83, 1.0, 4.71 ]', text)
            self.assertIn('gamma: 1.882', text)
            self.assertIn('maxGains: [ 9.83, 1.0, 4.71 ]', text)
            self.assertTrue(yaml.with_name('imx681.yaml.sp11-orig').is_file())
            result = subprocess.run([sys.executable, '-I', str(tool), '--sensor', 'imx681',
                                     '--neutral', str(raw), '--width', str(width), '--height', str(height),
                                     '--stride', str(stride), '--cfa', 'RGGB', '--yaml', str(yaml), '--restore'],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('gains: [', yaml.read_text())


    def test_calibrate_refusals_roi_clipping_and_dark_black(self):
        cal = load('calibrate', HERE.parent / 'calibrate.py')
        width = height = 16
        stride = width * 5 // 4

        def pack(values):
            out = bytearray()
            for y in range(height):
                for x in range(0, width, 4):
                    v = [values[y][x + i] for i in range(4)]
                    out += bytes([v[0] >> 2, v[1] >> 2, v[2] >> 2, v[3] >> 2,
                                  (v[0] & 3) | ((v[1] & 3) << 2) | ((v[2] & 3) << 4) | ((v[3] & 3) << 6)])
            return bytes(out)

        def frame(channels, patch=None):
            values = [[channels[cal.channel('RGGB', x, y)] for x in range(width)] for y in range(height)]
            if patch:
                x, y, v = patch
                values[y][x] = v
            return pack(values)

        tool = HERE.parent / 'calibrate.py'
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            neutral = temp / 'neutral.raw'
            neutral.write_bytes(frame((200, 400, 300)))
            clipped = temp / 'clipped.raw'
            clipped.write_bytes(frame((200, 400, 300), patch=(8, 8, 1023)))
            dark = temp / 'dark.raw'
            dark.write_bytes(frame((40, 60, 50)))
            base_yaml = ('version: 1\n'
                         'algorithms:\n'
                         '  - BlackLevel:\n'
                         '      blackLevel: 2560\n'
                         '  - Awb:\n'
                         '      maxGains: [ 9.83, 1.0, 4.71 ]\n')

            def run(raw, *extra):
                target = temp / 'imx681.yaml'
                target.write_text(base_yaml)
                return subprocess.run([sys.executable, '-I', str(tool), '--sensor', 'imx681',
                                       '--neutral', str(raw), '--width', str(width), '--height', str(height),
                                       '--stride', str(stride), '--cfa', 'RGGB', '--yaml', str(target),
                                       '--install'] + list(extra),
                                      capture_output=True, text=True, timeout=30)

            for roi in ('-8,0,8,8', '12,12,8,8', '0,0,0,8'):
                result = run(neutral, '--roi', roi)
                self.assertNotEqual(result.returncode, 0, roi)
                self.assertIn('ROI', result.stderr)
            result = run(clipped)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('clipped', result.stderr)

            target = temp / 'imx681.yaml'
            target.write_text(base_yaml)
            result = subprocess.run([sys.executable, '-I', str(tool), '--sensor', 'imx681',
                                     '--neutral', str(neutral), '--dark', str(dark),
                                     '--width', str(width), '--height', str(height), '--stride', str(stride),
                                     '--cfa', 'RGGB', '--yaml', str(target), '--install'],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('persisted blackLevel 3200', result.stdout)
            self.assertIn('red 2.333', result.stdout)
            self.assertIn('blue 1.400', result.stdout)
            text = target.read_text()
            self.assertIn('blackLevel: 3200', text)
            self.assertIn('gains: [ 2.333, 1.0, 1.400 ]', text)
            # The backup keeps the pre-calibration scalar, so restore undoes both edits.
            self.assertIn('blackLevel: 2560', target.with_name('imx681.yaml.sp11-orig').read_text())

    def test_awb_report_self_test_and_fake_cam(self):
        tool = HERE.parent / 'awb-report.sh'
        result = subprocess.run(['bash', str(tool), '--self-test'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS ceiling_r', result.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            cam = temp / 'cam'
            cam.write_text("""#!/bin/sh
if [ "$1" = "-l" ]; then
  echo '0: Internal back camera (/base/soc@0/cci@ac15000/i2c-bus@1/camera@10)'
  echo '1: Internal front camera (/base/soc@0/cci@ac16000/i2c-bus@1/camera@10)'
  exit 0
fi
echo "gain R/B: Vector { ${GAIN_R:-1}, 1, ${GAIN_B:-1}  }; temperature: 5000" >&2
""")
            cam.chmod(0o755)
            yamls = temp / 'ipa'
            yamls.mkdir()
            for sensor in ('imx681', 'ov13858'):
                (yamls / f'{sensor}.yaml').write_text('  - Awb:\n      maxGains: [ 9.83, 1.0, 4.71 ]\n')
            env = dict(os.environ, PATH=f'{temp}:' + os.environ['PATH'],
                       SP11_AWB_REPORT_TEST='1', SP11_AWB_REPORT_OUT=str(temp / 'report.txt'),
                       SP11_AWB_REPORT_YAML_DIR=str(yamls))
            result = subprocess.run(['bash', str(tool)], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('AWB_STUCK', result.stdout)
            self.assertIn('front (imx681, camera 1)', result.stdout)
            self.assertIn('rear (ov13858, camera 0)', result.stdout)
            env['GAIN_R'] = '2.2'
            env['GAIN_B'] = '1.4'
            result = subprocess.run(['bash', str(tool)], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('AWB_OK', result.stdout)
            self.assertTrue((temp / 'report.txt').is_file())

    def test_image_diagnostic_copies_match_source(self):
        repo = CAMERAS.parents[1]
        overlay = repo / 'image' / 'overlay' / 'usr' / 'libexec' / 'sp11' / 'camera-diagnostic'
        for name in ('calibrate.py', 'awb-report.sh', 'calibrate-camera.sh'):
            self.assertEqual((overlay / name).read_bytes(), (HERE.parent / name).read_bytes(),
                             f'image overlay {name} drifted from the source copy')
        self.assertEqual((repo / 'image' / 'overlay' / 'usr' / 'libexec' / 'sp11' / 'closed-loop-report.sh').read_bytes(),
                         (HERE.parent / 'closed-loop-report.sh').read_bytes(),
                         'image overlay closed-loop-report.sh drifted from the source copy')
        self.assertEqual((repo / 'image' / 'overlay' / 'usr' / 'libexec' / 'sp11' / 'closed-loop-validate.py').read_bytes(),
                         (repo / 'hardware' / 'audio-speakers' / 'userspace' / 'closed-loop' / 'closed-loop-validate.py').read_bytes(),
                         'image overlay closed-loop-validate.py drifted from the source copy')

    def test_closed_loop_report_with_fakes(self):
        tool = HERE.parent / 'closed-loop-report.sh'
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            asound = temp / 'asound' / 'card0' / 'pcm4c'
            (asound / 'sub0').mkdir(parents=True)
            (asound / 'info').write_text('name: MultiMedia5 capture\nid: MultiMedia5\n')
            (asound / 'sub0' / 'status').write_text('state: RUNNING\nowner_pid: 1\n')
            (asound / 'sub0' / 'hw_params').write_text('format: S16_LE\nchannels: 2\nrate: 48000\n')
            fw = temp / 'fw'
            fw.mkdir()
            model = 'X1E80100-Microsoft-Surface-Pro-11-CL'
            for suffix in ('-tplg.bin', '-sp11cl.bin', '-sp11cal.bin'):
                (fw / (model + suffix)).write_bytes(b'x')
            guard = temp / 'guard'
            guard.write_text('#!/bin/sh\necho "mode: closed-loop"\necho "nospk: 1"\necho "allowed: no"\n')
            guard.chmod(0o755)
            sup = temp / 'supervisor'
            sup.write_text('#!/bin/sh\necho "holding $1"\nsleep 5\n')
            sup.chmod(0o755)
            report = temp / 'report.txt'
            env = dict(os.environ, SP11_CL_REPORT_TEST='1', SP11_CL_REPORT_OUT=str(report),
                       SP11_CL_REPORT_GUARD=str(guard), SP11_CL_REPORT_SUPERVISOR=str(sup),
                       SP11_CL_ASOUND_ROOT=str(temp / 'asound'), SP11_CL_FW_DIR=str(fw),
                       SP11_CL_HOLD_SECONDS='1')
            result = subprocess.run(['bash', str(tool)], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('supervisor held the capture', result.stdout + result.stderr)
            self.assertIn('hw:0,4', result.stderr)
            text = report.read_text()
            self.assertIn('mode: closed-loop', text)
            self.assertIn('nospk: 1', text)
            self.assertIn('sha256', text)
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_closed_loop_report_refuses_without_private_files(self):
        tool = HERE.parent / 'closed-loop-report.sh'
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            env = dict(os.environ, SP11_CL_REPORT_TEST='1', SP11_CL_REPORT_OUT=str(temp / 'r.txt'),
                       SP11_CL_FW_DIR=str(temp / 'empty'))
            result = subprocess.run(['bash', str(tool)], env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('missing private CL file', result.stderr)

    def test_calibrate_camera_wrapper_picks_raw_by_size(self):
        tool = HERE.parent / 'calibrate-camera.sh'
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            capture = temp / 'capture.py'
            capture.write_text("""#!/bin/sh
out=
while [ $# -gt 0 ]; do [ "$1" = "--out" ] && out=$2; shift; done
mkdir -p "$out"
# viewfinder-sized file first, then the exact RAW10 size for each sensor
head -c 8294400 /dev/zero > "$out/frame-1.bin"
case "$out" in
  *front*) head -c 10368000 /dev/zero > "$out/frame-2.bin" ;;
  *)       head -c 3136320 /dev/zero > "$out/frame-2.bin" ;;
esac
""")
            capture.chmod(0o755)
            applied = temp / 'applied.txt'
            cal = temp / 'calibrate.py'
            cal.write_text(f"""#!/bin/sh
for a in "$@"; do printf '%s ' "$a" >> {applied}; done
echo >> {applied}
""")
            cal.chmod(0o755)
            env = dict(os.environ, SP11_CAL_TEST='1', SP11_CAL_CAPTURE=str(capture),
                       SP11_CAL_TOOL=str(cal), SP11_CAL_ROOTDIR=str(temp))
            result = subprocess.run(['bash', str(tool), 'front'], env=env,
                                    input='\n\n\n\n', capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            called = applied.read_text()
            self.assertIn('--sensor imx681', called)
            self.assertIn('--neutral ' + str(temp / 'cal-front-neutral' / 'frame-2.bin'), called)
            self.assertIn('--dark ' + str(temp / 'cal-front-dark' / 'frame-2.bin'), called)
            self.assertIn('--width 3840 --height 2160 --stride 4800 --cfa RGGB --install', called)


if __name__ == '__main__':
    unittest.main(verbosity=2)
