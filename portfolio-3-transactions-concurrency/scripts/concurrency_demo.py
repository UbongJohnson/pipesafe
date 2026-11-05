"""
Portfolio 3: two-session concurrency demonstrations for PipeSafe Analytics.

Two database sessions, A and B, act like two investigators updating the same
open accident report at the same time. Steps run in a fixed order, so every
run shows the same interleaving. Steps that must wait for a lock run in a
background thread, so the waiting is visible in the log.

Scenarios
  1. Non-repeatable read: READ COMMITTED vs REPEATABLE READ
  2. Phantom read:        READ COMMITTED vs REPEATABLE READ
  3. Lost update (the problem)
  4. Fix 1: pessimistic locking with SELECT ... FOR UPDATE
  5. Fix 2: REPEATABLE READ, which detects the conflict, then retries
  6. Fix 3: a single atomic UPDATE (no read-modify-write)
  7. A CHECK constraint stopping an over-recovery that locking exposes
  8. Deadlock (the problem)
  9. Fix: lock rows in a consistent order

Usage (run 00_setup_test_data.sql first):
    python scripts/concurrency_demo.py "dbname=pipesafe user=postgres host=localhost"
Writes the full transcript to results/concurrency_demo.log
"""
import os, sys, threading, time
import psycopg2

DSN = sys.argv[1] if len(sys.argv) > 1 else "dbname=pipesafe"
R1, R2 = 99990001, 99990002          # test reports from 00_setup_test_data.sql
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(os.path.dirname(HERE), "results", "concurrency_demo.log")
log_lock = threading.Lock()
log_lines = []
t0 = time.time()


def log(text=""):
    with log_lock:
        print(text)
        log_lines.append(text)


class Session:
    def __init__(self, name):
        self.name = name
        self.conn = psycopg2.connect(DSN)
        self.conn.autocommit = True           # we send BEGIN / COMMIT ourselves
        self.cur = self.conn.cursor()
        self.cur.execute("SET search_path TO pipesafe")
        self.cur.execute("SET deadlock_timeout = '1s'")

    def run(self, sql, show=True):
        """Run one statement and log it with its result or error."""
        stamp = f"{time.time() - t0:6.2f}s"
        log(f"[{stamp}] {self.name}> {sql}")
        try:
            self.cur.execute(sql)
            result = None
            if self.cur.description:
                result = self.cur.fetchall()
                if show:
                    value = result[0][0] if len(result) == 1 and len(result[0]) == 1 else result
                    log(f"           {self.name}  -> {value}")
            else:
                log(f"           {self.name}  -> {self.cur.statusmessage}")
            return result
        except psycopg2.Error as e:
            log(f"           {self.name}  -> {e.pgerror.strip().splitlines()[0]}")
            return e

    def close(self):
        self.conn.close()


def in_background(fn):
    """Run a step that may block on a lock; return the thread."""
    t = threading.Thread(target=fn)
    t.start()
    return t


def reset(admin):
    admin.cur.execute(f"UPDATE accident SET recovered_bbls = 300 WHERE report_number IN ({R1}, {R2})")
    admin.cur.execute("DELETE FROM accident WHERE report_number = 99990020")


def header(n, title, explanation):
    global t0
    t0 = time.time()
    log("\n" + "=" * 78)
    log(f"SCENARIO {n}: {title}")
    log(explanation)
    log("=" * 78)


def final_value(admin, note):
    admin.cur.execute(f"SELECT recovered_bbls FROM accident WHERE report_number = {R1}")
    v = admin.cur.fetchone()[0]
    log(f"RESULT: recovered_bbls for {R1} = {v}  ({note})")
    return v


SELECT_REC = f"SELECT recovered_bbls FROM accident WHERE report_number = {R1}"


def scenario_non_repeatable_read(admin, A, B):
    for level in ["READ COMMITTED", "REPEATABLE READ"]:
        reset(admin)
        header("1" + ("a" if level == "READ COMMITTED" else "b"),
               f"Non-repeatable read under {level}",
               "A reads the same report twice. B changes it in between and commits.")
        A.run(f"BEGIN ISOLATION LEVEL {level}")
        first = A.run(SELECT_REC)[0][0]
        B.run(f"UPDATE accident SET recovered_bbls = 350 WHERE report_number = {R1}")
        second = A.run(SELECT_REC)[0][0]
        A.run("COMMIT")
        same = "SAME value both times (stable snapshot)" if first == second else "DIFFERENT values in one transaction"
        log(f"RESULT: A saw {first} then {second} -> {same}")


def scenario_phantom(admin, A, B):
    count_sql = "SELECT COUNT(*) FROM accident WHERE operator_id = 31684 AND report_type = 'ORIGINAL'"
    for level in ["READ COMMITTED", "REPEATABLE READ"]:
        reset(admin)
        header("2" + ("a" if level == "READ COMMITTED" else "b"),
               f"Phantom read under {level}",
               "A counts an operator's open reports twice. B files a new report in between.")
        A.run(f"BEGIN ISOLATION LEVEL {level}")
        first = A.run(count_sql)[0][0]
        B.run("INSERT INTO accident (report_number, report_type, report_received_date, operator_id, "
              "on_off_shore, latitude, longitude, accident_datetime, pipe_facility_type, system_part_id, "
              "item_involved_id, commodity_subtype_id, release_type, unintentional_release_bbls, "
              f"recovered_bbls, cause_detail_id, narrative) SELECT 99990020, 'ORIGINAL', report_received_date, "
              "operator_id, on_off_shore, latitude, longitude, accident_datetime, pipe_facility_type, "
              "system_part_id, item_involved_id, commodity_subtype_id, release_type, 10, 0, cause_detail_id, "
              f"'TEST REPORT - phantom demo' FROM accident WHERE report_number = {R1}")
        second = A.run(count_sql)[0][0]
        A.run("COMMIT")
        log(f"RESULT: A counted {first} then {second} -> "
            + ("a new 'phantom' row appeared" if first != second else "no phantom (stable snapshot)"))


def scenario_lost_update(admin, A, B):
    reset(admin)
    header(3, "LOST UPDATE (the problem)",
           "Two investigators each read the recovered volume (300 bbl), add the oil THEY\n"
           "recovered (A: +50, B: +30) in their application, and write the total back.\n"
           "Correct final value: 300 + 50 + 30 = 380.")
    A.run("BEGIN")
    B.run("BEGIN")
    a_val = A.run(SELECT_REC)[0][0]
    b_val = B.run(SELECT_REC)[0][0]
    A.run(f"UPDATE accident SET recovered_bbls = {a_val + 50} WHERE report_number = {R1}")
    A.run("COMMIT")
    B.run(f"UPDATE accident SET recovered_bbls = {b_val + 30} WHERE report_number = {R1}")
    B.run("COMMIT")
    final_value(admin, "WRONG - A's 50 barrels were silently overwritten")


def scenario_for_update(admin, A, B):
    reset(admin)
    header(4, "FIX 1: SELECT ... FOR UPDATE (pessimistic locking)",
           "Each session locks the row when it reads it. B must wait until A commits,\n"
           "then reads A's new value.")
    A.run("BEGIN")
    a_val = A.run(SELECT_REC + " FOR UPDATE")[0][0]
    B.run("BEGIN")
    box = {}

    def b_steps():
        start = time.time()
        b_val = B.run(SELECT_REC + " FOR UPDATE")[0][0]     # blocks until A commits
        box["waited"] = time.time() - start
        B.run(f"UPDATE accident SET recovered_bbls = {b_val + 30} WHERE report_number = {R1}")
        B.run("COMMIT")

    t = in_background(b_steps)
    time.sleep(2)                                              # A is still working...
    log("           (B is blocked, waiting for A's lock)")
    A.run(f"UPDATE accident SET recovered_bbls = {a_val + 50} WHERE report_number = {R1}")
    A.run("COMMIT")
    t.join()
    log(f"B waited {box['waited']:.2f} s for the lock")
    final_value(admin, "CORRECT - both updates kept")


def scenario_repeatable_read(admin, A, B):
    reset(admin)
    header(5, "FIX 2: REPEATABLE READ detects the conflict (optimistic approach)",
           "No locks are taken when reading. PostgreSQL refuses B's write because the\n"
           "row changed after B's snapshot. The application retries B's transaction.")
    A.run("BEGIN ISOLATION LEVEL REPEATABLE READ")
    B.run("BEGIN ISOLATION LEVEL REPEATABLE READ")
    a_val = A.run(SELECT_REC)[0][0]
    b_val = B.run(SELECT_REC)[0][0]
    A.run(f"UPDATE accident SET recovered_bbls = {a_val + 50} WHERE report_number = {R1}")
    A.run("COMMIT")
    B.run(f"UPDATE accident SET recovered_bbls = {b_val + 30} WHERE report_number = {R1}")
    B.run("ROLLBACK")
    log("           (application catches the serialization error and retries B)")
    B.run("BEGIN ISOLATION LEVEL REPEATABLE READ")
    b_val = B.run(SELECT_REC)[0][0]
    B.run(f"UPDATE accident SET recovered_bbls = {b_val + 30} WHERE report_number = {R1}")
    B.run("COMMIT")
    final_value(admin, "CORRECT - conflict detected, retry applied")


def scenario_atomic_update(admin, A, B):
    reset(admin)
    header(6, "FIX 3: one atomic UPDATE (no read-modify-write)",
           "The addition happens inside the database: SET recovered = recovered + n.\n"
           "B's UPDATE waits for A's row lock, then re-reads the latest committed value.")
    A.run("BEGIN")
    A.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 50 WHERE report_number = {R1}")
    B.run("BEGIN")

    def b_steps():
        B.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 30 WHERE report_number = {R1}")
        B.run("COMMIT")

    t = in_background(b_steps)
    time.sleep(1.5)
    log("           (B is blocked, waiting for A's row lock)")
    A.run("COMMIT")
    t.join()
    final_value(admin, "CORRECT - both increments applied")


def scenario_check_constraint(admin, A, B):
    reset(admin)
    header(7, "Locking + CHECK constraint stop an impossible total",
           "500 bbl were released and 300 recovered. A records +150 and B records +100,\n"
           "which together would exceed what was released. With locking, B sees A's\n"
           "value and the CHECK (recovered <= released) rejects B's update.")
    A.run("BEGIN")
    a_val = A.run(SELECT_REC + " FOR UPDATE")[0][0]
    B.run("BEGIN")

    def b_steps():
        b_val = B.run(SELECT_REC + " FOR UPDATE")[0][0]
        B.run(f"UPDATE accident SET recovered_bbls = {b_val + 100} WHERE report_number = {R1}")
        B.run("ROLLBACK")

    t = in_background(b_steps)
    time.sleep(1.5)
    A.run(f"UPDATE accident SET recovered_bbls = {a_val + 150} WHERE report_number = {R1}")
    A.run("COMMIT")
    t.join()
    final_value(admin, "consistent - B's impossible update was refused and must be checked by B")
    log("Without locking, B would have written 300 + 100 = 400, silently losing A's 150 bbl\n"
        "and passing the CHECK. The constraint is only reliable when updates are serialised.")


def scenario_deadlock(admin, A, B):
    reset(admin)
    header(8, "DEADLOCK (the problem)",
           f"A updates report {R1} then {R2}. B updates the same two reports in the\n"
           "OPPOSITE order. Each ends up waiting for a row the other has locked.")
    A.run("BEGIN")
    B.run("BEGIN")
    A.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R1}")
    B.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R2}")
    outcome = {}

    def a_steps():
        outcome["A"] = A.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R2}")

    def b_steps():
        outcome["B"] = B.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R1}")

    ta = in_background(a_steps)
    time.sleep(0.3)
    tb = in_background(b_steps)
    ta.join(); tb.join()
    for s in (A, B):
        failed = isinstance(outcome[s.name], psycopg2.Error)
        s.run("ROLLBACK" if failed else "COMMIT")
    victim = [n for n, r in outcome.items() if isinstance(r, psycopg2.Error)]
    log(f"RESULT: PostgreSQL detected the deadlock after deadlock_timeout (1 s) and "
        f"cancelled session {', '.join(victim)} so the other could finish.")


def scenario_ordered_locks(admin, A, B):
    reset(admin)
    header(9, "FIX: lock rows in a consistent order",
           "Both sessions lock BOTH reports first, always in report_number order.\n"
           "B simply waits for A instead of deadlocking.")
    lock_sql = (f"SELECT report_number FROM accident WHERE report_number IN ({R1}, {R2}) "
                "ORDER BY report_number FOR UPDATE")
    A.run("BEGIN")
    A.run(lock_sql)
    B.run("BEGIN")

    def b_steps():
        B.run(lock_sql)                                         # waits for A
        B.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R2}")
        B.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R1}")
        B.run("COMMIT")

    t = in_background(b_steps)
    time.sleep(1.5)
    A.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R1}")
    A.run(f"UPDATE accident SET recovered_bbls = recovered_bbls + 1 WHERE report_number = {R2}")
    A.run("COMMIT")
    t.join()
    admin.cur.execute(f"SELECT report_number, recovered_bbls FROM accident "
                      f"WHERE report_number IN ({R1}, {R2}) ORDER BY 1")
    values = ", ".join(f"{r} = {v}" for r, v in admin.cur.fetchall())
    log(f"RESULT: {values} - no deadlock, both sessions' changes applied (300 + 1 + 1)")


def main():
    admin = Session("admin")
    A, B = Session("A"), Session("B")
    log(f"PipeSafe concurrency demonstrations - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    admin.cur.execute("SELECT version()")
    log(admin.cur.fetchone()[0])
    for scenario in [scenario_non_repeatable_read, scenario_phantom, scenario_lost_update,
                     scenario_for_update, scenario_repeatable_read, scenario_atomic_update,
                     scenario_check_constraint, scenario_deadlock, scenario_ordered_locks]:
        scenario(admin, A, B)
    reset(admin)
    for s in (A, B, admin):
        s.close()
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"\nTranscript saved to {LOG_PATH}")


if __name__ == "__main__":
    main()
