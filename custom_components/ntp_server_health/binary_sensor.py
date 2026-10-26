"""NTP health as an automation-friendly problem sensor."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .health import AGGREGATE_UNIQUE_ID, summarize_health
from .settings import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Share polling with the measurement sensors in this config entry."""
    async_add_entities([
        *(NtpProblem(coordinator, host) for host, coordinator in entry.runtime_data.items()),
        NtpHealthGroup(entry.runtime_data),
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


class NtpHealthGroup(BinarySensorEntity):
    """Flag any configured server that is not healthy, including unavailable updates."""

    _attr_name = 'NTP Server Health Problem'
    _attr_unique_id = AGGREGATE_UNIQUE_ID
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, coordinators):
        self._coordinators = coordinators
        self._update_summary()

    @callback
    def _update_summary(self):
        self._summary = summarize_health(
            (host, coordinator.data, coordinator.last_update_success)
            for host, coordinator in self._coordinators.items()
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        for coordinator in self._coordinators.values():
            self.async_on_remove(coordinator.async_add_listener(self._handle_update))
        self._update_summary()

    @callback
    def _handle_update(self):
        self._update_summary()
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._summary['problem_count'] > 0 or self._summary['server_count'] == 0

    @property
    def extra_state_attributes(self):
        registry = er.async_get(self.hass)
        members = []
        for host in self._coordinators:
            entity_id = registry.async_get_entity_id('binary_sensor', DOMAIN, f'{host}_problem')
            if entity_id is not None:
                members.append(entity_id)
        problems = [
            {
                **problem,
                'health_entity_id': registry.async_get_entity_id(
                    'sensor', DOMAIN, f'{problem["server"]}_status'
                ),
            }
            for problem in self._summary['problems']
        ]
        return {**self._summary, 'entity_id': members, 'problems': problems}
