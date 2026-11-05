"""
run_and_capture.py - runs the portfolio steps on YOUR computer and saves a
screenshot (PNG) of each step's output, plus the raw text.

Every image is stamped with your user name, computer name, operating system
and the date and time it was produced, so it is evidence from your own run.

Install once:   pip install psycopg2-binary pymongo pandas numpy pillow

Windows (Portfolios 1-4), from the repository folder:
    python run_and_capture.py --portfolios 1,2,3,4 ^
        --data "C:\\path\\to\\accident_hazardous_liquid_jan2010_present.txt" ^
        --password YOUR_POSTGRES_PASSWORD ^
        --mongo "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/"

WSL / Linux (Portfolio 5 needs Linux):
    python3 run_and_capture.py --portfolios 5 \\
        --data /mnt/c/path/to/accident_hazardous_liquid_jan2010_present.txt \\
        --pg-bin /usr/lib/postgresql/18/bin

Options:
    --host / --port / --user / --password / --dbname   PostgreSQL connection (Portfolios 1-3)
    --mongo URI          MongoDB Atlas connection string (Portfolio 4; skipped if missing)
    --pg-bin FOLDER      PostgreSQL programs folder (Portfolio 5)

Output: <portfolio>/screenshots/NN_name.png (+ .txt), and fresh results/ files.
Portfolio 1 creates the pipesafe database if it does not exist, then REBUILDS
it from the raw file. Portfolios 2 and 3 need Portfolio 1's data already loaded.
"""
import argparse, datetime, getpass, glob, os, platform, re, shutil, socket, subprocess, sys, textwrap

ROOT = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.join(ROOT, "portfolio-1-database-design")
P2 = os.path.join(ROOT, "portfolio-2-query-optimisation")
P3 = os.path.join(ROOT, "portfolio-3-transactions-concurrency")
P4 = os.path.join(ROOT, "portfolio-4-nosql")
P5 = os.path.join(ROOT, "portfolio-5-distributed-cloud")
PY = sys.executable
STAMP = (f"{getpass.getuser()}@{socket.gethostname()} | {platform.system()} {platform.release()} | "
         f"Python {platform.python_version()}")

# ------------------------------------------------------------------ images
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Pillow is missing. Run:  pip install pillow")


def load_font(size):
    for path in [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                 "/System/Library/Fonts/Menlo.ttc"]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT, FONT_BOLD = load_font(15), load_font(16)
WRAP, PAGE = 150, 60          # characters per line, lines per image


def render(title, command, text, png_path):
    """Draw a terminal-style image. Long output is split over several images."""
    lines = []
    for raw in text.replace("\t", "    ").splitlines() or [""]:
        lines.extend(textwrap.wrap(raw, WRAP, replace_whitespace=False, drop_whitespace=False) or [""])
    pages = [lines[i:i + PAGE] for i in range(0, len(lines), PAGE)] or [[]]
    char_w = FONT.getlength("M")
    line_h = 19
    paths = []
    for n, page in enumerate(pages, 1):
        header = [f"{title}" + (f"  (page {n} of {len(pages)})" if len(pages) > 1 else ""),
                  f"{STAMP} | {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"]
        cmd = [f"> {c}" for c in textwrap.wrap(command, WRAP)]
        width_chars = max([len(l) for l in page + header + cmd] + [60])
        w = int(width_chars * char_w) + 40
        h = 20 + 2 * 22 + 12 + len(cmd) * line_h + 10 + len(page) * line_h + 20
        img = Image.new("RGB", (w, h), "#1e1e1e")
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 20 + 2 * 22 + 4], fill="#2d2d30")
        d.text((20, 12), header[0], font=FONT_BOLD, fill="#ffffff")
        d.text((20, 34), header[1], font=FONT, fill="#9cdcfe")
        y = 20 + 2 * 22 + 12
        for c in cmd:
            d.text((20, y), c, font=FONT, fill="#6a9955"); y += line_h
        y += 10
        for l in page:
            colour = "#f48771" if ("ERROR" in l or "FAILED" in l or "DIFFERENT" in l) else "#d4d4d4"
            d.text((20, y), l, font=FONT, fill=colour); y += line_h
        out = png_path if len(pages) == 1 else png_path.replace(".png", f"_p{n}.png")
        img.save(out)
        paths.append(out)
    return paths


# ------------------------------------------------------------------ running steps
class Runner:
    def __init__(self, args):
        self.args = args
        self.env = dict(os.environ, PGPASSWORD=args.password or "", PGCLIENTENCODING="UTF8",
                        PYTHONIOENCODING="utf-8")
        self.counter = {}
        self.failures = []

    def psql_path(self):
        found = shutil.which("psql")
        if found:
            return found
        def version(path):          # newest install first: 18 before 9
            v = os.path.basename(os.path.dirname(os.path.dirname(path)))
            return int(v) if v.isdigit() else 0
        for path in sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin\psql.exe"), key=version, reverse=True):
            return path
        if self.args.pg_bin and os.path.exists(os.path.join(self.args.pg_bin, "psql")):
            return os.path.join(self.args.pg_bin, "psql")
        sys.exit("psql not found. Add PostgreSQL's bin folder to PATH or use --pg-bin.")

    def psql(self, *extra, port=None, db=None):
        a = self.args
        return [self.psql_path(), "-h", a.host, "-p", str(port or a.port), "-U", a.user,
                "-d", db or a.dbname, "-X", "-w", "-v", "ON_ERROR_STOP=0", *extra]   # -w: never wait at a password prompt

    def dsn(self):
        a = self.args
        d = f"dbname={a.dbname} user={a.user} host={a.host} port={a.port}"
        return d + (f" password={a.password}" if a.password else "")

    def query_value(self, sql, db):
        """Run one query quietly; return (ok, first value or error text)."""
        r = subprocess.run(self.psql("-tA", "-v", "ON_ERROR_STOP=1", "-c", sql, db=db),
                           env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode == 0, r.stdout.strip()

    def ensure_database(self, rebuilding):
        """Check the server can be reached, create the database if it is missing,
        and (when Portfolio 1 is not being run) check its data is already loaded."""
        a = self.args
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", a.dbname):
            sys.exit(f"--dbname must be lower-case letters, digits and _ only (got {a.dbname!r}).")
        ok, out = self.query_value("SELECT version()", db="postgres")
        if not ok:
            sys.exit("Cannot connect to PostgreSQL (database 'postgres'):\n  " + out +
                     "\nCheck the server is running and pass --password (or set PGPASSWORD).")
        print(f"Connected: {out}")
        ok, out = self.query_value(f"SELECT 1 FROM pg_database WHERE datname = '{a.dbname}'", db="postgres")
        if out != "1":
            if not rebuilding:
                sys.exit(f"The {a.dbname} database does not exist yet. "
                         "Run Portfolio 1 first (add 1 to --portfolios); it creates and loads it.")
            self.step(P1, "create_database", f"Portfolio 1 - create the {a.dbname} database",
                      self.psql("-v", "ON_ERROR_STOP=1", "-c",
                                f"CREATE DATABASE {a.dbname} ENCODING 'UTF8' TEMPLATE template0",
                                db="postgres"), critical=True)
        if not rebuilding:
            ok, out = self.query_value("SELECT COUNT(*) FROM pipesafe.accident", db=a.dbname)
            if not ok or out in ("", "0"):
                sys.exit(f"The {a.dbname} database has no PipeSafe data yet. "
                         "Run Portfolio 1 first (add 1 to --portfolios).")

    def shown(self, cmd):
        text = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        if self.args.password:
            text = text.replace(self.args.password, "********")
        if self.args.mongo:
            text = text.replace(self.args.mongo, "mongodb+srv://********")
        return text.replace(sys.executable, "python").replace(self.psql_path(), "psql")

    def step(self, folder, name, title, cmd, cwd=None, save_as=None, critical=False, env=None, stdin=None):
        """Run one command, save its output as text + PNG (and optionally into results/)."""
        n = self.counter.get(folder, 0) + 1
        self.counter[folder] = n
        shots = os.path.join(folder, "screenshots")
        os.makedirs(shots, exist_ok=True)
        base = os.path.join(shots, f"{n:02d}_{name}")
        print(f"[{os.path.basename(folder)}] {title} ...", flush=True)
        r = subprocess.run(cmd, cwd=cwd or folder, env=env or self.env, input=stdin,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace")
        out = r.stdout.rstrip()
        if r.returncode != 0:
            out += f"\n\n[exit code {r.returncode}]"
            self.failures.append(f"{os.path.basename(folder)}: {title}")
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(out + "\n")
        if save_as:
            with open(os.path.join(folder, save_as), "w", encoding="utf-8") as f:
                f.write(out + "\n")
        render(title, self.shown(cmd), out, base + ".png")
        if r.returncode != 0 and critical:
            sys.exit(f"\nSTOPPED: '{title}' failed. See {base}.txt")
        return out

    def show_file(self, folder, name, title, path):
        """Screenshot of a results file (e.g. an execution plan)."""
        n = self.counter.get(folder, 0) + 1
        self.counter[folder] = n
        base = os.path.join(folder, "screenshots", f"{n:02d}_{name}")
        text = open(path, encoding="utf-8").read().rstrip()
        shutil.copyfile(path, base + ".txt")
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        render(title, f"type {rel}" if os.name == "nt" else f"cat {rel}", text, base + ".png")


# ------------------------------------------------------------------ portfolios
def portfolio_1(r, a):
    load_dir = os.path.join(P1, "load")
    r.step(P1, "create_tables", "Portfolio 1 - create the 20-table schema",
           r.psql("-f", "sql/01_create_tables.sql"), critical=True)
    r.step(P1, "prepare_load", "Portfolio 1 - split the PHMSA file into normalised CSVs",
           [PY, "scripts/prepare_load.py", a.data, load_dir], critical=True)
    r.step(P1, "load_data", "Portfolio 1 - load the CSVs (all constraints on)",
           r.psql("-f", "sql/02_load_data.sql"), critical=True)
    r.step(P1, "verify", "Portfolio 1 - verify row counts and totals against the source file",
           r.psql("-f", "sql/03_verify.sql"))
    r.step(P1, "table_list", "Portfolio 1 - tables in the pipesafe schema",
           r.psql("-c", r"\dt+ pipesafe.*"))


def portfolio_2(r, a):
    r.step(P2, "setup_bench", "Portfolio 2 - build the 100x scaled test copy",
           r.psql("-f", "sql/01_setup_bench.sql"), critical=True)
    r.step(P2, "benchmark", "Portfolio 2 - benchmark: median times before/after, result checks",
           [PY, "scripts/benchmark.py", r.dsn()], critical=True)
    for f, t in [("pipesafe_before_Q3", "Q3 date range BEFORE (real data): Seq Scan"),
                 ("pipesafe_after_Q3", "Q3 date range AFTER (real data): Index Scan"),
                 ("bench_before_Q4", "Q4 one operator BEFORE (scaled): Seq Scan"),
                 ("bench_after_Q4", "Q4 one operator AFTER (scaled): composite index"),
                 ("bench_before_Q6", "Q6 text search BEFORE (scaled): Seq Scan"),
                 ("bench_after_Q6", "Q6 text search AFTER (scaled): trigram index"),
                 ("bench_after_Q8b", "Q8b costliest accidents AFTER (scaled): materialised view")]:
        r.show_file(P2, "plan_" + f, "Portfolio 2 - " + t, os.path.join(P2, "results", f + ".txt"))
    r.step(P2, "write_cost", "Portfolio 2 - insert cost with and without the new indexes",
           r.psql("-f", "sql/04_write_cost.sql"), save_as="results/write_cost_run.txt")


def portfolio_3(r, a):
    for f, t in [("00_setup_test_data", "create two open test reports"),
                 ("01_commit", "COMMIT: new accident across four tables"),
                 ("02_rollback_on_error", "automatic ROLLBACK on a CHECK violation"),
                 ("03_explicit_rollback_and_savepoint", "explicit ROLLBACK and SAVEPOINT")]:
        r.step(P3, f, "Portfolio 3 - " + t, r.psql("-e", "-f", f"sql/{f}.sql"),
               save_as=f"results/{f}.log")
    # reset the test reports (as before the scenarios in transactions-report.md), no screenshot
    subprocess.run(r.psql("-q", "-f", "sql/00_setup_test_data.sql"), cwd=P3, env=r.env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    r.step(P3, "concurrency_demo", "Portfolio 3 - two sessions: isolation, lost update + fixes, deadlock",
           [PY, "scripts/concurrency_demo.py", r.dsn()])
    r.step(P3, "99_cleanup", "Portfolio 3 - remove test reports (6,052 remain)",
           r.psql("-e", "-f", "sql/99_cleanup.sql"), save_as="results/99_cleanup.log")


def portfolio_4(r, a):
    if not a.mongo:
        print("[portfolio-4-nosql] skipped: no --mongo connection string given")
        return
    data = os.path.join(P4, "data")
    r.step(P4, "build_documents", "Portfolio 4 - build accident and operator documents",
           [PY, "scripts/build_documents.py", a.data, data], critical=True)
    r.step(P4, "check_documents", "Portfolio 4 - check every document against the validator rules",
           [PY, "scripts/check_documents.py", os.path.join(data, "accidents.jsonl")])
    r.step(P4, "load_mongodb", "Portfolio 4 - load into MongoDB with validator and indexes",
           [PY, "scripts/load_mongodb.py", a.mongo, data], critical=True)
    r.step(P4, "run_queries", "Portfolio 4 - the ten MongoDB queries",
           [PY, "scripts/run_queries.py", a.mongo, os.path.join("results", "query_results_atlas.txt")])
    r.step(P4, "atlas_replica_set", "Portfolio 5 (cloud) - Atlas replica set check",
           [PY, os.path.join(P5, "scripts", "atlas_replica_check.py"), a.mongo], cwd=P5)


def portfolio_5(r, a):
    if os.name == "nt":
        print("[portfolio-5-distributed-cloud] skipped: run Portfolio 5 inside WSL/Linux")
        return
    if not a.pg_bin:
        sys.exit("Portfolio 5 needs --pg-bin (e.g. /usr/lib/postgresql/18/bin)")
    cluster = os.path.join(P5, "cluster")
    if os.path.exists(cluster):
        sys.exit(f"{cluster} already exists. Stop it (scripts/stop_cluster.sh ./cluster) and delete it first.")
    sock = "/tmp"
    env5 = dict(r.env, PG_BIN=a.pg_bin, SKIP_PAUSE="1", PGPASSWORD="")

    def ps(port, db, *extra):
        return [os.path.join(a.pg_bin, "psql"), "-h", sock, "-p", str(port), "-U", "postgres",
                "-d", db, "-X", *extra]

    r.step(P5, "setup_cluster", "Portfolio 5 - create primary, standby and two shards",
           ["bash", "scripts/setup_cluster.sh", cluster], env=env5, critical=True)
    load_dir = os.path.join(P1, "load")
    if not os.path.exists(os.path.join(load_dir, "accident.csv")):
        r.step(P5, "prepare_load", "Portfolio 5 - prepare the pipesafe CSVs",
               [PY, os.path.join(P1, "scripts", "prepare_load.py"), a.data, load_dir], cwd=P1, critical=True)
    r.step(P5, "load_primary", "Portfolio 5 - load pipesafe into the primary (streams to the standby)",
           ps(5601, "pipesafe", "-q", "-f", "sql/01_create_tables.sql", "-f", "sql/02_load_data.sql",
              "-c", "SELECT COUNT(*) AS accidents_on_primary FROM pipesafe.accident"),
           cwd=P1, env=env5, critical=True)
    r.step(P5, "replication_status", "Portfolio 5 - replication status on primary and standby",
           ["bash", "-c",
            f"echo '--- primary (5601)'; {' '.join(ps(5601, 'pipesafe'))} -c "
            "\"SELECT application_name, state, sync_state, replay_lag FROM pg_stat_replication;\"; "
            f"echo '--- standby (5602)'; {' '.join(ps(5602, 'pipesafe'))} -c "
            "\"SELECT pg_is_in_recovery() AS read_only_replica, COUNT(*) AS accidents FROM pipesafe.accident;\""],
           env=env5)
    for port in (5603, 5604):
        r.step(P5, f"shard_node_{port}", f"Portfolio 5 - create shard table on port {port}",
               ps(port, "pipesafe_shard", "-f", "sql/01_shard_node.sql"), env=env5)
    r.step(P5, "coordinator", "Portfolio 5 - distributed table over the two shards",
           ps(5601, "pipesafe", "-e", "-f", "sql/02_coordinator.sql"), env=env5,
           save_as="results/02_coordinator.log")
    r.step(P5, "sharding_queries", "Portfolio 5 - routing, pruning, scatter-gather, pushdown, skew",
           ps(5601, "pipesafe", "-e", "-f", "sql/03_sharding_queries.sql"), env=env5,
           save_as="results/03_sharding_queries.log")
    r.step(P5, "replication_demo", "Portfolio 5 - replication, sync vs async, standby failure, failover",
           [PY, "scripts/replication_demo.py", cluster, a.pg_bin, sock], env=env5)
    r.step(P5, "stop_cluster", "Portfolio 5 - stop the cluster",
           ["bash", "scripts/stop_cluster.sh", cluster], env=env5)


def main():
    p = argparse.ArgumentParser(description="Run the portfolio steps and capture screenshots.")
    p.add_argument("--portfolios", default="1,2,3,4", help="e.g. 1,2,3,4 or 5")
    p.add_argument("--data", required=True, help="path to accident_hazardous_liquid_jan2010_present.txt")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", default="5432")
    p.add_argument("--user", default="postgres")
    p.add_argument("--password", default=os.environ.get("PGPASSWORD", ""))
    p.add_argument("--dbname", default="pipesafe")
    p.add_argument("--mongo", default="")
    p.add_argument("--pg-bin", default="")
    a = p.parse_args()
    if not os.path.exists(a.data):
        sys.exit(f"Data file not found: {a.data}")
    r = Runner(a)
    wanted = [s.strip() for s in a.portfolios.split(",")]
    print(f"Evidence stamp: {STAMP}\n")
    if any(k in wanted for k in ("1", "2", "3")):      # these use the local PostgreSQL server
        r.ensure_database(rebuilding="1" in wanted)
    for key, fn in [("1", portfolio_1), ("2", portfolio_2), ("3", portfolio_3),
                    ("4", portfolio_4), ("5", portfolio_5)]:
        if key in wanted:
            fn(r, a)
    print("\nDone. Screenshots are in each portfolio's screenshots/ folder.")
    if r.failures:
        print("These steps reported errors (check their .txt files):")
        for f in r.failures:
            print("  -", f)


if __name__ == "__main__":
    main()
