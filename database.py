"""
Database Module - All database operations in one place
"""
import sqlite3
from config import DB_PATH, DB_TIMEOUT

class Database:
    """Simple database wrapper with connection management"""
    
    @staticmethod
    def get_connection():
        """Get database connection with proper settings"""
        conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute(f'PRAGMA busy_timeout={int(timeout * 1000)}')
        return conn
    
    @staticmethod
    def execute(query, params=(), fetch_one=False, fetch_all=False):
        """Execute query with automatic connection management"""
        conn = None
        try:
            conn = Database.get_connection()
            cursor = conn.execute(query, params)
            
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            else:
                conn.commit()
                result = cursor.lastrowid
            
            return result
        except Exception as e:
            print(f"[DB] Error executing query: {e}")
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    @staticmethod
    def fetch_one(query, params=()):
        """Fetch single row"""
        return Database.execute(query, params, fetch_one=True)
    
    @staticmethod
    def fetch_all(query, params=()):
        """Fetch all rows"""
        return Database.execute(query, params, fetch_all=True)
    
    @staticmethod
    def insert(table, data):
        """Insert data into table"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return Database.execute(query, tuple(data.values()))
    
    @staticmethod
    def update(table, data, where_clause, where_params):
        """Update table with data"""
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = tuple(data.values()) + where_params
        Database.execute(query, params)
    
    @staticmethod
    def delete(table, where_clause, where_params):
        """Delete from table"""
        query = f"DELETE FROM {table} WHERE {where_clause}"
        Database.execute(query, where_params)

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
