# CSV capacity contract — manager-capacity-2x-1

Implemented behavior, not a new publication policy. Source: `src/AIConnect.Core/CsvModelCatalogue.cs` (`BrowseFit`, `Fit`, `CatalogueBrowseRows`, `CatalogueAssessments`), `LocalHardwarePolicy.cs`, `CsvAcquisition.cs`. Tests: `CsvCatalogueTests` and `CsvPublisherKitTests`.

## Separate decisions

| Decision | Meaning |
|---|---|
| Valid CSV | Production parser accepts its structure. Research, incomplete and deprecated entries can be valid. |
| Browse match | Current platform and memory screening passes; no executable compatibility or measured fit claim. Research rows can pass. |
| Recommendation eligible | `Fit` also requires candidate status, complete package, evidence, pinned component metadata and matching integrated adapter. Still only recommended to try. |
| Prepared | Exact required files resolved and their downloaded bytes checked. Publisher-provided hashes alone are not file verification. |
| Tested on this device | Successful manager test bound to exact package, files, runtime and settings. CSV cannot confer this. |

Category preference order is editorial order within each category, not benchmark truth. UI ranks remaining hardware matches consecutively. Existing downloads/draft choices may remain visible even if fresh screening excludes them; deprecated entries do not receive that retention exception. A weekly publisher does not know client free memory, installed adapters or device test results.

## Actual memory screening

All `_gib` values are binary GiB (1,073,741,824 bytes). File sizes are bytes; file size is not runtime allocation. Installed RAM and currently free RAM are different inputs. Do not pool GPUs, or add dedicated VRAM to RAM.

- Global local-work gate: known total RAM at most 4 GiB, no positive execution-GPU capacity and no positive available unified pool disables local work. Unknown RAM is not treated as 4 GiB. This is a product gate, not a scientific assertion about every CPU model.
- Both paths reject deprecated rows, stale (>5 minutes) or absent device snapshots, wrong OS and missing complete-pipeline memory scope/evidence/basis. `Fit` is stricter as below.
- Dedicated/CPU browsing: positive `recommended_system_ram_gib`, if supplied, must fit installed RAM. Positive `required_free_host_ram_gib` must fit currently available RAM. Unknown/zero required host budget is not fit.
- Dedicated GPU browsing requires CUDA, exactly one GPU, positive required free VRAM and available VRAM. Full budget fits normally. At 85% through less than 100% of the GPU budget, browsing allows a borderline candidate only if free host RAM covers the host budget **plus the GPU shortfall**. Less than 85% is excluded. This is a tolerance heuristic for possible offload, not proof the runtime supports it; offload may be slower. It does not add RAM and VRAM into one pool, nor provide a host-RAM tolerance.
- CPU-only browsing requires CPU backend. A valid topology string alone is insufficient.
- Unified browsing requires an explicitly measured shared-memory pool and positive unified budget; at least 85% allows a borderline candidate. It does not add host RAM again or apply the dedicated-path installed-RAM check. There is no integrated unified execution adapter in `Fit` today.
- No extra fixed reserve is subtracted by these CSV functions. `fit_budget_basis` and `memory_assumptions` should explain any publisher reserve already included. The older phase-allocation adviser (`AdviserReport.cs`) has a separate default 1 GiB-per-pool reserve; **do not apply or claim that reserve as the CSV policy**.

`Fit` additionally requires `row_status=candidate`, `package_completeness=complete`, architecture and runtime version, nonempty manifest with nonempty component revisions, matching installed adapter and backend, sufficient requested context, and `required_gpu_features=none` for non-CPU routes. Unified execution is rejected. Dedicated free VRAM must meet the **full** budget: the 15% browsing allowance does not make a recommendation. The acquisition resolver separately enforces exact SHA/revisions/size and shard rules. `Fit` does not independently fetch publisher metadata or run inference.

Synthetic executable cases include 4 GiB/no GPU disabled, 14/16 GiB borderline with adequate host headroom, insufficient host headroom excluded, 13/16 GiB excluded, research/unknown evidence not recommended, unified explicit pool and stale snapshots. No real GPU allocation is simulated as a successful test.

## Existing producer contract versus proposed decisions

Research rows may leave runtime, architecture, memory bounds, sources/dates, revisions and hashes unknown. Required CSV columns, enums, identities and syntactically valid file JSON remain mandatory. An empty file array is permitted. The parser does not enforce source freshness, licence accuracy, runtime claims or reproducibility of estimates. Source fields (`memory_source_urls`, `runtime_support_source_url`, `other_source_urls`, `checked_date`, `reviewed_utc`) carry evidence but their date/URL semantics are not universally validated. Do not label unknown data measured or tested.

For recommendation eligibility the production requirements above apply. Hashes/size in publisher metadata identify claims about artifacts; HEAD, Range, config or file-header reads do not independently hash complete weights. Keep observation method, source/date, context, batch, resolution, quantization, offload and margins in the row's evidence fields and companion release report. No new runtime recipe is approved here, including Qwen-Image flow-shift. Abliterated variants follow exactly the same identity, compatibility and evidence rules; this kit does not decide whether the scheduled researcher includes them.

**Agreed warning policy (Tom): errors only.** All validator warnings remain in reports but do not block promotion. Exit 1 (invalid data) or 2 (invocation/tool failure) blocks the validation gate. A valid candidate with warnings passes that gate. Exact-byte checks, synthetic exclusion and successful runner execution still apply; this does not confer device verification or change client capacity filtering. No additional source freshness, coverage, licence or ranking gate is introduced by this kit. The external publisher remains responsible for its existing publication operations.
