#!/usr/bin/env python3
"""Pin integrity, drift and download-destination check for a v6 catalogue CSV (metadata only).

usage: check_pins.py catalogue.csv --json report.json

For every pinned Hugging Face component (repository_url, revision, filename, size_bytes, sha256):
 1. PIN       model detail at the pinned revision must still list the file with the same size
              and LFS SHA-256.                                 -> ok | mismatch | missing | error
 2. DRIFT     compare the same path at the repository's current head:
              unchanged bytes at a newer commit -> "unchanged-newer-commit" (KEEP the pin; no change)
              different size/hash, or file gone -> "changed-upstream" / "removed-upstream"
                                                   (candidate for a reviewed replacement row)
 3. ACCESS    a) HEAD /resolve/<pinned>/<file> WITHOUT following redirects
                 401/403 -> "gated";  302/307 -> destination URL
              b) GET <destination> with Range: bytes=0-0 (one byte; never a full download)
                 206 and Content-Range total == size_bytes -> "verified"
                 runner cannot connect to the destination  -> "destination-unverified"
                 anything else                             -> "failed:<detail>"
              A redirect alone is never reported as verified.
Network errors are reported as inconclusive; they never change the catalogue.
Exit 0 = every pin ok and every lookup answered; 1 = integrity problem (mismatch/missing);
3 = inconclusive (API errors or rate limits after bounded retries; nothing may be changed); 2 = usage.
"""
import csv, json, subprocess, sys, urllib.parse, datetime, re, collections

def now(): return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def curl(args, timeout=60):
    p = subprocess.run(["curl", "-sS", "--max-time", str(timeout)] + args, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

def api(path, attempts=4):
    """GET a Hub API document. Rate limits (429) are waited out per the server's hint; any other
    non-200 or a body without the expected fields is an ERROR (inconclusive), never 'missing'."""
    import time
    for attempt in range(attempts):
        rc, out, err = curl(["-L", "-w", "\n%{http_code}", "-D", "/tmp/.hfhdr", f"https://huggingface.co/api/models/{path}"])
        if rc != 0: return None, f"network: {err.strip()[:160]}"
        body, _, code = out.rpartition("\n")
        if code == "429" and attempt < attempts - 1:
            hdr = open("/tmp/.hfhdr").read().lower()
            m = re.search(r"retry-after:\s*(\d+)", hdr) or re.search(r'ratelimit:.*?t=(\d+)', hdr)
            time.sleep(min(int(m.group(1)) + 2 if m else 30, 310)); continue
        if code != "200": return None, f"http {code}: {body[:120]}"
        try: d = json.loads(body)
        except json.JSONDecodeError: return None, f"bad response: {body[:120]}"
        if not isinstance(d, dict) or "siblings" not in d or "sha" not in d: return None, f"unexpected response: {str(d)[:120]}"
        return d, None
    return None, "rate limited: retries exhausted"

_detail = {}
def detail(repo, rev=None):
    key = (repo, rev)
    if key not in _detail:
        _detail[key] = api(f"{repo}/revision/{rev}?blobs=true" if rev else f"{repo}?blobs=true")
    return _detail[key]

def files_of(d):
    return {s["rfilename"]: (s.get("size"), (s.get("lfs") or {}).get("sha256")) for s in (d or {}).get("siblings", [])}

def access(repo, rev, name, size):
    url = f"https://huggingface.co/{repo}/resolve/{rev}/{urllib.parse.quote(name)}"
    rc, out, err = curl(["-o", "/dev/null", "-I", "-w", "%{http_code} %{redirect_url}", url], 30)
    if rc != 0: return {"result": "failed:hub-unreachable", "detail": err.strip()[:160]}
    code, _, loc = out.partition(" ")
    if code in ("401", "403"): return {"result": "gated", "hubStatus": int(code)}
    if code not in ("302", "307") or not loc: return {"result": f"failed:hub-status-{code}"}
    host = urllib.parse.urlparse(loc).netloc
    rc, out, err = curl(["-o", "/dev/null", "-r", "0-0", "-D", "-", "-w", "\n%{http_code}", loc], 30)
    if rc != 0:
        reason = "proxy refused" if "403" in err or "CONNECT tunnel failed" in err else err.strip()[:120]
        return {"result": "destination-unverified", "destinationHost": host, "detail": f"runner cannot reach {host} ({reason})"}
    lines = out.strip().splitlines(); status = lines[-1].strip() if lines else ""
    cr = next((l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("content-range:")), "")
    m = re.match(r"bytes 0-0/(\d+)", cr)
    if status == "206" and m and int(m.group(1)) == size:
        return {"result": "verified", "destinationHost": host, "contentRange": cr}
    return {"result": f"failed:destination-status-{status}", "destinationHost": host, "contentRange": cr}

def main():
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
    out, integrity_ok, inconclusive = [], True, []
    for r in rows:
        for i, f in enumerate(json.loads(r["required_files_json"] or "[]")):
            m = re.match(r"https://huggingface.co/([^/]+/[^/]+)/?$", f.get("repository_url") or "")
            rec = {"entry_id": r["entry_id"], "index": i, "repository": f.get("repository_url"), "filename": f.get("filename"),
                   "revision": f.get("revision"), "size_bytes": f.get("size_bytes"), "sha256": f.get("sha256"), "checkedUtc": now()}
            if not m:
                rec.update(pin="not-checked:non-HF", drift="not-checked", access={"result": "not-checked"}); out.append(rec); continue
            repo, rev, name, size, sha = m.group(1), f.get("revision"), f.get("filename"), f.get("size_bytes"), f.get("sha256")
            d, err = detail(repo, rev)
            if err: rec["pin"] = f"error:{err}"
            else:
                got = files_of(d).get(name)
                rec["pin"] = "missing" if got is None else ("ok" if got == (size, sha) else f"mismatch:{got}")
            if rec["pin"] != "ok" and not rec["pin"].startswith("error"): integrity_ok = False
            if rec["pin"].startswith("error"): inconclusive.append(rec["entry_id"])
            h, err = detail(repo)
            if err: rec["drift"] = f"error:{err}"; inconclusive.append(rec["entry_id"])
            else:
                rec["headRevision"] = h.get("sha")
                cur = files_of(h).get(name)
                rec["drift"] = ("same-commit" if h.get("sha") == rev else
                                "removed-upstream" if cur is None else
                                "unchanged-newer-commit" if cur == (size, sha) else "changed-upstream")
                rec["gated"] = h.get("gated")
            rec["access"] = access(repo, rev, name, size)
            out.append(rec)
    summary = {"file": sys.argv[1], "components": len(out), "checkedUtc": now(),
               "pin": dict(collections.Counter(x["pin"].split(":")[0] for x in out)),
               "drift": dict(collections.Counter(x["drift"].split(":")[0] for x in out)),
               "access": dict(collections.Counter(x["access"]["result"].split(":")[0] for x in out)),
               "integrity": ("PROBLEM" if not integrity_ok else "INCONCLUSIVE" if inconclusive else "ok")}
    if "--json" in sys.argv: json.dump({"summary": summary, "components": out}, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
    print(json.dumps(summary, indent=1))
    for x in out:
        if x["pin"] != "ok" or x["drift"] in ("changed-upstream", "removed-upstream") or x["access"]["result"] not in ("verified", "destination-unverified"):
            print("  ATTENTION", x["entry_id"][:50], x["filename"], x["pin"], x["drift"], x["access"]["result"])
    sys.exit(1 if not integrity_ok else 3 if inconclusive else 0)

if __name__ == "__main__":
    main()
