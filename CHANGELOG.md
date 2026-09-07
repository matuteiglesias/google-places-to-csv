# Changelog

## 0.2.0 — unreleased

Local-business kernel / external-integration readiness pass.

### Added

- provider-neutral `BusinessRecord` contract;
- durable `BusinessRef` handoff contract;
- governed provider registry with Google Places as the first adapter;
- `--provider` and `--output-contract business|refs|provider` CLI surfaces;
- IDs-only automatic field selection for durable Google `refs` handoff;
- standalone `places-costcheck` console tool;
- installable `pyproject.toml` and console entry points;
- explicit provider persistence/compliance documentation;
- provider extension contract and evidence-driven issue templates;
- offline tests for provider identity, handoff, normalized records, packaging and costcheck.

### Changed

- default CLI output is the provider-neutral `business` contract rather than the legacy Google-shaped CSV schema;
- legacy Google-shaped output remains available through `--output-contract provider`;
- CI installs the package and smoke-tests the public console surfaces before running the credential-free contract suite.

### Deliberately not included

- Openmart/Foursquare/Geoapify adapters without a concrete consumer;
- PyPI publication;
- an open-source license decision;
- automatic owner/email enrichment;
- generalized source-code scanning or GitHub PR comments for costcheck.

## 0.1.x — pre-release repository history

The repository originated as a small Google Places Text Search -> CSV/JSON utility. The 2026-09-07 hardening pass consolidated the runtime, introduced explicit Google field/SKU profiles and offline CI, and made one-page Text Search Pro the safe default.
