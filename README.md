# ai-model-catalogue

The producer repository for the AI Connect Manager **v6 model catalogue** (CSV, 66 columns).

**Status: not published.** There is no `latest.json` yet, and no schedule is enabled.

## Layout

| Path | Purpose |
|---|---|
| `accepted.json` | The last accepted release (baseline for every run): file, size, SHA-256 and what "accepted" covered |
| `releases/ai-model-catalogue-v6-YYYYMMDD-revN.csv` | Immutable release files, never edited after commit, each with a `.sha256` next to it |
| `releases/notes/revN/` | Change summary, unresolved items, memory report and provenance for each release |
| `tools/precheck_csv.py` | Publisher pre-check. Part A mirrors `CsvModelCatalogue.ParseCore` (**not** the app validator); part B adds publisher-only checks |
| `tools/check_pins.py` | Pin integrity, upstream drift and download-destination access (one-byte range request; no weight downloads) |
| `tools/resolve_candidate.py` | Pins a new candidate's files from Hugging Face metadata; never guesses |
| `tools/estimation/` | Reproducible VRAM estimates for llama.cpp rows (pinned configs with SHA-256) |
| `tools/run_checks.sh` | Runs all checks on one CSV and writes `reports/<name>/` |
| `tools/make_latest.py` | Writes `latest.json` **only when publication is authorised** |
| `reports/` | Check outputs, one folder per run |
| `RUNBOOK.md` | Rules and procedure for manual and scheduled update runs |

## Workflow

1. **Runs propose; people decide.** Runs work on branches and open pull requests. Rulesets aren't enforced on this private repository's plan, so the "no direct pushes to `main`" rule is a process rule in `RUNBOOK.md`.
2. **Status wording.** Every PR says **"publisher checks passed; app validation pending"** until the app's `CsvModelCatalogue.Parse` is run on the proposed file.
3. **Merging isn't publishing.** Merging records an accepted release. Publishing (`latest.json` plus hosting) is a separate, explicitly authorised step.

## Distribution pointer (`latest.json`, created only at publication)

```json
{"schemaVersion": 6, "releaseId": "...", "publishedUtc": "<real UTC>", "csvUrl": "https://.../<immutable file>.csv", "sizeBytes": 0, "sha256": "..."}
```

The app must fetch it without credentials, so publication needs a public location (a public repository or GitHub Pages); this repository is private.
