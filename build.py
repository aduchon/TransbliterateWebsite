#!/usr/bin/env python3
"""Build transbliterate.com: content/ + templates/ + assets/ -> _site/.

Usage:
  python build.py            build once
  python build.py --serve    build, serve on :8000, rebuild on change
"""
import argparse
import http.server
import json
import shutil
import sys
from functools import partial
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
SITE = ROOT / "_site"
WATCH_DIRS = ["content", "templates", "static", "assets"]


def load_sonnets():
    """Load every content/sonnets/NNN/manifest.json, sorted by sequence number."""
    sonnets = []
    for manifest in sorted((ROOT / "content" / "sonnets").glob("*/manifest.json")):
        data = json.loads(manifest.read_text())
        data["slug"] = manifest.parent.name
        sonnets.append(data)
    sonnets.sort(key=lambda s: s.get("seq", s.get("sonnet", 0)))
    return sonnets


def build():
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    md = partial(markdown.markdown, extensions=["smarty"])

    site = yaml.safe_load((ROOT / "content" / "site.yaml").read_text())
    specs = yaml.safe_load((ROOT / "content" / "specs.yaml").read_text())
    garden = json.loads((ROOT / "content" / "garden.json").read_text())
    sonnets = load_sonnets()
    ctx = {"site": site, "sonnets": sonnets}

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    def render(template, out, **extra):
        (SITE / out).parent.mkdir(parents=True, exist_ok=True)
        (SITE / out).write_text(env.get_template(template).render(**ctx, **extra))

    render("index.html", "index.html")
    render("about.html", "about/index.html", body=md((ROOT / "content" / "about.md").read_text()))
    render("process.html", "process/index.html",
           body=md((ROOT / "content" / "statement.md").read_text()), specs=specs)
    render("garden.html", "garden/index.html", garden=garden)
    for i, s in enumerate(sonnets):
        render("sonnet.html", f"sonnets/{s['slug']}/index.html", s=s,
               prev=sonnets[i - 1] if i > 0 else None,
               next=sonnets[i + 1] if i + 1 < len(sonnets) else None)

    shutil.copytree(ROOT / "static", SITE / "static")
    if (ROOT / "assets").exists():
        shutil.copytree(ROOT / "assets", SITE / "assets")
    (SITE / "CNAME").write_text(site["domain"] + "\n")
    (SITE / ".nojekyll").write_text("")
    print(f"built {len(sonnets)} sonnet page(s) -> {SITE}")


def serve():
    import socket
    from contextlib import suppress

    class DualStackServer(http.server.ThreadingHTTPServer):
        address_family = socket.AF_INET6

        def server_bind(self):
            with suppress(OSError):
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            super().server_bind()

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    server = DualStackServer(("::1", 8000), handler)
    print("serving http://localhost:8000")
    try:
        from watchfiles import watch
        import threading
        threading.Thread(target=server.serve_forever, daemon=True).start()
        for changes in watch(*[ROOT / d for d in WATCH_DIRS]):
            print(f"{len(changes)} change(s), rebuilding")
            try:
                build()
            except Exception as e:  # keep serving on a broken edit
                print(f"build failed: {e}", file=sys.stderr)
    except ImportError:
        print("watchfiles not installed; serving without auto-rebuild")
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    build()
    if args.serve:
        serve()
