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


def fixture(card='okay', bus='disabled', link=False, amp_status='', parent_status='', marker=None):
    chosen = ' chosen {\n  sp11,speaker-policy = %s;\n };\n' % marker if marker else ''
    return '''/dts-v1/;
/ {
%s sound {
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
''' % (chosen, card, '  wsa-dai-link {\n  };' if link else '', amp_status, bus, parent_status)


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


D26 = '"d26-open-loop-v1"'


def speakers(**kw):
    return fixture(bus='okay', link=True, **kw)


class D26Tests(unittest.TestCase):
    def test_default_profile_rejects_speakers_even_with_marker(self):
        self.assertFalse(safety.check(speakers(marker=D26))['s1_ok'])

    def test_default_profile_rejects_speakers_without_marker(self):
        self.assertFalse(safety.check(speakers())['s1_ok'])

    def test_d26_accepts_marked_speakers(self):
        result = safety.check(speakers(marker=D26), profile='d26')
        self.assertTrue(result['s1_ok'])
        self.assertTrue(result['d26_speaker_paths'])

    def test_d26_rejects_unmarked_speakers(self):
        self.assertFalse(safety.check(speakers(), profile='d26')['s1_ok'])

    def test_d26_rejects_unknown_marker_value(self):
        self.assertFalse(safety.check(speakers(marker='"yes"'), profile='d26')['s1_ok'])

    def test_marker_not_allowed_in_default_profile_on_microphone_dtb(self):
        self.assertFalse(safety.check(fixture(marker=D26))['s1_ok'])

    def test_marker_must_be_under_chosen(self):
        source = speakers().replace('sound {', 'sound {\n  sp11,speaker-policy = %s;' % D26, 1)
        self.assertFalse(safety.check(source, profile='d26')['s1_ok'])

    def test_d26_empty_tree_fails_closed(self):
        self.assertFalse(safety.check('/ {\n chosen {\n  sp11,speaker-policy = %s;\n };\n};' % D26, profile='d26')['s1_ok'])


if __name__ == '__main__':
    unittest.main()
