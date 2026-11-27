# rev5 change summary (update run 2026-11-27)

Proposed: `releases/ai-model-catalogue-v6-20261127-rev5.csv`, 36 rows, 125,425 bytes,
SHA-256 `2859c4840638918cc22fc233b48ef8c573d604112db2b6058051d265fc282b50`.
Baseline: accepted rev4 (`b796f839…dd22`), unchanged. Not published; `accepted.json` not changed.

Status: **publisher checks passed; app validation pending.**

## Existing pins
All 62 rev4 components: same commit, size and SHA-256 match, destination access verified
(`reports/2026-11-27-run-baseline/`). No replacement is proposed.

## New research rows (appended at the end of their category; no existing rank changed)

| Category | Rank | Row | File | Bytes | Estimate (8K, v0.2) |
|---|---|---|---|---|---|
| light_text | 5 | NVIDIA Nemotron 3.5 Bolt E4B Q4_K_M | nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB @0e5d71fc | 6,180,446,208 | 6.1–7.6 GiB |
| heavy_text | 15 | Gemma 4 31B IT Q4_0 | ggml-org/gemma-4-31B-it-GGUF @f39d3801 | 17,992,313,088 | 18.2–19.7 GiB |
| heavy_text | 16 | Qwen3.6-35B-A3B Q4_K_M | ggml-org/Qwen3.6-35B-A3B-GGUF @52f9f9b8 | 20,542,732,576 | 19.4–20.9 GiB |
| heavy_text | 17 | Inkling 2 Mini IQ4_NL | ggml-org/Inkling-2-Mini-GGUF @0bdc5806 | 17,627,940,768 | unknown (unsupported) |

Each file: full commit, exact filename, size and publisher SHA-256 from the Hub model detail,
cross-checked against the tree listing; anonymous download verified at the CDN destination by a
1-byte range request whose total matches the pinned size. No weights downloaded.

Estimates are estimator v0.2 figures (weights + KV + recurrent state; plus logits/compute allowance
and 1 GiB), not measurements. Reproduce with `python3 releases/notes/rev5/provenance/estimate_new_rows.py`.
Configs added to `tools/estimation/configs.tsv`, pinned to the original repositories' commits.

## Text corrections to three rev4 rows
`qwen3.5-122b-a10b_ud_q4_k_xl…`, `gpt-oss-120b_mxfp4…`, `qwen3-14b_q4_k_m…`: `limitations` still said
the revision, size, SHA-256 and HTTP check were unverified, although rev4 pinned and verified them.
Only that clause, `reviewed_utc` and `change_note` changed. Details in `provenance/changes-rev5.json`.

## Ranking proposals (not applied)
- Qwen3.6-35B-A3B could rank above Qwen3.5-122B-A10B for 24 GB GPUs (fits fully on GPU at 8K by estimate). Needs your preference decision.
- Inkling 2 Mini should stay last until its memory is established.

## Candidates seen but not added
Abliterated/uncensored variants of the above (none yet from an identifiable publisher with a pinned licence basis), Ternary-Bonsai-2.5-27B (new 1.58-bit format; llama.cpp support not established), new text-to-image releases (MiniMax-H3-Image, Nemotron-Labs-Image-30B-A3B: no stable-diffusion.cpp recipe found), and ASR releases (no whisper.cpp-format files from the publisher).
