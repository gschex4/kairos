# Cross-Checks: Data Sources & Techniques

Practical playbooks for the three Elo blind-spot checks (A: recent form, B: squad value, C: H2H).

## A. Recent Form (last 10 matches)

### Best source: Wikipedia API (curl to API, not browser)
```bash
# 1. Find section numbers for 2025 and 2026 match results
curl -s "https://en.wikipedia.org/w/api.php?action=parse&page=TEAM_NAME&format=json&prop=sections&origin=*" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); [print(s['index'], s['line']) for s in d.get('parse',{}).get('sections',[]) if '2025' in s['line'] or '2026' in s['line']]"

# 2. Fetch match text for the section (e.g., section 19 = 2025)
curl -s "https://en.wikipedia.org/w/api.php?action=parse&page=TEAM_NAME&format=json&prop=text&section=19&origin=*" | \
  python3 -c "
import sys, json, re
data = json.load(sys.stdin)
text = data['parse']['text']['*']
clean = re.sub(r'<[^>]+>', ' ', text)
clean = re.sub(r'&nbsp;', ' ', clean)
clean = re.sub(r'\s+', ' ', clean)
print(clean)
"
```

**Team page names known to work:**
- `United_States_men%27s_national_soccer_team`
- `Paraguay_national_football_team`

**For other teams:** run a search first to confirm the exact page title:
`curl -s "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=Ecuador+national+football+team&format=json&origin=*"`

### Pitfalls
- **Rate limit:** ~5 requests per second sustained will trigger a block. Space requests out. If blocked, wait 30-60 seconds.
- **Text parsing:** The HTML contains CSS class bloat and collapsed `[show]` tables. Python regex stripping works well enough — look for `Team X#–Y# Team` patterns in the cleaned text. Scores use en-dash (–) not hyphen (-).
- **Some teams don't have dedicated 2025/2026 result sections:** If the sections query returns nothing useful, fall back to the team's main page and look for "Results and fixtures" section.

## B. Squad Value Delta (Transfermarkt)

### Best source: x_search (much faster than browsing Transfermarkt directly)
```python
# Use x_search with query:
# "Transfermarkt [Team] national team squad total market value 2026"
#
# xAI/Grok returns the value in euros with citations to X posts referencing Transfermarkt data.
```

### Known values (from Jun 5, 2026 research):
- USA: €385.65M (FIFA rank 16)
- Paraguay: ~€145M
- Ecuador: ~€366M
- Ivory Coast: ~€600M
- Ghana: ~€170M (converted from $188M)
- Panama: ~€35M

### Fallback: Transfermarkt browser approach
URL pattern: `https://www.transfermarkt.com/team-name/startseite/verein/{ID}`
**Known IDs:** USA = 3505

**Pitfalls:**
- Verein IDs are NOT sequential by country — guessing wrong leads to Bosnian clubs
- Cookie consent modals and region-popup banners block content from browser automation
- National teams are listed under "Club" category on Transfermarkt, not "Country" in the breadcrumb
- The site changes its DOM structure frequently — snapshot scraping is fragile

### What the check tells you
A team's squad value reflects its player quality at market rates. A large gap between Elo rank and squad-value rank (e.g., top-10 Elo but outside top-30 squad value) suggests the team overperformed its talent in recent years and may regress. Conversely, a young, high-value squad with mid-table Elo is likely improving.

**Rule of thumb:** A >2x squad value gap in the *opposite direction* of your Elo-based bet direction is a -1¢ to -2¢ adjustment signal.

## C. Head-to-Head (H2H)

### Best source: Wikipedia
Each national team's Wikipedia page usually has a "Head-to-head record" section that lists results against all opponents in a compact table.

**Quick check:** Search `site:en.wikipedia.org "[Team A] vs [Team B] head to head"` or look at the team page for the specific opponent.

### Fallback: ESPN
ESPN's match preview pages often include recent H2H history. Navigate to the match preview and check for a "Last 5 meetings" section.

### Pitfalls
- Many H2H records are ancient (friendlies from 1990s, Copa America from 1980s) — a 20-year-old result is noise, not signal
- **Only count the last 4-5 matches** and only if they're within the last 10 years
- Friendly results in neutral venues matter less than competitive results
- If there are fewer than 3 H2H matches, treat the check as inconclusive — no adjustment

**Rule of thumb:** A 4+ match winless streak against the specific opponent in competitive matches is a -1¢ discount regardless of Elo gap. A single data point is not actionable.
