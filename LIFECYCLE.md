# Repository lifecycle

**State:** `maintenance`  
**Decision date:** 2026-08-03  
**Review cadence:** annual  
**Next portfolio review:** August 2027

## Why this state

This repository is retained as a small, focused client for exporting Google Places API v1 text-search results to CSV or JSON. The capability is useful, but it should remain bounded rather than grow into a general scraping or lead-management platform.

## Maintenance policy

- Preserve the narrow official-API client and deterministic output conventions.
- Verify annually, or before a paid production run, that endpoints, field masks, pagination, and authentication still match the current Google Places API.
- Correct observed API breakage, cost-risk documentation, or misleading examples.
- Do not add broad enrichment, CRM, scraping, or workflow features without a named current consumer.
- Never commit API keys or billing credentials.

## Verification boundary

This lifecycle declaration does not certify that the documented field mask, pagination delay, pricing/SKU guidance, or example commands remain current on 2026-08-03.

Before use, verify:

1. the official API endpoint and enabled project;
2. requested fields and applicable SKU cost;
3. page-token behavior and rate limits;
4. output schema and flattening behavior;
5. legal, attribution, retention, and downstream-use requirements;
6. that the run is intentionally authorized to incur charges.

## Scope boundary

The repository is an API client, not a web scraper and not a canonical leads database. Generated CSV or JSON files are run outputs and should be governed according to their intended use and sensitivity.
