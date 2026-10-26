"""Config-entry-managed NTP server health monitoring."""
import asyncio
from datetime import timedelta
from functools import partial
import logging

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .health import AGGREGATE_UNIQUE_ID
from .ntp import query
from .settings import DOMAIN, normalize_settings

_LOGGER = logging.getLogger(__name__)
PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass, entry):
    """Set up polling and entities from settings stored by the GUI."""
    options = normalize_settings(dict(entry.options or entry.data))
    coordinators = {}
    for host in options['servers']:
        async def update(host=host):
            return await hass.async_add_executor_job(partial(
                query, host, options['timeout'], options['warning_dispersion'],
                options['critical_dispersion'], options['warning_stratum'],
                options['critical_stratum'],
            ))

        coordinators[host] = DataUpdateCoordinator(
            hass, _LOGGER, name=f'NTP {host}', config_entry=entry,
            update_method=update,
            update_interval=timedelta(seconds=options['scan_interval']),
        )
    await asyncio.gather(*(
        coordinator.async_config_entry_first_refresh()
        for coordinator in coordinators.values()
    ))
    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Removed hosts must not leave orphaned entities in the registry.
    expected = {
        f'{host}_{metric}' for host in coordinators
        for metric in ('root_dispersion_ms', 'root_delay_ms', 'stratum', 'status', 'problem')
    }
    expected.add(AGGREGATE_UNIQUE_ID)
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id not in expected:
            registry.async_remove(entity.entity_id)
    return True


async def async_reload_entry(hass, entry):
    """Apply a GUI edit or JSON import without restarting Home Assistant."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Remove entities; coordinator unload callbacks stop their polling."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
