"""Fixtures for the 42 Intra tests."""

from __future__ import annotations

from typing import Any

import pytest

import custom_components.ft_homeassistant  # noqa: F401  (load the repo's integration)
from custom_components.ft_homeassistant.const import (
    API_BASE,
    CONF_LOGIN,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

USER_ID = 123456
LOGIN = "hdurrant"
TOKEN_URL = f"{API_BASE}/oauth/token"
USER_URL = f"{API_BASE}/v2/users/{USER_ID}"
LOGIN_URL = f"{API_BASE}/v2/users/{LOGIN}"
STATS_URL = f"{API_BASE}/v2/users/{USER_ID}/locations_stats"

# Frozen "now": Friday 2026-11-06 04:00 in the test time zone (US/Pacific).
NOW = "2026-11-06 12:00:00+00:00"

USER: dict[str, Any] = {
    "id": USER_ID,
    "login": LOGIN,
    "displayname": "Harmonie Durrant",
    "location": "c1r2p3",
    "wallet": 42,
    "correction_point": 5,
    "campus": [{"id": 1, "name": "Paris"}],
    "cursus_users": [
        {
            "cursus_id": 9,
            "level": 8.5,
            "grade": None,
            "begin_at": "2024-07-01T00:00:00.000Z",
            "cursus": {"id": 9, "name": "C Piscine"},
        },
        {
            "cursus_id": 21,
            "level": 7.42,
            "grade": "Member",
            "begin_at": "2024-10-01T00:00:00.000Z",
            "cursus": {"id": 21, "name": "42cursus"},
        },
    ],
}

STATS = {
    "2026-10-31": "05:00:00",  # before the month: ignored
    "2026-11-01": "02:00:00",  # Sunday: month only
    "2026-11-03": "03:30:00",
    "2026-11-06": "01:15:00.5",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable the repo's custom integration in every test."""
    return


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A configured entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=LOGIN,
        unique_id=str(USER_ID),
        data={
            CONF_CLIENT_ID: "u-s4t2ud-uid",
            CONF_CLIENT_SECRET: "s-s4t2ud-secret",
            CONF_LOGIN: LOGIN,
            CONF_USER_ID: USER_ID,
        },
    )


def mock_token(aioclient_mock: AiohttpClientMocker, **extra: Any) -> None:
    """Register a successful token response."""
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "token",
            "token_type": "bearer",
            "expires_in": 7200,
            **extra,
        },
    )


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock a working 42 API."""
    mock_token(aioclient_mock)
    aioclient_mock.get(USER_URL, json=USER)
    aioclient_mock.get(LOGIN_URL, json=USER)
    aioclient_mock.get(STATS_URL, json=STATS)
    return aioclient_mock
