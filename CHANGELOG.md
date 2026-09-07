# Changelog

## 0.2.0 — unreleased

Local-business kernel / external-integration readiness pass.

### Added

- provider-neutral `BusinessRecord` contract;
- durable `BusinessRef` handoff contract;
- governed provider registry;
- Google Places Text Search adapter with field-mask cost preflight;
- Openmart Local Business API adapter for a concrete lead-census consumer;
- structured `GeoArea` city/state/country request contract alongside Google circle bias;
- `--provider` and `--output-contract business|refs|provider` CLI surfaces;
- IDs-only automatic field selection for durable Google `refs` handoff;
- bounded `local-business-census` console tool with dry-run, total-request budget, cross-cell deduplication, membership provenance and run manifests;
- affluent-US website-lead census example (4 markets × 4 local-service categories);
- standalone `places-costcheck` console tool;
- installable `pyproject.toml` and console entry points;
- explicit provider persistence/compliance documentation;
- provider extension contract and evidence-driven issue templates;
- offline tests for provider identity, Openmart normalization, census budgeting/deduplication, packaging and costcheck.

### Changed

- default CLI output is the provider-neutral `business` contract rather than the legacy Google-shaped CSV schema;
- provider-specific options are now validated at the CLI boundary rather than leaking Google field-mask/geography assumptions into every adapter;
- legacy Google-shaped output remains available through `--output-contract provider`;
- CI installs the package and smoke-tests the discovery, census and costcheck public console surfaces before running the credential-free contract suite.

### Release gates still open

- run the included Openmart census once with a user-owned `OPENMART_API_KEY`;
- verify the live response envelope and normalized field mapping against current provider behavior;
- inspect data quality/deduplication on the resulting business universe;
- decide distribution/license posture before PyPI publication.

### Deliberately not included

- Foursquare/Geoapify adapters without a concrete consumer;
- PyPI publication;
- an open-source license decision;
- automatic people/owner/email enrichment or paid contact unlocking;
- outreach automation / CRM behavior;
- generalized source-code scanning or GitHub PR comments for costcheck.

## 0.1.x — pre-release repository history

The repository originated as a small Google Places Text Search -> CSV/JSON utility. The 2026-09-07 hardening pass consolidated the runtime, introduced explicit Google field/SKU profiles and offline CI, and made one-page Text Search Pro the safe default.
