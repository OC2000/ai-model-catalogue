#!/usr/bin/env python3
"""Pin the component files of a NEW candidate row from Hugging Face metadata (no weight downloads).

usage: resolve_candidate.py spec.json out.json
spec.json: [{"slot": "main_model", "repo": "owner/name", "filename": "path/in/repo.gguf",
             "shard_index": 1, "shard_count": 1, "revision": null}, ...]
  revision null -> the repository's current head commit is pinned.

Output: a JSON array in the catalogue's required_files_json shape, plus a "_evidence"
list with the cross-check and access results. Any component that cannot be resolved
exactly is returned with null fields and an evidence entry saying why: nothing is
guessed. The caller decides whether the row is complete, partial or unknown.
"""
import json, sys, subprocess, re, urllib.parse, datetime, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_pins import access, now

def get(url):
    p = subprocess.run(["curl", "-sS", "-L", "--max-time", "60", "-D", "/dev/stderr", url], capture_output=True, text=True)
    if p.returncode: raise RuntimeError(p.stderr.strip()[:200])
    return json.loads(p.stdout), p.stderr

def tree_entry(repo, rev, path):
    d = path.rsplit("/", 1)[0] if "/" in path else ""
    url = f"https://huggingface.co/api/models/{repo}/tree/{rev}" + (f"/{urllib.parse.quote(d)}" if d else "")
    while url:
        j, hdr = get(url)
        if not isinstance(j, list): return None
        for e in j:
            if e.get("path") == path: return e
        m = re.search(r'<([^>]+)>;\s*rel="next"', hdr); url = m.group(1) if m else None
    return None

def main():
    spec = json.load(open(sys.argv[1])); out, ev = [], []
    for s in spec:
        repo, name = s["repo"], s["filename"]
        rec = {"slot": s["slot"], "repository_url": f"https://huggingface.co/{repo}", "revision": None, "filename": name,
               "size_bytes": None, "sha256": None, "shard_index": s.get("shard_index", 1), "shard_count": s.get("shard_count", 1),
               "source_url": None, "checked_utc": now()}
        try:
            d, _ = get(f"https://huggingface.co/api/models/{repo}" + (f"/revision/{s['revision']}" if s.get("revision") else "") + "?blobs=true")
            sib = {x["rfilename"]: x for x in d.get("siblings", [])}
            if name not in sib:
                ev.append({"filename": name, "result": "file not found at this revision (exact, case-sensitive)"}); out.append(rec); continue
            x = sib[name]; size, sha = x.get("size"), (x.get("lfs") or {}).get("sha256")
            t = tree_entry(repo, d["sha"], name)
            toid = ((t or {}).get("lfs") or {}).get("oid")
            if t is None: cross = "not in tree"
            elif toid and set(toid) == {"*"}: cross = "size only (gated repo hides LFS oid)" if t.get("size") == size else "MISMATCH"
            else: cross = "detail == tree" if (t.get("size"), toid) == (size, sha) else "MISMATCH"
            if cross == "MISMATCH" or sha is None:
                ev.append({"filename": name, "result": f"not pinned: {cross if sha else 'no published SHA-256'}"}); out.append(rec); continue
            rec.update(revision=d["sha"], size_bytes=size, sha256=sha, source_url=f"https://huggingface.co/api/models/{repo}/revision/{d['sha']}")
            ev.append({"filename": name, "crossCheck": cross, "gated": d.get("gated"),
                       "license": (d.get("cardData") or {}).get("license"), "licenseName": (d.get("cardData") or {}).get("license_name"),
                       "access": access(repo, d["sha"], name, size)})
        except Exception as e:
            ev.append({"filename": name, "result": f"error: {e}"})
        out.append(rec)
    json.dump({"required_files_json": out, "_evidence": ev}, open(sys.argv[2], "w"), indent=1)
    print(json.dumps(ev, indent=1))

if __name__ == "__main__":
    main()
