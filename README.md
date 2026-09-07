# google-places-to-csv

Small, maintenance-mode CLI for exporting **Google Places API Text Search (New)** results to normalized CSV and/or raw JSON.

The canonical entry point is:

```bash
python -m gmaps_scraper.cli --query "restaurants in Buenos Aires"
```

The repository intentionally stays narrow: official Places API access, explicit field masks, bounded pagination, deterministic output, and cost-aware defaults. It is not a web scraper, CRM, or general Google Cloud billing tool.

## Why the default changed

Google bills Text Search (New) according to the **highest SKU triggered by any field in the response field mask**. A seemingly convenient default containing ratings, websites, hours, or reviews can therefore raise every successful search request into a more expensive tier.

As of the contract verification on **2026-09-07**:

- `rating`, `userRatingCount`, `websiteUri`, phone, opening-hours, and price fields trigger **Text Search Enterprise**;
- `reviews` and `reviewSummary` trigger **Text Search Enterprise + Atmosphere**;
- the default `core` profile contains only IDs-only + Pro fields and therefore triggers **Text Search Pro**.

The default is also **one page**, so an ordinary invocation makes at most one Text Search request unless the caller explicitly opts into `--max-pages 2` or `3`. The CLI reports that maximum request count alongside the SKU preflight.

Authoritative references:

- https://developers.google.com/maps/documentation/places/web-service/text-search
- https://developers.google.com/maps/billing-and-pricing/sku-details
- https://developers.google.com/maps/billing-and-pricing/pricing

Google can change field classifications and pricing. The CLI reports the highest tier implied by its dated local map before making a network request; custom fields absent from that map are reported as **UNCLASSIFIED**, never assumed cheap.

## Quick start

```bash
git clone https://github.com/matuteiglesias/google-places-to-csv.git
cd google-places-to-csv

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

export GOOGLE_PLACES_API_KEY="YOUR_KEY"
python -m gmaps_scraper.cli \
  --query "restaurants in Buenos Aires" \
  --format csv
```

The package also accepts `GOOGLE_API_KEY`. Do not commit API keys or billing credentials.

## Cost-aware profiles

Choose at most one of `--profile` and `--fields`.

| Profile | Intended use | Highest current Text Search SKU |
| --- | --- | --- |
| `ids` | IDs/resource names only | Essentials (IDs Only) |
| `core` | useful search CSV baseline | Pro |
| `enterprise` | core + rating/contact/hours/price | Enterprise |
| `atmosphere` | enterprise + reviews | Enterprise + Atmosphere |

`core` is the default.

Examples:

```bash
# Cheapest discovery shape
python -m gmaps_scraper.cli \
  --query "cafes in Almagro, Buenos Aires" \
  --profile ids

# Default useful baseline: Pro
python -m gmaps_scraper.cli \
  --query "cafes in Almagro, Buenos Aires" \
  --profile core \
  --format both

# Explicitly opt in to higher-cost contact/rating/hour fields
python -m gmaps_scraper.cli \
  --query "cafes in Almagro, Buenos Aires" \
  --profile enterprise

# Explicitly opt in to reviews / Atmosphere fields
python -m gmaps_scraper.cli \
  --query "cafes in Almagro, Buenos Aires" \
  --profile atmosphere
```

## Expert custom field masks

`--fields` bypasses the named profiles while keeping the same SKU preflight:

```bash
python -m gmaps_scraper.cli \
  --query "restaurants in Almagro, Buenos Aires" \
  --fields "places.displayName,places.formattedAddress,places.location,places.googleMapsUri"
```

The tool normalizes and de-duplicates the mask and includes `nextPageToken` for pagination. Nested masks such as `places.displayName.text` are classified through their documented top-level billable field.

Wildcard masks (`*` / `places.*`) and fields that are not in the dated local classification map produce an unmistakable **UNCLASSIFIED** warning. The CLI does not attempt to estimate your dollar bill because actual spend depends on current Google pricing, monthly volume, region, contracts, and future changes.

## CLI

```text
--query / -q        One Text Search query (required)
--profile           ids | core | enterprise | atmosphere
--fields            Expert comma-separated field-mask override
--max-pages         1..3, default 1
--language-code     Optional Places language code
--region-code       Optional Places region code
--out-dir           Output directory, default ./out
--format            csv | json | both, default csv
```

Text Search (New) currently returns at most 60 results across all pages. This client caps `--max-pages` at 3, but makes one page the default so extra billable page requests are explicit.

## Output contract

CSV output uses the requested fields to create deterministic, analysis-friendly columns. Common nested structures such as location, address components, opening hours, and price ranges are expanded where supported by the normalizer.

Raw JSON output is the list of returned Place objects. With `--format both`, CSV and raw JSON are produced from the same query and field selection.

Generated files go under `./out/` unless `--out-dir` is supplied. `out/` is ignored by Git.

## Transport behavior

The client:

- posts to `https://places.googleapis.com/v1/places:searchText`;
- requires an explicit response field mask;
- follows `nextPageToken` using `pageToken`;
- defaults to one page and allows an explicit maximum of three;
- retries only explicit retryable HTTP responses (`429`, `500`, `502`, `503`, `504`), with bounded backoff;
- does **not** automatically retry ambiguous network exceptions, because the server may already have received a billable request.

There is no automatic Place Details enrichment pass.

## Tests

Normal tests require no Google credentials and no network access:

```bash
python -m unittest discover -s tests -v
```

CI runs the offline contract suite on Python 3.10 and 3.12 with Places API key variables explicitly blank.

## Legacy entry point

`python text_runner.py ...` remains only as a compatibility shim and prints a deprecation notice. It delegates directly to the canonical package CLI and contains no independent API or billing logic.

Prefer `python -m gmaps_scraper.cli` in all new usage.

## Lifecycle

This repository is in `maintenance` state. See [`LIFECYCLE.md`](LIFECYCLE.md) and the dated [`API contract audit`](docs/API_CONTRACT_AUDIT_2026-09-07.md).

Before a paid production run, verify the current Google endpoint, requested fields/SKU, quotas, legal/attribution requirements, and that the run is intentionally authorized to incur charges.
