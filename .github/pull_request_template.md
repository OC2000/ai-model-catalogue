## Status

**publisher checks passed; app validation pending**
<!-- If anything failed, replace the line above with what failed. Never call the pre-check the app validator. -->

## Release

| | |
|---|---|
| Baseline (`accepted.json`) | releaseId, SHA-256 |
| Proposed file | `releases/ai-model-catalogue-v6-YYYYMMDD-revN.csv` |
| Size / SHA-256 | |
| Rows (added / superseded / unchanged) | |

## Changes
- New rows (added at the end of their category, `row_status = research`):
- Replacement proposals (`supersedes_entry_id`), with the upstream change that triggered each:
- Pins kept despite newer commits (`unchanged-newer-commit`):

## Ranking proposals (not applied)
<!-- Ranks in the CSV stay unique and consecutive; reorderings proposed here for review. -->

## Checks
- Part A, mirror of `CsvModelCatalogue.ParseCore` (not the app validator):
- Part B, publisher checks (pins, sizes, SHA-256, pinned URLs, access vocabulary):
- Pin integrity / drift / destination access (206 + Content-Range = size):
- Memory estimates (budgets never lowered):

## Not established
<!-- Metadata verification ≠ download access ≠ completeness ≠ runtime compatibility ≠ local testing. -->

## Reviewer checklist
- [ ] App validation (`CsvModelCatalogue.Parse`) run on the proposed file
- [ ] Ranking proposals accepted or rejected
- [ ] Merge does **not** publish; `latest.json` is created only on explicit authorisation
