#!/usr/bin/env python3
"""S1 regression cases for the microphone-only exception; no dtc needed."""
import importlib.util
from pathlib import Path
import unittest
import sys

sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location('safety', Path(__file__).with_name('kernel-dtb-safety.py'))
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)


def fixture(card='okay', bus='disabled', link=False, amp_status='', parent_status=''):
    return '''/dts-v1/;
/ {
 sound {
  compatible = "qcom,x1e80100-sndcard";
  status = "%s";
%s
 };
 soc@0 {
  soundwire@6b10000 {
   speaker@0,0 {
    compatible = "sdw20217020400";
%s
   };
   status = "%s";
  };
%s
 };
};
''' % (card, '  wsa-dai-link {\n  };' if link else '', amp_status, bus, parent_status)


class SafetyTests(unittest.TestCase):
    def test_disabled_default(self):
        self.assertTrue(safety.check(fixture(card='disabled', link=True))['s1_ok'])

    def test_microphone_only(self):
        result = safety.check(fixture())
        self.assertTrue(result['s1_ok'])
        self.assertEqual(result['microphone_only_cards'], ['/sound'])

    def test_wsa_link_rejected_even_when_disabled(self):
        source = fixture(link=True).replace('wsa-dai-link {', 'wsa-dai-link {\n   status = "disabled";')
        self.assertFalse(safety.check(source)['s1_ok'])

    def test_renamed_wsa_link_rejected(self):
        source = fixture(link=True).replace('wsa-dai-link {', 'speaker-dai-link {\n   link-name = "WSA Playback";')
        self.assertFalse(safety.check(source)['s1_ok'])

    def test_enabled_bus_rejected_even_with_disabled_amplifier(self):
        self.assertFalse(safety.check(fixture(bus='okay', amp_status='    status = "disabled";'))['s1_ok'])

    def test_enabled_amplifier_rejected(self):
        self.assertFalse(safety.check(fixture(card='disabled', bus='okay'))['s1_ok'])

    def test_effective_parent_disable_after_child(self):
        self.assertTrue(safety.check(fixture(bus='okay', parent_status='  status = "disabled";'))['s1_ok'])

    def test_missing_bus_rejected(self):
        self.assertFalse(safety.check(fixture().replace('soundwire@6b10000', 'unknown-bus'))['s1_ok'])

    def test_empty_tree_fails_closed(self):
        self.assertFalse(safety.check('/ {\n};')['s1_ok'])


if __name__ == '__main__':
    unittest.main()
