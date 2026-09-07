# Local-business provider contract

The repository is evolving from a Google-specific CSV utility into a small provider-aware local-business discovery kernel. The objective is **not** to implement every Places/data API. The objective is to make adding the next provider surgical when a real workflow requires it.

## Stable concepts

### Discovery request

`DiscoveryRequest` captures the provider request inputs the kernel currently needs:

- text query;
- provider field mask/profile when applicable;
- bounded page/request count;
- language and region hints;
- optional provider-neutral circular geography bias (`GeoCircle`).

The circular bias is deliberately shared because it maps naturally to current Google Text Search, Foursquare Place Search, and Geoapify spatial search semantics. Exact inclusion/restriction semantics remain provider-specific; the current Google adapter maps it to `locationBias`, which is a bias rather than a hard boundary.

A future provider may expose additional provider-specific options, but the shared kernel should only grow when at least two real providers need the same concept.

### BusinessRef

`BusinessRef` is the durable identity/handoff contract:

```json
{
  "provider": "google",
  "provider_id": "ChIJ...",
  "source_query": "plumbers in Austin",
  "observed_at": "2026-09-07T19:00:00+00:00"
}
```

It deliberately excludes business names, addresses, ratings, phone numbers, reviews, and other provider content. For Google, `provider_id` is the Google Place ID, which Google explicitly allows to be stored.

This is the preferred seam for persistent enrichment workflows.

### BusinessRecord

`BusinessRecord` is the provider-neutral processing/integration contract. Current common fields include:

- provider + provider ID;
- name/address/location;
- categories/type/status;
- website/phone;
- rating/review count;
- provider URL;
- source-query provenance.

The schema is intentionally modest. Do not turn it into a universal CRM model. Provider-specific fields can stay in provider-native payloads until repeated downstream demand justifies a shared field.

`BusinessRecord` does **not** imply that its contents may be persisted. Persistence is governed by `ProviderSpec` and the provider's actual terms.

## Provider adapter requirements

An adapter implements three operations:

1. `search(DiscoveryRequest) -> list[raw provider records]`
2. `to_ref(raw) -> BusinessRef | None`
3. `to_record(raw) -> BusinessRecord`

It also declares a `ProviderSpec` with explicit capabilities and policy metadata.

The existing Google adapter is deliberately thin and delegates transport to the already-tested Text Search client.

## Output contracts

The CLI exposes three contracts:

### `business` (default)

Provider-neutral records for programmatic processing and integrations.

This gives workflow tools (Pipedream, n8n, Make, MCP servers, internal lead workflows) a stable shape without coupling them to the Google response schema.

### `refs`

Durable provider IDs plus client-generated provenance only.

For Google this automatically uses the IDs-only field profile, so it simultaneously minimizes the requested content and the current Text Search SKU. This is the preferred handoff to a provider that supports persistent enrichment by Google Place ID.

### `provider`

Legacy Google-shaped output for compatibility and diagnostics. It is intentionally not the extension contract for new providers.

## Candidate provider seams

These are **candidates**, not implemented adapters.

| Provider | Current relevant seam | Why it matters |
| --- | --- | --- |
| Google Places | Text Search + circle bias + durable Place ID | high-quality discovery, explicit field/SKU governance |
| Openmart | search + enrichment, including lookup by Google Place ID | persistent local-business/lead enrichment path |
| Foursquare Places | place search by query/location/category | independent place identity and discovery backend |
| Geoapify Places | category + spatial Places API | category/geography-first POI discovery backend |

References verified during the 2026-09-07 design pass:

- Google Text Search geography: https://developers.google.com/maps/documentation/places/web-service/text-search
- Google Place IDs: https://developers.google.com/maps/documentation/places/web-service/place-id
- Openmart local-business API: https://www.openmart.com/products/local-business-data-api
- Foursquare Place Search: https://docs.foursquare.com/fsq-developers-places/reference/place-search
- Geoapify Places API: https://apidocs.geoapify.com/docs/places/

## Integration examples

### Geography-biased Google discovery -> durable refs

```bash
local-business-discover \
  --query "roofers" \
  --latitude 32.7767 \
  --longitude -96.7970 \
  --radius-m 10000 \
  --output-contract refs \
  --format json
```

For Google, the circle is a search bias, not a hard inclusion boundary. The output can be queued, deduplicated, or handed to a downstream provider keyed by Google Place ID without persisting the richer Google response.

### Transient normalized business records

```bash
local-business-discover \
  --query "cafes" \
  --latitude -34.6037 \
  --longitude -58.3816 \
  --radius-m 5000 \
  --profile core \
  --output-contract business \
  --format json
```

This is the intended surface for workflow integrations that need a stable provider-neutral shape.

### Cost preflight without a provider call

```bash
places-costcheck \
  --fields "places.displayName,places.formattedAddress,places.websiteUri"
```

This surface exists independently from discovery so other repositories/integrations can use the cost contract without adopting the full client.

## Non-goals for the kernel

- universal CRM schema;
- automatic owner/email enrichment without a named provider and consumer;
- silent cross-provider identity merging;
- scraping web pages;
- assuming one provider's legal/storage contract applies to another;
- account-specific billing estimation;
- implementing adapters merely to populate a logo list.
