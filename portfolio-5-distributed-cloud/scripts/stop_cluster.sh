#!/usr/bin/env bash
# Stops every instance created by setup_cluster.sh.  Usage: ./scripts/stop_cluster.sh ./cluster
PG_BIN="${PG_BIN:-$(dirname "$(command -v pg_ctl)")}"
BASE="$(realpath -m "${1:-./cluster}")"
for d in primary standby shard_a shard_b; do
  [ -f "$BASE/$d/postmaster.pid" ] && "$PG_BIN/pg_ctl" -D "$BASE/$d" -m fast stop && echo "stopped $d"
done
exit 0
