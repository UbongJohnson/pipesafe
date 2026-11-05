"""
Portfolio 2 benchmark: runs the eight queries before and after optimisation,
on the real data (schema pipesafe) and the 100x scaled copy (schema bench).

For each query and phase it:
  * runs the query twice to warm the cache,
  * runs EXPLAIN (ANALYZE, BUFFERS) 7 times and keeps the median execution time,
  * saves the full text plan to results/<schema>_<phase>_Q<n>.txt,
  * checks the optimised query returns exactly the same rows as the original.

Usage:
    python scripts/benchmark.py "dbname=pipesafe user=postgres host=localhost"
Run from the portfolio-2-query-optimisation folder.
"""
import json, re, statistics, sys, csv, os
import psycopg2

DSN = sys.argv[1] if len(sys.argv) > 1 else "dbname=pipesafe"
RUNS = 7
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
os.makedirs(RESULTS, exist_ok=True)

def load_queries(path):
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^-- (Q\d+b?)\b", text, flags=re.M)[1:]
    queries = {}
    for i in range(0, len(parts), 2):
        body = parts[i + 1].split("\n", 1)[1]          # drop rest of the "-- Qn." title line
        sql = "\n".join(l for l in body.splitlines() if not l.strip().startswith("--")).strip()
        queries[parts[i]] = sql.rstrip(";").strip()
    return queries

def run_sql_file(cur, path):
    cur.execute(open(path, encoding="utf-8").read())

def scans_on(plan, table="accident"):
    """List the scan types used on a table, e.g. ['Seq Scan']."""
    found = []
    def walk(node):
        if node.get("Relation Name") == table:
            found.append(node["Node Type"] + (f" ({node['Index Name']})" if "Index Name" in node else ""))
        for child in node.get("Plans", []):
            walk(child)
    walk(plan)
    return sorted(set(found))

def measure(cur, sql):
    for _ in range(2):                                       # warm-up
        cur.execute(sql); cur.fetchall()
    times, plan = [], None
    for _ in range(RUNS):
        cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
        result = cur.fetchone()[0][0]
        times.append(result["Execution Time"])
        plan = result["Plan"]
    cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql)
    text_plan = "\n".join(r[0] for r in cur.fetchall())
    cur.execute(sql)
    rows = sorted(map(repr, cur.fetchall()))
    return statistics.median(times), plan, text_plan, rows

def main():
    before = load_queries(os.path.join(ROOT, "queries.sql"))
    after = load_queries(os.path.join(ROOT, "queries_optimised.sql"))
    conn = psycopg2.connect(DSN); conn.autocommit = True
    cur = conn.cursor()
    rows_out = []
    for schema in ["pipesafe", "bench"]:
        cur.execute(f"SET search_path TO {schema}, public")
        for phase, queries, setup in [("before", before, "03_undo.sql"),
                                      ("after", after, "02_optimise.sql")]:
            run_sql_file(cur, os.path.join(ROOT, "sql", setup))
            cur.execute("CHECKPOINT")
            for q, sql in queries.items():
                ms, plan, text_plan, rows = measure(cur, sql)
                with open(os.path.join(RESULTS, f"{schema}_{phase}_{q}.txt"), "w") as f:
                    f.write(f"-- {schema} / {phase} / {q}\n{sql};\n\n{text_plan}\n")
                rows_out.append({"schema": schema, "phase": phase, "query": q,
                                 "median_ms": round(ms, 2), "rows": len(rows),
                                 "accident_scan": "; ".join(scans_on(plan)),
                                 "result_hash": hash(tuple(rows))})
                print(f"{schema:9s} {phase:6s} {q}: {ms:9.2f} ms  {len(rows):6d} rows  {scans_on(plan)}")
        # cost of keeping the materialised view up to date
        times = []
        for _ in range(3):
            cur.execute("SELECT clock_timestamp()"); t0 = cur.fetchone()[0]
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_accident_totals")
            cur.execute("SELECT clock_timestamp()"); t1 = cur.fetchone()[0]
            times.append((t1 - t0).total_seconds() * 1000)
        refresh_ms = statistics.median(times)
        rows_out.append({"schema": schema, "phase": "refresh", "query": "REFRESH mv_accident_totals",
                         "median_ms": round(refresh_ms, 2), "rows": "", "accident_scan": "", "result_hash": None})
        print(f"{schema:9s} REFRESH MATERIALIZED VIEW CONCURRENTLY: {refresh_ms:.0f} ms")
    # leave the database in the optimised state
    with open(os.path.join(RESULTS, "timings.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["schema", "phase", "query", "median_ms", "rows", "accident_scan"])
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r[k] for k in w.fieldnames})
    # same rows before and after?
    print("\nResult check (optimised query returns identical rows):")
    for schema in ["pipesafe", "bench"]:
        for q in before:
            b = next(r for r in rows_out if r["schema"] == schema and r["phase"] == "before" and r["query"] == q)
            for a in [r for r in rows_out if r["schema"] == schema and r["phase"] == "after" and r["query"][:2] == q]:
                print(f"  {schema:9s} {a['query']:3s} vs {q}: {'identical' if a['result_hash'] == b['result_hash'] else 'DIFFERENT'}")

if __name__ == "__main__":
    main()
