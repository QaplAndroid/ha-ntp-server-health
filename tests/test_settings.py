"""Exercise real settings validation and JSON transfers without Home Assistant."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'custom_components/ntp_server_health/settings.py'
SPEC = importlib.util.spec_from_file_location('ntp_health_settings', MODULE)
settings = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = settings
SPEC.loader.exec_module(settings)


class SettingsTests(unittest.TestCase):
    def document(self, values=None, **envelope):
        document = {
            'format': settings.DOMAIN,
            'version': 1,
            'settings': deepcopy(settings.DEFAULTS) if values is None else values,
        }
        document.update(envelope)
        return json.dumps(document)

    def assert_invalid(self, values, code):
        with self.assertRaises(settings.SettingsError) as raised:
            settings.normalize_settings(values)
        self.assertEqual(raised.exception.code, code)

    def assert_import_invalid(self, text, code):
        with self.assertRaises(settings.SettingsError) as raised:
            settings.import_settings(text)
        self.assertEqual(raised.exception.code, code)

    def test_normalization_does_not_modify_input(self):
        source = {'servers': ['  NTP.EXAMPLE  ', '192.0.2.10'], 'scan_interval': 30.0}
        before = deepcopy(source)
        normalized = settings.normalize_settings(source)
        self.assertEqual(normalized['servers'], ['ntp.example', '192.0.2.10'])
        self.assertIsInstance(normalized['scan_interval'], int)
        normalized['servers'].append('extra.example')
        self.assertEqual(source, before)

    def test_json_export_import_roundtrip(self):
        source = {
            'servers': [' NTP.EXAMPLE ', '2001:db8::1'],
            'scan_interval': 120,
            'timeout': 1.25,
            'warning_dispersion': 0.025,
            'critical_dispersion': 0.5,
            'warning_stratum': 3,
            'critical_stratum': 8,
        }
        exported = settings.export_settings(source)
        self.assertEqual(json.loads(exported), {
            'format': 'ntp_server_health', 'version': 1,
            'settings': settings.normalize_settings(source),
        })
        restored = settings.import_settings(exported)
        self.assertEqual(restored, settings.normalize_settings(source))
        self.assertEqual(settings.export_settings(restored), exported)
        self.assertEqual(source['servers'][0], ' NTP.EXAMPLE ')

    def test_unknown_settings_are_rejected(self):
        self.assert_invalid({'unexpected': 1}, 'unknown_settings')
        self.assert_import_invalid(self.document({**settings.DEFAULTS, 'unexpected': 1}),
                                   'unknown_settings')

    def test_import_requires_every_setting(self):
        for key in settings.DEFAULTS:
            with self.subTest(key=key):
                values = deepcopy(settings.DEFAULTS)
                del values[key]
                self.assert_import_invalid(self.document(values), 'missing_settings')

    def test_import_requires_exact_envelope(self):
        valid = json.loads(self.document())
        for key in valid:
            with self.subTest(missing=key):
                value = dict(valid)
                del value[key]
                self.assert_import_invalid(json.dumps(value), 'invalid_format')
        self.assert_import_invalid(self.document(unexpected=1), 'invalid_format')
        self.assert_import_invalid(self.document(format='another_integration'), 'invalid_format')
        for version in (0, 2, True, 1.0, '1', None):
            with self.subTest(version=version):
                self.assert_import_invalid(self.document(version=version), 'unsupported_version')
        for value in (None, [], 'settings', 42):
            with self.subTest(settings=value):
                self.assert_import_invalid(self.document(settings=value), 'invalid_settings')

    def test_malformed_and_duplicate_key_json_is_rejected(self):
        for text in ('', '{', 'not json', None, '{} trailing'):
            with self.subTest(text=text):
                self.assert_import_invalid(text, 'invalid_json')
        self.assert_import_invalid('{"format":"wrong","format":"ntp_server_health"}',
                                   'invalid_json')
        for text in ('[]', 'null', '42', '"text"'):
            with self.subTest(text=text):
                self.assert_import_invalid(text, 'invalid_format')

    def test_numeric_fields_reject_bool_strings_nonfinite_and_other_types(self):
        for key in settings.DEFAULTS.keys() - {'servers'}:
            for value in (True, False, '3', None, [], {}, float('nan'),
                          float('inf'), float('-inf'), 10 ** 1000):
                with self.subTest(key=key, value=value):
                    self.assert_invalid({key: value}, 'invalid_number')
                    full = {**settings.DEFAULTS, key: value}
                    self.assert_import_invalid(self.document(full), 'invalid_number')

    def test_integer_fields_reject_fractional_values(self):
        for key in ('scan_interval', 'warning_stratum', 'critical_stratum'):
            with self.subTest(key=key):
                self.assert_invalid({key: 10.5}, 'invalid_number')
        result = settings.normalize_settings({
            'scan_interval': 60.0, 'warning_stratum': 10.0, 'critical_stratum': 15.0,
        })
        for key in ('scan_interval', 'warning_stratum', 'critical_stratum'):
            self.assertIsInstance(result[key], int)

    def test_numeric_ranges(self):
        for key, value in (
            ('scan_interval', 9), ('timeout', 0), ('timeout', 0.099), ('timeout', 30.001),
            ('warning_dispersion', -0.001), ('critical_dispersion', -0.001),
            ('warning_stratum', 0), ('warning_stratum', 16),
            ('critical_stratum', 0), ('critical_stratum', 16),
        ):
            with self.subTest(key=key, value=value):
                self.assert_invalid({key: value}, 'out_of_range')
        result = settings.normalize_settings({
            'scan_interval': 10, 'timeout': 0.1, 'warning_dispersion': 0,
            'critical_dispersion': 0.001, 'warning_stratum': 1, 'critical_stratum': 15,
        })
        self.assertEqual(result['scan_interval'], 10)
        self.assertEqual(result['timeout'], 0.1)
        self.assertEqual(settings.normalize_settings({'timeout': 30})['timeout'], 30)
        self.assertEqual(settings.normalize_settings({'scan_interval': 100000})['scan_interval'],
                         100000)

    def test_warning_thresholds_must_be_strictly_lower(self):
        for warning, critical, code in (
            ('warning_dispersion', 'critical_dispersion', 'dispersion_order'),
            ('warning_stratum', 'critical_stratum', 'stratum_order'),
        ):
            for value in (1, 2):
                with self.subTest(warning=warning, value=value):
                    self.assert_invalid({warning: value, critical: 1}, code)

    def test_hosts_are_trimmed_lowercased_and_preserve_order(self):
        hosts = [' NTP.EXAMPLE.COM ', '192.0.2.10', '2001:DB8::1', 'local-host', 'ntp.example.']
        self.assertEqual(settings.normalize_settings({'servers': hosts})['servers'],
                         ['ntp.example.com', '192.0.2.10', '2001:db8::1',
                          'local-host', 'ntp.example.'])

    def test_duplicate_hosts_are_rejected_after_normalization(self):
        for hosts in (['example.org', 'example.org'], [' NTP.EXAMPLE ', 'ntp.example']):
            with self.subTest(hosts=hosts):
                self.assert_invalid({'servers': hosts}, 'duplicate_servers')
                self.assert_import_invalid(self.document({**settings.DEFAULTS, 'servers': hosts}),
                                           'duplicate_servers')

    def test_empty_or_non_hostname_server_values_are_rejected(self):
        for hosts in ([], 'ntp.example', None, [True], [1], [''], ['  '],
                      ['https://ntp.example'], ['ntp.example/path'], [r'ntp.example\path'],
                      ['ntp.example:123'], ['ntp example'], ['ntp\texample'],
                      ['ntp\nexample'], ['-ntp.example'], ['ntp..example'],
                      ['user@ntp.example'], ['ntp.example?query'], ['ntp.example#fragment']):
            with self.subTest(hosts=hosts):
                self.assert_invalid({'servers': hosts}, 'invalid_servers')

    def test_settings_must_be_a_dictionary(self):
        for value in (None, [], 'settings', 3):
            with self.subTest(value=value):
                self.assert_invalid(value, 'invalid_settings')


if __name__ == '__main__':
    unittest.main(verbosity=2)
