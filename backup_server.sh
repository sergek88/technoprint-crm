#!/usr/bin/env bash
# TechnoPrint server-side daily backup.
# Dumps the Postgres DB + a snapshot of critical config, verifies integrity,
# rotates old copies, and alerts via Telegram on failure.
# Deployed to: /opt/technoprint/backup.sh  (run by cron + pulled by the Mac)
set -uo pipefail

BACKUP_DIR=/opt/technoprint/backups
ENV_FILE=/opt/technoprint/backend/.env
RETENTION_DAYS=10
STAMP=$(date +%Y%m%d_%H%M%S)
DB_OUT="$BACKUP_DIR/db_${STAMP}.sql.gz"
CFG_OUT="$BACKUP_DIR/config_${STAMP}.tar.gz"
LOG="$BACKUP_DIR/backup.log"

mkdir -p "$BACKUP_DIR"

# Load TG creds for failure alerts (optional)
[ -f "$ENV_FILE" ] && . "$ENV_FILE" 2>/dev/null

tg() {
  [ -n "${TG_BOT_TOKEN:-}" ] && [ -n "${TG_ADMIN_CHAT_ID:-}" ] || return 0
  curl -s -m 15 "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TG_ADMIN_CHAT_ID}" \
    --data-urlencode "text=$1" >/dev/null 2>&1
  return 0
}

fail() {
  echo "[$(date '+%F %T')] FAIL: $1" >> "$LOG"
  tg "⚠️ TechnoPrint: серверный бэкап НЕ удался — $1"
  exit 1
}

# 1) DB dump (plain SQL, --clean so it restores over an existing DB)
docker exec tp-db pg_dump -U technoprint -d technoprint --clean --if-exists 2>>"$LOG" | gzip -9 > "$DB_OUT" || fail "pg_dump"
gzip -t "$DB_OUT" 2>>"$LOG" || fail "gzip integrity"

# 2) sanity: dump must actually contain the orders table data
cnt=$(gunzip -c "$DB_OUT" | grep -c "COPY public.orders")
[ "$cnt" -ge 1 ] || fail "dump missing orders table"

SIZE=$(du -h "$DB_OUT" | cut -f1)

# 3) config snapshot (secrets + compose + nginx site) — needed for full DR
tar -czf "$CFG_OUT" -C / \
  opt/technoprint/backend/.env \
  opt/technoprint/docker-compose.yml \
  etc/nginx/sites-available/tp.fixpo.ru 2>>"$LOG" \
  || echo "[$(date '+%F %T')] WARN: config snapshot partial" >> "$LOG"

# 4) convenience symlink to newest
ln -sf "$DB_OUT" "$BACKUP_DIR/latest.sql.gz"

# 5) rotation
find "$BACKUP_DIR" -name 'db_*.sql.gz'      -mtime +$RETENTION_DAYS -delete 2>/dev/null
find "$BACKUP_DIR" -name 'config_*.tar.gz'  -mtime +$RETENTION_DAYS -delete 2>/dev/null

echo "[$(date '+%F %T')] OK $DB_OUT ($SIZE)" >> "$LOG"
