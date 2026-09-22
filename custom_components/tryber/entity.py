"""Base entity shared by sensors and binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_USER, DOMAIN
from .coordinator import TryberCoordinator


def _device_name(coordinator: TryberCoordinator) -> str:
    """Default device name: "Tryber <first name> <last name>".

    First and last name come from /users/me, already fetched by the first
    refresh. They fall back to a plain "Tryber" when the API does not return
    them. This is only the default: a name set by the user in the UI wins.
    """
    user: dict[str, Any] = (coordinator.data or {}).get(DATA_USER) or {}
    full_name = " ".join(
        part
        for key in ("name", "surname")
        if (part := str(user.get(key) or "").strip())
    )
    return f"Tryber {full_name}" if full_name else "Tryber"


class TryberEntity(CoordinatorEntity[TryberCoordinator]):
    """Base: links the entity to the coordinator and to the account device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TryberCoordinator,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        entry_id = coordinator.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=_device_name(coordinator),
            manufacturer="AppQuality",
            model="Tester account",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://app.tryber.me/my-dashboard/",
        )
