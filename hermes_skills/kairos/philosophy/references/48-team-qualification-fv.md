# 48-Team Format — Group Qualification Fair Value

The 2026 World Cup expanded to 48 teams (12 groups of 4). The knockout stage takes 32 teams:
- **Top 2 from each group** (24 teams)
- **8 best 3rd-place teams** (from 12 groups)

This means ~67% of teams advance (32/48), vs 50% in the old 32-team format. This changes how we price KXWCGROUPQUAL contracts.

## Qualification probability boost

In the old format, a mid-tier European team in a "Group of Death" might have 40-50% to advance. In the 48-team format, that same team might have 60-70% because finishing 3rd with a decent record is often enough.

## Points thresholds (historical pattern from expanded tournaments)

| Points | Typical outcome |
|--------|----------------|
| 5+ | Guaranteed advancement (top 2) |
| 4 | Advances ~95% of the time (top 2 or best 3rd) |
| 3 | Advances ~60-70% of the time (needs favorable GD among 12 3rd-place teams) |
| 2 | Almost always eliminated |
| 0-1 | Eliminated |

Key insight: a team that beats the group minnow (3 pts) and draws one of the two stronger teams (1 pt) = 4 pts → near-certain qualification. This makes qualification significantly easier than the old format.

## Applying to KXWCGROUPQUAL FV

When pricing a team like Sweden (Elo ~1712, 3rd in a group with NED 1944, JPN 1906):

1. **Scenario analysis over direct Elo conversion.** Don't just compute "chance of finishing top 2." Model: beat Tunisia (~60%), then need ~1 point from Japan/Netherlands combined for 4 pts. Even 3 pts with neutral GD often advances.

2. **Adjust for group composition.** Groups with a clear minnow (like Tunisia in Group F) boost qualification for all three stronger teams because the minnow is a reliable 3 points.

3. **Don't sum to 200%.**
   - Top 2 = 2 slots guaranteed
   - 3rd place = ~67% chance (8/12) of advancing
   - Total expected advancers per group ≈ 2.67
   - Sum of all four teams' qualification probabilities should ≈ 267%

4. **Mid-tier teams get the biggest boost.** The 3rd-place safety net primarily helps the 2nd/3rd strongest teams in each group. The favorite (Netherlands) is already ~90%+, so the format change adds little. The weakest team (Tunisia) gets a small bump but still needs results.

## Example: Group F (NED/JPN/SWE/TUN)

Without 3rd-place safety net (top 2 only):
- NED 85%, JPN 68%, SWE 42%, TUN 5% = 200%

With 3rd-place safety net:
- NED 89%, JPN 76%, SWE 64%, TUN 38% = 267%

The biggest beneficiary is the 3rd team (Sweden +22pp) and the weakest (Tunisia +33pp), while favorites gain little.

## Pitfalls

- **Don't ignore goal difference.** 3 points with -3 GD might not advance; 3 points with +0 GD probably does. If a team's path to 3 points involves a heavy loss to the group favorite, their 3rd-place GD may be too poor.
- **The 3rd-place safety net is not infinite.** If there are many groups with strong 4th-place teams, the bar for best 3rd-place could be higher (4 pts). Tunisia-level minnows across multiple groups lower the bar.
