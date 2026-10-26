"""Select completed P0-01 A/B cells and retain focused retry provenance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "outputs/p0-01-release"
RUNS = ["ab-final", "ab-retry", "ab-retry-fr-desktop"]
selected = {}
attempts = []

for run in RUNS:
    path = BASE / run / "comparison.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for case in data["cases"]:
        a = json.loads(Path(case["a"]).read_text(encoding="utf-8"))
        b = json.loads(Path(case["b"]).read_text(encoding="utf-8"))
        record = {
            "run": run,
            "name": case["name"],
            "status": case["comparison"]["status"],
            "findings": case["comparison"]["findings"],
            "a_pages": len(a["pages"]),
            "b_pages": len(b["pages"]),
            "a_api_events": len(a["api_events"]),
            "b_api_events": len(b["api_events"]),
            "a_exception": a.get("exception"),
            "b_exception": b.get("exception"),
            "a_errors": a["errors"],
            "b_errors": b["errors"],
            "trace_a": str(BASE / run / case["name"] / "A/trace.zip"),
            "trace_b": str(BASE / run / case["name"] / "B/trace.zip"),
        }
        attempts.append(record)
        if record["status"] == "PASS":
            selected[case["name"]] = record

expected = {
    f"{fixture}_{language}_{viewport}"
    for fixture in ("P0-01-empty-v1", "P0-01-43x2-46x3-v1")
    for language in ("en", "fr")
    for viewport in ("desktop", "mobile")
}
if set(selected) != expected:
    raise SystemExit(f"Missing passing cells: {sorted(expected - set(selected))}")
for record in selected.values():
    if record["a_pages"] != record["b_pages"] or record["a_pages"] not in (7, 8):
        raise SystemExit(f"Bad page count: {record['name']}")
    if record["a_errors"] or record["b_errors"]:
        raise SystemExit(f"Unexpected browser error: {record['name']}")
    if not Path(record["trace_a"]).is_file() or not Path(record["trace_b"]).is_file():
        raise SystemExit(f"Missing trace: {record['name']}")

summary = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "Controlled A/B browser GET mocks; no production API writes or post-deployment smoke",
    "baseline": "Sites v9 / 4550358b96f0a26bd118d98e2e64eb956beaecbf",
    "candidate": "local dirty checkout / f860e97c9aa2bf71197ec69dbf98238fbc7137c8",
    "selected_cells": [selected[name] for name in sorted(expected)],
    "attempts": attempts,
    "counts": {
        "selected_pass": len(selected),
        "selected_pages_per_side": sum(r["a_pages"] for r in selected.values()),
        "initial_connection_resets": sum(
            "ERR_CONNECTION_RESET" in (r["a_exception"] or "") for r in attempts
        ),
        "regressions": sum(r["status"] == "REGRESSION" for r in attempts),
    },
}
output = BASE / "ab-verified.json"
output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(summary["counts"])
print("sha256", hashlib.sha256(output.read_bytes()).hexdigest())
