# transbliterate.com

Static site for *Transbliterations, Volume Two: Shakespeare* by Andrew Duchon —
the submission vehicle for the .ART Award 2026 (deadline Nov 1, 2026).

## Develop

```bash
pip install -r requirements.txt
python build.py --serve        # http://127.0.0.1:8000, rebuilds on change
```

## Add or restyle a sonnet

1. Pull the chosen SeqAccepted run: `pipeline/fetch_drive.sh 018 <TIMESTAMP_SEED>`
   (needs `brew install rclone` + a `gdrive` remote; or download manually into
   `pipeline/inbox/Sonnet018/<TIMESTAMP_SEED>/`).
2. Ingest: `python pipeline/ingest.py --sonnet 018 --run <TIMESTAMP_SEED> --book pipeline/inbox/book.txt`
   — idempotent; re-run with a different run ID to swap the style.
3. 3D: `pipeline/compress_glb.sh in.glb assets/models/018/line_05.glb`, then add
   an entry to `models` in the manifest (and to `content/garden.json`).
4. Videos: `pipeline/encode_video.sh in.mp4 assets/video/018/slerp.mp4`, then add
   to `videos` in the manifest (`kind`: `slerp` or `diff`).
5. Check: `python pipeline/check_budget.py` (also enforced in CI).

`content/sonnets/001/` is a placeholder demo — replace via step 2.

## Deploy

Push to `main`: GitHub Actions builds and publishes to GitHub Pages
(custom domain from `content/site.yaml` → CNAME).
