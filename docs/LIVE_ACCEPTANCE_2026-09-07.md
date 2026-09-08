# Live acceptance evidence — 2026-09-07

This file records the first real Openmart census attempt for the `0.2.0` release gate without publishing provider credentials, business identities, or lead data.

## Plan

- provider: Openmart
- plan: `examples/census/website-leads-us-affluent.json`
- intended cells: 16
- page size: 50
- max pages per cell: 1
- pre-network request budget: 16
- theoretical raw-record ceiling: 800

The plan covers four explicit business categories across four explicit affluent US markets. It is a bounded API exercise, not an open-ended market-intelligence crawler.

## Observed result

The first real run completed 15 of 16 cells and returned 671 business observations before the provider returned an account-level HTTP 402 on the final cell.

The live adapter therefore reached real Openmart search responses successfully across most of the plan. However, this run cannot be treated as release acceptance because the pre-fix census runner held results in memory until the whole run completed. The terminal provider exception unwound execution before the run artifacts were written, so the 671 returned observations were not durably available for normalization, dedupe, manifest, or commercial-use inspection.

No provider credential should be committed or copied into this repository.

## Failure exposed by reality

The failed run revealed a material paid-data durability bug:

> a bounded provider failure after successful paid cells could discard all earlier returned records.

PR #6, `Make census results durable and resumable`, corrected that contract by:

- creating the run directory before the first network request;
- atomically checkpointing normalized records, membership, checkpoint state, and manifest after every completed cell;
- recording `in_progress`, `failed`, and `complete` run status;
- preserving failed-cell metadata and provider error text;
- adding `--resume-run` with plan-hash verification;
- skipping already completed cells during resume so they are not reissued.

Post-fix `main` commit: `85d12082a187031581b1bd0fe02999b2a118f480`.

Post-fix offline CI workflow run: `34168038978`, conclusion `success` on Python 3.10 and 3.12.

## What the first attempt proves

It is reasonable to treat the following as empirical evidence, but not yet as a completed release gate:

- the Openmart account/key could authenticate and execute live search requests;
- the current endpoint/payload contract was accepted for at least 15 cells;
- the provider returned substantial business data at the expected order of magnitude;
- the bounded request budget was small enough to expose account-level credit behavior quickly;
- checkpoint/resume was a necessary product invariant, not theoretical hardening.

## What remains unproven

A persisted current-code run is still required to inspect:

- final normalized field coverage;
- durable provider IDs;
- cross-cell deduplication;
- artifact/manifest count agreement;
- resume behavior under a real provider failure, if one occurs;
- provider account usage versus the actual number of issued requests;
- whether the resulting business universe is useful for the intended personal prospecting workflow.

## Next acceptance action

Once the Openmart account can issue requests again, rerun the same bounded plan from current `main`:

```bash
local-business-census \
  examples/census/website-leads-us-affluent.json \
  --max-total-requests 16
```

If it stops part-way through, preserve the new `out/census/...` run directory and resume that exact directory with `--resume-run` after the provider/account condition is resolved.

Do not commit the resulting lead CSVs or provider IDs to the public repository. The release decision should use aggregate acceptance findings only.
