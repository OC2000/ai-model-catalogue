#!/usr/bin/env python3
"""Find leads for a catalogue update run: new repositories from watched publishers, trending repositories
per task, and abliterated/uncensored variants of model families already in the catalogue.

Leads are NOT catalogue entries. Each must be checked against primary sources (publisher model card,
licence, files) before a row is added. Hub metadata only; no weights are downloaded.

usage: discover.py <accepted.csv> [--days 21] [--out leads.json]
exit: 0 = ran (leads may be empty); 3 = Hub unreachable or rate-limited (inconclusive)
"""
import csv, json, re, subprocess, sys, time, datetime, urllib.parse

HUB = "https://huggingface.co/api/models"
# Original publishers and established GGUF / runtime-format packagers. Edit in review, not silently.
WATCH = ["Qwen", "google", "nvidia", "meta-llama", "mistralai", "microsoft", "openai", "deepseek-ai",
         "thinkingmachines", "moonshotai", "zai-org", "ibm-granite", "allenai", "tencent", "baidu",
         "ggml-org", "unsloth", "bartowski", "lmstudio-community",
         "black-forest-labs", "stabilityai", "Comfy-Org", "Tongyi-MAI", "krea", "MiniMaxAI", "city96", "leejet",
         "ggerganov", "Systran", "distil-whisper"]
TASKS = ["text-generation", "image-text-to-text", "text-to-image", "automatic-speech-recognition"]
ABLIT = ["abliterated", "uncensored", "heretic"]
FIELDS = "&".join("expand%5B%5D=" + f for f in ("createdAt", "downloads", "likes", "pipeline_tag", "tags", "gated", "lastModified"))

class Inconclusive(Exception): pass

def get(url, attempts=4):
    for i in range(attempts):
        p = subprocess.run(["curl", "-sS", "-L", "-D", "-", "--max-time", "60", url], capture_output=True, text=True)
        out = p.stdout.replace("\r\n", "\n")
        head, _, body = out.partition("\n\n")
        while body.startswith("HTTP/"):  # redirects / proxy CONNECT
            head, _, body = body.partition("\n\n")
        status = head.split(" ")[1] if head.startswith("HTTP/") else "000"
        if status == "200":
            try: return json.loads(body)
            except ValueError: pass
        if status == "429":
            m = re.search(r"(?im)^retry-after:\s*(\d+)", head) or re.search(r"(?im)^ratelimit:.*?t=(\d+)", head)
            time.sleep(min(int(m.group(1)) + 1 if m else 30, 310)); continue
        time.sleep(3 * (i + 1))
    raise Inconclusive(url)

def stem(name):
    """Family stem: 'Qwen3.6-35B-A3B-GGUF' -> 'qwen'; 'gemma-4-31B-it' -> 'gemma'."""
    m = re.match(r"[a-z]+", re.sub(r"[^a-z0-9]", "", name.lower()))
    return m.group(0) if m else ""

def version(name):
    m = re.search(r"(?i)[a-z]-?(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else None

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return 2
    days = int(a[a.index("--days") + 1]) if "--days" in a else 21
    out = a[a.index("--out") + 1] if "--out" in a else None
    rows = list(csv.DictReader(open(a[0], newline="")))
    have = {r["model_id"].lower() for r in rows} | {r["variant_repo_url"].split("huggingface.co/")[-1].lower() for r in rows}
    fams = {}
    for r in rows:
        n = r["model_id"].split("/")[-1]
        fams.setdefault(stem(n), set()).add((n, version(n), r["category"]))
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    seen, leads = set(), []

    def add(m, source):
        mid = m["id"]
        if mid.lower() in have or mid in seen or (m.get("createdAt") or "")[:10] < since: return
        seen.add(mid)
        name = mid.split("/")[-1]; s = stem(name); v = version(name)
        known = sorted(fams.get(s, []) if s else [], key=lambda x: (x[1] is None, x[1]))
        newer = [k[0] for k in known if v is not None and k[1] is not None and v > k[1]]
        tags = m.get("tags") or []
        leads.append({"id": mid, "source": source, "created": m.get("createdAt", "")[:10], "downloads": m.get("downloads"),
                      "likes": m.get("likes"), "pipeline": m.get("pipeline_tag"), "gated": m.get("gated"),
                      "gguf": "gguf" in tags, "license": next((t[8:] for t in tags if t.startswith("license:")), None),
                      "abliterated": any(k in mid.lower() for k in ABLIT),
                      "family_in_catalogue": [k[0] for k in known][:6],
                      "possible_newer_version_of": newer[:6]})

    try:
        for org in WATCH:
            for m in get(f"{HUB}?author={urllib.parse.quote(org)}&sort=createdAt&direction=-1&limit=25&{FIELDS}"):
                add(m, "watched-publisher")
        for t in TASKS:
            for m in get(f"{HUB}?pipeline_tag={t}&sort=trendingScore&limit=40&{FIELDS}"):
                add(m, "trending:" + t)
        for fam in sorted(fams):
            if len(fam) < 3: continue
            for k in ABLIT:
                for m in get(f"{HUB}?search={urllib.parse.quote(fam + ' ' + k)}&sort=downloads&direction=-1&limit=15&{FIELDS}"):
                    add(m, "abliterated-of:" + fam)
    except Inconclusive as e:
        print("INCONCLUSIVE: Hub request failed:", e, file=sys.stderr)
        return 3
    leads.sort(key=lambda x: (not x["possible_newer_version_of"], x["source"] != "watched-publisher", -(x["downloads"] or 0)))
    rep = {"generatedUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "baseline": a[0], "since": since, "watched": WATCH, "count": len(leads), "leads": leads,
           "note": "Leads only. Verify each against primary sources before adding a row."}
    s = json.dumps(rep, indent=1)
    open(out, "w").write(s + "\n") if out else print(s)
    print(f"{len(leads)} leads since {since}; {sum(bool(l['possible_newer_version_of']) for l in leads)} possible newer versions; "
          f"{sum(l['abliterated'] for l in leads)} abliterated/uncensored", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
