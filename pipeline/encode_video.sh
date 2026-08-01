#!/usr/bin/env bash
# Encode a video for the web and emit a poster frame next to it.
# Usage: pipeline/encode_video.sh in.mp4 assets/video/018/slerp.mp4
set -euo pipefail
IN="${1:?usage: encode_video.sh in.mp4 out.mp4}"
OUT="${2:?missing output path}"
mkdir -p "$(dirname "$OUT")"
ffmpeg -y -i "$IN" -c:v libx264 -crf 23 -preset slow -pix_fmt yuv420p \
  -vf "scale='min(1920,iw)':-2" -movflags +faststart -an "$OUT"
POSTER="${OUT%.mp4}_poster"
ffmpeg -y -i "$OUT" -frames:v 1 -q:v 3 "${POSTER}.png"
cwebp -quiet -q 80 "${POSTER}.png" -o "${POSTER}.webp" && rm "${POSTER}.png"
echo "wrote $OUT and ${POSTER}.webp"
