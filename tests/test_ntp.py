"""Exercise the real UDP client against a controlled loopback NTP server."""
import importlib.util
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'custom_components/ntp_server_health/ntp.py'
SPEC = importlib.util.spec_from_file_location('ntp_health_protocol', MODULE)
ntp = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ntp
SPEC.loader.exec_module(ntp)


class NtpProtocolTests(unittest.TestCase):
    def exchange(self, *, dispersion=0.03125, stratum=2, leap=0,
                 mode=4, version=4, wrong_origin=False, short=False,
                 missing_transmit=False, silence=False, **thresholds):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
            server.bind(('127.0.0.1', 0))
            server.settimeout(2)
            errors = []

            def respond():
                try:
                    request, address = server.recvfrom(4096)
                    if silence:
                        return
                    response = bytearray(48)
                    response[0] = (leap << 6) | (version << 3) | mode
                    response[1] = stratum
                    struct.pack_into('!iI', response, 4, -16384, int(dispersion * 65536))
                    response[12:16] = b'GPS\x00'
                    response[24:32] = bytes(8) if wrong_origin else request[40:48]
                    if not missing_transmit:
                        response[40:48] = request[40:48]
                    server.sendto(response[:20] if short else response, address)
                except Exception as err:
                    errors.append(err)

            thread = threading.Thread(target=respond)
            thread.start()
            options = dict(warning_dispersion=0.125, critical_dispersion=1.0,
                           warning_stratum=10, critical_stratum=15)
            options.update(thresholds)
            result = ntp.query('127.0.0.1', 0.1, port=server.getsockname()[1], **options)
            thread.join(3)
            self.assertFalse(thread.is_alive())
            if errors:
                raise errors[0]
            return result

    def test_decodes_signed_delay_and_unsigned_dispersion(self):
        result = self.exchange()
        self.assertEqual(result.status, 'OK')
        self.assertEqual(result.root_delay_ms, -250)
        self.assertEqual(result.root_dispersion_ms, 31.25)
        self.assertEqual(result.stratum, 2)
        self.assertEqual(result.remote_address, '127.0.0.1')

    def test_dispersion_boundaries(self):
        self.assertEqual(self.exchange(dispersion=0.125).status, 'WARNING')
        self.assertEqual(self.exchange(dispersion=1.0).status, 'CRITICAL')
        result = self.exchange(dispersion=40000)
        self.assertEqual(result.root_dispersion_ms, 40000000)
        self.assertEqual(result.status, 'CRITICAL')

    def test_stratum_boundaries_and_critical_precedence(self):
        self.assertEqual(self.exchange(stratum=10).status, 'OK')
        self.assertEqual(self.exchange(stratum=11).status, 'WARNING')
        self.assertEqual(self.exchange(stratum=15).status, 'WARNING')
        self.assertEqual(self.exchange(stratum=16).status, 'CRITICAL')
        result = self.exchange(stratum=11, dispersion=1.0)
        self.assertEqual((result.status, result.reason), ('CRITICAL', 'Root dispersion'))

    def test_leap_alarm_and_announcements(self):
        self.assertEqual(self.exchange(leap=1).status, 'OK')
        self.assertEqual(self.exchange(leap=2).status, 'OK')
        result = self.exchange(leap=3)
        self.assertEqual((result.status, result.reason), ('CRITICAL', 'Leap alarm'))
        self.assertEqual(result.root_dispersion_ms, 31.25)

    def test_rejects_invalid_packets_without_zero_measurements(self):
        for options in ({'wrong_origin': True}, {'short': True}, {'mode': 3},
                        {'version': 2}, {'stratum': 0}, {'missing_transmit': True}):
            with self.subTest(options=options):
                result = self.exchange(**options)
                self.assertEqual(result.status, 'CRITICAL')
                self.assertIsNone(result.root_dispersion_ms)
                self.assertIsNone(result.stratum)

    def test_timeout_then_recovery(self):
        failed = self.exchange(silence=True)
        self.assertEqual(failed.status, 'CRITICAL')
        self.assertIsNone(failed.root_dispersion_ms)
        recovered = self.exchange(version=3)
        self.assertEqual(recovered.status, 'OK')
        self.assertEqual(recovered.root_dispersion_ms, 31.25)


if __name__ == '__main__':
    unittest.main(verbosity=2)
