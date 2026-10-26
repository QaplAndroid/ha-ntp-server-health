"""Validated settings and versioned copy/paste configuration, without HA dependencies."""
import ipaddress
import json
import math
import re

DOMAIN = 'ntp_server_health'
DEFAULTS = {
    'servers': ['pool.ntp.org'],
    'scan_interval': 60,
    'timeout': 3,
    'warning_dispersion': 0.1,
    'critical_dispersion': 1.0,
    'warning_stratum': 10,
    'critical_stratum': 15,
}
_HOST_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z')
_INTEGER_FIELDS = {'scan_interval', 'warning_stratum', 'critical_stratum'}
_BOUNDS = {
    'scan_interval': (10, None),
    'timeout': (0.1, 30),
    'warning_dispersion': (0, None),
    'critical_dispersion': (0, None),
    'warning_stratum': (1, 15),
    'critical_stratum': (1, 15),
}


class SettingsError(ValueError):
    """A validation failure with a Home Assistant translation key."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _normalize_servers(servers):
    if not isinstance(servers, list) or not servers:
        raise SettingsError('invalid_servers')
    normalized = []
    seen = set()
    for server in servers:
        if not isinstance(server, str):
            raise SettingsError('invalid_servers')
        host = server.strip().lower()
        if not host or any(char.isspace() or char in '/\\?#@' for char in host):
            raise SettingsError('invalid_servers')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            name = host.removesuffix('.')
            if len(name) > 253 or not all(
                _HOST_LABEL.fullmatch(label) for label in name.split('.')
            ):
                raise SettingsError('invalid_servers') from None
        if host in seen:
            raise SettingsError('duplicate_servers')
        seen.add(host)
        normalized.append(host)
    return normalized


def normalize_settings(value: dict) -> dict:
    """Return complete fresh settings, filling defaults but rejecting unknown keys."""
    if not isinstance(value, dict):
        raise SettingsError('invalid_settings')
    if value.keys() - DEFAULTS.keys():
        raise SettingsError('unknown_settings')
    settings = {**DEFAULTS, **value}
    settings['servers'] = _normalize_servers(settings['servers'])
    for key, (minimum, maximum) in _BOUNDS.items():
        number = settings[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise SettingsError('invalid_number')
        try:
            finite = math.isfinite(number)
        except OverflowError:
            finite = False
        if not finite:
            raise SettingsError('invalid_number')
        if key in _INTEGER_FIELDS and number != int(number):
            raise SettingsError('invalid_number')
        if number < minimum or (maximum is not None and number > maximum):
            raise SettingsError('out_of_range')
        settings[key] = int(number) if key in _INTEGER_FIELDS else float(number)
    if settings['warning_dispersion'] >= settings['critical_dispersion']:
        raise SettingsError('dispersion_order')
    if settings['warning_stratum'] >= settings['critical_stratum']:
        raise SettingsError('stratum_order')
    return settings


def export_settings(settings: dict) -> str:
    """Export complete normalized settings in the version 1 JSON envelope."""
    return json.dumps(
        {'format': DOMAIN, 'version': 1, 'settings': normalize_settings(settings)},
        indent=2, ensure_ascii=False, allow_nan=False,
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SettingsError('invalid_json')
        result[key] = value
    return result


def import_settings(text: str) -> dict:
    """Validate a complete JSON document without modifying any current settings."""
    if not isinstance(text, str):
        raise SettingsError('invalid_json')
    try:
        document = json.loads(text, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as err:
        if isinstance(err, SettingsError):
            raise
        raise SettingsError('invalid_json') from err
    if not isinstance(document, dict) or set(document) != {'format', 'version', 'settings'}:
        raise SettingsError('invalid_format')
    if document['format'] != DOMAIN:
        raise SettingsError('invalid_format')
    if type(document['version']) is not int or document['version'] != 1:
        raise SettingsError('unsupported_version')
    settings = document['settings']
    if not isinstance(settings, dict):
        raise SettingsError('invalid_settings')
    if DEFAULTS.keys() - settings.keys():
        raise SettingsError('missing_settings')
    return normalize_settings(settings)
