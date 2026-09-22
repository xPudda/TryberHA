"""Tryber integration for Home Assistant (tester area)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TryberClient
from .const import DOMAIN
from .coordinator import TryberCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type TryberConfigEntry = ConfigEntry[TryberCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TryberConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    session = async_get_clientsession(hass)
    client = TryberClient(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinator = TryberCoordinator(hass, entry, client)
    # First refresh: on failure HA shows the error and retries.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TryberConfigEntry) -> bool:
    """Unload the integration."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: TryberConfigEntry) -> None:
    """Reload the integration after a configuration change."""
    await hass.config_entries.async_reload(entry.entry_id)
