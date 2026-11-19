#!/usr/bin/env python3
"""Compiled evaluator without and with the step cache on every Examples gate model that takes more than
--min seconds: CPU time (user+sys) and peak RSS, median of --runs, the two variants run in turn.
Every run is appended to OUT.jsonl; a restarted measurement continues from there.

usage: bench-examples.py --out FILE [--runs 5] [--min 1.0] [--max-runtime 5] BIN       env: EXAMPLES
"""
import json, os, subprocess, sys, statistics
args = sys.argv[1:]
def opt(name, default):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
    return default
out = opt("--out", "bench/examples-over-1s.json"); runs = int(opt("--runs", "5")); tmin = float(opt("--min", "1.0")); maxrt = float(opt("--max-runtime", "5"))
B = os.path.abspath(args[0]); EX = os.environ.get("EXAMPLES", "/home/user/refs/Examples")
VARIANTS = [("compiled", {"EVERYSTATE_STEP_CACHE": "off"}), ("cache", {"EVERYSTATE_STEP_CACHE": "on"})]
def secs(r):
    if r == "unknown": return 1e9
    t = 0
    for x in r.split(":"): t = t * 60 + float(x)
    return t
cases = []
for d in sorted(os.listdir(os.path.join(EX, "specifications"))):
    mf = os.path.join(EX, "specifications", d, "manifest.json")
    if not os.path.exists(mf): continue
    for mod in json.load(open(mf))["modules"]:
        for m in mod["models"]:
            if m["mode"] != "exhaustive search" or secs(m["runtime"]) > maxrt or m["result"] == "unknown": continue
            cases.append((m["path"], mod["path"]))
log = out + ".jsonl"; rows = []
if os.path.exists(log): rows = [json.loads(l) for l in open(log) if l.strip()]
done = {(r["round"], r["cfg"], r["variant"]) for r in rows}
def run(cfg, spec, env):
    p = subprocess.Popen([B, "-Dtlc2.tool.impl.Tool.cdot=true", "-json", "-config", cfg, spec], cwd=EX, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=dict(os.environ, **env))
    o = p.stdout.read(); _, st, ru = os.wait4(p.pid, 0)
    try: j = json.loads(o.decode().strip().split("\n")[-1])
    except Exception: j = {}
    return ru.ru_utime + ru.ru_stime, ru.ru_maxrss // 1024, j
def rec(rnd, cfg, variant, t, rss, j):
    r = {"round": rnd, "cfg": cfg, "variant": variant, "cpu": t, "rss": rss, "status": j.get("status"), "distinct": j.get("distinct"), "generated": j.get("generated"), "load": os.getloadavg()[0]}
    rows.append(r)
    with open(log, "a") as f: f.write(json.dumps(r) + "\n")
# round -1: which models are long enough
for cfg, spec in cases:
    if (-1, cfg, "compiled") not in done:
        t, rss, j = run(cfg, spec, VARIANTS[0][1]); rec(-1, cfg, "compiled", t, rss, j)
long = [c for c in cases if next(r["cpu"] for r in rows if r["round"] == -1 and r["cfg"] == c[0]) >= tmin]
for rnd in range(runs):
    for cfg, spec in long:
        for name, env in VARIANTS:
            if (rnd, cfg, name) in done: continue
            t, rss, j = run(cfg, spec, env); rec(rnd, cfg, name, t, rss, j)
table = []
for cfg, _ in long:
    row = {"model": os.path.basename(cfg)[:-4], "cfg": cfg}
    for name, _ in VARIANTS:
        rs = [r for r in rows if r["round"] >= 0 and r["cfg"] == cfg and r["variant"] == name]
        row[name] = {"cpuS": round(statistics.median(r["cpu"] for r in rs), 3), "rssMb": max(r["rss"] for r in rs), "distinct": rs[-1]["distinct"], "generated": rs[-1]["generated"], "status": rs[-1]["status"]}
    row["ratio"] = round(row["cache"]["cpuS"] / row["compiled"]["cpuS"], 3)
    row["same"] = all(row["cache"][k] == row["compiled"][k] for k in ("distinct", "generated", "status"))
    table.append(row)
table.sort(key=lambda r: -r["ratio"])
for r in table:
    print(f"{r['model'][:34]:34s} compiled {r['compiled']['cpuS']:6.2f}s {r['compiled']['rssMb']:4d}MB  cache {r['cache']['cpuS']:6.2f}s {r['cache']['rssMb']:4d}MB  ratio {r['ratio']:.3f}{'' if r['same'] else '  RESULT DIFFERS'}")
json.dump({"load": os.getloadavg(), "runs": runs, "min": tmin, "rows": table}, open(out, "w"), indent=1)
