#!/usr/bin/env bash
# Compress a TRELLIS GLB for the web (9-22 MB -> target 2-5 MB).
# Usage: pipeline/compress_glb.sh in.glb assets/models/018/line_05.glb [texture_size]
set -euo pipefail
IN="${1:?usage: compress_glb.sh in.glb out.glb [texture_size]}"
OUT="${2:?missing output path}"
TEX="${3:-1024}"
mkdir -p "$(dirname "$OUT")"
npx -y @gltf-transform/cli@4 optimize "$IN" "$OUT" \
  --compress draco --texture-compress webp --texture-size "$TEX" \
  --simplify true --simplify-error 0.001
SIZE=$(stat -f%z "$OUT")
echo "$OUT: $((SIZE / 1024 / 1024)) MB"
if (( SIZE > 6 * 1024 * 1024 )); then
  echo "still over 6 MB — retry with texture_size 512" >&2
  exit 1
fi
