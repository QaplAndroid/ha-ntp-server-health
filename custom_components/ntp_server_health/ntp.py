"""NTP wire protocol and health policy; no Home Assistant dependencies."""
from dataclasses import dataclass
import socket
import struct
import time

NTP_EPOCH = 2208988800


@dataclass(frozen=True)
class Result:
    status: str
    reason: str
    remote_address: str | None = None
    stratum: int | None = None
    root_delay_ms: float | None = None
    root_dispersion_ms: float | None = None
    leap: int | None = None
    version: int | None = None
    reference_id: str | None = None


def query(host: str, timeout: float, warning_dispersion: float,
          critical_dispersion: float, warning_stratum: int,
          critical_stratum: int, port: int = 123) -> Result:
    """Query one server. Dispersion thresholds are seconds; output is ms."""
    try:
        family, socktype, protocol, _, address = socket.getaddrinfo(
            host, port, type=socket.SOCK_DGRAM
        )[0]
        with socket.socket(family, socktype, protocol) as client:
            client.settimeout(timeout)
            client.connect(address)
            packet = bytearray(48)
            packet[0] = 0x23  # NTP v4, client mode
            now = time.time() + NTP_EPOCH
            seconds = int(now)
            struct.pack_into('!II', packet, 40, seconds & 0xFFFFFFFF,
                             int((now - seconds) * 2**32))
            client.send(packet)
            response = client.recv(4096)
            remote = client.getpeername()[0]
        if len(response) < 48:
            raise ValueError(f'Invalid NTP response: {len(response)} bytes')
        if response[24:32] != packet[40:48]:
            raise ValueError('NTP originate timestamp does not match request')
        leap = response[0] >> 6
        version = (response[0] >> 3) & 7
        if version not in (3, 4):
            raise ValueError(f'Unsupported NTP version: {version}')
        if response[0] & 7 != 4:
            raise ValueError('Invalid NTP mode (expected server)')
        stratum = response[1]
        reference_id = response[12:16].hex().upper()
        if stratum == 0:
            raise ValueError(f'Stratum 0 / Kiss-o-Death: {reference_id}')
        if response[40:48] == bytes(8):
            raise ValueError('Missing NTP transmit timestamp')
        delay = struct.unpack_from('!i', response, 4)[0] / 65536.0
        dispersion = struct.unpack_from('!I', response, 8)[0] / 65536.0
        status, reason = 'OK', 'Within thresholds'
        if leap == 3:
            status, reason = 'CRITICAL', 'Leap alarm'
        elif stratum > critical_stratum:
            status, reason = 'CRITICAL', f'Stratum {stratum}'
        elif dispersion >= critical_dispersion:
            status, reason = 'CRITICAL', 'Root dispersion'
        elif stratum > warning_stratum:
            status, reason = 'WARNING', f'Stratum {stratum}'
        elif dispersion >= warning_dispersion:
            status, reason = 'WARNING', 'Root dispersion'
        return Result(status, reason, remote, stratum, delay * 1000,
                      dispersion * 1000, leap, version, reference_id)
    except (OSError, ValueError) as err:
        return Result('CRITICAL', str(err))
