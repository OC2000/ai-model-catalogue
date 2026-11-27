#!/usr/bin/env python3
"""Write latest.json for a release that is ACTUALLY being published. Run only with explicit approval.

usage: make_latest.py releases/<immutable>.csv --url https://<host>/<path>/<same filename> [--out latest.json]

- csvUrl must be https, without credentials or a query string, and must end in the release file name.
- The release file must already be committed and must never be edited afterwards (immutable name per revision).
- sizeBytes and sha256 are computed from the file; publishedUtc is the real time this runs.
Refuses to write if anything is inconsistent.
"""
import hashlib, json, os, sys, datetime, urllib.parse, re

def main():
    if len(sys.argv) < 4 or "--url" not in sys.argv: print(__doc__); sys.exit(2)
    path = sys.argv[1]; url = sys.argv[sys.argv.index("--url") + 1]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "latest.json"
    name = os.path.basename(path)
    m = re.fullmatch(r"(ai-model-catalogue-v6-\d{8}-rev\d+)\.csv", name)
    if not m: sys.exit("release file name must be ai-model-catalogue-v6-YYYYMMDD-revN.csv")
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.username or u.password or u.query or not u.path.endswith("/" + name):
        sys.exit("csvUrl must be https, credential- and query-free, and end with the release file name")
    raw = open(path, "rb").read()
    doc = {"schemaVersion": 6, "releaseId": m.group(1),
           "publishedUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "csvUrl": url, "sizeBytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    json.dump(doc, open(out, "w"), indent=2); open(out, "a").write("\n")
    print(json.dumps(doc, indent=2))

if __name__ == "__main__":
    main()
