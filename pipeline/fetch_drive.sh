#!/usr/bin/env bash
# Pull one sonnet's SeqAccepted runs from Google Drive into the inbox.
# One-time setup: brew install rclone && rclone config   (create a remote named "gdrive")
# Usage: pipeline/fetch_drive.sh 018 [RUN_ID]
#   Without RUN_ID, pulls every candidate run so you can compare.
set -euo pipefail
SONNET=$(printf "%03d" "${1:?usage: fetch_drive.sh SONNET [RUN_ID]}")
RUN="${2:-}"
# Adjust this to the Drive path of the images root folder:
DRIVE_ROOT="gdrive:SonnetImages"
DEST="$(dirname "$0")/inbox/Sonnet${SONNET}"

SRC="${DRIVE_ROOT}/Sonnet${SONNET}/Sequences/SeqAccepted"
if [[ -n "$RUN" ]]; then
  rclone copy "${SRC}/${RUN}" "${DEST}/${RUN}" --progress
else
  rclone copy "${SRC}" "${DEST}" --progress
fi
echo "pulled into ${DEST}"
