"""
Database Module - All database operations in one place
"""
from __future__ import annotations

from __future__ import annotations

import os
import re
from typing import Any, Optional

from shared.db_connection import DB_ENGINE, get_db_connection


def _normalize_placeholders(sql: str) -> str:
    """Convert SQLite-style placeholders (? placeholders) to PostgreSQL (%s).

    This keeps existing SQL in the app working while we migrate.
    """
    if DB_ENGINE != "postgres":
        return sql

    # Only replace plain ? tokens that are used as placeholders.
    # This heuristic is adequate for the current codebase.
    return re.sub(r"\?(?![\w\d])", "%s", sql)


class Database:
    """Centralized DB wrapper.

    - PostgreSQL: uses psycopg2 RealDictCursor (dict rows)
    - SQLite fallback: uses sqlite3 with row access by column name

    Important: callers provide SQL using '?' placeholders (legacy).
    For Postgres, we convert '?' to '%s'.
    """

    @staticmethod
    def execute(sql: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
        sql = _normalize_placeholders(sql)
        conn = None
        try:
            conn = get_db_connection()

            # psycopg2 uses cursors; sqlite3 supports conn.execute.
            # Using cursor() for both improves consistency.
            with conn.cursor() as cur:
                cur.execute(sql, params)

                if fetch_one:
                    return cur.fetchone()
                if fetch_all:
                    return cur.fetchall()

                conn.commit()
                # For non-select operations, return nothing.
                return None
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @staticmethod
    def fetch_one(sql: str, params: tuple = ()):
        return Database.execute(sql, params=params, fetch_one=True)

    @staticmethod
    def fetch_all(sql: str, params: tuple = ()):
        return Database.execute(sql, params=params, fetch_all=True)

    @staticmethod
    def insert(table: str, data: dict[str, Any]):
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING id"
        row = Database.fetch_one(sql, tuple(data.values()))
        # psycopg2 RETURNING id -> dict row has key 'id'
        if not row:
            return None
        return row["id"] if isinstance(row, dict) else row[0]

    @staticmethod
    def update(table: str, data: dict[str, Any], where_clause: str, where_params: tuple):
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = tuple(data.values()) + tuple(where_params)
        Database.execute(sql, params=params)

    @staticmethod
    def delete(table: str, where_clause: str, where_params: tuple):
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        Database.execute(sql, params=tuple(where_params))


# Quick access functions
def get_stats():
    """Get booking statistics"""
    stats = {}
    
    # Bus bookings
    result = Database.fetch_one("SELECT COUNT(*) as cnt FROM BusBookings")
    stats['total_bus'] = result['cnt'] if result else 0
    
    result = Database.fetch_one("SELECT COUNT(*) as cnt FROM BusBookings WHERE status IN ('Pending', 'Confirmed')")
    stats['active_bus'] = result['cnt'] if result else 0
    
    result = Database.fetch_one("SELECT COALESCE(SUM(price), 0) as total FROM BusBookings WHERE status='Confirmed'")
    stats['bus_revenue'] = float(result['total']) if result else 0
    
    # Resort bookings
    result = Database.fetch_one("SELECT COUNT(*) as cnt FROM ResortBookings")
    stats['total_resort'] = result['cnt'] if result else 0
    
    result = Database.fetch_one("SELECT COUNT(*) as cnt FROM ResortBookings WHERE status IN ('Pending', 'Confirmed')")
    stats['active_resort'] = result['cnt'] if result else 0
    
    result = Database.fetch_one("SELECT COALESCE(SUM(price), 0) as total FROM ResortBookings WHERE status='Confirmed'")
    stats['resort_revenue'] = float(result['total']) if result else 0
    
    # Combined
    stats['total_bookings'] = stats['total_bus'] + stats['total_resort']
    stats['active_bookings'] = stats['active_bus'] + stats['active_resort']
    stats['total_revenue'] = stats['bus_revenue'] + stats['resort_revenue']
    
    return stats

def get_bookings(booking_type, status=None, limit=100):
    """Get bookings with optional filter"""
    table = 'BusBookings' if booking_type == 'bus' else 'ResortBookings'
    
    query = f"SELECT * FROM {table}"
    params = []
    
    if status:
        query += " WHERE status = ?"
        params.append(status)
    
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    return Database.fetch_all(query, params)

def update_booking_status(booking_type, booking_id, status):
    """Update booking status"""
    table = 'BusBookings' if booking_type == 'bus' else 'ResortBookings'
    Database.update(table, {'status': status}, 'id = ?', (booking_id,))

def get_settings():
    """Get website settings"""
    return Database.fetch_one("SELECT * FROM WebsiteSettings WHERE id = 1")

def update_settings(data):
    """Update website settings"""
    Database.update('WebsiteSettings', data, 'id = 1', ())
