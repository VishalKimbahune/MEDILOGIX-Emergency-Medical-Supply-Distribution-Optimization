"""
Idempotent, non-destructive additive schema migration helper (Phase 5 & Auth Redesign).

Ensures newly added nullable columns exist on pre-existing SQLite/PostgreSQL
databases without resetting tables or altering historical records.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# (table_name, column_name, sql_column_definition)
ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    # Phase 5 Stage 3
    ("vehicle_assignments", "route_geometry_json", "JSON"),
    # Redesign: Demand approval & multi-line order grouping
    ("demands", "order_group_code", "VARCHAR(40)"),
    ("demands", "approval_status", "VARCHAR(32) DEFAULT 'approved'"),
    ("demands", "emergency_reason", "TEXT"),
    ("demands", "required_by", "DATETIME"),
    ("demands", "rejection_reason", "TEXT"),
    ("demands", "submitted_by_user_id", "INTEGER"),
    ("demands", "reviewed_by_user_id", "INTEGER"),
    ("demands", "reviewed_at", "DATETIME"),
    # Redesign: Driver assignment & warehouse shipment preparation
    ("vehicles", "assigned_driver_user_id", "INTEGER"),
    ("vehicle_assignments", "assigned_driver_user_id", "INTEGER"),
    ("vehicle_assignments", "preparation_status", "VARCHAR(32) DEFAULT 'pending'"),
    ("vehicle_assignments", "preparation_notes", "VARCHAR(255)"),
    ("vehicle_assignments", "prepared_at", "DATETIME"),
    ("delivery_stops", "confirmed_by_user_id", "INTEGER"),
    ("delivery_stops", "confirmed_at", "DATETIME"),
]


def ensure_additive_columns(target_engine: Engine) -> list[str]:
    """
    Inspect existing database tables and apply safe additive ALTER TABLE statements
    for any missing columns. Preserves 100% of existing rows and IDs.

    Returns a list of applied migration identifiers (`table.column`).
    """
    applied: list[str] = []
    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())

    cols_by_table: dict[str, set[str]] = {}
    for table_name, col_name, col_def in ADDITIVE_COLUMNS:
        if table_name not in existing_tables:
            continue
        if table_name not in cols_by_table:
            cols_by_table[table_name] = {
                col["name"] for col in inspector.get_columns(table_name)
            }
        if col_name not in cols_by_table[table_name]:
            with target_engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
            cols_by_table[table_name].add(col_name)
            ident = f"{table_name}.{col_name}"
            applied.append(ident)
            logger.info("Applied additive column migration: %s", ident)

    return applied
