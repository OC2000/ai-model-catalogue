# Memory estimation report: catalogue v6 rev4

**Catalogue:** `ai-model-catalogue-v6-20261127-rev4.csv` (SHA-256 `b796f839…dd22`)
**Purpose:** an independent, reproducible comparison against the CSV's published memory budgets. **No budget or estimate column in the CSV was changed.** These figures are estimates, not measurements, and they establish neither app support nor fit on any device.

## 1. Reproduce

```
cd estimation
python estimate_rev4.py ../ai-model-catalogue-v6-20261127-rev4.csv           # offline, bundled configs
python estimate_rev4.py ../ai-model-catalogue-v6-20261127-rev4.csv --fetch   # re-download pinned configs first
```

The script refuses to run if any config's SHA-256 differs from `configs.tsv`. It writes `estimates-rev4.json`. In this run, both the offline and the re-fetch passes gave identical output, with SHA-256 `0e364032…bbc6`.

| Input | Value |
|---|---|
| Estimator | `vram_estimate.py` v0.2, SHA-256 `ad08200aa1081e4752c05c87e54ebe20dba03e9e75b335285da0bd637041b84e` (the same code used in the JSON-track catalogue) |
| File sizes | exact `size_bytes` from rev4 `required_files_json` (publisher metadata, cross-checked) |
| Model architecture | publisher `config.json` at a pinned commit (§4) |
| KV cache type | f16 · one sequence · logits buffer n_vocab × 512 × 4 bytes · allowance 1 GiB |

## 2. Method and assumptions

**Text rows (llama.cpp, `offload_mode = full_gpu`):**

```
core  = sum of required file bytes                        (all tensors counted on the GPU)
      + KV cache  = Σ attention layers (k_dim + v_dim) × tokens kept × 2 bytes
                    tokens kept = context_tokens (full attention) or min(context, window) (sliding)
      + linear-attention state (f32, once per sequence)
total = core + logits buffer + 1 GiB allowance (CUDA context, other compute buffers, desktop)
```

Each comparison uses the row's own `context_tokens` and `required_free_vram_gib`:

| Result | Condition |
|---|---|
| budget covers estimate | budget ≥ total |
| budget within estimate range | core ≤ budget < total. Review: the budget may be tight. |
| budget below core estimate | budget < core. Review: the budget may be insufficient. |

**Limits of the method:**
- **It can overstate** real use. Token embeddings may stay in system RAM, and for Gemma, V is counted separately even though K and V are shared.
- **It can understate** real use. Compute buffers beyond logits, prompt-processing batches above 512, and other applications aren't modelled.
- **Cache type and flash attention:** the CSV's own figures may assume flash attention or a different cache type. This method uses f16 throughout.
- **Out of scope:** MLA attention (DeepSeek/Kimi style), CPU expert offload, and unified-memory rows. These are reported as not estimated, rather than guessed.

**Image and transcription rows:** these are weights-only floor checks using exact component bytes. Under `text_encoders_cpu`, the text encoders are counted as host-resident and everything else as GPU-resident. Activations, which grow with resolution, aren't modelled, so the check can only show that a budget covers the weights.

## 3. Results

### Text (llama.cpp)

| entry_id | context | file bytes | KV GiB | state GiB | core GiB | total GiB | CSV VRAM budget GiB | result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `qwen3.5-9b_ud_q4_k_xl_light_text_llamacpp_win_cuda` | 16384 | 5,966,095,584 | 0.50 | 0.049 | 6.11 | 7.58 | 8.5 | budget covers estimate |
| `qwen3-8b_q4_k_m_light_text_llamacpp_win_cuda` | 8192 | 5,027,783,488 | 1.12 | 0.000 | 5.81 | 7.10 | 7.7 | budget covers estimate |
| `qwen3-4b_q4_k_m_light_text_llamacpp_win_cuda` | 8192 | 2,497,280,256 | 1.12 | 0.000 | 3.45 | 4.74 | 4.5 | **budget within estimate range** |
| `qwen2.5-7b-instruct_q4_k_m_light_text_llamacpp_win_cuda` | 8192 | 4,683,073,632 | 0.44 | 0.000 | 4.80 | 6.09 | 7.5 | budget covers estimate |
| `qwen3.5-122b-a10b_ud_q4_k_xl_heavy_text_32k_llamacpp_win_cuda` | 32768 | 77,029,996,032 | 0.75 | 0.146 | 72.64 | 74.11 | 86.0 | budget covers estimate |
| `gpt-oss-120b_mxfp4_heavy_text_32k_llamacpp_win_cuda` | 32768 | 63,387,346,208 | 1.13 | 0.000 | 60.16 | 61.55 | 72.0 | budget covers estimate |
| `qwen3-32b_q4_k_m_heavy_text_32k_llamacpp_win_cuda` | 32768 | 19,762,149,024 | 8.00 | 0.000 | 26.40 | 27.69 | 29.5 | budget covers estimate |
| `qwen3.8-27b_ud_q4_k_xl_heavy_text_8k_llamacpp_win_cuda` | 8192 | 17,659,407,264 | 0.50 | 0.146 | 17.09 | 18.57 | 20.5 | budget covers estimate |
| `qwen3-30b-a3b_q4_k_m_heavy_text_8k_llamacpp_win_cuda` | 8192 | 18,556,685,824 | 0.75 | 0.000 | 18.03 | 19.32 | 22.5 | budget covers estimate |
| `gpt-oss-20b_mxfp4_heavy_text_128k_llamacpp_win_cuda` | 131072 | 12,109,566,624 | 3.00 | 0.000 | 14.28 | 15.66 | 23.0 | budget covers estimate |
| `qwen3-32b_q4_k_m_heavy_text_8k_llamacpp_win_cuda` | 8192 | 19,762,149,024 | 2.00 | 0.000 | 20.40 | 21.69 | 23.5 | budget covers estimate |
| `gpt-oss-20b_mxfp4_heavy_text_8k_llamacpp_win_cuda` | 8192 | 12,109,566,624 | 0.19 | 0.000 | 11.47 | 12.85 | 15.8 | budget covers estimate |
| `gemma-4-26b-a4b-it_q4_0_heavy_text_8k_llamacpp_win_cuda` | 8192 | 14,618,145,824 | 0.35 | 0.000 | 13.97 | 15.47 | 15.8 | budget covers estimate |
| `qwen3-14b_q4_k_m_heavy_text_16k_llamacpp_win_cuda` | 16384 | 9,001,752,960 | 2.50 | 0.000 | 10.88 | 12.17 | 12.0 | **budget within estimate range** |
| `gemma-4-12b-it_q4_k_m_heavy_text_32k_llamacpp_win_cuda` | 32768 | 7,662,533,088 | 0.81 | 0.000 | 7.95 | 9.45 | 12.5 | budget covers estimate |

**Summary:** no CSV budget is below the independent core estimate. The two flagged budgets, Qwen3-4B (4.5 GiB) and Qwen3-14B (12.0 GiB), sit 0.24 and 0.17 GiB under the indicative total. They are within this method's uncertainty, but there's little margin, so review is recommended. Following the conservative-budget rule, the CSV budgets are kept and none was lowered to match these estimates. Where the CSV is larger (for example gpt-oss-20b at 128K: 23.0 vs 15.66 GiB), the CSV figure stands.

### Image and transcription (weights-only floor)

| entry_id | offload_mode | GPU-resident weights, bytes (GiB) | host-resident weights, bytes (GiB) | VRAM budget | host RAM budget | result |
|---|---|---:|---:|---:|---:|---|
| `z-image-turbo_q4_k_light_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 4,199,554,692 (3.91) | 2,497,280,256 (2.33) | 8.0 | 12.0 | within budget |
| `z-image-turbo_q3_k_light_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 3,478,863,492 (3.24) | 2,497,280,256 (2.33) | 4.8 | 12.0 | within budget |
| `flux-2-klein-4b_q4_k_m_light_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 2,940,522,396 (2.74) | 2,497,280,256 (2.33) | 8.5 | 12.0 | within budget |
| `flux-3-image-klein_unresolved_light_image_generation_sdcpp_win_cuda` | (unset) | 4,266,156,284 (3.97) | 0 | – | – | no budget to compare |
| `sdxl-turbo_fp16_light_image_generation_sdcpp_win_cuda` | none | 6,938,081,905 (6.46) | 0 | 9.5 | 12.0 | within budget |
| `qwen-image-2.1_q4_k_heavy_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 4,873,003,472 (4.54) | 5,148,699,488 (4.80) | 16.5 | 18.0 | within budget |
| `flux-2-klein-9b_q4_k_m_heavy_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 6,010,111,612 (5.60) | 5,027,783,488 (4.68) | 12.5 | 14.0 | within budget |
| `qwen-image-2.1-turbo_unresolved_heavy_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 4,581,865,712 (4.27) | 5,148,699,488 (4.80) | 16.0 | 18.0 | within budget |
| `krea-2-raw_q4_k_m_heavy_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 7,259,460,832 (6.76) | 0 (encoders not yet listed) | 15.5 | 14.0 | within budget (package partial) |
| `flux-1-dev_q4_k_s_heavy_image_generation_sdcpp_win_cuda` | text_encoders_cpu | 7,141,293,028 (6.65) | 10,033,985,176 (9.34) | 14.5 | 16.0 | within budget |
| `whisper-large-v3-turbo_q5_0_transcription_whispercpp_win_cuda` | full_gpu | 574,041,195 (0.53) | 0 | 2.5 | 4.0 | within budget |
| `whisper-base-en_f16_transcription_whispercpp_win_cpu` | none | 147,964,211 (0.14) | 0 | – | 2.0 | no VRAM budget |

Every image and Whisper VRAM budget covers its GPU-resident weights. Activation memory isn't checked, so that is the most this method can say.

### Not estimated

| entry_id | reason |
|---|---|
| `kimi-k2-instruct_ud_q2_k_xl_heavy_text_32k_llamacpp_win_hybrid` | MLA attention and CPU expert offload are outside the estimator's scope. The CSV's publisher-guidance budget is kept. |
| `kimi-k2-instruct_ud_q2_k_xl_heavy_text_32k_llamacpp_macos_unified` | MLA attention and unified memory are outside the estimator's scope. |
| `flux-2-dev_fp8_…`, `moss-image-sft_…`, `qwen3.8-27b_unresolved_…` | No resolved files. |

## 4. Sources: pinned configs (`estimation/configs/`, SHA-256 checked on every run)

| key | repository | commit | SHA-256 |
|---|---|---|---|
| Qwen_Qwen3.5-9B | Qwen/Qwen3.5-9B | c202236235762e1c871ad0ccb60c8ee5ba337b9a | d0883072e01861ed0b2d47be3c16c36a8e81c224c7ffaa310c6558fb3f932b05 |
| Qwen_Qwen3-8B | Qwen/Qwen3-8B | b968826d9c46dd6066d109eabc6255188de91218 | f7c4eadfbbf522470667b797a3c89be2524832d2d599797248dc304fff447c30 |
| Qwen_Qwen3-4B | Qwen/Qwen3-4B | 1cfa9a7208912126459214e8b04321603b3df60c | 8ba006f74fecfaaeb392872a60f4a480e7ec9860153d2e1b769ec81f9a147f8a |
| Qwen_Qwen2.5-7B-Instruct | Qwen/Qwen2.5-7B-Instruct | a09a35458c702b33eeacc393d103063234e8bc28 | 7463bb0ea78315365e6c6b74de4e73bbcc8359dfb0c5a737584e077d42c0b03c |
| Qwen_Qwen3.5-122B-A10B | Qwen/Qwen3.5-122B-A10B | dc4d348443bc740c68e2d77492492c11606384d5 | af07d0423658865afb52bd0d6fd3c2cc45d988425b76193467fd19129655cecd |
| openai_gpt-oss-120b | openai/gpt-oss-120b | b5c939de8f754692c1647ca79fbf85e8c1e70f8a | 933aeb666a3fd851133ddd7686414f369bc564c4185fb5704416550879f10566 |
| Qwen_Qwen3-32B | Qwen/Qwen3-32B | 9216db5781bf21249d130ec9da846c4624c16137 | 97e295b63283935788fac5e4f8860862a56d4089538cafc93f0431f2ebe483bb |
| Qwen_Qwen3.8-27B | Qwen/Qwen3.8-27B | 37561816e66b5b9153b1b64c10968c18c1e6f4a0 | 191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab |
| Qwen_Qwen3-30B-A3B | Qwen/Qwen3-30B-A3B | ad44e777bcd18fa416d9da3bd8f70d33ebb85d39 | 2850ddb3bf7aecad20b611e2d44f3077fc8193f4827c93beddd4c02ad63c2297 |
| openai_gpt-oss-20b | openai/gpt-oss-20b | 6cee5e81ee83917806bbde320786a8fb61efebee | 3a2a26ded679375b7928ddeca59764df7cea83220c1961035f6d6e232659e9ce |
| google_gemma-4-26B-A4B-it | google/gemma-4-26B-A4B-it | 4d7ae4984b7db7de8f8457170b3f1a419ee76d52 | ed0c1eb3633de771906e9ba004a44cc5635bcc06ee2062077c3d2e88a50707d3 |
| Qwen_Qwen3-14B | Qwen/Qwen3-14B | 40c069824f4251a91eefaf281ebe4c544efd3e18 | e73c3664ca09b10a673fef0c22e8a6b456201d49bd4713c9691f775720e8857a |
| google_gemma-4-12B-it | google/gemma-4-12B-it | 43c9d014b231474fa7212dbb48a762566c2b255d | 478c46e8d2c52d5c2d85bf67e3b3e8c90e7c9d91086cee27e3c267907e936bd9 |
| moonshotai_Kimi-K2-Instruct | moonshotai/Kimi-K2-Instruct | fd1984e2b7a3350dbf7305fe73a4ede25c14de50 | 8c13ae1049df55f29b3bdcae69a562433f243ff70dac251d819ecad8dbdf7439 |

The configs were read through the Hugging Face Hub API (https://huggingface.co/docs/hub/api). File sizes come from each row's pinned `required_files_json` entries; see `provenance/resolved-rev4.json` for the per-file evidence.
