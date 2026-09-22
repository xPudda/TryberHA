"""Sensori Tryber: guadagni, esperienza, ranking e campagne."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TryberConfigEntry
from .const import (
    DATA_ACTIVE_LIST,
    DATA_AVAILABLE_LIST,
    DATA_CAMPAIGNS_ACCEPTED,
    DATA_CAMPAIGNS_ACTIVE,
    DATA_CAMPAIGNS_AVAILABLE,
    DATA_RANK,
    DATA_USER,
)
from .entity import TryberEntity


def _nested(data: dict[str, Any], *keys: str) -> Any:
    """Legge un valore annidato restituendo None se manca un livello."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


@dataclass(frozen=True, kw_only=True)
class TryberSensorDescription(SensorEntityDescription):
    """Descrizione di un sensore con la funzione che ne estrae il valore."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: tuple[TryberSensorDescription, ...] = (
    # --- Guadagni gia' liquidati --------------------------------------------
    TryberSensorDescription(
        key="booty_net",
        name="Net earnings",
        icon="mdi:cash-check",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda d: _nested(d[DATA_USER], "booty", "net", "value"),
    ),
    TryberSensorDescription(
        key="booty_gross",
        name="Gross earnings",
        icon="mdi:cash",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda d: _nested(d[DATA_USER], "booty", "gross", "value"),
    ),
    # --- Compensi maturati non ancora pagati --------------------------------
    TryberSensorDescription(
        key="pending_booty_net",
        name="Net pending earnings",
        icon="mdi:cash-clock",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda d: _nested(d[DATA_USER], "pending_booty", "net", "value"),
    ),
    TryberSensorDescription(
        key="pending_booty_gross",
        name="Gross pending earnings",
        icon="mdi:cash-clock",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda d: _nested(d[DATA_USER], "pending_booty", "gross", "value"),
    ),
    TryberSensorDescription(
        key="booty_threshold",
        name="Payout threshold",
        icon="mdi:target",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        suggested_display_precision=2,
        value_fn=lambda d: _nested(d[DATA_USER], "booty_threshold", "value"),
        attrs_fn=lambda d: {
            "threshold_reached": bool(
                _nested(d[DATA_USER], "booty_threshold", "isOver")
            )
        },
    ),
    # --- Attivita' -----------------------------------------------------------
    TryberSensorDescription(
        key="total_exp_pts",
        name="Experience points",
        icon="mdi:star-four-points",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="pts",
        value_fn=lambda d: d[DATA_USER].get("total_exp_pts"),
    ),
    TryberSensorDescription(
        key="approved_bugs",
        name="Approved bugs",
        icon="mdi:bug-check",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d[DATA_USER].get("approved_bugs"),
    ),
    TryberSensorDescription(
        key="attended_cp",
        name="Attended campaigns",
        icon="mdi:clipboard-check",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d[DATA_USER].get("attended_cp"),
    ),
    # --- Ranking mensile -----------------------------------------------------
    TryberSensorDescription(
        key="rank_position",
        name="Ranking position",
        icon="mdi:podium",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d[DATA_RANK].get("rank"),
    ),
    TryberSensorDescription(
        key="monthly_level",
        name="Monthly level",
        icon="mdi:medal",
        value_fn=lambda d: _nested(d[DATA_RANK], "level", "name"),
        attrs_fn=lambda d: {
            "previous_level": _nested(d[DATA_RANK], "previousLevel", "name"),
            "prospect_level": _nested(d[DATA_RANK], "prospect", "level", "name"),
            "next_level": _nested(
                d[DATA_RANK], "prospect", "next", "level", "name"
            ),
        },
    ),
    TryberSensorDescription(
        key="monthly_points",
        name="Monthly points",
        icon="mdi:chart-line",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pts",
        value_fn=lambda d: d[DATA_RANK].get("points"),
    ),
    TryberSensorDescription(
        key="points_to_next_level",
        name="Points to next level",
        icon="mdi:trending-up",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="pts",
        value_fn=lambda d: _nested(d[DATA_RANK], "prospect", "next", "points"),
    ),
    # --- Campagne ------------------------------------------------------------
    TryberSensorDescription(
        key="campaigns_available",
        name="Available campaigns",
        icon="mdi:bullhorn",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(DATA_CAMPAIGNS_AVAILABLE),
        # L'elenco completo finisce negli attributi: utile nei template e
        # nelle notifiche, senza dover creare un'entita' per campagna.
        attrs_fn=lambda d: {"campaigns": d.get(DATA_AVAILABLE_LIST) or []},
    ),
    TryberSensorDescription(
        key="latest_campaign",
        name="Latest available campaign",
        icon="mdi:new-box",
        value_fn=lambda d: (
            (d.get(DATA_AVAILABLE_LIST) or [{}])[0].get("name")
            if d.get(DATA_AVAILABLE_LIST)
            else None
        ),
        attrs_fn=lambda d: (
            {
                "id": (d[DATA_AVAILABLE_LIST][0]).get("id"),
                "free_spots": (d[DATA_AVAILABLE_LIST][0]).get("free_spots"),
                "total_spots": (d[DATA_AVAILABLE_LIST][0]).get("total_spots"),
                "applications_close": (d[DATA_AVAILABLE_LIST][0]).get("close_date"),
                "start_date": (d[DATA_AVAILABLE_LIST][0]).get("start_date"),
            }
            if d.get(DATA_AVAILABLE_LIST)
            else {}
        ),
    ),
    TryberSensorDescription(
        key="campaigns_accepted",
        name="Accepted campaigns",
        icon="mdi:account-check",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(DATA_CAMPAIGNS_ACCEPTED),
    ),
    TryberSensorDescription(
        key="campaigns_active",
        name="Active campaigns",
        icon="mdi:play-circle-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(DATA_CAMPAIGNS_ACTIVE),
        attrs_fn=lambda d: {"campaigns": d.get(DATA_ACTIVE_LIST) or []},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TryberConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea i sensori."""
    coordinator = entry.runtime_data
    async_add_entities(
        TryberSensor(coordinator, description) for description in SENSORS
    )


class TryberSensor(TryberEntity, SensorEntity):
    """Un sensore alimentato dal coordinator."""

    entity_description: TryberSensorDescription

    @property
    def native_value(self) -> Any:
        """Valore corrente estratto dai dati del coordinator."""
        if not self.coordinator.data:
            return None
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except (KeyError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attributi aggiuntivi, se la descrizione ne prevede."""
        if not self.coordinator.data or not self.entity_description.attrs_fn:
            return None
        try:
            attrs = self.entity_description.attrs_fn(self.coordinator.data)
        except (KeyError, TypeError):
            return None
        # Nasconde le chiavi senza valore per non sporcare la UI.
        return {k: v for k, v in attrs.items() if v is not None}
