"""Read-only per-outlet evaluation of one canary run from the runtime workspace. Usage: wave_eval.py <workspace> <run-id-fragment> [--json out]"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ws, run = Path(sys.argv[1]), sys.argv[2]


def rows(relative):
    out = []
    for line in (ws / relative).read_bytes().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


log = [r for r in rows("requests/requests.jsonl") if run in r.get("run_id", "")]
planned = {r["request_id"]: r for r in log if r["event"] == "PLANNED"}
per = defaultdict(lambda: {"robots": Counter(), "channel_documents": Counter(), "items": Counter(), "item_fetch_ids_2xx": [], "denied": Counter()})
for r in log:
    if r["event"] == "PLANNED":
        continue
    outlet = planned.get(r["request_id"], {}).get("outlet_id", "?")
    status = (r.get("result") or {}).get("status")
    kind = {"robots_txt": "robots", "channel_document": "channel_documents", "item": "items"}.get(r["fetch_kind"], r["fetch_kind"])
    if r["final"] != "FETCHED":
        per[outlet]["denied"][f"{r['fetch_kind']}:{(r.get('policy_reasons') or [r['final']])[0]}"] += 1
        continue
    per[outlet][kind][str(status)] += 1
    if kind == "items" and status is not None and 200 <= status < 300:
        per[outlet]["item_fetch_ids_2xx"].append((r.get("fetch_ids") or [None])[-1])

events = [r for r in rows("discovery/events.jsonl") if run in r.get("run_id", "")]
inputs = [r for r in rows("discovery/inputs.jsonl") if run in r.get("run_id", "")]
quals = [r for r in rows("discovery/qualifications.jsonl") if run in r.get("run_id", "")]
labels = {r["fetch_id"]: r for r in rows("admission/labels.jsonl")}
summary = {}
outlets = sorted(set(per) | {e["outlet_id"] for e in events})
for outlet in outlets:
    p = per[outlet]
    mine = [e for e in events if e["outlet_id"] == outlet]
    docs = [i for i in inputs if i["channel_id"].startswith(outlet + ":")]
    ids = [f for f in p["item_fetch_ids_2xx"] if f]
    labelled = [labels[f] for f in ids if f in labels]
    chars = [label["measurements"]["body_characters"] for label in labelled]
    summary[outlet] = {
        "robots": dict(p["robots"]), "channel_documents": dict(p["channel_documents"]), "denied": dict(p["denied"]),
        "inputs": [f"{i['channel_id'].split(':ch:')[1]}:{i['outcome']}:{i.get('format')}:{i.get('entries')}" for i in docs],
        "events": len(mine), "event_problems": dict(Counter(e["problem"] for e in mine if e["problem"])),
        "candidates_listed": len({e["candidate_id"] for e in mine if e["candidate_id"]}),
        "qualifications": dict(Counter(f"{q['decision']}:{(q.get('reasons') or [''])[0]}" for q in quals if q["outlet_id"] == outlet)),
        "items": dict(p["items"]), "items_2xx": len(p["item_fetch_ids_2xx"]), "items_2xx_labelled": len(labelled),
        "body_characters_median": int(statistics.median(chars)) if chars else None,
        "body_characters_min_max": [min(chars), max(chars)] if chars else None,
        "items_with_body_text": sum(1 for c in chars if c >= 500),
        "blocking_reasons": dict(Counter(reason for label in labelled for reason in label.get("blocking_reasons", []))),
    }
print(json.dumps(summary, indent=1, ensure_ascii=False))
if "--json" in sys.argv:
    Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
