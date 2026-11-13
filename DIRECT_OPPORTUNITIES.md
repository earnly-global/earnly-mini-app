# Earnly direct-opportunity research (V7.1)

This upgrade preserves the existing payment and auth functions. It adds **official Greenhouse employer job boards** as a configurable research source, and labels generic signup platforms separately.

## Enable employer boards

Edit `direct-job-sources.json` to contain reviewed employer boards, for example:

```json
[{"board_token":"YOUR_CONFIRMED_BOARD_TOKEN","company":"Employer name"}]
```

The token must be confirmed from the employer’s own Greenhouse job-board URL. **Do not add invented tokens.** Run `python scripts/update_opportunities.py` to fetch live public postings; the existing GitHub update workflow also runs this on its schedule. The separate Supabase sync workflow imports the updated catalog on its next scheduled run. No API key is required for public Greenhouse listings.

## What is and is not verified

A published job is an **application opportunity**, not immediate work or guaranteed pay. Location, remote status, pay, current hiring, and eligibility are *not verified* unless explicitly supported. Existing platform listings remain accessible but are clearly labeled as signup directories. There are **no individual paid game offers or individual surveys** sourced by this release: those require approved direct-offer sources and truthful eligibility/payout data.

## Deployment

Upload the repository contents to GitHub preserving paths. Run `python -m unittest discover -s tests -p 'test_*.py'` and `npm test`. Review GitHub Actions `Update Earnly opportunities`, then `Earnly Discovery Sync`. The V6 server-side Discovery endpoint is unchanged and still needs separate backend changes before it can prioritize employer-direct results.
