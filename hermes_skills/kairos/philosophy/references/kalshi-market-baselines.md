# Kalshi World Cup Market Baselines

Last updated: 2026-06-08

## KXMENWORLDCUP (Tournament Winner) — cents (bid price)
- Spain: 16.5
- France: 16.2
- Brazil: 8.2
- England: 7.4
- Argentina: 6.4
- Germany: 5.4
- Portugal: 3.1 (NOTE: surged to 10.1 by Jun 8 — stale baseline)
- Netherlands: 2.2
- Colombia: 2.3

## KXWCGOALLEADER (Top Goalscorer) — cents (bid price)
- Mbappe: 16
- Kane: 12
- Messi: 5
- Haaland: 4
- Gyokeres: 4 (no Kalshi market found with non-zero bid)
- Isak: 3 (no Kalshi market found with non-zero bid)
- Vinicius Jr: 3

## KXWCAWARD — Golden Ball — cents (bid price)
- Kane: 13 (NOTE: dropped to 7.0 by Jun 8 — stale baseline)
- Yamal: 12
- Mbappe: 11

## KXWCGROUPQUAL — Group Qualifiers — cents (bid price)
- Overpriced SELLs: USA D 81, Morocco C 87, Ghana L 49
- Undervalued BUYs: Haiti C 12, Iraq I 14, Curacao E 9, Panama L 30

## Kalshi API Notes
- Public endpoint (no auth): `https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=SERIES&with_nested_markets=true&limit=100`
- `yes_bid_dollars` = what you can sell at (the "current price" for comparison)
- `yes_ask_dollars` = what you'd pay to buy
- Skip markets where `yes_bid_dollars` is null (no liquidity)
- Volume field may be 0 on thin markets
- Market tickers follow pattern: `{SERIES}-{SUFFIX}-{COUNTRY/PLAYER}` e.g. KXMENWORLDCUP-26-PT, KXWCAWARD-26GBALL-HKANE
