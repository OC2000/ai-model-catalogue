# rev5 unresolved items

1. **Capacity budgets not set for new rows.** `required_free_vram_gib`, `required_free_host_ram_gib` and `fit_budget_basis` are blank because the capacity policy is pending. The rows are therefore not browse/fit eligible. Not filled in by adding a margin.
2. **Runtime compatibility not established.** `runtime_version_or_commit` is blank for all four rows. Gemma 4 and Qwen3.5-family MoE GGUFs already appear in rev4; `inkling2_loop` is new and its minimum llama.cpp build is unknown. No app support or local testing claimed.
3. **Inkling 2 Mini memory unknown.** Estimator v0.2 does not model the looped architecture; `memory_scope` and `memory_evidence_type` are `unknown`.
4. **Inkling GGUF licence.** The ggml-org repository declares no licence; the row uses the original model's Apache-2.0 (thinkingmachines/Inkling-2-Mini). The mirror's lack of a licence does not change that obligation.
5. **Nemotron Bolt licence is OpenMDW-1.1**, recorded as `LicenseRef-OpenMDW-1.1`. Its "4GB" repository name is not used as a memory figure.
6. **Estimate caveats.** Bolt: shared-KV layers not modelled (over-count). Gemma 31B: K=V attention counted separately (conservative). Qwen3.6: no CPU expert offload estimated.
7. **Carried over from rev4:** Qwen-Image runtime contract (flow-shift), Z-Image text encoder, capacity policy, publication location.
