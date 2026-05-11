"""MOR Workbench Database

Single SQLite file (mor_workbench.db) with two sales data tables:

- sales_records          歷史業績，來源為月底更新的業績明細 Excel，sync 時整批覆蓋。
- current_month_records  當月累積業績，來源為使用者隨時上傳的 SHPB 報表，
                         上傳時只取代當月，月底 sync 後自動清除。

兩表的欄位結構相同；load_sales_detail() 在讀取時合併兩者，
forecast_engine 永遠只看合併後的結果，不感知資料來源的差異。
詳見 docs/architecture/current-month-data-integration.md。

Migration strategy
------------------
All schema changes go into _MIGRATIONS as (version, [sql, ...]) tuples.
_apply_migrations() creates schema_migrations on first run, then applies
only versions not yet recorded — so startup cost is one SELECT instead of
N PRAGMA table_info() calls.

ALTER TABLE migrations are wrapped in _exec_tolerant() which ignores
"duplicate column name" errors so they are safe to run against DBs that
already have the column (either from a previous migration or from being
created fresh with the full schema in migration 1).
"""
import sqlite3
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema migrations — add new entries at the end; never modify existing ones.
# ---------------------------------------------------------------------------

_MIGRATIONS: list[tuple[int, list[str]]] = [
    # 1 — full initial schema (all tables with all columns as of this version)
    (1, [
        """CREATE TABLE IF NOT EXISTS sales_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_date DATE NOT NULL,
            customer_name TEXT NOT NULL,
            product_code TEXT NOT NULL,
            product_name TEXT,
            quantity REAL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            amount REAL DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_records(order_date)",
        "CREATE INDEX IF NOT EXISTS idx_sales_product ON sales_records(product_code)",
        """CREATE TABLE IF NOT EXISTS item_configs (
            product_code TEXT PRIMARY KEY,
            is_excluded INTEGER DEFAULT 0,
            is_budgeted INTEGER DEFAULT 1,
            is_visible INTEGER DEFAULT 1,
            price_quantity REAL DEFAULT 0,
            item_status TEXT DEFAULT 'active',
            status_label TEXT,
            custom_category TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS forecast_adjustments (
            year INTEGER,
            month INTEGER,
            customer_name TEXT,
            product_code TEXT,
            manual_quantity REAL,
            adjustment_reason TEXT,
            updated_by TEXT DEFAULT 'System',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (year, month, customer_name, product_code)
        )""",
        """CREATE TABLE IF NOT EXISTS forecast_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_name TEXT NOT NULL,
            snapshot_type TEXT,
            year INTEGER,
            month INTEGER,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS snapshot_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER,
            customer_name TEXT,
            product_code TEXT,
            system_forecast REAL,
            manual_adjustment REAL,
            final_forecast REAL,
            FOREIGN KEY (snapshot_id) REFERENCES forecast_snapshots(id)
        )""",
        """CREATE TABLE IF NOT EXISTS current_month_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_date DATE NOT NULL,
            customer_name TEXT NOT NULL,
            product_code TEXT NOT NULL,
            product_name TEXT,
            quantity REAL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            amount REAL DEFAULT 0,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cmr_date ON current_month_records(order_date)",
        "CREATE INDEX IF NOT EXISTS idx_cmr_product ON current_month_records(product_code)",
        """CREATE TABLE IF NOT EXISTS budget_targets (
            year INTEGER,
            month INTEGER,
            customer_name TEXT,
            product_code TEXT,
            target_quantity REAL DEFAULT 0,
            target_amount REAL DEFAULT 0,
            base_target_quantity REAL DEFAULT 0,
            PRIMARY KEY (year, month, customer_name, product_code)
        )""",
        """CREATE TABLE IF NOT EXISTS workday_calendar (
            date TEXT PRIMARY KEY,
            is_workday INTEGER NOT NULL DEFAULT 1,
            holiday_name TEXT,
            source TEXT,
            note TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS month_close_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_batch_id INTEGER,
            actual_row_count INTEGER DEFAULT 0,
            actual_quantity_total REAL DEFAULT 0,
            actual_amount_total REAL DEFAULT 0,
            note TEXT,
            final_snapshot_id INTEGER,
            UNIQUE (year, month)
        )""",
        """CREATE TABLE IF NOT EXISTS daily_import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_filename TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            sales_year INTEGER NOT NULL,
            sales_month INTEGER NOT NULL,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER DEFAULT 0,
            date_start DATE,
            date_end DATE,
            quantity_total REAL DEFAULT 0,
            taxed_amount_total REAL DEFAULT 0,
            status TEXT DEFAULT 'success',
            message TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS daily_sales_actuals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sales_year INTEGER NOT NULL,
            sales_month INTEGER NOT NULL,
            sales_date DATE NOT NULL,
            customer_code TEXT,
            customer_name TEXT NOT NULL,
            product_code TEXT NOT NULL,
            product_name TEXT,
            sales_quantity REAL DEFAULT 0,
            gift_quantity REAL DEFAULT 0,
            actual_quantity REAL DEFAULT 0,
            net_unit_price REAL DEFAULT 0,
            taxed_amount REAL DEFAULT 0,
            bonus_basis_amount REAL DEFAULT 0,
            invoice_number TEXT,
            shipment_number TEXT,
            order_type TEXT,
            performance_type TEXT,
            import_batch_id INTEGER,
            FOREIGN KEY (import_batch_id) REFERENCES daily_import_batches(id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_daily_actuals_month ON daily_sales_actuals(sales_year, sales_month)",
        "CREATE INDEX IF NOT EXISTS idx_daily_actuals_row ON daily_sales_actuals(customer_name, product_code)",
    ]),

    # 2 — backfill: sales_records.amount for DBs created before this column existed
    (2, ["ALTER TABLE sales_records ADD COLUMN amount REAL DEFAULT 0"]),

    # 3 — backfill: item_configs columns added incrementally over time
    (3, [
        "ALTER TABLE item_configs ADD COLUMN is_budgeted INTEGER DEFAULT 1",
        "ALTER TABLE item_configs ADD COLUMN is_visible INTEGER DEFAULT 1",
        "ALTER TABLE item_configs ADD COLUMN price_quantity REAL DEFAULT 0",
        "ALTER TABLE item_configs ADD COLUMN item_status TEXT DEFAULT 'active'",
        "ALTER TABLE item_configs ADD COLUMN status_label TEXT",
        "ALTER TABLE item_configs ADD COLUMN custom_category TEXT",
    ]),

    # 4 — data migration: normalise legacy '停用' label to item_status = 'discontinued'
    (4, [
        """UPDATE item_configs
           SET item_status = 'discontinued'
           WHERE status_label = '停用'
             AND (item_status IS NULL OR item_status = '' OR item_status = 'active')""",
    ]),

    # 5 — backfill: forecast_adjustments.updated_by
    (5, ["ALTER TABLE forecast_adjustments ADD COLUMN updated_by TEXT DEFAULT 'System'"]),

    # 6 — backfill: budget_targets amount and base quantity columns
    (6, [
        "ALTER TABLE budget_targets ADD COLUMN target_amount REAL DEFAULT 0",
        "ALTER TABLE budget_targets ADD COLUMN base_target_quantity REAL DEFAULT 0",
    ]),

    # 7 — backfill: month_close_records.final_snapshot_id
    (7, ["ALTER TABLE month_close_records ADD COLUMN final_snapshot_id INTEGER"]),
]


def _exec_tolerant(conn: sqlite3.Connection, sql: str) -> None:
    """Execute sql; silently skip 'duplicate column name' errors from ALTER TABLE."""
    try:
        conn.execute(sql)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc):
            raise


def _apply_migrations(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    for version, statements in _MIGRATIONS:
        if version in applied:
            continue
        for sql in statements:
            _exec_tolerant(conn, sql)
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
    conn.commit()


class MORDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            _apply_migrations(conn)


def get_db(project_root: Path) -> MORDatabase:
    db_path = project_root / "mor_workbench.db"
    return MORDatabase(db_path)
