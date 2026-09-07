# Repository lifecycle

**State:** `maintenance`  
**Decision date:** 2026-08-03  
**Latest API/SKU contract verification:** 2026-09-07  
**Review cadence:** annual, and before any material paid production run  
**Next portfolio review:** August 2027

## Why this state

This repository is retained as a small, focused client for exporting Google Places API Text Search (New) results to CSV or JSON. The capability is useful, but it should remain bounded rather than grow into a general scraping, enrichment, lead-management, or billing platform.

## Canonical runtime

Use:

```bash
python -m gmaps_scraper.cli ...
```

`text_runner.py` is only a compatibility shim. It must not regain independent HTTP, pagination, field-mask, billing, or normalization logic.

## Maintenance policy

- Preserve the narrow official-API client and deterministic output conventions.
- Keep the default field profile at the intended useful/cheap tier (`core` -> Text Search Pro under the 2026-09-07 contract).
- Keep semantic field profiles separate from the dated field-to-SKU billing classification.
- Treat wildcard or unknown custom fields as unclassified, never implicitly cheap.
- Verify annually, or before a paid production run, that endpoint, field classifications, pagination, authentication, quotas, and policies still match the current Google Places API.
- Correct observed API breakage, cost-risk documentation, misleading examples, or tests that no longer match the official contract.
- Keep normal CI fully offline and credential-free.
- Do not add automatic Place Details enrichment, CRM, scraping, dashboards, or generalized billing features without a named current consumer and an explicit bounded design.
- Never commit API keys or billing credentials.

## Current verification boundary

The Text Search field/SKU map in `gmaps_scraper/billing.py` was verified against Google's official Text Search (New) documentation on 2026-09-07. Google may add or reclassify fields later; the local map is dated evidence, not permanent truth.

The CLI reports the highest known triggered SKU before network access. It does not estimate dollar spend.

Before a paid production run, verify:

1. the official API endpoint and enabled project;
2. requested fields and applicable Text Search SKU;
3. current pricing/free-usage caps and quotas;
4. page-token behavior and result limits;
5. output schema and downstream retention/use;
6. legal, attribution, and policy requirements;
7. that the API credential is intentionally authorized and appropriately restricted;
8. that the run is intentionally authorized to incur charges.

## Transport boundary

The client may retry explicit retryable HTTP responses with bounded backoff. It must not automatically retry ambiguous network exceptions where the server could already have received a billable request.

Text Search pagination is capped at three pages in the client. No historical fixed page-token sleep should be treated as part of the API contract without current evidence.

## Scope boundary

The repository is an API client, not a web scraper and not a canonical leads database. Generated CSV or JSON files are run outputs and should be governed according to their intended use and sensitivity.
