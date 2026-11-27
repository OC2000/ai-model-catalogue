#!/usr/bin/env python3
"""Publisher pre-check for the v6 model-catalogue CSV.

THIS IS NOT THE APP VALIDATOR. The authoritative implementation is
AIConnect.Core.CsvModelCatalogue.Parse/ParseCore (CsvModelCatalogue.cs). Part A below
mirrors those rules as closely as practical so failures surface before review; any
disagreement is resolved in favour of the app. Part B adds publisher-only checks that
the app parser does not enforce (pins, sizes, hashes, URL pinning, access vocabulary).

usage: precheck_csv.py catalogue.csv [--json report.json]
exit 0 = both parts pass, 1 = failure, 2 = usage
"""
import csv, io, json, math, re, sys

HEADER = ("entry_id,model_id,variant_id,model_name,publisher,category,capabilities,parameter_count_billion_total,"
  "parameter_count_billion_active,quantization,file_format,runtime_name,runtime_version_or_commit,backend,operating_systems,"
  "memory_type,gpu_count,estimated_peak_vram_gib_low,estimated_peak_vram_gib_high,recommended_system_ram_gib,"
  "estimated_peak_unified_memory_gib_low,estimated_peak_unified_memory_gib_high,memory_scope,memory_evidence_type,"
  "memory_assumptions,offload_mode,image_width,image_height,context_tokens,max_output_tokens,batch_size,recommended_steps,"
  "sampler,guidance_scale,flow_shift,model_page_url,variant_repo_url,revision,main_weight_filename,additional_required_files,"
  "runtime_support_source_url,recommendation_priority,recommendation_reason,short_description,best_for,limitations,license_id,"
  "license_url,access_requirements,checked_date,memory_source_urls,other_source_urls,schema_version,row_status,"
  "supersedes_entry_id,architecture,required_gpu_features,required_free_vram_gib,required_free_host_ram_gib,"
  "required_free_unified_memory_gib,fit_budget_basis,required_files_json,package_completeness,reviewed_utc,change_note,"
  "category_preference_order").split(",")
NUMERIC = ("parameter_count_billion_total,parameter_count_billion_active,gpu_count,estimated_peak_vram_gib_low,"
  "estimated_peak_vram_gib_high,recommended_system_ram_gib,estimated_peak_unified_memory_gib_low,"
  "estimated_peak_unified_memory_gib_high,image_width,image_height,context_tokens,max_output_tokens,batch_size,"
  "recommended_steps,guidance_scale,flow_shift,recommendation_priority,required_free_vram_gib,required_free_host_ram_gib,"
  "required_free_unified_memory_gib").split(",")
CATEGORIES = {"light_image_generation", "heavy_image_generation", "light_text", "heavy_text", "transcription"}
MAX_BYTES = 2 * 1024 * 1024
HEX40, HEX64 = re.compile(r"^[0-9a-f]{40}$"), re.compile(r"^[0-9a-f]{64}$")
ACCESS = {"public", "gated", "unknown"}

def num(v):
    """Approximates .NET double.TryParse(NumberStyles.Float, InvariantCulture)."""
    if v == "": return None
    s = v.strip()
    if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?|[+-]?(Infinity|NaN|∞)", s): return "bad"
    try: return float(s.replace("∞", "inf").replace("Infinity", "inf"))
    except ValueError: return "bad"

def part_a(raw):
    """Mirror of CsvModelCatalogue.ParseCore. Returns (rows, error-or-None)."""
    if len(raw) > MAX_BYTES: return [], "CSV exceeds 2 MiB."
    try: text = raw.decode("utf-8")
    except UnicodeDecodeError as e: return [], f"Not UTF-8: {e}"
    text = text.lstrip("﻿")
    try: table = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as e: return [], f"Malformed catalogue data: {e}"
    table = [t for t in table if t != []]  # TextFieldParser skips blank lines
    if not table or table[0] != HEADER: return [], "Expected the exact 66-column v6 header."
    rows, seen = [], set()
    for n, fields in enumerate(table[1:], start=2):
        if len(fields) != len(HEADER) or any(len(f) > 50000 for f in fields): return [], f"line {n}: Invalid CSV row width or field length."
        r = dict(zip(HEADER, fields))
        if (len(rows) >= 1000 or r["schema_version"] != "6" or r["category"] not in CATEGORIES or not r["entry_id"].strip()
                or not r["model_name"].strip() or not r["model_id"].strip() or not r["variant_id"].strip() or r["entry_id"] in seen):
            return [], f"line {n}: Invalid version, category or model identity."
        try: rank = int(r["category_preference_order"].strip())
        except ValueError: return [], f"line {n}: Invalid category preference order."
        if not 1 <= rank <= 1000: return [], f"line {n}: Invalid category preference order."
        if (r["row_status"] not in ("research", "candidate", "deprecated") or r["package_completeness"] not in ("complete", "partial", "unknown")
                or r["backend"] not in ("CUDA", "CPU", "Metal") or r["memory_type"] not in ("dedicated_gpu", "cpu_only", "unified_memory")):
            return [], f"line {n}: Invalid status or hardware topology."
        for k in NUMERIC:
            v = num(r[k])
            if v is not None and (v == "bad" or not math.isfinite(v) or v < 0): return [], f"line {n}: Invalid numeric value: {k}"
        for p in ("estimated_peak_vram_gib_", "estimated_peak_unified_memory_gib_"):
            lo, hi = num(r[p + "low"]), num(r[p + "high"])
            if lo is not None and hi is not None and lo > hi: return [], f"line {n}: Memory range is reversed."
        b, pk = num(r["required_free_vram_gib"]), num(r["estimated_peak_vram_gib_high"])
        if b is not None and pk is not None and b < pk: return [], f"line {n}: VRAM budget below peak."
        b, pk = num(r["required_free_unified_memory_gib"]), num(r["estimated_peak_unified_memory_gib_high"])
        if b is not None and pk is not None and b < pk: return [], f"line {n}: Unified budget below peak."
        mt = r["memory_type"]
        if ((mt != "unified_memory" and r["required_free_unified_memory_gib"] != "") or (mt != "dedicated_gpu" and r["required_free_vram_gib"] != "")
                or (mt == "unified_memory" and r["required_free_host_ram_gib"] != "")):
            return [], f"line {n}: Mixed memory topologies."
        try: files = json.loads(r["required_files_json"])
        except json.JSONDecodeError as e: return [], f"line {n}: Malformed catalogue data: {e}"
        if not isinstance(files, list) or len(files) > 100: return [], f"line {n}: Invalid component manifest."
        for f in files:
            if not isinstance(f, dict): return [], f"line {n}: Invalid component object."
            if "filename" not in f or "repository_url" not in f: return [], f"line {n}: Malformed catalogue data: missing filename/repository_url"
            name, url = f["filename"], f["repository_url"]
            if not isinstance(name, (str, type(None))) or not isinstance(url, (str, type(None))): return [], f"line {n}: Malformed catalogue data: non-string path"
            m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*)://([^/?#]*)", url or "")
            if (not name or not name.strip() or name.startswith("/") or "\\" in name or any(s in ("..", ".", "") for s in name.split("/"))
                    or ":" in name or not m or m.group(1).lower() != "https" or "@" in m.group(2)):
                return [], f"line {n}: Invalid component path or repository URL."
        seen.add(r["entry_id"]); rows.append(r)
    if not rows: return [], "Empty catalogue."
    by = {}
    for r in rows: by.setdefault(r["category"], []).append(int(r["category_preference_order"].strip()))
    for c, ranks in by.items():
        if sorted(ranks) != list(range(1, len(ranks) + 1)): return [], f"Each category needs unique consecutive preference numbers ({c}: {sorted(ranks)})."
    return rows, None

def part_b(rows):
    """Publisher-only checks (not enforced by the app parser)."""
    errs, warns = [], []
    for r in rows:
        e = r["entry_id"]; files = json.loads(r["required_files_json"])
        if r["access_requirements"] not in ACCESS: errs.append(f"{e}: access_requirements {r['access_requirements']!r} not in {sorted(ACCESS)}")
        if r["package_completeness"] == "complete" and not files: errs.append(f"{e}: complete package with no required files")
        if r["revision"] and not HEX40.match(r["revision"]): errs.append(f"{e}: revision is not a full 40-char commit")
        if files and not r["revision"]: errs.append(f"{e}: has required files but no row revision")
        for i, f in enumerate(files):
            tag = f"{e} file[{i}] {f.get('filename')}"
            if not HEX40.match(str(f.get("revision") or "")): errs.append(f"{tag}: revision not a full 40-char commit")
            if not isinstance(f.get("size_bytes"), int) or f["size_bytes"] <= 0: errs.append(f"{tag}: size_bytes missing")
            if not HEX64.match(str(f.get("sha256") or "")): errs.append(f"{tag}: publisher SHA-256 missing or malformed")
            if not str(f.get("repository_url", "")).startswith("https://huggingface.co/"): warns.append(f"{tag}: non-Hugging Face repository (pin checks not automated)")
        comp = [f for f in files if f.get("slot") not in ("main_model", "denoiser")]
        want = [f"{f['repository_url']}/resolve/{f.get('revision')}/{f['filename']}" for f in comp]
        have = [u for u in r["additional_required_files"].split(";") if u]
        if have != want: errs.append(f"{e}: additional_required_files does not match the pinned companion files")
        if "/resolve/main/" in r["additional_required_files"]: errs.append(f"{e}: unpinned /resolve/main/ URL")
        mains = [f["filename"].split("/")[-1] for f in files if f.get("slot") in ("main_model", "denoiser")]
        if files and r["main_weight_filename"] and r["main_weight_filename"].split("/")[-1] not in mains:
            errs.append(f"{e}: main_weight_filename not among main/denoiser files")
    return errs, warns

def main():
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    raw = open(sys.argv[1], "rb").read()
    rows, err = part_a(raw)
    rep = {"file": sys.argv[1], "bytes": len(raw), "partA_mirrorOfAppParser": "fail" if err else "pass", "partA_error": err,
           "rows": len(rows), "note": "Not the app validator. App validation pending until CsvModelCatalogue.Parse is run on this file."}
    if not err:
        errs, warns = part_b(rows)
        rep.update({"partB_publisherChecks": "fail" if errs else "pass", "partB_errors": errs, "partB_warnings": warns})
    if "--json" in sys.argv: json.dump(rep, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("partB_errors", "partB_warnings")}))
    for x in rep.get("partB_errors", []): print("  ERROR", x)
    for x in rep.get("partB_warnings", []): print("  WARN ", x)
    sys.exit(0 if not err and not rep.get("partB_errors") else 1)

if __name__ == "__main__":
    main()
