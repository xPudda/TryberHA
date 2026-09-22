"""Coordinator: aggregates the data and detects newly applicable campaigns."""

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
    DATA_ACTIVE_LIST,
    DATA_AVAILABLE_LIST,
    DATA_BUGS_NEED_REVIEW,
    DATA_BUGS_NEED_REVIEW_COUNT,
    DATA_CAMPAIGNS_ACCEPTED,
    DATA_CAMPAIGNS_ACTIVE,
    DATA_CAMPAIGNS_AVAILABLE,
    DATA_NEW_CAMPAIGNS,
    DATA_NEW_SELECTIONS,
    DATA_RANK,
    DATA_USER,
    DOMAIN,
    EVENT_CAMPAIGN_SELECTED,
    EVENT_NEW_CAMPAIGN,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class TryberCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the tester data and hands it over to the entities."""

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

        # Ids of the campaigns already notified, persisted across restarts.
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}"
        )
        self._seen_ids: set[int] = set()
        self._seen_accepted_ids: set[int] = set()
        self._store_loaded = False
        # Explicit flags: they tell "never ran" apart from "no campaigns".
        self._initialized = False
        self._accepted_initialized = False

    async def _async_load_seen(self) -> None:
        """Load the already seen ids from storage (once)."""
        if self._store_loaded:
            return
        stored = await self._store.async_load() or {}
        self._seen_ids = {int(i) for i in stored.get("seen_ids", [])}
        self._initialized = bool(stored.get("initialized", False))
        self._seen_accepted_ids = {int(i) for i in stored.get("seen_accepted_ids", [])}
        self._accepted_initialized = bool(stored.get("accepted_initialized", False))
        self._store_loaded = True
        _LOGGER.debug(
            "Loaded %d applicable campaigns and %d selections already seen",
            len(self._seen_ids),
            len(self._seen_accepted_ids),
        )

    async def _async_save_seen(self) -> None:
        """Persist the seen ids."""
        await self._store.async_save(
            {
                "seen_ids": sorted(self._seen_ids),
                "initialized": self._initialized,
                "seen_accepted_ids": sorted(self._seen_accepted_ids),
                "accepted_initialized": self._accepted_initialized,
            }
        )

    def _detect_new(
        self,
        campaigns: list[dict[str, Any]],
        seen: set[int],
        initialized: bool,
    ) -> tuple[list[dict[str, Any]], set[int], bool]:
        """Find the campaigns never seen before.

        Returns the new campaigns, the ids to remember and the updated
        initialization flag. On the very first run everything counts as
        "already seen": otherwise every existing campaign would fire a
        notification.
        """
        current_ids = {c["id"] for c in campaigns if c.get("id") is not None}

        if not initialized:
            return [], current_ids, True

        new_ids = current_ids - seen
        # Only the campaigns still listed are remembered, so the store does not
        # grow forever; a campaign that comes back is reported again.
        return [c for c in campaigns if c.get("id") in new_ids], current_ids, True

    def _fire_events(self, event: str, campaigns: list[dict[str, Any]]) -> None:
        """Fire one bus event per campaign in the list."""
        for campaign in campaigns:
            _LOGGER.info(
                "Tryber event %s: %s (id %s)",
                event,
                campaign.get("name"),
                campaign.get("id"),
            )
            self.hass.bus.async_fire(event, dict(campaign))

    async def _async_update_data(self) -> dict[str, Any]:
        """Run the calls in parallel on every polling cycle."""
        await self._async_load_seen()

        try:
            user, rank, available, accepted, active, need_review = await asyncio.gather(
                self.client.async_get_user(),
                self.client.async_get_rank(),
                self.client.async_get_available_campaigns(),
                self.client.async_count_accepted_campaigns(),
                self.client.async_get_active_campaigns(),
                self.client.async_get_need_review_bugs(),
            )
        except TryberAuthError as err:
            # Restarts the re-authentication flow in HA. The message shown in
            # the UI comes from the "exceptions" section of strings.json, so it
            # follows the language of the Home Assistant instance.
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except TryberError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        new_campaigns, self._seen_ids, self._initialized = self._detect_new(
            available, self._seen_ids, self._initialized
        )
        if new_campaigns:
            self._fire_events(EVENT_NEW_CAMPAIGN, new_campaigns)

        (
            new_selections,
            self._seen_accepted_ids,
            self._accepted_initialized,
        ) = self._detect_new(active, self._seen_accepted_ids, self._accepted_initialized)
        if new_selections:
            self._fire_events(EVENT_CAMPAIGN_SELECTED, new_selections)

        await self._async_save_seen()

        need_review_count, need_review_bugs = need_review

        return {
            DATA_USER: user or {},
            DATA_RANK: rank or {},
            DATA_AVAILABLE_LIST: available,
            DATA_CAMPAIGNS_AVAILABLE: len(available),
            DATA_CAMPAIGNS_ACCEPTED: accepted,
            DATA_ACTIVE_LIST: active,
            DATA_CAMPAIGNS_ACTIVE: len(active),
            DATA_NEW_CAMPAIGNS: new_campaigns,
            DATA_NEW_SELECTIONS: new_selections,
            DATA_BUGS_NEED_REVIEW: need_review_bugs,
            DATA_BUGS_NEED_REVIEW_COUNT: need_review_count,
        }
