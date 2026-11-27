"""Reproduce the rev5 new-row estimates with estimator v0.2 and the pinned configs in tools/estimation/configs."""
import json, sys
sys.path.insert(0, "tools/estimation"); from vram_estimate import layout_from_config, kv_bytes
G = 1024**3
for eid, cfg, size in [("nemotron-3.5-bolt-e4b", "nvidia_NVIDIA-Nemotron-3.5-Bolt-E4B-BF16", 6180446208),
                       ("gemma-4-31b-it", "google_gemma-4-31B-it", 17992313088),
                       ("qwen3.6-35b-a3b", "Qwen_Qwen3.6-35B-A3B", 20542732576)]:
    L = layout_from_config(json.load(open(f"tools/estimation/configs/{cfg}.json")))
    kv = kv_bytes(L, 8192, "f16"); core = size + kv + L["state_bytes"]; total = core + L["vocab"] * 512 * 4 + G
    print(f"{eid}: low(core) {core/G:.3f} GiB, high(total) {total/G:.3f} GiB, kv {kv/G:.3f}, state {L['state_bytes']/G:.3f}; {'; '.join(L['notes'])}")
