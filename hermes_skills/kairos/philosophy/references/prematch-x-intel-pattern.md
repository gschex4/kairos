# Pre-Match X Intel Gathering Pattern

Reliable pattern for gathering pre-match intel (lineups, injuries, weather, credible sources)
when Firecrawl/web_search is unavailable. Proven working Jun 10, 2026.

## The Pattern: delegate_task with x_search fan-out

Fan out parallel delegate_task subagents — one per match — with `toolsets: ["x_search"]`.
Each subagent handles its own X queries independently. Subagents CAN use x_search but
NOT web_search/web_extract.

### Task template (per match)

```json
{
  "goal": "Find pre-match intel for {HOME} vs {AWAY} World Cup match: lineups, injuries, weather, credible sources.",
  "context": "Search X/Twitter for lineup news, injury updates, pre-match intel for {HOME} vs {AWAY} World Cup 2026 match ({DATE}). Search official accounts ({HOME_HANDLE}, {AWAY_HANDLE}) and credible journalists (Fabrizio Romano, David Ornstein). Focus on: confirmed starting XI, key injuries, weather conditions, venue details.",
  "toolsets": ["x_search"]
}
```

### Query patterns that work

- Official accounts: `"from:{handle} lineup"` or `"{handle} {team} XI"`
- Injury news: `"{player} injury update 2026"`
- Pre-match news: `"{team1} vs {team2} preview lineup June 2026"`
- Credible journalist coverage: search by journalist handle + team names

### Known limitations

- **No confirmed XI until ~60 min before kickoff** — normal. Pre-match windows should still
  gather predicted lineups and flag injury concerns.
- **Weather from X** — search `"{venue city} weather June 11 2026"` or similar.
- **Subagent browser snapshots are often truncated** on Wikipedia/Transfermarkt — not suitable
  for data extraction. Use parent-agent browser_console for structured data.
- **Subagents report what they found, not verified facts** — always corroborate critical
  claims (injuries to star players) with a second source before adjusting fair value.

### Output format

Subagent returns: confirmed/expected lineups, injury status of key players, weather notes,
credible source citations. The parent agent then vets the intel and adjusts fair value
accordingly.

## Why Not Parent-Agent x_search Directly

Parent-agent direct x_search works too, but delegate_task fan-out lets you research 3-5
matches in parallel in one turn. On busy match days, serial research is too slow.
