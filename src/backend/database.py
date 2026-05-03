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
                    unit_price REAL DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_records(order_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales_records(product_code)")

            # Item Configs (Global management)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS item_configs (
                    product_code TEXT PRIMARY KEY,
                    is_excluded INTEGER DEFAULT 0,
                    is_budgeted INTEGER DEFAULT 1,
                    is_visible INTEGER DEFAULT 1,
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
            if 'status_label' not in cols:
                conn.execute("ALTER TABLE item_configs ADD COLUMN status_label TEXT")

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
                    PRIMARY KEY (year, month, customer_name, product_code)
                )
            """)

            conn.commit()

def get_db(project_root: Path) -> MORDatabase:
    db_path = project_root / "mor_workbench.db"
    return MORDatabase(db_path)
