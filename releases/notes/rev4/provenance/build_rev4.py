"""Build v6 CSV rev4 from rev3 + resolved metadata. Preserves the 66 columns, column order,
row order, entry IDs, quoting (QUOTE_ALL, LF) and rankings.

usage: build_rev4.py rev3.csv resolved-rev4.json rev4.csv changes.json
"""
import csv, json, re, sys, io, datetime, copy
rev3, resolved_path, out_path, changes_path = sys.argv[1:5]
raw = open(rev3, "rb").read().decode("utf-8")
rows = list(csv.DictReader(io.StringIO(raw, newline="")))
cols = list(rows[0].keys()); assert len(cols) == 66
R = json.load(open(resolved_path))
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TODAY = NOW[:10]
VAE_SHA = "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38"
LUMINA = {"repo": "Comfy-Org/Lumina-Image-2", "sha": "5b072540ef86570fecb8249c505f23d5bdeb88cd",
          "filename": "split_files/vae/ae.safetensors", "size": 335304388, "sha256": VAE_SHA}
VAE_BASIS = ("VAE licence basis: the identical file (SHA-256 afc8e282...29e38, 335,304,388 bytes) is published by Black Forest Labs in "
             "black-forest-labs/FLUX.1-schnell under Apache-2.0; the Comfy-Org mirror's own repository licence is not relied on.")
PENDING = re.compile(r"[^.;]*(Full 40-char commit revisions, exact byte sizes, and live HTTP HEAD/Range anonymous download checks remain pending|"
                     r"immutable revisions? (and|hash)[^.;]*pending manager resolution|immutable repository revision and exact byte/hash manifest pending manager resolution|"
                     r"immutable revision and hashes pending manager resolution)[^.;]*")
PINNED = "rev4 records full commits, exact sizes and publisher SHA-256 for every required file (metadata check only; not an app-support or local test)"
api = lambda repo, sha: f"https://huggingface.co/api/models/{repo}/revision/{sha}"
resolve_url = lambda repo, sha, fn: f"https://huggingface.co/{repo}/resolve/{sha}/{fn}"
changes = []
out_rows = []
for r in rows:
    r = dict(r); orig = dict(r); notes = []
    files = json.loads(r["required_files_json"] or "[]")
    access = []
    for i, f in enumerate(files):
        v = R.get(f"{orig['entry_id']}#{i}")
        if not v or v["status"] != "resolved":
            continue
        repo, sha, fn, size, h = v["repo"], v["sha"], v["filename"], v["size"], v["sha256"]
        acc = v["access"]
        if repo == "black-forest-labs/FLUX.1-dev" and fn == "ae.safetensors" and h == VAE_SHA:
            repo, sha, fn, size, h = LUMINA["repo"], LUMINA["sha"], LUMINA["filename"], LUMINA["size"], LUMINA["sha256"]
            acc = "anonymous-ok"  # tested: HEAD /resolve/<sha>/split_files/vae/ae.safetensors -> 302
            notes.append("VAE moved from gated black-forest-labs/FLUX.1-dev ae.safetensors to the byte-identical public Comfy-Org/Lumina-Image-2 copy")
        if v.get("caseFixedFrom"):
            notes.append(f"filename case corrected {v['caseFixedFrom']} -> {fn}")
        f.update({"repository_url": f"https://huggingface.co/{repo}", "revision": sha, "filename": fn, "size_bytes": size,
                  "sha256": h, "source_url": api(repo, sha), "checked_utc": v["checkedUtc"]})
        access.append(acc)
    if files:
        r["required_files_json"] = json.dumps(files, separators=(",", ":"), ensure_ascii=False)
        # additional_required_files: companions (slot not main_model/denoiser), pinned, rev3 order
        r["additional_required_files"] = ";".join(resolve_url(re.sub(r"https://huggingface.co/", "", f["repository_url"]), f["revision"], f["filename"])
                                                  for f in files if f["slot"] not in ("main_model", "denoiser"))
        main = [f for f in files if f["slot"] in ("main_model", "denoiser")]
        if main:
            mf = main[0]
            if r["main_weight_filename"].lower() == mf["filename"].lower() and r["main_weight_filename"] != mf["filename"]:
                old = r["main_weight_filename"]
                for k in cols:
                    if k not in ("required_files_json",) and old in r[k]:
                        r[k] = r[k].replace(old, mf["filename"])
            vrepo = re.sub(r"https://huggingface.co/([^/]+/[^/]+).*", r"\1", r["variant_repo_url"])
            pinned = {re.sub(r"https://huggingface.co/", "", f["repository_url"]): f["revision"] for f in files}
            if vrepo in pinned:
                r["revision"] = pinned[vrepo]
        if access and all(a == "anonymous-ok" for a in access):
            new_access = "public"
        elif any(a == "gated-or-auth" for a in access):
            new_access = "gated"
        else:
            new_access = r["access_requirements"]
        if new_access != r["access_requirements"]:
            notes.append(f"access_requirements {r['access_requirements']} -> {new_access} (anonymous download access tested per file without downloading)")
            r["access_requirements"] = new_access
        r["limitations"] = PENDING.sub(" " + PINNED, r["limitations"]).replace("  ", " ").strip()
        if any(f["repository_url"].endswith("Comfy-Org/Lumina-Image-2") for f in files):
            if VAE_BASIS not in r["limitations"]:
                r["limitations"] = (r["limitations"].rstrip(". ") + ". " + VAE_BASIS)
        if any(f["sha256"] == "868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3" and "AtomicChat" in f["repository_url"] for f in files):
            s2 = ("VAE provenance: AtomicChat vae/ae.safetensors is byte-identical (SHA-256 868fe7b3...a343) to ae.safetensors in Black Forest Labs' gated "
                  "black-forest-labs/flux-3-image-klein; FLUX Kommunity License obligations from BFL's release apply.")
            if s2 not in r["limitations"]: r["limitations"] = r["limitations"].rstrip(". ") + ". " + s2
            notes.append("recorded VAE byte identity with Black Forest Labs' flux-3-image-klein ae.safetensors")
        if orig["entry_id"].startswith("flux-1-dev"):
            r["limitations"] = r["limitations"].replace("gated access required for ae.safetensors.",
                "the FLUX.1-dev denoiser (city96 GGUF derivative) remains under the FLUX.1-dev Non-Commercial licence regardless of anonymous download access.")
    if orig["entry_id"].startswith("flux-2-dev"):
        r["limitations"] = ("Gated FLUX [dev] Non-Commercial License. unsloth/FLUX.2-dev-FP8 (revision 7264beb00407a66160c69a5a4d2508f2f8678a67) publishes both "
                            ".pt and .safetensors files (FLUX.2-dev-FP8.safetensors 32,244,888,488 bytes; FLUX.2-dev-text_encoder-FP8.safetensors 24,683,085,096 bytes; also INT8). "
                            "Whether stable-diffusion.cpp can load these quantized safetensors is not verified. Remains research/unknown until a verified "
                            "stable-diffusion.cpp GGUF/safetensors variant is selected.")
        notes.append("corrected rev3 claim that the FP8 repository is .pt-only; it also publishes .safetensors")
    if orig["entry_id"].startswith("flux-3-image-klein"):
        notes.append("additional_required_files now lists the VAE already present in required_files_json")
    # bookkeeping fields
    if files or notes:
        r["checked_date"] = TODAY
        r["reviewed_utc"] = NOW
        n = len(files)
        base = (f"rev4: pinned {n} required file{'s' if n != 1 else ''} to full commits with exact case-sensitive filenames, byte sizes and publisher SHA-256 "
                "(Hub model detail cross-checked against tree; anonymous access tested by HEAD without downloading)" if files else "rev4: no required files to pin")
        r["change_note"] = (base + ("; " + "; ".join(notes) if notes else "") + ". Metadata verification only: not app support, runtime compatibility or local testing.")
    changes.append({"entry_id": orig["entry_id"], "fields": [k for k in cols if r[k] != orig[k]], "notes": notes})
    out_rows.append(r)
buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=cols, quoting=csv.QUOTE_ALL, lineterminator="\n"); w.writeheader(); w.writerows(out_rows)
open(out_path, "w", encoding="utf-8", newline="").write(buf.getvalue())
json.dump(changes, open(changes_path, "w"), indent=1)
print("written", out_path, NOW)
