# Exporting your Polymarket wallet's private key

> **Legacy (Polymarket).** Kairos now trades on **Kalshi**, which authenticates
> with an RSA API key (`KALSHI_API_KEY` + `KALSHI_KEY_PATH`), not a wallet
> private key. New setups do **not** need this doc — see
> [HERMES_WIRING.md](HERMES_WIRING.md) for Kalshi credential setup. This is kept
> only for the retired Polymarket path.

The bot signs every Polymarket order with the wallet's private key. So
wherever the bot runs, the private key has to be in its `.env` file. This
doc walks through getting it out of Polymarket's embedded wallet.

## Background

When you sign up to Polymarket with email or a social login, Polymarket
creates an "embedded wallet" for you under the hood. As of 2026 this is
typically backed by Privy (Magic Labs was breached in Dec 2025 and is no
longer the standard provider). Privy supports private key export from the
UI.

The wallet **address** is public and safe to share. The **private key** is
the money. Treat it like the seed phrase to a bank account.

## Steps (Polymarket + Privy)

1. Sign in to your Polymarket bot account at https://polymarket.com.
2. Click your profile icon (top right) → **Wallet** or **Settings**.
3. Look for an option labeled **Export private key**, **Show secret key**, or
   **Backup wallet**. The exact label varies by Privy version.
4. Confirm any 2FA / email verification step.
5. Polymarket / Privy will display a 64-character hex string starting with
   `0x`. That's your private key. **Do not screenshot it.** Type or paste it
   directly into `~/dev/kairos/.env` as the value of `POLYMARKET_PRIVATE_KEY`.
6. While you're in the wallet UI, also copy the **public address** (also
   starts with `0x`, 40 hex chars after that). Paste that into
   `POLYMARKET_FUNDER_ADDRESS` in the same `.env` file.

## If you don't see an export option

Some Privy configurations require the embedded wallet to be "claimed" before
the key is exportable. Look for a **Claim wallet** or **Self-custody this
wallet** button first.

If that path is blocked entirely for your account (rare but possible), the
workaround is:

1. Install MetaMask in your browser.
2. Generate a new wallet there (write down the seed phrase somewhere safe
   that is not on this computer).
3. Add Polygon network to MetaMask (chainlist.org has a one-click for
   Polygon).
4. From Polymarket, withdraw your USDC to that MetaMask wallet's address on
   Polygon.
5. Use MetaMask's **Export Private Key** option (under account → three dots
   → Account details → Show private key).
6. Paste that into `.env` as `POLYMARKET_PRIVATE_KEY`.
7. Connect that MetaMask wallet to Polymarket so the account is now
   associated with the self-custodied wallet.

This adds ~10 minutes but works in any configuration.

## After you have the key in `.env`

Run the smoke test to confirm the file is loaded correctly:

```bash
cd ~/dev/kairos
python -m src.main --smoke-test
```

If it prints `=== Smoke test passed ===` without errors, the wallet creds
are wired in. The smoke test does not touch Polymarket — it only verifies
that the config loader can read your file.

## Security reminders

- Anyone with `POLYMARKET_PRIVATE_KEY` can drain the wallet. Do not paste it
  into chat apps, screenshot it, or commit it to git. `.gitignore` is set to
  exclude `.env` but verify with `git status` before any commit.
- Fund this wallet with only the bankroll you're willing to lose. $50 to
  start.
- If the key is ever exposed (even briefly), move the funds immediately to
  a new wallet and update `.env` with the new key.
