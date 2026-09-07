# 0.2.0 release checklist

`0.2.0` remains unreleased until these gates are satisfied.

## Contract / CI

- [ ] Python 3.10 offline CI green.
- [ ] Python 3.12 offline CI green.
- [ ] `local-business-discover --help` installs and runs.
- [ ] `local-business-census --help` installs and runs.
- [ ] included census dry-run succeeds with no credentials.
- [ ] `places-costcheck --profile core` installs and runs.
- [ ] all tests run with Google/Openmart credentials blank.

## One live acceptance run

Run exactly one bounded provider test before widening scope:

```bash
export OPENMART_API_KEY='...'
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --max-total-requests 16
```

Then verify:

- [ ] response envelope accepted without fallback guessing masking a provider change;
- [ ] provider IDs are present for the overwhelming majority of observations;
- [ ] names/addresses/websites/phones/rating fields map correctly where returned;
- [ ] cross-cell deduplication is sensible;
- [ ] manifest counts match artifacts;
- [ ] no credential appears in outputs/logs;
- [ ] provider account usage/credits match the expected bounded request count;
- [ ] sample business records are useful enough for the intended personal prospecting workflow.

If the live schema differs, repair the adapter and add the observed shape as a fixture before release.

## Documentation / policy

- [ ] re-check Google Maps Platform and service-specific terms on release day;
- [ ] re-check Openmart API/product/account terms on release day;
- [ ] update `policy_verified_on` values if needed;
- [ ] README links to `COMPLIANCE.md`, `docs/CENSUS.md`, and this checklist;
- [ ] changelog accurately states what shipped and what remains excluded.

## Distribution decision

Before public package publication, explicitly decide:

- [ ] repository/package license posture;
- [ ] whether PyPI publication is desired;
- [ ] whether the distribution name `google-places-to-csv` remains appropriate despite the provider-neutral kernel;
- [ ] whether to tag `0.2.0rc1` first or go directly to `0.2.0`.

Do not publish to PyPI or add an OSS license as an incidental cleanup step.

## Release command sequence (only after gates pass)

1. change `0.2.0.dev0` to the chosen release version in `pyproject.toml` and `gmaps_scraper/__init__.py`;
2. change `0.2.0 — unreleased` in `CHANGELOG.md` to the release date;
3. run full offline tests from a clean checkout;
4. build package artifacts locally and inspect metadata;
5. tag/release only after the distribution/license decision is explicit.
