"""Costanti dell'integrazione Tryber."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "tryber"

# --- API ---------------------------------------------------------------------

BASE_URL: Final = "https://app.tryber.me/api"

# Il WAF davanti all'API rifiuta le richieste senza header "da browser":
# senza questi header la risposta e' un 403 HTML invece del JSON.
DEFAULT_HEADERS: Final = {
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (compatible; HomeAssistant-Tryber/1.0)",
    "origin": "https://app.tryber.me",
    "referer": "https://app.tryber.me/",
}

# Campi richiesti a /users/me: una sola chiamata invece di molte.
USER_FIELDS: Final = ",".join(
    [
        "name",
        "surname",
        "booty",
        "pending_booty",
        "booty_threshold",
        "total_exp_pts",
        "attended_cp",
        "approved_bugs",
        "rank",
    ]
)

# Margine di sicurezza sulla scadenza del token: lo rinnoviamo prima che scada
# davvero, per non incappare in un 401 a meta' aggiornamento.
TOKEN_EXPIRY_MARGIN: Final = timedelta(minutes=10)

# Timeout di ogni singola richiesta HTTP.
REQUEST_TIMEOUT: Final = 30

# --- Polling -----------------------------------------------------------------

UPDATE_INTERVAL: Final = timedelta(minutes=2)

# --- Chiavi dei dati aggregati dal coordinator -------------------------------

DATA_USER: Final = "user"
DATA_RANK: Final = "rank"
DATA_CAMPAIGNS_AVAILABLE: Final = "campaigns_available"
DATA_CAMPAIGNS_ACCEPTED: Final = "campaigns_accepted"
DATA_AVAILABLE_LIST: Final = "available_list"
DATA_NEW_CAMPAIGNS: Final = "new_campaigns"

# --- Rilevamento nuove campagne ----------------------------------------------

# Evento sparato sul bus di HA quando compare una campagna candidabile.
EVENT_NEW_CAMPAIGN: Final = "tryber_new_campaign"

# Solo le campagne con questo visibility.type sono candidabili.
VISIBILITY_AVAILABLE: Final = "available"

# Store per ricordare le campagne gia' viste tra un riavvio e l'altro.
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = "tryber_seen_campaigns"

# Quante campagne chiedere per pagina.
CAMPAIGNS_PAGE_SIZE: Final = 100
# Con i filtri sotto bastano 1-2 pagine; il limite e' solo una rete di sicurezza.
CAMPAIGNS_MAX_PAGES: Final = 5

# /users/me/campaigns restituisce TUTTO lo storico (oltre 1400 campagne dal 2018)
# ordinato dalla piu' vecchia. Senza questi filtri le campagne aperte finiscono
# in fondo e non vengono mai raggiunte.
#   filterBy[statusID]=1  -> solo campagne aperte
#   filterBy[completed]=0 -> data di fine da oggi in avanti
#   orderBy=close_date DESC -> le piu' recenti per prime, come ulteriore garanzia
CAMPAIGNS_QUERY: Final = {
    "filterBy[statusID]": 1,
    "filterBy[completed]": 0,
    "orderBy": "close_date",
    "order": "DESC",
}
