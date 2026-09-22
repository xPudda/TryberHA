"""Constants of the Tryber integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "tryber"

# --- API ---------------------------------------------------------------------

BASE_URL: Final = "https://app.tryber.me/api"

# The WAF in front of the API rejects requests without "browser-like" headers:
# without them the answer is an HTML 403 instead of JSON.
DEFAULT_HEADERS: Final = {
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (compatible; HomeAssistant-Tryber/1.0)",
    "origin": "https://app.tryber.me",
    "referer": "https://app.tryber.me/",
}

# Fields requested from /users/me: one call instead of many.
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

# Safety margin on the token expiry: it is renewed before it really expires,
# so an update never hits a 401 halfway through.
TOKEN_EXPIRY_MARGIN: Final = timedelta(minutes=10)

# Timeout of every single HTTP request.
REQUEST_TIMEOUT: Final = 30

# --- Polling -----------------------------------------------------------------

UPDATE_INTERVAL: Final = timedelta(minutes=2)

# --- Keys of the data aggregated by the coordinator --------------------------

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

# --- Bugs waiting for more information ---------------------------------------

# States in wp_appq_evd_bug_status: 1 Refused, 2 Approved, 3 Pending,
# 4 Need Review. Only 4 puts the ball back in the tester's court: the bug is
# neither approved nor refused and the team is asking for more information.
BUG_STATUS_NEED_REVIEW: Final = 4

# /users/me/bugs matches filterBy[status] against both the id and the state
# name, so the id is enough and does not depend on the label language.
BUGS_NEED_REVIEW_QUERY: Final = {
    "filterBy[status]": BUG_STATUS_NEED_REVIEW,
    "orderBy": "id",
    "order": "DESC",
}

# How many bugs to list in the attributes; the count comes from "total" anyway.
BUGS_PAGE_SIZE: Final = 50

# --- New campaign detection --------------------------------------------------

# Event fired on the HA bus when an applicable campaign shows up.
EVENT_NEW_CAMPAIGN: Final = "tryber_new_campaign"

# Event fired when you are selected for a campaign.
EVENT_CAMPAIGN_SELECTED: Final = "tryber_campaign_selected"

# Only campaigns with this visibility.type can be applied to.
VISIBILITY_AVAILABLE: Final = "available"

# Store used to remember the campaigns already seen across restarts.
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = "tryber_seen_campaigns"

# How many campaigns to request per page.
CAMPAIGNS_PAGE_SIZE: Final = 100
# With the filters below 1-2 pages are enough; the limit is just a safety net.
CAMPAIGNS_MAX_PAGES: Final = 5

# /users/me/campaigns returns the WHOLE history (over 1400 campaigns since 2018)
# sorted from the oldest one. Without these filters the open campaigns end up at
# the bottom and are never reached.
#   filterBy[statusId]=1  -> open campaigns only (the API reads "statusId", not
#                            "statusID": with the wrong spelling the filter is
#                            silently ignored)
#   filterBy[completed]=0 -> end date from today onwards
#   orderBy=close_date DESC -> most recent first, as a further guarantee
CAMPAIGNS_QUERY: Final = {
    "filterBy[statusId]": 1,
    "filterBy[completed]": 0,
    "orderBy": "close_date",
    "order": "DESC",
}

# Campaigns you were selected for and that have not ended yet.
#   filterBy[accepted]=1  -> accepted applications only
#   filterBy[completed]=0 -> excludes the ones already finished
ACCEPTED_CAMPAIGNS_QUERY: Final = {
    "filterBy[accepted]": 1,
    "filterBy[completed]": 0,
    "orderBy": "start_date",
    "order": "DESC",
}
