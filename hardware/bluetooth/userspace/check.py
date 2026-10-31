#!/usr/bin/python3
"""Exercise boot-helper decisions with a fake MGMT peer, never real hardware."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
# Synthetic identity, constructed only in the temporary test directory.
ADDRESS = ":".join(f"{b:02X}" for b in (2, 1, 2, 3, 4, 5))
MOCK = '''#!/usr/bin/python3
import os, pathlib, sys
p = pathlib.Path(os.environ['BT_TEST_DIR'])
args = sys.argv[1:]
op = next(a for a in args if a in ('config', 'info', 'public-addr'))
with (p/'calls').open('a') as f: f.write(op+'\\n')
mode = os.environ['BT_TEST_MODE']
if op == 'config':
    if mode == 'query-error':
        print('Reading hci0 config failed with status 0x11 (Invalid Index)')
    else:
        calls = (p/'calls').read_text().splitlines().count('config')
        if mode == 'setup' and calls < 3:
            print('Reading hci0 config failed with status 0x11 (Invalid Index)')
        else:
            missing = '' if mode == 'configured' or (p/'set').exists() else 'public-address '
            if mode == 'external': missing = 'external public-address '
            print('hci0: Unconfigured controller')
            print('\\tsupported options: public-address ')
            print('\\tmissing options: '+missing)
elif op == 'public-addr':
    # Model BlueZ returning zero even though the operation was rejected.
    if mode == 'rejected':
        print('Set public address failed')
    else: (p/'set').write_text(args[-1])
elif (p/'set').exists():
    print('hci0: Primary controller')
    value = (p/'set').read_text()
    if mode == 'wrong-info': value = ':'.join(['00']*6)
    print('\\taddr '+value+' version 13 manufacturer 29 class 0x000000')
else:
    print('Reading hci0 info failed with status 0x12 (Not Configured)')
'''


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        mock = self.bin / 'btmgmt'
        mock.write_text(MOCK)
        mock.chmod(0o755)
        self.file = self.root / 'address'
        self.file.write_text(ADDRESS.lower() + '\r\n')
        # Isolate the installed-file lookup from any real host provisioning.
        self.helper = self.root / 'helper'
        self.helper.write_text((HERE/'sp11-bt-address').read_text().replace(
            '/etc/sp11/bt-address', str(self.root/'installed-address')).replace(
            '/run/sp11/identity-bt-mode', str(self.root/'mode')))

    def run_helper(self, mode='ready', *, matching=True, boot_source=False, cmdline='root=x'):
        env = dict(os.environ, BT_TEST_DIR=str(self.root), BT_TEST_MODE=mode,
                   PATH=str(self.bin) + ':' + os.environ['PATH'])
        # Stub hardware, boot-source absence and inter-poll sleep after sourcing.
        shell = ('. "$1"; controller_matches() { '+('true' if matching else 'false')+
                 '; }; read_cmdline() { echo "'+cmdline+'"; }; sleep() { :; }; read_boot_address() { return 1; }; main hci0'+
                 ('' if boot_source else ' "$2"'))
        result = subprocess.run(['bash', '-c', shell, 'check', str(self.helper), str(self.file)],
                                env=env, text=True, capture_output=True, timeout=15)
        self.assertNotIn(ADDRESS, result.stdout + result.stderr)
        self.assertNotIn(ADDRESS.lower(), result.stdout + result.stderr)
        return result

    def calls(self):
        p = self.root/'calls'
        return p.read_text().splitlines() if p.exists() else []

    def test_apply_and_repeat_preserves_address(self):
        self.assertEqual(self.run_helper().returncode, 0)
        self.assertEqual((self.root/'set').read_text(), ADDRESS)
        self.assertEqual(self.run_helper().returncode, 0)
        self.assertEqual(self.calls().count('public-addr'), 1)

    def test_configured_needs_no_file(self):
        self.file.unlink()
        self.assertEqual(self.run_helper('configured').returncode, 0)
        self.assertEqual(self.calls(), ['config'])

    def test_setup_race_retried(self):
        self.assertEqual(self.run_helper('setup').returncode, 0)
        self.assertEqual(self.calls().count('config'), 3)

    def test_missing_source_skips_without_writes(self):
        self.file.unlink()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0)
        self.assertIn('controller remains unconfigured; skipped', result.stderr)
        self.assertNotIn('public-addr', self.calls())

    def test_unavailable_boot_source_skips_without_writes(self):
        result = self.run_helper(boot_source=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('provision EFI/sp11/bt-address', result.stderr)
        self.assertNotIn('public-addr', self.calls())

    def test_invalid_and_sentinel_files_rejected(self):
        for value in ('bad', ':'.join(['00']*6), ':'.join(['FF']*6),
                      ':'.join(f'{b:02X}' for b in (0, 0, 0, 0, 90, 173)),
                      ADDRESS + '\n' + ADDRESS, ADDRESS + ' '*112 + 'bad'):
            with self.subTest(value_kind=len(value)):
                self.file.write_text(value)
                self.assertNotEqual(self.run_helper().returncode, 0)
                self.assertNotIn('public-addr', self.calls())

    def test_query_error_exit_zero_does_not_write(self):
        self.assertNotEqual(self.run_helper('query-error').returncode, 0)
        self.assertEqual(self.calls(), ['config']*6)

    def test_external_configuration_not_overridden(self):
        self.assertNotEqual(self.run_helper('external').returncode, 0)
        self.assertNotIn('public-addr', self.calls())

    def test_rejected_command_exit_zero_not_success(self):
        self.assertNotEqual(self.run_helper('rejected').returncode, 0)

    def test_wrong_final_address_not_success(self):
        self.assertNotEqual(self.run_helper('wrong-info').returncode, 0)

    def test_identity_none_makes_no_call_and_logs_mode(self):
        result = self.run_helper(cmdline='root=x sp11.identity=none')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn('identity mode=none', result.stderr)
        self.assertEqual((self.root/'mode').read_text().strip(), 'none')

    def test_identity_default_and_invalid_inject_and_log_mode(self):
        for cmdline in ('root=x', 'sp11.identity=inject', 'sp11.identity=bogus'):
            with self.subTest(cmdline=cmdline):
                (self.root/'set').unlink(missing_ok=True)
                (self.root/'calls').unlink(missing_ok=True)
                result = self.run_helper(cmdline=cmdline)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('identity mode=inject', result.stderr)
                self.assertIn('public-addr', self.calls())
                self.assertEqual((self.root/'mode').read_text().strip(), 'inject')

    def test_other_controller_not_changed(self):
        self.assertEqual(self.run_helper(matching=False).returncode, 0)
        self.assertEqual(self.calls(), [])

    def boot_source(self, *, invalid=False, non_iso=False):
        # Fake block node, sysfs and utilities: no real mount or disk access.
        node = self.root/'iso'
        try:
            os.mknod(node, stat.S_IFBLK | 0o600, os.makedev(7, 254))
        except PermissionError:
            self.skipTest('block-node fixture needs container CAP_MKNOD')
        disk = self.root/'disk'
        for name in ('iso', 'esp', 'unrelated'):
            d = disk/name
            d.mkdir(parents=True)
            (d/'partition').touch()
        utilities = '''#!/usr/bin/python3
import os, pathlib, shutil, sys
r = pathlib.Path(os.environ['BT_TEST_DIR'])
cmd = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if cmd == 'findmnt': print(r/'iso')
elif cmd == 'readlink':
    print(r/'disk/iso' if args[-1].startswith('/sys/class/block/') else args[-1])
elif cmd == 'blkid':
    field = args[args.index('-s')+1]
    if args[-1] == str(r/'iso'): print('ext4' if os.environ['BT_NON_ISO']=='1' else 'iso9660')
    elif args[-1] == '/dev/esp': print('BOOT' if field == 'LABEL' else 'vfat')
    else: sys.exit(1)
elif cmd == 'mount':
    assert 'ro,nosuid,nodev,noexec,umask=0077' in args
    assert args[-2] == '/dev/esp'
    (r/'mounted').touch()
    d = pathlib.Path(args[-1])/'EFI/sp11'
    d.mkdir(parents=True)
    shutil.copyfile(r/'address', d/'bt-address')
elif cmd == 'umount':
    (r/'unmounted').touch()
    shutil.rmtree(pathlib.Path(args[-1])/'EFI')
'''
        for name in ('findmnt', 'readlink', 'blkid', 'mount', 'umount'):
            p = self.bin/name
            p.write_text(utilities)
            p.chmod(0o755)
        if invalid:
            self.file.write_text('invalid')
        env = dict(os.environ, BT_TEST_DIR=str(self.root), BT_NON_ISO=str(int(non_iso)),
                   PATH=str(self.bin)+':'+os.environ['PATH'])
        shell = '. "$1"; addr=; read_boot_address'
        r = subprocess.run(['bash', '-c', shell, 'check', str(HERE/'sp11-bt-address')],
                           env=env, text=True, capture_output=True, timeout=15)
        self.assertNotIn(ADDRESS, r.stderr)
        return r

    def test_boot_source_read_only_and_unmounted(self):
        r = self.boot_source()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, ADDRESS)
        self.assertTrue((self.root/'unmounted').exists())

    def test_bad_boot_source_still_unmounted(self):
        r = self.boot_source(invalid=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, '')
        self.assertTrue((self.root/'unmounted').exists())

    def test_boot_source_not_live_iso_is_refused(self):
        self.assertNotEqual(self.boot_source(non_iso=True).returncode, 0)
        self.assertFalse((self.root/'mounted').exists())

    def test_collector_masks_addresses_and_aliases(self):
        sample = 'Controller '+ADDRESS+'\n    Alias: private-name\n/org/bluez/hci0/dev_'+ADDRESS.replace(':', '_')+'\n'
        for name in ('btmgmt', 'bluetoothctl', 'rfkill', 'systemctl', 'journalctl'):
            p = self.bin/name
            p.write_text('#!/usr/bin/python3\nprint('+repr(sample)+')\n')
            p.chmod(0o755)
        env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'])
        r = subprocess.run(['bash', str(HERE/'sp11-bt-collect')], env=env,
                           capture_output=True, text=True, check=True)
        self.assertIn('[BDADDR MASKED]', r.stdout)
        self.assertNotIn(ADDRESS, r.stdout+r.stderr)
        self.assertNotIn(ADDRESS.replace(':', '_'), r.stdout+r.stderr)
        self.assertNotIn('private-name', r.stdout+r.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
