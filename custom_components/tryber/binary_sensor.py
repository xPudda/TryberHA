"""Binary sensor: utile per automazioni (es. notifica quando puoi incassare)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TryberConfigEntry
from .const import DATA_USER
from .entity import TryberEntity

THRESHOLD_DESCRIPTION = BinarySensorEntityDescription(
    key="booty_threshold_reached",
    name="Payout threshold reached",
    icon="mdi:cash-lock-open",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TryberConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea il binary sensor."""
    async_add_entities([TryberThresholdBinarySensor(entry.runtime_data, THRESHOLD_DESCRIPTION)])


class TryberThresholdBinarySensor(TryberEntity, BinarySensorEntity):
    """True quando i compensi maturati superano la soglia di pagamento."""

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if not data:
            return None
        threshold = data.get(DATA_USER, {}).get("booty_threshold")
        if not isinstance(threshold, dict):
            return None
        return bool(threshold.get("isOver"))
