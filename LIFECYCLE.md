# Repository lifecycle

**State:** `maintenance`  
**Decision date:** 2026-08-03  
**Latest Google API/SKU + policy verification:** 2026-09-07  
**Review cadence:** annual, and before any material paid production run  
**Next portfolio review:** August 2027

## Why this state

This repository is retained as a small, governed local-business discovery kernel. Google Places Text Search (New) is the implemented provider today. The reusable asset is the combination of provider identity, explicit cost/policy contracts, normalized business records, durable handoff references, and deterministic output.

It should remain bounded rather than grow into a general scraping, CRM, enrichment, lead-management, or cloud-billing platform.

## Canonical runtime

Use:

```bash
local-business-discover ...
# or
python -m gmaps_scraper.cli ...
```

`google-places-to-csv` is an installed compatibility/product-name alias. `text_runner.py` is only a legacy shim. Neither may regain independent HTTP, pagination, field-mask, billing, provider-policy, or normalization logic.

## Maintenance policy

- Preserve one canonical provider/discovery kernel rather than parallel provider-specific applications.
- Keep the Google default at the intended useful/cheap tier (`core` -> Text Search Pro under the 2026-09-07 contract) and one page.
- Keep semantic field profiles separate from dated field-to-SKU billing classification.
- Keep provider cost semantics separate from provider persistence/data-policy semantics.
- Treat wildcard or unknown custom Google fields as unclassified, never implicitly cheap.
- Keep the durable `BusinessRef` contract minimal; do not let provider content drift into it.
- Add a new provider adapter only for a named current consumer/workflow. Every adapter must declare policy/capability metadata and durable identity semantics.
- Verify annually, or before a paid production run, that provider endpoints, field classifications, pagination, authentication, quotas, policies, and persistence assumptions remain current.
- Correct observed API breakage, cost-risk/policy documentation, misleading examples, or tests that no longer match authoritative provider evidence.
- Keep normal CI fully offline and credential-free.
- Do not add automatic Place Details enrichment, owner/email enrichment, scraping, dashboards, CRM features, or generalized billing features without a named current consumer and an explicit bounded design.
- Never commit API keys or billing credentials.

## Current Google verification boundary

The Text Search field/SKU map in `gmaps_scraper/billing.py` was verified against Google's official Text Search (New) documentation on 2026-09-07. The Google persistence guidance in `gmaps_scraper/providers.py` and `COMPLIANCE.md` was verified against the official Places policies and Place ID documentation on the same date.

Google may change fields, pricing, policies, or regional terms later; the local metadata is dated evidence, not permanent truth.

The CLI reports the highest known triggered Google SKU before network access. It does not estimate dollar spend.

Before a paid production run, verify:

1. the provider endpoint and enabled account/project;
2. requested fields and applicable cost/SKU/credit semantics;
3. current pricing/free-usage caps and quotas;
4. pagination/result limits;
5. durable identifier and persistence/redistribution rules;
6. output schema and downstream retention/use;
7. legal, attribution, and regional policy requirements;
8. that credentials are intentionally authorized and appropriately restricted;
9. that the run is intentionally authorized to incur charges.

## Transport boundary

The Google client may retry explicit retryable HTTP responses with bounded backoff. It must not automatically retry ambiguous network exceptions where the server could already have received a billable request.

Google Text Search pagination is capped at three pages in the client and defaults to one. No historical fixed page-token sleep should be treated as part of the API contract without current evidence.

## Data boundary

The repository is an API client/kernel, not a canonical leads database.

- `refs` is the durable identity handoff surface.
- `business` is a provider-neutral processing/integration surface whose persistence remains provider-terms-controlled.
- `provider` is a legacy/provider-native surface whose persistence remains provider-terms-controlled.

See `COMPLIANCE.md` before building a persistent dataset.

## Scope boundary

The next provider or feature should be justified by a real edge: Matías's own lead workflow, an external integration/contributor, a provider partnership, or a paid/credible user. Do not implement roadmap items merely because they are imaginable.
