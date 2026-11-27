"""Build rev5 from accepted rev4: append four research rows, correct three stale sentences. rev4 is not modified."""
import csv, io, json, hashlib, sys
SRC = "releases/ai-model-catalogue-v6-20261127-rev4.csv"
DST = "releases/ai-model-catalogue-v6-20261127-rev5.csv"
P = "releases/notes/rev5/provenance/"
NOW = sys.argv[1]  # reviewed_utc, e.g. 2026-11-27T12:00:00Z
raw = open(SRC, newline="").read()
rd = csv.DictReader(io.StringIO(raw)); cols = rd.fieldnames; rows = list(rd)
changes = []

# 1. Stale text: these rows' files are pinned and verified (reports/2026-11-27-run-baseline), but their
#    limitations still say pinning/HTTP checks are unverified. Replace that clause only.
PINNED = "files pinned to an immutable commit with exact byte size and publisher SHA-256; anonymous download verified by bounded request (2026-11-27)"
for eid_prefix, old in [("qwen3.5-122b-a10b_ud_q4_k_xl", "immutable revision, exact byte sizes, SHA-256, and live HTTP check remain unverified"),
                        ("gpt-oss-120b_mxfp4", "exact byte size, SHA-256, and live HTTP HEAD check remain unverified"),
                        ("qwen3-14b_q4_k_m", "immutable revision, exact byte size, SHA-256, and live HTTP HEAD check remain unverified")]:
    r = next(x for x in rows if x["entry_id"].startswith(eid_prefix))
    assert old in r["limitations"], eid_prefix
    r["limitations"] = r["limitations"].replace(old, PINNED)
    r["reviewed_utc"] = NOW
    r["change_note"] = "rev5: corrected stale limitations text (files were already pinned and verified in rev4); no file, memory or rank change."
    changes.append({"entry_id": r["entry_id"], "change": "limitations text corrected", "old": old, "new": PINNED})

def files(key):
    return json.load(open(P + key + ".out.json"))["required_files_json"]

def nextrank(cat):
    return str(max(int(x["category_preference_order"]) for x in rows if x["category"] == cat) + 1)

EST = "VRAM estimator v0.2 (tools/estimation/vram_estimate.py), 8192 tokens, f16 KV cache, full GPU offload, text only (no mmproj). Low = weights + KV + recurrent state; high = low + logits/compute allowance + 1 GiB. An estimate, not a measured or lower-bound figure."
NOBUDGET = "No free-VRAM or host-RAM budget is set: the capacity policy is pending, so this row is not browse/fit eligible."
new = [
  dict(key="bolt", entry_id="nemotron-3.5-bolt-e4b_q4_k_m_light_text_8k_llamacpp_win_cuda", model_id="nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-BF16",
       variant_id="nemotron-3.5-bolt-e4b_q4_k_m_gguf", model_name="NVIDIA Nemotron 3.5 Bolt E4B (Q4_K_M, 8K Context)", publisher="NVIDIA",
       category="light_text", total="8.0", active="", quant="Q4_K_M", arch="gemma4", low="6.1", high="7.6",
       repo="nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB", main="Nemotron-3.5-Bolt-E4B-Q4_K_M.gguf",
       lic="LicenseRef-OpenMDW-1.1", lic_url="https://openmdw.ai/license/1-1/",
       assume="Over-count: num_kv_shared_layers not modelled. Weights 6,180,446,208 bytes (5.76 GiB). The '4GB' in the repository name is not used as a memory figure.",
       desc="NVIDIA post-train of Gemma-4-E4B-it for fast local assistants and tool use, published by NVIDIA as a single Q4_K_M GGUF.",
       best="Small-GPU chat, tool use and voice/device assistants where low latency matters.",
       lim="Research row: llama.cpp build compatibility and quality not tested here. Licence is OpenMDW-1.1 (not Apache); review terms.",
       srcs="https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB https://huggingface.co/google/gemma-4-E4B-it"),
  dict(key="gemma31", entry_id="gemma-4-31b-it_q4_0_heavy_text_8k_llamacpp_win_cuda", model_id="google/gemma-4-31B-it",
       variant_id="gemma-4-31b-it_q4_0_gguf", model_name="Gemma 4 31B IT (Q4_0, 8K Context)", publisher="Google",
       category="heavy_text", total="31.3", active="31.3", quant="Q4_0", arch="gemma4", low="18.2", high="19.7",
       repo="ggml-org/gemma-4-31B-it-GGUF", main="gemma-4-31B-it-Q4_0.gguf",
       lic="Apache-2.0", lic_url="https://huggingface.co/google/gemma-4-31B-it",
       assume="attention_k_eq_v set; V cache counted separately (conservative). Weights 17,992,313,088 bytes (16.76 GiB).",
       desc="Largest dense Gemma 4 instruction model, Q4_0 GGUF from ggml-org.",
       best="24 GB-class GPUs wanting a dense model stronger than Gemma 4 26B-A4B.",
       lim="Research row: dense 31B decodes slower than the MoE options; not tested here.",
       srcs="https://huggingface.co/google/gemma-4-31B-it https://huggingface.co/ggml-org/gemma-4-31B-it-GGUF"),
  dict(key="qwen36", entry_id="qwen3.6-35b-a3b_q4_k_m_heavy_text_8k_llamacpp_win_cuda", model_id="Qwen/Qwen3.6-35B-A3B",
       variant_id="qwen3.6-35b-a3b_q4_k_m_gguf", model_name="Qwen3.6-35B-A3B (Q4_K_M, 8K Context)", publisher="Qwen",
       category="heavy_text", total="36.0", active="3.0", quant="Q4_K_M", arch="qwen35moe", low="19.4", high="20.9",
       repo="ggml-org/Qwen3.6-35B-A3B-GGUF", main="Qwen3.6-35B-A3B-Q4_K_M.gguf",
       lic="Apache-2.0", lic_url="https://huggingface.co/Qwen/Qwen3.6-35B-A3B/blob/main/LICENSE",
       assume="Hybrid Gated DeltaNet / gated attention (30 linear + 10 full layers); recurrent state f32. Weights 20,542,732,576 bytes (19.13 GiB). MoE experts fully on GPU (no CPU offload modelled).",
       desc="Qwen 3.6 MoE (35B total, 3B active, 256 experts) with hybrid linear attention, Q4_K_M GGUF from ggml-org.",
       best="24 GB-class GPUs wanting fast MoE decoding; long-context capable (262K native).",
       lim="Research row: not tested here; CPU expert offload for smaller GPUs not estimated.",
       srcs="https://huggingface.co/Qwen/Qwen3.6-35B-A3B https://huggingface.co/ggml-org/Qwen3.6-35B-A3B-GGUF"),
  dict(key="inkling", entry_id="inkling-2-mini_iq4_nl_heavy_text_llamacpp_win_cuda", model_id="thinkingmachines/Inkling-2-Mini",
       variant_id="inkling-2-mini_iq4_nl_gguf", model_name="Inkling 2 Mini (IQ4_NL)", publisher="Thinking Machines Lab",
       category="heavy_text", total="26.4", active="3.4", quant="IQ4_NL", arch="inkling2_loop", low="", high="",
       repo="ggml-org/Inkling-2-Mini-GGUF", main="Inkling-2-Mini-IQ4_NL.gguf",
       lic="Apache-2.0", lic_url="https://huggingface.co/thinkingmachines/Inkling-2-Mini",
       assume="", desc="Looped MoE (128 experts, 8 active; three passes, 5.4B effective active) released 2026-11-20; IQ4_NL GGUF from ggml-org.",
       best="Unknown until memory is established; candidate for 24 GB-class GPUs by file size alone (17.6 GB).",
       lim="Memory unknown: the looped architecture (inkling2_loop) is not supported by estimator v0.2. llama.cpp minimum build not established. The GGUF repository states no licence; licence taken from the original model (Apache-2.0).",
       srcs="https://huggingface.co/thinkingmachines/Inkling-2-Mini https://huggingface.co/ggml-org/Inkling-2-Mini-GGUF"),
]
template = next(x for x in rows if x["entry_id"].startswith("gemma-4-26b-a4b-it_q4_0"))
for n in new:
    r = {c: "" for c in cols}
    for c in ("capabilities","file_format","runtime_name","backend","operating_systems","memory_type","gpu_count","offload_mode","max_output_tokens","batch_size","schema_version","access_requirements"):
        r[c] = template[c]
    known = bool(n["low"])
    fj = files(n["key"]); f = fj[0]
    assert f["filename"] == n["main"] and len(fj) == 1
    r.update(entry_id=n["entry_id"], model_id=n["model_id"], variant_id=n["variant_id"], model_name=n["model_name"], publisher=n["publisher"],
             category=n["category"], parameter_count_billion_total=n["total"], parameter_count_billion_active=n["active"], quantization=n["quant"],
             runtime_version_or_commit="", estimated_peak_vram_gib_low=n["low"], estimated_peak_vram_gib_high=n["high"],
             recommended_system_ram_gib="", memory_scope="complete_pipeline" if known else "unknown",
             memory_evidence_type="derived_estimate" if known else "unknown",
             memory_assumptions=(EST + " " + n["assume"] + " " + NOBUDGET) if known else "Not estimated: architecture unsupported by estimator v0.2. " + NOBUDGET,
             context_tokens="8192" if known else "", model_page_url="https://huggingface.co/" + n["model_id"],
             variant_repo_url="https://huggingface.co/" + n["repo"], revision=f["revision"], main_weight_filename=n["main"],
             additional_required_files="", runtime_support_source_url="https://huggingface.co/" + n["repo"],
             recommendation_priority="", recommendation_reason="New research row (rev5 update run); appended at the end of the category, ranking unchanged pending review.",
             short_description=n["desc"], best_for=n["best"], limitations=n["lim"], license_id=n["lic"], license_url=n["lic_url"],
             checked_date=NOW[:10], memory_source_urls="https://huggingface.co/" + n["model_id"] + "/blob/" + "" if False else ("https://huggingface.co/" + n["model_id"] if known else ""),
             other_source_urls=n["srcs"], row_status="research", architecture=n["arch"], package_completeness="complete",
             reviewed_utc=NOW, change_note="rev5: new research row; 1 file pinned (commit, exact filename, size, publisher SHA-256; destination access verified).",
             category_preference_order=nextrank(n["category"]),
             required_files_json=json.dumps(fj, separators=(",", ":")))
    rows.append(r)
    changes.append({"entry_id": r["entry_id"], "change": "new research row", "rank": r["category_preference_order"], "category": r["category"]})
# keep categories grouped in original order: insert each new row after the last row of its category
order = []
for c in dict.fromkeys(x["category"] for x in rows):
    order += [x for x in rows if x["category"] == c]
out = io.StringIO(); w = csv.DictWriter(out, cols, quoting=csv.QUOTE_ALL, lineterminator="\n"); w.writeheader(); w.writerows(order)
data = out.getvalue().encode("ascii")
open(DST, "wb").write(data)
json.dump(changes, open(P + "changes-rev5.json", "w"), indent=1)
print(DST, len(data), hashlib.sha256(data).hexdigest())
