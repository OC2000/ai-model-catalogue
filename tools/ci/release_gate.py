#!/usr/bin/env python3
"""Decide exactly what the app-validator check must validate for a change, from git history only.

- Every release CSV added between BASE and HEAD is validated (against the release accepted at BASE).
- Any modification, deletion or rename of an existing release file is an error (releases are immutable).
- If no release was added, the release named by HEAD's accepted.json is validated.
- accepted.json must name an existing release whose size and SHA-256 match.
- latest.json must exist (missing or deleted is an error) and is always validated against the exact bytes it names
  (raw.githubusercontent.com/OC2000/ai-model-catalogue/<commit>/releases/<name>.csv, read from git at that commit).
  A pointer that cannot be resolved is an error, never a skip.

usage: release_gate.py --base REF [--head REF] --out DIR
Writes DIR/plan.json ({"validations": [...], "errors": [...]}) and the input bytes under DIR/inputs/.
exit: 0 = plan written and no errors; 1 = errors (plan still written); 2 = usage/git failure.
"""
import hashlib, json, os, re, subprocess, sys

REL = re.compile(r"^releases/ai-model-catalogue-v6-\d{8}-rev\d+\.csv$")
URL = re.compile(r"^https://raw\.githubusercontent\.com/OC2000/ai-model-catalogue/([0-9a-f]{40})/(releases/[A-Za-z0-9._-]+\.csv)$")

def git(*a, binary=False):
    p = subprocess.run(["git", *a], capture_output=True)
    if p.returncode: raise LookupError(p.stderr.decode(errors="replace").strip())
    return p.stdout if binary else p.stdout.decode()

def blob(rev, path):
    try: return git("show", f"{rev}:{path}", binary=True)
    except LookupError: return None

def main():
    a = sys.argv[1:]
    try:
        base = a[a.index("--base") + 1]; out = a[a.index("--out") + 1]
        head = a[a.index("--head") + 1] if "--head" in a else "HEAD"
    except (ValueError, IndexError):
        print(__doc__); return 2
    os.makedirs(os.path.join(out, "inputs"), exist_ok=True)
    errors, vals, n = [], [], [0]

    def save(data, label):
        n[0] += 1
        p = os.path.join(out, "inputs", f"{n[0]:02d}-{label}")
        open(p, "wb").write(data); return p

    def accepted_at(rev):
        b = blob(rev, "accepted.json")
        if b is None: return None
        try: return json.loads(b)
        except ValueError: errors.append(f"accepted.json at {rev} is not valid JSON"); return None

    try:
        merge_base = git("merge-base", base, head).strip()
        diff = git("diff", "--name-status", "-M", merge_base, head, "--", "releases/")
    except LookupError as e:
        print("git failure:", e, file=sys.stderr); return 2

    added = []
    for line in diff.splitlines():
        parts = line.split("\t"); st = parts[0]
        paths = parts[1:]
        if st == "A":
            p = paths[0]
            if p.endswith(".csv"):
                if REL.match(p): added.append(p)
                else: errors.append(f"added release has an invalid name: {p}")
        elif any(x.endswith(".csv") or x.endswith(".csv.sha256") for x in paths):
            errors.append(f"existing release file changed ({st}): {' -> '.join(paths)}. Releases are immutable; add a new revision instead.")

    base_acc = accepted_at(merge_base)
    prev_path = base_acc.get("file") if base_acc else None
    prev_bytes = blob(merge_base, prev_path) if prev_path else None
    prev_file = save(prev_bytes, "previous.csv") if prev_bytes is not None else None

    for p in added:
        data = blob(head, p)
        vals.append({"label": f"added release {p}", "csv": save(data, os.path.basename(p)),
                     "csvPath": p, "previous": prev_file, "previousPath": prev_path if prev_file else None, "manifest": None})

    head_acc = accepted_at(head)
    if head_acc is None:
        errors.append("accepted.json missing at HEAD")
    else:
        f = head_acc.get("file", ""); data = blob(head, f) if REL.match(f or "") else None
        if data is None:
            errors.append(f"accepted.json names a release that does not exist at HEAD: {f!r}")
        else:
            if len(data) != head_acc.get("sizeBytes") or hashlib.sha256(data).hexdigest() != head_acc.get("sha256"):
                errors.append(f"accepted.json size/SHA-256 do not match {f}")
            if not added:
                same = (f == prev_path)
                vals.append({"label": f"accepted release {f}", "csv": save(data, os.path.basename(f)), "csvPath": f,
                             "previous": None if same else prev_file, "previousPath": None if same else prev_path, "manifest": None})

    man = blob(head, "latest.json")
    if man is None:
        errors.append("latest.json is missing at HEAD: the live feed pointer must exist")
    else:
        try:
            m = json.loads(man); url = m.get("csvUrl", "")
        except (ValueError, AttributeError):
            m, url = None, ""
            errors.append("latest.json is not valid JSON")
        mm = URL.match(url or "")
        if m is not None and not mm:
            errors.append(f"latest.json csvUrl is not a commit-pinned release URL of this repository: {url!r}")
        elif mm:
            commit, path = mm.groups()
            data = blob(commit, path)
            if data is None:
                errors.append(f"latest.json names {path} at {commit[:12]}, which is not in this repository's history")
            else:
                cur = blob(head, path)
                if cur is not None and cur != data:
                    errors.append(f"{path} at HEAD differs from the bytes latest.json pins at {commit[:12]}")
                same = (path == prev_path)
                vals.append({"label": f"latest.json pointer -> {path}@{commit[:12]}", "csv": save(data, "pointer-" + os.path.basename(path)),
                             "csvPath": path, "previous": None if same else prev_file, "previousPath": None if same else prev_path,
                             "manifest": save(man, "latest.json")})

    plan = {"base": merge_base, "head": git("rev-parse", head).strip(), "validations": vals, "errors": errors}
    json.dump(plan, open(os.path.join(out, "plan.json"), "w"), indent=1)
    for v in vals: print("VALIDATE:", v["label"], "| previous:", v["previousPath"])
    for e in errors: print("ERROR:", e)
    if not vals and not errors: errors.append("nothing to validate")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
