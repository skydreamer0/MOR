import sqlite3
from pathlib import Path
from typing import Optional

class MORDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            # Sales Records (Normalized from 業績明細)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sales_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_date DATE NOT NULL,
                    customer_name TEXT NOT NULL,
                    product_code TEXT NOT NULL,
                    product_name TEXT,
                    quantity REAL DEFAULT 0,
                    unit_price REAL DEFAULT 0,
                    amount REAL DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_records(order_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales_records(product_code)")
            # Migration: add amount column if upgrading from older DB
            sales_cols = [col[1] for col in conn.execute("PRAGMA table_info(sales_records)").fetchall()]
            if "amount" not in sales_cols:
                conn.execute("ALTER TABLE sales_records ADD COLUMN amount REAL DEFAULT 0")

            # Item Configs (Global management)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS item_configs (
                    product_code TEXT PRIMARY KEY,
                    is_excluded INTEGER DEFAULT 0,
                    is_budgeted INTEGER DEFAULT 1,
                    is_visible INTEGER DEFAULT 1,
                    price_quantity REAL DEFAULT 0,
                    item_status TEXT DEFAULT 'active',
                    status_label TEXT, -- e.g., 'Discontinued', 'Special'
                    custom_category TEXT
                )
            """)

            # Simple migration for item_configs
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(item_configs)")
            cols = [col[1] for col in cursor.fetchall()]
            if 'is_budgeted' not in cols:
                conn.execute("ALTER TABLE item_configs ADD COLUMN is_budgeted INTEGER DEFAULT 1")
            if 'is_visible' not in cols:
                conn.execute("ALTER TABLE item_configs ADD COLUMN is_visible INTEGER DEFAULT 1")
            if 'price_quantity' not in cols:
                conn.execute("ALTER TABLE item_configs ADD COLUMN price_quantity REAL DEFAULT 0")
            if 'item_status' not in cols:
                conn.execute("ALTER TABLE item_configs ADD COLUMN item_status TEXT DEFAULT 'active'")
            if 'status_label' not in cols:
                conn.execute("ALTER TABLE item_configs ADD COLUMN status_label TEXT")
            if 'custom_category' not in cols:
                conn.execute("ALTER TABLE item_configs ADD COLUMN custom_category TEXT")
            conn.execute("""
                UPDATE item_configs
                SET item_status = 'discontinued'
                WHERE status_label = '停用'
                  AND (item_status IS NULL OR item_status = '' OR item_status = 'active')
            """)

            # Forecast Adjustments (User overrides)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forecast_adjustments (
                    year INTEGER,
                    month INTEGER,
                    customer_name TEXT,
                    product_code TEXT,
                    manual_quantity REAL,
                    adjustment_reason TEXT,
                    updated_by TEXT DEFAULT 'System',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (year, month, customer_name, product_code)
                )
            """)
            cursor.execute("PRAGMA table_info(forecast_adjustments)")
            adjustment_cols = [col[1] for col in cursor.fetchall()]
            if 'updated_by' not in adjustment_cols:
                conn.execute("ALTER TABLE forecast_adjustments ADD COLUMN updated_by TEXT DEFAULT 'System'")

            # Snapshots (Versioning)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forecast_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_name TEXT NOT NULL,
                    snapshot_type TEXT, -- e.g., 'Draft', 'Final'
                    year INTEGER,
                    month INTEGER,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshot_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER,
                    customer_name TEXT,
                    product_code TEXT,
                    system_forecast REAL,
                    manual_adjustment REAL,
                    final_forecast REAL,
                    FOREIGN KEY (snapshot_id) REFERENCES forecast_snapshots(id)
                )
            """)

            # Budget Targets (From 2026預算報表)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budget_targets (
                    year INTEGER,
                    month INTEGER,
                    customer_name TEXT,
                    product_code TEXT,
                    target_quantity REAL DEFAULT 0,
                    target_amount REAL DEFAULT 0,
                    base_target_quantity REAL DEFAULT 0,
                    PRIMARY KEY (year, month, customer_name, product_code)
                )
            """)
            cursor.execute("PRAGMA table_info(budget_targets)")
            budget_cols = [col[1] for col in cursor.fetchall()]
            if 'target_amount' not in budget_cols:
                conn.execute("ALTER TABLE budget_targets ADD COLUMN target_amount REAL DEFAULT 0")
            if 'base_target_quantity' not in budget_cols:
                conn.execute("ALTER TABLE budget_targets ADD COLUMN base_target_quantity REAL DEFAULT 0")

            # Workday Calendar (Phase 2: Taiwan official office-day data)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workday_calendar (
                    date TEXT PRIMARY KEY,
                    is_workday INTEGER NOT NULL DEFAULT 1,
                    holiday_name TEXT,
                    source TEXT,
                    note TEXT
                )
            """)

            # Daily Sales Import (Phase 1: current-month actuals)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_import_batches (
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
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_sales_actuals (
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
                )
            """)
            # Composite index for month-range scans; row-level index for customer+product aggregation
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_actuals_month ON daily_sales_actuals(sales_year, sales_month)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_actuals_row ON daily_sales_actuals(customer_name, product_code)")

            conn.commit()

def get_db(project_root: Path) -> MORDatabase:
    db_path = project_root / "mor_workbench.db"
    return MORDatabase(db_path)
