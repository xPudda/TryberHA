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
DATA_CAMPAIGNS_ACTIVE: Final = "campaigns_active"
DATA_AVAILABLE_LIST: Final = "available_list"
DATA_ACTIVE_LIST: Final = "active_list"
DATA_NEW_CAMPAIGNS: Final = "new_campaigns"
DATA_NEW_SELECTIONS: Final = "new_selections"
DATA_BUGS_NEED_REVIEW: Final = "bugs_need_review"
DATA_BUGS_NEED_REVIEW_COUNT: Final = "bugs_need_review_count"

# --- Bug in attesa di informazioni -------------------------------------------

# Stati in wp_appq_evd_bug_status: 1 Refused, 2 Approved, 3 Pending,
# 4 Need Review. Il 4 e' l'unico in cui la palla torna al tester: il bug non e'
# ne' approvato ne' rifiutato e il team chiede altre informazioni.
BUG_STATUS_NEED_REVIEW: Final = 4

# /users/me/bugs confronta filterBy[status] sia con l'id sia con il nome dello
# stato, quindi l'id basta e non dipende dalla lingua dell'etichetta.
BUGS_NEED_REVIEW_QUERY: Final = {
    "filterBy[status]": BUG_STATUS_NEED_REVIEW,
    "orderBy": "id",
    "order": "DESC",
}

# Quanti bug elencare negli attributi; il conteggio arriva comunque da "total".
BUGS_PAGE_SIZE: Final = 50

# --- Rilevamento nuove campagne ----------------------------------------------

# Evento sparato sul bus di HA quando compare una campagna candidabile.
EVENT_NEW_CAMPAIGN: Final = "tryber_new_campaign"

# Evento sparato quando vieni selezionato per una campagna.
EVENT_CAMPAIGN_SELECTED: Final = "tryber_campaign_selected"

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
#   filterBy[statusId]=1  -> solo campagne aperte (l'API legge "statusId", non
#                            "statusID": con la grafia sbagliata il filtro viene
#                            ignorato senza errore)
#   filterBy[completed]=0 -> data di fine da oggi in avanti
#   orderBy=close_date DESC -> le piu' recenti per prime, come ulteriore garanzia
CAMPAIGNS_QUERY: Final = {
    "filterBy[statusId]": 1,
    "filterBy[completed]": 0,
    "orderBy": "close_date",
    "order": "DESC",
}

# Campagne in cui sei stato selezionato e che non si sono ancora concluse.
#   filterBy[accepted]=1  -> solo le candidature accettate
#   filterBy[completed]=0 -> esclude quelle gia' finite
ACCEPTED_CAMPAIGNS_QUERY: Final = {
    "filterBy[accepted]": 1,
    "filterBy[completed]": 0,
    "orderBy": "start_date",
    "order": "DESC",
}
