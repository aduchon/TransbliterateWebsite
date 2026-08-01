#!/usr/bin/env python3
"""Ingest one sonnet's chosen SeqAccepted run into the site.

  python pipeline/ingest.py --sonnet 018 --run 20250524223431_1277862290

Reads   pipeline/inbox/Sonnet018/<RUN>/  (<RUN>_line_NN.png + <RUN>.json)
Writes  assets/img/018/line_NN.webp (+ _thumb) and content/sonnets/018/manifest.json

Re-running with a different --run replaces images and per-line metadata but
preserves hand-edited manifest fields (texts, models, videos, part, title_line).
Optional inputs, merged when present:
  --book pipeline/inbox/book.txt        plain-text export of the Google Doc;
                                        poem extracted via 'Transbliterated (NNN)' headers
  pipeline/sonnets_original.json        {"18": "Shall I compare..."} original texts
  pipeline/inbox/Sonnet018/glb/*.glb    compressed via compress_glb.sh separately
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
         (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def roman(n):
    out = ""
    for value, sym in ROMAN:
        while n >= value:
            out += sym
            n -= value
    return out


def cwebp(src, dst, width, quality):
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cwebp", "-quiet", "-q", str(quality), "-resize", str(width), "0",
                    str(src), "-o", str(dst)], check=True)


def line_meta(run_json, n):
    """Pull per-line metadata out of the run JSON, tolerating layout variants."""
    entries = run_json if isinstance(run_json, list) else \
        run_json.get("lines", run_json.get("settings", []))
    if isinstance(entries, dict):
        entries = list(entries.values())
    for e in entries:
        if isinstance(e, dict) and e.get("line_number") == n:
            core = e.get("core_prompt_dict1", {})
            return {k: core.get(k) for k in
                    ("material", "art_period", "artists", "background", "time_of_day")
                    if core.get(k)} | {
                "seed": e.get("seed") or (run_json.get("seed") if isinstance(run_json, dict) else None),
                "steps": e.get("steps"),
                "prompt": e.get("prompt1"),
            }
    # fall back to run-level fields
    if isinstance(run_json, dict):
        return {"seed": run_json.get("seed"), "steps": run_json.get("steps")}
    return {}


def poem_from_book(book_text, seq):
    """Extract transbliteration `seq` from a plain-text export of the book."""
    pattern = rf"Transbliterat\w*\s*\({seq:03d}\)"
    match = re.search(pattern, book_text)
    if not match:
        return None
    rest = book_text[match.end():]
    nxt = re.search(r"(Transbliterat\w*\s*\(\d{3}\)|^Part\s+[IVX]+\.)", rest, re.M)
    body = rest[: nxt.start()] if nxt else rest
    lines = [ln.strip() for ln in body.splitlines()]
    # drop leading blank/marker lines like "[-841]"
    while lines and (not lines[0] or re.fullmatch(r"\\?\[?-?\d+\\?\]?", lines[0])):
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return [ln for ln in lines if ln]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sonnet", required=True, help="sonnet number, e.g. 018 or 18")
    ap.add_argument("--run", required=True, help="TIMESTAMP_SEED run folder name")
    ap.add_argument("--seq", type=int, help="transbliteration sequence number (defaults to existing manifest or sonnet #)")
    ap.add_argument("--book", type=Path, help="plain-text export of the book doc")
    ap.add_argument("--inbox", type=Path, default=ROOT / "pipeline" / "inbox")
    args = ap.parse_args()

    num = int(args.sonnet)
    slug = f"{num:03d}"
    run_dir = args.inbox / f"Sonnet{slug}" / args.run
    if not run_dir.is_dir():
        sys.exit(f"run folder not found: {run_dir}")

    run_json_path = run_dir / f"{args.run}.json"
    run_json = json.loads(run_json_path.read_text()) if run_json_path.exists() else {}
    if not run_json_path.exists():
        print(f"warning: {run_json_path.name} missing; line metadata will be empty")

    manifest_path = ROOT / "content" / "sonnets" / slug / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    seq = args.seq or manifest.get("seq", num)

    if args.book:
        poem = poem_from_book(args.book.read_text(), seq)
        if poem:
            manifest["transbliteration"] = poem
        else:
            print(f"warning: Transbliterated ({seq:03d}) not found in {args.book}")

    originals_path = ROOT / "pipeline" / "sonnets_original.json"
    if originals_path.exists() and not manifest.get("original"):
        manifest["original"] = json.loads(originals_path.read_text()).get(str(num), "")

    poem_lines = manifest.get("transbliteration", [])
    lines = []
    for png in sorted(run_dir.glob(f"{args.run}_line_*.png")):
        n = int(png.stem.rsplit("_", 1)[1])
        image = f"img/{slug}/line_{n:02d}.webp"
        thumb = f"img/{slug}/line_{n:02d}_thumb.webp"
        cwebp(png, ROOT / "assets" / image, 1344, 82)
        cwebp(png, ROOT / "assets" / thumb, 480, 78)
        lines.append({
            "n": n,
            "text": poem_lines[n - 1] if 0 < n <= len(poem_lines) else "",
            "image": image, "thumb": thumb, "width": 1344, "height": 768,
            "meta": line_meta(run_json, n),
        })
    if not lines:
        sys.exit(f"no {args.run}_line_*.png files in {run_dir}")

    manifest.update({
        "sonnet": num, "roman": roman(num), "seq": seq, "run": args.run, "lines": lines,
    })
    manifest.setdefault("part", "")
    manifest.setdefault("title_line", poem_lines[0] if poem_lines else "")
    manifest.setdefault("original", "")
    manifest.setdefault("transbliteration", [])
    manifest.setdefault("models", [])
    manifest.setdefault("videos", [])

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {manifest_path.relative_to(ROOT)}: {len(lines)} lines from run {args.run}")
    if not manifest["transbliteration"]:
        print("note: no poem text yet — rerun with --book <export.txt> or edit the manifest")


if __name__ == "__main__":
    main()
