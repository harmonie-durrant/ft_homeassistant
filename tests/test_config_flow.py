"""Tests for the 42 Intra config flow."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from custom_components.ft_homeassistant.const import (
    CONF_LOGIN,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from .conftest import LOGIN, LOGIN_URL, NOW, TOKEN_URL, USER, USER_ID, USER_URL, mock_token

USER_INPUT = {
    CONF_CLIENT_ID: " uid ",
    CONF_CLIENT_SECRET: "secret",
    CONF_LOGIN: "HDurrant",
}


async def test_user_flow(hass: HomeAssistant, mock_api: AiohttpClientMocker) -> None:
    """A valid form creates the entry, keyed on the user id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == LOGIN
    assert result["data"] == {
        CONF_CLIENT_ID: "uid",
        CONF_CLIENT_SECRET: "secret",
        CONF_LOGIN: LOGIN,
        CONF_USER_ID: USER_ID,
    }
    assert result["result"].unique_id == str(USER_ID)


@pytest.mark.parametrize(
    ("token_status", "user_status", "error"),
    [
        (HTTPStatus.UNAUTHORIZED, HTTPStatus.OK, {"base": "invalid_auth"}),
        (HTTPStatus.BAD_GATEWAY, HTTPStatus.OK, {"base": "cannot_connect"}),
        (HTTPStatus.OK, HTTPStatus.NOT_FOUND, {CONF_LOGIN: "user_not_found"}),
        (HTTPStatus.OK, HTTPStatus.UNPROCESSABLE_ENTITY, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    token_status: HTTPStatus,
    user_status: HTTPStatus,
    error: dict[str, str],
) -> None:
    """Errors are shown on the form, and the flow can recover."""
    if token_status == HTTPStatus.OK:
        mock_token(aioclient_mock)
    else:
        aioclient_mock.post(TOKEN_URL, status=token_status)
    aioclient_mock.get(LOGIN_URL, status=user_status, json={})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == error

    aioclient_mock.clear_requests()
    mock_token(aioclient_mock)
    aioclient_mock.get(LOGIN_URL, json=USER)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The same student can't be added twice."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.freeze_time(NOW)
async def test_reauth(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """Reauth stores the new credentials."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CLIENT_ID: "uid2", CONF_CLIENT_SECRET: "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_CLIENT_ID] == "uid2"
    assert config_entry.data[CONF_CLIENT_SECRET] == "new"
    await hass.async_block_till_done()


async def test_reauth_invalid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A refused secret keeps the form open."""
    config_entry.add_to_hass(hass)
    aioclient_mock.post(TOKEN_URL, status=HTTPStatus.UNAUTHORIZED)
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CLIENT_ID: "uid", CONF_CLIENT_SECRET: "bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.freeze_time(NOW)
async def test_reconfigure_keeps_secret(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """An empty secret in reconfigure keeps the current one."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CLIENT_ID: "uid2"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_CLIENT_ID] == "uid2"
    assert config_entry.data[CONF_CLIENT_SECRET] == "s-s4t2ud-secret"
    # Validated against the stored user id, not the login.
    assert any(call[1].path == USER_URL.removeprefix("https://api.intra.42.fr") for call in mock_api.mock_calls)
    await hass.async_block_till_done()


@pytest.mark.freeze_time(NOW)
async def test_options(
    hass: HomeAssistant, mock_api: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """The refresh interval is stored as an int."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30.0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_SCAN_INTERVAL: 30}
    await hass.async_block_till_done()
    assert config_entry.runtime_data.update_interval.total_seconds() == 30 * 60
