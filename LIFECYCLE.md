# Repository lifecycle

**State:** `maintenance`  
**Decision date:** 2026-08-03  
**Latest provider API/policy verification:** 2026-09-07  
**Review cadence:** annual, and before any material paid production run  
**Next portfolio review:** August 2027

## Why this state

This repository is retained as a small, governed local-business discovery and census kernel. Google Places Text Search and Openmart Local Business API are the implemented providers today. The reusable asset is the combination of provider identity, explicit cost/policy contracts, normalized business records, bounded discovery/census execution, durable handoff references, and deterministic output/provenance.

Openmart was added for a concrete current consumer: Matías's bounded prospect-list census in affluent local-service markets. That satisfies the existing rule that provider additions must serve a named workflow; it is not a reason to generalize into a broad lead platform.

The repository should remain bounded rather than grow into general scraping, CRM, market-intelligence, website-audit, enrichment, lead-management, or cloud-billing software.

## Canonical runtime

Use:

```bash
local-business-discover ...
local-business-census ...
# or
python -m gmaps_scraper.cli ...
```

`google-places-to-csv` is an installed compatibility/product-name alias. `text_runner.py` is only a legacy shim. Neither may regain independent HTTP, pagination, field-mask, billing, provider-policy, or normalization logic.

## Maintenance policy

- Preserve one canonical provider/discovery kernel rather than parallel provider-specific applications.
- Keep provider-specific geography/request semantics explicit; do not force them into a false universal abstraction.
- Keep the Google default at the intended useful/cheap tier (`core` -> Text Search Pro under the 2026-09-07 contract) and one page.
- Keep semantic Google field profiles separate from dated field-to-SKU billing classification.
- Keep provider cost semantics separate from provider persistence/data-policy semantics.
- Treat wildcard or unknown custom Google fields as unclassified, never implicitly cheap.
- Keep the durable `BusinessRef` contract minimal; do not let provider content drift into it.
- Keep multi-cell censuses finite, preflighted, request-budgeted, deduplicated by provider identity, and provenance-preserving.
- Add another provider adapter only for a named current consumer/workflow. Every adapter must declare policy/capability metadata and durable identity semantics.
- Verify annually, or before a paid production run, that provider endpoints, request schemas, pagination, authentication, quotas, policies, persistence assumptions, and relevant cost semantics remain current.
- Correct observed API breakage, cost-risk/policy documentation, misleading examples, or tests that no longer match authoritative provider evidence.
- Keep normal CI fully offline and credential-free.
- Do not add automatic Place Details enrichment, people/owner/email enrichment, paid contact unlocking, website crawling/scoring, opportunity inference, dashboards, CRM features, outreach, or generalized billing features without a separately justified bounded design.
- Never commit API keys or billing credentials.

## Current provider verification boundary

### Google

The Text Search field/SKU map in `gmaps_scraper/billing.py` was verified against Google's official Text Search (New) documentation on 2026-09-07. Google persistence guidance in `gmaps_scraper/providers.py` and `COMPLIANCE.md` was checked against current Google Maps Platform/service-specific terms on the same date.

Google may change fields, pricing, policies, or regional terms later; the local metadata is dated evidence, not permanent truth. The CLI reports the highest known triggered Google SKU before network access and does not estimate account-specific dollar spend.

### Openmart

The Local Business API transport shape, page-size guidance, public lead-generation positioning, and storage/use statements represented in the adapter/docs were checked against current Openmart public API/product documentation on 2026-09-07.

The first live user-account census remains an explicit release gate because public documentation cannot prove the exact response envelope, field availability, credits, account terms, or live data quality for a specific subscription.

Before any material paid production run, verify:

1. provider endpoint and enabled account/project;
2. requested data and applicable cost/credit semantics;
3. current pricing/free-usage caps and quotas;
4. pagination/result limits;
5. durable identifier and persistence/redistribution rules;
6. live output schema and downstream retention/use;
7. legal, attribution, privacy/marketing, and regional requirements relevant to intended use;
8. that credentials are intentionally authorized and appropriately restricted;
9. that the run is intentionally authorized to incur charges.

## Transport boundary

Provider clients may retry explicit retryable HTTP responses with bounded backoff. They must not automatically retry ambiguous network exceptions where the server could already have received a billable/credited request.

Google Text Search pagination is capped at three pages in the client and defaults to one. Openmart census pagination is likewise explicitly bounded by the caller and the local page-size/request guards.

## Data boundary

The repository is an API client/kernel, not a canonical leads database or commercial-intelligence system.

- `refs` is the minimal provider identity/handoff surface.
- `business` is a provider-neutral record whose persistence rights remain provider-specific.
- `provider` is a legacy Google-native compatibility surface.
- `local-business-census` is a finite acquisition/deduplication/provenance workflow; it does not decide which business should be sold to or why.

For the current lead-census use case, Openmart is used because its current public product documentation explicitly supports B2B lead-generation/storage. The user must still verify actual account terms before production use. See `COMPLIANCE.md`.

## Scope boundary

The current real edge is now implemented: Matías can produce a bounded, structured local-business universe for his own prospecting workflow without moving commercial judgment into this repository.

The next feature should be justified by evidence from that live census, an external integration/contributor, a provider partnership, or a paid/credible user. Do not implement additional providers, enrichment, website analysis, or outreach merely because they are imaginable.

## Release boundary

`0.2.0` remains unreleased until:

- offline CI is green;
- one bounded live Openmart census is run with a user-owned key;
- the actual response schema/normalization/dedupe and provider usage are inspected;
- provider policy metadata is rechecked if release date changes materially;
- license/distribution posture is explicitly decided before any PyPI publication.

See `docs/RELEASE_CHECKLIST.md`.
