#!/usr/bin/env python3
"""Failure-case tests for release_gate.py, run in throwaway git repositories. usage: test_release_gate.py"""
import hashlib, json, os, subprocess, sys, tempfile
GATE = os.path.abspath(os.path.join(os.path.dirname(__file__), "release_gate.py"))
R4, R5, R6 = (f"releases/ai-model-catalogue-v6-20261127-rev{i}.csv" for i in (4, 5, 6))

def sh(*a, cwd): return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

def write(d, path, data):
    full = os.path.join(d, path); os.makedirs(os.path.dirname(full) or d, exist_ok=True)
    open(full, "wb").write(data if isinstance(data, bytes) else data.encode())

def commit(d, msg):
    sh("git", "add", "-A", cwd=d); sh("git", "commit", "-q", "-m", msg, cwd=d); return sh("git", "rev-parse", "HEAD", cwd=d)

def accepted(path, data):
    return json.dumps({"schemaVersion": 6, "file": path, "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

def latest(commit_id, path, data):
    return json.dumps({"schemaVersion": 6, "releaseId": os.path.basename(path)[:-4], "publishedUtc": "2026-11-27T11:45:38Z",
                       "csvUrl": f"https://raw.githubusercontent.com/OC2000/ai-model-catalogue/{commit_id}/{path}",
                       "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

def repo():
    d = tempfile.mkdtemp()
    sh("git", "init", "-q", "-b", "main", cwd=d); sh("git", "config", "user.email", "t@example.invalid", cwd=d); sh("git", "config", "user.name", "t", cwd=d)
    write(d, R4, b"rev4\n"); write(d, R5, b"rev5\n"); write(d, "accepted.json", accepted(R5, b"rev5\n"))
    c = commit(d, "releases")
    write(d, "latest.json", latest(c, R5, b"rev5\n")); commit(d, "pointer")
    sh("git", "branch", "base", cwd=d)
    return d

def gate(d):
    out = tempfile.mkdtemp()
    p = subprocess.run([sys.executable, GATE, "--base", "base", "--out", out], cwd=d, capture_output=True, text=True)
    return p.returncode, json.load(open(os.path.join(out, "plan.json"))), p.stdout

CASES = []
def case(f): CASES.append(f); return f

@case
def clean_new_release_is_validated(d):
    write(d, R6, b"rev6\n"); commit(d, "add rev6")
    rc, plan, _ = gate(d)
    assert rc == 0, plan["errors"]
    labels = [v["label"] for v in plan["validations"]]
    assert any(R6 in l and l.startswith("added") for l in labels), labels
    assert any(l.startswith("latest.json pointer") for l in labels), "pointer must always be validated"
    assert all(v["previousPath"] == R5 for v in plan["validations"] if v["label"].startswith("added"))

@case
def every_added_release_is_validated_not_just_the_last_name(d):
    a, b = "releases/ai-model-catalogue-v6-20261201-rev6.csv", "releases/ai-model-catalogue-v6-20261130-rev7.csv"
    write(d, a, b"x\n"); write(d, b, b"y\n"); commit(d, "two")
    rc, plan, _ = gate(d)
    got = {v["csvPath"] for v in plan["validations"] if v["label"].startswith("added")}
    assert got == {a, b}, got

@case
def modified_existing_release_fails(d):
    write(d, R4, b"rev4 edited\n"); write(d, R6, b"rev6\n"); commit(d, "edit rev4")
    rc, plan, _ = gate(d)
    assert rc == 1 and any("existing release file changed (M)" in e and R4 in e for e in plan["errors"]), plan["errors"]

@case
def deleted_release_fails(d):
    os.remove(os.path.join(d, R4)); commit(d, "delete rev4")
    rc, plan, _ = gate(d)
    assert rc == 1 and any("(D)" in e for e in plan["errors"]), plan["errors"]

@case
def renamed_release_fails(d):
    sh("git", "mv", R4, "releases/ai-model-catalogue-v6-20261127-rev9.csv", cwd=d); commit(d, "rename")
    rc, plan, _ = gate(d)
    assert rc == 1 and any("(R" in e for e in plan["errors"]), plan["errors"]

@case
def pointer_to_a_different_release_is_validated_against_that_file(d):
    c = sh("git", "rev-parse", "HEAD", cwd=d)
    write(d, "latest.json", latest(c, R4, b"rev4\n")); commit(d, "point at rev4")
    rc, plan, _ = gate(d)
    v = [v for v in plan["validations"] if v["label"].startswith("latest.json pointer")]
    assert rc == 0 and len(v) == 1 and v[0]["csvPath"] == R4 and open(v[0]["csv"], "rb").read() == b"rev4\n", plan

@case
def pointer_to_unknown_commit_fails(d):
    write(d, "latest.json", latest("0" * 40, R5, b"rev5\n")); commit(d, "bad commit")
    rc, plan, _ = gate(d)
    assert rc == 1 and any("not in this repository's history" in e for e in plan["errors"]), plan["errors"]

@case
def pointer_to_main_branch_url_fails(d):
    m = json.loads(open(os.path.join(d, "latest.json")).read()); m["csvUrl"] = m["csvUrl"].replace(m["csvUrl"].split("/")[5], "main")
    write(d, "latest.json", json.dumps(m)); commit(d, "main url")
    rc, plan, _ = gate(d)
    assert rc == 1 and any("not a commit-pinned" in e for e in plan["errors"]), plan["errors"]

@case
def unparseable_pointer_fails(d):
    write(d, "latest.json", "{not json"); commit(d, "broken")
    rc, plan, _ = gate(d)
    assert rc == 1 and any("not valid JSON" in e for e in plan["errors"]), plan["errors"]

@case
def pointer_with_wrong_hash_is_still_sent_to_the_validator(d):
    m = json.loads(open(os.path.join(d, "latest.json")).read()); m["sha256"] = "f" * 64
    write(d, "latest.json", json.dumps(m)); commit(d, "wrong hash")
    rc, plan, _ = gate(d)
    v = [v for v in plan["validations"] if v["manifest"]]
    assert rc == 0 and v, "gate must hand the changed pointer to the app validator, which rejects the hash"

@case
def accepted_json_mismatch_fails(d):
    write(d, "accepted.json", accepted(R5, b"something else\n")); commit(d, "bad accepted")
    rc, plan, _ = gate(d)
    assert rc == 1 and any("do not match" in e for e in plan["errors"]), plan["errors"]

@case
def deleted_pointer_fails(d):
    os.remove(os.path.join(d, "latest.json")); commit(d, "delete latest.json")
    rc, plan, _ = gate(d)
    assert rc != 0 and any("latest.json is missing" in e for e in plan["errors"]), (rc, plan["errors"])

@case
def missing_pointer_fails_even_without_other_changes(d):
    sh("git", "rm", "-q", "latest.json", cwd=d); c = commit(d, "no pointer")
    sh("git", "branch", "-f", "base", c, cwd=d)  # base also lacks it: still an error
    rc, plan, _ = gate(d)
    assert rc != 0 and any("latest.json is missing" in e for e in plan["errors"]), (rc, plan["errors"])

failed = 0
for f in CASES:
    try: f(repo()); print("PASS", f.__name__)
    except AssertionError as e: failed += 1; print("FAIL", f.__name__, e)
print(f"{len(CASES) - failed}/{len(CASES)} passed"); sys.exit(1 if failed else 0)
