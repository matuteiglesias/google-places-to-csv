# google-places-to-csv

A small **governed local-business discovery kernel** with a cost-aware Google Places implementation today and provider-ready contracts for future enrichment/discovery backends.

The repository began as a Google Places -> CSV utility. Its stronger boundary is now:

```text
query / geography
      ↓
provider (Google today)
      ↓
governed request + cost preflight
      ↓
provider-neutral BusinessRecord
      ↓
durable BusinessRef / provider ID
      ↓
downstream enrichment or lead workflow
```

It intentionally remains a bounded API client/kernel rather than becoming a CRM, scraper, or generic lead platform.

## What is valuable here

- **Cost-aware Google Places field masks**: named `ids`, `core`, `enterprise`, and `atmosphere` profiles with dated field -> SKU classification.
- **One-request safe default**: ordinary Google discovery uses the `core` (Text Search Pro) profile and one page unless explicitly expanded.
- **Geography-aware discovery**: a provider-neutral circular search bias maps to Google `locationBias` today and is reusable by future place providers.
- **Standalone cost preflight**: `places-costcheck` classifies a field mask without credentials or network access.
- **Provider-neutral business contract**: integrations can consume `BusinessRecord` instead of the Google response schema.
- **Durable ID handoff**: `refs` emits only provider identity + client provenance; for Google this means Place IDs and automatically uses the IDs-only profile.
- **Explicit provider policy metadata**: cost classification and persistence policy are separate contracts.
- **Offline CI**: tests cannot spend provider/API money.

## Install from the repository

Python 3.10+:

```bash
git clone https://github.com/matuteiglesias/google-places-to-csv.git
cd google-places-to-csv

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

This installs three console entry points:

```text
local-business-discover
google-places-to-csv
places-costcheck
```

`python -m gmaps_scraper.cli` remains the canonical module invocation.

> Packaging is release-ready but this repository has not yet committed to a PyPI/public-license strategy. See **Licensing posture** below.

## 1. Durable discovery handoff

For a pipeline that needs persistent identity rather than Google Places content:

```bash
export GOOGLE_PLACES_API_KEY="YOUR_KEY"

local-business-discover \
  --query "roofers" \
  --center "32.7767,-96.7970" \
  --radius-m 10000 \
  --output-contract refs \
  --format json
```

For Google, the circle is a **bias**, not a hard geographic inclusion boundary. `refs` deliberately requests the Google IDs-only profile and produces records shaped like:

```json
{
  "provider": "google",
  "provider_id": "ChIJ...",
  "source_query": "roofers",
  "observed_at": "2026-09-07T19:00:00+00:00"
}
```

Google explicitly exempts Place IDs from Places caching restrictions. This contract is therefore the preferred seam for durable queues, deduplication, and downstream providers that accept Google Place IDs.

## 2. Provider-neutral business records

Default usage returns a common `BusinessRecord` shape:

```bash
local-business-discover \
  --query "cafes" \
  --center "-34.6037,-58.3816" \
  --radius-m 5000 \
  --profile core \
  --output-contract business \
  --format both
```

Common fields include provider/provider ID, name, address, coordinates, type/category information, status, website/phone, rating/review count, provider URL, and source-query provenance.

The schema is intentionally modest. Missing/unrequested fields remain empty rather than encouraging a universal CRM model.

**Important:** a normalized record is not automatically a persistable record. Provider terms still govern the source content. See [`COMPLIANCE.md`](COMPLIANCE.md).

## 3. Legacy/provider-shaped output

For Google-specific compatibility and diagnostics:

```bash
local-business-discover \
  --query "restaurants in Almagro" \
  --fields "places.displayName,places.formattedAddress" \
  --output-contract provider \
  --format csv
```

This preserves the requested-field-driven flattened schema from the original utility. New provider integrations should prefer `business` or `refs` instead of depending on this Google-specific surface.

## 4. Cost preflight as a standalone tool

No API key or network call is needed:

```bash
places-costcheck \
  --fields "places.displayName,places.formattedAddress,places.websiteUri"
```

Example outcome:

```text
Highest triggered SKU: Text Search Enterprise
```

Machine-readable evidence:

```bash
places-costcheck \
  --fields "places.displayName,places.reviews" \
  --max-requests 3 \
  --json
```

Unknown fields and wildcard masks are reported as **UNCLASSIFIED**, never assumed cheap.

## Google field profiles

Verified against Google's Text Search (New) contract on **2026-09-07**.

| Profile | Intended use | Highest current Text Search SKU |
| --- | --- | --- |
| `ids` | durable discovery identity | Essentials (IDs Only) |
| `core` | useful business discovery baseline | Pro |
| `enterprise` | contact/rating/hours/price | Enterprise |
| `atmosphere` | enterprise + reviews/atmosphere | Enterprise + Atmosphere |

The CLI prints the selected profile, maximum request count, verification date, and highest triggered SKU before network access.

Google can change field classifications and pricing. The dated local map is evidence, not permanent truth.

Authoritative references:

- https://developers.google.com/maps/documentation/places/web-service/text-search
- https://developers.google.com/maps/billing-and-pricing/sku-details
- https://developers.google.com/maps/billing-and-pricing/pricing

## Provider contract

Google is the only implemented discovery provider in this version. The extension boundary is already explicit:

1. `DiscoveryRequest` with query, bounded requests, language/region, and optional `GeoCircle`;
2. `search(DiscoveryRequest)`;
3. `to_ref(raw) -> BusinessRef`;
4. `to_record(raw) -> BusinessRecord`;
5. `ProviderSpec` with docs, terms/policy metadata, durable identifier, and capabilities.

See [`docs/PROVIDER_CONTRACT.md`](docs/PROVIDER_CONTRACT.md).

Current provider candidates driven by actual commercial/integration relevance—not by a desire to collect adapters—include:

- **Openmart**: local-business search/enrichment and lookup by Google Place ID;
- **Foursquare Places**: independent place search/identity;
- **Geoapify Places**: category + spatial POI discovery.

No adapter should be implemented until a real workflow/user makes its semantics concrete.

## CLI surface

```text
--query / -q        Discovery query (required)
--provider          google (current implementation)
--profile           ids | core | enterprise | atmosphere
--fields            Expert Google field-mask override
--center            Optional LAT,LNG search-bias center
--radius-m          Radius paired with --center; Google supports 0..50000
--output-contract   business | refs | provider
--max-pages         1..3, default 1
--language-code     Optional Google language code
--region-code       Optional Google region code
--out-dir           Output directory, default ./out
--format            csv | json | both, default csv
```

`--output-contract refs` intentionally rejects expensive/custom field selections because those fields do not change the durable identity handoff.

## Transport behavior

For Google Text Search, the client:

- posts to `https://places.googleapis.com/v1/places:searchText`;
- requires/normalizes an explicit field mask;
- can map a provider-neutral circular geography to Google `locationBias`;
- follows `nextPageToken` using `pageToken`;
- defaults to one page and caps explicit pagination at three pages;
- retries only explicit retryable HTTP responses (`429`, `500`, `502`, `503`, `504`) with bounded backoff;
- does **not** automatically retry ambiguous network exceptions where the server may already have received a billable request.

There is no automatic Place Details enrichment pass.

## Provider data / compliance boundary

Cost and persistence are deliberately separate.

For Google, current official policy explicitly permits storing Place IDs. Other Places content remains governed by Google Maps Platform terms and applicable caching/storage/redistribution restrictions. EEA terms may differ.

The repository therefore distinguishes:

- `refs`: durable identity handoff;
- `business`: provider-neutral processing contract, still provider-terms-controlled;
- `provider`: provider-native/legacy content, still provider-terms-controlled.

Read [`COMPLIANCE.md`](COMPLIANCE.md) before building a persistent production dataset.

## Tests

Normal tests need no provider credentials and no network access:

```bash
python -m unittest discover -s tests -v
```

CI installs the package, smoke-tests the console commands, and runs the offline contract suite on Python 3.10 and 3.12 with Google API-key variables explicitly blank.

## Integration surfaces this is meant to support

Without requiring those projects to adopt this CLI wholesale, the contracts are suitable for:

- internal lead sourcing/enrichment pipelines;
- n8n / Make / Pipedream-style workflow nodes;
- MCP tools/servers;
- local-search/SEO infrastructure;
- provider adapters and enrichment bridges;
- FinOps/static analysis using `places-costcheck`;
- bounded API-cost/integration audits.

## Lifecycle

The repository remains in `maintenance` state: small, focused, evidence-driven. See [`LIFECYCLE.md`](LIFECYCLE.md) and the dated [`API contract audit`](docs/API_CONTRACT_AUDIT_2026-09-07.md).

New functionality should either:

1. serve a named current consumer/provider integration, or
2. strengthen the existing provider/cost/compliance contracts.

## Licensing posture

**No open-source license has been selected yet.**

That is deliberate while the project tests whether its strongest return path is reputation/services, open-core distribution, commercial/OEM licensing, or a managed integration surface. The absence of a license should not be interpreted as permission to reuse the code under MIT/Apache terms.

If you want to integrate, redistribute, or build commercially on the project, open a GitHub issue describing the intended use. That conversation is useful product evidence while the licensing strategy remains open.
