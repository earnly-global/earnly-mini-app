# Earnly V7.3 — Real Opportunity Research Engine

## What is implemented
- Greenhouse public employer-board integration (from V7.1).
- Lever public employer-board integration (new).
- Reviewed individual tasks, studies, game rewards and crypto bounties intake (new).
- Existing Remotive and platform directory ingestion retained.
- No fake earnings, no inferred phone eligibility, no unverified payout guarantees.
- Existing Telegram authentication, payments and Supabase RPC are untouched.

## How to enable actual employer discovery
Edit `direct-job-sources.json` and add only employer boards that you have confirmed are official, e.g.:

```json
[
  {"provider":"greenhouse","board_token":"OFFICIAL_BOARD_TOKEN","company":"Employer name"},
  {"provider":"lever","site_slug":"OFFICIAL_SITE_SLUG","company":"Employer name"}
]
```

Replace placeholders with real official tokens/slugs after reviewing the employer's career page. Do not insert fabricated entries. Job postings are *applications*, not immediate paid work. An employer's location label does not establish country eligibility or phone compatibility.

## Individual tasks and studies
Populate `direct-tasks-reviewed.json` with individually researched live offers. Each record needs an HTTPS direct task URL, separate HTTPS source evidence, countries, start requirements, `requires_deposit:false`, `requires_seed_phrase:false`, and `review_status:"human_reviewed"`. Example **schema only, not a live offer**:

```json
[{"name":"Example only — do not publish","url":"https://example.org/task/123","source_url":"https://example.org/task/123/terms","opportunity_type":"individual_task","category":"ai","description":"Example","countries":["CA"],"device_support":["phone"],"start_requirements":"Example qualification","payout":"Unverified","payout_evidence_status":"not_verified","requires_deposit":false,"requires_seed_phrase":false,"review_status":"human_reviewed"}]
```

Never add that example to the live catalog. This importer is deliberately review-gated; the automated process cannot independently certify payments. Existing sync maps non-platform listings to `remote_job` for compatibility with the current Supabase RPC, so the new individual-task kinds are **not yet represented distinctly in the backend**. A later additive schema/RPC and frontend upgrade is required before presenting them as separate live categories.

## Test and run
```
python -m unittest discover -s tests -v
python scripts/update_opportunities.py
python scripts/sync_discovery.py opportunities.json
```

The updater makes live requests. Never run `--apply` unless you have reviewed the output and intended to publish it. Existing GitHub Actions may automatically sync catalog changes; review both scheduled workflows before deploying.

## Not complete yet
- No new real sources were validated live in this offline build; both configuration files remain empty.
- No live payout verification or individual game/paid survey API integration.
- No phone/country eligibility verification from employers.
- No backend/frontend dedicated task-type filter yet.
- Live production payment and renewal tests remain outstanding.
