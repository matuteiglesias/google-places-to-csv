# Bounded local-business census

`local-business-census` turns a finite JSON plan into a deduplicated business universe. It is intentionally not a market-intelligence agent, CRM, scraper, or outreach system.

The boundary is:

```text
explicit business query × explicit geography × explicit provider
    -> bounded provider requests
    -> normalized BusinessRecord / BusinessRef
    -> deterministic dedupe
    -> per-cell durable checkpoint
    -> provenance + run manifest
```

## Why Openmart for the website-lead demo

The included lead-census example uses Openmart rather than Google Places because the intended artifact is a persistent prospecting dataset. Openmart's current public product documentation explicitly supports B2B lead generation and storage/use of returned structured JSON. Google Maps Platform applies materially different export/storage restrictions to Places content. See `COMPLIANCE.md` and re-verify provider/account terms before production use.

## Install

```bash
python -m pip install -e .
```

For Openmart live calls:

```bash
export OPENMART_API_KEY='...'
```

Never commit the key.

## Dry-run first

The repository includes a concrete near-demo plan:

```bash
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --dry-run
```

The plan contains 16 cells:

- 4 markets: Greenwich CT, Arlington VA, Irvine CA, Scottsdale AZ;
- 4 categories: cosmetic dentist, medical spa, kitchen/bath remodeler, estate-planning attorney;
- 50 records maximum per cell;
- 1 page per cell.

Therefore the run is bounded to at most 16 provider requests and 800 raw observations before deduplication.

The example is a first empirical cohort, not a claim that these are globally optimal markets/categories.

## Run the census

```bash
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --max-total-requests 16
```

The request budget is a hard pre-network guard. A plan that exceeds the budget fails before provider calls begin.

The run directory is created **before the first network request**. After every successfully completed cell, the current records, memberships, checkpoint and manifest are atomically replaced on disk before the next provider request begins. This is a paid-data durability invariant: a later 402, 429, network error or provider failure must not erase already returned results.

## Artifacts

Each live run creates a timestamped directory under `out/census/` containing:

- `businesses.csv` — one normalized record per deduplicated provider identity;
- `membership.csv` — every cell/business membership observation, preserving which query/geography found each identity;
- `checkpoint.json` — exact resumable state after the last completed cell;
- `manifest.json` — plan hash, provider/policy metadata, status, request/record budgets, per-cell counts, unique count, failure metadata when applicable, and artifact names.

During an incomplete run, these files are valid partial artifacts. `manifest.json` uses `status: in_progress` while running and `status: failed` if a provider call raises. A successful run ends with `status: complete`.

The normalized business surface currently includes:

- provider and provider ID;
- business name;
- formatted address;
- latitude/longitude where returned;
- type/category fields;
- business status where returned;
- website;
- phone;
- rating and review count where returned;
- provider URL where returned;
- source query.

Fields absent from the provider response stay empty. The census runner does not manufacture values.

## Resume after a provider failure

If a run stops after some cells have completed, do **not** start a new census and repay for those cells. Resume the checkpointed directory:

```bash
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --max-total-requests 16 \
  --resume-run out/census/website-leads-us-affluent_YYYYMMDD_HHMMSS
```

The plan hash must match the checkpoint. Already completed cell indices are skipped without provider calls; execution resumes at the first unfinished cell.

The request budget remains a bound on the plan itself, not a promise that resume will reissue every request. Resume only spends requests for unfinished cells.

## What this demo is meant to prove

A successful live run should answer bounded engineering questions:

1. Does the provider return the documented response envelope?
2. Does the current normalization map the fields we actually receive?
3. How many unique businesses survive cross-query/cross-cell deduplication?
4. What share has websites/phones/review metadata?
5. Is the resulting universe useful enough to inspect commercially?
6. Are any additional structured provider fields worth adding to the stable contract?
7. Does checkpoint/resume preserve every completed billable cell across provider failures?

Do not expand the schema or add another provider until the live answers justify it.

## What is deliberately outside this command

- website-quality assessment;
- arbitrary crawling;
- AI opportunity inference;
- employee/owner lookup;
- paid contact-data unlocking;
- email sequencing;
- CRM synchronization;
- automated outreach.

Those can consume the bounded census artifact elsewhere if a real workflow justifies them.