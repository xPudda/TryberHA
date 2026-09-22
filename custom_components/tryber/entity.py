"""Entita' base comune a sensori e binary sensor."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TryberCoordinator


class TryberEntity(CoordinatorEntity[TryberCoordinator]):
    """Base: collega l'entita' al coordinator e al dispositivo dell'account."""

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

        # Nome del device volutamente breve e senza contesto: con il formato
        # entity ID di HA (area + device + entity) un nome lungo genererebbe
        # entity_id come sensor.tryber_nome_cognome_net_earnings.
        # Risultato atteso: sensor.tryber_net_earnings
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Tryber",
            manufacturer="AppQuality",
            model="Tester account",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://app.tryber.me/my-dashboard/",
        )
