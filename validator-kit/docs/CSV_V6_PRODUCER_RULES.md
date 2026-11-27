# Production CSV v6 rules and field dictionary

Authority: `CsvCatalogueSchema.Header`, `Parse` and `ParseCore` in `src/AIConnect.Catalogue/CsvCatalogueSchema.cs`, copied unchanged into the kit. This is not `catalogue/catalogue.schema.json`; that JSON schema belongs to the historical JSON catalogue and is not included in this minimal kit. The old `tools/Catalogue.Validator` is not a CSV validator.

## Enforced input rules

UTF-8 with optional BOM, strict decoding; at most 2 MiB of original bytes. Exact ordered 66-column header, quoted CSV including multiline text; 1–1000 rows, every row same width, each field <=50,000 characters. No normalization of input bytes for feed hash. Nonempty entry/model/variant IDs and model name; entry IDs unique. Schema `6`. Category is one of light_image_generation, heavy_image_generation, light_text, heavy_text, transcription. Each category present has unique consecutive integer category_preference_order values 1..N; not every category has to be present.

Enums: row_status research/candidate/deprecated; package_completeness complete/partial/unknown; backend CUDA/CPU/Metal; memory_type dedicated_gpu/cpu_only/unified_memory. Numeric fields may be empty, otherwise finite nonnegative invariant-culture numbers. Low memory bounds cannot exceed high; required free GPU/unified budgets cannot be below their corresponding supplied peak high. Unified budget cannot appear on non-unified rows; dedicated VRAM budget cannot appear on non-dedicated rows; unified rows cannot supply host free-RAM budget.

required_files_json is an array of at most 100 objects. Each object must have a safe nonempty relative filename (no absolute path, backslash, colon, empty/dot/parent segments) and absolute HTTPS repository_url without user information. An empty array is legal research data. Other manifest metadata can be unresolved. These parser checks are deliberately weaker than acquisition checks; complete is a claim, not independent proof of a complete pipeline.

## Field groups (all headers must exist)

| Fields | Meaning / representation |
|---|---|
| entry_id, model_id, variant_id, model_name, publisher | Stable row, family/variant identity and display labels. |
| category, capabilities, category_preference_order | Work category, descriptive capabilities, per-category editorial rank. |
| parameter_count_billion_total, parameter_count_billion_active | Optional nonnegative parameter counts in billions. |
| quantization, file_format, architecture | Exact variant format and architecture; descriptive until adapter checks. |
| runtime_name, runtime_version_or_commit, backend, operating_systems | Runtime claim and OS tokens separated by semicolons; current manager route uses windows_x64. |
| memory_type, gpu_count | Separate dedicated, CPU or unified topology; CSV execution does not pool GPUs. |
| estimated_peak_vram_gib_low, estimated_peak_vram_gib_high, estimated_peak_unified_memory_gib_low, estimated_peak_unified_memory_gib_high | Optional memory range; unknown is blank, not zero. |
| recommended_system_ram_gib, required_free_host_ram_gib, required_free_vram_gib, required_free_unified_memory_gib | Installed capacity versus free budgets; binary GiB. |
| memory_scope, memory_evidence_type, memory_assumptions, fit_budget_basis, offload_mode | Scope, evidence method/assumptions, allowance basis and offload claim; see capacity contract. |
| image_width, image_height, context_tokens, max_output_tokens, batch_size, recommended_steps, sampler, guidance_scale, flow_shift | Workload/settings; numbers optional, no executable permission from these fields. |
| model_page_url, variant_repo_url, revision, main_weight_filename, additional_required_files, required_files_json | Model and complete dependency references. JSON component properties used by acquisition identity: slot, repository_url, filename, revision, size_bytes, sha256, shard_index, shard_count. |
| runtime_support_source_url, memory_source_urls, other_source_urls, checked_date, reviewed_utc | Evidence provenance/review dates; source/date gaps reported, not silently invented. |
| recommendation_priority, recommendation_reason, short_description, best_for, limitations | Editorial explanations; category_preference_order controls ordering. |
| license_id, license_url, access_requirements | Publisher terms/access claims; not legal or anonymous-access verification. |
| schema_version, row_status, supersedes_entry_id, package_completeness, change_note | Version/lifecycle, predecessor link, completeness claim and update rationale. |
| required_gpu_features | Non-CPU recommendation needs literal none unless feature validation is added to the adapter. |

## Repair guidance

INPUT_REJECTED: use diagnostic message and CSV root/previous/manifest location; parser currently does not expose physical row numbers, and quoted multiline fields make line guessing unsafe. Warning locations use entry ID plus field/JSON-array index. Correct malformed JSON/columns/enums, duplicate IDs or ranks, bounds/topology errors; never modify real input automatically to force acceptance.

UNRESOLVED_FILE: resolve actual publisher commit, case-sensitive path, positive exact byte size and SHA-256, and every shard. INCOMPLETE_PACKAGE: establish required supporting components, not just weights. CAPACITY_UNKNOWN: provide sourced complete-pipeline method and budgets or retain research-only. RESEARCH_ONLY: expected for valid research/deprecated data, not permission to relabel it candidate. SOURCE_GAPS: supply authentic sources and dates where known. None of these warnings claims local validation of model execution.

Diff uses `CsvCatalogueIdentity.Id` directly (the manager delegates `CsvAcquisition.Id` to it). Entry removal = withdrawn; addition = added. Changed acquisition identity = files-runtime-settings-identity. Pure deprecation = withdrawn; changed rank = ranking-editorial; other metadata/policy changes = metadata-policy. Every changed field is listed, so a rank change accompanied by memory changes remains reviewable. JSON key order and component order alone do not change acquisition identity. Memory budgets, prose, dates and ranks do not change acquisition identity, but can change filtering/content policy. File/revision/hash/quantization/component/runtime/settings changes do. Changing entry ID is remove/add; no automatic migration of tests or selections.
