"""Constants for the 42 Intra integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Final

DOMAIN: Final = "ft_homeassistant"
LOGGER = logging.getLogger(__package__)

API_BASE: Final = "https://api.intra.42.fr"
APPS_URL: Final = "https://profile.intra.42.fr/oauth/applications"
PROFILE_URL: Final = "https://profile.intra.42.fr/users/{login}"

CONF_LOGIN: Final = "login"
CONF_USER_ID: Final = "user_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 15  # minutes
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 120

# Start a re-authentication this long before the application secret expires.
SECRET_EXPIRY_WARNING: Final = timedelta(days=3)

# The main 42 cursus; its level is preferred over other cursus (Piscine, …).
MAIN_CURSUS_ID: Final = 21
