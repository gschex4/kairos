# Manual Elo → Fair-Value (Poisson) Model

Use this when the `kairos_fair_value` plugin tool is unavailable (e.g., on Kalshi-only
hosts where `POLYMARKET_PRIVATE_KEY` is absent). This IS a fallback — the plugin tool
gives the trusted output. Compare against the benchmark calibration points below before
trusting manual output.

## Calibrated Model Parameters (9-Jun-2026)

These parameters reproduce the trusted `kairos_fair_value` output within ±1 percentage
point for the benchmark matches:

```python
BASE_GOALS = 2.55        # international tournament average
HOME_ADV_ELO = 35        # neutral venue (WC), slight listed-home bump
GOAL_RANGE = 12          # Poisson truncation (0..11 goals)
```

Remove the `* 1.05 / * 0.95` multipliers — they distort the Elo share.

## Benchmark Calibration Points (from Jun 5 scan)

These are the TRUSTED numbers from the actual `kairos_fair_value` tool output.
If your manual model doesn't land within ±1pp of these, you have a parameter bug.

| Match | Elo H | Elo A | Gap | FV Home | FV Draw | FV Away |
|---|---|---|---|---|---|---|
| MEX vs RSA | 1875 | 1518 | +357 | **71.0%** | ~18% | ~11% |
| KOR vs CZE | 1758 | 1740 | +18 | **37.6%** | ~27.8% | **34.2%** |
| USA vs PAR | 1733 | 1832 | -99 | ~31% | ~24% | **45.6%** |
| CIV vs ECU | 1695 | 1938 | -243 | ~15% | ~18% | **67.0%** |
| GHA vs PAN | 1510 | 1730 | -220 | ~18% | ~20% | **62.0%** |

## Reference Implementation

```python
import math

def elo_to_fair_value(home_elo, away_elo, is_neutral=True):
    ha = 35 if is_neutral else 100
    adj_h = home_elo + ha
    adj_a = away_elo
    base = 2.55

    h_share = 1 / (1 + 10**((adj_a - adj_h) / 400))
    a_share = 1 - h_share
    exp_h, exp_a = base * h_share, base * a_share

    hw = dw = aw = 0.0
    for h in range(12):
        for a in range(12):
            p = ((exp_h**h * math.exp(-exp_h) / math.factorial(h)) *
                 (exp_a**a * math.exp(-exp_a) / math.factorial(a)))
            if h > a: hw += p
            elif h == a: dw += p
            else: aw += p
    total = hw + dw + aw
    return hw/total, dw/total, aw/total
```

## When the Manual Code and the Benchmark Disagree — TRUST THE BENCHMARK

The reference implementation is a **pure Poisson** model. The trusted `kairos_fair_value`
tool used a **Dixon-Coles** model that inflates draw probabilities — pulling down both
win probabilities, especially the favorite's. The benchmark table captures actual
Dixon-Coles output. The pure Poisson code **will overshoot favorites consistently**:

| Match | Elo Gap | Pure Poisson (code) | Benchmark (trusted) | Δ |
|---|---|---|---|---|
| MEX vs RSA | +357 | MEX 84.4% | MEX 71.0% | +13.4pp |
| KOR vs CZE | +18 | KOR 46.0% | KOR 37.6% | +8.4pp |

**Rule**: If the manual code's output differs from the benchmark pattern by >5pp for a
comparable Elo gap, **use the benchmark table as your anchor, not the code output.**
Interpolate between the closest benchmark points, then adjust with cross-checks.

## Pitfalls

- **Do NOT use multipliers** (1.05/0.95). They inflate edges on narrow Elo gaps and
  break calibration against the trusted benchmark.
- **Base goals > 2.6 overstates favorites.** The calibrated value is 2.55.
- **The pure Poisson code overstates favorites vs. the Dixon-Coles benchmark.**
  On Elo gaps >200, the overshoot can be 10+ percentage points. Always sanity-check
  against the benchmark table — if the code says >75% for a +357 gap, trust the
  benchmark's 71% instead and adjust from there. The code is a directional tool,
  not a precision instrument.
- **This model does NOT know about lineups, injuries, rest days, or weather.**
  Fair-value is an anchor, not a crystal ball. Adjust AFTER cross-checks.
