# 0.2.0 release checklist

`0.2.0` remains unreleased until the remaining empirical and distribution gates are satisfied.

## Contract / CI

The current `main` workflow proves these gates on Python 3.10 and 3.12 with Google/Openmart credentials blank.

- [x] Python 3.10 offline CI green.
- [x] Python 3.12 offline CI green.
- [x] `local-business-discover --help` installs and runs.
- [x] `local-business-census --help` installs and runs.
- [x] included census dry-run succeeds with no credentials.
- [x] `places-costcheck --profile core` installs and runs.
- [x] all tests run with Google/Openmart credentials blank.

Latest post-checkpoint `main` run at the time of this update: workflow run `34168038978`, commit `85d12082a187031581b1bd0fe02999b2a118f480`, conclusion `success`.

## Live acceptance status

A first real Openmart census was attempted on 2026-09-07 using the included affluent-US plan. It completed 15 of 16 cells and returned 671 business observations before Openmart returned an account-level HTTP 402 on the final cell.

That attempt established that the live request/response path was broadly functional, but it did **not** satisfy the release gate because the pre-fix runner kept successful results in memory and lost them when the final provider exception unwound the process. PR #6 (`Make census results durable and resumable`) fixed that failure mode by checkpointing completed cells atomically and adding plan-hash-verified resume.

See `docs/LIVE_ACCEPTANCE_2026-09-07.md` for the bounded evidence record.

### Remaining live gate

Once the Openmart account can issue requests again, run the same bounded plan from current `main`:

```bash
export OPENMART_API_KEY='...'
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --max-total-requests 16
```

If the account fails part-way through again, keep the generated run directory and resume it rather than starting over:

```bash
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --max-total-requests 16 \
  --resume-run out/census/website-leads-us-affluent_YYYYMMDD_HHMMSS
```

Then verify from the persisted artifacts:

- [ ] run reaches `status: complete` (possibly after resume);
- [ ] response envelope is accepted without fallback guessing masking a provider change;
- [ ] provider IDs are present for the overwhelming majority of observations;
- [ ] names/addresses/websites/phones/rating fields map correctly where returned;
- [ ] cross-cell deduplication is sensible;
- [ ] manifest counts match persisted artifacts;
- [ ] checkpoint/resume preserves every completed paid cell across any provider failure;
- [ ] no credential appears in outputs/logs;
- [ ] provider account usage/credits match the actual bounded request count;
- [ ] sample business records are useful enough for the intended personal prospecting workflow.

If the live schema differs, repair the adapter and add the observed shape as a fixture before release.

Do not commit `out/census/` lead artifacts to this public repository; `out/` is intentionally ignored.

## Documentation / policy

- [ ] re-check Google Maps Platform and service-specific terms on release day;
- [ ] re-check Openmart API/product/account terms on release day;
- [ ] update `policy_verified_on` values if needed;
- [x] README links to `COMPLIANCE.md`, `docs/CENSUS.md`, and this checklist;
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
