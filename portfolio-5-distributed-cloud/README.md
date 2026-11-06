# Portfolio 5: Distributed and Cloud Database

The PipeSafe database running on a real **four-server PostgreSQL cluster**: a primary, a streaming standby and two region shards. It demonstrates replication, synchronous vs asynchronous consistency, the availability trade-off when a server fails, failover, and sharding with routing and query pushdown. MongoDB Atlas's built-in replica set is used as cloud evidence.

## Contents

| File | What it contains |
|---|---|
| `distributed-report.md` | **The write-up:** architecture, results R1–R6, CAP/PACELC analysis, sharding design and trade-offs, cloud deployment plan |
| `scripts/setup_cluster.sh` | Creates the 4 PostgreSQL instances (ports 5601–5604) and the standby |
| `scripts/stop_cluster.sh` | Stops them all |
| `scripts/replication_demo.py` | Scenarios R1–R6: status, replication delay, read-only standby, synchronous commit, standby failure, failover |
| `sql/01_shard_node.sql` | Table created on each shard server |
| `sql/02_coordinator.sql` | `postgres_fdw` servers, the region-partitioned distributed table, and loading |
| `sql/03_sharding_queries.sql` | Distribution, pruning, scatter-gather, aggregate pushdown, insert routing, skew check |
| `scripts/atlas_replica_check.py` | Cloud evidence: Atlas replica set members, secondary reads, `w=1` vs `w="majority"` |
| `results/replication_demo.log` | Output of R1–R6 |
| `results/02_coordinator.log`, `results/03_sharding_queries.log`, `results/shard_nodes.log` | Sharding output |
| `screenshots/` | Evidence from your own machine |

## Key Results

| Demo | Result |
|---|---|
| Asynchronous replication | Standby 6.26 ms behind (median); every immediate replica read was stale |
| Synchronous (`remote_apply`) | No stale reads; commits 1.3× slower |
| Standby down, synchronous | Writes **blocked** (consistency chosen over availability) |
| Failover | No data lost; writes accepted 0.76 s after the primary crashed |
| Sharding by region | SOUTH 3,682 / others 2,370; Texas queries read only one shard; totals identical to the single database |

## How to Run

This needs **Linux, macOS or Windows with WSL** (Windows Subsystem for Linux). On Windows, install WSL and Ubuntu (`wsl --install -d Ubuntu`), then inside Ubuntu:

```bash
sudo apt update && sudo apt install -y postgresql-18 python3-psycopg2 python3-pandas python3-numpy python3-pil python3-pymongo fonts-dejavu-core
```

The cluster uses ports 5601–5604, so Ubuntu's own PostgreSQL on 5432 can keep running.

**In WSL, keep the cluster folder in Linux** (for example `~/pipesafe-cluster`), not under `/mnt/c/...`. PostgreSQL refuses data folders on a Windows drive because their permissions cannot be restricted. `run_and_capture.py --portfolios 5` does this automatically.

```bash
cd portfolio-5-distributed-cloud
CLUSTER=~/pipesafe-cluster   # in WSL: a Linux folder, not /mnt/c/...

# 1. Build the cluster (pauses so you can load the data into the primary)
PG_BIN=/usr/lib/postgresql/18/bin ./scripts/setup_cluster.sh $CLUSTER
#    In a second terminal, from portfolio-1-database-design:
#      psql -h /tmp -p 5601 -U postgres -d pipesafe -f sql/01_create_tables.sql
#      psql -h /tmp -p 5601 -U postgres -d pipesafe -f sql/02_load_data.sql
#    then press Enter in the first terminal.

# 2. Sharding (run BEFORE step 3, because step 3 crashes the primary on purpose)
psql -h /tmp -p 5603 -U postgres -d pipesafe_shard -f sql/01_shard_node.sql
psql -h /tmp -p 5604 -U postgres -d pipesafe_shard -f sql/01_shard_node.sql
psql -h /tmp -p 5601 -U postgres -d pipesafe -f sql/02_coordinator.sql
psql -h /tmp -p 5601 -U postgres -d pipesafe -e -f sql/03_sharding_queries.sql

# 3. Replication, consistency and failover
python scripts/replication_demo.py $CLUSTER /usr/lib/postgresql/18/bin /tmp

# 4. Stop everything (rm -rf $CLUSTER to start again from scratch)
./scripts/stop_cluster.sh $CLUSTER
```

Change `/usr/lib/postgresql/18/bin` to your PostgreSQL version. After step 3 the old primary is permanently replaced, so rebuild the cluster to run it again.

**Cloud evidence (MongoDB Atlas, from Portfolio 4):**
```bash
python scripts/atlas_replica_check.py "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/"
```

## Screenshots to Take

1. `SELECT * FROM pg_stat_replication;` on port 5601, and `SELECT pg_is_in_recovery();` on 5602.
2. The terminal output of `replication_demo.py`, especially R5 (blocked commit) and R6 (failover).
3. The two `EXPLAIN` outputs from `03_sharding_queries.sql`: the single-shard Texas query, and the pushed-down `GROUP BY`.
4. Atlas: **Overview** page showing the 3 replica set members, plus the output of `atlas_replica_check.py`.
