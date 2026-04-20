# Alpaca Data Service

This Supabase Edge Function proxies requests to the Alpaca Market Data API. It is used for asset discovery and historical data fetching in the Argus frontend.

## Configuration

The following secrets must be set in your Supabase project:

- `ALPACA_API_KEY`: Your Alpaca API Key ID.
- `ALPACA_SECRET_KEY`: Your Alpaca API Secret Key.

You can set these via the Supabase CLI:
```bash
supabase secrets set ALPACA_API_KEY=your_key ALPACA_SECRET_KEY=your_secret
```

## Actions

### 1. Assets Lookup
Fetches a filtered list of active US equities and crypto assets.
`GET /alpaca-data-service?action=assets`

### 2. Bars (Historical Data)
Fetches historical OHLCV data.
`GET /alpaca-data-service?action=bars&symbol=BTC/USD&timeframe=1Min&start=2024-01-01T00:00:00Z&asset_class=crypto`

## Deployment
```bash
supabase functions deploy alpaca-data-service
```
