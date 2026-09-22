"""Client per le API tester di Tryber.

Gestisce l'autenticazione username/password, conserva il bearer token finche'
non scade e lo rinnova in automatico. Usa solo endpoint dell'area utente
(/users/me/...), nessun endpoint riservato allo staff.
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
    """Errore generico di comunicazione con l'API."""


class TryberAuthError(TryberError):
    """Credenziali rifiutate o token non piu' valido."""


class TryberClient:
    """Wrapper asincrono sulle API utente di Tryber."""

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
        # Evita che piu' aggiornamenti concorrenti facciano login in parallelo.
        self._auth_lock = asyncio.Lock()

    # --- proprieta' pubbliche ------------------------------------------------

    @property
    def user_id(self) -> int | None:
        """Id del tester autenticato, noto dopo il primo login."""
        return self._user_id

    # --- autenticazione ------------------------------------------------------

    @property
    def _token_valid(self) -> bool:
        """True se il token in cache e' ancora spendibile (con margine)."""
        if not self._token or not self._token_expires:
            return False
        return datetime.now(timezone.utc) < self._token_expires - TOKEN_EXPIRY_MARGIN

    async def async_login(self) -> None:
        """Ottiene un nuovo bearer token da POST /authenticate."""
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
            raise TryberError("Timeout durante l'autenticazione") from err
        except aiohttp.ClientError as err:
            raise TryberError(f"Errore di rete durante l'autenticazione: {err}") from err

        if response.status in (401, 403):
            # Il 403 HTML arriva dal WAF, il 401 JSON dall'applicazione.
            raise TryberAuthError("Credenziali rifiutate dall'API Tryber")
        if response.status != 200:
            raise TryberError(f"Login fallito (HTTP {response.status}): {text[:200]}")

        try:
            data = await response.json(content_type=None)
        except ValueError as err:
            raise TryberError("Risposta di login non in formato JSON") from err

        token = data.get("token")
        if not token:
            raise TryberAuthError("Nessun token nella risposta di login")

        self._token = token
        self._user_id = data.get("id")

        # "exp" e' un timestamp Unix; se manca, assumiamo la durata standard 24h.
        exp = data.get("exp")
        if exp:
            self._token_expires = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        else:
            self._token_expires = datetime.now(timezone.utc) + TOKEN_EXPIRY_MARGIN

        _LOGGER.debug(
            "Login Tryber riuscito per id %s, token valido fino a %s",
            self._user_id,
            self._token_expires,
        )

    async def _async_ensure_token(self) -> str:
        """Restituisce un token valido, rinnovandolo se serve."""
        async with self._auth_lock:
            if not self._token_valid:
                await self.async_login()
            # A questo punto il token c'e' per costruzione.
            return self._token  # type: ignore[return-value]

    # --- richieste -----------------------------------------------------------

    async def _async_get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        empty_on_404: bool = False,
    ) -> Any:
        """GET autenticata; su 401 rifa' il login una volta sola e riprova."""
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
                raise TryberError(f"Timeout su {path}") from err
            except aiohttp.ClientError as err:
                raise TryberError(f"Errore di rete su {path}: {err}") from err

            if response.status == 401 and attempt == 1:
                # Token scaduto prima del previsto: invalidiamo e riproviamo.
                _LOGGER.debug("401 su %s, rinnovo il token", path)
                self._token = None
                continue

            if response.status == 403:
                raise TryberAuthError(f"Accesso negato su {path}")
            if response.status == 404 and empty_on_404:
                return None
            if response.status != 200:
                raise TryberError(f"HTTP {response.status} su {path}: {text[:200]}")

            try:
                return await response.json(content_type=None)
            except ValueError as err:
                raise TryberError(f"Risposta non JSON su {path}") from err

        raise TryberAuthError(f"Autenticazione fallita su {path}")

    # --- endpoint utilizzati -------------------------------------------------

    async def async_get_user(self) -> dict[str, Any]:
        """GET /users/me con i soli campi che servono ai sensori."""
        return await self._async_get("users/me", {"fields": USER_FIELDS})

    async def async_get_rank(self) -> dict[str, Any]:
        """GET /users/me/rank: livello mensile, punti e posizione."""
        return await self._async_get("users/me/rank")

    async def async_count_accepted_campaigns(self) -> int:
        """Conta le campagne in cui sei stato selezionato.

        Chiediamo un solo elemento (limit=1): ci interessa il totale, non la
        lista. Il filtro viaggia in stile qs -> filterBy[accepted]=1.
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
        """Elenco delle campagne a cui puoi effettivamente candidarti.

        Scorre le pagine di /users/me/campaigns e tiene solo quelle con
        visibility.type == "available": le altre sono gia' candidate
        ("candidate") o non aperte a te ("unavailable").

        La query e' filtrata sulle sole campagne aperte e non concluse: senza
        filtri l'endpoint restituisce l'intero storico (1400+ voci dal 2018).
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
                # Alcune campagne risultano available ma senza posti liberi.
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
            # Ci fermiamo quando abbiamo scaricato tutto o l'API non pagina.
            if total is None or start >= int(total):
                break

        return campaigns

    async def async_get_active_campaigns(self) -> list[dict[str, Any]]:
        """Campagne in cui sei stato selezionato e che non sono ancora finite.

        Con filterBy[accepted]=1 l'API restituisce solo le candidature
        accettate, quindi l'elenco corrisponde alle campagne che stai
        effettivamente svolgendo. Una pagina basta: sono al massimo qualche
        decina. Nessun risultato significa 404, non lista vuota.
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
        """Bug per cui il team ha chiesto altre informazioni al tester.

        Il filtro sullo stato esclude per costruzione i bug gia' approvati o
        rifiutati. Quando nessun bug corrisponde, l'endpoint risponde 404
        invece di una lista vuota: va letto come "nessun bug", non come errore.
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
