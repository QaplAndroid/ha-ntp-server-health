"""Behavioral coverage of the aggregate's server health policy."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/ntp_server_health'
SPEC = importlib.util.spec_from_file_location('ntp_group_protocol', ROOT / 'ntp.py')
ntp = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ntp
SPEC.loader.exec_module(ntp)
SPEC = importlib.util.spec_from_file_location('ntp_group_health', ROOT / 'health.py')
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


class AggregateHealthTests(unittest.TestCase):
    def test_all_servers_ok(self):
        result = health.summarize_health([
            ('a.example', ntp.Result('OK', 'Within thresholds'), True),
            ('b.example', ntp.Result('OK', 'Within thresholds'), True),
        ])
        self.assertEqual(result, {'server_count': 2, 'problem_count': 0, 'problems': []})

    def test_warning_lists_only_the_affected_server_and_reason(self):
        result = health.summarize_health([
            ('a.example', ntp.Result('OK', 'Within thresholds'), True),
            ('b.example', ntp.Result('WARNING', 'Root dispersion', stratum=3,
                                     root_dispersion_ms=200), True),
        ])
        self.assertEqual(result['problem_count'], 1)
        self.assertEqual(result['problems'], [{
            'server': 'b.example', 'status': 'WARNING', 'reason': 'Root dispersion',
            'root_dispersion_ms': 200, 'stratum': 3,
        }])

    def test_timeout_and_warning_are_both_problems(self):
        result = health.summarize_health([
            ('a.example', ntp.Result('CRITICAL', 'timed out'), True),
            ('b.example', ntp.Result('WARNING', 'Stratum 11', stratum=11), True),
        ])
        self.assertEqual(result['problem_count'], 2)
        self.assertEqual([(p['server'], p['status'], p['reason']) for p in result['problems']],
                         [('a.example', 'CRITICAL', 'timed out'),
                          ('b.example', 'WARNING', 'Stratum 11')])
        self.assertIsNone(result['problems'][0]['root_dispersion_ms'])

    def test_failed_update_does_not_reuse_stale_healthy_measurements(self):
        stale = ntp.Result('OK', 'Within thresholds', stratum=2, root_dispersion_ms=10)
        result = health.summarize_health([('a.example', stale, False)])
        self.assertEqual(result['problem_count'], 1)
        self.assertEqual(result['problems'][0]['status'], 'UNAVAILABLE')
        self.assertIsNone(result['problems'][0]['root_dispersion_ms'])
        self.assertIsNone(result['problems'][0]['stratum'])

    def test_missing_initial_result_is_not_healthy(self):
        result = health.summarize_health([('a.example', None, True)])
        self.assertEqual(result['problem_count'], 1)
        self.assertEqual(result['problems'][0]['status'], 'UNAVAILABLE')

    def test_recovery_clears_problem_details(self):
        samples = [('a.example', ntp.Result('CRITICAL', 'timed out'), True)]
        self.assertEqual(health.summarize_health(samples)['problems'][0]['reason'], 'timed out')
        samples[0] = ('a.example', ntp.Result('OK', 'Within thresholds'), True)
        self.assertEqual(health.summarize_health(samples),
                         {'server_count': 1, 'problem_count': 0, 'problems': []})

    def test_removing_failed_server_removes_its_problem(self):
        samples = [('a.example', ntp.Result('OK', 'Within thresholds'), True),
                   ('b.example', ntp.Result('CRITICAL', 'timed out'), True)]
        self.assertEqual(health.summarize_health(samples)['problems'][0]['server'], 'b.example')
        del samples[1]
        self.assertEqual(health.summarize_health(samples),
                         {'server_count': 1, 'problem_count': 0, 'problems': []})


if __name__ == '__main__':
    unittest.main(verbosity=2)
