---
name: readytrader-forex-paper
description: "Paper forex trading through the ReadyTrader-FOREX MCP tools: rate, risk check, paper order. Never live."
version: 2.0.0
author: Bill Wilson (up2itnow0822)
tags: ["trading", "forex", "fx", "currencies", "paper-trading", "readytrader", "mcp"]
trigger_patterns:
  - paper trade forex
  - paper trade eurusd
  - forex rate readytrader
  - readytrader forex
  - fx risk check
  - economic calendar forex
---

# ReadyTrader-FOREX paper trading

The ReadyTrader FOREX plugin registers the ReadyTrader-FOREX MCP server as `readytrader_forex`, always
under that name. Its tools are called as `readytrader_forex.<tool>` with `tool_args`, for example:

```json
{"tool_name": "readytrader_forex.get_stock_price", "tool_args": {"symbol": "EURUSD"}}
```

The server runs the paper profile only: paper mode, trading halted, live execution disabled, no
broker keys. Every order is simulated against a paper FX account (USD cash, leverage 30:1) kept in
the plugin folder.

## Rules

- Currency pairs only (`EURUSD`, `GBPUSD`, `USDJPY`, `EUR/USD` also works). Amounts are units of the
  base currency (1,000 units of EURUSD is 1,000 euros), not dollars.
- Never try to enable live trading, change the server's environment, or reset the paper account
  (`readytrader_forex.reset_paper_account`) unless the user asks for a reset. If the user asks for a
  live trade, refuse: live trading is an operator process outside this plugin.
- Read every answer's `ok` first. `ok: false` carries `error.code` and `error.message`; report them.

## Procedure

1. Rate: `readytrader_forex.get_stock_price` with `{"symbol": "EURUSD"}`; the rate is `data.price`
   (`data.bid` / `data.ask` too). It sizes the order; it is not sent with it. `fetch_price_error`
   means there is no rate for that pair right now.
2. Account: `readytrader_forex.get_paper_account` shows `cash_usd`, `equity_usd`, `free_margin_usd`
   and open positions (`market_data_error` when a position cannot be priced right now). If it is
   empty, `readytrader_forex.deposit_paper_funds` with `{"asset": "USD", "amount": 10000}` (the
   account holds USD only).
3. Risk check: `readytrader_forex.validate_trade_risk` with `{"side": "buy", "symbol": "EURUSD",
   "amount_usd": <USD value of the order>, "portfolio_value": <equity_usd>}`. The USD value is the
   units times what one unit of the pair's first (base) currency is worth in USD:
   - base USD (`USDJPY`, `USDCHF`, `USDCAD`): the units themselves (400 USDJPY is 400 USD);
   - quoted in USD (`EURUSD`, `GBPUSD`, `AUDUSD`): units x the pair's rate;
   - neither (`EURGBP`, `EURJPY`): units x the base currency's USD rate from `get_stock_price`
     (`EURUSD` for `EURGBP`; for a base quoted only as `USDxxx`, units / that rate).

   Proceed only when `data.result.allowed` is `true`; otherwise report `data.result.reason` and stop.
   When `data.result.needs_confirmation` is `true`, ask the user before placing the order. `ok: true`
   only means the check ran. Each order may be at most 5% of equity. The limit applies to each order,
   not to the position: several orders can build a larger position, so tell the user when one would,
   and never split an order to get past a refusal. The server also halts trading on a pair when its
   volatility jumps.
4. Order: `readytrader_forex.place_market_order` with `{"symbol": "EURUSD", "side": "buy", "amount":
   <units>}`, with no `price` (the server fills at its market rate). The order repeats the risk check
   with its own USD valuation against the account's real equity. Done when `ok` is `true` and
   `data.venue` is `"paper"`; report `data.result` (fill rate, realized P&L, position) and
   `data.account`.
5. A refusal ends the attempt; report it, do not retry with other numbers:
   `risk_blocked` (the risk rules refused, including "Could not value ..." when the pair has no USD
   rate; `error.message` says why), `insufficient_margin`, `market_data_error` (no market rate to fill
   at), `invalid_request` (not a currency pair, or a deposit that is not USD).

## Good to know

- `readytrader_forex.get_forex_market_brief` (rate, DXY trend, calendar, headlines) and
  `readytrader_forex.get_economic_calendar` need no keys. The server's news-window rule is not
  active (the answer's `inactive_rules` says so), so check the calendar yourself before trading around
  high-impact releases.
- `get_market_news`, `get_financial_news`, `fetch_financial_news`, `get_social_sentiment` and
  `analyze_social_sentiment` need provider keys, which this plugin never passes to the server, so here
  they always answer `not_configured`. `get_forex_news` and `get_free_news` need no key; a feed that
  does not answer gives `source_unavailable`.
- `readytrader_forex.place_limit_order` fills only a marketable limit; otherwise it answers
  `limit_not_marketable`, because paper mode keeps no resting orders.
- `start_brokerage_private_ws` answers `paper_mode_not_supported`: paper orders fill at once and
  never rest at a broker.
- `run_backtest_simulation` and `run_synthetic_stress_test` execute the strategy code you pass;
  review it first.
