# Earnly Crypto Hub — safe foundation (V7.2)

## What is implemented

- `scripts/crypto_hub.py`: validates *individual*, manually reviewed crypto-earning offers.
- `crypto-opportunities-reviewed.json`: approved-source intake, intentionally empty until reviewed offers are added.
- `scripts/update_opportunities.py`: merges approved crypto offers into the existing public catalog, deduplicated by URL. Rejected submissions are reported in `opportunities-report.json`.
- `tests/test_crypto_hub.py`: validation tests.

## Adding a legitimate offer

Add a JSON object to `crypto-opportunities-reviewed.json` only after checking the official provider page, eligibility, terms, and absence of a deposit-to-unlock requirement. Required fields:

- `name`, `url` (direct offer HTTPS), `official_source_url` (HTTPS)
- `opportunity_type`: `crypto_job`, `crypto_bounty`, `crypto_game`, `crypto_microtask`, `crypto_research`, `crypto_reward`
- `start_requirement`: `apply`, `task_available`, `registration_required`, `screening_required`
- `payout_evidence_status`: `unverified`, `terms_reviewed`, `payout_evidence_reviewed`
- `countries`: list of explicitly supported country codes; use `["Not verified"]` if unclear
- `device`: `phone`, `both`, or `laptop`
- `last_reviewed_at`: ISO date
- `requires_deposit`: `false` (unknown or true is rejected)
- For `crypto_game`, `withdrawal_terms_reviewed: true` after reviewing current terms.
- For `payout_evidence_reviewed`, provide `payout_evidence_url`. Do not label a reward as paid solely because the provider advertises it.

Optional: `description`, `payout`, `payment`, `company`, `requirements`.

**Do not include wallet addresses, private keys, seed phrases, personal identification data, referral-only links, or pay-to-unlock tasks.** This intake never connects to wallets or transfers funds.

## Run tests

`python -m unittest discover -s tests -v`

`node --test test/security.test.mjs`

`python scripts/update_opportunities.py` makes live network calls to existing public sources and writes the catalog. The GitHub scheduled updater already runs this command; do not manually replace Supabase functions.

## Remaining work before launch

- Add real official sources and reviewed individual offers (none seeded in this package).
- Add structured crypto fields to the Supabase discovery table/RPC before relying on server-side Premium/VIP crypto filters. Current sync retains `category=crypto` but maps non-platform offers into its existing `remote_job` listing kind, so subtypes are not yet preserved in Supabase.
- Verify mobile presentation, current offer availability, geographic eligibility, and payouts independently.
- Do not represent site reachability or advertised rewards as proof of actual payment.
- Complete live Stars billing and subscription lifecycle tests separately.
