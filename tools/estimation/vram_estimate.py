#!/usr/bin/env python3
"""VRAM estimator v0.2 for llama.cpp text packages (catalogue schema v1).

Produces an ESTIMATE under stated assumptions. It is neither a measurement nor a
guaranteed bound in either direction, and must not be used on its own to reject
a model as incompatible:

    core  = weights + kv_cache(context, cache_type) + recurrent_state
    total = core + logits_buffer(n_vocab, n_ubatch) + overhead_allowance

  Assumptions that can OVERSTATE core: every tensor counted on the GPU (llama.cpp
  may keep token embeddings in system RAM); V cache counted separately even where
  the model shares K and V. Terms that can make total UNDERSTATE: compute buffers
  beyond logits, CUDA context, desktop use (covered only by the allowance).

  weights          exact file bytes, all counted as GPU-resident (assumption)
  kv_cache         per attention layer: (k_dim + v_dim) * tokens_kept * bytes/elem
                   tokens_kept = context for full attention, min(context, window)
                   for sliding-window layers
  recurrent_state  fixed per sequence for linear-attention / SSM layers (f32)
  logits_buffer    n_vocab * n_ubatch * 4 bytes (f32 output for one micro-batch)
  overhead         a stated allowance for CUDA context, other compute buffers and
                   the desktop. It is a parameter, not knowledge.

Architecture comes from one of two inputs:
  --gguf-header FILE   bytes from the start of the .gguf (exact tensor shapes)
  --config FILE        publisher config.json (exact for the declared architecture,
                       assumes the GGUF is a faithful conversion)

Indication per GPU profile (bytes), never a verdict:
  "above"   core estimate is larger than the card: probably needs offload or a
            smaller file; confirm by measurement before treating as incompatible
  "near"    core fits but core + allowance does not: needs measurement
  "below"   core + allowance fits: probably fits; confirm by measurement
"""
import argparse, json, struct, sys

GIB = 1024 ** 3
CACHE_BYTES = {"f16": 2.0, "q8_0": 34 / 32, "q4_0": 18 / 32}   # ggml block sizes
DEFAULT_CONTEXTS = [4096, 8192, 16384, 32768, 65536, 131072]


# ---------------------------------------------------------------- config path
def layout_from_config(cfg):
    """Return dict(layers=[{kind, k_dim, v_dim, window}], vocab, max_ctx, notes, state_bytes)."""
    t = cfg.get("text_config", cfg)
    n = t["num_hidden_layers"]
    heads = t["num_attention_heads"]
    hd = t.get("head_dim") or t["hidden_size"] // heads
    kv = t.get("num_key_value_heads", heads)
    types = t.get("layer_types")
    notes, layers, state = [], [], 0
    if types is None:
        sw = t.get("sliding_window") if t.get("use_sliding_window", False) else None
        types = ["sliding_attention" if sw else "full_attention"] * n
    for lt in types:
        if lt == "full_attention":
            gkv = t.get("num_global_key_value_heads") or kv
            ghd = t.get("global_head_dim") or hd
            if t.get("num_global_key_value_heads") or t.get("global_head_dim"):
                k = gkv * ghd
            else:
                k = kv * hd
            layers.append({"kind": "full", "k_dim": k, "v_dim": k, "window": None})
        elif lt == "sliding_attention":
            layers.append({"kind": "sliding", "k_dim": kv * hd, "v_dim": kv * hd, "window": t["sliding_window"]})
        elif lt == "linear_attention":   # Gated DeltaNet style (Qwen3.5 / 3.8)
            vh, kd, vd = t["linear_num_value_heads"], t["linear_key_head_dim"], t["linear_value_head_dim"]
            kh, ker = t["linear_num_key_heads"], t.get("linear_conv_kernel_dim", 4)
            s = vh * kd * vd * 4 + (2 * kh * kd + vh * vd) * (ker - 1) * 4
            state += s
            layers.append({"kind": "linear", "k_dim": 0, "v_dim": 0, "window": None})
        else:
            raise SystemExit(f"unsupported layer type {lt!r}: add it before estimating")
    if t.get("attention_k_eq_v"):
        notes.append("attention_k_eq_v is set; V cache still counted separately (conservative: llama.cpp storage not confirmed).")
    if any(l["kind"] == "linear" for l in layers):
        notes.append("Linear-attention state assumed f32 (mamba_ssm_dtype / llama.cpp recurrent cache); counted once per sequence.")
    if t.get("num_kv_shared_layers"):
        notes.append("num_kv_shared_layers > 0 not modelled: estimate is an over-count.")
    return {"layers": layers, "vocab": t["vocab_size"], "max_ctx": t.get("max_position_embeddings"),
            "state_bytes": state, "notes": notes, "source": "config.json"}


# ------------------------------------------------------------------ GGUF path
GT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}

class Buf:
    def __init__(s, b): s.b, s.o = b, 0
    def take(s, n):
        if s.o + n > len(s.b): raise EOFError("header bytes exhausted: fetch a larger range")
        r = s.b[s.o:s.o + n]; s.o += n; return r
    def u(s, fmt): v = struct.unpack(fmt, s.take(struct.calcsize(fmt)))[0]; return v
    def str(s): return s.take(s.u("<Q")).decode("utf-8", "replace")
    def val(s, t):
        if t == 8: return s.str()
        if t == 9:
            et, n = s.u("<I"), s.u("<Q")
            if et == 8: return [s.str() for _ in range(n)]
            if et in GT and n > 4096:          # big numeric arrays (token scores etc.): skip
                s.take(struct.calcsize(GT[et]) * n); return f"<array {n}>"
            return [s.val(et) for _ in range(n)]
        return s.u(GT[t])

def read_gguf_header(b):
    r = Buf(b)
    if r.take(4) != b"GGUF": raise SystemExit("not a GGUF file")
    ver = r.u("<I"); nt, nkv = r.u("<Q"), r.u("<Q")
    kv = {}
    for _ in range(nkv):
        k = r.str(); kv[k] = r.val(r.u("<I"))
    tensors = {}
    for _ in range(nt):
        name = r.str(); nd = r.u("<I")
        dims = [r.u("<Q") for _ in range(nd)]; typ = r.u("<I"); off = r.u("<Q")
        tensors[name] = {"dims": dims, "type": typ}
    return ver, kv, tensors

def layout_from_gguf(kv, tensors):
    arch = kv["general.architecture"]
    n = kv[f"{arch}.block_count"]
    notes, layers, state = [], [], 0
    sw = kv.get(f"{arch}.attention.sliding_window")
    pattern = kv.get(f"{arch}.attention.sliding_window_pattern")
    if sw and not isinstance(pattern, list):
        notes.append("sliding_window present but no per-layer pattern in GGUF: all layers counted as full attention (over-count).")
    for i in range(n):
        k = tensors.get(f"blk.{i}.attn_k.weight"); v = tensors.get(f"blk.{i}.attn_v.weight")
        if k is None:
            if any(t.startswith(f"blk.{i}.ssm") for t in tensors):
                layers.append({"kind": "linear", "k_dim": 0, "v_dim": 0, "window": None}); continue
            raise SystemExit(f"layer {i}: no attn_k and no ssm tensors (fused QKV or MLA?) - unsupported, do not estimate")
        kd = k["dims"][1]; vd = v["dims"][1] if v else kd
        if v is None: notes.append(f"layer {i}: no attn_v (K=V); V cache counted anyway (conservative).")
        sliding = bool(sw) and isinstance(pattern, list) and bool(pattern[i])
        layers.append({"kind": "sliding" if sliding else "full", "k_dim": kd, "v_dim": vd, "window": sw if sliding else None})
    if any(l["kind"] == "linear" for l in layers):
        d_state = kv.get(f"{arch}.ssm.state_size"); d_inner = kv.get(f"{arch}.ssm.inner_size")
        if d_state and d_inner:
            per = d_state * d_inner * 4
            state = per * sum(l["kind"] == "linear" for l in layers)
            notes.append("Recurrent state approximated as ssm.state_size * ssm.inner_size * 4 bytes per linear layer.")
        else:
            notes.append("Recurrent layers found but ssm sizes missing: state NOT counted (under-count).")
    # dedupe repeated per-layer notes
    seen, uniq = set(), []
    for x in notes:
        key = x.split(":")[1] if x.startswith("layer ") else x
        if key not in seen: seen.add(key); uniq.append(x if not x.startswith("layer ") else "Some layers have no attn_v (K=V); V cache counted anyway (conservative).")
    vocab = len(kv["tokenizer.ggml.tokens"]) if isinstance(kv.get("tokenizer.ggml.tokens"), list) else kv.get(f"{arch}.vocab_size")
    return {"layers": layers, "vocab": vocab, "max_ctx": kv.get(f"{arch}.context_length"),
            "state_bytes": state, "notes": uniq, "source": "gguf-header"}


# ------------------------------------------------------------------ estimate
def kv_bytes(layout, ctx, cache):
    e = CACHE_BYTES[cache]
    tot = 0
    for l in layout["layers"]:
        if l["kind"] == "linear": continue
        toks = min(ctx, l["window"]) if l["window"] else ctx
        tot += (l["k_dim"] + l["v_dim"]) * toks * e
    return int(tot)

def estimate(layout, weights, profiles, contexts, caches, ubatch, overhead):
    logits = layout["vocab"] * ubatch * 4
    rows = []
    for cache in caches:
        for c in contexts:
            if layout["max_ctx"] and c > layout["max_ctx"]: continue
            kvb = kv_bytes(layout, c, cache)
            core = weights + kvb + layout["state_bytes"]
            total = core + logits + overhead
            verdicts = {}
            for p in profiles:
                g = p["gpuBytes"]
                verdicts[p["id"]] = "above" if core > g else ("below" if total <= g else "near")
            rows.append({"cache": cache, "context": c, "kvBytes": kvb, "coreBytes": core,
                         "totalBytes": total, "verdicts": verdicts})
    return {"weightsBytes": weights, "stateBytes": layout["state_bytes"], "logitsBytes": logits,
            "overheadBytes": overhead, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--config"); g.add_argument("--gguf-header")
    ap.add_argument("--weights-bytes", type=int, required=True, help="exact GGUF file size")
    ap.add_argument("--profiles", required=True, help="catalogue JSON to take profiles from")
    ap.add_argument("--contexts", default=",".join(map(str, DEFAULT_CONTEXTS)))
    ap.add_argument("--caches", default="f16,q8_0")
    ap.add_argument("--ubatch", type=int, default=512)
    ap.add_argument("--overhead-gib", type=float, default=1.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.config:
        layout = layout_from_config(json.load(open(a.config)))
    else:
        _, kv, tens = read_gguf_header(open(a.gguf_header, "rb").read())
        layout = layout_from_gguf(kv, tens)
    profiles = json.load(open(a.profiles))["profiles"]
    res = estimate(layout, a.weights_bytes, profiles, [int(x) for x in a.contexts.split(",")],
                   a.caches.split(","), a.ubatch, int(a.overhead_gib * GIB))
    res["layout"] = {"source": layout["source"], "maxContext": layout["max_ctx"], "vocab": layout["vocab"],
                     "full": sum(l["kind"] == "full" for l in layout["layers"]),
                     "sliding": sum(l["kind"] == "sliding" for l in layout["layers"]),
                     "linear": sum(l["kind"] == "linear" for l in layout["layers"]), "notes": layout["notes"]}
    if a.json:
        print(json.dumps(res, indent=1)); return
    L = res["layout"]
    print(f"layout from {L['source']}: {L['full']} full, {L['sliding']} sliding, {L['linear']} linear layers; "
          f"vocab {L['vocab']}; max ctx {L['maxContext']}")
    for n in L["notes"]: print("  note:", n)
    print(f"weights {res['weightsBytes']/GIB:.2f} GiB | state {res['stateBytes']/GIB:.3f} GiB | "
          f"logits {res['logitsBytes']/GIB:.2f} GiB | overhead allowance {res['overheadBytes']/GIB:.2f} GiB")
    ids = [p["id"].replace("gpu-", "").replace("-gib", "") for p in profiles]
    print(f"{'cache':6}{'ctx':>8}{'KV GiB':>9}{'total GiB':>11}  " + " ".join(f"{i:>7}" for i in ids))
    sym = {"above": "^", "near": "~", "below": "v"}
    for r in res["rows"]:
        print(f"{r['cache']:6}{r['context']:>8}{r['kvBytes']/GIB:>9.2f}{r['totalBytes']/GIB:>11.2f}  " +
              " ".join(f"{sym[r['verdicts'][p['id']]]:>7}" for p in profiles))

if __name__ == "__main__":
    main()
