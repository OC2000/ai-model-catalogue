# Catalogue update runbook

This runbook is for a catalogue update run, whether manual or scheduled. Every run starts from a fresh clone and works only on a new branch. **A run never pushes to `main`, never merges, never publishes and never changes a schedule.**

## Status label (mandatory)

Every pull request and report states its validation status in these words:

> **publisher checks passed; app validation pending**

…or, if a check failed, says which one. Never call `tools/precheck_csv.py` the app validator. The app validator is `AIConnect.Core.CsvModelCatalogue.Parse` (`CsvModelCatalogue.cs`), and it hasn't been integrated into this job.

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
8. **Memory.** Published budgets are never lowered to match an estimate.
   - New text rows get a reproducible estimate (`tools/estimation/`), recorded with its inputs.
   - A budget that looks tight is flagged for review, not edited.
9. **Validation before proposing.** The whole candidate CSV must pass `tools/run_checks.sh` (part A: mirror of the app parser; part B: publisher checks; pin integrity) before a PR is opened.
10. **Failure preserves the baseline.** If research, validation or network access fails, open no release PR. `accepted.json` and `releases/` stay unchanged. At most, open a report-only PR (`reports/` only) describing the failure, or simply report it.
11. **Publishing is separate.** `latest.json` is created only when publication is explicitly authorised, using `tools/make_latest.py` with the real hosted URL; it records the real time. A run never creates or edits `latest.json`.

## Procedure

1. Clone the repository and create a branch: `update/YYYYMMDD-revN` (or `report/YYYYMMDD` for a report-only run).
2. Run `tools/run_checks.sh <accepted file> reports/<date>-baseline`.
   - If pin integrity fails, stop and report.
   - Note any `changed-upstream` or `removed-upstream` files.
3. Research new releases and quantisations for the five categories, using primary sources only (publisher model cards and repositories, runtime documentation). News and community lists are leads only.
4. For each candidate:
   - Pin its files with `tools/resolve_candidate.py`.
   - Fill only the fields that are established.
   - Add the row at the end of its category.
   - Estimate memory where the estimator supports the architecture.
5. Write the new CSV as a new immutable file. Do not modify the previous one.
6. Run `tools/run_checks.sh <new file> reports/<date>-revN`. Everything must pass. Then write `releases/notes/revN/` with a change summary, unresolved items and a memory report.
7. If nothing changed, open no release PR; report "no changes".
8. Otherwise commit, push the branch, and open a PR using the template. **Do not merge.**
