# Local-business provider contract

The repository is a small provider-aware local-business discovery and census kernel. The objective is **not** to implement every Places/data API. The objective is to keep provider semantics explicit and make the next adapter surgical only when a real workflow requires it.

## Stable concepts

### Discovery request

`DiscoveryRequest` captures only shared inputs already required by implemented providers:

- text query;
- provider field mask/profile when applicable;
- bounded page/request count;
- optional page size when the provider exposes it;
- language and region hints when supported;
- optional circular geography (`GeoCircle`);
- optional structured geography (`GeoArea`: city/state/country).

Geography semantics remain provider-specific rather than being falsely unified:

- Google currently maps `GeoCircle` to Text Search `locationBias`; it is a bias, not a hard inclusion boundary.
- Openmart currently maps `GeoArea` to its structured city/state/country search payload.

A future shared concept should enter `DiscoveryRequest` only when concrete implemented workflows justify it. Provider-only knobs can remain adapter-specific until then.

### BusinessRef

`BusinessRef` is the minimal durable identity/handoff contract:

```json
{
  "provider": "google",
  "provider_id": "ChIJ...",
  "source_query": "plumbers in Austin",
  "observed_at": "2026-09-07T19:00:00+00:00"
}
```

It deliberately excludes business names, addresses, ratings, phone numbers, reviews, and other provider content. Whether a provider ID may be persisted is still governed by that provider's current terms/policy metadata.

### BusinessRecord

`BusinessRecord` is the provider-neutral processing/integration contract. Current common fields include:

- provider + provider ID;
- name/address/location;
- categories/type/status;
- website/phone;
- rating/review count;
- provider URL;
- source-query provenance.

The schema is intentionally modest. Do not turn it into a universal CRM model. Missing fields remain empty; provider-specific fields stay provider-specific until repeated downstream demand justifies a shared field.

`BusinessRecord` does **not** itself grant persistence rights. Persistence is governed by `ProviderSpec` and the provider/account's actual terms. The current Openmart adapter is specifically present because Matías's bounded lead-census workflow requires a provider whose documented product surface supports persistent B2B lead data.

## Provider adapter requirements

An adapter implements three operations:

1. `search(DiscoveryRequest) -> list[raw provider records]`
2. `to_ref(raw) -> BusinessRef | None`
3. `to_record(raw) -> BusinessRecord`

It also declares a `ProviderSpec` with explicit capabilities and dated policy metadata.

Implemented adapters are deliberately thin:

- **Google Places Text Search** delegates transport to the existing cost-aware Text Search client.
- **Openmart Local Business API** delegates transport/pagination/normalization to `gmaps_scraper.openmart` and supports the current structured-area lead-census use case.

## Output contracts

### `business` (default)

Provider-neutral records for programmatic processing and integrations.

For Openmart this is also the normal census artifact because its current public product documentation explicitly supports B2B lead-generation/storage; users must still verify their actual account terms before production use.

### `refs`

Minimal provider IDs plus client-generated provenance.

For Google this automatically uses the IDs-only field profile, minimizing requested Google Places content and the current Text Search SKU. For other providers it remains a provider-identity handoff, subject to that provider's identifier policy.

### `provider`

Legacy Google-shaped output for compatibility and diagnostics. It is intentionally not the extension contract for new providers.

## Implemented provider seams

| Provider | Implemented seam | Current intended use |
| --- | --- | --- |
| Google Places | Text Search + circle bias + field/SKU preflight + Place ID | bounded discovery/integration under Google's service contract; durable ID handoff where allowed |
| Openmart | local-business search + structured city/state/country area + normalized record | persistent bounded B2B lead census under Openmart's documented product/account terms |

References verified during the 2026-09-07 pass:

- Google Text Search: https://developers.google.com/maps/documentation/places/web-service/text-search
- Google Maps service-specific terms: https://cloud.google.com/maps-platform/terms/maps-service-terms
- Openmart API tutorial: https://www.openmart.com/product-tutorials/using-the-openmart-api-to-fetch-data
- Openmart Local Business Data API: https://www.openmart.com/products/local-business-data-api

## Candidate future seams

These are **not implemented** and should remain that way until a real consumer requires them:

| Provider | Potential seam | Why it might matter |
| --- | --- | --- |
| Foursquare Places | place search by query/location/category | independent place identity/discovery backend |
| Geoapify Places | category + spatial Places API | category/geography-first POI discovery backend |

## Integration examples

### Geography-biased Google discovery -> minimal refs

```bash
local-business-discover \
  --query "roofers" \
  --latitude 32.7767 \
  --longitude -96.7970 \
  --radius-m 10000 \
  --output-contract refs \
  --format json
```

### Persistent Openmart business discovery

```bash
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

### Bounded multi-cell census

```bash
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --dry-run
```

The included plan is bounded to 16 cells and at most 16 provider requests / 800 raw observations before deduplication. See `docs/CENSUS.md`.

### Google cost preflight without a provider call

```bash
places-costcheck \
  --fields "places.displayName,places.formattedAddress,places.websiteUri"
```

This surface remains independent from discovery so other repositories/integrations can use the Google cost contract without adopting the full client.

## Census contract

A census is a finite set of explicit `query × geography` cells. The runner must:

- preflight and hard-cap total provider requests before network access;
- preserve provider identity for deterministic cross-cell deduplication;
- preserve cell membership/provenance rather than collapsing how a business was found;
- emit a run manifest with the plan hash, provider/policy metadata, budgets and counts;
- perform no arbitrary web crawling, opportunity inference, people lookup, outreach, or CRM synchronization.

This is the intended boundary for Matías's current lead-list use case.

## Non-goals for the kernel

- universal CRM schema;
- website-quality or market-intelligence inference;
- automatic owner/email enrichment or paid contact unlocking;
- silent cross-provider identity merging;
- arbitrary web scraping;
- assuming one provider's legal/storage contract applies to another;
- account-specific dollar billing estimation;
- outreach automation;
- implementing adapters merely to populate a logo list.
