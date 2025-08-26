# google-places-to-csv

Minimal CLI to turn **Google Places API v1 Text Search** results into clean **CSV/JSON files**.
Supports field masks, pagination via `nextPageToken`, multi-query runs, and standardized filenames.

* Input: one or more text queries (e.g., `restaurants in Buenos Aires`, `dentist palermo`, `barber 11211`)
* Output: `./data/places_text_<slug(query)>_<YYYYMMDD_HHMMSS>.csv|json`
* Auth: API key via `GOOGLE_PLACES_API_KEY` env var
* Defaults: robust field mask including name, address, phones, website, ratings, hours, price level, reviews

This repo is intentionally lightweight so you can **get a leads CSV in one command**.

---

## Features

* **One-file CLI** (`text_runner.py`) — no framework overhead.&#x20;
* **Pagination** with `nextPageToken` (auto backoff between pages).&#x20;
* **Field masks** via `X-Goog-FieldMask`, with a sensible default you can override.&#x20;
* **CSV/JSON output** to a `data/` folder with consistent filenames.&#x20;
* **Column flattening** for nested fields and lists (joins list values for easier Excel/BI use).&#x20;

---

## Quick start

```bash
# 1) Clone
git clone https://github.com/<you>/google-places-to-csv.git
cd google-places-to-csv

# 2) (Optional) create venv
python3 -m venv .venv && source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt  # only 'requests' if you keep it lean

# 4) Set your API key
export GOOGLE_PLACES_API_KEY="YOUR_KEY"

# 5) Run
python data/text_runner.py --query "restaurants in Buenos Aires" --format csv
```

> On Windows (PowerShell):
> `setx GOOGLE_PLACES_API_KEY "YOUR_KEY"` then open a new shell.

---

## Usage

```bash
python data/text_runner.py \
  --query "restaurants in Buenos Aires" \
  --format csv \
  --max-pages 5 \
  --language-code es \
  --region-code AR
```

* `--query` (repeatable): Add multiple queries by repeating the flag
* `--format`: `csv` (default) or `json`
* `--max-pages`: default 5 (respects Places `nextPageToken`)
* `--language-code` / `--region-code`: pass through to the API
* `--fields`: override the default response field mask

All outputs are written under `./data/` with timestamped filenames.&#x20;

---

## Default fields (FieldMask)

By default the script requests a comprehensive set of fields so your CSV is useful out of the box:

```
places.id,places.name,places.displayName,places.formattedAddress,
places.location,places.types,places.primaryType,places.businessStatus,
places.googleMapsUri,places.primaryTypeDisplayName,places.plusCode,
places.addressComponents,places.shortFormattedAddress,places.viewport,
places.pureServiceAreaBusiness,places.containingPlaces,
places.internationalPhoneNumber,places.websiteUri,
places.rating,places.userRatingCount,
places.currentOpeningHours,places.regularOpeningHours,
places.priceLevel,places.priceRange,
places.reviews,places.reviewSummary
```

You can replace it with `--fields "<comma list>"`.
The tool automatically prepends `nextPageToken` so pagination still works.&#x20;

---

## Examples

**Multiple queries in one run**

```bash
python data/text_runner.py \
  --query "dentist palermo" \
  --query "pediatra belgrano" \
  --format csv --max-pages 3
```

**JSON output and custom fields**

```bash
python data/text_runner.py \
  --query "cafes recoleta" \
  --format json \
  --fields "places.displayName,places.formattedAddress,places.location,places.googleMapsUri"
```

---

## How pagination works

The script posts to `places:searchText`, collects `places[]`, and uses `nextPageToken` to fetch subsequent pages with a small delay (≈2.1s) until the token disappears or `--max-pages` is reached.&#x20;

---

## Output schema (CSV)

Columns are generated from the requested field mask. Nested objects are flattened to strings; lists are joined with commas or semicolons. This keeps the CSV friendly for spreadsheets while retaining key details.&#x20;

---

## Install notes

* Python 3.9+ recommended.
* Only dependency is `requests`. If you keep the repo minimal:

  ```
  pip install requests
  ```

---

## Pricing, quotas & SKUs (read me before scaling)

Google Places bills by **SKU** depending on which fields you request. If you only need IDs, you can request `places.id` / `places.name` (ID-only SKU). Rich fields like `rating`, `openingHours`, or `reviews` move you into **Pro/Enterprise** SKUs. Trim your `--fields` in production to control cost. (The CLI lets you swap masks per run.)

---

## Troubleshooting

* **HTTP 400 – invalid field**: You likely requested a field not available for `searchText`. Remove/adjust your `--fields`.
* **HTTP 403/401**: Check the API key, enable **Places API** for your project, ensure billing is active.
* **Only 20 results**: Raise `--max-pages` and let the script paginate; if results are exhausted, the API stops returning a token.
* **CSV columns missing**: The Places API only returns fields you explicitly ask for in the field mask; add them via `--fields`.

---

## Roadmap

* Optional **Nearby Search** mode (circle or viewport bias)
* **Place Details** enrichment by place ID (second pass)
* Native **Parquet** / **NDJSON** output
* Simple **dedup** cache by `places.id`

---

## Legal

Use of Google Places data is governed by Google’s Terms. You’re responsible for respecting **usage limits, quotas, and attribution**. This tool is a thin client around the official API and **does not scrape** web pages.

---

## License

MIT (suggested). Add a `LICENSE` file if you plan to keep it open source.

---

**Search phrases**

* Google Places API text search to CSV
* Export Google Maps places to CSV/JSON
* Places API v1 `nextPageToken` pagination
* `X-Goog-FieldMask` examples (displayName, websiteUri, rating, openingHours)
* Lead list from Google Places
* Local SEO data extraction with Places API

