"""Coordinator: aggrega i dati e rileva le nuove campagne candidabili."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TryberAuthError, TryberClient, TryberError
from .const import (
    DATA_AVAILABLE_LIST,
    DATA_BUGS_NEED_REVIEW,
    DATA_BUGS_NEED_REVIEW_COUNT,
    DATA_CAMPAIGNS_ACCEPTED,
    DATA_CAMPAIGNS_AVAILABLE,
    DATA_NEW_CAMPAIGNS,
    DATA_RANK,
    DATA_USER,
    DOMAIN,
    EVENT_NEW_CAMPAIGN,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class TryberCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Scarica i dati del tester e li mette a disposizione delle entita'."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TryberClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.client = client

        # Id delle campagne gia' notificate, persistiti tra i riavvii.
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}"
        )
        self._seen_ids: set[int] = set()
        self._store_loaded = False
        # Flag esplicito: distingue "mai girato" da "nessuna campagna aperta".
        self._initialized = False

    async def _async_load_seen(self) -> None:
        """Carica dallo storage gli id gia' visti (una sola volta)."""
        if self._store_loaded:
            return
        stored = await self._store.async_load() or {}
        self._seen_ids = {int(i) for i in stored.get("seen_ids", [])}
        self._initialized = bool(stored.get("initialized", False))
        self._store_loaded = True
        _LOGGER.debug("Caricate %d campagne gia' viste", len(self._seen_ids))

    async def _async_save_seen(self) -> None:
        """Salva gli id visti."""
        await self._store.async_save(
            {"seen_ids": sorted(self._seen_ids), "initialized": self._initialized}
        )

    def _detect_new(self, campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Restituisce le campagne mai viste prima.

        Al primissimo avvio consideriamo tutto come "gia' visto": altrimenti
        la prima esecuzione sparerebbe una notifica per ogni campagna aperta.
        """
        current_ids = {c["id"] for c in campaigns if c.get("id") is not None}

        if not self._initialized:
            # Prima esecuzione in assoluto: registriamo lo stato di partenza
            # senza notificare, altrimenti arriverebbe una raffica di eventi.
            self._seen_ids = current_ids
            self._initialized = True
            return []

        new_ids = current_ids - self._seen_ids
        # Teniamo solo le campagne ancora aperte, cosi' lo store non cresce
        # all'infinito; se una campagna riappare verra' segnalata di nuovo.
        self._seen_ids = current_ids
        return [c for c in campaigns if c.get("id") in new_ids]

    def _fire_events(self, new_campaigns: list[dict[str, Any]]) -> None:
        """Spara un evento sul bus per ogni nuova campagna."""
        for campaign in new_campaigns:
            _LOGGER.info(
                "Nuova campagna Tryber disponibile: %s (id %s)",
                campaign.get("name"),
                campaign.get("id"),
            )
            self.hass.bus.async_fire(EVENT_NEW_CAMPAIGN, dict(campaign))

    async def _async_update_data(self) -> dict[str, Any]:
        """Esegue le chiamate in parallelo a ogni ciclo di polling."""
        await self._async_load_seen()

        try:
            user, rank, available, accepted, need_review = await asyncio.gather(
                self.client.async_get_user(),
                self.client.async_get_rank(),
                self.client.async_get_available_campaigns(),
                self.client.async_count_accepted_campaigns(),
                self.client.async_get_need_review_bugs(),
            )
        except TryberAuthError as err:
            # Fa ripartire il flusso di ri-autenticazione in HA.
            raise ConfigEntryAuthFailed(str(err)) from err
        except TryberError as err:
            raise UpdateFailed(str(err)) from err

        new_campaigns = self._detect_new(available)
        if new_campaigns:
            self._fire_events(new_campaigns)
        await self._async_save_seen()

        need_review_count, need_review_bugs = need_review

        return {
            DATA_USER: user or {},
            DATA_RANK: rank or {},
            DATA_AVAILABLE_LIST: available,
            DATA_CAMPAIGNS_AVAILABLE: len(available),
            DATA_CAMPAIGNS_ACCEPTED: accepted,
            DATA_NEW_CAMPAIGNS: new_campaigns,
            DATA_BUGS_NEED_REVIEW: need_review_bugs,
            DATA_BUGS_NEED_REVIEW_COUNT: need_review_count,
        }
