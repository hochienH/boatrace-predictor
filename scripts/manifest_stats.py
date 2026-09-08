"""從 manifest 統計抓取結果與吞吐率。"""

import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw/_manifest.jsonl")
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
print("total", len(rows))
print("by kind", dict(collections.Counter(r["kind"] for r in rows)))
print("by outcome", dict(collections.Counter(r["outcome"] for r in rows)))
if rows:
    span = max(r["ts"] for r in rows) - min(r["ts"] for r in rows)
    print(f"span {span:.1f}s -> {len(rows) / max(span, 1):.2f} req/s")
    recent = rows[-300:]
    if len(recent) > 1:
        rspan = recent[-1]["ts"] - recent[0]["ts"]
        print(f"recent {len(recent)} in {rspan:.1f}s -> {len(recent) / max(rspan, 1e-6):.2f} req/s")
