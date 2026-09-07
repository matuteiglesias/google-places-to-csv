# google-places-to-csv

A small **governed local-business discovery and census kernel** with explicit provider, cost, persistence, and request-budget boundaries.

The repository began as a Google Places -> CSV utility. Its stronger boundary is now:

```text
query / geography
      ↓
provider (Google Places | Openmart)
      ↓
governed request / provider-specific preflight
      ↓
provider-neutral BusinessRecord or BusinessRef
      ↓
bounded single-query export or multi-cell census
      ↓
deterministic dedupe + provenance + run manifest
```

It intentionally remains a bounded data-acquisition kernel rather than becoming a CRM, generic market-intelligence agent, scraper, or outreach system.

## What is valuable here

- **Cost-aware Google Places field masks**: named `ids`, `core`, `enterprise`, and `atmosphere` profiles with dated field -> SKU classification.
- **One-request safe Google default**: ordinary Google discovery uses the `core` (Text Search Pro) profile and one page unless explicitly expanded.
- **Provider-neutral records**: integrations consume `BusinessRecord` / `BusinessRef` instead of hard-coding provider response schemas.
- **Two real provider semantics**: Google circular location bias and Openmart structured city/state/country areas are represented explicitly rather than pretending all geography works the same way.
- **Provider-specific persistence metadata**: cost classification and data-use/persistence policy are separate contracts.
- **Bounded census runner**: `local-business-census` executes a finite JSON plan with dry-run, hard request budgets, cross-cell deduplication, membership provenance, and a run manifest.
- **Standalone Google cost preflight**: `places-costcheck` classifies a field mask without credentials or network access.
- **Offline CI**: normal tests and smoke checks cannot spend provider/API money.

## Install from the repository

Python 3.10+:

```bash
git clone https://github.com/matuteiglesias/google-places-to-csv.git
cd google-places-to-csv

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

This installs four console entry points:

```text
local-business-discover
local-business-census
google-places-to-csv
places-costcheck
```

`0.2.0` is still unreleased. See [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).

## 1. Single-query Google discovery

```bash
export GOOGLE_PLACES_API_KEY="YOUR_KEY"

local-business-discover \
  --query "roofers" \
  --latitude 32.7767 \
  --longitude -96.7970 \
  --radius-m 10000 \
  --output-contract refs \
  --format json
```

For Google, the circle is a **location bias**, not a hard inclusion boundary. The `refs` contract automatically uses the IDs-only field profile and emits only provider identity plus client provenance:

```json
{
  "provider": "google",
  "provider_id": "ChIJ...",
  "source_query": "roofers",
  "observed_at": "2026-09-07T19:00:00+00:00"
}
```

Current Google service-specific terms allow caching Google ID values such as Places `place_id` where the applicable documentation allows it. Other Places content is subject to materially stricter export/storage rules. See [`COMPLIANCE.md`](COMPLIANCE.md).

## 2. Single-query Openmart discovery

For a persistent business/prospecting dataset, use a provider whose documented data-use contract fits that purpose. Openmart's current public product documentation explicitly markets its Local Business API for B2B lead generation and says returned structured JSON may be stored and used; users should still verify the terms attached to their account.

```bash
export OPENMART_API_KEY="YOUR_KEY"

local-business-discover \
  --provider openmart \
  --query "cosmetic dentist" \
  --city Greenwich \
  --state CT \
  --country US \
  --page-size 50 \
  --output-contract business \
  --format both
```

The provider-neutral `BusinessRecord` can contain, where returned:

- provider / provider ID;
- business name;
- address and coordinates;
- type/category fields;
- status;
- website;
- phone;
- rating / review count;
- provider URL;
- source-query provenance.

Missing fields remain empty; the kernel does not manufacture values.

## 3. Bounded multi-cell census

The repository includes a concrete near-demo plan:

```bash
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --dry-run
```

It contains 16 explicit cells:

- **markets**: Greenwich CT, Arlington VA, Irvine CA, Scottsdale AZ;
- **categories**: cosmetic dentist, medical spa, kitchen/bath remodeler, estate-planning attorney;
- **page size**: 50;
- **pages per cell**: 1.

So the plan is bounded to at most **16 provider requests / 800 raw observations** before deduplication.

Live execution:

```bash
export OPENMART_API_KEY="YOUR_KEY"

local-business-census \
  examples/census/website-leads-us-affluent.json \
  --max-total-requests 16
```

Each run creates:

```text
out/census/<plan>_<timestamp>/
  businesses.csv
  membership.csv
  manifest.json
```

`businesses.csv` is deduplicated by provider identity. `membership.csv` preserves which query/geography cells found each business. `manifest.json` records the plan hash, provider/policy metadata, request/record budgets, per-cell counts and final unique count.

See [`docs/CENSUS.md`](docs/CENSUS.md) for the contract and acceptance questions.

## 4. Google provider-shaped compatibility output

For Google-specific compatibility/diagnostics:

```bash
local-business-discover \
  --query "restaurants in Almagro" \
  --fields "places.displayName,places.formattedAddress" \
  --output-contract provider \
  --format csv
```

New integrations should prefer `business` or `refs`; `provider` remains a legacy Google-specific surface.

## 5. Google cost preflight

No API key or network call is needed:

```bash
places-costcheck \
  --fields "places.displayName,places.formattedAddress,places.websiteUri"
```

Machine-readable evidence:

```bash
places-costcheck \
  --fields "places.displayName,places.reviews" \
  --max-requests 3 \
  --json
```

Unknown fields and wildcard masks are **UNCLASSIFIED**, never assumed cheap.

## Google field profiles

Verified against Google's Text Search (New) contract on **2026-09-07**.

| Profile | Intended use | Highest current Text Search SKU |
| --- | --- | --- |
| `ids` | durable discovery identity | Essentials (IDs Only) |
| `core` | useful business discovery baseline | Pro |
| `enterprise` | contact/rating/hours/price | Enterprise |
| `atmosphere` | enterprise + reviews/atmosphere | Enterprise + Atmosphere |

The Google CLI preflight prints the selected profile, maximum request count, verification date and highest triggered SKU before network access. Google can change classifications/pricing; the dated map is evidence, not permanent truth.

Authoritative references:

- https://developers.google.com/maps/documentation/places/web-service/text-search
- https://developers.google.com/maps/billing-and-pricing/sku-details
- https://developers.google.com/maps/billing-and-pricing/pricing

## Provider contract

Implemented providers:

### Google Places Text Search

- query + optional `GeoCircle` location bias;
- explicit field mask and dated billing classification;
- max three pages / 60 Text Search results under the current API contract;
- durable Google ID handoff;
- provider-terms-controlled content persistence.

### Openmart Local Business API

- query + optional `GeoArea(city, state, country)`;
- bounded offset pagination, maximum page size 100;
- normalized business record / Openmart identity;
- persistence mode recorded as `provider-documented-lead-generation` based on current public provider documentation;
- no automatic people enrichment, paid contact unlocking, or outreach.

Every adapter declares a `ProviderSpec` with documentation/policy surfaces, verification date, persistence guidance, durable identifier and capabilities.

See [`docs/PROVIDER_CONTRACT.md`](docs/PROVIDER_CONTRACT.md) and [`COMPLIANCE.md`](COMPLIANCE.md).

## CLI surface

Common discovery options:

```text
--query / -q        discovery query (required)
--provider          google | openmart
--output-contract   business | refs | provider
--max-pages         1..3, default 1
--out-dir           output directory, default ./out
--format            csv | json | both, default csv
```

Google-specific:

```text
--profile           ids | core | enterprise | atmosphere
--fields            expert field-mask override
--latitude
--longitude
--radius-m          all three geography values supplied together; radius 0..50000
--language-code
--region-code
```

Openmart-specific:

```text
--city
--state
--country
--page-size         1..100
```

Provider-specific arguments are rejected when used with the wrong adapter rather than silently ignored.

## Transport behavior

Google Text Search:

- POST `https://places.googleapis.com/v1/places:searchText`;
- explicit normalized field mask;
- optional circular location bias;
- `nextPageToken` / `pageToken` pagination;
- one-page default, maximum three pages;
- bounded retries only for explicit retryable HTTP responses (`429`, `500`, `502`, `503`, `504`);
- no automatic retry for ambiguous network failures;
- no automatic Place Details enrichment.

Openmart:

- POST `https://api.openmart.ai/api/v1/search`;
- API key from `OPENMART_API_KEY`;
- structured city/state/country location when supplied;
- bounded offset pagination;
- default 50 / maximum 100 records per page in this adapter;
- one-page default, maximum three pages;
- bounded explicit HTTP retry behavior;
- no people/contact enrichment beyond fields already returned by the business-search response.

## Compliance boundary

**Cost and persistence are separate contracts.** A cheap field is not automatically persistable, and a provider that permits persistent business data is not automatically cheap.

Do not infer data rights from CSV/JSON output. Read [`COMPLIANCE.md`](COMPLIANCE.md) and re-check provider/account terms before production use.

## Tests

Normal tests need no provider credentials and no network access:

```bash
python -m unittest discover -s tests -v
```

CI installs the package, smoke-tests discovery/census/costcheck surfaces, validates the included census plan in dry-run mode, and runs the offline suite on Python 3.10 and 3.12 with Google and Openmart key variables blank.

## Lifecycle and release

The repository remains small and evidence-driven. New functionality should either:

1. serve a named current consumer/provider integration, or
2. strengthen existing provider/cost/compliance contracts.

See:

- [`LIFECYCLE.md`](LIFECYCLE.md)
- [`docs/CENSUS.md`](docs/CENSUS.md)
- [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)
- [`CHANGELOG.md`](CHANGELOG.md)

The next release gate is one bounded live Openmart census with a user-owned key, followed by inspection of the actual response schema, normalization quality, deduplication, and account usage. That empirical check should happen before promoting `0.2.0.dev0` to a release candidate/final version.

## Licensing posture

**No open-source license has been selected yet.**

That remains deliberate while the project tests whether its strongest return path is reputation/services, open-core distribution, commercial/OEM licensing, or a managed integration surface. Absence of a license should not be interpreted as MIT/Apache permission.

If you want to integrate, redistribute, or build commercially on the project, open a GitHub issue describing the intended use.
