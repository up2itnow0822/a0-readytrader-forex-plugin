"""Tests for the ReadyTrader FOREX tool classes."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import tools.forex_tools as fx


def _mock_httpx_success(payload: dict):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=client), client


def _mock_httpx_connect_error():
    client = MagicMock()
    client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=client), client


def _mock_httpx_timeout():
    client = MagicMock()
    client.post = AsyncMock(side_effect=httpx.TimeoutException("slow"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=client), client


def _make(tool_cls, agent, **args):
    return tool_cls(agent=agent, args=args)


class TestConfig:
    def test_defaults_applied(self, set_plugin_config, mock_agent):
        set_plugin_config()
        cfg = fx._cfg(mock_agent)
        assert cfg["mcp_server_url"] == "http://localhost:8000"
        assert cfg["default_pair"] == "EURUSD"
        assert cfg["mcp_request_timeout"] == 30

    def test_url_override(self, set_plugin_config, mock_agent):
        set_plugin_config(mcp_server_url="http://fx.example.com:9000")
        cfg = fx._cfg(mock_agent)
        assert cfg["mcp_server_url"] == "http://fx.example.com:9000"

    @pytest.mark.parametrize("blocked", [
        "http://169.254.169.254/",
        "http://metadata.google.internal/",
        "http://metadata.azure.com/",
    ])
    def test_ssrf_blocked(self, set_plugin_config, mock_agent, blocked):
        set_plugin_config(mcp_server_url=blocked)
        cfg = fx._cfg(mock_agent)
        assert cfg["mcp_server_url"] == "http://localhost:8000"
        assert "_ssrf_warning" in cfg

    def test_ssrf_bad_scheme(self, set_plugin_config, mock_agent):
        set_plugin_config(mcp_server_url="ftp://example.com/")
        cfg = fx._cfg(mock_agent)
        assert cfg["mcp_server_url"] == "http://localhost:8000"
        assert "_ssrf_warning" in cfg


TOOL_CASES = [
    (fx.GetForexPrice,       {"symbol": "EURUSD"},                         "get_stock_price"),
    (fx.FetchForexOHLCV,     {"symbol": "EURUSD"},                         "fetch_ohlcv"),
    (fx.GetForexMarketBrief, {"symbol": "EURUSD"},                         "get_forex_market_brief"),
    (fx.GetForexRegime,      {"symbol": "EURUSD"},                         "get_market_regime"),
    (fx.RunForexBacktest,    {"symbol": "EURUSD", "strategy_code": "pass"}, "run_backtest_simulation"),
    (fx.GetEconomicCalendar, {},                                           "get_economic_calendar"),
    (fx.GetForexSentiment,   {},                                           "get_market_sentiment"),
]


class TestToolsSuccess:
    @pytest.mark.parametrize("tool_cls,args,expected_mcp_name", TOOL_CASES)
    async def test_success(self, set_plugin_config, mock_agent,
                            tool_cls, args, expected_mcp_name):
        set_plugin_config()
        payload = {"ok": True, "tool": expected_mcp_name}
        factory, client = _mock_httpx_success(payload)
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(tool_cls, mock_agent, **args)
            response = await tool.execute()
        assert response.break_loop is False
        parsed = json.loads(response.message)
        assert parsed == payload
        call = client.post.await_args
        assert call.kwargs["json"]["name"] == expected_mcp_name


class TestToolsOffline:
    @pytest.mark.parametrize("tool_cls,args,expected_mcp_name", TOOL_CASES)
    async def test_connect_error(self, set_plugin_config, mock_agent,
                                  tool_cls, args, expected_mcp_name):
        set_plugin_config()
        factory, _ = _mock_httpx_connect_error()
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(tool_cls, mock_agent, **args)
            response = await tool.execute()
        parsed = json.loads(response.message)
        assert parsed["error"] == "mcp_unreachable"
        assert "ReadyTrader-FOREX" in parsed["message"]

    async def test_timeout(self, set_plugin_config, mock_agent):
        set_plugin_config()
        factory, _ = _mock_httpx_timeout()
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(fx.GetForexPrice, mock_agent, symbol="EURUSD")
            response = await tool.execute()
        parsed = json.loads(response.message)
        assert parsed["error"] == "mcp_unreachable"


class TestConfigOverrideRespected:
    async def test_url_override_used(self, set_plugin_config, mock_agent):
        set_plugin_config(mcp_server_url="http://fx.example.com:1234")
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(fx.GetForexPrice, mock_agent, symbol="EURUSD")
            await tool.execute()
        call = client.post.await_args
        assert call.args[0].startswith("http://fx.example.com:1234")

    async def test_trading_mode_forwarded(self, set_plugin_config, mock_agent):
        set_plugin_config(trading_mode="live")
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(fx.GetForexPrice, mock_agent, symbol="EURUSD")
            await tool.execute()
        payload = client.post.await_args.kwargs["json"]
        assert payload["arguments"]["mode"] == "live"

    async def test_ssrf_warning_prepended(self, set_plugin_config, mock_agent):
        set_plugin_config(mcp_server_url="http://metadata.google.internal/")
        factory, _ = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(fx.GetForexPrice, mock_agent, symbol="EURUSD")
            response = await tool.execute()
        assert response.message.startswith("[WARNING]")
        assert "SSRF" in response.message


class TestPairValidation:
    @pytest.mark.parametrize("bad_pair", [
        "EURUSDX",      # too long
        "EUR",          # too short
        "eurusd",       # lowercase
        "EUR/USD",      # slash
        "EU1USD",       # digit
        "",             # empty
    ])
    @pytest.mark.parametrize("tool_cls", [
        fx.GetForexPrice, fx.FetchForexOHLCV,
        fx.GetForexMarketBrief, fx.GetForexRegime, fx.RunForexBacktest,
    ])
    async def test_invalid_pair_rejected(self, set_plugin_config, mock_agent,
                                          tool_cls, bad_pair):
        set_plugin_config()
        # Mock httpx even though we expect no call — defensive
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(tool_cls, mock_agent, symbol=bad_pair, strategy_code="pass")
            response = await tool.execute()
        assert "Invalid pair" in response.message
        client.post.assert_not_awaited()

    async def test_valid_pair_accepted(self, set_plugin_config, mock_agent):
        set_plugin_config()
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            tool = _make(fx.GetForexPrice, mock_agent, symbol="GBPJPY")
            response = await tool.execute()
        assert json.loads(response.message) == {"ok": True}
        client.post.assert_awaited_once()


class TestCalendarDaysBounds:
    async def test_default_days(self, set_plugin_config, mock_agent):
        set_plugin_config()
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            await _make(fx.GetEconomicCalendar, mock_agent).execute()
        args = client.post.await_args.kwargs["json"]["arguments"]
        assert args["days"] == fx._CALENDAR_DAYS_DEFAULT == 7

    async def test_capped_at_max(self, set_plugin_config, mock_agent):
        set_plugin_config()
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            await _make(fx.GetEconomicCalendar, mock_agent, days=999).execute()
        args = client.post.await_args.kwargs["json"]["arguments"]
        assert args["days"] == fx._CALENDAR_DAYS_MAX == 30

    async def test_min_days_one(self, set_plugin_config, mock_agent):
        set_plugin_config()
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            await _make(fx.GetEconomicCalendar, mock_agent, days=0).execute()
        args = client.post.await_args.kwargs["json"]["arguments"]
        assert args["days"] == 1

    async def test_non_int_days_uses_default(self, set_plugin_config, mock_agent):
        set_plugin_config()
        factory, client = _mock_httpx_success({"ok": True})
        with patch.object(fx.httpx, "AsyncClient", factory):
            await _make(fx.GetEconomicCalendar, mock_agent, days="banana").execute()
        args = client.post.await_args.kwargs["json"]["arguments"]
        assert args["days"] == 7


class TestStrategyCodeLimit:
    async def test_oversize_rejected(self, set_plugin_config, mock_agent):
        set_plugin_config()
        big = "x" * (fx._STRATEGY_CODE_LIMIT + 1)
        tool = _make(fx.RunForexBacktest, mock_agent, symbol="EURUSD", strategy_code=big)
        response = await tool.execute()
        assert "too large" in response.message
