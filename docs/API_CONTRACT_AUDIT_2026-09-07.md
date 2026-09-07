# Google Places API contract audit — 2026-09-07

Status: **Agent A audit complete; implementation intentionally deferred to the hardening pass.**

Repository lifecycle remains `maintenance`: keep this a small official-API client, not a general scraping, CRM, enrichment, or billing platform.

## 1. Executive decision

The repository should converge on `python -m gmaps_scraper.cli` as the single canonical runtime path. The root `text_runner.py` is an older duplicated implementation with materially different defaults and output behavior; maintaining both would preserve cost and correctness drift.

The hardening pass should:

1. make a useful **Text Search Pro** profile the default;
2. expose explicit higher-cost profiles for Enterprise and Enterprise + Atmosphere fields;
3. preserve expert `--fields` overrides;
4. classify the highest Text Search SKU implied by the selected mask before a request is made;
5. keep field-profile semantics separate from billing classification;
6. fail visibly when a custom field cannot be classified rather than silently assuming a cheap tier;
7. add offline tests and keep live paid API calls out of CI;
8. deprecate/remove the duplicate root runner after migration coverage exists.

No automatic Place Details enrichment should be introduced as part of this work. A second request per returned place changes the billing model and should only exist for a named consumer with explicit bounds.

## 2. Current repository surface

### Preferred package path

`gmaps_scraper/cli.py` delegates API access to `gmaps_scraper/api.py`, normalization to `gmaps_scraper/normalize.py`, and output helpers to `gmaps_scraper/utils.py`.

Strengths already present:

- one API module instead of inline HTTP in the CLI;
- `--fields` is propagated into normalization;
- `--max-pages` is validated to `1..3`;
- deterministic CSV column ordering;
- raw JSON output is available;
- `nextPageToken` is normalized into the field mask.

Material problems:

- the comment calls the current default mask “lean”, but it contains Enterprise fields;
- there is no SKU classifier or profile abstraction;
- there are no tests or CI checks;
- the request helper declares `max_retries` and `timeout` parameters but does not actually implement retries and hard-codes the timeout;
- the fixed `2.1s` pagination sleep appears inherited from legacy Places behavior; the current Text Search (New) documentation describes `pageToken` pagination but does not document that fixed delay. Do not preserve the sleep as a contractual requirement without evidence;
- no dependency/packaging manifest exists at repository root even though the README refers to `requirements.txt`.

### Legacy root path

`text_runner.py` duplicates argument parsing, HTTP, pagination, normalization, CSV/JSON writing, and API-key handling.

Material drift:

- default `--max-pages` is `5`, despite Text Search (New) returning at most 60 results across pages and the package CLI enforcing `1..3`;
- default field mask includes `reviews` and `reviewSummary`, which pushes successful Text Search requests to Enterprise + Atmosphere;
- its custom `--fields` value is used for the API request, but CSV normalization still uses `DEFAULT_FIELDS`, so request semantics and CSV schema can disagree;
- JSON output wraps `{query, count, places}` while the package path writes the raw place list;
- retry/backoff behavior exists here but not in the newer package API module.

**Decision:** do not repair both implementations independently. Preserve any useful behavior through tests, then retire the duplicate root implementation or reduce it to a thin compatibility shim that delegates to the package.

## 3. Documentation drift

The README currently mixes the two generations of the repository:

- it points Quick Start at `python data/text_runner.py`, but that file does not exist;
- it tells users to install from `requirements.txt`, but that file does not exist;
- it documents a default `--max-pages` of `5` while the package CLI uses `3`;
- it advertises reviews in the default mask while the package CLI comments them out;
- its pricing warning is directionally correct but does not tell users what SKU the default actually triggers.

The README should be rewritten from the canonical CLI after implementation rather than patched line-by-line around both runtimes.

## 4. Current Google Text Search (New) contract

Verified against official Google documentation on **2026-09-07**.

Authoritative references:

- Text Search (New): https://developers.google.com/maps/documentation/places/web-service/text-search
- Places API usage and billing: https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
- Google Maps Platform core pricing: https://developers.google.com/maps/billing-and-pricing/pricing
- Text Search REST reference: https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places/searchText

Relevant contract points:

- endpoint: `POST https://places.googleapis.com/v1/places:searchText`;
- a response field mask is required;
- billing is based on the **highest applicable SKU represented in the field mask**;
- Text Search (New) returns at most 60 results across pages, subject to change;
- `pageSize` is `1..20`, defaulting to 20 when omitted;
- `nextPageToken` is returned when another page exists and is passed back as `pageToken`;
- page requests are separate API requests and therefore should be treated as separately billable successful requests;
- Google discourages wildcard `*` masks in production.

### Fields used by this repository and their current tiers

**Essentials (IDs Only)**

- `nextPageToken`
- `places.id`
- `places.name`

**Pro**

- `places.addressComponents`
- `places.businessStatus`
- `places.containingPlaces`
- `places.displayName`
- `places.formattedAddress`
- `places.googleMapsUri`
- `places.location`
- `places.plusCode`
- `places.primaryType`
- `places.primaryTypeDisplayName`
- `places.pureServiceAreaBusiness`
- `places.shortFormattedAddress`
- `places.types`
- `places.viewport`

**Enterprise**

- `places.currentOpeningHours`
- `places.internationalPhoneNumber`
- `places.priceLevel`
- `places.priceRange`
- `places.rating`
- `places.regularOpeningHours`
- `places.userRatingCount`
- `places.websiteUri`

**Enterprise + Atmosphere**

- `places.reviews`
- `places.reviewSummary`

Google can add or reclassify fields. This table is a dated local contract, not a permanent truth.

### Pricing snapshot, not a runtime estimator

As of the verification date, the global pricing page lists:

- Text Search Pro: 5,000 free monthly calls, then $32 / 1,000 in the first paid tier;
- Text Search Enterprise: 1,000 free monthly calls, then $35 / 1,000;
- Text Search Enterprise + Atmosphere: 1,000 free monthly calls, then $40 / 1,000.

The CLI should **not** calculate a dollar bill from those figures. Actual spend depends on monthly usage, tiering, negotiated pricing, subscriptions, region, and future Google changes. It should report the triggered SKU tier and link/document the verification source.

## 5. Target architecture

Keep the design small and explicit.

### `gmaps_scraper/profiles.py`

Own semantic field sets only. Suggested profiles:

- `ids`: IDs-only / minimal discovery;
- `core`: useful CSV baseline containing only Essentials + Pro fields;
- `enterprise`: `core` plus contact/rating/hours/price fields;
- `atmosphere`: `enterprise` plus review fields.

The default should be `core`.

Profiles should be immutable tuples/sets and independently testable.

### `gmaps_scraper/billing.py`

Own billing classification only:

- tier ordering;
- dated Text Search field-to-tier map;
- canonicalization of nested masks to their top-level billable field (for example `places.displayName.text` -> `places.displayName`);
- wildcard handling (`*` must never be classified as cheap);
- `highest_sku(fields)`;
- explicit `UNKNOWN`/unclassified result for fields absent from the dated table.

Do not derive profiles from the billing map or vice versa. Tests should assert the intended relationship, e.g. `highest_sku(CORE_FIELDS) == PRO`.

### `gmaps_scraper/cli.py`

Suggested public contract:

- `--profile {ids,core,enterprise,atmosphere}`, default `core`;
- `--fields ...` remains an expert override and is mutually exclusive with a non-default explicit profile, or has clearly documented precedence;
- before network access, print selected field count and highest known Text Search SKU;
- for unclassified custom fields, print an unmistakable pricing-verification warning; do not silently classify them as Pro/Essentials;
- do not add a generic interactive confirmation prompt unless later evidence shows it is needed. Non-interactive scripts should remain usable.

### `gmaps_scraper/api.py`

Keep transport concerns here:

- field-mask normalization/deduplication;
- request construction;
- bounded timeout;
- bounded retry policy for clearly retryable HTTP responses;
- pagination.

Make retry behavior deterministic and testable by injecting/mocking the request/sleep boundary. Avoid retrying indiscriminately after ambiguous network failures because repeated successful searches can mean repeated billing.

### `gmaps_scraper/normalize.py`

Retain this as the only CSV normalization implementation. Tests should ensure custom masks materialize only the requested logical fields and that nested expansion remains deterministic.

## 6. Output contract decision

Prefer the package-path conventions already represented by `data/fixtures/`:

- CSV: normalized analysis-friendly rows;
- JSON: raw list of returned Place objects;
- `both`: both files from the same canonical query/mask.

If metadata such as query, selected profile, field mask, SKU classification, or verification date is important, prefer a small sidecar metadata artifact rather than silently changing the raw JSON fixture contract. Agent B may choose otherwise, but must make the choice explicit and test it.

## 7. Test packet

All normal tests must run without credentials and without network access.

Minimum tests:

1. `CORE_FIELDS` resolves to Pro and contains no Enterprise/Atmosphere field.
2. `ids` resolves to Essentials IDs Only.
3. adding `places.rating` or `places.websiteUri` raises classification to Enterprise.
4. adding `places.reviews` or `places.reviewSummary` raises classification to Enterprise + Atmosphere.
5. nested custom fields classify through their parent billable field.
6. wildcard `*` is never reported as a cheap/known-safe mask.
7. an unknown field yields explicit unclassified status.
8. field-mask normalization adds `nextPageToken` once and preserves order.
9. pagination stops when no token exists and respects `max_pages <= 3`.
10. package CLI rejects page counts outside `1..3` before network access.
11. custom `--fields` controls both the request mask and CSV normalization/schema.
12. default CLI path contains no review fields.
13. README examples are exercised at least at argument-parsing/help level.
14. no test requires `GOOGLE_PLACES_API_KEY`.

A later manually authorized live smoke test can validate current server behavior; it must not be part of CI and must make expected billable calls explicit before execution.

## 8. Implementation sequence for Agent B

Order matters because each step should reduce ambiguity for the next:

1. add offline test harness around current package path;
2. add billing classifier + dated source metadata;
3. add semantic profiles and assertions linking profiles to expected tiers;
4. switch CLI default to `core` and expose `--profile`;
5. make SKU classification visible before network access;
6. repair request retry/timeout semantics and remove or justify legacy pagination sleep;
7. lock custom `--fields` request/output behavior with tests;
8. deprecate root `text_runner.py` by delegation or removal once compatibility coverage exists;
9. align README, install/dependency instructions, examples, lifecycle notes, and output contract;
10. run the full offline acceptance suite;
11. optionally perform one explicit live smoke test with a deliberately cheap mask after credential/billing readiness is confirmed.

## 9. Acceptance gate

The hardening pass is complete only when all are true:

- one documented canonical invocation exists;
- default invocation classifies as the intended cheap/useful SKU (Pro);
- `ids` can reach the IDs-only tier;
- Enterprise fields visibly raise the classification;
- reviews visibly raise it to Enterprise + Atmosphere;
- custom fields control request and output consistently;
- no default path silently requests reviews;
- README examples match executable behavior;
- tests cover the cost contract and run offline;
- live API use is never required by CI;
- the repository remains a small Places Text Search client.

## 10. Non-goals

Do not add in this maintenance packet:

- CRM or lead-management features;
- scraping;
- dashboards;
- external cost-guard product integration;
- automatic Place Details enrichment of every search result;
- account-specific dollar-cost estimation;
- generalized Google Cloud billing management;
- broad refactors unrelated to the identified contract drift.
