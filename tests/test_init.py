"""Tests for setup, entities and the coordinator."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus

import pytest
from freezegun.api import FrozenDateTimeFactory

from custom_components.ft_homeassistant.api import parse_duration
from custom_components.ft_homeassistant.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from .conftest import NOW, STATS, STATS_URL, TOKEN_URL, USER, USER_ID, USER_URL, mock_token

pytestmark = pytest.mark.freeze_time(NOW)


def test_parse_duration() -> None:
    """Logtime strings are parsed, with or without microseconds."""
    assert parse_duration("04:40:36.89249") == timedelta(
        hours=4, minutes=40, seconds=36.89249
    )
    assert parse_duration("00:21:53") == timedelta(minutes=21, seconds=53)


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_states(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Entities report the profile and the logtime per period."""
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # today 01:15:00.5, week = Tue 03:30 + today, month = + Sun 02:00
    assert hass.states.get("sensor.harmonie_durrant_logtime_today").state == "1.25"
    assert hass.states.get("sensor.harmonie_durrant_logtime_this_week").state == "4.75"
    assert hass.states.get("sensor.harmonie_durrant_logtime_this_month").state == "6.75"
    assert hass.states.get("sensor.harmonie_durrant_location").state == "c1r2p3"
    assert hass.states.get("binary_sensor.harmonie_durrant_logged_in").state == STATE_ON

    level = hass.states.get("sensor.harmonie_durrant_level")
    assert level.state == "7.42"  # 42cursus preferred over the Piscine
    assert level.attributes["cursus"] == "42cursus"
    assert hass.states.get("sensor.harmonie_durrant_wallet").state == "42"
    assert hass.states.get("sensor.harmonie_durrant_evaluation_points").state == "5"
    # No secret expiry in the token response: no diagnostic sensor.
    assert hass.states.get("sensor.harmonie_durrant_application_secret_expiry") is None

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, str(USER_ID)), config_entry.entry_id
    )
    assert device is not None
    assert device.model == "Paris"

    # The logtime request uses the month start (before Monday) and HA's time zone.
    stats_call = next(c for c in mock_api.mock_calls if c[1].path.endswith("locations_stats"))
    assert stats_call[1].query["begin_at"] == "2026-11-01"
    assert stats_call[1].query["end_at"] == "2026-11-07"
    assert stats_call[1].query["time_zone"] == hass.config.time_zone

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_logged_out(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """No location means logged out."""
    mock_token(aioclient_mock)
    aioclient_mock.get(USER_URL, json={**USER, "location": None})
    aioclient_mock.get(STATS_URL, json={})
    await setup(hass, config_entry)
    assert hass.states.get("binary_sensor.harmonie_durrant_logged_in").state == STATE_OFF
    assert hass.states.get("sensor.harmonie_durrant_logtime_today").state == "0.0"


async def test_auth_failed_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A refused secret puts the entry in reauth."""
    aioclient_mock.post(TOKEN_URL, status=HTTPStatus.UNAUTHORIZED)
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_rate_limit_keeps_data(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """On a rate limit the last data is kept."""
    await setup(hass, config_entry)

    mock_api.clear_requests()
    mock_token(mock_api)
    mock_api.get(USER_URL, status=HTTPStatus.TOO_MANY_REQUESTS)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.harmonie_durrant_wallet").state == "42"


async def test_server_error_makes_unavailable(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Other errors make the entities unavailable until the next success."""
    await setup(hass, config_entry)

    mock_api.clear_requests()
    mock_token(mock_api)
    mock_api.get(USER_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.harmonie_durrant_wallet").state == STATE_UNAVAILABLE


async def test_expired_token_is_renewed(
    hass: HomeAssistant,
    mock_api: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """A 401 on a request renews the token once and retries."""
    await setup(hass, config_entry)
    coordinator = config_entry.runtime_data

    calls = {"n": 0}

    async def first_401(method, url, data):
        from pytest_homeassistant_custom_component.test_util.aiohttp import (
            AiohttpClientMockResponse,
        )

        calls["n"] += 1
        if calls["n"] == 1:
            return AiohttpClientMockResponse(method, url, status=HTTPStatus.UNAUTHORIZED)
        return AiohttpClientMockResponse(method, url, json=USER)

    mock_api.clear_requests()
    mock_token(mock_api)
    mock_api.get(USER_URL, side_effect=first_401)
    mock_api.get(STATS_URL, json=STATS)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert calls["n"] == 2
    assert sum(1 for c in mock_api.mock_calls if c[0] == "POST") == 1


async def test_secret_expiry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """When the token reports the secret expiry, show it and reauth before it."""
    # 2026-11-08 12:00 UTC: two days after NOW, inside the warning window.
    mock_token(aioclient_mock, secret_valid_until=1794139200)
    aioclient_mock.get(USER_URL, json=USER)
    aioclient_mock.get(STATS_URL, json=STATS)
    await setup(hass, config_entry)

    state = hass.states.get("sensor.harmonie_durrant_application_secret_expiry")
    assert state.state == "2026-11-08T12:00:00+00:00"
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_refresh_button(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The Refresh button fetches again."""
    await setup(hass, config_entry)
    before = mock_api.call_count
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.harmonie_durrant_refresh"},
        blocking=True,
    )
    assert mock_api.call_count == before + 2  # user + logtime, token reused
