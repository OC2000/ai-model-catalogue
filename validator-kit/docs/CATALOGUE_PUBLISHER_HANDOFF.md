# Minimal CSV publisher kit — 1.1.0

Replacement for the accepted 2x kit, from checkpoint b1b5750. Implemented for review. The previous ZIP SHA-256 is confirmed as `4906c2e22356745bc994bf8cc489a3a72efc9d1665a729007cce5da4353c47c9`. Use the new minimal ZIP for public transfer instead; do not publish the old full-Core kit.

## Contents and boundary

`AIConnect.Catalogue.csproj` is a dependency-free .NET library containing only CSV schema/parser/data types, feed-envelope parsing and the pure acquisition identity calculation used for the change report. AIConnect.Core and CsvCatalogue.Validator both reference it. App `CsvModelCatalogue.Parse` and `CsvAcquisition.Id` delegate to that same implementation; there is no copied stand-in parser. The existing AIConnect.Core namespace is retained for source API compatibility, but these types now live in AIConnect.Catalogue.dll. Existing app consumers should rebuild with the new project dependency.

The kit includes only that library, the CLI, exact SDK/build/lock files, these producer documents, integrity/smoke scripts and a CI template. No AIConnect.Core project, Gemini/helper/provider/credential code, device probing, downloads, model data, embedded resources or app catalogue. Capacity filtering/persistence/runtime checks stay private in the app; their existing behavior is documented, not exported as executable code. Packaging uses an explicit file allowlist.

Version 1.1.0; schema 6; unchanged capacity policy manager-capacity-2x-1. SourceCheckpoint identifies base b1b5750; SHA256SUMS identifies actual kit source. ZIP hash must be supplied through a trusted channel; it is integrity, not a signature. No claim of acceptance or new source commit until Tom accepts this revision.

## Build and run

Requirements: .NET SDK **10.0.403**, roll-forward disabled, .NET 10 target. There are no NuGet package dependencies. PowerShell 7 (`pwsh`) runs the scripts on Linux/Windows; Windows PowerShell also worked locally. The CLI itself uses only dotnet.

Claude's workspace cannot install the SDK: perform the first Linux proof on GitHub Actions. Linux and hosted runner execution are **unverified here**. Windows local build and smoke are verified; the supplied uninstalled CI matrix tries ubuntu-latest and windows-latest independently. Use Linux after it passes, otherwise windows-latest. Do not treat lack of a Linux run as success, and do not automatically publish merely because one matrix job started.

From extracted kit root, stop if any preceding command fails:

```powershell
pwsh -File tools/CsvCatalogue.Validator/Verify-Kit.ps1 -KitRoot .
dotnet restore tools/CsvCatalogue.Validator --locked-mode --ignore-failed-sources
dotnet build tools/CsvCatalogue.Validator -c Release --no-restore
pwsh -File tools/CsvCatalogue.Validator/Test-Kit.ps1 -OutputDirectory synthetic-smoke
dotnet tools/CsvCatalogue.Validator/bin/Release/net10.0/CsvCatalogue.Validator.dll --csv candidate.csv --kind candidate --previous accepted.csv --json validation.json
```

`--previous`, `--manifest` and `--json` are optional. Output files must be new; input cannot be overwritten. All validation is offline, read-only and bounded. No user profile, model files, credentials, UI or native runtimes are accessed. CI checkout/SDK setup is separate from offline validation.

After committing exact CSV bytes and obtaining the **actual** immutable commit, construct proposed latest.json and run:

```powershell
dotnet tools/CsvCatalogue.Validator/bin/Release/net10.0/CsvCatalogue.Validator.dll --csv candidate.csv --kind candidate --previous accepted.csv --manifest latest.proposed.json --json pointer-validation.json
```

Manifest: <=16 KiB; schemaVersion 6; nonblank releaseId <=160 characters; positive sizeBytes <=2 MiB; 64-hex sha256; valid publishedUtc <= five minutes ahead. csvUrl must be HTTPS raw.githubusercontent.com/OC2000/ai-model-catalogue/{40-hex-real-commit}/releases/{safe-name}.csv, default port, no user info/query/fragment. The pointer is mutable; release bytes are not. Never invent the commit or point release bytes to main. CLI checks exact CSV size/hash but cannot prove the remote commit exists.

## Results and agreed warning policy

**Tom's policy is errors only: warnings are reported but do not block promotion.** Exit 0 passes the validator gate even with warnings; exit 1 rejects data; exit 2 is invocation/IO/tool failure and must block. Warnings must remain visible in reports, not silently discarded. No extra warning-to-error policy is introduced here.

Stdout JSON includes Valid, Kind, version/base checkpoint/policy, exact byte count/SHA-256, previous identity if supplied, diagnostics and Changes; stderr is a concise summary. `PublicationApproved=false` means this offline tool has not performed remote publication, checked remote bytes or established runtime/device verification. It is not a warning-based veto: the external publisher should gate on exit code/Valid, declared candidate kind, exact-byte identity and its completed publication steps, not require PublicationApproved=true. Same applies to valid research-only rows.

Error locations are csv:$, previous:$ or manifest:$; parser does not invent physical line numbers for multiline CSV. Warnings identify entry/field/index. Oversized input is rejected before full hashing. Diagnostics are deterministic except intentional time-dependent future-date validation. Reports are never written over existing files.

`--kind synthetic` labels smoke fixtures and cannot validate a publication manifest. The external publisher must reject synthetic provenance and control its input path; deliberately relabelling invented data as candidate cannot be detected by this parser. The smoke script checks separate-process exit codes 0, 1 and 2. It must never feed publication.

Schema/data dictionary: CSV_V6_PRODUCER_RULES.md; existing client memory behavior: CSV_CAPACITY_CONTRACT.md. Warnings do not weaken client filtering or promote research rows to runtime support. Abliterated variants use the same rules. Qwen-Image runtime settings remain unresolved; no new runtime integration is shipped.

## External runner and publication

The CI example is a template, not installed automation. It uses contents: read, no stored checkout credentials and no scheduling or promotion. Pin actions to reviewed immutable SHAs before deployment. First prove build/smoke and actual catalogue validation on the runner, then retain the working platform. Include report JSON in the external job's existing reporting path.

Publication remains the external workflow: research -> candidate -> errors-only validation -> immutable release commit -> proposed pointer validation -> fetch and verify exact published CSV bytes -> update pointer last. Serialize promotion or compare expected prior pointer/branch commit. Existing release identity with different bytes must fail; identical retries can be no-ops. Failure leaves current live pointer unchanged. This kit does not implement remote writing, staging, concurrency or online research.

Publisher hashes/HEAD/Range are metadata, not independent hashing of complete model weights. Keep sources, dates, access/licence/estimate claims honest; the validator does not certify these claims or local inference. No added warning-based approval step is required by this revision.

Reproduce transfer in the private workspace: scripts/New-CsvPublisherKit.ps1 -OutputDirectory artifacts/csv-publisher-kit-1.1.0 (fresh destination required). Source checksums are reproducible; ZIP timestamps can change its hash. No external repository access is assumed.

Next task: review the minimal kit and prove its Linux/Windows execution on the GitHub runner. Do not begin the next module automatically.