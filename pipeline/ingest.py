#!/usr/bin/env python3
"""Ingest one sonnet's chosen SeqAccepted run into the site.

  python pipeline/ingest.py --sonnet 018 --run 20250524223431_1277862290

Reads   pipeline/inbox/Sonnet018/<RUN>/  (<RUN>_line_NN.png + <RUN>.json)
Writes  assets/img/018/line_NN.webp (+ _thumb) and content/sonnets/018/manifest.json

Re-running with a different --run replaces images and per-line metadata but
preserves hand-edited manifest fields (texts, models, videos, part, title_line).
Optional inputs, merged when present:
  pipeline/poems.json                   poem texts w/ indentation; regenerate via
                                        extract_poems.py from the book .docx
  pipeline/sonnets_original.json        {"18": "Shall I compare..."} original texts
  pipeline/inbox/Sonnet018/glb/*.glb    compressed via compress_glb.sh separately
"""
import argparse
import difflib
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


def cwebp(src, dst, width, quality, cap=300 * 1024):
    dst.parent.mkdir(parents=True, exist_ok=True)
    while True:
        subprocess.run(["cwebp", "-quiet", "-q", str(quality), "-resize", str(width), "0",
                        str(src), "-o", str(dst)], check=True)
        if dst.stat().st_size <= cap or quality <= 55:
            break
        quality -= 10


def flatten(v):
    """Single-element lists read better as scalars in the manifest."""
    return v[0] if isinstance(v, list) and len(v) == 1 else v


def line_info(run_json, n):
    """Text + metadata for image-line n from the run JSON.

    Run JSON layout: one core_prompt_dict1/2 for the whole run (a run = one
    style), plus parallel arrays line_numbers / lines / prompts1 / prompts2.
    The 'lines' texts are image-line groupings of the poem, so they are the
    captions — not a 1:1 split of the transbliteration.
    """
    core = run_json.get("core_prompt_dict1", {})
    meta = {k: flatten(core[k]) for k in
            ("material", "art_period", "artists", "background", "time_of_day")
            if core.get(k)}
    meta |= {"seed": run_json.get("seed"), "steps": run_json.get("steps")}
    text = ""
    numbers = run_json.get("line_numbers", [])
    if n in numbers:
        idx = numbers.index(n)
        texts, prompts = run_json.get("lines", []), run_json.get("prompts1", [])
        if idx < len(texts):
            text = texts[idx]
        if idx < len(prompts):
            meta["prompt"] = prompts[idx]
    return text, {k: v for k, v in meta.items() if v is not None}


def align_use_lines(use_lines, poem):
    """Partition the poem's non-blank lines into one group per use line.

    A use line is a paraphrased concatenation of consecutive poem lines —
    words get tweaked ("world" -> "earth"), symbolizing words inserted
    ("conceptual eyes"), and anchor words repeated from earlier groups
    ("desire", "I alone") — so alignment is fuzzy: a DP over monotonic
    partitions maximizing token-sequence similarity per group.
    """
    def toks(s):
        return re.findall(r"[a-z']+", s.lower())

    def sim(use, group):
        a, b = toks(use), [t for ln in group for t in toks(ln)]
        return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0

    lines = [ln for ln in poem if ln.strip()]
    U, P = len(use_lines), len(lines)
    if not U or U > P:
        return None
    NEG = float("-inf")
    dp = [[NEG] * (P + 1) for _ in range(U + 1)]
    back = [[0] * (P + 1) for _ in range(U + 1)]
    dp[0][0] = 0.0
    for u in range(1, U + 1):
        for p in range(u, P + 1):
            for k in range(max(u - 1, p - 6), p):
                if dp[u - 1][k] > NEG:
                    s = dp[u - 1][k] + sim(use_lines[u - 1], lines[k:p])
                    if s > dp[u][p]:
                        dp[u][p], back[u][p] = s, k
    groups, p = [], P
    for u in range(U, 0, -1):
        k = back[u][p]
        groups.append(lines[k:p])
        p = k
    return list(reversed(groups))


def apply_poem(manifest, seq):
    """Fill poem text/part/roman from pipeline/poems.json (see extract_poems.py).

    Lines carry leading tabs and stanza-break empty strings — indentation is
    part of the work; preserve it verbatim (templates render inside <pre>).
    """
    poems_path = ROOT / "pipeline" / "poems.json"
    if not poems_path.exists():
        print("note: pipeline/poems.json missing — run extract_poems.py on the book docx")
        return
    poem = json.loads(poems_path.read_text()).get(f"{seq:03d}")
    if not poem:
        print(f"warning: poem {seq:03d} not in poems.json")
        return
    manifest["transbliteration"] = poem["lines"]
    manifest["part"] = re.sub(r"\s+", " ", poem["part"])
    manifest["roman"] = poem["roman"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sonnet", required=True, help="sonnet number, e.g. 018 or 18")
    ap.add_argument("--run", required=True, help="TIMESTAMP_SEED run folder name")
    ap.add_argument("--seq", type=int, help="transbliteration sequence number (defaults to existing manifest or sonnet #)")
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

    apply_poem(manifest, seq)

    originals_path = ROOT / "pipeline" / "sonnets_original.json"
    if originals_path.exists() and not manifest.get("original"):
        manifest["original"] = json.loads(originals_path.read_text()).get(str(num), "")

    use_path = args.inbox / f"Sonnet{slug}" / f"Sonnet{slug}_use_lines.txt"
    groups = None
    if use_path.exists():
        use_lines = [ln.rstrip() for ln in use_path.read_text().splitlines() if ln.strip()]
        groups = align_use_lines(use_lines, manifest.get("transbliteration", []))
        if groups is None:
            print("warning: could not align use lines to poem")
    else:
        print(f"note: {use_path.name} missing — captions fall back to prompt lines")

    img_dir = ROOT / "assets" / "img" / slug
    if img_dir.exists():
        for old in img_dir.glob("*.webp"):
            old.unlink()
    lines = []
    for png in sorted(run_dir.glob(f"{args.run}_line_*.png")):
        n = int(png.stem.rsplit("_", 1)[1])
        image = f"img/{slug}/line_{n:02d}.webp"
        thumb = f"img/{slug}/line_{n:02d}_thumb.webp"
        cwebp(png, ROOT / "assets" / image, 1344, 82)
        cwebp(png, ROOT / "assets" / thumb, 480, 78)
        text, meta = line_info(run_json, n)
        entry = {
            "n": n, "text": text,
            "image": image, "thumb": thumb, "width": 1344, "height": 768,
            "meta": meta,
        }
        if groups and n < len(groups):
            entry["poem_lines"] = groups[n]
        lines.append(entry)
    if not lines:
        sys.exit(f"no {args.run}_line_*.png files in {run_dir}")

    manifest.update({
        "sonnet": num, "roman": roman(num), "seq": seq, "run": args.run, "lines": lines,
    })
    manifest.pop("placeholder", None)
    manifest.pop("comment", None)
    poem = manifest.get("transbliteration", [])
    manifest.setdefault("part", "")
    first = next((ln.strip() for ln in poem if ln.strip()), "")
    manifest["title_line"] = manifest.get("title_line") or first
    manifest.setdefault("original", "")
    manifest.setdefault("transbliteration", [])
    manifest.setdefault("models", [])
    manifest.setdefault("videos", [])

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {manifest_path.relative_to(ROOT)}: {len(lines)} lines from run {args.run}")
    if not manifest["transbliteration"]:
        print("note: no poem text yet — run extract_poems.py, then re-run ingest")


if __name__ == "__main__":
    main()
