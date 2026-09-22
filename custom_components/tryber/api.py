"""Client for the Tryber tester API.

Handles username/password authentication, keeps the bearer token until it
expires and renews it automatically. Only user-area endpoints are used
(/users/me/...), never staff-only ones.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import (
    ACCEPTED_CAMPAIGNS_QUERY,
    BASE_URL,
    BUGS_NEED_REVIEW_QUERY,
    BUGS_PAGE_SIZE,
    CAMPAIGNS_MAX_PAGES,
    CAMPAIGNS_PAGE_SIZE,
    CAMPAIGNS_QUERY,
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT,
    TOKEN_EXPIRY_MARGIN,
    USER_FIELDS,
    VISIBILITY_AVAILABLE,
)

_LOGGER = logging.getLogger(__name__)


class TryberError(Exception):
    """Generic API communication error."""


class TryberAuthError(TryberError):
    """Credentials rejected or token no longer valid."""


class TryberClient:
    """Async wrapper around the Tryber user API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password

        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._user_id: int | None = None
        # Prevents concurrent updates from logging in at the same time.
        self._auth_lock = asyncio.Lock()

    # --- public properties ---------------------------------------------------

    @property
    def user_id(self) -> int | None:
        """Id of the authenticated tester, known after the first login."""
        return self._user_id

    # --- authentication ------------------------------------------------------

    @property
    def _token_valid(self) -> bool:
        """True while the cached token is still usable (with a margin)."""
        if not self._token or not self._token_expires:
            return False
        return datetime.now(timezone.utc) < self._token_expires - TOKEN_EXPIRY_MARGIN

    def _redacted(self, text: str) -> str:
        """Strip the password from a response body.

        On wrong credentials the API echoes the password back in clear text
        inside the error message ("Password xxx not matching utente"): without
        this cleanup it would end up in the Home Assistant logs.
        """
        if not self._password:
            return text
        return text.replace(self._password, "***")

    async def async_login(self) -> None:
        """Get a new bearer token from POST /authenticate."""
        payload = {"username": self._username, "password": self._password}

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.post(
                    f"{BASE_URL}/authenticate",
                    json=payload,
                    headers={**DEFAULT_HEADERS, "content-type": "application/json"},
                )
                text = await response.text()
        except asyncio.TimeoutError as err:
            raise TryberError("Timeout while authenticating") from err
        except aiohttp.ClientError as err:
            raise TryberError(f"Network error while authenticating: {err}") from err

        if response.status in (401, 403):
            # The HTML 403 comes from the WAF, the JSON 401 from the app.
            raise TryberAuthError("Credentials rejected by the Tryber API")
        if response.status != 200:
            raise TryberError(
                f"Login failed (HTTP {response.status}): {self._redacted(text)[:200]}"
            )

        try:
            data = await response.json(content_type=None)
        except ValueError as err:
            raise TryberError("Login response is not JSON") from err

        token = data.get("token")
        if not token:
            raise TryberAuthError("No token in the login response")

        self._token = token
        self._user_id = data.get("id")

        # "exp" is a Unix timestamp; when missing we assume the standard 24h.
        exp = data.get("exp")
        if exp:
            self._token_expires = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        else:
            self._token_expires = datetime.now(timezone.utc) + TOKEN_EXPIRY_MARGIN

        _LOGGER.debug(
            "Tryber login succeeded for id %s, token valid until %s",
            self._user_id,
            self._token_expires,
        )

    async def _async_ensure_token(self) -> str:
        """Return a valid token, renewing it when needed."""
        async with self._auth_lock:
            if not self._token_valid:
                await self.async_login()
            # At this point the token exists by construction.
            return self._token  # type: ignore[return-value]

    # --- requests ------------------------------------------------------------

    async def _async_get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        empty_on_404: bool = False,
    ) -> Any:
        """Authenticated GET; on 401 it logs in again once and retries."""
        for attempt in (1, 2):
            token = await self._async_ensure_token()
            headers = {**DEFAULT_HEADERS, "authorization": f"Bearer {token}"}

            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    response = await self._session.get(
                        f"{BASE_URL}/{path.lstrip('/')}",
                        params=params,
                        headers=headers,
                    )
                    text = await response.text()
            except asyncio.TimeoutError as err:
                raise TryberError(f"Timeout on {path}") from err
            except aiohttp.ClientError as err:
                raise TryberError(f"Network error on {path}: {err}") from err

            if response.status == 401 and attempt == 1:
                # Token expired earlier than expected: drop it and retry.
                _LOGGER.debug("401 on %s, renewing the token", path)
                self._token = None
                continue

            if response.status == 403:
                raise TryberAuthError(f"Access denied on {path}")
            if response.status == 404 and empty_on_404:
                return None
            if response.status != 200:
                raise TryberError(f"HTTP {response.status} on {path}: {text[:200]}")

            try:
                return await response.json(content_type=None)
            except ValueError as err:
                raise TryberError(f"Non-JSON response on {path}") from err

        raise TryberAuthError(f"Authentication failed on {path}")

    # --- endpoints used ------------------------------------------------------

    async def async_get_user(self) -> dict[str, Any]:
        """GET /users/me with only the fields the sensors need."""
        return await self._async_get("users/me", {"fields": USER_FIELDS})

    async def async_get_rank(self) -> dict[str, Any]:
        """GET /users/me/rank: monthly level, points and position."""
        return await self._async_get("users/me/rank")

    async def async_count_accepted_campaigns(self) -> int:
        """Count the campaigns the tester has been selected for.

        Only one item is requested (limit=1): what matters is the total, not
        the list. The filter travels qs-style -> filterBy[accepted]=1.
        """
        data = await self._async_get(
            "users/me/campaigns",
            {"limit": 1, "start": 0, "filterBy[accepted]": 1},
            empty_on_404=True,
        )
        if not isinstance(data, dict):
            return 0
        total = data.get("total")
        if total is None:
            total = len(data.get("results") or [])
        return int(total)

    async def async_get_available_campaigns(self) -> list[dict[str, Any]]:
        """List the campaigns the tester can actually apply to.

        Pages through /users/me/campaigns and keeps only the ones with
        visibility.type == "available": the others are already applied to
        ("candidate") or not open to this tester ("unavailable").

        The query is filtered to open, unfinished campaigns only: without
        filters the endpoint returns the whole history (1400+ entries
        since 2018).
        """
        campaigns: list[dict[str, Any]] = []
        start = 0

        for _ in range(CAMPAIGNS_MAX_PAGES):
            data = await self._async_get(
                "users/me/campaigns",
                {**CAMPAIGNS_QUERY, "limit": CAMPAIGNS_PAGE_SIZE, "start": start},
                empty_on_404=True,
            )
            if not isinstance(data, dict):
                break

            results = data.get("results") or []
            if not results:
                break

            for item in results:
                if not isinstance(item, dict):
                    continue
                visibility = item.get("visibility") or {}
                if visibility.get("type") != VISIBILITY_AVAILABLE:
                    continue
                # Some campaigns are available but have no free spots left.
                free_spots = visibility.get("freeSpots")
                campaigns.append(
                    {
                        "id": item.get("id"),
                        "name": item.get("name") or item.get("customer_title"),
                        "start_date": (item.get("dates") or {}).get("start"),
                        "end_date": (item.get("dates") or {}).get("end"),
                        "close_date": (item.get("dates") or {}).get("close"),
                        "free_spots": free_spots,
                        "total_spots": visibility.get("totalSpots"),
                        "applied": bool(item.get("applied")),
                    }
                )

            start += len(results)
            total = data.get("total")
            # Stop once everything is fetched or the API stops paginating.
            if total is None or start >= int(total):
                break

        return campaigns

    async def async_get_active_campaigns(self) -> list[dict[str, Any]]:
        """Campaigns the tester was selected for and that are still running.

        With filterBy[accepted]=1 the API returns accepted applications only,
        so the list matches the campaigns currently being worked on. A single
        page is enough: there are a few dozen at most. No result means a 404,
        not an empty list.
        """
        data = await self._async_get(
            "users/me/campaigns",
            {**ACCEPTED_CAMPAIGNS_QUERY, "limit": CAMPAIGNS_PAGE_SIZE, "start": 0},
            empty_on_404=True,
        )
        if not isinstance(data, dict):
            return []

        campaigns: list[dict[str, Any]] = []
        for item in data.get("results") or []:
            if not isinstance(item, dict):
                continue
            dates = item.get("dates") or {}
            campaigns.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "start_date": dates.get("start"),
                    "end_date": dates.get("end"),
                    "close_date": dates.get("close"),
                    "campaign_type": item.get("campaign_type"),
                }
            )

        return campaigns

    async def async_get_need_review_bugs(self) -> tuple[int, list[dict[str, Any]]]:
        """Bugs for which the team asked the tester for more information.

        The status filter excludes approved and refused bugs by construction.
        When no bug matches, the endpoint answers 404 instead of an empty
        list: that must be read as "no bugs", not as an error.
        """
        data = await self._async_get(
            "users/me/bugs",
            {**BUGS_NEED_REVIEW_QUERY, "limit": BUGS_PAGE_SIZE, "start": 0},
            empty_on_404=True,
        )
        if not isinstance(data, dict):
            return 0, []

        bugs: list[dict[str, Any]] = []
        for item in data.get("results") or []:
            if not isinstance(item, dict):
                continue
            campaign = item.get("campaign") or {}
            bugs.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "campaign_id": campaign.get("id"),
                    "campaign": campaign.get("name"),
                    "severity": (item.get("severity") or {}).get("name"),
                }
            )

        total = data.get("total")
        count = int(total) if total is not None else len(bugs)
        return count, bugs
