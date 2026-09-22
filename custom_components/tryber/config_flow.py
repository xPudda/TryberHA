"""Config flow: setup da UI con username e password."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TryberAuthError, TryberClient, TryberError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class TryberConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gestisce l'aggiunta e la ri-autenticazione dell'account Tryber."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry_data: Mapping[str, Any] | None = None

    async def _async_validate(self, username: str, password: str) -> int | None:
        """Prova il login; restituisce l'id tester o solleva un errore."""
        session = async_get_clientsession(self.hass)
        client = TryberClient(session, username, password)
        await client.async_login()
        return client.user_id

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Primo step: credenziali."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                user_id = await self._async_validate(username, password)
            except TryberAuthError:
                errors["base"] = "invalid_auth"
            except TryberError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - difesa contro errori imprevisti
                _LOGGER.exception("Errore non gestito durante il login Tryber")
                errors["base"] = "unknown"
            else:
                # Un solo config entry per tester.
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Tryber ({username})",
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Avviato quando il token non e' piu' rinnovabile (password cambiata)."""
        self._reauth_entry_data = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Chiede di nuovo la password mantenendo lo stesso username."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        username = entry.data[CONF_USERNAME]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await self._async_validate(username, password)
            except TryberAuthError:
                errors["base"] = "invalid_auth"
            except TryberError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_PASSWORD: password}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": username},
            errors=errors,
        )
