"""Base entity shared by sensors and binary sensors."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TryberCoordinator


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

        # The device name is deliberately short and context-free: with the HA
        # entity ID format (area + device + entity) a long name would produce
        # entity ids such as sensor.tryber_first_last_net_earnings.
        # Expected result: sensor.tryber_net_earnings
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Tryber",
            manufacturer="AppQuality",
            model="Tester account",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://app.tryber.me/my-dashboard/",
        )
