#!/bin/sh
set -e

SRC="${DB_PATH:-/data/velmora.db}"
TS="$(date +%F_%H-%M-%S)"
DST="/backups/velmora_${TS}.db"
KEEP="${BACKUP_KEEP:-14}"

if [ ! -f "$SRC" ]; then
  echo "[backup] DB not found: $SRC"
  exit 0
fi

echo "[backup] Backing up $SRC -> $DST"

if command -v sqlite3 >/dev/null 2>&1; then
  # Safe online backup even if API is running
  sqlite3 "$SRC" ".backup '$DST'"
else
  cp -f "$SRC" "$DST"
fi

# prune old backups (keep newest $KEEP)
echo "[backup] Pruning, keeping last $KEEP"
ls -1t /backups/velmora_*.db 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f