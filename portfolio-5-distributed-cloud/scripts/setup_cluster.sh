#!/usr/bin/env bash
# =====================================================================
# setup_cluster.sh : builds a small PostgreSQL cluster on ONE machine
#
#   primary  (port 5601) - read/write, holds pipesafe
#   standby  (port 5602) - streaming replica of the primary (read-only)
#   shard_a  (port 5603) - shard for the SOUTH region
#   shard_b  (port 5604) - shard for all other regions
#
# Linux, macOS or Windows WSL. Each "server" is a separate PostgreSQL
# instance with its own data folder, port and processes. On a real
# deployment each would run on its own machine or cloud VM.
#
# Usage:  PG_BIN=/usr/lib/postgresql/16/bin ./scripts/setup_cluster.sh ./cluster
# =====================================================================
set -euo pipefail
PG_BIN="${PG_BIN:-$(dirname "$(command -v pg_ctl)")}"
BASE="$(realpath -m "${1:-./cluster}")"
SOCK="${SOCK_DIR:-/tmp}"
mkdir -p "$BASE"

start() {  # start <dir> <port>
  "$PG_BIN/pg_ctl" -D "$1" -o "-p $2 -k $SOCK -c listen_addresses=''" -l "$1.log" -w start >/dev/null
  echo "  started $(basename "$1") on port $2"
}

echo "1. Primary (port 5601)"
"$PG_BIN/initdb" -D "$BASE/primary" -A trust -U postgres >/dev/null
cat >> "$BASE/primary/postgresql.conf" <<CONF
wal_level = replica
max_wal_senders = 5
wal_keep_size = 256MB
hot_standby = on
CONF
start "$BASE/primary" 5601
"$PG_BIN/psql" -h "$SOCK" -p 5601 -U postgres -qc "CREATE DATABASE pipesafe"

echo "2. Load the Portfolio 1 database into the primary now, then press Enter."
echo "   (from portfolio-1-database-design:  psql -h $SOCK -p 5601 -U postgres -d pipesafe -f sql/01_create_tables.sql"
echo "                                        psql -h $SOCK -p 5601 -U postgres -d pipesafe -f sql/02_load_data.sql)"
if [ -z "${SKIP_PAUSE:-}" ]; then read -r; fi

echo "3. Standby (port 5602): copy the primary with pg_basebackup, then stream changes"
"$PG_BIN/pg_basebackup" -h "$SOCK" -p 5601 -U postgres -D "$BASE/standby" -R -X stream -C -S standby_slot
start "$BASE/standby" 5602

echo "4. Shard servers (ports 5603, 5604)"
for n in a:5603 b:5604; do
  name="shard_${n%%:*}"; port="${n##*:}"
  "$PG_BIN/initdb" -D "$BASE/$name" -A trust -U postgres >/dev/null
  start "$BASE/$name" "$port"
  "$PG_BIN/psql" -h "$SOCK" -p "$port" -U postgres -qc "CREATE DATABASE pipesafe_shard"
done
echo "Done. Cluster folder: $BASE"
