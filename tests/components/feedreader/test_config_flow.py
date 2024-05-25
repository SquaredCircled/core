"""The tests for the feedreader config flow."""

from unittest.mock import Mock, patch
import urllib

import pytest

from homeassistant.components.feedreader import CONF_URLS
from homeassistant.components.feedreader.const import (
    CONF_MAX_ENTRIES,
    DEFAULT_MAX_ENTRIES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import URL, VALID_CONFIG_DEFAULT

from tests.common import MockConfigEntry


@pytest.fixture(name="feedparser")
def feedparser_fixture(feed_one_event: bytes) -> Mock:
    """Patch libraries."""
    with (
        patch(
            "homeassistant.components.feedreader.config_flow.feedparser.http.get",
            return_value=feed_one_event,
        ) as feedparser,
    ):
        yield feedparser


@pytest.fixture(name="setup_entry")
def fsetup_entry_fixture(feed_one_event: bytes) -> Mock:
    """Patch libraries."""
    with (
        patch("homeassistant.components.feedreader.async_setup_entry") as setup_entry,
    ):
        yield setup_entry


async def test_user(hass: HomeAssistant, feedparser, setup_entry) -> None:
    """Test starting a flow by user."""
    # init user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: URL, CONF_MAX_ENTRIES: 5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RSS Sample"
    assert result["data"][CONF_URL] == URL
    assert result["data"][CONF_MAX_ENTRIES] == 5


async def test_import(hass: HomeAssistant, feedparser, setup_entry) -> None:
    """Test starting an import flow."""
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert not config_entries

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_URLS: [URL]}})

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert config_entries
    assert len(config_entries) == 1
    assert config_entries[0].title == "RSS Sample"
    assert config_entries[0].data[CONF_URL] == URL
    assert config_entries[0].data[CONF_MAX_ENTRIES] == DEFAULT_MAX_ENTRIES

    assert ir.async_get(hass).async_get_issue(HA_DOMAIN, "deprecated_yaml_feedreader")


async def test_user_errors(
    hass: HomeAssistant, feedparser, setup_entry, feed_one_event
) -> None:
    """Test starting a flow by user which results in an URL error."""
    # init user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # raise URLError
    feedparser.side_effect = urllib.error.URLError("Test")
    feedparser.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: URL, CONF_MAX_ENTRIES: 5}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "url_error"}

    # no feed entries returned
    feedparser.side_effect = None
    feedparser.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: URL, CONF_MAX_ENTRIES: 5}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_feed_entries"}

    # success
    feedparser.side_effect = None
    feedparser.return_value = feed_one_event
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_URL: URL, CONF_MAX_ENTRIES: 5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RSS Sample"
    assert result["data"][CONF_URL] == URL
    assert result["data"][CONF_MAX_ENTRIES] == 5


async def test_reconfigure(hass: HomeAssistant, feedparser) -> None:
    """Test starting a reconfigure flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # init user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    # success
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_async_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "http://other.rss.local/rss_feed.xml",
                CONF_MAX_ENTRIES: 10,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_URL: "http://other.rss.local/rss_feed.xml",
        CONF_MAX_ENTRIES: 10,
    }

    await hass.async_block_till_done()
    assert mock_async_reload.call_count == 1


async def test_reconfigure_errors(
    hass: HomeAssistant, feedparser, setup_entry, feed_one_event
) -> None:
    """Test starting a reconfigure flow by user which results in an URL error."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)

    # init user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    # raise URLError
    feedparser.side_effect = urllib.error.URLError("Test")
    feedparser.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: "http://other.rss.local/rss_feed.xml",
            CONF_MAX_ENTRIES: 10,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"
    assert result["errors"] == {"base": "url_error"}

    # no feed entries returned
    feedparser.side_effect = None
    feedparser.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: "http://other.rss.local/rss_feed.xml",
            CONF_MAX_ENTRIES: 10,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"
    assert result["errors"] == {"base": "no_feed_entries"}

    # success
    feedparser.side_effect = None
    feedparser.return_value = feed_one_event

    # success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_URL: "http://other.rss.local/rss_feed.xml",
            CONF_MAX_ENTRIES: 10,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_URL: "http://other.rss.local/rss_feed.xml",
        CONF_MAX_ENTRIES: 10,
    }
