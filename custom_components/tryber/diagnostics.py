"""Diagnostics: integration state without credentials or personal data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import TryberConfigEntry
from .const import (
    DATA_BUGS_NEED_REVIEW_COUNT,
    DATA_CAMPAIGNS_ACCEPTED,
    DATA_CAMPAIGNS_ACTIVE,
    DATA_CAMPAIGNS_AVAILABLE,
    DATA_RANK,
    DATA_USER,
)

CONFIG_TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}
USER_TO_REDACT = {"name", "surname"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TryberConfigEntry
) -> dict[str, Any]:
    """Debug data downloadable from the UI.

    The file often ends up attached to a public issue, so credentials, first
    and last name and campaign titles (confidential customer information) are
    left out.
    """
    data = entry.runtime_data.data or {}

    return {
        "entry": async_redact_data(dict(entry.data), CONFIG_TO_REDACT),
        "user": async_redact_data(data.get(DATA_USER) or {}, USER_TO_REDACT),
        "rank": data.get(DATA_RANK),
        "counts": {
            "campaigns_available": data.get(DATA_CAMPAIGNS_AVAILABLE),
            "campaigns_accepted": data.get(DATA_CAMPAIGNS_ACCEPTED),
            "campaigns_active": data.get(DATA_CAMPAIGNS_ACTIVE),
            "bugs_need_review": data.get(DATA_BUGS_NEED_REVIEW_COUNT),
        },
    }
