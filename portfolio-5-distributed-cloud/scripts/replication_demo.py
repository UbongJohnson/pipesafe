"""
Portfolio 5: replication, consistency, availability and failover demos.

Needs the cluster from setup_cluster.sh (primary on 5601, standby on 5602,
with pipesafe loaded). Must be run by the user that owns the cluster
folders, because it stops, starts and promotes servers with pg_ctl.

Scenarios
  R1  Replication status
  R2  Asynchronous replication: how long until a write is visible on the standby
  R3  The standby is read-only
  R4  Synchronous replication (remote_apply): no stale reads, but slower commits
  R5  Availability vs consistency: what happens when the standby is down
  R6  Failover: the primary crashes, the standby is promoted

WARNING: R6 stops the primary for good. To run again, rebuild the cluster.

Usage:
    python scripts/replication_demo.py ./cluster [/usr/lib/postgresql/16/bin] [/tmp]
Writes results/replication_demo.log
"""
import os, statistics, subprocess, sys, threading, time
import psycopg2

BASE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "./cluster")
PG_BIN = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(
    subprocess.run(["which", "pg_ctl"], capture_output=True, text=True).stdout.strip())
SOCK = sys.argv[3] if len(sys.argv) > 3 else "/tmp"
PRIMARY, STANDBY = 5601, 5602
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(HERE), "results", "replication_demo.log")
lines = []
TEST_BASE = 99996000                    # test report numbers (not real PHMSA reports)


def log(text=""):
    print(text)
    lines.append(str(text))


def header(code, title, text=""):
    log("\n" + "=" * 78)
    log(f"{code}: {title}")
    if text:
        log(text)
    log("=" * 78)


def connect(port, autocommit=True):
    conn = psycopg2.connect(host=SOCK, port=port, user="postgres", dbname="pipesafe",
                            connect_timeout=3)
    conn.autocommit = autocommit
    return conn


def q(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else cur.statusmessage


def pg_ctl(*args):
    r = subprocess.run([os.path.join(PG_BIN, "pg_ctl"), *args], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def stop(node, mode="fast"):
    return pg_ctl("-D", os.path.join(BASE, node), "-m", mode, "-w", "stop")


def start(node, port):
    return pg_ctl("-D", os.path.join(BASE, node), "-o", f"-p {port} -k {SOCK} -c listen_addresses=''",
                  "-l", os.path.join(BASE, node + ".log"), "-w", "start")


# INSERT ... SELECT that copies a real accident under a new (test) report number
def build_copy_sql(conn):
    cols = [r[0] for r in q(conn, """SELECT column_name FROM information_schema.columns
             WHERE table_schema = 'pipesafe' AND table_name = 'accident' ORDER BY ordinal_position""")]
    rest = ", ".join(cols[1:])
    return (f"INSERT INTO pipesafe.accident ({', '.join(cols)}) "
            f"SELECT %s, {rest} FROM pipesafe.accident WHERE report_number = 20260244")


def visible_on_standby(sb, report):
    return q(sb, "SELECT 1 FROM pipesafe.accident WHERE report_number = %s", (report,)) != []


def measure_visibility(pr, sb, copy_sql, start_no, n=20):
    """Insert n rows on the primary; for each, check the standby immediately,
    then poll until visible. Returns (immediate misses, list of ms to visible)."""
    misses, delays = 0, []
    for i in range(n):
        report = start_no + i
        q(pr, copy_sql, (report,))                       # autocommit: committed on return
        t = time.perf_counter()
        if not visible_on_standby(sb, report):
            misses += 1
            while not visible_on_standby(sb, report):
                time.sleep(0.0005)
        delays.append((time.perf_counter() - t) * 1000)
    return misses, delays


def commit_latency(pr, copy_sql, start_no, n=50):
    times = []
    for i in range(n):
        t = time.perf_counter()
        q(pr, copy_sql, (start_no + i,))
        times.append((time.perf_counter() - t) * 1000)
    return statistics.median(times)


def main():
    pr, sb = connect(PRIMARY), connect(STANDBY)
    copy_sql = build_copy_sql(pr)
    q(pr, f"DELETE FROM pipesafe.accident WHERE report_number BETWEEN {TEST_BASE} AND {TEST_BASE + 999}")
    log(f"PipeSafe replication demonstrations - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(q(pr, "SELECT version()")[0][0])

    # ------------------------------------------------------------------ R1
    header("R1", "Replication status")
    for name, c in [("primary", pr), ("standby", sb)]:
        rec, n, cost = q(c, """SELECT pg_is_in_recovery(), COUNT(*), SUM(total_cost_usd)
                               FROM pipesafe.v_accident_summary""")[0]
        log(f"{name:8s} port {c.info.port}: in recovery (read-only replica) = {rec}, "
            f"accidents = {n}, total cost = {cost}")
    for row in q(pr, "SELECT application_name, client_addr, state, sync_state FROM pg_stat_replication"):
        log(f"primary sees replica: application={row[0]} state={row[2]} sync_state={row[3]}")

    # ------------------------------------------------------------------ R2
    header("R2", "Asynchronous replication: time until a write is visible on the standby",
           "20 accident reports are inserted on the primary. After each COMMIT the standby is\n"
           "read immediately, then polled until the new report appears.")
    misses, delays = measure_visibility(pr, sb, copy_sql, TEST_BASE)
    log(f"Immediate read on standby missed the new row: {misses} of 20 times (stale reads)")
    log(f"Time until visible on standby: median {statistics.median(delays):.2f} ms, "
        f"max {max(delays):.2f} ms")

    # ------------------------------------------------------------------ R3
    header("R3", "The standby is read-only")
    try:
        q(sb, copy_sql, (TEST_BASE + 900,))
    except psycopg2.Error as e:
        log(f"INSERT on standby -> {e.pgerror.strip().splitlines()[0]}")

    # ------------------------------------------------------------------ R4
    header("R4", "Synchronous replication (synchronous_commit = remote_apply)",
           "COMMIT on the primary now waits until the standby has APPLIED the change.")
    async_ms = commit_latency(pr, copy_sql, TEST_BASE + 100)
    q(pr, "ALTER SYSTEM SET synchronous_standby_names = '*'")
    q(pr, "ALTER SYSTEM SET synchronous_commit = 'remote_apply'")
    q(pr, "SELECT pg_reload_conf()")
    time.sleep(1)
    pr.close(); pr = connect(PRIMARY)
    log("sync_state now: " + str(q(pr, "SELECT sync_state FROM pg_stat_replication")[0][0]))
    sync_ms = commit_latency(pr, copy_sql, TEST_BASE + 200)
    misses_sync, delays_sync = measure_visibility(pr, sb, copy_sql, TEST_BASE + 300)
    log(f"Median single-insert commit time: asynchronous {async_ms:.2f} ms, "
        f"synchronous (remote_apply) {sync_ms:.2f} ms  ({sync_ms / async_ms:.1f}x slower)")
    log(f"Immediate read on standby missed the new row: {misses_sync} of 20 times")

    # ------------------------------------------------------------------ R5
    header("R5", "Availability vs consistency: the standby goes down",
           "With synchronous replication, a COMMIT cannot finish without the standby.")
    log("stopping standby: " + stop("standby").splitlines()[-1])
    pr.notices.clear()
    pid = q(pr, "SELECT pg_backend_pid()")[0][0]
    outcome = {}

    def write():
        t = time.perf_counter()
        try:
            q(pr, copy_sql, (TEST_BASE + 500,))
            outcome["result"] = "committed"
        except psycopg2.Error as e:
            outcome["result"] = e.pgerror.strip()
        outcome["seconds"] = time.perf_counter() - t

    th = threading.Thread(target=write); th.start()
    time.sleep(5)
    log(f"after 5 s the INSERT is still waiting: {th.is_alive()}")
    admin = connect(PRIMARY)
    q(admin, "SELECT pg_cancel_backend(%s)", (pid,))
    th.join()
    log(f"cancelled after {outcome['seconds']:.1f} s")
    for n in pr.notices:
        log("server said: " + n.strip())
    on_primary = q(admin, "SELECT COUNT(*) FROM pipesafe.accident WHERE report_number = %s",
                   (TEST_BASE + 500,))[0][0]
    log(f"row exists on primary: {on_primary == 1} (committed locally, NOT confirmed on any replica)")
    log("\nChoosing availability instead: switch back to asynchronous replication")
    q(admin, "ALTER SYSTEM RESET synchronous_standby_names")
    q(admin, "ALTER SYSTEM RESET synchronous_commit")
    q(admin, "SELECT pg_reload_conf()")
    time.sleep(1)
    pr.close(); pr = connect(PRIMARY)
    t = time.perf_counter()
    q(pr, copy_sql, (TEST_BASE + 501,))
    log(f"INSERT with the standby still down: committed in {(time.perf_counter() - t) * 1000:.1f} ms")
    log("restarting standby: " + start("standby", STANDBY).splitlines()[-1])
    sb = connect(STANDBY)
    t = time.perf_counter()
    while not visible_on_standby(sb, TEST_BASE + 501):
        time.sleep(0.01)
    log(f"standby caught up with the writes it missed in {(time.perf_counter() - t) * 1000:.0f} ms "
        f"(both test rows present: {visible_on_standby(sb, TEST_BASE + 500) and visible_on_standby(sb, TEST_BASE + 501)})")

    # ------------------------------------------------------------------ R6
    header("R6", "Failover: the primary crashes and the standby is promoted")
    q(pr, copy_sql, (TEST_BASE + 600,))
    while not visible_on_standby(sb, TEST_BASE + 600):
        time.sleep(0.01)
    before = q(sb, "SELECT COUNT(*) FROM pipesafe.accident")[0][0]
    log(f"last report written before the crash: {TEST_BASE + 600} (replicated). Accidents on standby: {before}")
    pr.close()
    log("crash primary (immediate stop): " + stop("primary", "immediate").splitlines()[-1])
    t_down = time.perf_counter()
    try:
        connect(PRIMARY)
    except psycopg2.OperationalError as e:
        log("connect to primary -> " + str(e).strip().splitlines()[0])
    try:
        q(sb, copy_sql, (TEST_BASE + 601,))
    except psycopg2.Error as e:
        log("write to standby before promotion -> " + e.pgerror.strip().splitlines()[0])
    log("promote standby: SELECT pg_promote() -> " + str(q(sb, "SELECT pg_promote(wait => true)")[0][0]))
    sb.close(); sb = connect(STANDBY)
    q(sb, copy_sql, (TEST_BASE + 601,))
    log(f"write on the NEW primary (port {STANDBY}) succeeded "
        f"{(time.perf_counter() - t_down):.2f} s after the crash")
    rec, n, has_last = q(sb, f"""SELECT pg_is_in_recovery(), COUNT(*),
                                 bool_or(report_number = {TEST_BASE + 600}) FROM pipesafe.accident""")[0]
    log(f"new primary: in recovery = {rec}, accidents = {n}, last pre-crash report present = {has_last}")

    q(sb, f"DELETE FROM pipesafe.accident WHERE report_number BETWEEN {TEST_BASE} AND {TEST_BASE + 999}")
    log(f"test rows removed; accidents now {q(sb, 'SELECT COUNT(*) FROM pipesafe.accident')[0][0]}")
    sb.close()
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nsaved to", LOG)


if __name__ == "__main__":
    main()
