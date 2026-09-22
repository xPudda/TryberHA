"""Binary sensors: handy for automations (e.g. notify when you can cash out)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TryberConfigEntry
from .const import DATA_BUGS_NEED_REVIEW, DATA_BUGS_NEED_REVIEW_COUNT, DATA_USER
from .entity import TryberEntity

THRESHOLD_DESCRIPTION = BinarySensorEntityDescription(
    key="booty_threshold_reached",
    name="Payout threshold reached",
    icon="mdi:cash-lock-open",
)

NEED_REVIEW_DESCRIPTION = BinarySensorEntityDescription(
    key="bugs_need_review",
    name="Bug info requested",
    icon="mdi:comment-question-outline",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TryberConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            TryberThresholdBinarySensor(coordinator, THRESHOLD_DESCRIPTION),
            TryberNeedReviewBinarySensor(coordinator, NEED_REVIEW_DESCRIPTION),
        ]
    )


class TryberThresholdBinarySensor(TryberEntity, BinarySensorEntity):
    """True when the accrued earnings are above the payout threshold."""

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if not data:
            return None
        threshold = data.get(DATA_USER, {}).get("booty_threshold")
        if not isinstance(threshold, dict):
            return None
        return bool(threshold.get("isOver"))


class TryberNeedReviewBinarySensor(TryberEntity, BinarySensorEntity):
    """True when at least one reported bug is waiting for more info from you.

    These are the bugs in "Need Review" state: still open, so neither approved
    nor refused.
    """

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if not data:
            return None
        return bool(data.get(DATA_BUGS_NEED_REVIEW_COUNT))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        if not data:
            return None
        return {
            "count": data.get(DATA_BUGS_NEED_REVIEW_COUNT, 0),
            "bugs": data.get(DATA_BUGS_NEED_REVIEW) or [],
        }
