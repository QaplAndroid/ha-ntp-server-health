"""NTP measurements, server time, and health state."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .settings import DOMAIN

METRICS = {
    'root_dispersion_ms': ('Root dispersion', 'ms', 'mdi:timer-alert-outline'),
    'root_delay_ms': ('Root delay', 'ms', 'mdi:timer-outline'),
    'stratum': ('Stratum', None, 'mdi:layers-outline'),
    'status': ('Health', None, 'mdi:server-security'),
    'server_time': ('Server time', None, 'mdi:clock-outline'),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Load measurements using the entry's shared per-server results."""
    async_add_entities([
        NtpSensor(coordinator, host, metric)
        for host, coordinator in entry.runtime_data.items()
        for metric in METRICS
    ])


class NtpSensor(CoordinatorEntity, SensorEntity):
    """One value from one shared NTP query."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, host, metric):
        super().__init__(coordinator)
        label, unit, icon = METRICS[metric]
        self._metric = metric
        self._attr_name = label
        self._attr_unique_id = f'{host}_{metric}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)}, name=f'NTP {host}', model='NTP server',
        )
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if metric == 'server_time':
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def available(self):
        result = self.coordinator.data
        return super().available and result is not None and (
            self._metric == 'status' or getattr(result, self._metric) is not None
        )

    @property
    def native_value(self):
        result = self.coordinator.data
        return getattr(result, self._metric) if result is not None else None

    @property
    def extra_state_attributes(self):
        if self._metric != 'status' or self.coordinator.data is None:
            return None
        result = self.coordinator.data
        return {
            'reason': result.reason,
            'remote_address': result.remote_address,
            'leap_indicator': result.leap,
            'ntp_version': result.version,
            'reference_id': result.reference_id,
        }
