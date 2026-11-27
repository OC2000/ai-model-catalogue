# Catalogue update runbook

This runbook is for a catalogue update run, whether manual or scheduled. Every run starts from a fresh clone and works only on a new branch. **A run never pushes directly to `main` and never changes a schedule.** It merges and publishes only through the automatic-release gate below.

> **Automatic publishing resumed (owner decision 2026-11-27)** after the production validator was integrated as required checks on `main`, the capacity policy was agreed (errors-only gating), and a failing pull request was shown to be blocked from merging (PR #12). A run merges and publishes only through the automatic-release gate (rule 12, steps 9-11); anything else leaves its PR open and the live feed unchanged.

## Status label (mandatory)

Every pull request and report states its validation status in these words:

> **publisher checks passed; app validation pending** (until the GitHub check below has finished)
> **publisher checks passed; app validation passed** (both required checks succeeded on the PR's head commit)
> **app validation failed** (either required check failed: never publish)

Never call `tools/precheck_csv.py` the app validator. The app validator is the production `CsvCatalogue.Validator` (kit 1.1.0, `validator-kit/`, shared `AIConnect.Catalogue` parser), run by the GitHub workflow **App validator** (`.github/workflows/validate-catalogue.yml`) on every pull request. Its required checks are **`validate (ubuntu-latest)`** and **`validate (windows-latest)`**. The workflow validates every added release against the accepted one, fails any change to an existing release, and always validates `latest.json` (which must exist) against the exact bytes it pins.

Warning policy: **errors block, warnings don't.** A validator error, a release-gate error or a failed job is a failed check and blocks merging and publication. Warnings (`RESEARCH_ONLY`, `CAPACITY_UNKNOWN`, `INCOMPLETE_PACKAGE`, `UNRESOLVED_FILE`, `SOURCE_GAPS`, …) never block, but are counted and listed in the release notes and the PR.

## Rules

1. **Baseline.** Start from the release named in `accepted.json` and check its SHA-256 first. Never edit a file in `releases/`. Each revision is a new immutable file: `releases/ai-model-catalogue-v6-YYYYMMDD-revN.csv`.
2. **Keep pins stable.** A newer repository commit is *not* a reason to change a row. Replacement is proposed only when a relevant pinned file has changed or been removed upstream (`drift` = `changed-upstream` or `removed-upstream`), or when the settings the row depends on have changed according to primary sources.
   - Propose the replacement as a **new row** with `supersedes_entry_id` pointing at the old one. The old row stays as it is until a reviewer decides.
   - `unchanged-newer-commit` means **no change**.
3. **Schema and categories.** Use the 66-column v6 header exactly, and only the five categories: `light_image_generation`, `heavy_image_generation`, `light_text`, `heavy_text`, `transcription`.
   - New rows start as `row_status = research`.
   - Anything not established from a primary source stays blank or `unknown`, and `package_completeness` says `partial` or `unknown`. **Never invent metadata.**
4. **Ranks.** `category_preference_order` must stay unique and consecutive from 1 within each category, deprecated rows included.
   - A new row goes at the **end** of its category.
   - Any reordering is proposed in the PR description for review, and is not applied silently.
5. **Access.** Access is verified at the real download destination, not the redirect (`tools/check_pins.py`): a one-byte range request that must return `206`, with a `Content-Range` total equal to the pinned size.
   - Report `destination-unverified` honestly if the runner can't reach the host.
   - **Never download full weights.**
6. **Licences.** `license_id` follows the original model's licence.
   - A public mirror is used only when it is byte-identical (same SHA-256) **and** its provenance is established (the publisher released the same bytes).
   - A mirror's repository licence never relicenses its contents.
7. **Claims stay separate.** Metadata verification, download access, package completeness and runtime compatibility are recorded separately. Never claim app support, runtime compatibility or local testing; only the app can establish those.
8. **Memory.** Capacity policy (owner decision 2026-11-27): **errors-only publication gating**. Missing capacity evidence (`CAPACITY_UNKNOWN`, blank budgets) is a warning, not a blocker. The app's existing hardware filtering (policy `manager-capacity-2x-1`) is unchanged, so rows without a complete-pipeline budget stay published but are never offered as hardware matches. Runs never invent a budget to make a row matchable. Published budgets are never lowered to match an estimate.
   - New text rows get a reproducible estimate (`tools/estimation/`), recorded with its inputs.
   - A budget that looks tight is flagged for review, not edited.
9. **Validation before proposing.** The whole candidate CSV must pass `tools/run_checks.sh` (part A: mirror of the app parser; part B: publisher checks; pin integrity) before a PR is opened.
10. **Failure preserves the baseline.** If research, validation or network access fails, open no release PR. `accepted.json` and `releases/` stay unchanged. At most, open a report-only PR (`reports/` only) describing the failure, or simply report it.
11. **Publishing goes through the gate.** `latest.json` is written only by `tools/make_latest.py`, only in step 10 below, with the commit-pinned hosted URL and the real time. It is never edited by hand.
12. **Automatic-release gate.** A run may merge its own release PR and publish only when **all** of these hold; otherwise it leaves the PR open for review and publishes nothing:
    - `tools/run_checks.sh` passed on the new CSV (exit 0), and the baseline check passed at the start of the run;
    - every existing row is unchanged, except for rows explicitly superseded (old row kept; new row with `supersedes_entry_id`) and corrections to factually stale text;
    - no existing rank changed; new rows are only appended;
    - at most 8 new rows.
    Ranking proposals are never applied by a run: they go into a GitHub issue titled `Ranking proposals YYYY-MM-DD`.
    - **App validator:** both required checks (`validate (ubuntu-latest)`, `validate (windows-latest)`) succeeded on the release PR's head commit, and later on the publish PR's head commit (which validates the proposed `latest.json`). Warning policy (owner decision 2026-11-27): **errors only** block promotion. Warnings such as `RESEARCH_ONLY`, `CAPACITY_UNKNOWN`, `INCOMPLETE_PACKAGE`, `UNRESOLVED_FILE` and `SOURCE_GAPS` do not block, but every warning is listed in the release notes and PR. The validator report always says `PublicationApproved: false`; approval comes from this gate, not from the report.

## Procedure

1. Clone the repository and create a branch: `update/YYYYMMDD-revN` (or `report/YYYYMMDD` for a report-only run).
2. Run `tools/run_checks.sh <accepted file> reports/<date>-baseline`.
   - If pin integrity fails, stop and report.
   - Note any `changed-upstream` or `removed-upstream` files.
3. Run `tools/discover.py <accepted file> --days 21 --out reports/<date>-revN/leads.json` (exit 3 = Hub unreachable: stop, baseline kept). Then research the leads, using primary sources only (publisher model cards and repositories, runtime documentation). Leads, news and community lists are never evidence.
   - Prioritise: newer versions of families already in the catalogue (`possible_newer_version_of`), then new releases from watched publishers, then abliterated/uncensored variants (always researched and included, owner decision 2026-11-27; they need an identifiable publisher, a licence that follows the original model, and the same pinning rules), then trending repositories.
   - A newer version is added as a **new row** at the end of its category. It never silently replaces the older model; whether to deprecate or re-rank the older one is a ranking proposal.
4. For each candidate:
   - Pin its files with `tools/resolve_candidate.py`.
   - Fill only the fields that are established.
   - Add the row at the end of its category.
   - Estimate memory where the estimator supports the architecture.
5. Write the new CSV as a new immutable file. Do not modify the previous one.
6. Run `tools/run_checks.sh <new file> reports/<date>-revN`. Everything must pass. Then write `releases/notes/revN/` with a change summary, unresolved items and a memory report.
7. If nothing changed, open no release PR; report "no changes".
8. Otherwise commit, push the branch, and open a PR using the template, labelled **publisher checks passed; app validation pending**.
   - Wait for the **App validator** workflow on the PR's head commit (poll the check runs, up to 30 minutes). Read both jobs' conclusions and the validator output (job logs or the `validation-*` artifacts).
   - Both succeeded: change the PR title/status to **publisher checks passed; app validation passed** and add a comment with the validator result and warning counts by code.
   - Either failed or timed out: label it **app validation failed** (or **app validation inconclusive**), comment with the errors, and stop. Never merge or publish it. The live feed stays unchanged.
9. If the automatic-release gate (rule 12) holds, merge the PR through the API (never a direct push). Otherwise stop here; the PR waits for review.
10. Publish: on a branch `publish/YYYYMMDD-revN`, run `tools/make_latest.py releases/<new>.csv --url https://raw.githubusercontent.com/OC2000/ai-model-catalogue/<merge commit>/releases/<new>.csv --out latest.json`, set `accepted.json` to the new release (`acceptance`: "publisher checks passed; app validation passed (GitHub check)", `published`: true, `publishedUtc` from latest.json), open a PR, wait for both required checks to succeed on it (they validate the new pointer), then merge it.
    - Partial failure: if the release PR merged but publishing failed, the previous `latest.json` stays authoritative. Report it exactly that way ("release revN stored but not published"), never as "nothing merged". The next run starts from `accepted.json`, which still names the previous release.
11. Verify: fetch `https://raw.githubusercontent.com/OC2000/ai-model-catalogue/main/latest.json` (allow up to 5 minutes' cache), then the CSV it names, and confirm size and SHA-256. If this fails, report it prominently; the app keeps its previous catalogue.
