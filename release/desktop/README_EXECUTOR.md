# AEGIS_Executor.mq5 v2.00

## What it does

1. Every `PollSeconds`, calls:
   `GET {ServerUrl}/api/executor/pending?account_id=...&symbol=EURUSD`
2. If the brain published a **BUY** or **SELL** for that account+symbol, executes `OrderSend` on the **attached chart**.
3. Reports result via `POST {ServerUrl}/api/executor/ack`.

Local file `aegis_signal.txt` remains an **optional fallback** only.

## MT5 setup (required)

1. Tools → Options → Expert Advisors  
2. Enable **Allow algorithmic trading**  
3. Enable **Allow WebRequest for listed URL**  
4. Add exactly: `https://aegis-api-0z1p.onrender.com` (or your API host, no path)  
5. Attach EA to the chart you want to trade (e.g. GBPUSD M5)  
6. Inputs:
   - `ServerUrl` = API base URL  
   - `AccountId` = AEGIS account id (e.g. ACC-…)  
   - `ApiKey` = mobile/portal API key  
7. AutoTrading button ON in toolbar  

## Server side

Brain `/aegis/analyze` publishes BUY/SELL into `ExecutorSignalService` when analysis produces a trade signal.  
Signals expire after 300s. ACK removes them so they are not repeated.

## Limits

- One magic-number position per symbol if `OnePositionOnly=true`
- Spread filter `MaxSpreadPts`
- Production still requires server-side `production_authorized` / subscription for live path; demo signals follow account plan
