"""
ReadyTrader FOREX tools for Agent Zero.
Wraps the ReadyTrader-FOREX MCP server to give agents access to
forex market data, economic calendars, technical analysis, and trading.
"""
import json
from typing import Optional

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.plugins import get_plugin_config


def _cfg(agent) -> dict:
    defaults = {
        "mcp_server_url": "http://localhost:8000",
        "trading_mode": "paper",
        "default_pair": "EURUSD",
        "default_timeframe": "1h",
        "max_position_size_usd": 1000.0,
    }
    cfg = get_plugin_config("readytrader-forex", agent=agent) or {}
    for k, v in defaults.items():
        cfg.setdefault(k, v)
    return cfg


async def _call_mcp(base_url: str, tool_name: str, args: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/mcp/call_tool",
            json={"name": tool_name, "arguments": args},
        )
        resp.raise_for_status()
        return resp.json()


class GetForexPrice(Tool):
    """Fetch the current price of a forex currency pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_stock_price",
                {"symbol": symbol, "exchange": "alpaca"},
            )
            return Response(message=json.dumps(result, indent=2), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching price: {e}", break_loop=False)


class GetEconomicCalendar(Tool):
    """Fetch upcoming economic events that may affect forex markets."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"], "get_economic_calendar", {}
            )
            return Response(message=json.dumps(result, indent=2), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching calendar: {e}", break_loop=False)


class FetchForexOHLCV(Tool):
    """Fetch OHLCV candle data for a forex pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        timeframe = self.args.get("timeframe", cfg["default_timeframe"])
        limit = int(self.args.get("limit", 24))
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "fetch_ohlcv",
                {"symbol": symbol, "timeframe": timeframe, "limit": limit},
            )
            return Response(message=json.dumps(result, indent=2), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching OHLCV: {e}", break_loop=False)


class GetForexSentiment(Tool):
    """Get market sentiment for forex pairs from news and social sources."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"], "get_market_sentiment", {}
            )
            return Response(message=json.dumps(result, indent=2), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching sentiment: {e}", break_loop=False)


class GetForexMarketBrief(Tool):
    """Get a market brief for a specific forex pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_forex_market_brief",
                {"symbol": symbol},
            )
            return Response(message=json.dumps(result, indent=2), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching brief: {e}", break_loop=False)


class GetForexRegime(Tool):
    """Detect the current market regime for a forex pair."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        symbol = self.args.get("symbol", cfg["default_pair"])
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "get_market_regime",
                {"symbol": symbol},
            )
            return Response(message=json.dumps(result, indent=2), break_loop=False)
        except Exception as e:
            return Response(message=f"Error fetching regime: {e}", break_loop=False)


class RunForexBacktest(Tool):
    """Run a backtest simulation on a forex strategy."""

    async def execute(self, **kwargs) -> Response:
        cfg = _cfg(self.agent)
        try:
            result = await _call_mcp(
                cfg["mcp_server_url"],
                "run_backtest_simulation",
                {
                    "strategy_code": self.args.get("strategy_code", ""),
                    "symbol": self.args.get("symbol", cfg["default_pair"]),
                    "timeframe": self.args.get("timeframe", cfg["default_timeframe"]),
                },
            )
            return Response(message=json.dumps(result, indent=2), break_loop=False)
        except Exception as e:
            return Response(message=f"Error running backtest: {e}", break_loop=False)
