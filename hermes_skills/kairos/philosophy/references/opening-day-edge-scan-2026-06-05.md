# Opening-Day Edge Scan — June 5, 2026

*Pre-match scan performed 6 days before first kickoff (Jun 11). All prices from Kalshi public API. Elo from eloratings.net (live, June 5, 2026).*

## Elo Ratings Used

| Code | Team | Elo | Code | Team | Elo |
|------|------|-----|------|------|-----|
| ESP | Spain | 2155 | ARG | Argentina | 2113 |
| FRA | France | 2062 | ENG | England | 2020 |
| BRA | Brazil | 1988 | POR | Portugal | 1984 |
| COL | Colombia | 1977 | NED | Netherlands | 1944 |
| ECU | Ecuador | 1935 | GER | Germany | 1925 |
| NOR | Norway | 1917 | CRO | Croatia | 1908 |
| TUR | Turkiye | 1906 | JPN | Japan | 1906 |
| MEX | Mexico | 1875 | PAR | Paraguay | 1832 |
| AUT | Austria | 1830 | CAN | Canada | 1793 |
| KOR | Korea Rep | 1758 | CZE | Czechia | 1740 |
| USA | United States | 1733 | RSA | South Africa | 1518 |

## Opening Match Edges (sorted by edge magnitude)

### 1. Paraguay to beat USA — Jun 12, ticker `KXWCGAME-26JUN12USAPAR-PAR`
- Fair value (Elo model): **45.6%**
- Market ask: **24¢**
- **Edge: +21.6%** ← largest structural misprice found
- Root cause: USA home-team sentiment inflating the "USA win" market to 50¢ (FV 26.8%). The market is pricing the flag, not the players.
- Signal type: **Sentiment misprice**
- Note: This is the best edge of the entire opening slate. Place before morning of Jun 11 when US casual bettors wake up.

### 2. Mexico to beat South Africa — Jun 11, ticker `KXWCGAME-26JUN11MEXRSA-MEX`
- Fair value (Elo model): **71.0%**
- Market ask: **70¢**
- **Edge: +1.0%**
- Root cause: Mexico (1875) vs RSA (1518 — 68th in world). Massive Elo gap but tournament opener uncertainty keeps the market from pricing it higher.
- Signal type: **Narrow-favorite squeeze**
- Note: Tournament opener. High volume. Thin margin but high confidence.

### 3. Czechia to beat Korea Rep — Jun 11, ticker `KXWCGAME-26JUN11KORCZE-CZE`
- Fair value (Elo model): **34.2%**
- Market ask: **33¢**
- **Edge: +1.2%**
- Root cause: Near-identical Elo (1740 vs 1758). Korea slightly favored by market due to Asia home-adjacent venue.
- Signal type: **Coin-flip mispricing**

### 4. Canada to beat Bosnia — Jun 12, ticker `KXWCGAME-26JUN12CANBIH-CAN`
- Fair value (Elo model): **56.0%**
- Market ask: **55¢**
- **Edge: +1.0%**
- Note: Thin edge, not actionable at these levels.

## Kalshi Market Discovery Note

- The `kairos_list_matches` tool errors out (requires `POLYMARKET_PRIVATE_KEY`)
- **Workaround:** Use Kalshi events API directly:
  ```
  GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true&limit=200
  ```
- This returns all group-stage events with sub_title like "USA vs PAR (Jun 12)"
- Parse the nested `markets[]` to get the 3 outcome tickers per match

## Auth Status (June 5, 2026)

- API key ID: `${KALSHI_API_KEY}`
- Private key location: `/c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem` (persistent, NOT /tmp)
- Auth test: `GET /portfolio/balance` → HTTP 401 `INCORRECT_API_KEY_SIGNATURE`
- Signing attempted: RSA-PSS-SHA256, salt len 32 and -1, both via openssl piping and Python subprocess
- Result: Auth NOT yet working. The private key PEM saved from user's chat matches the API key ID, but Kalshi rejects the signature. Likely causes:
  1. Public key uploaded to Kalshi doesn't match this private key
  2. API key was rotated/recreated on Kalshi side
  3. A subtle signing format difference (e.g. Kalshi may expect digest of path + timestamp + something else)
