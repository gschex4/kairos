# Heat Analysis Workflow for World Cup Betting

## When to Run
- At tournament start and whenever a cold-climate team is about to play in a hot outdoor venue
- During pre-match scan: run BEFORE looking at prices, like the other cross-checks
- Re-check if weather forecasts shift significantly (heat wave, cold snap)

## Step-by-Step

### 1. Identify Hot Venue Matches
Cross-reference the match schedule against `references/wc2026-venue-heat.md`. Only matches in the OPEN-AIR DANGER ZONES matter (Miami, Monterrey, Guadalajara, Kansas City). Skip roof-controllable venues unless there's confirmed news that the roof will be open.

### 2. Classify Both Teams by Climate Origin
Use the team climate list in `references/wc2026-venue-heat.md`. The signal fires when:
- Team A is COLD (Nordic, British, northern/central European, Canada, New Zealand)
- Team B is WARM/HOT (African, Middle Eastern, Latin American, Caribbean, Southeast Asian)
- The venue is in a DANGER ZONE

### 3. Check Kickoff Time
Afternoon kicks (12-4pm local) maximize heat stress. Evening kicks (7pm+) reduce it by 5-10°C. The signal is strongest for afternoon games in Miami/Monterrey.

### 4. Quantify the Edge
The heat edge is directional: fade the cold team, back the hot team. Adjustment magnitude:
- COLD vs HOT in Miami afternoon: **fade cold team by 5-7 cents** (largest adjustment)
- COLD vs HOT in Monterrey/Guadalajara afternoon: **fade cold team by 4-6 cents**
- COLD vs HOT evening kick: **fade cold team by 2-4 cents**
- TEMPERATE vs HOT afternoon: **fade temperate team by 2-3 cents**
- Any in Kansas City: same as Monterrey tier but add humidity effect

### 5. Cross-Reference Against Market Price
If the market already has the hot team heavily favored (85¢+), the edge is too small to act on — the spread eats it. The sweet spot is:
- Cold team priced 40-55¢ against hot opponent in hot venue → fade cold team
- Hot team priced 25-40¢ against cold opponent in hot venue → back hot team

### 6. Corroborate with X
Search X for:
- "team name heat training" or "team name acclimatization" — some teams specifically prepare
- Venue-specific weather forecasts from local accounts
- Player/coach quotes about conditions

### 7. Bet Expression
- **Fade cold team**: Bet NO on the cold team, or bet YES on hot team directly
- **Under 2.5 goals**: Heat suppresses scoring (less high-speed running, more fatigue)
- **2H goal timing**: More goals in second half as defenders wilt

## Known Heat-Exposed Matchups (Jun 2026)

These are identified from the group draw + venue assignments. Re-verify against current Kalshi prices before betting.

| Match | Date | Venue | Cold Team | Hot Team | Signal Strength |
|-------|------|-------|-----------|----------|-----------------|
| Sweden vs Tunisia | Jun 14 | Monterrey | SWE (51¢) | TUN (49¢) | **STRONG** |
| Scotland vs Brazil | Jun 24 | Miami | SCO (15¢) | BRA (85¢) | Weak (already priced) |
| Czechia vs South Africa | Jun 18 | Guadalajara | CZE (50¢) | RSA (50¢) | MODERATE |
| S Korea vs Czechia | Jun 11 | Guadalajara | CZE (63¢) | KOR (37¢) | MODERATE |
| Colombia vs Portugal | Jun 27 | Miami | POR (73¢) | COL (27¢) | MILD |
| Saudi Arabia vs Uruguay | Jun 15 | Miami | URU (88¢) | KSA (12¢) | Weak (already priced) |

Prices shown are YES ask at time of analysis (2026-06-08). Always re-fetch before betting.

## Sources
- X: @WCFieldGuide (schedule), @lavozdexela (venue details), @OfficialGamex7 (fixtures)
- FIFA official: fifa.com match schedule PDF
- Kalshi: public API for current prices
