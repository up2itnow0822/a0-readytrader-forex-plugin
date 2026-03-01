# ReadyTrader FOREX — Agent Zero Plugin

An Agent Zero plugin that connects your agent to the [ReadyTrader-FOREX](https://github.com/up2itnow0822/ReadyTrader-FOREX) MCP server. Your agent gets forex quotes, economic calendar events, market briefs, sentiment data, and backtesting through a running ReadyTrader-FOREX instance.

## What it does

- **Get forex prices** — live quotes for any currency pair
- **Economic calendar** — upcoming events that move forex markets
- **Market briefs** — quick summary of a pair's current state
- **Sentiment analysis** — news and social sentiment for currency pairs
- **Backtest strategies** — test forex strategies against historical data
- **Regime detection** — figure out if a pair is trending or chopping

## Setup

1. Install and run the [ReadyTrader-FOREX](https://github.com/up2itnow0822/ReadyTrader-FOREX) MCP server
2. Drop this plugin into your Agent Zero plugins directory
3. Configure the MCP server URL in Settings → Agent → ReadyTrader FOREX

Defaults to paper trading. Flip to live when ready.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `mcp_server_url` | `http://localhost:8000` | ReadyTrader-FOREX server address |
| `trading_mode` | `paper` | `paper` or `live` |
| `default_pair` | `EURUSD` | Default currency pair |
| `max_position_size_usd` | `1000` | Per-trade size cap |
| `max_leverage` | `10` | Maximum leverage allowed |

## License

MIT
