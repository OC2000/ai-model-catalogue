#!/usr/bin/env python3
"""Independent, reproducible memory estimates for a v6 catalogue CSV (comparison only).

usage: estimate_csv.py catalogue.csv [--fetch]
Inputs: configs.tsv (key, repo, pinned commit, SHA-256) + configs/<key>.json, and the exact
file sizes in each row's required_files_json. Writes estimates.json and prints a table.
It never edits the catalogue: CSV budgets stay as published.

llama.cpp rows (config path, vram_estimate.py v0.2):
  core  = sum(required file bytes) + KV cache at the row's context_tokens (f16)
          + linear-attention state            (all tensors counted GPU-resident)
  total = core + n_vocab x 512 x 4 (logits) + 1 GiB allowance
  Comparison against required_free_vram_gib:
    budget >= total            -> "budget covers estimate"
    core <= budget < total     -> "budget within estimate range"
    budget < core              -> "budget below core estimate: review"
  Unsupported: MLA attention (kv_lora_rank), CPU expert offload, unified memory rows.
stable-diffusion.cpp / whisper.cpp rows: exact component bytes split by offload_mode
  (text_encoders_cpu -> text encoders counted in host RAM, the rest on the GPU).
  Activations are not modelled, so this is a weights-only floor check.
"""
import csv, hashlib, json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
from vram_estimate import layout_from_config, kv_bytes
GIB = 1024 ** 3
cfg = {}
for line in open(os.path.join(here, "configs.tsv")):
    k, repo, sha, h = line.rstrip("\n").split("\t")
    path = os.path.join(here, "configs", f"{k}.json")
    if "--fetch" in sys.argv:
        subprocess.run(["curl", "-sSL", "--fail", "-o", path, f"https://huggingface.co/{repo}/resolve/{sha}/config.json"], check=True)
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if got != h: sys.exit(f"config {k}: SHA-256 {got} != {h}")
    cfg[repo] = (k, sha, h)
ALIAS = {"Qwen/Qwen3-14B-GGUF": "Qwen/Qwen3-14B"}
rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
out = []
for r in rows:
    files = json.loads(r["required_files_json"] or "[]")
    e = {"entry_id": r["entry_id"], "runtime": r["runtime_name"], "context": r["context_tokens"], "offload": r["offload_mode"],
         "budgetVramGiB": r["required_free_vram_gib"], "budgetHostRamGiB": r["required_free_host_ram_gib"],
         "budgetUnifiedGiB": r["required_free_unified_memory_gib"], "fileBytes": sum(f["size_bytes"] or 0 for f in files)}
    if not files:
        e["result"] = "not estimated: no resolved files"; out.append(e); continue
    if r["runtime_name"] == "llama.cpp":
        repo = ALIAS.get(r["model_page_url"].replace("https://huggingface.co/", ""), r["model_page_url"].replace("https://huggingface.co/", ""))
        if repo not in cfg: e["result"] = f"not estimated: no pinned config for {repo}"; out.append(e); continue
        k, sha, h = cfg[repo]; c = json.load(open(os.path.join(here, "configs", f"{k}.json")))
        t = c.get("text_config", c)
        e.update({"config": f"configs/{k}.json", "configRepo": repo, "configRevision": sha, "configSha256": h})
        if t.get("kv_lora_rank") is not None:
            e["result"] = "not estimated: MLA attention (kv_lora_rank) unsupported by vram_estimate.py v0.2"; out.append(e); continue
        if r["offload_mode"] not in ("full_gpu",) or not r["required_free_vram_gib"]:
            e["result"] = f"not estimated: offload_mode {r['offload_mode'] or 'unset'} / no dedicated-VRAM budget (estimator models all-GPU only)"; out.append(e); continue
        layout = layout_from_config(c)
        ctx = int(r["context_tokens"])
        kv = kv_bytes(layout, ctx, "f16"); core = e["fileBytes"] + kv + layout["state_bytes"]
        total = core + layout["vocab"] * 512 * 4 + GIB
        b = float(r["required_free_vram_gib"]) * GIB
        e.update({"kvBytes": kv, "stateBytes": layout["state_bytes"], "coreBytes": core, "totalBytes": total,
                  "coreGiB": round(core / GIB, 2), "totalGiB": round(total / GIB, 2), "notes": layout["notes"],
                  "result": "budget covers estimate" if b >= total else ("budget within estimate range" if b >= core else "budget below core estimate: review")})
    else:
        cpu_slots = {"text_encoder", "text_encoder_2"} if r["offload_mode"] == "text_encoders_cpu" else set()
        gpu = sum(f["size_bytes"] for f in files if f["slot"] not in cpu_slots); cpu = sum(f["size_bytes"] for f in files if f["slot"] in cpu_slots)
        e.update({"gpuResidentWeightBytes": gpu, "hostResidentWeightBytes": cpu, "gpuWeightsGiB": round(gpu / GIB, 2), "hostWeightsGiB": round(cpu / GIB, 2),
                  "bySlot": {f["slot"]: f["size_bytes"] for f in files}})
        if not r["required_free_vram_gib"]:
            e["result"] = "weights only; no dedicated-VRAM budget to compare"
        else:
            b = float(r["required_free_vram_gib"]) * GIB
            e["result"] = ("weights-only floor within budget (activations not modelled)" if gpu <= b else "GPU-resident weights exceed budget: review")
    out.append(e)
json.dump(out, open(os.path.join(here, "estimates.json"), "w"), indent=1)
for e in out:
    est = (f"core {e['coreGiB']:6.2f} / total {e['totalGiB']:6.2f}" if "coreGiB" in e else
           (f"GPU weights {e['gpuWeightsGiB']:6.2f} / host {e['hostWeightsGiB']:5.2f}" if "gpuWeightsGiB" in e else "-"))
    print(f"{e['entry_id'][:44]:44} budget {e['budgetVramGiB'] or '-':>5} | {est:36} | {e['result']}")
