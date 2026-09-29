"""
ReadyTrader FOREX tools for Agent Zero.
Wraps the ReadyTrader-FOREX MCP server to give agents access to
forex market data, economic calendars, technical analysis, and trading.
"""
import json
import re
from urllib.parse import urlparse

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.plugins import get_plugin_config


_BLOCKED_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.azure.com",
}
_DEFAULT_URL = "http://localhost:8000"
_PAIR_RE = re.compile(r"^[A-Z]{6}$")
_CALENDAR_DAYS_DEFAULT = 7
_CALENDAR_DAYS_MAX = 30
_STRATEGY_CODE_LIMIT = 20000


def _validate_url(url: str):
    try:
        parsed = urlparse(url)
    except Exception:
        return _DEFAULT_URL, f"Invalid mcp_server_url ({url!r}); falling back to {_DEFAULT_URL}."
    if parsed.scheme not in ("http", "https"):
        return _DEFAULT_URL, f"mcp_server_url must use http or https; falling back to {_DEFAULT_URL}."
    host = (parsed.hostname or "").lower()
    if not host:
        return _DEFAULT_URL, f"mcp_server_url has no host; falling back to {_DEFAULT_URL}."
    if host in _BLOCKED_HOSTS:
        return _DEFAULT_URL, (
            f"mcp_server_url host {host!r} is blocked (SSRF protection); "
            f"falling back to {_DEFAULT_URL}."
        )
    return url, None


def _cfg(agent) -> dict:
    defaults = {
        "mcp_server_url": _DEFAULT_URL,
        "trading_mode": "paper",
        "default_pair": "EURUSD",
        "default_timeframe": "1h",
        "max_position_size_usd": 1000.0,
        "mcp_request_timeout": 30,
    }
    cfg = get_plugin_config("readytrader_forex", agent=agent) or {}
    for k, v in defaults.items():
        cfg.setdefault(k, v)
    safe_url, warning = _validate_url(cfg["mcp_server_url"])
    cfg["mcp_server_url"] = safe_url
    if warning:
        cfg["_ssrf_warning"] = warning
    return cfg


async def _call_mcp(base_url: str, tool_name: str, args: dict, timeout: float = 30) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url}/mcp/call_tool",
                json={"name": tool_name, "arguments": args},
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {
            "error": "mcp_unreachable",
            "message": (
                f"MCP server unreachable at {base_url}. "
                "Start ReadyTrader-FOREX MCP server per README."
            ),
            "detail": str(e),
        }


def _format(result: dict, warning: str | None) -> str:
    body = json.dumps(result, indent=2)
    if warning:
        return f"[WARNING] {warning}\n{body}"
    return body


def _validate_pair(pair: str):
    if not _PAIR_RE.match(pair or ""):
        return Response(
            message=f"Invalid pair {pair!r}. Expected 6 uppercase letters (e.g. EURUSD).",
            break_loop=False,
        )
    return None


class GetForexPrice(Tool):
    """Fetch the current price of a forex currency pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        bad = _validate_pair(symbol)
        if bad:
            return bad
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_stock_price",
                {"symbol": symbol, "exchange": "alpaca", "mode": cfg["trading_mode"]},
                timeout=cfg["mcp_request_timeout"],
            )
            return Response(message=_format(result, cfg.get("_ssrf_warning")), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching price: {e}", break_loop=False)


class GetEconomicCalendar(Tool):
    """Fetch upcoming economic events that may affect forex markets."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        try:
            days = int(self.args.get("days", _CALENDAR_DAYS_DEFAULT))
        except (TypeError, ValueError):
            days = _CALENDAR_DAYS_DEFAULT
        days = max(1, min(days, _CALENDAR_DAYS_MAX))
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_economic_calendar",
                {"days": days},
                timeout=cfg["mcp_request_timeout"],
            )
            return Response(message=_format(result, cfg.get("_ssrf_warning")), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching calendar: {e}", break_loop=False)


class FetchForexOHLCV(Tool):
    """Fetch OHLCV candle data for a forex pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        bad = _validate_pair(symbol)
        if bad:
            return bad
        timeframe = self.args.get("timeframe", cfg["default_timeframe"])
        limit = int(self.args.get("limit", 24))
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "fetch_ohlcv",
                {"symbol": symbol, "timeframe": timeframe, "limit": limit, "mode": cfg["trading_mode"]},
                timeout=cfg["mcp_request_timeout"],
            )
            return Response(message=_format(result, cfg.get("_ssrf_warning")), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching OHLCV: {e}", break_loop=False)


class GetForexSentiment(Tool):
    """Get market sentiment for forex pairs from news and social sources."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_market_sentiment",
                {},
                timeout=cfg["mcp_request_timeout"],
            )
            return Response(message=_format(result, cfg.get("_ssrf_warning")), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching sentiment: {e}", break_loop=False)


class GetForexMarketBrief(Tool):
    """Get a market brief for a specific forex pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        bad = _validate_pair(symbol)
        if bad:
            return bad
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_forex_market_brief",
                {"symbol": symbol},
                timeout=cfg["mcp_request_timeout"],
            )
            return Response(message=_format(result, cfg.get("_ssrf_warning")), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching brief: {e}", break_loop=False)


class GetForexRegime(Tool):
    """Detect the current market regime for a forex pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        bad = _validate_pair(symbol)
        if bad:
            return bad
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_market_regime",
                {"symbol": symbol},
                timeout=cfg["mcp_request_timeout"],
            )
            return Response(message=_format(result, cfg.get("_ssrf_warning")), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching regime: {e}", break_loop=False)


class RunForexBacktest(Tool):
    """Run a backtest simulation on a forex strategy."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        bad = _validate_pair(symbol)
        if bad:
            return bad
        strategy_code = self.args.get("strategy_code", "") or ""
        if len(strategy_code) > _STRATEGY_CODE_LIMIT:
            return Response(
                message=(
                    f"strategy_code too large ({len(strategy_code)} chars, "
                    f"max {_STRATEGY_CODE_LIMIT}). Shrink the strategy or split it."
                ),
                break_loop=False,
            )
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "run_backtest_simulation",
                {
                    "strategy_code": strategy_code,
                    "symbol": symbol,
                    "timeframe": self.args.get("timeframe", cfg["default_timeframe"]),
                    "mode": cfg["trading_mode"],
                },
                timeout=cfg["mcp_request_timeout"],
            )
            return Response(message=_format(result, cfg.get("_ssrf_warning")), break_loop=False)
        except Exception as e:
            return Response(message=f"Error running backtest: {e}", break_loop=False)
