"""Resolve every required file in a v6 CSV against the Hugging Face Hub (metadata only).

usage: resolve_files.py catalogue.csv out.json
For each (repository, filename): current full commit, exact filename (unique
case-insensitive match allowed and flagged), size, LFS SHA-256 from model
detail (?blobs=true), cross-checked against tree/{commit}; anonymous access is
tested with a HEAD request to /resolve/{commit}/{file} WITHOUT following the
redirect (no bytes downloaded). Gated repositories hide LFS oids in tree.
"""
import csv, json, re, subprocess, sys, urllib.parse, datetime

def run(args):
    return subprocess.run(args, capture_output=True, text=True)
def get_json(url):
    p = run(["curl", "-sS", "--max-time", "60", "-L", "-D", "/dev/stderr", url])
    return json.loads(p.stdout), p.stderr
def head_status(url):
    p = run(["curl", "-sS", "-o", "/dev/null", "-I", "--max-time", "30", "-w", "%{http_code} %{redirect_url}", url])
    code, _, loc = p.stdout.partition(" ")
    host = urllib.parse.urlparse(loc).netloc if loc else ""
    return int(code or 0), host

now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
repos, trees, out = {}, {}, {}
for r in rows:
    for i, f in enumerate(json.loads(r["required_files_json"] or "[]")):
        m = re.match(r"https://huggingface.co/([^/]+/[^/]+)/?$", f.get("repository_url") or "")
        key = f"{r['entry_id']}#{i}"
        if not m:
            out[key] = {"status": "no-repository"}; continue
        repo = m.group(1)
        if repo not in repos:
            try: repos[repo], _ = get_json(f"https://huggingface.co/api/models/{repo}?blobs=true")
            except Exception as e: repos[repo] = {"error": str(e)[:200]}
        d = repos[repo]
        if "siblings" not in d:
            out[key] = {"status": "repository-unavailable", "repo": repo, "detail": str(d)[:200]}; continue
        sib = {s["rfilename"]: s for s in d["siblings"]}
        fn = f["filename"]; s = sib.get(fn); case_fixed = None
        if s is None:
            cands = [k for k in sib if k.lower() == fn.lower()]
            if len(cands) == 1: case_fixed = cands[0]; s = sib[cands[0]]
        if s is None:
            out[key] = {"status": "file-not-found", "repo": repo, "sha": d["sha"], "filename": fn}; continue
        name = case_fixed or fn
        rev = d["sha"]
        d_dir = name.rsplit("/", 1)[0] if "/" in name else ""
        tk = (repo, rev, d_dir)
        if tk not in trees:
            url = f"https://huggingface.co/api/models/{repo}/tree/{rev}" + (f"/{urllib.parse.quote(d_dir)}" if d_dir else "")
            ent = {}
            while url:
                j, hdr = get_json(url)
                if not isinstance(j, list):
                    ent["__error__"] = str(j)[:200]; break
                for e in j: ent[e["path"]] = e
                mm = re.search(r'<([^>]+)>;\s*rel="next"', hdr); url = mm.group(1) if mm else None
            trees[tk] = ent
        t = trees[tk].get(name)
        lfs = s.get("lfs") or {}
        dsha, dsize = lfs.get("sha256"), s.get("size")
        tsha = (t or {}).get("lfs", {}).get("oid") if t else None
        tsize = (t or {}).get("size")
        masked = bool(tsha) and set(tsha) == {"*"}
        if t is None: cross = "not in tree" + (f" (tree error: {trees[tk]['__error__']})" if "__error__" in trees[tk] else "")
        elif masked: cross = "size only (tree hides LFS oid: gated repo)" if dsize == tsize else "MISMATCH size"
        elif dsha is None: cross = "non-LFS file: no published SHA-256" if dsize == tsize else "MISMATCH size"
        else: cross = "detail == tree" if (dsha, dsize) == (tsha, tsize) else "MISMATCH"
        code, host = head_status(f"https://huggingface.co/{repo}/resolve/{rev}/{urllib.parse.quote(name)}")
        access = "anonymous-ok" if code in (302, 307) else ("gated-or-auth" if code in (401, 403) else f"http-{code}")
        out[key] = {"status": "resolved", "repo": repo, "sha": rev, "filename": name, "caseFixedFrom": fn if case_fixed else None,
                    "size": dsize, "sha256": dsha, "crossCheck": cross, "gated": d.get("gated"), "license": (d.get("cardData") or {}).get("license"),
                    "licenseName": (d.get("cardData") or {}).get("license_name"), "headStatus": code, "redirectHost": host, "access": access, "checkedUtc": now()}
json.dump(out, open(sys.argv[2], "w"), indent=1)
import collections
print(collections.Counter(v["status"] for v in out.values()))
print(collections.Counter(v.get("crossCheck") for v in out.values() if v["status"] == "resolved"))
print(collections.Counter(v.get("access") for v in out.values() if v["status"] == "resolved"))
for k, v in out.items():
    if v["status"] != "resolved" or v.get("caseFixedFrom") or v.get("access") != "anonymous-ok" or "MISMATCH" in (v.get("crossCheck") or ""):
        print(" ", k[:60], {x: v.get(x) for x in ("status", "repo", "filename", "caseFixedFrom", "access", "crossCheck")})
