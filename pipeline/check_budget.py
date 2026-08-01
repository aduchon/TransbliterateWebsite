#!/usr/bin/env python3
"""Asset-size budget gate; run locally and in CI. Exits 1 on any violation."""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
MB = 1024 * 1024
CAPS = {".webp": 300 * 1024, ".glb": 6 * MB, ".mp4": 20 * MB, ".webm": 20 * MB}
THUMB_CAP = 50 * 1024
PER_SONNET_CAP = 35 * MB
TOTAL_CAP = 600 * MB


def main():
    failures, per_sonnet, total = [], defaultdict(int), 0
    for f in sorted(ASSETS.rglob("*")):
        if not f.is_file() or f.name == ".DS_Store":
            continue
        size = f.stat().st_size
        total += size
        rel = f.relative_to(ASSETS)
        if len(rel.parts) >= 2:
            per_sonnet[rel.parts[1]] += size
        cap = THUMB_CAP if f.stem.endswith("_thumb") else CAPS.get(f.suffix.lower())
        if cap and size > cap:
            failures.append(f"{rel}: {size / MB:.1f} MB > cap {cap / MB:.1f} MB")

    for sonnet, size in sorted(per_sonnet.items()):
        flag = " OVER" if size > PER_SONNET_CAP else ""
        print(f"  {sonnet}: {size / MB:5.1f} MB{flag}")
        if size > PER_SONNET_CAP:
            failures.append(f"sonnet {sonnet} total {size / MB:.1f} MB > {PER_SONNET_CAP / MB:.0f} MB")
    print(f"assets total: {total / MB:.1f} MB (cap {TOTAL_CAP / MB:.0f} MB)")
    if total > TOTAL_CAP:
        failures.append(f"assets total {total / MB:.1f} MB > {TOTAL_CAP / MB:.0f} MB")

    if failures:
        print("\nBUDGET FAILURES:", *failures, sep="\n  ")
        sys.exit(1)
    print("budget OK")


if __name__ == "__main__":
    main()
