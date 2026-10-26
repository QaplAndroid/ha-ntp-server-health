"""Native setup, options, and copy/paste JSON configuration for NTP health."""
from __future__ import annotations

from typing import Any

import probatio

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .settings import (
    DEFAULTS,
    DOMAIN,
    SettingsError,
    export_settings,
    import_settings,
    normalize_settings,
)


def _settings_schema(values: dict) -> probatio.Schema:
    """Keep current values, including a failed submission, visible in the form."""
    values = dict(values)
    if isinstance(values['servers'], list):
        values['servers'] = '\n'.join(values['servers'])
    fields = {
        probatio.Required('servers', default=values['servers']): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        ),
    }
    for key, minimum, maximum, integer, seconds in (
        ('scan_interval', 10, None, True, True),
        ('timeout', 0.1, 30, False, True),
        ('warning_dispersion', 0, None, False, True),
        ('critical_dispersion', 0, None, False, True),
        ('warning_stratum', 1, 15, True, False),
        ('critical_stratum', 1, 15, True, False),
    ):
        config = selector.NumberSelectorConfig(
            min=minimum,
            step=1 if integer else 'any',
            mode=selector.NumberSelectorMode.BOX,
        )
        if maximum is not None:
            config['max'] = maximum
        if seconds:
            config['unit_of_measurement'] = 's'
        fields[probatio.Required(key, default=values[key])] = selector.NumberSelector(config)
    return probatio.Schema(fields)


def _manual_settings(user_input: dict) -> dict:
    values = dict(user_input)
    values['servers'] = values['servers'].splitlines()
    return normalize_settings(values)


def _json_schema(text: str) -> probatio.Schema:
    return probatio.Schema({
        probatio.Required('configuration', default=text): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        ),
    })


class NtpServerHealthConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create the one integration entry, manually or from a JSON document."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NtpServerHealthOptionsFlow:
        """Let Home Assistant supply the config entry to the options flow."""
        return NtpServerHealthOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')
        return self.async_show_menu(
            step_id='user', menu_options=['settings', 'import_config'],
        )

    async def _async_finish(self, settings: dict):
        """Check again at creation, including flows that were already open."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title='NTP Server Health', data=settings)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')
        errors = {}
        if user_input is not None:
            try:
                settings = _manual_settings(user_input)
            except SettingsError as err:
                errors['base'] = err.code
            else:
                return await self._async_finish(settings)
        return self.async_show_form(
            step_id='settings',
            data_schema=_settings_schema(user_input if user_input is not None else DEFAULTS),
            errors=errors,
        )

    async def async_step_import_config(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')
        errors = {}
        text = user_input['configuration'] if user_input is not None else ''
        if user_input is not None:
            try:
                settings = import_settings(text)
            except SettingsError as err:
                errors['base'] = err.code
            else:
                return await self._async_finish(settings)
        return self.async_show_form(
            step_id='import_config', data_schema=_json_schema(text), errors=errors,
        )


class NtpServerHealthOptionsFlow(config_entries.OptionsFlow):
    """Save complete replacement options, or display JSON without saving."""

    def _current_settings(self) -> dict:
        return normalize_settings(dict(self.config_entry.options or self.config_entry.data))

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(
            step_id='init', menu_options=['settings', 'import_config', 'export_config'],
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                settings = _manual_settings(user_input)
            except SettingsError as err:
                errors['base'] = err.code
            else:
                return self.async_create_entry(title='', data=settings)
        return self.async_show_form(
            step_id='settings',
            data_schema=_settings_schema(
                user_input if user_input is not None else self._current_settings()
            ),
            errors=errors,
        )

    async def async_step_import_config(self, user_input: dict[str, Any] | None = None):
        errors = {}
        text = user_input['configuration'] if user_input is not None else ''
        if user_input is not None:
            try:
                settings = import_settings(text)
            except SettingsError as err:
                errors['base'] = err.code
            else:
                return self.async_create_entry(title='', data=settings)
        return self.async_show_form(
            step_id='import_config', data_schema=_json_schema(text), errors=errors,
        )

    async def async_step_export_config(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id='export_config',
            data_schema=_json_schema(export_settings(self._current_settings())),
            last_step=False,
        )
