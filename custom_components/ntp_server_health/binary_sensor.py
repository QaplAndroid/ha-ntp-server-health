"""NTP health as an automation-friendly problem sensor."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    """Share polling with the measurement sensors in this config entry."""
    async_add_entities([
        NtpProblem(coordinator, host)
        for host, coordinator in entry.runtime_data.items()
    ])


class NtpProblem(CoordinatorEntity, BinarySensorEntity):
    """Mark warnings, critical results and communication failures as problems."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, host):
        super().__init__(coordinator)
        self._attr_name = f'NTP {host} Problem'
        self._attr_unique_id = f'{host}_problem'

    @property
    def available(self):
        return super().available and self.coordinator.data is not None

    @property
    def is_on(self):
        result = self.coordinator.data
        return result.status != 'OK' if result is not None else None

    @property
    def extra_state_attributes(self):
        result = self.coordinator.data
        return {'reason': result.reason} if result is not None else None
